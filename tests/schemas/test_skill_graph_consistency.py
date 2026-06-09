"""Path B rung 1 — static lint #2: the skill DEPENDENCY GRAPH is consistent.

``schemas/skill-frontmatter.schema.json`` PROMISES (in its ``consumes``/``produces``
field descriptions) that the skill dependency graph is validated so glossary-audit
"can build a directed dependency graph" and "detects orphans". No such validator
existed — glossary-audit lints GLOSSARY.md *terms*, not the skill graph. This module
is that missing validator.

Two FAIL units + two advisory checks (mirrors ``test_skill_body_mcp_subset_declared``):

  • per-skill : ``dangling_produces_for(skill) == set()`` — every ``produces`` entry
                resolves to a real skill name. One parametrized test per skill so a
                regression names the offending skill directly.
  • graph     : ``consumes_cycles(ROOT) == []`` — the ``consumes`` prerequisite graph
                is acyclic (a GREEN guard that catches a FUTURE cycle).
  • TEETH     : a synthetic skill tree with (a) a dangling ``produces`` edge and (b) a
                ``consumes`` cycle is detected — proof the lint is not a vacuous no-op.
  • health    : ``graph_health(ROOT)`` runs and reports ``produces``-cycles (which
                exist BY DESIGN — ``produces`` is a different relation than ``consumes``
                — and are therefore advisory, never asserted as pass/fail).
"""
from __future__ import annotations

import pathlib

import pytest

from scripts.validation.skill_graph_consistency import (
    consumes_cycles,
    dangling_produces_for,
    graph_health,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
_SKILLS = sorted(ROOT.glob("skills/**/SKILL.md"))


@pytest.mark.parametrize(
    "skill",
    _SKILLS,
    ids=[str(p.relative_to(ROOT)) for p in _SKILLS],
)
def test_skill_produces_edges_resolve(skill: pathlib.Path):
    """Every ``produces`` entry is a DOWNSTREAM SKILL NAME that resolves to a real
    skill dir; a non-resolving entry is a contract defect (repoint or remove)."""
    dangling = dangling_produces_for(skill)
    assert dangling == set(), (
        f"{skill.relative_to(ROOT)} declares produces: edge(s) resolving to NO "
        f"skill: {sorted(dangling)}.\n"
        "Remediation: produces entries are downstream SKILL NAMES (schema pattern "
        "'^[a-z][a-z0-9-]*$'); repoint to a real skill or remove the stale edge. "
        "(lint #2: produces ⊆ skills.)"
    )


def test_consumes_prerequisite_graph_is_acyclic():
    """The ``consumes`` prerequisite graph (producer→consumer over refs whose prefix
    resolves to a skill) MUST be acyclic, else it is un-topo-sortable for a planner."""
    cycles = consumes_cycles(ROOT)
    assert cycles == [], (
        f"consumes prerequisite graph has cycle(s): {cycles}.\n"
        "A producer→consumer dependency cycle has no valid topological run order. "
        "(produces-cycles are advisory — see graph_health — but consumes-cycles fail.)"
    )


def _write_skill(dir_path, name, *, produces=(), consumes=(), outputs=("events.jsonl",)):
    """Emit a minimal synthetic SKILL.md (clean YAML, no dedent pitfalls)."""
    dir_path.mkdir(parents=True, exist_ok=True)

    def _block(key, items):
        if not items:
            return f"{key}: []"
        return key + ":\n" + "\n".join(f'  - "{it}"' for it in items)

    frontmatter = "\n".join(
        [
            "---",
            f"name: {name}",
            _block("outputs", outputs),
            _block("consumes", consumes),
            _block("produces", produces),
            "---",
            f"body of {name}",
            "",
        ]
    )
    (dir_path / "SKILL.md").write_text(frontmatter, encoding="utf-8")


def test_teeth_lint_detects_synthetic_dangling_and_cycle(tmp_path):
    """TEETH: without this, a no-op lint would pass vacuously. Build a tiny fake skill
    tree containing both defect classes and assert each is caught."""
    # alpha produces a skill that does not exist -> dangling produces edge.
    _write_skill(tmp_path / "skills/x/alpha", "alpha", produces=["ghost-skill"])
    # beta <-> gamma form a consumes prerequisite cycle.
    _write_skill(tmp_path / "skills/x/beta", "beta", consumes=["gamma:events.jsonl"])
    _write_skill(tmp_path / "skills/x/gamma", "gamma", consumes=["beta:events.jsonl"])

    dangling = dangling_produces_for(
        tmp_path / "skills/x/alpha/SKILL.md", root=tmp_path
    )
    assert dangling == {"ghost-skill"}, f"dangling produces not detected: {dangling}"

    cycles = consumes_cycles(tmp_path)
    assert cycles, "consumes cycle (beta<->gamma) not detected"
    in_cycles = {node for cycle in cycles for node in cycle}
    assert {"beta", "gamma"} <= in_cycles, f"cycle should involve beta & gamma: {cycles}"


def test_graph_health_runs_and_reports_produces_cycles():
    """Health smoke test: the advisory dashboard runs and returns the expected keys.
    Asserts produces-cycles are REPORTED (non-empty today), NOT specific values, so the
    test does not become brittle as the graph evolves."""
    health = graph_health(ROOT)
    assert set(health) == {
        "asymmetry_pct",
        "produces_cycles",
        "orphan_consumed_artifacts",
        "unrecognised_consume_prefixes",
    }, f"unexpected graph_health keys: {sorted(health)}"
    # produces graph HAS cycles by design (e.g. portfolio-overview <-> weekly-brief);
    # reported, never failed.
    assert health["produces_cycles"], "expected produces-graph cycles to be reported"
