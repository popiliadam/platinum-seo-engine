"""tests/scripts/test_sf_mcp_client.py — v1.9.1 D-SF-14 MCP Streamable-HTTP client.

These tests exercise the client against the **real** MCP Streamable-HTTP
protocol (revision 2024-11-05), as proven by live curl against the
seospider-mcp-server. The v1.8 tests were rewritten in v1.9.1 because they
mocked an *assumed* bare-JSON-RPC-POST protocol that the real server rejects —
the mocks encoded the engine's assumption, not the wire reality, which is
exactly why a broken transport shipped with green tests.

The mock server (:class:`_MockMcpServer`) simulates the full handshake:

    1. ``initialize``                → HTTP 200, ``Mcp-Session-Id`` *response header*.
    2. ``notifications/initialized`` → HTTP 202, empty body (a notification).
    3. ``tools/call``                → HTTP 200, JSON **or** SSE (``data:``) body.

It also RECORDS every request (method, url, headers, body) so the regression
test can assert the wire-level contract that the v1.8 client violated.

Coverage:
    * Handshake + envelope formatting (POST body shape, params).
    * SSE (text/event-stream) tool response parsing.
    * JSON (application/json) tool response parsing.
    * REGRESSION — the bug-catcher: handshake-before-call ordering + the
      mandatory ``Accept`` and ``Mcp-Session-Id`` headers on the tool call.
    * health() True (live handshake) / False (server down).
    * MCP tool-level error (``result.isError``) returned as-is (NOT raised).
    * JSON-RPC protocol error (top-level ``error``) → SfMcpToolError.
    * Timeout → SfMcpTimeoutError after 3 attempts (backoff 1s, 2s).
    * Connection error → 3-retry exp-backoff; all-fail → SfMcpConnectionError.
    * Response size cap → SfMcpResponseTooLargeError; HTTP 4xx → SfMcpToolError.
    * Session expiry → re-initialize once + retry.
    * Redirect handling (#20): 3xx is NOT followed (SSRF guard) — it surfaces as
      SfMcpToolError; health() returns False on a redirect during initialize.
    * Spider-BUSY retry (v1.9.2): transient busy → retry-with-backoff →
      success; busy forever → exhaust budget + return busy as-is (no loop, no
      raise); permanent isError (SecurityException) → NO retry; success → NO
      retry.

Mocking: ``httpx.MockTransport`` (built into httpx — no extra dependency).

Refs:
    * scripts/util/sf_mcp_client.py (system under test)
    * D-SF-14 (first reusable HTTP MCP client)
    * MCP spec 2024-11-05 — Streamable-HTTP transport
"""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from scripts.util.sf_mcp_client import (
    DEFAULT_MAX_RESPONSE_BYTES,
    MCP_ACCEPT_HEADER,
    RETRY_DELAYS_SECONDS,
    SESSION_ID_HEADER,
    SfMcpClient,
    SfMcpConnectionError,
    SfMcpResponseTooLargeError,
    SfMcpTimeoutError,
    SfMcpToolError,
    _progress_indicates_loaded,
)


BASE_URL = "http://127.0.0.1:11435/mcp"
DEFAULT_SESSION_ID = "11111111-2222-3333-4444-555555555555"


# ---------------------------------------------------------------------------
# Recording mock MCP server (full Streamable-HTTP handshake simulation)
# ---------------------------------------------------------------------------

def _jsonrpc_result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _sse_body(envelope: dict, *, session_id: str = DEFAULT_SESSION_ID) -> str:
    """Encode a JSON-RPC envelope as a single SSE ``event: message`` frame.

    Mirrors the live server byte-for-byte: ``id:`` / ``event: message`` /
    ``data: {json}`` lines terminated by a blank line.
    """
    return (
        f"id: {session_id}\n"
        "event: message\n"
        f"data: {json.dumps(envelope)}\n"
        "\n"
    )


class _Recorded:
    """One captured request."""

    __slots__ = ("method", "url", "headers", "rpc_method", "body")

    def __init__(self, request: httpx.Request) -> None:
        self.method = request.method
        self.url = str(request.url)
        # httpx.Headers is case-insensitive; copy to a plain dict for asserts.
        self.headers = {k.lower(): v for k, v in request.headers.items()}
        self.body = json.loads(request.content) if request.content else {}
        self.rpc_method = self.body.get("method")


