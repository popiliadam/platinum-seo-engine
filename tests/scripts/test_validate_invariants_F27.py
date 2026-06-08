"""tests/scripts/test_validate_invariants_F27.py — AMO batch 3-gov-driftF.

F-27 (csr_mcp, ENGINE-governance): every OUTWARD MCP tool a skill DECLARES in
its ``mcp_tools`` frontmatter MUST be covered by an ``outward_action_gate``
matcher (the gate's gated-MCP set). An ungated declared outward MCP tool is a
silent hole in the batch-2b consent wall (Süleyman's Indexing hard-constraint):
the action would ship without the per-session consent gate.

Mirrors the F-24 engine-governance test shape — the rule ignores the
``workbook`` + ``workspace_root`` and reads the skills tree + the IMPORTED gate
constant. The skills root is injected via ``skills_root=`` so a tmp tree can
force PASS / FAIL / AMBER deterministically; the gate matcher is the imported
``_MCP_SUBMIT_TOOL`` (monkeypatched to simulate a gate that forgot a tool).
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from scripts.validation import validate_invariants
from scripts.validation.validate_invariants import check_F_27


def _stub_workbook() -> Workbook:
    """F-27 is engine-governance — it ignores the workbook arg (mirror F-24)."""
    return Workbook()


def _write_skill(
    skills_root: Path,
    relpath: str,
    *,
    required: list[str] | None = None,
    optional: list[str] | None = None,
) -> None:
    """Seed ``skills_root/<relpath>/SKILL.md`` declaring the given ``mcp_tools``
    (qualified ``mcp__server__tool`` form, as real skills declare them)."""
    lines = ["---", f"name: {relpath.replace('/', '-')}", "mcp_tools:"]
    if required:
        lines.append("  required:")
        lines += [f"    - {tool}" for tool in required]
    if optional:
        lines.append("  optional:")
        lines += [f"    - {tool}" for tool in optional]
    lines += ["description: synthetic", "---", "body", ""]
    path = skills_root / relpath / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# --- live regression lock: the REAL skills tree is clean ---------------------

def test_real_tree_passes() -> None:
    """Live engine state: the only outward MCP tool any skill declares is
    ``gsc__submit_sitemap`` and the 2b gate covers it → PASS HIGH."""
    result = check_F_27(_stub_workbook(), "demo")
    assert result["verdict"] == "PASS", result
    assert result["severity"] == "HIGH"
    assert "gsc__submit_sitemap" in result["evidence"]


def test_real_tree_no_false_positive_amber() -> None:
    """Zero-false-positive lock: no real declared tool trips the AMBER
    outward-looking tripwire (every non-submit tool is a read/query verb), so
    the real tree is PASS, never the MEDIUM/AMBER branch."""
    result = check_F_27(_stub_workbook(), "demo")
    assert result["verdict"] == "PASS"
    assert result["severity"] != "MEDIUM"


# --- precision: a read-only skill is NEVER flagged ---------------------------

def test_read_only_tools_pass(tmp_path: Path) -> None:
    """A skill declaring ONLY GSC read tools (index_inspect / list / get) must
    NOT be flagged — locks the read-verb exclusion against false-positives
    (the explicit DURUR: do NOT flag gsc__index_inspect/list_sitemaps/get)."""
    _write_skill(
        tmp_path,
        "reporting/reads-only",
        required=[
            "mcp__gsc__index_inspect",
            "mcp__gsc__list_sitemaps",
            "mcp__gsc__get_sitemap",
        ],
    )
    result = check_F_27(_stub_workbook(), "demo", skills_root=tmp_path)
    assert result["verdict"] == "PASS", result


# --- FAIL: an ungated declared OUTWARD tool is a hole in the consent wall -----

def test_ungated_outward_tool_fails(tmp_path: Path, monkeypatch) -> None:
    """A skill declares ``gsc__submit_sitemap`` (a curated OUTWARD tool) but the
    gate matcher set no longer covers it (gate forgot it) → FAIL HIGH, the tool
    named in ``sample_violations``."""
    _write_skill(
        tmp_path, "publishing/pinger",
        required=["mcp__gsc__submit_sitemap"],
    )
    # Simulate a gate whose only MCP matcher is NOT the submit tool.
    monkeypatch.setattr(
        validate_invariants, "_MCP_SUBMIT_TOOL", "mcp__gsc__not_the_submit_tool"
    )
    result = check_F_27(_stub_workbook(), "demo", skills_root=tmp_path)
    assert result["verdict"] == "FAIL", result
    assert result["severity"] == "HIGH"
    assert any("gsc__submit_sitemap" in v for v in result["sample_violations"])


def test_gate_hole_without_declaration_fails(monkeypatch) -> None:
    """Even with NO skill declaring it, a curated outward tool the gate forgot
    (``_OUTWARD_MCP_TOOLS ⊄ gate_matchers``) is a gate hole → FAIL HIGH."""
    monkeypatch.setattr(
        validate_invariants, "_MCP_SUBMIT_TOOL", "mcp__gsc__not_the_submit_tool"
    )
    result = check_F_27(_stub_workbook(), "demo")  # real tree, broken gate
    assert result["verdict"] == "FAIL", result
    assert result["severity"] == "HIGH"
    assert any("gsc__submit_sitemap" in v for v in result["sample_violations"])


# --- AMBER: an outward-LOOKING tool nobody classified ------------------------

def test_unclassified_outward_tool_ambers(tmp_path: Path) -> None:
    """A skill declares a FUTURE outward-looking tool (``indexing__url_updated``)
    that is NOT in ``_OUTWARD_MCP_TOOLS`` and is not a read verb → AMBER
    (MEDIUM severity + FAIL verdict, which §17.2 maps to AMBER): review and
    classify it before it ships ungated."""
    _write_skill(
        tmp_path, "publishing/future-indexer",
        optional=["mcp__indexing__url_updated"],
    )
    result = check_F_27(_stub_workbook(), "demo", skills_root=tmp_path)
    assert result["verdict"] == "FAIL", result
    assert result["severity"] == "MEDIUM"  # MEDIUM → AMBER per §17.2
    assert any("url_updated" in v for v in result["sample_violations"])


# --- SKIP: missing skills tree (engine state ambiguous → AMBER) --------------

def test_missing_skills_root_skips(tmp_path: Path) -> None:
    """A skills_root that does not exist → SKIP (mirror F-24 missing-file SKIP:
    engine state ambiguous, surfaces AMBER, never a false RED)."""
    result = check_F_27(_stub_workbook(), "demo", skills_root=tmp_path / "nope")
    assert result["verdict"] == "SKIP", result
