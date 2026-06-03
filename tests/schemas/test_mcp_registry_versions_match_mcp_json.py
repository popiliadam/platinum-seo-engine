"""P0-03 (codex audit Phase 1): the MCP tool registry's version_lock for a
pinned server MUST equal the version actually pinned in .mcp.json. The registry
had lagged at dataforseo 2.8.9 while .mcp.json pinned @2.8.10 — a silent failure
surface per §13.1 (no semver ranges for MCP servers). This test locks the two
together so the next bump cannot land in only one file.
"""
import json
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _dataforseo_version_from_mcp_json() -> str:
    cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    args = cfg["mcpServers"]["dataforseo"]["args"]
    m = re.search(r"dataforseo-mcp-server@([0-9][0-9.]*)", " ".join(args))
    assert m, "could not find dataforseo-mcp-server@<ver> in .mcp.json"
    return m.group(1)


def test_dataforseo_version_lock_matches_mcp_json():
    reg = json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))
    lock = reg["servers"]["dataforseo"]["version_lock"]
    assert lock == _dataforseo_version_from_mcp_json(), (
        f"registry dataforseo version_lock={lock!r} != .mcp.json version "
        f"{_dataforseo_version_from_mcp_json()!r}")