class _MockMcpServer:
    """Stateful, recording MCP Streamable-HTTP server for ``httpx.MockTransport``.

    Args:
        tool_result: the JSON-RPC ``result`` returned for ``tools/call``.
        tool_transport: ``"sse"`` (default, like the live server) or ``"json"``.
        session_id: the session id handed out by ``initialize``.
        require_session_on_tool: if True, a ``tools/call`` without the
            ``Mcp-Session-Id`` header returns the real server's HTTP-400
            ``-32600`` session error (used by the re-init test).
    """

    def __init__(
        self,
        *,
        tool_result=None,
        tool_transport: str = "sse",
        session_id: str = DEFAULT_SESSION_ID,
        require_session_on_tool: bool = True,
    ) -> None:
        self.tool_result = tool_result if tool_result is not None else {"ok": True}
        self.tool_transport = tool_transport
        self.session_id = session_id
        self.require_session_on_tool = require_session_on_tool
        self.requests: list[_Recorded] = []
        #: count of initialize calls — proves re-handshake / caching behavior.
        self.initialize_count = 0
        self.tool_call_count = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        rec = _Recorded(request)
        self.requests.append(rec)
        method = rec.rpc_method

        if method == "initialize":
            self.initialize_count += 1
            body = _jsonrpc_result(
                rec.body["id"],
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "seospider-mcp-server", "version": "1.0.0"},
                },
            )
            return httpx.Response(
                200,
                json=body,
                headers={SESSION_ID_HEADER: self.session_id},
            )

        if method == "notifications/initialized":
            # A notification → HTTP 202, empty body (matches the live server).
            return httpx.Response(202)

        if method == "tools/call":
            self.tool_call_count += 1
            if self.require_session_on_tool and SESSION_ID_HEADER.lower() not in rec.headers:
                # Real server's response when the session header is absent.
                return httpx.Response(
                    400,
                    json={
                        "jsonrpc": "2.0",
                        "id": rec.body.get("id"),
                        "error": {
                            "code": -32600,
                            "message": (
                                "Session ID required in mcp-session-id header"
                            ),
                        },
                    },
                )
            envelope = _jsonrpc_result(rec.body["id"], self.tool_result)
            if self.tool_transport == "sse":
                return httpx.Response(
                    200,
                    text=_sse_body(envelope, session_id=self.session_id),
                    headers={"content-type": "text/event-stream;charset=UTF-8"},
                )
            return httpx.Response(
                200,
                json=envelope,
                headers={"content-type": "application/json;charset=UTF-8"},
            )

        raise AssertionError(f"unexpected JSON-RPC method in test: {method!r}")


#: The live SF Spider-BUSY tool-level error text (Manager-observed, verbatim).
#: A state-changing op (sf_load_crawl / sf_crawl) leaves the Spider transiently
#: BUSY and tool calls return this with ``isError == true`` until it is ready.
SPIDER_BUSY_TEXT = (
    "Tool error: IllegalStateException: Tool cannot be called currently. "
    "Please check the state of the Spider"
)


def _busy_result() -> dict:
    """The transient Spider-BUSY tool-level error result (``isError == true``)."""
    return {
        "content": [{"type": "text", "text": SPIDER_BUSY_TEXT}],
        "isError": True,
    }


class _SequencedToolServer(_MockMcpServer):
    """Mock server whose ``tools/call`` returns a *scripted sequence* of results.

    Each ``tools/call`` pops the next result from ``tool_results``; once the
    list is exhausted the final entry is repeated (so "busy forever" = a single
    busy entry that is reused). This lets a test drive the busy → busy → success
    progression that the live Spider exhibits after a state-changing op.
    """

    def __init__(self, tool_results: list[dict], **kwargs) -> None:
        super().__init__(**kwargs)
        assert tool_results, "tool_results must be non-empty"
        self._scripted = list(tool_results)

    def handler(self, request: httpx.Request) -> httpx.Response:
        rec = _Recorded(request)
        method = rec.rpc_method
        # Handshake methods reuse the base behaviour (and its recording).
        if method != "tools/call":
            return super().handler(request)

        self.requests.append(rec)
        self.tool_call_count += 1
        idx = min(self.tool_call_count - 1, len(self._scripted) - 1)
        self.tool_result = self._scripted[idx]  # for visibility/debug
        envelope = _jsonrpc_result(rec.body["id"], self._scripted[idx])
        # Busy/permanent tool errors are returned over the live SSE transport.
        return httpx.Response(
            200,
            text=_sse_body(envelope, session_id=self.session_id),
            headers={"content-type": "text/event-stream;charset=UTF-8"},
        )


def _client_for(
    server: _MockMcpServer,
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_seconds: float = 30.0,
    busy_retry_max: int = 6,
    busy_retry_base_delay: float = 2.0,
) -> SfMcpClient:
    return SfMcpClient(
        BASE_URL,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        busy_retry_max=busy_retry_max,
        busy_retry_base_delay=busy_retry_base_delay,
        transport=httpx.MockTransport(server.handler),
    )


def _raw_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_seconds: float = 30.0,
) -> SfMcpClient:
    """Client wired to an arbitrary low-level handler (for failure-mode tests)."""
    return SfMcpClient(
        BASE_URL,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        transport=httpx.MockTransport(handler),
    )


# ---------------------------------------------------------------------------
# Case 1: Handshake + JSON-RPC envelope formatting
# ---------------------------------------------------------------------------

def test_call_tool_emits_jsonrpc_tools_call_envelope() -> None:
    """The ``tools/call`` POST body must match the MCP JSON-RPC spec exactly."""
    server = _MockMcpServer(tool_result={"echo": "pong"})
    client = _client_for(server)

    result = client.call_tool("sf_crawl", start_url="https://example.com", max_pages=10)

    # The tool-call request is the last one (after initialize + initialized).
    tool_req = server.requests[-1]
    assert tool_req.method == "POST"
    assert tool_req.url == BASE_URL
    assert tool_req.rpc_method == "tools/call"

    body = tool_req.body
    assert body["jsonrpc"] == "2.0", "JSON-RPC version must be exactly '2.0'"
    assert body["params"]["name"] == "sf_crawl"
    assert body["params"]["arguments"] == {
        "start_url": "https://example.com",
        "max_pages": 10,
    }
    assert isinstance(body["id"], str) and len(body["id"]) == 32, \
        "id must be a uuid4().hex (32 chars)"

    assert result == {"echo": "pong"}


