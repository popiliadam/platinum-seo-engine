"""Path B rung 1 — static lint #2: the skill DEPENDENCY GRAPH is consistent.

``schemas/skill-frontmatter.schema.json`` PROMISES (in its ``consumes``/``produces``
descriptions) that the dependency graph is validated so glossary-audit "can build a
directed dependency graph" and "detects orphans". No such validator existed —
glossary-audit lints GLOSSARY.md *terms* (``produces: []``), not the skill graph. This
module is that missing validator: pure Path-A governance today (catches contract drift)
AND the hard prerequisite for any future planner (which topo-sorts a *validated*
``consumes`` DAG, sound only once the graph is known acyclic).

Two relations, treated differently:
  ``produces`` — DOWNSTREAM SKILL NAMES (schema pattern ``^[a-z][a-z0-9-]*$``). A name
    resolving to no skill dir is a dangling edge = a real defect (per-skill FAIL unit).
  ``consumes`` — upstream refs ``{producer-skill}:{artifact}`` (a prerequisite: "to run
    me, that producer's artifact must exist first"). The prefix is usually a skill but
    sometimes a concept tag (``rules:``, ``templates:``, ``per-project:``); only a ref
    whose prefix resolves to a skill is a graph edge — a non-resolving prefix is
    ADVISORY (possible typo), not a hard fail.

WHY produces-cycles are ADVISORY but consumes-cycles FAIL — they are different relations.
``consumes`` is the prerequisite ordering: a cycle there means the DAG has no valid
topological run order (un-runnable for a planner) → hard fail. ``produces`` merely
*names downstream consumers*; that graph has cycles BY DESIGN (``portfolio-overview`` ⇄
``portfolio-weekly-brief``, ``generate-images`` ⇄ ``new-blog``) and is ~88% asymmetric
vs ``consumes`` — saying nothing about run-order — so ``graph_health`` REPORTS them,
never fails.

Anchored at ``Path(__file__).resolve().parents[2]`` (the working tree), NOT
``CLAUDE_PLUGIN_ROOT`` — an installed copy must never shadow it (0c bare-CLI lesson).
Frontmatter via ``yaml.safe_load`` (PyYAML, requirements.txt ``pyyaml>=6.0``);
malformed/empty → "no declarations" (a real gap, never a crash), per ``skill_mcp_usage``.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from scripts.validation.skill_mcp_usage import split_frontmatter_body

#: Repo root — scripts/validation/skill_graph_consistency.py -> parents[2].
ROOT = Path(__file__).resolve().parents[2]


def _as_list(value) -> list[str]:
    """Coerce a frontmatter field to a list of strings. None/malformed/scalar -> []
    ("no declarations" — a real gap, never a crash)."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _frontmatter(skill_path: str | os.PathLike[str]) -> dict:
    """Parse ONE skill's frontmatter to a dict. Malformed/empty/non-mapping -> {}."""
    text = Path(skill_path).read_text(encoding="utf-8")
    frontmatter, _ = split_frontmatter_body(text)
    if not frontmatter.strip():
        return {}
    try:
        data = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_graph(root: str | os.PathLike[str] = ROOT) -> dict[str, dict]:
    """``{skill_name: {"produces": [...], "consumes": [...], "outputs": [...]}}``.

    A skill's identity is its frontmatter ``name`` (fall back to the directory name).
    """
    graph: dict[str, dict] = {}
    for skill in sorted(Path(root).glob("skills/**/SKILL.md")):
        fm = _frontmatter(skill)
        name = str(fm.get("name") or skill.parent.name)
        graph[name] = {
            "produces": _as_list(fm.get("produces")),
            "consumes": _as_list(fm.get("consumes")),
            "outputs": _as_list(fm.get("outputs")),
        }
    return graph


def _consume_prefix(ref: str) -> str:
    """Producer half of a ``{producer}:{artifact}`` consumes ref (whole ref if no ':')."""
    return ref.split(":", 1)[0]


def dangling_produces_for(
    skill_path: str | os.PathLike[str], root: str | os.PathLike[str] = ROOT
) -> set[str]:
    """``produces`` entries of ONE skill that resolve to NO real skill name.

    The per-skill FAIL unit: a non-empty result is a contract defect (a downstream
    edge pointing at a skill that does not exist).
    """
    names = set(parse_graph(root))
    produces = _as_list(_frontmatter(skill_path).get("produces"))
    return {entry for entry in produces if entry not in names}


