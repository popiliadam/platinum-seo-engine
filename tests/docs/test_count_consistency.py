"""
LC-5 + LC-6 — count-consistency drift guard.

Auto-validates the canonical capability manifests (.claude-plugin/plugin.json
+ marketplace.json) AND the invariant-count cites against ground truth
(filesystem counts + len(rules) + len(_RULE_FUNCTIONS)). If a skill/command/
MCP server is added, or an invariant rule lands, these tests FAIL until every
documented count is reconciled — so the counts can never silently drift again.

Scope is the CURRENT-STATE manifests + active cite spots only; frozen
historical specs/plans and resolved OQ narrative are intentionally NOT swept.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.validation import validate_invariants

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Ground-truth counters
# ---------------------------------------------------------------------------

def _count_skills() -> int:
    return len(list((_REPO_ROOT / "skills").rglob("SKILL.md")))


def _count_commands() -> int:
    return len(list((_REPO_ROOT / "commands").glob("*.md")))


def _count_mcp_servers() -> int:
    data = json.loads((_REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    return len(data.get("mcpServers", {}))


def _count_schemas() -> int:
    # README's canonical definition (line 243): all *.json in schemas/ =
    # 20 *.schema.json + cross-sheet-invariants.json = 21.
    return len(list((_REPO_ROOT / "schemas").glob("*.json")))


def _plugin_desc() -> str:
    data = json.loads((_REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    return data["description"]


def _marketplace_desc() -> str:
    data = json.loads((_REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    return data["plugins"][0]["description"]


def _read(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# LC-5 — capability manifest counts match the filesystem
# ---------------------------------------------------------------------------

def test_plugin_json_counts_match_filesystem() -> None:
    desc = _plugin_desc()
    assert f"{_count_skills()} skill" in desc
    assert f"{_count_commands()} slash command" in desc
    assert f"{_count_mcp_servers()} MCP server" in desc


def test_marketplace_json_counts_match_filesystem() -> None:
    desc = _marketplace_desc()
    assert f"{_count_skills()} skills" in desc
    assert f"{_count_commands()} commands" in desc
    assert f"{_count_mcp_servers()} MCP servers" in desc
    # codex-audit finding 13: schema count was unbound (blurb said "20 schemas"
    # while README + filesystem have 21). Lock it to the filesystem now.
    assert f"{_count_schemas()} schemas" in desc


def test_marketplace_json_has_no_stale_v17_counts() -> None:
    # The known pre-v1.7 drift the LC-5 sweep targeted must be gone.
    desc = _marketplace_desc()
    assert "43 skills" not in desc
    assert "15 commands" not in desc
    assert "3 MCP servers" not in desc


# ---------------------------------------------------------------------------
# LC-6 — invariant counts match ground truth (declared / implemented / tiers)
# ---------------------------------------------------------------------------

def _declared_count() -> int:
    data = json.loads(_read("schemas/cross-sheet-invariants.json"))
    return len(data["rules"])


def _implemented_count() -> int:
    return len(validate_invariants._RULE_FUNCTIONS)


def test_declared_invariant_count_is_31_and_cited() -> None:
    declared = _declared_count()
    assert declared == 32
    schema = json.loads(_read("schemas/cross-sheet-invariants.json"))
    assert f"{declared} CSR Registry" in schema["title"]
    assert f"{declared} Cross-Sheet Rules" in schema["description"]


def test_implemented_invariant_count_is_24_and_cited() -> None:
    implemented = _implemented_count()
    assert implemented == 25
    src = _read("scripts/validation/validate_invariants.py")
    assert f"{implemented} hand-coded invariant rules" in src
    assert f"evaluates the {implemented}" in src
    assert f"{implemented}-rule contract" in src
    assert f"{implemented}-rule registry" in src
    # Stale value must be gone.
    assert "20 hand-coded" not in src
    assert "20-rule" not in src


def test_invariant_tier_counts_sum_to_implemented() -> None:
    src = _read("scripts/validation/validate_invariants.py")
    tiers = {m.group(1): int(m.group(2))
             for m in re.finditer(r"# (CRITICAL|HIGH|MEDIUM) \((\d+)\)", src)}
    assert tiers == {"CRITICAL": 5, "HIGH": 14, "MEDIUM": 6}
    assert sum(tiers.values()) == _implemented_count()


def test_drift_check_skill_narrative_counts() -> None:
    implemented = _implemented_count()
    doc = _read("skills/governance/drift-check/SKILL.md")
    assert f"`evaluate_invariants` ({implemented} rules)" in doc
    assert f"The {implemented} rules are partitioned" in doc
    assert f"## {implemented} Invariant Rules" in doc
    # Tier table mirrors validate_invariants section comments.
    assert "| HIGH      | 14    |" in doc
    assert "| MEDIUM    | 6     |" in doc
    # Stale narrative gone.
    assert "(20 rules)" not in doc
    assert "The 21 rules" not in doc


def test_sibling_invariant_cites_match_implemented() -> None:
    implemented = _implemented_count()
    for rel in ("skills/reporting/monitoring-weekly/SKILL.md", "rules/events-writer.md"):
        text = _read(rel)
        assert f"invariants:{implemented}" in text, rel
        # Stale literal cites must be gone (wildcard invariants:* is fine).
        assert "invariants:20" not in text, rel
        assert "invariants:21" not in text, rel


def test_drift_check_test_count_cite_matches_actual() -> None:
    actual = len(re.findall(r"^\s*def test_", _read("tests/skills/test_drift_check.py"), re.M))
    doc = _read("skills/governance/drift-check/SKILL.md")
    assert f"({actual} cases incl. live pilot)" in doc
    assert "(11 cases" not in doc


# ---------------------------------------------------------------------------
# Phase 6 cleanup — doc/comment count drift guards (P2-02, P3-03 + carry-overs)
#
# Each cite below is anchored to a GROUND-TRUTH counter so a future
# skill/invariant/MCP-server change can never leave a stale literal behind.
# ---------------------------------------------------------------------------

def test_skills_count_is_45() -> None:
    """Mechanical lock: 47 SKILL.md on disk. Every doc/comment cite that
    names the skill count must track this number."""
    assert _count_skills() == 47


def test_glossary_cites_current_invariant_count() -> None:
    """docs/GLOSSARY.md Invariant definition must cite the live CSR rule
    count (31, len(cross-sheet-invariants.rules)), never the stale pre-SF
    '28'."""
    glossary = _read("docs/GLOSSARY.md")
    assert f"{_declared_count()} CSR rule" in glossary
    assert "28 CSR rule" not in glossary


def test_generate_images_cites_current_mcp_server_count() -> None:
    """skills/production/generate-images/SKILL.md MCP-boundary cites must
    track the live .mcp.json server count (4: gsc/dataforseo/ScraplingServer/
    sf), never the stale '3 servers'."""
    doc = _read("skills/production/generate-images/SKILL.md")
    assert f"{_count_mcp_servers()} servers" in doc
    assert "3 servers" not in doc


def test_skill_count_comments_track_filesystem() -> None:
    """Test/CI comments that cite the SKILL.md count must track the live
    number (45), never the stale '43'."""
    skills = _count_skills()
    for rel in (
        "tests/ci/test_ci_yaml.py",
        "tests/schemas/test_events_schema_event_type_enum_v1_1.py",
    ):
        text = _read(rel)
        assert f"{skills} SKILL.md" in text, rel
        assert "43 SKILL.md" not in text, rel


def test_dump_workspace_docstring_reads_active_project() -> None:
    """scripts/state/dump_workspace.py must describe reading the
    active_project key (the code's real behavior since the legacy 'slug'
    rename), not the stale 'bound slug'."""
    src = _read("scripts/state/dump_workspace.py")
    assert "active_project" in src
    assert "bound slug" not in src