# ---------------------------------------------------------------------------
# Case 2: REGRESSION — the bug-catcher.
# Would FAIL against the v1.8 client (no handshake, no Accept/session headers).
# ---------------------------------------------------------------------------

def test_regression_handshake_and_required_headers_before_tool_call() -> None:
    """Pin the wire contract the v1.8 client violated → caused the live HTTP 400.

    Asserts the client:
      (a) performs the ``initialize`` handshake BEFORE any ``tools/call``,
      (b) sends ``Accept: application/json, text/event-stream`` on the call,
      (c) sends the ``Mcp-Session-Id`` header (the value handed out by
          ``initialize``) on the call,
      (d) sends the ``notifications/initialized`` step between them.
    """
    server = _MockMcpServer(tool_result={"crawls": []})
    client = _client_for(server)

    client.call_tool("sf_list_crawls")

    methods = [r.rpc_method for r in server.requests]
    # (a) + (d): exact handshake order before the tool call.
    assert methods == [
        "initialize",
        "notifications/initialized",
        "tools/call",
    ], f"client must handshake before tools/call; got order {methods}"

    init_req = server.requests[0]
    tool_req = server.requests[-1]

    # (b) Accept header carries BOTH media types on EVERY request.
    for rec in server.requests:
        assert rec.headers.get("accept") == MCP_ACCEPT_HEADER, (
            f"{rec.rpc_method} must send Accept '{MCP_ACCEPT_HEADER}'; "
            f"got {rec.headers.get('accept')!r}"
        )
        assert "application/json" in rec.headers.get("content-type", ""), (
            f"{rec.rpc_method} must send Content-Type application/json"
        )

    # (c) Session id from initialize's RESPONSE header is replayed on the call.
    assert SESSION_ID_HEADER.lower() not in init_req.headers, (
        "initialize must NOT pre-send a session id (server mints it)"
    )
    assert tool_req.headers.get(SESSION_ID_HEADER.lower()) == DEFAULT_SESSION_ID, (
        "tools/call must carry the Mcp-Session-Id minted by initialize"
    )


# ---------------------------------------------------------------------------
# Case 3: Tool response parsing — SSE and JSON variants
# ---------------------------------------------------------------------------

def test_call_tool_parses_sse_event_stream_response() -> None:
    """text/event-stream body → JSON-RPC result extracted from the data: frame.

    This is the live server's actual tool-call transport.
    """
    server = _MockMcpServer(
        tool_result={"content": [{"type": "text", "text": "hi"}], "isError": False},
        tool_transport="sse",
    )
    client = _client_for(server)

    result = client.call_tool("sf_list_crawls")
    assert result == {"content": [{"type": "text", "text": "hi"}], "isError": False}

    # Confirm the response really was SSE (guards against the mock drifting).
    assert server.tool_transport == "sse"


def test_call_tool_parses_application_json_response() -> None:
    """application/json body → JSON-RPC result parsed directly (no SSE framing)."""
    server = _MockMcpServer(tool_result={"recovered": True}, tool_transport="json")
    client = _client_for(server)

    result = client.call_tool("sf_generate_report", report_name="page_titles_all")
    assert result == {"recovered": True}


def test_call_tool_returns_mcp_tool_level_error_as_is() -> None:
    """``result.isError == true`` is an MCP tool-level error → returned, NOT raised.

    The live server returns this (HTTP 200) when the Spider is not in a
    callable state. The transport succeeded, so the consumer skill must
    receive the result and interpret ``isError`` itself.
    """
    tool_error_result = {
        "content": [{"type": "text", "text": "Tool error: IllegalStateException"}],
        "isError": True,
    }
    server = _MockMcpServer(tool_result=tool_error_result, tool_transport="sse")
    client = _client_for(server)

    result = client.call_tool("sf_list_crawls")
    assert result == tool_error_result
    assert result["isError"] is True


# ---------------------------------------------------------------------------
# Case 4: health() — live handshake vs server down
# ---------------------------------------------------------------------------

def test_health_true_on_successful_handshake() -> None:
    """health() returns True iff the initialize handshake yields a session id."""
    server = _MockMcpServer()
    client = _client_for(server)

    assert client.health() is True
    assert server.initialize_count == 1
    # health warms the cache → a follow-up call_tool reuses the session.
    client.call_tool("sf_list_crawls")
    assert server.initialize_count == 1, "health() should warm + reuse the session"


def test_health_false_when_server_unreachable() -> None:
    """health() returns False (never raises) on connection failure."""
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _raw_client(refuse)
    assert client.health() is False


def test_health_false_when_initialize_returns_no_session_header() -> None:
    """A 200 initialize with NO Mcp-Session-Id header is not 'alive'."""
    def no_session(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json=_jsonrpc_result(body["id"], {"ok": True}))

    client = _raw_client(no_session)
    assert client.health() is False


def test_health_false_on_http_error_status() -> None:
    """A non-2xx initialize → health() False (no raise)."""
    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = _raw_client(server_error)
    assert client.health() is False


# ---------------------------------------------------------------------------
# Case 5: JSON-RPC protocol error → SfMcpToolError
# ---------------------------------------------------------------------------

