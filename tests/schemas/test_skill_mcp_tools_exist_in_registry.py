"""P0-03 (codex audit Phase 1): every MCP tool a skill DECLARES it needs (in its
SKILL.md `mcp_tools.required` / `.optional` frontmatter) must exist in
mcp-tool-registry.json — so the registry's tool inventory cannot drift out of
sync with what skills actually call. The registry had enumerated only 33 tools
while skill frontmatter referenced ~47 unique ones.

Also locks the D-SF-02 ScraplingServer↔scrapling alias (Task 1.4): every
.mcp.json mcpServers key must resolve to a registry server — directly, or via
that server's explicit `mcp_json_key` alias field (the same alias the runtime
F-24 check relies on through validate_invariants._MCP_JSON_KEY_ALIASES).

higgsfield is EXCLUDED here — it is an intentional user-level external
dependency (NOT a plugin .mcp.json server), represented under
external_user_dependencies and covered by test_generate_images_external_dep.py
(P1-13).
"""
import json
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

# .mcp.json server key -> mcp-tool-registry.json server key (D-SF-02 alias).
# Mirrors scripts/validation/validate_invariants.py _MCP_JSON_KEY_ALIASES.
_ALIAS = {"ScraplingServer": "scrapling"}

# Servers represented as external user dependencies (NOT plugin .mcp.json /
# registry servers); their tools are intentionally absent from registry.servers
# and validated separately (P1-13).
_EXTERNAL_SERVERS = {"higgsfield"}

_TOOL_RE = re.compile(r"mcp__([A-Za-z0-9]+)__([A-Za-z0-9_]+)")
_MCP_TOOLS_BLOCK_RE = re.compile(
    r"(?ms)^mcp_tools:[ \t]*$\n(.*?)^(?:[A-Za-z_][A-Za-z0-9_-]*:|---)"
)


def _registry() -> dict:
    return json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))


def _registry_tool_names() -> set[str]:
    reg = _registry()
    return {
        t["tool_name"]
        for srv in reg["servers"].values()
        for t in srv["tools"]
    }


def _normalize(server: str, tool: str) -> str:
    """mcp__<server>__<tool> -> registry tool_name key (server alias applied)."""
    return f"{_ALIAS.get(server, server)}__{tool}"


def _iter_skill_mcp_tools():
    """Yield (skill_path, kind, server, tool) for every mcp_tools entry across
    skills/**/SKILL.md (kind ∈ {'required','optional'}). The `mcp_tools:`
    frontmatter block is parsed with a focused regex (no YAML dependency)."""
    for skill in sorted(ROOT.glob("skills/**/SKILL.md")):
        txt = skill.read_text(encoding="utf-8")
        m = _MCP_TOOLS_BLOCK_RE.search(txt)
        if not m:
            continue
        kind = None
        for line in m.group(1).splitlines():
            if re.match(r"\s*required:\s*$", line):
                kind = "required"
                continue
            if re.match(r"\s*optional:\s*$", line):
                kind = "optional"
                continue
            tok = _TOOL_RE.search(line)
            if tok and kind:
                yield skill, kind, tok.group(1), tok.group(2)


def _missing_for(kind: str) -> list[str]:
    reg_tools = _registry_tool_names()
    missing = []
    for skill, k, server, tool in _iter_skill_mcp_tools():
        if k != kind or server in _EXTERNAL_SERVERS:
            continue
        key = _normalize(server, tool)
        if key not in reg_tools:
            missing.append(f"{key}  (<- {skill.relative_to(ROOT)})")
    return sorted(set(missing))


def test_required_skill_tools_exist_in_registry():
    missing = _missing_for("required")
    assert not missing, (
        "REQUIRED skill MCP tools absent from mcp-tool-registry.json:\n"
        + "\n".join(missing)
    )


def test_optional_skill_tools_exist_in_registry():
    missing = _missing_for("optional")
    assert not missing, (
        "OPTIONAL skill MCP tools absent from mcp-tool-registry.json "
        "(registry completeness, P0-03):\n" + "\n".join(missing)
    )


def test_mcp_json_keys_resolve_to_registry_servers():
    """Task 1.4 / D-SF-02: every .mcp.json mcpServers key must be a registry
    server key OR aliased to one via that server's `mcp_json_key`. Locks the
    ScraplingServer↔scrapling alias the runtime F-24 check already relies on."""
    cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = _registry()["servers"]
    resolvable = set(servers)
    for srv in servers.values():
        alias = srv.get("mcp_json_key")
        if alias:
            resolvable.add(alias)
    unresolved = [k for k in cfg.get("mcpServers", {}) if k not in resolvable]
    assert not unresolved, (
        f".mcp.json server keys with no registry server (direct or via "
        f"mcp_json_key alias): {unresolved}. Registry servers={sorted(servers)}"
    )
    # The specific D-SF-02 alias must be explicit, not incidental.
    assert servers.get("scrapling", {}).get("mcp_json_key") == "ScraplingServer", (
        "scrapling server must declare mcp_json_key='ScraplingServer' (the "
        "D-SF-02 alias the runtime F-24 check relies on via "
        "_MCP_JSON_KEY_ALIASES)"
    )
