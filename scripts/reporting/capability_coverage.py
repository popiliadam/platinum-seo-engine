#!/usr/bin/env python3
"""capability_coverage.py — the READ-ONLY capability-coverage + effectiveness audit.

The operator's north-star (Path B governance): "are ALL skills / MCP tools / scripts
used EFFECTIVELY, and is there a mechanism that audits that?" Of 45 skills, ~half run
AD-HOC (Claude invokes them from their SKILL.md description triggers) — OUTSIDE the
sequenced + denetçi + oracle orchestration; the 4 workflows orchestrate only 2 of the
4 MCP servers. This module is that mechanism: it partitions every capability and tells
the operator, data-driven, WHICH ad-hoc parts to promote into orchestration next.

It is a sibling of ``portfolio_status`` / ``orchestration_metrics`` (same READ-ONLY
contract, same ``parents[2]`` anchor) and joins the lint family (3a ``skill_mcp_usage``,
lint2 ``workflow_tool_declared``, F-27, pb1 ``skill_graph_consistency``). It REUSES pb1's
``parse_graph`` for the skill roster + dependency graph and 3a's ``declared_tools`` /
``_alias`` / ``_TOOL_RE`` so "declared" + the tool-key alias never drift from the lints.

STATIC coverage (plugin-side — no workspace data, so the plugin stays agnostic):
  * Skills  -> orchestrated (a workflow STEPS writer) / commanded (a command invokes its
    SKILL.md) / ad-hoc-only (neither — reachable ONLY via its description triggers, never
    sequenced or audited). PRECEDENCE orchestrated > commanded > ad-hoc-only.
  * MCP      -> orchestrated (a workflow STEPS ``tool`` that is not None) / declared-only
    (in some skill's ``mcp_tools`` but no workflow step) / unused (in the registry,
    declared by no skill). higgsfield is reported separately as external/optional.
  * Scripts  -> referenced (its module name appears elsewhere in the repo) / orphaned.

RUNTIME coverage (OPTIONAL — workspace-side, only with --workspace-root + --slug):
  events.jsonl carries NO ``skill`` field, so skill-level runtime attribution is LIMITED.
  The reliable live signal is the PROVENANCE sheet -> writer-skill proxy (a written sheet
  that an orchestrated writer owns ⇒ that writer ran). The MCP-tool signal from ``audit``
  events' ``audit_target`` (an ``mcp__server__tool`` token) is near-EMPTY in live data
  (see the module's report note) — built + seed-tested, honestly labeled thin live.

Recommendations: the ad-hoc-only skills ranked by a simple graph-centrality proxy — the
count of ``produces`` + ``consumes`` edges (from pb1's graph) incident to the skill — so
the operator sees which to promote into a workflow / router-intent FIRST.

READ-ONLY: this module reads text + JSON and opens NO file for writing. It adds no hook,
schema, or command and never blocks anything. Anchored at ``parents[2]`` (the working
tree), NOT ``CLAUDE_PLUGIN_ROOT`` — an installed copy must never shadow it (0c lesson).
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Iterable, Sequence

from scripts.orchestration.workflows import (
    audit_suite,
    content_pipeline,
    monthly_maintenance,
    new_project_setup,
)
from scripts.validation.skill_graph_consistency import parse_graph
from scripts.validation.skill_mcp_usage import (
    _MCP_TOOLS_BLOCK_RE,
    _TOOL_RE,
    _alias,
    declared_tools,
    split_frontmatter_body,
)

#: Repo root — scripts/reporting/capability_coverage.py -> parents[2].
ROOT = Path(__file__).resolve().parents[2]

#: The 4 hard-coded Path-A workflows whose STEPS tables ARE the orchestration.
_WORKFLOWS = (monthly_maintenance, audit_suite, new_project_setup, content_pipeline)

#: Precise command->skill invocation signal: a command BODY referencing a skill by its
#: full ``skills/<category>/<dir>/SKILL.md`` path (the ``> **Skill:**`` / ``Skill chain``
#: blockquotes + step bodies). A "do not use when" prose mention uses backtick short-names
#: / ``/command`` forms, NOT this path form — so this regex never false-counts a mention.
_SKILL_PATH_RE = re.compile(r"skills/[a-z0-9-]+/([a-z0-9-]+)/SKILL\.md")

#: Text extensions scanned when deciding whether a script module is "referenced". A broad
#: set on purpose — a false "orphan" is worse than a false "referenced" (be conservative).
_CORPUS_EXTS = frozenset(
    {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".toml", ".cfg", ".sh", ".ini"}
)
#: Directories never walked (caches / VCS / installed copies / worktrees).
_SKIP_DIRS = frozenset(
    {"__pycache__", ".git", "node_modules", ".claude", "worktrees", ".pytest_cache",
     ".venv", "venv", ".mypy_cache", ".ruff_cache"}
)


# ===========================================================================
# Workflow-derived facts (read the imported STEPS tables — NOT root-dependent)
# ===========================================================================

def _iter_steps() -> Iterable[dict]:
    """Yield every STEPS entry across the 4 workflows (in workflow + table order)."""
    for workflow in _WORKFLOWS:
        for step in workflow.STEPS:
            yield step


def _step_skill_name(step: dict) -> str:
    """The skill a STEPS entry maps to: its ``writer`` (the 3 data drivers) or, for
    content_pipeline (no ``writer`` key), its ``name`` normalized (``new_blog`` ->
    ``new-blog``)."""
    writer = step.get("writer")
    return writer if writer else step["name"].replace("_", "-")


def orchestrated_skill_names() -> set[str]:
    """Skill names that appear as a workflow STEPS writer (orchestration membership)."""
    return {_step_skill_name(step) for step in _iter_steps()}


def orchestrated_tool_keys() -> set[str]:
    """Registry-key set of MCP tools a workflow STEP orchestrates.

    A STEP's ``tool`` is ``mcp__server__tool`` OR None (schema_audit / new_content_plan
    pin None; content_pipeline carries no ``tool`` key). None / missing contributes
    nothing. The key is normalized with 3a's ``_TOOL_RE`` + ``_alias`` so it matches the
    registry + the declared set exactly.
    """
    keys: set[str] = set()
    for step in _iter_steps():
        tool = step.get("tool")
        if not tool:
            continue
        match = _TOOL_RE.search(tool)
        if match:
            keys.add(f"{_alias(match.group(1))}__{match.group(2)}")
    return keys


def sheet_writer_map() -> dict[str, str]:
    """``{sheet: writer-skill}`` for every orchestrated sheet (first writer wins).

    The runtime sheet -> writer-skill proxy source: a STEP commits ``sheet`` via its
    ``writer`` skill, so a provenance row for that sheet is evidence the writer ran.
    content_pipeline steps have no ``sheet`` and contribute nothing.
    """
    mapping: dict[str, str] = {}
    for step in _iter_steps():
        sheet, writer = step.get("sheet"), step.get("writer")
        if sheet and writer:
            mapping.setdefault(sheet, writer)
    return mapping


# ===========================================================================
# STATIC — skills
# ===========================================================================

def commanded_skill_names(root: str | os.PathLike[str] = ROOT) -> set[str]:
    """Skill dir-names invoked by a command via a ``skills/.../SKILL.md`` body path.

    Precise: only the full SKILL.md path counts (an invocation), never a backtick
    short-name prose mention. Every engine skill has frontmatter ``name`` == its dir
    name (verified), so the captured dir-name IS the skill name.
    """
    names: set[str] = set()
    commands_dir = Path(root) / "commands"
    if not commands_dir.is_dir():
        return names
    for command in sorted(commands_dir.glob("*.md")):
        text = command.read_text(encoding="utf-8")
        names.update(_SKILL_PATH_RE.findall(text))
    return names


def classify_skills(
    root: str | os.PathLike[str] = ROOT, *, orchestrated: Iterable[str] | None = None
) -> dict:
    """Partition every skill into exactly one of orchestrated / commanded / ad-hoc-only.

    Roster + identity come from pb1 ``parse_graph`` (keyed by frontmatter ``name``).
    PRECEDENCE: orchestrated > commanded > ad-hoc-only. ``orchestrated`` is injectable
    (tests / what-if) and defaults to the real workflow writers; it is intersected with
    the roster so a non-existent name never creates a phantom bucket entry. ad-hoc-only
    is NOT "dead" — every skill is reachable via its description triggers; it means
    "only reachable ad-hoc, never sequenced/denetçi-audited".
    """
    roster = set(parse_graph(root))
    orch = (set(orchestrated) if orchestrated is not None
            else orchestrated_skill_names()) & roster
    commanded = commanded_skill_names(root) & roster

    buckets: dict[str, list[str]] = {"orchestrated": [], "commanded": [], "ad_hoc_only": []}
    for name in sorted(roster):
        if name in orch:
            buckets["orchestrated"].append(name)
        elif name in commanded:
            buckets["commanded"].append(name)
        else:
            buckets["ad_hoc_only"].append(name)
    counts = {key: len(value) for key, value in buckets.items()}
    return {**buckets, "counts": counts, "total": len(roster)}


# ===========================================================================
# STATIC — MCP tools
# ===========================================================================

def _registry(root: str | os.PathLike[str] = ROOT) -> dict:
    """Parse mcp-tool-registry.json (object form). Missing/corrupt -> {} (never raise)."""
    try:
        data = json.loads(
            (Path(root) / "mcp-tool-registry.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def registry_tool_keys(root: str | os.PathLike[str] = ROOT) -> set[str]:
    """The ``tool_name`` set of the 4 registry SERVERS (gsc/dataforseo/scrapling/sf).

    higgsfield lives under ``external_user_dependencies`` (NOT a server) and is excluded
    here — it is surfaced separately as external/optional.
    """
    keys: set[str] = set()
    for server in (_registry(root).get("servers") or {}).values():
        for tool in server.get("tools") or []:
            name = tool.get("tool_name")
            if name:
                keys.add(name)
    return keys


def external_tool_keys(root: str | os.PathLike[str] = ROOT) -> list[str]:
    """``{server}__{tool}`` keys for external/optional user MCPs (higgsfield)."""
    keys: list[str] = []
    external = _registry(root).get("external_user_dependencies") or {}
    for server, info in external.items():
        for tool in info.get("tools") or []:
            keys.append(f"{server}__{tool}")
    return sorted(keys)


def declared_tool_keys(root: str | os.PathLike[str] = ROOT) -> set[str]:
    """Union of every skill's DECLARED ``mcp_tools`` (registry-keys).

    Starts from 3a ``declared_tools`` (same block regex + ``ScraplingServer -> scrapling``
    alias as the lint family), then SUPPLEMENTS it with a block-scoped token scan that also
    catches the YAML INLINE-FLOW form ``optional: ["mcp__gsc__list_sites"]`` — which 3a's
    line-anchored required/optional parser misses (e.g. init-project). Without this an
    actively declared+invoked tool (``gsc__list_sites``) is mislabeled "unused/dead". The
    scan is scoped to the ``mcp_tools`` BLOCK (not the whole frontmatter), so a prose tool
    mention elsewhere in the frontmatter never inflates "declared".

    [manager fix, 2026-06-09 — root cause is a latent blind spot in 3a ``declared_tools``;
    follow-up: teach 3a to parse inline-flow at the source, then drop this supplement.]
    """
    declared: set[str] = set()
    for skill in sorted(Path(root).glob("skills/**/SKILL.md")):
        frontmatter, _ = split_frontmatter_body(skill.read_text(encoding="utf-8"))
        declared |= declared_tools(frontmatter)
        block = _MCP_TOOLS_BLOCK_RE.search(frontmatter + "\n---\n")
        if block:
            for match in _TOOL_RE.finditer(block.group(1)):
                declared.add(f"{_alias(match.group(1))}__{match.group(2)}")
    return declared


def classify_mcp(root: str | os.PathLike[str] = ROOT) -> dict:
    """Partition every REGISTRY tool into orchestrated / declared-only / unused.

    PRECEDENCE orchestrated > declared-only > unused (an orchestrated tool that is also
    declared lands in orchestrated). higgsfield is reported in ``external_optional`` and
    is never in the 3 server buckets.
    """
    registry = registry_tool_keys(root)
    orch = orchestrated_tool_keys()
    declared = declared_tool_keys(root)

    orchestrated = sorted(t for t in registry if t in orch)
    declared_only = sorted(t for t in registry if t not in orch and t in declared)
    unused = sorted(t for t in registry if t not in orch and t not in declared)
    counts = {
        "orchestrated": len(orchestrated),
        "declared_only": len(declared_only),
        "unused": len(unused),
    }
    return {
        "orchestrated": orchestrated,
        "declared_only": declared_only,
        "unused": unused,
        "external_optional": external_tool_keys(root),
        "counts": counts,
        "total": len(registry),
    }


# ===========================================================================
# STATIC — scripts
# ===========================================================================

def _script_modules(root: Path) -> list[tuple[str, str]]:
    """``[(posix_relpath, module_stem)]`` for ``scripts/**/*.py`` (excl. __pycache__ +
    ``__init__.py`` — package markers are referenced implicitly, never "orphaned")."""
    modules: list[tuple[str, str]] = []
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        return modules
    for path in sorted(scripts_dir.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts) or path.name == "__init__.py":
            continue
        modules.append((path.relative_to(root).as_posix(), path.stem))
    return modules


def _reference_corpus(root: Path) -> list[tuple[str, str]]:
    """``[(posix_relpath, text)]`` for every scanned text file under ``root``.

    The haystack for "is this module name referenced anywhere?" — skips cache/VCS dirs
    and reads only ``_CORPUS_EXTS``. Unreadable files are skipped (never fatal).
    """
    corpus: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in _CORPUS_EXTS:
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            corpus.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return corpus


def classify_scripts(root: str | os.PathLike[str] = ROOT) -> dict:
    """Partition every script module into referenced / orphaned.

    ``referenced`` = the module stem appears as a whole word in ANY OTHER repo file
    (an import ``from scripts.x.stem``, an invocation ``python3 -m scripts.x.stem``, a
    skill/command/CI mention). Conservative on purpose: a false "orphan" is worse than a
    false "referenced". An ``orphaned`` record carries ``low_confidence`` = True when the
    module is a runnable CLI (defines ``__main__`` — likely invoked via shell, not
    grep-visible) or its stem is short/generic (≤ 6 chars) — flagging where a "dead"
    claim is least safe.
    """
    root_path = Path(root)
    modules = _script_modules(root_path)
    corpus = _reference_corpus(root_path)

    referenced: list[str] = []
    orphaned: list[dict] = []
    for relpath, stem in modules:
        pattern = re.compile(r"\b" + re.escape(stem) + r"\b")
        is_referenced = any(
            other_path != relpath and pattern.search(text)
            for other_path, text in corpus
        )
        if is_referenced:
            referenced.append(relpath)
            continue
        own_text = next((t for p, t in corpus if p == relpath), "")
        runnable = '__name__ == "__main__"' in own_text or "__name__ == '__main__'" in own_text
        orphaned.append(
            {"path": relpath, "low_confidence": bool(runnable or len(stem) <= 6)}
        )
    counts = {"referenced": len(referenced), "orphaned": len(orphaned)}
    return {
        "referenced": referenced,
        "orphaned": orphaned,
        "counts": counts,
        "total": len(modules),
    }


# ===========================================================================
# Recommendations — ad-hoc skills ranked by graph centrality (pb1 graph)
# ===========================================================================

def skill_centrality(graph: dict[str, dict]) -> dict[str, int]:
    """``{skill: incident-edge count}`` over the resolving ``produces`` + ``consumes``
    edges (the value proxy). Each resolving edge increments BOTH endpoints' degree, so a
    skill that many others produce/consume — or that itself produces/consumes many —
    ranks high. Mirrors pb1's edge construction (a consumes prefix is the producer)."""
    names = set(graph)
    degree = {name: 0 for name in names}
    for name, data in graph.items():
        for produced in data.get("produces", []):
            if produced in names:
                degree[name] += 1
                degree[produced] += 1
        for ref in data.get("consumes", []):
            producer = ref.split(":", 1)[0]
            if producer in names and producer != name:
                degree[name] += 1
                degree[producer] += 1
    return degree