def test_call_tool_raises_on_jsonrpc_error_field() -> None:
    """A top-level JSON-RPC ``error`` (protocol fault) → SfMcpToolError."""
    def server_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        # tools/call → JSON-RPC error envelope
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": body["id"],
                "error": {"code": -32601, "message": "Method not found"},
            },
            headers={"content-type": "application/json"},
        )

    client = _raw_client(server_handler)
    with pytest.raises(SfMcpToolError) as exc_info:
        client.call_tool("sf_bogus")
    assert "Method not found" in str(exc_info.value)
    assert exc_info.value.rpc_error == {"code": -32601, "message": "Method not found"}


# ---------------------------------------------------------------------------
# Case 6: Timeout exhausts retries → SfMcpTimeoutError
# ---------------------------------------------------------------------------

def test_call_tool_timeout_raises_after_three_attempts(monkeypatch) -> None:
    """All 3 tool-call attempts time out → SfMcpTimeoutError, sleep called twice.

    The handshake succeeds; only ``tools/call`` times out (so the retry/backoff
    under test is the tool-call loop, not the handshake).
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    attempts = {"tool": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        attempts["tool"] += 1
        raise httpx.ReadTimeout("simulated read timeout", request=request)

    client = _raw_client(handler, timeout_seconds=0.01)
    with pytest.raises(SfMcpTimeoutError) as exc_info:
        client.call_tool("sf_crawl_progress", run_id="abc")

    assert attempts["tool"] == 3, "client must attempt the tool call exactly 3 times"
    assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]], (
        f"client must sleep (1s, 2s) between attempts; got {sleeps}"
    )
    assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 7: 3-retry exponential backoff on connection errors
# ---------------------------------------------------------------------------

def test_call_tool_retries_three_times_with_exp_backoff(monkeypatch) -> None:
    """Tool-call conn error on attempts 1+2, success on 3 → no exception.

    Then: all-fail → SfMcpConnectionError after exactly 3 attempts (2 sleeps).
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    state = {"tool": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        state["tool"] += 1
        if state["tool"] < 3:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(
            200,
            text=_sse_body(_jsonrpc_result(body["id"], {"recovered": True})),
            headers={"content-type": "text/event-stream"},
        )

    client = _raw_client(handler)
    result = client.call_tool("sf_generate_report", report_name="page_titles_all")

    assert state["tool"] == 3, "expected exactly 3 tool attempts (2 fail + 1 ok)"
    assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]], (
        f"backoff must be exactly (1s, 2s); got {sleeps}"
    )
    assert result == {"recovered": True}

    # All-fail variant → SfMcpConnectionError, no 4th attempt.
    sleeps.clear()
    fail_state = {"tool": 0}

    def always_fail(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        fail_state["tool"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    client2 = _raw_client(always_fail)
    with pytest.raises(SfMcpConnectionError) as exc_info:
        client2.call_tool("sf_crawl", start_url="https://example.com")

    assert fail_state["tool"] == 3, "must not exceed 3 tool attempts"
    assert len(sleeps) == 2, "exactly 2 sleeps between 3 attempts (no trailing sleep)"
    assert "3 attempts" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case 8: Response size cap + HTTP 4xx
# ---------------------------------------------------------------------------

def test_call_tool_response_too_large_raises() -> None:
    """Body > max_response_bytes → SfMcpResponseTooLargeError (SSE body counts)."""
    big_payload = "x" * (1000 + 1)  # over a small 1000-byte cap
    server = _MockMcpServer(tool_result={"blob": big_payload}, tool_transport="sse")
    client = _client_for(server, max_response_bytes=1000)

    with pytest.raises(SfMcpResponseTooLargeError) as exc_info:
        client.call_tool("sf_generate_report", report_name="all_inlinks")
    assert "exceeds" in str(exc_info.value)
    assert "1000" in str(exc_info.value)


def test_call_tool_http_4xx_raises_tool_error_no_retry() -> None:
    """A non-session HTTP 4xx on the tool call → SfMcpToolError, no retry."""
    state = {"tool": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        state["tool"] += 1
        return httpx.Response(400, text="bad arguments")  # not a session error

    client = _raw_client(handler)
    with pytest.raises(SfMcpToolError) as exc_info:
        client.call_tool("sf_crawl", start_url="not-a-url")
    assert exc_info.value.status_code == 400
    assert state["tool"] == 1, "HTTP 4xx must NOT be retried"


# ---------------------------------------------------------------------------
# Case 9: Session expiry → re-initialize once + retry
# ---------------------------------------------------------------------------

def test_call_tool_reinitializes_once_on_session_error() -> None:
    """A stale session (HTTP-400 session error) → re-handshake once + retry → ok.

    Simulates a server that has forgotten the cached session: the first
    tools/call with the (now-stale) id is rejected with the session-required
    400; the client must re-initialize and succeed on the retry.
    """
    state = {"init": 0, "tool": 0}
    first_session = "aaaa1111-0000-0000-0000-000000000000"
    second_session = "bbbb2222-0000-0000-0000-000000000000"

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        headers = {k.lower(): v for k, v in request.headers.items()}

        if method == "initialize":
            state["init"] += 1
            sid = first_session if state["init"] == 1 else second_session
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: sid},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)

        # tools/call: reject the FIRST session id as stale; accept the second.
        state["tool"] += 1
        sent_sid = headers.get(SESSION_ID_HEADER.lower())
        if sent_sid != second_session:
            return httpx.Response(
                400,
                json={
                    "jsonrpc": "2.0",
                    "id": body.get("id"),
                    "error": {
                        "code": -32600,
                        "message": "Session ID required in mcp-session-id header",
                    },
                },
            )
        return httpx.Response(
            200,
            text=_sse_body(_jsonrpc_result(body["id"], {"done": True}),
                           session_id=second_session),
            headers={"content-type": "text/event-stream"},
        )

    client = _raw_client(handler)
    result = client.call_tool("sf_list_crawls")

    assert result == {"done": True}
    assert state["init"] == 2, "client must re-initialize exactly once on session error"
    assert state["tool"] == 2, "the tool call is retried once after re-handshake"


def test_call_tool_session_error_does_not_loop_forever() -> None:
    """A persistent session error → re-init ONCE then surface SfMcpToolError.

    Guards against an infinite re-handshake loop if the server keeps rejecting.
    """
    state = {"init": 0, "tool": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            state["init"] += 1
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        state["tool"] += 1
        return httpx.Response(
            400,
            json={
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32600,
                    "message": "Session ID required in mcp-session-id header",
                },
            },
        )

    client = _raw_client(handler)
    with pytest.raises(SfMcpToolError) as exc_info:
        client.call_tool("sf_list_crawls")
    assert exc_info.value.status_code == 400
    assert state["init"] == 2, "exactly one re-initialize (2 total) — no infinite loop"
    assert state["tool"] == 2, "tool attempted twice (original + one retry)"


# ---------------------------------------------------------------------------
# Case 10: Redirect handling (#20) — redirects are NOT followed (SSRF guard).
# The SF MCP base_url is loopback; a server 3xx that points off-host is always
# suspect, so follow_redirects=False + the 3xx surfaces as a clear error instead
# of silently chasing an attacker-controlled Location to a different host/port.
# ---------------------------------------------------------------------------

def test_call_tool_does_not_follow_redirect_surfaces_error() -> None:
    """#20: a 3xx on ``tools/call`` must NOT be followed — it surfaces as a clear
    SfMcpToolError and the client never POSTs to the redirect target.

    The handler offers a 200 success AT the redirect target; if the client (wrongly)
    followed the redirect it would reach it and return a result. The fix proves the
    redirect is refused: exactly ONE tool POST (to base_url) and an error raised.
    """
    redirect_target = "http://169.254.169.254/latest/meta-data"  # SSRF canary host
    tool_posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        # tools/call — the server tries to redirect us off-host.
        url = str(request.url)
        tool_posts.append(url)
        if url == BASE_URL:
            return httpx.Response(307, headers={"location": redirect_target}, text="")
        # Only reached if the client WRONGLY follows the redirect.
        return httpx.Response(
            200,
            text=_sse_body(_jsonrpc_result(body["id"], {"final": "followed!"})),
            headers={"content-type": "text/event-stream"},
        )

    client = _raw_client(handler)
    with pytest.raises(SfMcpToolError) as exc_info:
        client.call_tool("sf_list_crawls")

    assert exc_info.value.status_code == 307
    assert "redirect" in str(exc_info.value).lower()
    assert tool_posts == [BASE_URL], (
        f"redirect must NOT be followed; expected exactly one POST to {BASE_URL}, "
        f"got {tool_posts}"
    )


def test_health_false_on_redirect_during_initialize() -> None:
    """A 3xx on the initialize handshake makes health() return False (the redirect
    is surfaced internally as an error; health stays non-raising by contract)."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302, headers={"location": "http://evil.example/"}, text=""
        )

    client = _raw_client(handler)
    assert client.health() is False


# ---------------------------------------------------------------------------
# Case 11: Spider-BUSY retry (v1.9.2) — the whole point of the patch.
# After a state-changing op the Spider is transiently BUSY; the client must
# retry the SAME call until it clears, but NEVER retry a permanent error.
# ---------------------------------------------------------------------------

def test_busy_then_ready_retries_until_success(monkeypatch) -> None:
    """Busy (isError) twice → success on the 3rd call.

    The client must RETRY the SAME tool call and ultimately return the success
    (``isError == False``). Sleep is patched so the test is instant.
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    success = {
        "content": [{"type": "text", "text": "progress: 100%"}],
        "isError": False,
    }
    server = _SequencedToolServer(
        [_busy_result(), _busy_result(), success]
    )
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    result = client.call_tool("sf_crawl_progress")

    assert result == success, "client must retry past the busy window to the success"
    assert result["isError"] is False
    assert server.tool_call_count == 3, (
        "expected 3 tool calls (busy, busy, success); "
        f"got {server.tool_call_count}"
    )
    # Two retries happened → two backoff sleeps with the linear schedule (2s, 4s).
    assert sleeps == [2.0, 4.0], (
        f"busy backoff must be linear base*N (2s, 4s); got {sleeps}"
    )


def test_busy_exhausted_returns_busy_result_no_raise(monkeypatch) -> None:
    """Busy on EVERY call → retry exactly ``busy_retry_max`` times, then return.

    The busy result is returned AS-IS (no raise, no infinite loop). Total tool
    calls == busy_retry_max + 1 (the initial call plus the retries).
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    # A single busy entry is repeated forever by _SequencedToolServer.
    server = _SequencedToolServer([_busy_result()])
    busy_retry_max = 4
    client = _client_for(
        server, busy_retry_max=busy_retry_max, busy_retry_base_delay=2.0
    )

    result = client.call_tool("sf_crawl_progress")

    # Returned the busy result as-is (no exception raised).
    assert result["isError"] is True
    assert "IllegalStateException" in result["content"][0]["text"]
    assert "Tool cannot be called currently" in result["content"][0]["text"]
    # Initial call + busy_retry_max retries == busy_retry_max + 1 total calls.
    assert server.tool_call_count == busy_retry_max + 1, (
        f"expected {busy_retry_max + 1} tool calls (1 initial + "
        f"{busy_retry_max} retries); got {server.tool_call_count}"
    )
    # One sleep per retry (capped linear backoff: 2, 4, 6, 8).
    assert sleeps == [2.0, 4.0, 6.0, 8.0], (
        f"expected one capped-linear sleep per retry; got {sleeps}"
    )


def test_no_retry_on_permanent_error(monkeypatch) -> None:
    """A non-busy isError (SecurityException) → returned immediately, NO retry.

    Permanent tool errors (bad arg, security, size-cap) must NOT be retried —
    retrying is wasteful and wrong. Exactly ONE tool call, returned as-is.
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    permanent = {
        "content": [
            {
                "type": "text",
                "text": "Tool error: SecurityException: Absolute paths are not allowed",
            }
        ],
        "isError": True,
    }
    server = _SequencedToolServer([permanent])
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    result = client.call_tool("sf_export_report", file_path="/abs/path.csv")

    assert result == permanent, "permanent isError must be returned as-is"
    assert result["isError"] is True
    assert server.tool_call_count == 1, (
        f"permanent error must NOT be retried; got {server.tool_call_count} calls"
    )
    assert sleeps == [], "no backoff sleep on a permanent error"


def test_no_retry_on_success(monkeypatch) -> None:
    """A successful (non-error) result → returned immediately, exactly 1 call."""
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    success = {
        "content": [{"type": "text", "text": "ok"}],
        "isError": False,
    }
    server = _SequencedToolServer([success])
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    result = client.call_tool("sf_list_crawls")

    assert result == success
    assert server.tool_call_count == 1, (
        f"success must not trigger a retry; got {server.tool_call_count} calls"
    )
    assert sleeps == [], "no backoff sleep on success"


# ---------------------------------------------------------------------------
# Case 12: Per-call timeout / attempts override (v1.9.3 — load_crawl support).
# Two OPTIONAL keyword-only params let a caller fire a single FAST attempt with
# a short per-request timeout. Default behaviour MUST be byte-identical to
# today (all the Case-6 / Case-7 retry tests above still pass unchanged).
# ---------------------------------------------------------------------------

def _progress_result(
    *, active: int = 0, completed: int = 1822, percent: int = 100, waiting: int = 0
) -> dict:
    """An sf_crawl_progress tool result: JSON text inside a content text block.

    Mirrors the live SF MCP shape — the progress dict is JSON-encoded into
    ``content[0].text`` (NOT a structured field on the result).
    """
    payload = {
        "active": active,
        "completed": completed,
        "percentComplete": percent,
        "waiting": waiting,
    }
    return {
        "content": [{"type": "text", "text": json.dumps(payload)}],
        "isError": False,
    }


def test_call_tool_override_does_single_fast_attempt_on_timeout(monkeypatch) -> None:
    """``_max_attempts_override=1`` + ``_timeout_override`` → ONE post, short timeout.

    Asserts (a) exactly one tool post attempt is made (the retry loop is capped
    at 1), (b) the per-request httpx timeout equals the override (not the
    instance ``timeout_seconds``), and (c) it still raises SfMcpTimeoutError.
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    attempts = {"tool": 0}
    seen_timeouts: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        attempts["tool"] += 1
        # httpx records the effective per-request timeout in request.extensions.
        seen_timeouts.append(request.extensions.get("timeout"))
        raise httpx.ReadTimeout("simulated read timeout", request=request)

    client = _raw_client(handler, timeout_seconds=30.0)
    with pytest.raises(SfMcpTimeoutError):
        client.call_tool(
            "sf_load_crawl",
            crawl_id="big",
            _timeout_override=5.0,
            _max_attempts_override=1,
        )

    assert attempts["tool"] == 1, (
        f"override must cap the tool call at ONE attempt; got {attempts['tool']}"
    )
    assert sleeps == [], "a single capped attempt must not sleep between retries"
    # httpx normalises a float timeout into a per-operation dict; every leg = 5.0.
    assert seen_timeouts and all(
        v == {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0}
        for v in seen_timeouts
    ), f"per-request timeout must be the 5.0s override; got {seen_timeouts}"


def test_default_call_still_three_attempts_when_no_override(monkeypatch) -> None:
    """No override → IDENTICAL to today: 3 attempts, 2 sleeps, instance timeout.

    Pins backward-compatibility: threading the optional params must not change
    the default path. (Companion to the Case-6 timeout test.)
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    attempts = {"tool": 0}
    seen_timeouts: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body.get("method")
        if method == "initialize":
            return httpx.Response(
                200, json=_jsonrpc_result(body["id"], {"ok": True}),
                headers={SESSION_ID_HEADER: DEFAULT_SESSION_ID},
            )
        if method == "notifications/initialized":
            return httpx.Response(202)
        attempts["tool"] += 1
        seen_timeouts.append(request.extensions.get("timeout"))
        raise httpx.ReadTimeout("simulated read timeout", request=request)

    client = _raw_client(handler, timeout_seconds=12.0)
    with pytest.raises(SfMcpTimeoutError):
        client.call_tool("sf_crawl_progress")

    assert attempts["tool"] == 3, "default (no override) must still attempt 3 times"
    assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]], (
        f"default backoff must be (1s, 2s); got {sleeps}"
    )
    assert all(
        v == {"connect": 12.0, "read": 12.0, "write": 12.0, "pool": 12.0}
        for v in seen_timeouts
    ), f"default per-request timeout must be the instance 12.0s; got {seen_timeouts}"


