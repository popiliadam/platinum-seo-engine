"""tests/scripts/test_sf_mcp_client.py — v1.8 Phase 2 D-SF-14 HTTP MCP client.

5 cases covering the Worker Prompt verification matrix:

    1. JSON-RPC envelope formatting (POST body shape)
    2. Timeout → SfMcpTimeoutError after 3 attempts
    3. 3-retry exponential backoff on connection errors
    4. Response size cap → SfMcpResponseTooLargeError
    5. Redirect handling (301 → 200 follow)

Mocking: ``httpx.MockTransport`` (built into httpx — no extra dependency).
The transport handler is a callable ``(httpx.Request) -> httpx.Response``;
the client injects it via the ``transport=`` kwarg, so no monkey-patching.

Refs:
    * scripts/util/sf_mcp_client.py (system under test)
    * D-SF-14 (first reusable HTTP MCP client)
"""

from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from scripts.util.sf_mcp_client import (
    DEFAULT_MAX_RESPONSE_BYTES,
    RETRY_DELAYS_SECONDS,
    SfMcpClient,
    SfMcpConnectionError,
    SfMcpResponseTooLargeError,
    SfMcpTimeoutError,
    SfMcpToolError,
)


BASE_URL = "http://127.0.0.1:11435/mcp"


def _ok_envelope(request_id: str, result: dict | str | list | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result if result is not None else {"ok": True},
    }


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    timeout_seconds: float = 30.0,
) -> SfMcpClient:
    transport = httpx.MockTransport(handler)
    return SfMcpClient(
        BASE_URL,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        transport=transport,
    )


# ---------------------------------------------------------------------------
# Case 1: JSON-RPC envelope formatting
# ---------------------------------------------------------------------------

