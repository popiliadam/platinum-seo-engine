"""tests/commands/test_no_obsolete_sf_mcp_curl.py — F5-cmd lock (Audit #2).

The SF MCP server speaks **MCP Streamable-HTTP** — a stateful, session-based
transport, NOT a bare JSON-RPC POST (``scripts/util/sf_mcp_client.py:8-17``).
Two probe shapes that several commands shipped are OBSOLETE and fail against the
real server:

  1. ``GET /mcp/tools`` — there is no such route. The canonical client warms a
     session via an ``initialize`` handshake (``SfMcpClient.health()``); there
     is no bare tool-list endpoint to curl.
  2. a hand-rolled ``tools/call`` JSON-RPC POST with no ``Mcp-Session-Id``
     header — the server returns HTTP 400 ``-32600`` ("Session ID required").

A reader following either gets a false DOWN / MCP_CALL_FAILED even when SF MCP
is healthy. The canonical probe is the Claude Code ``mcp__sf__*`` tool wrapper
(which performs the handshake) or ``scripts/util/sf_mcp_client.py``.

Guards (mirror the audit's "Cross-Cutting Test Gaps" #3):
  - NO command may contain ``/mcp/tools`` (always the obsolete endpoint).
  - NO executed-shell block (``!`...` `` inline / ```bash fence) may hand-roll a
    ``tools/call`` JSON-RPC POST. Prose that *describes* the
    ``initialize -> notifications/initialized -> tools/call`` handshake is
    documentation (it is not executed) and is allowed.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"

_INLINE_BANG = re.compile(r"!`([^`]*)`")
_BASH_FENCE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def _shell_blocks(text: str) -> list[str]:
    """Executed-shell bodies only: !`...` inline blocks + ```bash fences."""
    return [m.group(1) for m in _INLINE_BANG.finditer(text)] + [
        m.group(1) for m in _BASH_FENCE.finditer(text)
    ]


def test_detector_flags_synthetic_obsolete_probes() -> None:
    """Anchor: the detector recognises both obsolete shapes (no vacuous green)."""
    bad_endpoint = "!`curl -sf http://127.0.0.1:11435/mcp/tools | jq .`"
    bad_post = (
        '!`curl -X POST http://127.0.0.1:11435/mcp -d '
        "'{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{}}'`"
    )
    assert "/mcp/tools" in bad_endpoint
    assert any("tools/call" in b for b in _shell_blocks(bad_post))
    # And the detector must NOT flag prose that merely describes the handshake.
    prose = "The client performs initialize -> tools/call with a session id."
    assert not _shell_blocks(prose)


def test_no_mcp_tools_endpoint_in_commands() -> None:
    """No command may probe the obsolete GET /mcp/tools route."""
    offenders: dict[str, list[int]] = {}
    for p in _command_files():
        lines = [
            ln
            for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "/mcp/tools" in line
        ]
        if lines:
            offenders[p.name] = lines
    assert not offenders, (
        "Commands still probe the obsolete SF endpoint GET /mcp/tools (no such "
        "route — use the mcp__sf__* tool wrapper / sf_mcp_client.py):\n"
        + "\n".join(f"  {n}: lines {ls}" for n, ls in sorted(offenders.items()))
    )


def test_no_sessionless_tools_call_post_in_shell() -> None:
    """No executed-shell block may hand-roll a session-less tools/call POST."""
    offenders: dict[str, int] = {}
    for p in _command_files():
        for block in _shell_blocks(p.read_text(encoding="utf-8")):
            if "tools/call" in block:
                offenders[p.name] = offenders.get(p.name, 0) + 1
    assert not offenders, (
        "Commands hand-roll a session-less tools/call JSON-RPC POST in an "
        "executed-shell block (returns HTTP 400 -32600 'Session ID required'); "
        "route SF health through the mcp__sf__* tool wrapper instead:\n"
        + "\n".join(f"  {n}: {c} block(s)" for n, c in sorted(offenders.items()))
    )