def test_override_params_not_leaked_into_jsonrpc_arguments() -> None:
    """``_timeout_override`` / ``_max_attempts_override`` MUST NOT reach the wire.

    They are client-side knobs, not tool arguments — the posted JSON-RPC
    ``params.arguments`` must contain ONLY the genuine tool kwargs.
    """
    server = _MockMcpServer(tool_result={"ok": True})
    client = _client_for(server)

    client.call_tool(
        "sf_load_crawl",
        crawl_id="demo-aluminum",
        _timeout_override=5.0,
        _max_attempts_override=1,
    )

    tool_req = server.requests[-1]
    assert tool_req.rpc_method == "tools/call"
    assert tool_req.body["params"]["arguments"] == {"crawl_id": "demo-aluminum"}, (
        "override knobs must not leak into params.arguments; "
        f"got {tool_req.body['params']['arguments']}"
    )


# ---------------------------------------------------------------------------
# Case 13: _progress_indicates_loaded — the readiness predicate.
# ---------------------------------------------------------------------------

def test_progress_indicates_loaded_true_for_settled_crawl() -> None:
    """active==0 AND (completed>0 OR percentComplete>=100) AND not isError → True."""
    assert _progress_indicates_loaded(
        _progress_result(active=0, completed=1822, percent=100)
    ) is True
    # completed>0 alone (percent missing/low) is enough.
    assert _progress_indicates_loaded(
        {"content": [{"type": "text", "text": json.dumps(
            {"active": 0, "completed": 5})}], "isError": False}
    ) is True
    # percentComplete>=100 alone (completed 0) is enough.
    assert _progress_indicates_loaded(
        {"content": [{"type": "text", "text": json.dumps(
            {"active": 0, "completed": 0, "percentComplete": 100})}],
         "isError": False}
    ) is True


