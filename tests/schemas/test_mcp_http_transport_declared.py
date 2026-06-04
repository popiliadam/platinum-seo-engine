"""Guard: HTTP MCP servers in .mcp.json must declare type:http.

Root-cause regression guard for the 2026-06-04 Codex P0-01 finding. Claude
Code defaults an entry's transport to stdio when `type` is absent; a bare
{"url": ...} entry (like `sf` since v1.8) therefore silently fails to register
and never appears in `claude mcp list`, even though the other 3 stdio servers
do. Any entry that has a `url` and no `command` MUST declare "type": "http".
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_url_only_mcp_servers_declare_http_type() -> None:
    cfg = json.loads((ROOT / ".mcp.json").read_text())
    for name, spec in cfg["mcpServers"].items():
        if "url" in spec and "command" not in spec:
            assert spec.get("type") == "http", (
                f"MCP server {name!r} has a url but no 'type': 'http' — Claude "
                f"Code defaults to stdio and the server fails to register"
            )
