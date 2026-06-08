"""AMO batch 3-gov-lint2 — static lint #2: every workflow STEP's required MCP
``tool`` ⊆ the DECLARED ``mcp_tools`` of the skill that runs that step ⊆ the MCP
registry. Stacks ABOVE batch 3a (``body ⊆ declared ⊆ registry`` for SKILLS): the
orchestrator pins, per workflow step, the MCP tool that step calls; this lint
proves that pinned tool is declared by the owning skill AND exists in the
registry — so a workflow and a skill cannot drift apart silently.

    workflow STEPS[].tool  ⊆  owning-skill declared mcp_tools  ⊆  registry

TDD shape (RED-first): the lint module is imported LAZILY inside the
module-dependent tests (UNIT / DISCOVERY / MAIN), so — before the module exists —
they fail with ModuleNotFoundError (an ImportError), WHILE the self-contained
TEETH test still runs and PROVES the detection is non-vacuous (a planted
synthetic gap trips BOTH the not-declared and absent-from-registry predicates).
TEETH deliberately mirrors the two predicates using batch 3a's ``declared_tools``
plus an inline registry read, so it needs no dependency on the not-yet-built
module.
"""
from __future__ import annotations

import importlib
import json
import pathlib

import pytest

from scripts.validation.skill_mcp_usage import declared_tools, split_frontmatter_body

ROOT = pathlib.Path(__file__).resolve().parents[2]
_MODULE = "scripts.validation.workflow_tool_declared"

#: The exact tool-bearing steps the orchestrator pins today (manager-verified,
#: fact D) in ``iter_workflow_tool_steps`` shape ``(workflow, step, writer,
#: normalized_tool)``. The three tool=None / no-tool steps (schema_audit,
#: new_content_plan, content_pipeline.*) are intentionally ABSENT.
_EXPECTED_STEPS = (
    ("monthly_maintenance", "gsc_pull", "gsc-pull", "gsc__search_analytics"),
    ("monthly_maintenance", "quick_wins", "quick-wins", "gsc__detect_quick_wins"),
    ("monthly_maintenance", "content_decay", "content-decay",
     "gsc__enhanced_search_analytics"),
    ("audit_suite", "tech_audit", "tech-audit", "dataforseo__on_page_lighthouse"),
    ("audit_suite", "on_page_audit", "on-page-audit",
     "dataforseo__on_page_content_parsing"),
    ("audit_suite", "cannibalization", "cannibalization", "gsc__search_analytics"),
    ("new_project_setup", "topical_map", "topical-map",
     "dataforseo__dataforseo_labs_google_keyword_ideas"),
    ("new_project_setup", "cluster_map", "cluster-map",
     "dataforseo__dataforseo_labs_google_keyword_suggestions"),
)


def _load():
    """Import the lint module (lazily — absent in the RED phase -> ImportError)."""
    return importlib.import_module(_MODULE)


def _param_steps():
    """Collection-time parametrize source: the module's real discovery once it
    exists (so a FUTURE workflow step is auto-covered), else the literal
    ``_EXPECTED_STEPS`` so MAIN still parametrizes 8 RED cases pre-build."""
    try:
        module = importlib.import_module(_MODULE)
    except ImportError:
        return sorted(_EXPECTED_STEPS)
    return sorted(module.iter_workflow_tool_steps())


_PARAM = _param_steps()
_IDS = [f"{wf}.{step}" for wf, step, _writer, _tool in _PARAM]


# --- UNIT -------------------------------------------------------------------
def test_normalize_tool_strips_five_char_prefix():
    normalized = _load().normalize_tool("mcp__gsc__search_analytics")
    assert normalized == "gsc__search_analytics"
    assert not normalized.startswith("_")  # locks 5-char removeprefix vs naive [4:]


def test_normalize_tool_aliases_scrapling_server():
    assert _load().normalize_tool(
        "mcp__ScraplingServer__sf_load_crawl"
    ) == "scrapling__sf_load_crawl"


def test_registry_tool_names_contains_known_keys():
    names = _load().registry_tool_names()
    assert "gsc__search_analytics" in names
    assert "dataforseo__on_page_lighthouse" in names


def test_resolve_skill_hits_and_misses():
    module = _load()
    hit = module.resolve_skill("gsc-pull")
    assert hit is not None
    assert str(hit).endswith("gsc-pull/SKILL.md")
    assert module.resolve_skill("definitely-not-a-skill") is None


# --- DISCOVERY --------------------------------------------------------------
def test_discovery_is_exactly_the_eight_tool_bearing_steps():
    steps = set(_load().iter_workflow_tool_steps())
    assert steps == set(_EXPECTED_STEPS)
    assert len(steps) == 8
    names = {(wf, step) for wf, step, _w, _t in steps}
    assert ("audit_suite", "schema_audit") not in names  # tool=None -> skipped
    assert ("new_project_setup", "new_content_plan") not in names  # tool=None
    assert not any(wf == "content_pipeline" for wf, *_ in steps)  # no tool key


# --- MAIN (the lint itself — GREEN on the real tree, one case per step) ------
@pytest.mark.parametrize("step", _PARAM, ids=_IDS)
def test_workflow_step_tool_declared_and_in_registry(step):
    workflow, name, _writer, _tool = step
    violations = _load().workflow_tool_violations()
    key = f"{workflow}.{name}"
    assert violations.get(key, []) == [], (
        f"{key}: workflow-pinned MCP tool not declared by its owning skill / "
        f"absent from registry: {violations.get(key)}"
    )


# --- TEETH (self-contained non-vacuity proof; runs even in the RED phase) ----
def _registry_names() -> set[str]:
    reg = json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))
    return {t["tool_name"] for srv in reg["servers"].values() for t in srv["tools"]}


def _synthetic_reasons(writer: str, qualified_tool: str) -> list[str]:
    """Independent mirror of the lint's two predicates (3a ``declared_tools`` +
    inline registry) so a planted gap is detectable WITHOUT importing the
    not-yet-built module — proving the lint is not vacuous."""
    server, _, tool = qualified_tool.removeprefix("mcp__").partition("__")
    normalized = f"{server}__{tool}"
    reasons: list[str] = []
    matches = sorted(ROOT.glob(f"skills/**/{writer}/SKILL.md"))
    skill = matches[0] if len(matches) == 1 else None
    if skill is None:
        reasons.append(f"writer '{writer}' resolves to no/multiple skill dir")
    else:
        frontmatter, _body = split_frontmatter_body(skill.read_text(encoding="utf-8"))
        if normalized not in declared_tools(frontmatter):
            reasons.append(f"tool {normalized} not declared by skill")
    if normalized not in _registry_names():
        reasons.append(f"tool {normalized} absent from registry")
    return reasons


def test_teeth_synthetic_gap_trips_both_predicates():
    # Synthetic tool built dynamically from parts — clearly not a real registry
    # tool, never declared by gsc-pull. Both predicates MUST fire.
    synthetic = "mcp__gsc__" + "_".join(["NONEXISTENT", "TOOL", "FIXTURE"])
    reasons = _synthetic_reasons("gsc-pull", synthetic)
    assert any("not declared by skill" in r for r in reasons), reasons
    assert any("absent from registry" in r for r in reasons), reasons
