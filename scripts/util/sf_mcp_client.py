"""scripts/util/sf_mcp_client.py — D-SF-14 reusable HTTP MCP client (first one).

Establishes the canonical HTTP MCP client pattern for PSEO. v1.8 SF MCP
integration is the first consumer; future HTTP MCPs (local LM Studio,
custom servers) reuse this class instead of re-implementing the MCP
Streamable-HTTP plumbing in each orchestrator.

Protocol: **MCP Streamable-HTTP transport** (JSON-RPC 2.0 over HTTP, MCP
revision 2024-11-05). This is a stateful, session-based transport — it is
NOT a bare JSON-RPC POST. Three things are mandatory on every request:

    1. ``Accept: application/json, text/event-stream`` — the server rejects
       requests that do not advertise BOTH media types (HTTP 400 ``-32600``).
    2. ``Content-Type: application/json``.
    3. ``Mcp-Session-Id: <uuid>`` — obtained from the *response header* of an
       ``initialize`` call. Tool calls without it return HTTP 400 ``-32600``
       ``"Session ID required in mcp-session-id header"``.

Handshake (performed lazily on first ``call_tool`` / ``health``):

    STEP 1 — ``initialize`` (POST). The server returns HTTP 200 with the new
             session id in the ``Mcp-Session-Id`` **response header** and an
             ``initialize`` result in the body.
    STEP 2 — ``notifications/initialized`` (POST, carries the session id).
             A JSON-RPC *notification* (no ``id``) → server returns HTTP 202
             with an empty body. No JSON-RPC response is expected.
    STEP 3 — ``tools/call`` (POST, carries the session id)::

                 {"jsonrpc": "2.0", "id": <uuid>, "method": "tools/call",
                  "params": {"name": tool_name, "arguments": kwargs}}

Response media types — the server replies to ``tools/call`` with EITHER:

    * ``application/json``  → the body IS the JSON-RPC envelope, OR
    * ``text/event-stream`` → Server-Sent-Events; the JSON-RPC envelope is the
      ``data:`` payload of an ``event: message`` frame. (The live SF server
      uses SSE for tool calls and JSON for ``initialize``.)

Both are parsed transparently; ``call_tool`` always returns the JSON-RPC
``result`` (dict). Note the distinction between two error layers:

    * **JSON-RPC protocol error** — top-level ``error`` field present →
      :class:`SfMcpToolError`.
    * **MCP tool-level error** — ``result.isError == true`` (e.g. the Spider is
      not in a callable state). This is returned to the caller AS-IS inside the
      ``result`` dict; the transport succeeded, so it is the consumer skill's
      job to interpret ``isError``. (Preserves the v1.8 contract: ``call_tool``
      only raises on transport / protocol faults, never on tool semantics.)

Reliability:
    * Connection errors / timeouts on a ``tools/call``: 3 attempts with
      exponential backoff (1s, 2s before attempts 2 and 3). HTTP 4xx and 5xx
      are NOT retried — 4xx is a caller-side fault and 5xx indicates a
      server-side failure that retrying won't fix.
    * Session expiry: if a ``tools/call`` fails with a session error (HTTP 400
      whose body mentions the session id header), the session is re-initialized
      ONCE and the call retried.
    * Response size cap: raises :class:`SfMcpResponseTooLargeError` when
      Content-Length OR the actual body bytes exceed ``max_response_bytes``
      (default 100,000 bytes per D-SF-05).

Logging: every call writes one stderr line in the PSEO ingestion convention
``[sf_mcp_client] {method} {tool} → {status}``.

Refs:
    * D-SF-14 — first HTTP MCP client, reusable pattern
    * D-SF-05 — Max Response Size 100,000 bytes default
    * scripts/ingestion/scrapling_ops.py — sister stdio MCP wrapper pattern
    * MCP spec 2024-11-05 — Streamable-HTTP transport (Mcp-Session-Id, SSE)
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

import httpx

__all__ = (
    "SfMcpError",
    "SfMcpConnectionError",
    "SfMcpTimeoutError",
    "SfMcpResponseTooLargeError",
    "SfMcpToolError",
    "SfMcpClient",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "RETRY_DELAYS_SECONDS",
    "MCP_PROTOCOL_VERSION",
    "MCP_ACCEPT_HEADER",
    "SESSION_ID_HEADER",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SfMcpError(Exception):
    """Base class for sf_mcp_client errors."""


class SfMcpConnectionError(SfMcpError):
    """Connection failure after all retry attempts exhausted."""


class SfMcpTimeoutError(SfMcpError):
    """Request timed out after all retry attempts exhausted."""


class SfMcpResponseTooLargeError(SfMcpError):
    """Response payload exceeds ``max_response_bytes`` cap (D-SF-05 100KB default)."""


class SfMcpToolError(SfMcpError):
    """HTTP 4xx/5xx OR JSON-RPC ``error`` field present in response.

    Note: a successful tool result that carries ``isError == true`` (an
    MCP tool-level error, e.g. "Spider not in a callable state") does NOT
    raise this — that result is returned to the caller as-is. This exception
    is reserved for transport / JSON-RPC protocol faults.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        rpc_error: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.rpc_error = rpc_error


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Per D-SF-05: SF default Max Response Size = 100,000 bytes.
DEFAULT_MAX_RESPONSE_BYTES: int = 100_000

