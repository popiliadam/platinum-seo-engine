"""AMO batch 3-gov-lint2 — static lint #2: every workflow STEP's required MCP
``tool`` ⊆ the DECLARED ``mcp_tools`` of the skill that runs that step ⊆ the MCP
registry. Stacks ABOVE batch 3a's ``body ⊆ declared ⊆ registry`` (skills): the
orchestrator (Faz 1/3) pins, per workflow step, the MCP ``tool`` that step calls
(e.g. monthly's ``gsc_pull`` requires ``mcp__gsc__search_analytics``). This lint
proves that pinned tool is actually DECLARED by the skill that runs the step AND
exists in the registry — so a workflow and a skill cannot drift out of sync
silently:

    workflow STEPS[].tool  ⊆  owning-skill declared mcp_tools  ⊆  registry

Pure / no side effects: functions read only files and import workflow modules to
read their module-level ``STEPS`` tuple (a plain literal — importing needs no
workspace/env, fact G). The declared-side check REUSES batch 3a's
``split_frontmatter_body`` + ``declared_tools`` so both lints share one
``server__tool`` key space; ``normalize_tool`` bridges the workflow's QUALIFIED
``mcp__server__tool`` into that key space (strip the 5-char ``mcp__`` prefix,
apply the same ScraplingServer->scrapling alias).

Paths are anchored file-relative (``parents[2]``), NOT ``CLAUDE_PLUGIN_ROOT`` — an
installed-plugin copy must never shadow the working tree (the 0c bare-CLI lesson).
"""
from __future__ import annotations

import importlib
import json
from collections.abc import Iterator
from pathlib import Path

from scripts.validation.skill_mcp_usage import declared_tools, split_frontmatter_body

#: Repo root — scripts/validation/workflow_tool_declared.py -> parents[2].
ROOT = Path(__file__).resolve().parents[2]

#: .mcp.json server key -> registry server key (mirrors skill_mcp_usage._ALIAS).
_SERVER_ALIAS = {"ScraplingServer": "scrapling"}

#: Dotted package the workflow modules import under (fact G — repo root on sys.path).
_WORKFLOWS_PKG = "scripts.orchestration.workflows"


def normalize_tool(qualified: str) -> str:
    """Qualified ``mcp__server__tool`` -> 3a key-space ``server__tool``.

    Strips the 5-char ``mcp__`` prefix with ``removeprefix`` (a naive ``[4:]``
    leaves a leading ``_`` and false-FAILs everything), splits server/tool on the
    FIRST ``__``, and applies the same ScraplingServer->scrapling alias
    ``skill_mcp_usage`` uses so the key matches ``declared_tools`` exactly.
    """
    server, _, tool = qualified.removeprefix("mcp__").partition("__")
    return f"{_SERVER_ALIAS.get(server, server)}__{tool}"


def registry_tool_names(root: Path | str = ROOT) -> set[str]:
    """The ``server__tool`` key set of every tool in ``mcp-tool-registry.json``.

    Canonical extraction (mirrors
    test_skill_mcp_tools_exist_in_registry._registry_tool_names): set membership,
    never substring.
    """
    reg = json.loads(
        (Path(root) / "mcp-tool-registry.json").read_text(encoding="utf-8")
    )
    return {t["tool_name"] for srv in reg["servers"].values() for t in srv["tools"]}


def resolve_skill(writer: str, root: Path | str = ROOT) -> Path | None:
    """The single ``skills/**/{writer}/SKILL.md`` a step's ``writer`` maps to.

    Returns ``None`` when the glob resolves to ZERO or MORE THAN ONE skill dir —
    an ambiguous/missing writer is itself a lint failure (surfaced by the caller,
    never raised here).
    """
    matches = sorted(Path(root).glob(f"skills/**/{writer}/SKILL.md"))
    return matches[0] if len(matches) == 1 else None


def iter_workflow_tool_steps(
    root: Path | str = ROOT,
) -> Iterator[tuple[str, str, str, str]]:
    """Yield ``(workflow_module, step_name, writer, normalized_tool)`` for every
    tool-bearing step across ``scripts/orchestration/workflows/*.py``.

    Glob-discovers the workflow modules (so a future workflow is auto-covered — no
    hardcoded module list), imports each, reads its module-level ``STEPS`` tuple,
    and yields one row per step whose ``tool`` is a non-None qualified string. A
    module without ``STEPS``, or a step with no / ``None`` ``tool`` (schema_audit,
    new_content_plan, the content_pipeline steps), is simply skipped.
    """
    workflows = Path(root) / "scripts" / "orchestration" / "workflows"
    for path in sorted(workflows.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = importlib.import_module(f"{_WORKFLOWS_PKG}.{path.stem}")
        for step in getattr(module, "STEPS", ()):
            tool = step.get("tool")
            if tool is not None:
                yield path.stem, step["name"], step["writer"], normalize_tool(tool)


def _step_reasons(
    writer: str, tool: str, registry: set[str], root: Path
) -> list[str]:
    """The (possibly empty) reason list for ONE normalized ``(writer, tool)``."""
    reasons: list[str] = []
    skill = resolve_skill(writer, root)
    if skill is None:
        reasons.append(f"writer '{writer}' resolves to no/multiple skill dir")
    else:
        frontmatter, _ = split_frontmatter_body(skill.read_text(encoding="utf-8"))
        if tool not in declared_tools(frontmatter):
            reasons.append(f"tool {tool} not declared by skill {skill.relative_to(root)}")
    if tool not in registry:
        reasons.append(f"tool {tool} absent from registry")
    return reasons


def workflow_tool_violations(root: Path | str = ROOT) -> dict[str, list[str]]:
    """``{f"{workflow}.{step}": [reasons]}`` for every tool-bearing step whose
    pinned tool is NOT declared by its owning skill or NOT in the registry.

    A step with an empty reason list is GREEN and omitted. Reasons:
      * ``writer '<w>' resolves to no/multiple skill dir`` (resolve_skill is None)
      * ``tool <T> not declared by skill <relpath>``       (T ∉ declared_tools)
      * ``tool <T> absent from registry``                  (T ∉ registry_tool_names)
    """
    root_path = Path(root)
    registry = registry_tool_names(root_path)
    violations: dict[str, list[str]] = {}
    for workflow, step, writer, tool in iter_workflow_tool_steps(root_path):
        reasons = _step_reasons(writer, tool, registry, root_path)
        if reasons:
            violations[f"{workflow}.{step}"] = reasons
    return violations
