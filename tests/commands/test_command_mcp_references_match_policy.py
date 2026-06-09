"""tests/commands/test_command_mcp_references_match_policy.py — F8 lock (Audit #2).

POLICY — MCP tools in slash commands
====================================
Slash commands are **skill-routing wrappers**. MCP tools (``mcp__server__tool``)
execute at the **skill level** — declared in the target skill's frontmatter
``mcp_tools`` and invoked in the skill body. A command lists MCP tools in its
own ``allowed-tools`` ONLY when the command/model drives the call directly:
an inline command with no skill (the SF health probe in ``/pseo-sf-status``),
or a multi-skill orchestrator that drives MCP across projects
(``/pseo-run-portfolio``).

Why this policy (and not "every body ref must be in allowed-tools"): these
commands route to skills whose frontmatter already declares the MCP tools.
Dumping those tools into the command's ``allowed-tools`` too would falsely
imply the command invokes them via its own ``!`...` `` shell — it does not
(shell cannot call MCP tools). The honest contract is: the command routes, the
skill owns the MCP call.

Enforced per command:
  P1 (HARD): no ``mcp__`` token may appear inside an executed-shell block
     (``!`...` `` inline / ```bash fence). Shell cannot invoke MCP tools — such
     a reference is a runtime-break bug (Claude Code would prompt or refuse).
  P2 (COVERAGE): every ``mcp__`` tool referenced in a command BODY is covered by
     exactly one of:
       (a) declared in that command's ``allowed-tools`` (command drives it), OR
       (b) the command routes to a skill (cites ``skills/.../SKILL.md``) that
           owns MCP execution, OR
       (c) the reference is an explicitly-listed governance EXAMPLE
           (``_ILLUSTRATIVE_REFS``) — the command names an outward MCP action it
           gates but never invokes.

This converts the audit's "false sense of command safety" into an explicit,
tested architectural contract: a command can never silently reference an MCP
tool that is neither permitted, delegated to a skill, nor a declared example.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"

# mcp__<server>__<tool>; server segment tolerates mixed case + hyphens
# (e.g. mcp__ScraplingServer__fetch, mcp__meta-ad-library-mcp__x).
_MCP = re.compile(r"mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_]+")
_INLINE_BANG = re.compile(r"!`([^`]*)`")
_BASH_FENCE = re.compile(r"```bash\s*\n(.*?)```", re.DOTALL)
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_ALLOWED = re.compile(r"^allowed-tools:\s*(.+)$", re.MULTILINE)
_SKILL_ROUTE = re.compile(r"skills/[A-Za-z0-9_/-]+/SKILL\.md")

# Governance commands that NAME an MCP outward-action as an illustrative example
# (Turkish "ör." = e.g.) but never invoke it. /pseo-approve writes the
# hash-chained consent ledger; the actual sitemap submit happens later,
# elsewhere, behind that consent — so the token is documentation, not a call.
_ILLUSTRATIVE_REFS: dict[str, set[str]] = {
    "pseo-approve.md": {"mcp__gsc__submit_sitemap"},
}


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def _shell_blocks(text: str) -> list[str]:
    return [m.group(1) for m in _INLINE_BANG.finditer(text)] + [
        m.group(1) for m in _BASH_FENCE.finditer(text)
    ]


def _allowed_mcp(text: str) -> set[str]:
    """MCP tools declared on the frontmatter allowed-tools line."""
    fm = _FRONTMATTER.search(text)
    if not fm:
        return set()
    m = _ALLOWED.search(fm.group(1))
    return set(_MCP.findall(m.group(1))) if m else set()


def _body_mcp(text: str) -> set[str]:
    """All mcp__ refs OUTSIDE the frontmatter (skill-chain prose, deps, etc.)."""
    fm = _FRONTMATTER.search(text)
    body = text[fm.end():] if fm else text
    return set(_MCP.findall(body))


def test_parser_finds_known_mcp_refs() -> None:
    """Anchor: the body + allowed-tools extractors see real refs (no vacuous green)."""
    gsc = (COMMANDS / "pseo-gsc-pull.md").read_text(encoding="utf-8")
    assert "mcp__gsc__search_analytics" in _body_mcp(gsc)
    portfolio = (COMMANDS / "pseo-run-portfolio.md").read_text(encoding="utf-8")
    assert "mcp__higgsfield__generate_image" in _allowed_mcp(portfolio)


def test_no_mcp_tool_invoked_in_executed_shell() -> None:
    """P1: shell cannot invoke MCP tools — none may appear in !`...`/```bash."""
    offenders: dict[str, list[str]] = {}
    for p in _command_files():
        hits = sorted(
            {t for b in _shell_blocks(p.read_text(encoding="utf-8")) for t in _MCP.findall(b)}
        )
        if hits:
            offenders[p.name] = hits
    assert not offenders, (
        "MCP tools referenced inside executed-shell blocks (shell cannot invoke "
        "MCP — route to a skill or have the model call the tool wrapper):\n"
        + "\n".join(f"  {n}: {h}" for n, h in sorted(offenders.items()))
    )


def test_every_mcp_reference_is_covered() -> None:
    """P2: each body MCP ref is declared, skill-routed, or an illustrative example."""
    offenders: dict[str, list[str]] = {}
    for p in _command_files():
        text = p.read_text(encoding="utf-8")
        body_refs = _body_mcp(text)
        if not body_refs:
            continue
        declared = _allowed_mcp(text)
        skill_routed = bool(_SKILL_ROUTE.search(text))
        illustrative = _ILLUSTRATIVE_REFS.get(p.name, set())
        uncovered = sorted(
            t
            for t in body_refs
            if t not in declared and not skill_routed and t not in illustrative
        )
        if uncovered:
            offenders[p.name] = uncovered
    assert not offenders, (
        "Command MCP references are neither declared in allowed-tools, nor "
        "covered by a skill route, nor listed as a governance example "
        "(_ILLUSTRATIVE_REFS):\n"
        + "\n".join(f"  {n}: {u}" for n, u in sorted(offenders.items()))
    )