def recommendations(
    root: str | os.PathLike[str] = ROOT, *, skills: dict | None = None
) -> list[dict]:
    """Ad-hoc-only skills ranked promote-first by centrality (desc), then name (asc).

    Each item: ``{skill, centrality, produces, consumes}``. The ranking answers "which
    ad-hoc skill is most worth pulling into a workflow / router-intent next?".
    """
    graph = parse_graph(root)
    classified = skills if skills is not None else classify_skills(root)
    degree = skill_centrality(graph)
    ranked = sorted(
        classified["ad_hoc_only"],
        key=lambda name: (-degree.get(name, 0), name),
    )
    return [
        {
            "skill": name,
            "centrality": degree.get(name, 0),
            "produces": len(graph.get(name, {}).get("produces", [])),
            "consumes": len(graph.get(name, {}).get("consumes", [])),
        }
        for name in ranked
    ]


# ===========================================================================
# RUNTIME — events.jsonl + coverage signals (OPTIONAL, workspace-side)
# ===========================================================================

def read_events(events_path: str | os.PathLike[str]) -> list[dict]:
    """Parse an append-only events.jsonl into a list of dicts.

    A malformed line is SKIPPED (robust — one bad row never blanks the signal); a missing
    file -> ``[]``. Never raises.
    """
    path = Path(events_path)
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            events.append(record)
    return events