def test_call_tool_emits_jsonrpc_2_0_envelope() -> None:
    """POST body must match the JSON-RPC 2.0 ``tools/call`` spec exactly."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_ok_envelope(captured["body"]["id"],
                                                    result={"echo": "pong"}))

    client = _make_client(handler)
    result = client.call_tool("sf_crawl", start_url="https://example.com", max_pages=10)

    assert captured["method"] == "POST"
    assert captured["url"] == BASE_URL

    body = captured["body"]
    assert body["jsonrpc"] == "2.0", "JSON-RPC version must be exactly '2.0'"
    assert body["method"] == "tools/call", "method must be 'tools/call'"
    assert body["params"]["name"] == "sf_crawl"
    assert body["params"]["arguments"] == {
        "start_url": "https://example.com",
        "max_pages": 10,
    }
    assert isinstance(body["id"], str) and len(body["id"]) == 32, \
        "id must be a uuid4().hex (32 chars)"

    assert result == {"echo": "pong"}


# ---------------------------------------------------------------------------
# Case 2: Timeout exhausts retries → SfMcpTimeoutError
# ---------------------------------------------------------------------------

def test_call_tool_timeout_raises_after_three_attempts(monkeypatch) -> None:
    """All 3 attempts time out → SfMcpTimeoutError, sleep called twice (between)."""
    attempts = {"count": 0}
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ReadTimeout("simulated read timeout", request=request)

    client = _make_client(handler, timeout_seconds=0.01)

    with pytest.raises(SfMcpTimeoutError) as exc_info:
        client.call_tool("sf_crawl_progress", run_id="abc")

    assert attempts["count"] == 3, "client must attempt exactly 3 times"
    assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]], (
        f"client must sleep (1s, 2s) between attempts; got {sleeps}"
    )
    assert "timed out" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# Case 3: 3-retry exponential backoff on connection errors
# ---------------------------------------------------------------------------

def test_call_tool_retries_three_times_with_exp_backoff(monkeypatch) -> None:
    """Connection error on attempts 1 and 2; success on attempt 3 → no exception.

    Verifies the exp-backoff schedule (1s, 2s) is consulted in order.
    """
    attempts = {"count": 0}
    sleeps: list[float] = []
    monkeypatch.setattr("scripts.util.sf_mcp_client.time.sleep", sleeps.append)

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ConnectError("connection refused", request=request)
        body = json.loads(request.content)
        return httpx.Response(200, json=_ok_envelope(body["id"], result={"recovered": True}))

    client = _make_client(handler)
    result = client.call_tool("sf_generate_report", report_name="page_titles_all")

    assert attempts["count"] == 3, "expected exactly 3 attempts (2 failures + 1 success)"
    assert sleeps == [RETRY_DELAYS_SECONDS[0], RETRY_DELAYS_SECONDS[1]], (
        f"backoff must be exactly (1s, 2s) between attempts 1→2 and 2→3; got {sleeps}"
    )
    assert result == {"recovered": True}

    # And: when ALL 3 attempts fail → SfMcpConnectionError (no 4th attempt).
    attempts["count"] = 0
    sleeps.clear()

    def always_fail(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    client2 = _make_client(always_fail)
    with pytest.raises(SfMcpConnectionError) as exc_info:
        client2.call_tool("sf_crawl", start_url="https://example.com")

    assert attempts["count"] == 3, "must not exceed 3 attempts even on continuous failure"
    assert len(sleeps) == 2, "exactly 2 sleeps between 3 attempts (no trailing sleep)"
    assert "3 attempts" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Case 4: Response size cap raises SfMcpResponseTooLargeError
# ---------------------------------------------------------------------------

def test_call_tool_response_too_large_raises() -> None:
    """Body > max_response_bytes → SfMcpResponseTooLargeError."""
    big_payload = "x" * (1000 + 1)  # 1001 bytes — over a small 1000-byte cap

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json=_ok_envelope(body["id"], result={"blob": big_payload}),
        )

    client = _make_client(handler, max_response_bytes=1000)
    with pytest.raises(SfMcpResponseTooLargeError) as exc_info:
        client.call_tool("sf_generate_report", report_name="all_inlinks")

    assert "exceeds" in str(exc_info.value)
    assert "1000" in str(exc_info.value)

    # And: HTTP 4xx must surface as SfMcpToolError (no retry) — sibling sanity
    # to confirm size-cap path doesn't swallow status semantics.
    def bad_request_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad arguments")

    client2 = _make_client(bad_request_handler)
    with pytest.raises(SfMcpToolError) as exc_info_2:
        client2.call_tool("sf_crawl", start_url="not-a-url")
    assert exc_info_2.value.status_code == 400


# ---------------------------------------------------------------------------
# Case 5: Redirect handling (307 → 200 follow, preserves POST + body)
# ---------------------------------------------------------------------------

def test_call_tool_follows_307_redirect_preserving_post_body() -> None:
    """307 Temporary Redirect must be followed; method (POST) + body preserved.

    Per RFC 7231 §6.4.7: only 307/308 explicitly preserve the request method
    and body. An MCP JSON-RPC server using redirects in practice MUST use 307
    (or 308), because 301/302/303 would downgrade POST→GET and drop the
    envelope body — silently breaking every tool call. This test pins that
    follow-redirects behavior end-to-end (envelope round-trips through the
    redirect intact).
    """
    redirect_target = BASE_URL + "/v2"
    call_log: list[tuple[str, str]] = []  # (url, method)
    bodies_received: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        call_log.append((url, request.method))
        if url == BASE_URL:
            return httpx.Response(
                307,
                headers={"location": redirect_target},
                text="",
            )
        # Redirected target — POST + body must still be present.
        body = json.loads(request.content)
        bodies_received.append(body)
        return httpx.Response(
            200,
            json=_ok_envelope(body["id"], result={"final": "yes"}),
        )

    client = _make_client(handler)
    result = client.call_tool("sf_list_crawls")

    assert call_log == [
        (BASE_URL, "POST"),
        (redirect_target, "POST"),
    ], f"expected POST on both original and redirected URL; got {call_log}"
    assert len(bodies_received) == 1, "redirected target must receive the envelope body"
    body = bodies_received[0]
    assert body["jsonrpc"] == "2.0"
    assert body["method"] == "tools/call"
    assert body["params"]["name"] == "sf_list_crawls"
    assert result == {"final": "yes"}
