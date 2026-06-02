"""
tests/smoke/test_sf_mcp_smoke.py — live SF MCP smoke (CI-skip).

Runs only when SF GUI + native MCP server are active on the operator's
local machine (default port 11435). CI runners skip automatically per
the ``@pytest.mark.skipif`` gate.

When the smoke passes, it confirms:
* The SF MCP HTTP transport is reachable
* ``sf_mcp_client.SfMcpClient.call_tool`` round-trips a JSON-RPC envelope
* ``sf_list_allowed_base_directory`` returns a non-empty path string

Refs:
    * Phase 3 Worker Prompt: smoke test must skipif unreachable
    * D-SF-14 — sf_mcp_client.SfMcpClient is the canonical HTTP MCP wrapper
"""

from __future__ import annotations

import pytest

from scripts.util.sf_mcp_client import SfMcpClient


SF_MCP_BASE_URL = "http://127.0.0.1:11435/mcp"


def _is_sf_mcp_running() -> bool:
    """Quick liveness probe via the canonical client handshake.

    There is NO ``GET /health`` route on the SF MCP server — the prior probe
    (`httpx.get(.../health)`) therefore ALWAYS returned False, so this smoke
    ALWAYS skipped even when SF was live (false "covered" confidence;
    OQ-SMOKE-HEALTH-PROBE). ``SfMcpClient.health()`` performs the real MCP
    ``initialize`` handshake and returns True only when the server is reachable
    and speaks the Streamable-HTTP protocol.
    """
    try:
        return SfMcpClient(base_url=SF_MCP_BASE_URL, timeout_seconds=2.0).health()
    except Exception:
        return False


@pytest.mark.skipif(
    not _is_sf_mcp_running(),
    reason="SF MCP not connected (port 11435 unreachable or httpx missing)",
)
def test_sf_mcp_live_list_allowed_base_directory() -> None:
    """Round-trip a real JSON-RPC call to SF 24 MCP.

    Asserts:
    * sf_mcp_client.SfMcpClient can connect
    * sf_list_allowed_base_directory returns a result dict
    * Returned payload contains a non-empty allowed_directory string
      (the orchestrator's DURUR-orch-4 probe depends on this contract)
    """
    client = SfMcpClient(base_url=SF_MCP_BASE_URL, timeout_seconds=10.0)
    assert client.health(), "SfMcpClient.health() handshake failed but smoke proceeded"

    result = client.call_tool("sf_list_allowed_base_directory")
    assert isinstance(result, dict), f"expected dict, got {type(result).__name__}"
    assert not result.get("isError"), (
        f"sf_list_allowed_base_directory returned a tool error: {result!r}"
    )
    # Live shape (verified 2026-06-02): the native SF MCP returns the path in the
    # MCP content envelope — {"isError": false, "content": [{"text": "/abs/path"}]}.
    # (Older mock-era code assumed a top-level {"allowed_directory"|"value"}; keep
    # those as fallbacks for forward-compat, but the real shape is content[*].text.)
    text = "".join(
        item.get("text", "")
        for item in result.get("content", [])
        if isinstance(item, dict)
    ).strip()
    payload = text or result.get("allowed_directory") or result.get("value")
    assert isinstance(payload, str) and payload, (
        f"sf_list_allowed_base_directory must return a non-empty path; got {result!r}"
    )