def _consumes_adjacency(graph: dict[str, dict]) -> dict[str, set[str]]:
    """``producer -> {consumers}`` for every consumes ref whose prefix resolves to a
    skill. Non-resolving prefixes contribute no edge (advisory — see graph_health)."""
    names = set(graph)
    adjacency: dict[str, set[str]] = {}
    for consumer, data in graph.items():
        for ref in data["consumes"]:
            producer = _consume_prefix(ref)
            if producer in names:
                adjacency.setdefault(producer, set()).add(consumer)
    return adjacency


def consumes_edges(root: str | os.PathLike[str] = ROOT) -> list[tuple[str, str]]:
    """Distinct ``(producer, consumer)`` prerequisite edges, sorted for determinism."""
    adjacency = _consumes_adjacency(parse_graph(root))
    return sorted(
        (producer, consumer)
        for producer, consumers in adjacency.items()
        for consumer in consumers
    )


def _find_cycles(adjacency: dict[str, set[str]], nodes) -> list[list[str]]:
    """All cycles in a directed graph via a DFS three-colour walk. Each cycle is the
    node list from the re-encountered GREY node back to itself."""
    white, grey, black = 0, 1, 2
    colour = {node: white for node in nodes}
    cycles: list[list[str]] = []

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = grey
        stack.append(node)
        for nxt in sorted(adjacency.get(node, ())):
            if colour.get(nxt, white) == grey:
                cycles.append(stack[stack.index(nxt):] + [nxt])
            elif colour.get(nxt, white) == white:
                visit(nxt, stack)
        stack.pop()
        colour[node] = black

    for node in sorted(nodes):
        if colour.get(node, white) == white:
            visit(node, [])
    return cycles


def consumes_cycles(root: str | os.PathLike[str] = ROOT) -> list[list[str]]:
    """Cycles in the ``consumes`` prerequisite graph. ``[]`` on an acyclic graph.

    The graph-level FAIL unit: a cycle means the skill DAG has no valid topological
    run order. ``[]`` today — a GREEN guard that catches a FUTURE cycle.
    """
    graph = parse_graph(root)
    return _find_cycles(_consumes_adjacency(graph), set(graph))


def _produces_cycles(graph: dict[str, dict]) -> list[list[str]]:
    """Cycles in the ``produces`` graph (resolving edges only). ADVISORY: expected
    non-empty by design — ``produces`` is a different relation than ``consumes``."""
    names = set(graph)
    adjacency: dict[str, set[str]] = {}
    for name, data in graph.items():
        for produced in data["produces"]:
            if produced in names:
                adjacency.setdefault(name, set()).add(produced)
    return _find_cycles(adjacency, names)


def _artifact_key(ref: str) -> str:
    """Path-prefix-insensitive artifact key — drops ``projects/{slug}/`` etc. so a
    consumer's templated path matches the producer's bare ``master.xlsx#sheet``."""
    return ref.rsplit("/", 1)[-1]


def graph_health(root: str | os.PathLike[str] = ROOT) -> dict:
    """ADVISORY governance dashboard (the schema's "directed dependency graph").
    NEVER asserted pass/fail. Keys:
      asymmetry_pct                 -- % of edges in only ONE relation (produces vs
                                       consumes); high by design (the relations differ).
      produces_cycles               -- cycles in the produces graph (expected non-empty).
      orphan_consumed_artifacts     -- consumes refs whose artifact is not in that
                                       (resolving) producer's outputs.
      unrecognised_consume_prefixes -- consumes prefixes resolving to no skill (typos or
                                       concept tags like ``rules:``/``templates:``).
    """
    graph = parse_graph(root)
    names = set(graph)

    produces_pairs = {
        (name, produced)
        for name, data in graph.items()
        for produced in data["produces"]
        if produced in names
    }
    consumes_pairs = {
        (producer, consumer)
        for producer, consumers in _consumes_adjacency(graph).items()
        for consumer in consumers
    }
    union = produces_pairs | consumes_pairs
    asymmetric = union - (produces_pairs & consumes_pairs)
    asymmetry_pct = round(100 * len(asymmetric) / len(union), 1) if union else 0.0

    orphans: set[str] = set()
    unrecognised: set[str] = set()
    for data in graph.values():
        for ref in data["consumes"]:
            producer = _consume_prefix(ref)
            if producer not in names:
                unrecognised.add(producer)
            elif ":" in ref:
                artifact = ref.split(":", 1)[1]
                produced_keys = {_artifact_key(o) for o in graph[producer]["outputs"]}
                if _artifact_key(artifact) not in produced_keys:
                    orphans.add(ref)

    return {
        "asymmetry_pct": asymmetry_pct,
        "produces_cycles": _produces_cycles(graph),
        "orphan_consumed_artifacts": sorted(orphans),
        "unrecognised_consume_prefixes": sorted(unrecognised),
    }