def test_progress_indicates_loaded_false_when_still_active() -> None:
    """active>0 → still crawling/loading → False (even at completed>0)."""
    assert _progress_indicates_loaded(
        _progress_result(active=3, completed=10, percent=40)
    ) is False


def test_progress_indicates_loaded_false_on_iserror() -> None:
    """isError==True → False regardless of the (here valid-looking) payload."""
    bad = _progress_result(active=0, completed=1822, percent=100)
    bad = {**bad, "isError": True}
    assert _progress_indicates_loaded(bad) is False


def test_progress_indicates_loaded_false_on_non_json_or_empty() -> None:
    """Non-JSON text, missing content, empty dict, non-dict → all False (defensive)."""
    assert _progress_indicates_loaded(
        {"content": [{"type": "text", "text": "not json {{"}], "isError": False}
    ) is False
    assert _progress_indicates_loaded({"isError": False}) is False  # no content
    assert _progress_indicates_loaded({}) is False
    assert _progress_indicates_loaded(None) is False  # type: ignore[arg-type]
    # Well-formed JSON but no active/completed/percent keys → not loaded.
    assert _progress_indicates_loaded(
        {"content": [{"type": "text", "text": json.dumps({"waiting": 5})}],
         "isError": False}
    ) is False


# ---------------------------------------------------------------------------
# Case 14: load_crawl — the resilient loader (the live-discovered fix).
# sf_load_crawl times out CLIENT-side on a big crawl but loads SERVER-side;
# load_crawl fires it fast+tolerantly then polls sf_crawl_progress to confirm.
# ---------------------------------------------------------------------------

