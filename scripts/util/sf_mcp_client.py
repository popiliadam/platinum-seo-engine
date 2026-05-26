"""scripts/util/sf_mcp_client.py — D-SF-14 reusable HTTP MCP client (first one).

Establishes the canonical HTTP MCP client pattern for PSEO. v1.8 SF MCP
integration is the first consumer; future HTTP MCPs (local LM Studio,
custom servers) reuse this class instead of re-implementing JSON-RPC
plumbing in each orchestrator.

Protocol: JSON-RPC 2.0 over HTTP. Each ``call_tool`` invocation wraps::

    {
        "jsonrpc": "2.0",
        "method":  "tools/call",
        "params":  {"name": tool_name, "arguments": kwargs},
        "id":      uuid.uuid4().hex
    }

Reliability:
    * Connection errors / timeouts: 3 attempts with exponential backoff
      (1s, 2s before attempts 2 and 3). HTTP 4xx and 5xx are NOT retried —
      4xx is a caller-side fault (wrong tool name, bad args) and 5xx
      indicates server-side failure that retrying won't fix (the orchestrator
      surfaces it to the operator).
    * Response size cap: raises :class:`SfMcpResponseTooLargeError` when
      Content-Length OR the actual body bytes exceed ``max_response_bytes``
      (default 100,000 bytes per D-SF-05).

Logging: every call writes one stderr line in the PSEO ingestion convention
``[sf_mcp_client] {method} {tool} → {status}``.

Refs:
    * D-SF-14 — first HTTP MCP client, reusable pattern
    * D-SF-05 — Max Response Size 100,000 bytes default
    * scripts/ingestion/scrapling_ops.py — sister stdio MCP wrapper pattern
"""

from __future__ import annotations

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
    """HTTP 4xx/5xx OR JSON-RPC ``error`` field present in response."""

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


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SfMcpClient:
    """HTTP JSON-RPC 2.0 client for SF MCP and future HTTP MCPs (D-SF-14).

    Args:
        base_url: Base URL of the MCP server (e.g. ``http://127.0.0.1:11435/mcp``).
            Trailing slash is stripped; path is appended verbatim per request.
        timeout_seconds: Per-request HTTP timeout. Default 30s. The orchestrator
            (skill body) owns cumulative poll timeouts; this client only knows
            about single-request timeouts.
        max_response_bytes: Hard cap on response body size; default 100,000 per
            D-SF-05. Raises :class:`SfMcpResponseTooLargeError` if exceeded.
        transport: Optional :class:`httpx.BaseTransport` for test injection
            (e.g. :class:`httpx.MockTransport`). When None a real network
            transport is used.
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

    # ---- public API ------------------------------------------------------

    def health(self) -> bool:
        """``GET {base_url}/health`` — returns True iff 2xx, False otherwise.

        Single attempt (no retry): health is a quick liveness probe; the
        caller decides what to do on a flaky result.
        """
        url = f"{self.base_url}/health"
        try:
            with self._make_client() as c:
                resp = c.get(url)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            self._log("GET", "health", f"error: {type(exc).__name__}: {exc}")
            return False
        ok = 200 <= resp.status_code < 300
        self._log("GET", "health", f"status={resp.status_code} ok={ok}")
        return ok

    def call_tool(self, tool_name: str, **kwargs: Any) -> dict:
        """Invoke an MCP tool via JSON-RPC 2.0 over HTTP.

        Retry policy:
            * 3 attempts total. Delays (1s, 2s) BETWEEN attempts on
              connection errors and timeouts only.
            * HTTP 4xx / 5xx: NO retry → raise :class:`SfMcpToolError`.
            * Response size exceeded: NO retry →
              raise :class:`SfMcpResponseTooLargeError`.

        Returns:
            The ``result`` field of the JSON-RPC envelope (dict). If the
            server returns a non-dict ``result``, it is wrapped as
            ``{"value": <result>}`` so callers can introspect uniformly.

        Raises:
            ValueError: ``tool_name`` is empty / not a string.
            SfMcpConnectionError: connection failed after all 3 attempts.
            SfMcpTimeoutError:    timed out after all 3 attempts.
            SfMcpToolError:       4xx/5xx OR JSON-RPC ``error`` field present.
            SfMcpResponseTooLargeError: response body exceeds cap.
        """
        if not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError(f"tool_name must be a non-empty string, got {tool_name!r}")

        envelope = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": dict(kwargs)},
            "id": uuid.uuid4().hex,
        }

        total_attempts = len(RETRY_DELAYS_SECONDS)
        last_conn_exc: Exception | None = None
        last_timeout_exc: Exception | None = None

        for attempt_idx in range(1, total_attempts + 1):
            try:
                resp = self._post_once(envelope)
            except httpx.TimeoutException as exc:
                last_timeout_exc = exc
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
                last_conn_exc = exc
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

            # Got a response — handle (no further retry from here).
            return self._handle_response(resp, tool_name)

        # Unreachable: loop always returns or raises.
        raise SfMcpError(
            f"unreachable retry-loop exit (last_conn={last_conn_exc!r}, "
            f"last_timeout={last_timeout_exc!r})"
        )

    # ---- internals -------------------------------------------------------

    def _make_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout_seconds,
            transport=self._transport,
            follow_redirects=True,
        )

    def _post_once(self, envelope: dict) -> httpx.Response:
        with self._make_client() as c:
            return c.post(self.base_url, json=envelope)

    def _handle_response(self, resp: httpx.Response, tool_name: str) -> dict:
        # 1. Content-Length pre-check (no body read if header says too big).
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

        # 2. Body length check (handles missing/chunked Content-Length).
        body = resp.content
        if len(body) > self.max_response_bytes:
            self._log("POST", tool_name,
                      f"response body too large: bytes={len(body)} "
                      f"cap={self.max_response_bytes}")
            raise SfMcpResponseTooLargeError(
                f"response body bytes={len(body)} exceeds "
                f"max_response_bytes={self.max_response_bytes}"
            )

        # 3. HTTP status (4xx/5xx → SfMcpToolError, no retry).
        if not (200 <= resp.status_code < 300):
            self._log("POST", tool_name, f"status={resp.status_code}")
            raise SfMcpToolError(
                f"HTTP {resp.status_code} from MCP server for {tool_name!r}: "
                f"{resp.text[:200]}",
                status_code=resp.status_code,
            )

        # 4. JSON-RPC envelope parse.
        try:
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001 — broad on purpose; non-JSON is a tool fault
            self._log("POST", tool_name, f"non-json response: {exc}")
            raise SfMcpToolError(
                f"non-JSON response from MCP server for {tool_name!r}: "
                f"{resp.text[:200]}"
            ) from exc

        if not isinstance(payload, dict):
            raise SfMcpToolError(
                f"JSON-RPC payload must be an object, got {type(payload).__name__}"
            )

        # 5. JSON-RPC error field (present + non-null).
        rpc_err = payload.get("error")
        if rpc_err is not None:
            err_msg = (
                rpc_err.get("message", "unknown")
                if isinstance(rpc_err, dict)
                else str(rpc_err)
            )
            self._log("POST", tool_name, f"rpc-error: {err_msg}")
            raise SfMcpToolError(
                f"JSON-RPC error from {tool_name!r}: {err_msg}",
                rpc_error=rpc_err if isinstance(rpc_err, dict) else None,
            )

        # 6. Result extraction.
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

    def _log(self, method: str, tool: str, status: str) -> None:
        print(f"[sf_mcp_client] {method} {tool} → {status}", file=sys.stderr)