def _tool_key_from_token(token: str) -> str | None:
    """Registry-key for an ``mcp__server__tool`` token, or None (external/no-match)."""
    match = _TOOL_RE.search(token)
    if not match:
        return None
    server, tool = match.group(1), match.group(2)
    aliased = _alias(server)
    # external servers (higgsfield) live outside the registry — never a runtime tool key.
    if aliased == "higgsfield" or server == "higgsfield":
        return None
    return f"{aliased}__{tool}"


def observed_mcp_tools(
    events: Sequence[dict], *, coverage_records: Sequence[dict] = ()
) -> set[str]:
    """Registry-keys observed at RUNTIME — from ``audit`` events' ``audit_target`` token
    + any coverage step ``observed_mcp``.

    LIVE REALITY: ``audit_target`` carries an ``mcp__server__tool`` token only rarely (it
    is mostly ``Bash`` / ``Edit`` / file paths), so this signal is near-empty against live
    data — see ``runtime_coverage``'s note. The mechanism is correct + seed-tested; the
    thinness is honestly reported, never fabricated.
    """
    observed: set[str] = set()
    for event in events:
        target = event.get("audit_target")
        if isinstance(target, str):
            key = _tool_key_from_token(target)
            if key:
                observed.add(key)
    for record in coverage_records:
        for step in record.get("steps") or []:
            for token in step.get("observed_mcp") or []:
                key = _tool_key_from_token(token) if "mcp__" in str(token) else str(token)
                if key and not str(key).startswith("higgsfield__"):
                    observed.add(key)
    return observed