class _LoadCrawlServer(_MockMcpServer):
    """Routes by tool name: ``sf_load_crawl`` vs ``sf_crawl_progress``.

    ``load_raises`` (e.g. httpx.ReadTimeout) simulates the client-side timeout
    the live big-crawl load triggers. ``progress_results`` is a scripted
    sequence for successive ``sf_crawl_progress`` calls (last entry repeats).
    """

    def __init__(
        self,
        *,
        load_raises: Exception | None = None,
        load_result: dict | None = None,
        progress_results: list[dict],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        assert progress_results, "progress_results must be non-empty"
        self._load_raises = load_raises
        self._load_result = load_result if load_result is not None else {"ok": True}
        self._progress = list(progress_results)
        self.load_call_count = 0
        self.progress_call_count = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        rec = _Recorded(request)
        if rec.rpc_method != "tools/call":
            return super().handler(request)
        self.requests.append(rec)
        self.tool_call_count += 1
        tool = rec.body["params"]["name"]
        if tool == "sf_load_crawl":
            self.load_call_count += 1
            if self._load_raises is not None:
                raise self._load_raises
            result = self._load_result
        elif tool == "sf_crawl_progress":
            idx = min(self.progress_call_count, len(self._progress) - 1)
            self.progress_call_count += 1
            result = self._progress[idx]
        else:
            raise AssertionError(f"unexpected tool in load test: {tool!r}")
        envelope = _jsonrpc_result(rec.body["id"], result)
        return httpx.Response(
            200,
            text=_sse_body(envelope, session_id=self.session_id),
            headers={"content-type": "text/event-stream;charset=UTF-8"},
        )


def test_load_crawl_success_when_load_times_out_but_progress_settles(monkeypatch) -> None:
    """THE live case: load TIMES OUT client-side, but progress reports loaded.

    sf_load_crawl raises SfMcpTimeoutError (the timeout is swallowed); the first
    sf_crawl_progress poll already shows active=0/completed=1822 → load_crawl
    RETURNS that progress (no raise).
    """
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    # sf_load_crawl raises a ReadTimeout on its single fast attempt → the
    # client's _post_with_retry surfaces SfMcpTimeoutError, which load_crawl
    # swallows. (A bare ConnectError path is covered implicitly by the same
    # except clause; we exercise the timeout flavour seen live.)
    server = _LoadCrawlServer(
        load_raises=httpx.ReadTimeout("client-side load timeout"),
        progress_results=[_progress_result(active=0, completed=1822, percent=100)],
    )
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    prog = client.load_crawl(
        "demo-aluminum",
        settle_timeout_seconds=5.0,
        poll_interval_seconds=0.05,
        load_fire_timeout_seconds=1.0,
    )

    assert _progress_indicates_loaded(prog) is True
    assert prog["content"][0]["text"]  # the real progress payload is returned
    assert server.load_call_count == 1, (
        f"load must be fired exactly once (fast); got {server.load_call_count}"
    )
    assert server.progress_call_count == 1, (
        "progress should settle on the first poll → exactly one progress call; "
        f"got {server.progress_call_count}"
    )
    assert sleeps == [], "settled on first poll → no poll sleeps"


def test_load_crawl_success_when_load_returns_cleanly(monkeypatch) -> None:
    """Variant: load returns WITHOUT a timeout, progress is loaded → success."""
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", lambda *_: None)

    server = _LoadCrawlServer(
        load_result={"content": [{"type": "text", "text": "loaded"}], "isError": False},
        progress_results=[
            _progress_result(active=2, completed=0, percent=10),   # not yet
            _progress_result(active=0, completed=1822, percent=100),  # settled
        ],
    )
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    prog = client.load_crawl(
        "demo-aluminum",
        settle_timeout_seconds=5.0,
        poll_interval_seconds=0.01,
        load_fire_timeout_seconds=15.0,
    )

    assert _progress_indicates_loaded(prog) is True
    assert server.load_call_count == 1
    assert server.progress_call_count == 2, (
        "first poll not settled, second settled → exactly two progress calls; "
        f"got {server.progress_call_count}"
    )


def test_load_crawl_raises_when_progress_never_settles(monkeypatch) -> None:
    """Load fired but progress stays active>0 past the budget → SfMcpTimeoutError.

    Uses a tiny settle budget + tiny poll interval so the test is instant; the
    deadline is driven by monotonic time, so we DON'T patch time.monotonic, only
    time.sleep (kept tiny by the 0.05s interval anyway).
    """
    # Let the real (tiny) sleeps run so the monotonic deadline actually elapses.
    server = _LoadCrawlServer(
        load_raises=httpx.ReadTimeout("client-side load timeout"),
        progress_results=[_progress_result(active=4, completed=0, percent=20)],  # never settles
    )
    client = _client_for(server, busy_retry_max=6, busy_retry_base_delay=2.0)

    with pytest.raises(SfMcpTimeoutError) as exc_info:
        client.load_crawl(
            "demo-aluminum",
            settle_timeout_seconds=0.3,
            poll_interval_seconds=0.05,
            load_fire_timeout_seconds=1.0,
        )

    msg = str(exc_info.value)
    assert "demo-aluminum" in msg
    assert "did not settle" in msg
    assert server.load_call_count == 1, "load fired once even on the failure path"
    assert server.progress_call_count >= 1, "at least one progress poll happened"


def test_load_crawl_validates_crawl_id() -> None:
    """Empty / non-str crawl_id → ValueError before any network call."""
    server = _LoadCrawlServer(
        progress_results=[_progress_result()],
    )
    client = _client_for(server)

    for bad in ("", "   ", None, 123):
        with pytest.raises(ValueError):
            client.load_crawl(bad)  # type: ignore[arg-type]
    assert server.load_call_count == 0, "validation must short-circuit before firing"


def test_load_crawl_swallows_load_tool_error_and_confirms_via_progress(monkeypatch) -> None:
    """A non-timeout tool-error RESULT from the load is ignored; progress decides.

    sf_load_crawl returns a tool-level isError result (NOT a raise) on the fire;
    load_crawl must not treat that as fatal — it proceeds to poll progress, which
    is loaded → success. (The progress poll is the real readiness gate.)
    """
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", lambda *_: None)

    load_err = {
        "content": [{"type": "text", "text": "Tool error: some transient state"}],
        "isError": True,
    }
    server = _LoadCrawlServer(
        load_result=load_err,
        progress_results=[_progress_result(active=0, completed=1822, percent=100)],
    )
    client = _client_for(server, busy_retry_max=0)  # don't busy-retry the err result

    prog = client.load_crawl(
        "demo-aluminum",
        settle_timeout_seconds=5.0,
        poll_interval_seconds=0.01,
        load_fire_timeout_seconds=15.0,
    )

    assert _progress_indicates_loaded(prog) is True
    assert server.load_call_count == 1
