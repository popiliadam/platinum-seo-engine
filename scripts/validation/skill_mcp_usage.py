"""AMO batch 3a — static lint #1: a skill's BODY-invoked MCP tools ⊆ its
DECLARED ``mcp_tools``. This is the COMPLEMENT of
``tests/schemas/test_skill_mcp_tools_exist_in_registry.py`` (which enforces
``declared ⊆ registry``). Together they close the triangle
``used ⊆ declared ⊆ registry`` — an undeclared MCP dependency can no longer hide.

Pure / no side effects: every function reads only the text (or single path) it is
given. The declared-side parsing MIRRORS the registry test EXACTLY (same
``_MCP_TOOLS_BLOCK_RE`` + ``_TOOL_RE`` + ``ScraplingServer→scrapling`` alias) so the
two halves agree on what "declared" means. ``invoked_tools`` is the new,
invocation-PRECISE half: it matches actual call sites, never prose mentions or
variable-dispatched calls.

A skill invokes an MCP tool three structurally distinct ways, so the detector has
three matchers:

  A) qualified call  — ``mcp__<server>__<tool>(`` (e.g. on-page-audit's
     ``mcp__gsc__search_analytics(...)``; sf-crawl-orchestrator's
     ``mcp__sf__sf_list_crawls()``). A backtick mention with NO call parens
     (monthly-report's prose) is NOT a call.
  B) native literal  — ``call_tool("sf_list_crawls")`` / ``call_tool(tool_name=...)``
     with a STRING-LITERAL first arg. A variable/f-string first arg
     (``call_tool(tool, ...)`` from SF_EXPORT_DISPATCH) is unresolvable statically
     and is NOT a call.
  C) wrapper method  — a known ``SfMcpClient`` method that maps 1:1 to a registry
     ``sf_`` tool. Only ``load_crawl`` qualifies: ``health()`` is an MCP initialize
     handshake (no ``sf_`` tool), ``call_tool`` is handled by class B, and every
     other public method is transport plumbing.

Paths are anchored file-relative (``Path(__file__).resolve().parents[2]``), NOT
``CLAUDE_PLUGIN_ROOT`` — an installed-plugin copy could otherwise shadow the
working tree (the 0c bare-CLI lesson).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

#: Repo root — scripts/validation/skill_mcp_usage.py -> parents[2].
ROOT = Path(__file__).resolve().parents[2]

# --- declared-side (mirrors test_skill_mcp_tools_exist_in_registry.py) ------
#: .mcp.json server key -> registry server key (D-SF-02 alias).
_ALIAS = {"ScraplingServer": "scrapling"}
#: External user-level servers whose tools live outside registry.servers.
_EXTERNAL_SERVERS = {"higgsfield"}
_TOOL_RE = re.compile(r"mcp__([A-Za-z0-9]+)__([A-Za-z0-9_]+)")
_MCP_TOOLS_BLOCK_RE = re.compile(
    r"(?ms)^mcp_tools:[ \t]*$\n(.*?)^(?:[A-Za-z_][A-Za-z0-9_-]*:|---)"
)

# --- invoked-side (NEW) — invocation-precise call-site matchers -------------
#: A) qualified call: ``mcp__server__tool`` immediately followed by ws + ``(``.
_QUALIFIED_CALL_RE = re.compile(r"mcp__([A-Za-z0-9]+)__([A-Za-z0-9_]+)[ \t]*\(")
#: B) native literal: ``call_tool(`` with a STRING-LITERAL first arg (positional
#:    or ``tool_name="..."``). A non-literal first arg never matches (no quote).
_CALL_TOOL_LITERAL_RE = re.compile(
    r"""call_tool\([ \t]*(?:tool_name[ \t]*=[ \t]*)?["']([a-z][a-z0-9_]+)["']"""
)
#: C) ``SfMcpClient`` wrapper methods that map 1:1 to a registry ``sf_`` tool.
_SF_WRAPPER_METHODS = {"load_crawl": "sf_load_crawl"}


def _alias(server: str) -> str:
    return _ALIAS.get(server, server)


def split_frontmatter_body(text: str) -> tuple[str, str]:
    """Split ``text`` on the FIRST TWO ``---``-only lines (line-based).

    Returns ``(frontmatter, body)``. A markdown ``---`` horizontal rule inside the
    body does NOT re-trigger the split (only the first two fences count). Fewer
    than two fences -> ``("", text)``: a malformed skill simply has no declarations
    (a real gap, not a crash).
    """
    lines = text.splitlines(keepends=True)
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2:
        return "", text
    first, second = fences[0], fences[1]
    return "".join(lines[first + 1:second]), "".join(lines[second + 1:])


def declared_tools(frontmatter: str) -> set[str]:
    """Registry-key set declared in the ``mcp_tools`` block (required ∪ optional).

    Mirrors the registry test: same block regex, same ``_TOOL_RE``, same alias. A
    sentinel terminator is appended so the block regex resolves even if
    ``mcp_tools`` is the last key in the frontmatter substring.
    """
    match = _MCP_TOOLS_BLOCK_RE.search(frontmatter + "\n---\n")
    if not match:
        return set()
    declared: set[str] = set()
    kind: str | None = None
    for line in match.group(1).splitlines():
        if re.match(r"\s*required:\s*$", line):
            kind = "required"
        elif re.match(r"\s*optional:\s*$", line):
            kind = "optional"
        else:
            token = _TOOL_RE.search(line)
            if token and kind:
                declared.add(f"{_alias(token.group(1))}__{token.group(2)}")
    return declared


def invoked_tools(body: str) -> set[str]:
    """Registry-key set of ACTUAL MCP invocations in a skill ``body``.

    Matches the three invocation classes (qualified call, native ``call_tool``
    string literal, known ``SfMcpClient`` wrapper). Prose mentions (a backtick
    token with no call parens) and variable-dispatched ``call_tool(var, ...)``
    are NOT invocations and are NOT returned. The ``higgsfield`` external server
    is skipped (its tools live outside the registry).
    """
    invoked: set[str] = set()
    for server, tool in _QUALIFIED_CALL_RE.findall(body):
        if server not in _EXTERNAL_SERVERS:
            invoked.add(f"{_alias(server)}__{tool}")
    for native_tool in _CALL_TOOL_LITERAL_RE.findall(body):
        invoked.add(f"sf__{native_tool}")
    for method, native_tool in _SF_WRAPPER_METHODS.items():
        if re.search(r"\." + re.escape(method) + r"[ \t]*\(", body):
            invoked.add(f"sf__{native_tool}")
    return invoked


def body_not_declared(skill_path: str | os.PathLike[str]) -> set[str]:
    """The gap for ONE skill: ``invoked_tools(body) - declared_tools(frontmatter)``."""
    text = Path(skill_path).read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter_body(text)
    return invoked_tools(body) - declared_tools(frontmatter)


def iter_skill_gaps(root: str | os.PathLike[str] = ROOT) -> dict[str, set[str]]:
    """``{skill_relpath: gap_set}`` for every skill with a non-empty body⊄declared gap."""
    root_path = Path(root)
    gaps: dict[str, set[str]] = {}
    for skill in sorted(root_path.glob("skills/**/SKILL.md")):
        gap = body_not_declared(skill)
        if gap:
            gaps[str(skill.relative_to(root_path))] = gap
    return gaps
