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

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

from scripts.util.sf_mcp_client import SfMcpClient


SF_MCP_BASE_URL = "http://127.0.0.1:11435/mcp"


def _is_sf_mcp_running() -> bool:
    """Quick liveness probe — single GET to /health with 1s timeout."""
    if not _HTTPX_AVAILABLE:
        return False
    try:
        resp = httpx.get(f"{SF_MCP_BASE_URL}/health", timeout=1.0)
        return resp.status_code == 200
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
    assert client.health(), "SF MCP /health failed but smoke proceeded"

    result = client.call_tool("sf_list_allowed_base_directory")
    assert isinstance(result, dict), f"expected dict, got {type(result).__name__}"
    # The native SF MCP returns either {"allowed_directory": "..."} or a
    # plain string wrapped in {"value": "..."}; both shapes are accepted by
    # the orchestrator body (it normalizes via isinstance check).
    payload = result.get("allowed_directory") or result.get("value")
    assert isinstance(payload, str) and payload, (
        f"sf_list_allowed_base_directory must return a non-empty path; got {result!r}"
    )