def observed_sheets(events: Sequence[dict]) -> set[str]:
    """Excel sheets written at RUNTIME — from ``provenance`` events' ``target_excel_sheet``.

    The RELIABLE live signal (87 provenance rows in a mature project). ``None`` sheets are
    dropped.
    """
    sheets: set[str] = set()
    for event in events:
        sheet = event.get("target_excel_sheet")
        if isinstance(sheet, str) and sheet:
            sheets.add(sheet)
    return sheets


def _coverage_records(workspace_root: Path, slug: str) -> list[dict]:
    """All coverage records for ``slug`` (``projects/<slug>/_state/coverage/*.json``)."""
    cov_dir = workspace_root / "projects" / slug / "_state" / "coverage"
    if not cov_dir.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(cov_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            records.append(data)
    return records


_RUNTIME_NOTE = (
    "skill-level runtime: LIMITED — events.jsonl has no skill field, so attribution is "
    "the provenance sheet→writer proxy (a written sheet an orchestrated writer owns ⇒ "
    "that writer ran); sheets no orchestrated writer owns are listed unattributed. "
    "MCP-tool runtime (audit_target mcp__ token) is near-empty in live data — thin live "
    "is expected, not fabricated."
)


def runtime_coverage(workspace_root: str | os.PathLike[str], slug: str) -> dict:
    """Workspace-side runtime coverage for one project (READ-ONLY; never raises).

    Reads ``projects/<slug>/_state/events.jsonl`` + the coverage records and returns the
    observed MCP tools, the writer-skills inferred via the sheet proxy, the raw observed
    sheets, and the sheets no orchestrated writer owns (honest "limited" bucket).
    """
    ws = Path(workspace_root)
    events = read_events(ws / "projects" / slug / "_state" / "events.jsonl")
    records = _coverage_records(ws, slug)
    sheets = observed_sheets(events)
    writers = sheet_writer_map()
    observed_writers = sorted({writers[s] for s in sheets if s in writers})
    unattributed = sorted(s for s in sheets if s not in writers)
    return {
        "slug": slug,
        "observed_mcp_tools": sorted(observed_mcp_tools(events, coverage_records=records)),
        "observed_writer_skills": observed_writers,
        "observed_sheets": sorted(sheets),
        "unattributed_sheets": unattributed,
        "note": _RUNTIME_NOTE,
    }


# ===========================================================================
# Report assembly + render
# ===========================================================================

def coverage_report(
    root: str | os.PathLike[str] = ROOT, *,
    workspace_root: str | os.PathLike[str] | None = None, slug: str | None = None,
) -> dict:
    """The full READ-ONLY coverage report (STATIC always; RUNTIME only with ws + slug)."""
    skills = classify_skills(root)
    runtime = (
        runtime_coverage(workspace_root, slug)
        if workspace_root is not None and slug
        else None
    )
    return {
        "skills": skills,
        "mcp": classify_mcp(root),
        "scripts": classify_scripts(root),
        "recommendations": recommendations(root, skills=skills),
        "runtime": runtime,
    }


def _join(items: Sequence[str], limit: int | None = None) -> str:
    """Comma-join (sorted display already); ``limit`` truncates with a "+N" remainder."""
    items = list(items)
    if limit is not None and len(items) > limit:
        return ", ".join(items[:limit]) + f", … (+{len(items) - limit})"
    return ", ".join(items) if items else "—"


def render_report(report: dict) -> str:
    """Render the report as ONE deterministic Turkish operator block.

    Headline counts + per-category tables + the promote-first recommendations + (when
    present) the runtime layer. Stable ordering + no clock, so calling twice yields an
    identical string (mirrors ``portfolio_status.render_triage``).
    """
    skills = report["skills"]
    mcp = report["mcp"]
    scripts = report["scripts"]
    sc = skills["counts"]
    mc = mcp["counts"]

    lines = [
        "📊 Kapasite Kapsam Denetimi (READ-ONLY)",
        "",
        f"Skill'ler ({skills['total']}): "
        f"orchestrated (orkestre) {sc['orchestrated']} · "
        f"commanded (komut) {sc['commanded']} · "
        f"ad-hoc-only {sc['ad_hoc_only']}",
        f"  orkestre: {_join(skills['orchestrated'])}",
        f"  komut:    {_join(skills['commanded'])}",
        f"  ad-hoc:   {_join(skills['ad_hoc_only'])}",
        "",
        f"MCP araçları ({mcp['total']} kayıtlı; 4 sunucu): "
        f"orchestrated {mc['orchestrated']} · "
        f"declared-only {mc['declared_only']} · "
        f"unused {mc['unused']}",
        f"  orkestre:      {_join(mcp['orchestrated'])}",
        f"  KULLANILMAYAN: {_join(mcp['unused'])}",
        f"  dış/opsiyonel: {_join(mcp['external_optional'])}",
        "",
        f"Script'ler ({scripts['total']}): "
        f"referenced {scripts['counts']['referenced']} · "
        f"orphaned {scripts['counts']['orphaned']}",
        f"  ÖKSÜZ (orphaned): "
        f"{_join([o['path'] for o in scripts['orphaned']])}",
        "",
        "Öneri — önce şu ad-hoc skill'leri orkestrasyona/route'a taşı "
        "(merkeziyet=produces+consumes kenar sayısı):",
        "| sıra | skill | merkeziyet | produces | consumes |",
        "|---|---|---|---|---|",
    ]
    for rank, rec in enumerate(report["recommendations"][:10], start=1):
        lines.append(
            f"| {rank} | {rec['skill']} | {rec['centrality']} | "
            f"{rec['produces']} | {rec['consumes']} |"
        )

    runtime = report.get("runtime")
    if runtime is not None:
        lines += [
            "",
            f"Runtime (proje: {runtime['slug']}):",
            f"  gözlenen MCP araçları: {_join(runtime['observed_mcp_tools'])}",
            f"  gözlenen writer-skill (sheet proxy): {_join(runtime['observed_writer_skills'])}",
            f"  atfedilemeyen sheet'ler: {_join(runtime['unattributed_sheets'])}",
            f"  not: {runtime['note']}",
        ]
    return "\n".join(lines)


# ===========================================================================
# CLI (READ-ONLY report; exit 0 always — it never fails a build)
# ===========================================================================

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m scripts.reporting.capability_coverage",
        description="READ-ONLY capability-coverage audit: which skills / MCP tools / "
                    "scripts are orchestrated vs ad-hoc vs unused, and which ad-hoc "
                    "skills to promote first.",
    )
    parser.add_argument(
        "--workspace-root", default=None,
        help="optional workspace root; with --slug, adds the (limited) runtime layer",
    )
    parser.add_argument(
        "--slug", default=None,
        help="optional project slug for runtime enrichment (needs --workspace-root)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI boundary: build + print the report. Exit 0 always."""
    args = _build_arg_parser().parse_args(argv)
    report = coverage_report(
        ROOT, workspace_root=args.workspace_root, slug=args.slug
    )
    print(render_report(report))
    return 0


__all__: Iterable[str] = (
    "orchestrated_skill_names", "commanded_skill_names", "classify_skills",
    "orchestrated_tool_keys", "declared_tool_keys", "registry_tool_keys",
    "external_tool_keys", "classify_mcp", "classify_scripts",
    "skill_centrality", "recommendations",
    "read_events", "observed_mcp_tools", "observed_sheets", "sheet_writer_map",
    "runtime_coverage", "coverage_report", "render_report", "main",
)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