#: Delays (in seconds) BETWEEN attempts. 3 attempts total → 2 sleeps are used
#: (1s after attempt 1, 2s after attempt 2). 4s is the documented next step in
#: the canonical 1·2^n exp-backoff schedule but is never slept in this client
#: because attempt 3 is terminal — included so the schedule is self-documenting.
RETRY_DELAYS_SECONDS: tuple[float, ...] = (1.0, 2.0, 4.0)

#: MCP protocol revision negotiated in ``initialize``. Matches the live
#: seospider-mcp-server (which advertises 2024-11-05).
MCP_PROTOCOL_VERSION: str = "2024-11-05"

#: The server REQUIRES both media types in Accept or it returns HTTP 400
#: ``-32600``. This exact header is sent on every post-handshake request.
MCP_ACCEPT_HEADER: str = "application/json, text/event-stream"

#: Header name carrying the MCP session id (case-insensitive per HTTP; httpx
#: lower-cases header lookups, so reads are robust to server casing).
SESSION_ID_HEADER: str = "Mcp-Session-Id"


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SfMcpClient:
    """MCP Streamable-HTTP client for SF MCP and future HTTP MCPs (D-SF-14).

    The transport is **stateful**: a session is established lazily (on the
    first :meth:`health` or :meth:`call_tool`) via the MCP handshake and the
    resulting ``Mcp-Session-Id`` is cached on the instance and replayed on
    every subsequent request.

    Args:
        base_url: Base URL of the MCP server (e.g. ``http://127.0.0.1:11435/mcp``).
            Trailing slash is stripped; the path is posted to verbatim.
        timeout_seconds: Per-request HTTP timeout. Default 30s. The orchestrator
            (skill body) owns cumulative poll timeouts; this client only knows
            about single-request timeouts.
        max_response_bytes: Hard cap on response body size; default 100,000 per
            D-SF-05. Raises :class:`SfMcpResponseTooLargeError` if exceeded.
        transport: Optional :class:`httpx.BaseTransport` for test injection
            (e.g. :class:`httpx.MockTransport`). When None a real network
            transport is used. A single transport handler serves the whole
            session (initialize → initialized → tools/call).
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError(f"base_url must be a non-empty string, got {base_url!r}")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = int(max_response_bytes)
        self._transport = transport
        #: Cached MCP session id (set by :meth:`_ensure_session`). ``None``
        #: means "no live session" → next call performs the handshake.
        self._session_id: str | None = None
        #: Persistent httpx client (lazy). Persisting it keeps an injected
        #: MockTransport handler consistent across handshake + tool calls and
        #: lets a real connection pool be reused for the session's lifetime.
        self._client: httpx.Client | None = None

    # ---- public API ------------------------------------------------------

    def health(self) -> bool:
        """Real liveness probe — there is **no** ``/health`` route on the server.

        Attempts the MCP ``initialize`` handshake with a short timeout and
        returns ``True`` iff it succeeds (HTTP 200 + a session id in the
        response header). Returns ``False`` on ANY failure (connection refused,
        timeout, non-200, missing session id) and never raises — F-26's crawl
        gate depends on a fast, non-throwing boolean.

        A successful probe also warms the session cache, so a subsequent
        :meth:`call_tool` reuses it instead of re-handshaking.
        """
        try:
            session_id = self._do_initialize()
        except Exception as exc:  # noqa: BLE001 — health is non-raising by contract
            self._log("POST", "health", f"down: {type(exc).__name__}: {exc}")
            return False
        ok = bool(session_id)
        if ok:
            # Warm the cache: complete the handshake so the session is usable.
            self._session_id = session_id
            try:
                self._send_initialized(session_id)
            except Exception as exc:  # noqa: BLE001 — best-effort warm-up
                # Probe still counts as "alive" (we got a session); the next
                # call_tool will re-handshake if this left the session unusable.
                self._session_id = None
                self._log("POST", "health", f"up but initialized-notify failed: {exc}")
        self._log("POST", "health", f"up ok={ok}")
        return ok

    def call_tool(self, tool_name: str, **kwargs: Any) -> dict:
        """Invoke an MCP tool via the Streamable-HTTP ``tools/call`` method.

        Ensures a live MCP session (lazy handshake) then POSTs::

            {"jsonrpc": "2.0", "id": <uuid>, "method": "tools/call",
             "params": {"name": tool_name, "arguments": kwargs}}

        Retry policy:
            * 3 attempts total on connection errors / timeouts, with delays
              (1s, 2s) BETWEEN attempts.
            * HTTP 4xx (non-session) / 5xx: NO retry → :class:`SfMcpToolError`.
            * Session error (HTTP 400 mentioning the session header): the
              session is re-initialized ONCE and the call retried.
            * Response size exceeded: NO retry → :class:`SfMcpResponseTooLargeError`.

        Returns:
            The ``result`` field of the JSON-RPC envelope (dict). A non-dict
            ``result`` is wrapped as ``{"value": <result>}``. An MCP tool-level
            error (``result.isError == true``) is returned as-is — it does NOT
            raise.

        Raises:
            ValueError: ``tool_name`` is empty / not a string.
            SfMcpConnectionError: connection failed after all attempts.
            SfMcpTimeoutError:    timed out after all attempts.
            SfMcpToolError:       4xx/5xx OR JSON-RPC ``error`` field present.
            SfMcpResponseTooLargeError: response body exceeds cap.
        """
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError(f"tool_name must be a non-empty string, got {tool_name!r}")

        # One automatic re-handshake on a stale/expired session.
        session_retried = False
        while True:
            self._ensure_session()
            envelope = {
                "jsonrpc": "2.0",
                "id": uuid.uuid4().hex,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": dict(kwargs)},
            }
            try:
                resp = self._post_with_retry(envelope, tool_name)
                return self._handle_tool_response(resp, tool_name)
            except SfMcpToolError as exc:
                if (
                    not session_retried
                    and exc.status_code == 400
                    and _is_session_error(exc)
                ):
                    self._log("POST", tool_name,
                              "session error → re-initializing once and retrying")
                    self._invalidate_session()
                    session_retried = True
                    continue
                raise

    def close(self) -> None:
        """Close the underlying httpx client (idempotent)."""
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None
        self._session_id = None

    def __enter__(self) -> "SfMcpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ---- session handshake ----------------------------------------------

    def _ensure_session(self) -> str:
        """Return a live session id, performing the MCP handshake if needed."""
        if self._session_id:
            return self._session_id
        session_id = self._do_initialize()
        if not session_id:
            raise SfMcpToolError(
                "MCP initialize returned no Mcp-Session-Id response header"
            )
        self._send_initialized(session_id)
        self._session_id = session_id
        return session_id

    def _invalidate_session(self) -> None:
        self._session_id = None

    def _do_initialize(self) -> str | None:
        """POST ``initialize``; return the ``Mcp-Session-Id`` response header.

        Raises on HTTP error / non-JSON body so :meth:`health` can treat any
        failure as "down". The body is validated as a JSON-RPC envelope but its
        ``result`` is not returned — only the session id header matters.
        """
        envelope = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "initialize",
            "params": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "pseo-engine", "version": "1.9.1"},
            },
        }
        resp = self._post_once(envelope)
        self._enforce_size_cap(resp, "initialize")
        if not (200 <= resp.status_code < 300):
            raise SfMcpToolError(
                f"HTTP {resp.status_code} from MCP initialize: {resp.text[:200]}",
                status_code=resp.status_code,
            )
        session_id = resp.headers.get(SESSION_ID_HEADER)
        # Parse the body to surface a JSON-RPC error (e.g. protocol mismatch).
        payload = self._parse_envelope(resp, "initialize")
        rpc_err = payload.get("error")
        if rpc_err is not None:
            raise SfMcpToolError(
                f"JSON-RPC error during initialize: {_rpc_error_message(rpc_err)}",
                rpc_error=rpc_err if isinstance(rpc_err, dict) else None,
            )
        self._log("POST", "initialize",
                  f"status={resp.status_code} session={'yes' if session_id else 'MISSING'}")
        return session_id

    def _send_initialized(self, session_id: str) -> None:
        """POST the ``notifications/initialized`` notification (no response body).

        It is a JSON-RPC notification (no ``id``); the server replies HTTP 202
        with an empty body. We only assert the status is 2xx.
        """
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        resp = self._post_once(notification, session_id=session_id)
        if not (200 <= resp.status_code < 300):
            raise SfMcpToolError(
                f"HTTP {resp.status_code} from notifications/initialized: "
                f"{resp.text[:200]}",
                status_code=resp.status_code,
            )
        self._log("POST", "notifications/initialized", f"status={resp.status_code}")

    # ---- transport -------------------------------------------------------

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout_seconds,
                transport=self._transport,
                follow_redirects=True,
            )
        return self._client

    def _build_headers(self, session_id: str | None) -> dict[str, str]:
        headers = {
            "Accept": MCP_ACCEPT_HEADER,
            "Content-Type": "application/json",
        }
        if session_id:
            headers[SESSION_ID_HEADER] = session_id
        return headers

    def _post_once(
        self, envelope: dict, *, session_id: str | None = None
    ) -> httpx.Response:
        """Single POST with MCP headers. ``session_id`` defaults to the cached one."""
        sid = session_id if session_id is not None else self._session_id
        client = self._get_client()
        return client.post(
            self.base_url,
            content=json.dumps(envelope).encode("utf-8"),
            headers=self._build_headers(sid),
        )

    def _post_with_retry(self, envelope: dict, tool_name: str) -> httpx.Response:
        """POST a ``tools/call`` envelope with 3-attempt conn/timeout backoff."""
        total_attempts = len(RETRY_DELAYS_SECONDS)
        for attempt_idx in range(1, total_attempts + 1):
            try:
                return self._post_once(envelope)
            except httpx.TimeoutException as exc:
                self._log("POST", tool_name,
                          f"attempt={attempt_idx}/{total_attempts} timeout: {exc}")
                if attempt_idx < total_attempts:
                    time.sleep(RETRY_DELAYS_SECONDS[attempt_idx - 1])
                    continue
                raise SfMcpTimeoutError(
                    f"request to {tool_name!r} timed out after {total_attempts} "
                    f"attempts ({self.timeout_seconds}s each): {exc}"
                ) from exc
            except httpx.RequestError as exc:
                # ConnectError, ReadError, WriteError, RemoteProtocolError, etc.
                self._log("POST", tool_name,
                          f"attempt={attempt_idx}/{total_attempts} "
                          f"conn-error: {type(exc).__name__}: {exc}")
                if attempt_idx < total_attempts:
                    time.sleep(RETRY_DELAYS_SECONDS[attempt_idx - 1])
                    continue
                raise SfMcpConnectionError(
                    f"connection to {tool_name!r} failed after {total_attempts} "
                    f"attempts: {type(exc).__name__}: {exc}"
                ) from exc
        # Unreachable: loop always returns or raises.
        raise SfMcpError("unreachable retry-loop exit")  # pragma: no cover

    # ---- response handling ----------------------------------------------

    def _enforce_size_cap(self, resp: httpx.Response, tool_name: str) -> None:
        # Content-Length pre-check (header may be absent on chunked/SSE).
        cl_header = resp.headers.get("content-length")
        if cl_header is not None:
            try:
                cl = int(cl_header)
            except ValueError:
                cl = None
            if cl is not None and cl > self.max_response_bytes:
                self._log("POST", tool_name,
                          f"response too large via header: content-length={cl} "
                          f"cap={self.max_response_bytes}")
                raise SfMcpResponseTooLargeError(
                    f"response Content-Length={cl} exceeds "
                    f"max_response_bytes={self.max_response_bytes}"
                )
        # Body length check (handles missing/chunked Content-Length, incl. SSE).
        body = resp.content
        if len(body) > self.max_response_bytes:
            self._log("POST", tool_name,
                      f"response body too large: bytes={len(body)} "
                      f"cap={self.max_response_bytes}")
            raise SfMcpResponseTooLargeError(
                f"response body bytes={len(body)} exceeds "
                f"max_response_bytes={self.max_response_bytes}"
            )

    def _handle_tool_response(self, resp: httpx.Response, tool_name: str) -> dict:
        """Validate + parse a ``tools/call`` response into its JSON-RPC ``result``."""
        self._enforce_size_cap(resp, tool_name)

        # HTTP status (4xx/5xx → SfMcpToolError, no retry here).
        if not (200 <= resp.status_code < 300):
            self._log("POST", tool_name, f"status={resp.status_code}")
            raise SfMcpToolError(
                f"HTTP {resp.status_code} from MCP server for {tool_name!r}: "
                f"{resp.text[:200]}",
                status_code=resp.status_code,
            )

        payload = self._parse_envelope(resp, tool_name)

        # JSON-RPC protocol error (top-level ``error``, present + non-null).
        rpc_err = payload.get("error")
        if rpc_err is not None:
            self._log("POST", tool_name, f"rpc-error: {_rpc_error_message(rpc_err)}")
            raise SfMcpToolError(
                f"JSON-RPC error from {tool_name!r}: {_rpc_error_message(rpc_err)}",
                rpc_error=rpc_err if isinstance(rpc_err, dict) else None,
            )

        # Result extraction. NOTE: a result with ``isError == true`` is an
        # MCP tool-level error and is returned as-is (transport succeeded).
        result = payload.get("result")
        self._log(
            "POST",
            tool_name,
            f"status={resp.status_code} ok rpc_id={payload.get('id', '?')}",
        )
        if result is None:
            return {}
        if isinstance(result, dict):
            return result
        return {"value": result}

    def _parse_envelope(self, resp: httpx.Response, tool_name: str) -> dict:
        """Parse a JSON-RPC envelope from a JSON *or* text/event-stream body.

        Dispatches on Content-Type (which may carry a ``;charset=...`` suffix):
            * ``application/json``   → ``json.loads(body)``.
            * ``text/event-stream``  → extract the ``data:`` JSON payload of the
              SSE message frame.
        """
        content_type = resp.headers.get("content-type", "").lower()
        text = resp.text

        if "text/event-stream" in content_type:
            raw = _extract_sse_data(text)
            if raw is None:
                self._log("POST", tool_name, "SSE response had no data: payload")
                raise SfMcpToolError(
                    f"text/event-stream response for {tool_name!r} contained no "
                    f"'data:' payload: {text[:200]}"
                )
            source = raw
        else:
            # Default to JSON (covers application/json and any unlabelled body).
            source = text

        try:
            payload = json.loads(source)
        except Exception as exc:  # noqa: BLE001 — non-JSON is a tool/transport fault
            self._log("POST", tool_name, f"non-json response: {exc}")
            raise SfMcpToolError(
                f"non-JSON response from MCP server for {tool_name!r}: "
                f"{source[:200]}"
            ) from exc

        if not isinstance(payload, dict):
            raise SfMcpToolError(
                f"JSON-RPC payload must be an object, got {type(payload).__name__}"
            )
        return payload

    def _log(self, method: str, tool: str, status: str) -> None:
        print(f"[sf_mcp_client] {method} {tool} → {status}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _extract_sse_data(text: str) -> str | None:
    """Return the concatenated ``data:`` payload from an SSE message body.

    SSE frames look like::

        id: <session>
        event: message
        data: {"jsonrpc":"2.0",...}

    Per the SSE spec, a single event may span multiple ``data:`` lines which
    are joined with ``\\n``. We collect every ``data:`` line in the body
    (the SF server emits a single ``event: message`` frame per tool call).
    Returns ``None`` if no ``data:`` line is present.
    """
    data_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("data:"):
            # Strip the prefix and a single optional leading space (SSE spec).
            value = line[len("data:"):]
            if value.startswith(" "):
                value = value[1:]
            data_lines.append(value)
    if not data_lines:
        return None
    return "\n".join(data_lines)


def _rpc_error_message(rpc_err: object) -> str:
    if isinstance(rpc_err, dict):
        return str(rpc_err.get("message", "unknown"))
    return str(rpc_err)


def _is_session_error(exc: SfMcpToolError) -> bool:
    """True if an HTTP-400 SfMcpToolError looks like a missing/expired session.

    The server reports this as ``-32600`` with a message that mentions the
    ``mcp-session-id`` header (e.g. "Session ID required in mcp-session-id
    header"). We match on the header name + 'session' in the message text.
    """
    msg = str(exc).lower()
    return "session" in msg and ("mcp-session-id" in msg or "session id" in msg)
