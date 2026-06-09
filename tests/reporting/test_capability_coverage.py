"""tests/reporting/test_capability_coverage.py — Path B capability-coverage audit.

TDD lock for scripts/reporting/capability_coverage.py: the READ-ONLY capability
coverage + effectiveness auditor. It answers the operator's north-star — "are ALL
skills / MCP tools / scripts used effectively, and is there a mechanism that audits
that?" — by partitioning every skill (orchestrated / commanded / ad-hoc-only),
every registry MCP tool (orchestrated / declared-only / unused), and every script
(referenced / orphaned), then ranking the ad-hoc skills to promote first. It WRITES
NOTHING — it only READS the workflow STEPS tables, the skill frontmatter (via pb1
``parse_graph``), the ``mcp_tools`` declarations (via 3a ``declared_tools``), the
MCP registry, the command bodies, and (optionally) a project's events.jsonl.

A sibling of ``portfolio_status`` / ``orchestration_metrics`` — same read-only
contract, same ``parents[2]`` anchor, joins the lint family (3a, lint2, F-27, pb1).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.reporting import capability_coverage as cc

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# tmp-tree fixture helpers (TEETH — a planted skill/command/script tree)
# ---------------------------------------------------------------------------

def _write_skill(root: Path, category: str, name: str, *, produces=None,
                 consumes=None, outputs=None) -> None:
    """Plant a minimal valid SKILL.md so ``parse_graph(root)`` rosters it."""
    sk = root / "skills" / category / name / "SKILL.md"
    sk.parent.mkdir(parents=True, exist_ok=True)
    fm = {
        "produces": produces or [],
        "consumes": consumes or [],
        "outputs": outputs or [],
    }
    body = ["---", f"name: {name}",
            "description: planted test skill"]
    for key, vals in fm.items():
        body.append(f"{key}:")
        for v in vals:
            body.append(f"  - \"{v}\"")
    body += ["---", "", f"# {name}", "planted body"]
    sk.write_text("\n".join(body) + "\n", encoding="utf-8")


def _write_command(root: Path, name: str, *, invokes_skill_path: str | None = None,
                   prose_mentions: tuple[str, ...] = ()) -> None:
    """Plant a command. ``invokes_skill_path`` is a real invocation (SKILL.md path);
    ``prose_mentions`` are backtick short-names that MUST NOT count as invocations."""
    cmd = root / "commands" / f"{name}.md"
    cmd.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", "description: planted command", "---", "", f"# /{name}"]
    if invokes_skill_path:
        lines.append(f"> **Skill:** `{invokes_skill_path}` runs the protocol.")
    for mention in prose_mentions:
        lines.append(f"Do not use when: `{mention}` is needed (separate skill).")
    cmd.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_events(ws: Path, slug: str, records: list[dict]) -> Path:
    """Seed an append-only events.jsonl at the REAL path for ``slug``."""
    path = ws / "projects" / slug / "_state" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
    )
    return path


# ===========================================================================
# A. STATIC — skills partition (orchestrated / commanded / ad-hoc-only)
# ===========================================================================

def test_classify_skills_partitions_all_45_real_skills():
    out = cc.classify_skills(_REPO_ROOT)
    buckets = (out["orchestrated"], out["commanded"], out["ad_hoc_only"])
    flat = [name for bucket in buckets for name in bucket]
    # every skill in EXACTLY one bucket (no dup, no gap)
    assert len(flat) == len(set(flat)), "a skill landed in two buckets"
    from scripts.validation.skill_graph_consistency import parse_graph
    assert set(flat) == set(parse_graph(_REPO_ROOT)), "buckets != skill roster"
    assert out["total"] == 45
    assert out["counts"]["orchestrated"] == len(out["orchestrated"])


def test_known_orchestrated_skills_classify_orchestrated():
    out = cc.classify_skills(_REPO_ROOT)
    # gsc-pull + content-decay are monthly STEPS writers
    assert "gsc-pull" in out["orchestrated"]
    assert "content-decay" in out["orchestrated"]
    # the content_pipeline name-normalized writers also resolve
    assert "new-blog" in out["orchestrated"]
    assert "generate-images" in out["orchestrated"]


def test_known_commanded_only_skill_classifies_commanded():
    out = cc.classify_skills(_REPO_ROOT)
    # drift-check is invoked by /pseo-driftcheck but is in NO workflow STEPS
    assert "drift-check" in out["commanded"]
    assert "drift-check" not in out["orchestrated"]


def test_known_ad_hoc_skill_classifies_ad_hoc_only():
    out = cc.classify_skills(_REPO_ROOT)
    # sf-import: not in any workflow STEPS, not invoked by a command SKILL.md path
    assert "sf-import" in out["ad_hoc_only"]
    assert "sf-import" not in out["orchestrated"]
    assert "sf-import" not in out["commanded"]


def test_orchestrated_skill_names_match_workflow_writers():
    names = cc.orchestrated_skill_names()
    # all 4 workflows contribute; content_pipeline via name-normalization
    for expected in ("gsc-pull", "quick-wins", "content-decay", "tech-audit",
                     "schema-audit", "topical-map", "faq-optimization"):
        assert expected in names


# ===========================================================================
# A2. STATIC — commanded precision (prose mention != invocation) + TEETH
# ===========================================================================

def test_commanded_uses_skill_md_path_not_prose(tmp_path):
    root = tmp_path / "engine"
    _write_skill(root, "cat", "planted-invoked")
    _write_skill(root, "cat", "planted-mentioned")
    # the command INVOKES planted-invoked (SKILL.md path) but only MENTIONS
    # planted-mentioned in prose — the mention must NOT make it commanded.
    _write_command(root, "zzz", invokes_skill_path="skills/cat/planted-invoked/SKILL.md",
                   prose_mentions=("planted-mentioned",))
    commanded = cc.commanded_skill_names(root)
    assert "planted-invoked" in commanded
    assert "planted-mentioned" not in commanded


def test_classify_skills_teeth_planted_tree(tmp_path):
    root = tmp_path / "engine"
    _write_skill(root, "cat", "planted-cmd")
    _write_skill(root, "cat", "planted-adhoc")
    _write_command(root, "zzz", invokes_skill_path="skills/cat/planted-cmd/SKILL.md")
    out = cc.classify_skills(root)
    assert out["ad_hoc_only"] == ["planted-adhoc"]
    assert out["commanded"] == ["planted-cmd"]
    assert out["orchestrated"] == []


def test_classify_skills_orchestrated_precedes_commanded(tmp_path):
    root = tmp_path / "engine"
    _write_skill(root, "cat", "planted-cmd")
    _write_command(root, "zzz", invokes_skill_path="skills/cat/planted-cmd/SKILL.md")
    # injected orchestrated set wins the precedence race over commanded
    out = cc.classify_skills(root, orchestrated={"planted-cmd"})
    assert out["orchestrated"] == ["planted-cmd"]
    assert out["commanded"] == []


# ===========================================================================
# B. STATIC — MCP tool partition (orchestrated / declared-only / unused)
# ===========================================================================

def test_classify_mcp_known_orchestrated_tool():
    out = cc.classify_mcp(_REPO_ROOT)
    assert "gsc__search_analytics" in out["orchestrated"]
    assert "dataforseo__on_page_lighthouse" in out["orchestrated"]


def test_classify_mcp_declared_only_tool():
    out = cc.classify_mcp(_REPO_ROOT)
    # scrapling__get: declared by scrapling-ops, never in a workflow STEP
    assert "scrapling__get" in out["declared_only"]
    assert "scrapling__get" not in out["orchestrated"]


def test_classify_mcp_unused_tool():
    out = cc.classify_mcp(_REPO_ROOT)
    # genuinely unused: in the registry, declared by NO skill, orchestrated by none
    assert "dataforseo__backlinks_summary" in out["unused"]
    assert "scrapling__list_sessions" in out["unused"]


def test_classify_mcp_inline_flow_optional_is_declared_not_unused():
    # REGRESSION (manager fix): init-project declares mcp__gsc__list_sites via the YAML
    # INLINE-FLOW form  `optional: ["mcp__gsc__list_sites"]`  — which 3a's line-anchored
    # declared_tools parser misses (it only sets `kind` on a bare `optional:` line). The
    # tool is declared AND invoked by init-project, so the audit must classify it
    # declared-only, never "unused/dead" (honors the prompt's do-not-overclaim-dead rule).
    out = cc.classify_mcp(_REPO_ROOT)
    assert "gsc__list_sites" in out["declared_only"]
    assert "gsc__list_sites" not in out["unused"]


def test_classify_mcp_partitions_registry():
    out = cc.classify_mcp(_REPO_ROOT)
    orch, dec, unused = set(out["orchestrated"]), set(out["declared_only"]), set(out["unused"])
    # disjoint
    assert orch & dec == set() and orch & unused == set() and dec & unused == set()
    # union == the full registry tool set
    assert orch | dec | unused == cc.registry_tool_keys(_REPO_ROOT)
    assert out["total"] == len(orch | dec | unused)


def test_classify_mcp_higgsfield_is_external_not_a_server_bucket():
    out = cc.classify_mcp(_REPO_ROOT)
    external = set(out["external_optional"])
    assert "higgsfield__generate_image" in external
    # higgsfield is NOT a registry server -> never in the 3 server buckets
    for bucket in ("orchestrated", "declared_only", "unused"):
        assert not any(t.startswith("higgsfield__") for t in out[bucket])


def test_orchestrated_tool_keys_skip_none_tool_steps():
    keys = cc.orchestrated_tool_keys()
    # schema_audit + new_content_plan carry "tool": None -> contribute nothing;
    # content_pipeline carries no tool key at all -> contributes nothing.
    assert "gsc__search_analytics" in keys
    assert len(keys) == 7  # the 7 non-None workflow tools


# ===========================================================================
# C. STATIC — script references (referenced / orphaned) + TEETH
# ===========================================================================

def test_classify_scripts_known_referenced():
    out = cc.classify_scripts(_REPO_ROOT)
    referenced = set(out["referenced"])
    # this very module is imported by orchestration_metrics + a command + tests
    assert any(p.endswith("reporting/capability_coverage.py") or
               p.endswith("reporting/portfolio_status.py") for p in referenced)
    assert isinstance(out["orphaned"], list)
    assert out["total"] == out["counts"]["referenced"] + out["counts"]["orphaned"]


def test_classify_scripts_teeth_planted_tree(tmp_path):
    root = tmp_path / "engine"
    helper = root / "scripts" / "sub" / "used_helper_mod.py"
    caller = root / "scripts" / "sub" / "caller_mod.py"
    orphan = root / "scripts" / "sub" / "lonely_orphan_mod.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("X = 1\n", encoding="utf-8")
    caller.write_text("from scripts.sub.used_helper_mod import X\n", encoding="utf-8")
    orphan.write_text("def f():\n    return 0\n", encoding="utf-8")
    out = cc.classify_scripts(root)
    referenced = set(out["referenced"])
    orphaned = {o["path"] for o in out["orphaned"]}
    assert any(p.endswith("used_helper_mod.py") for p in referenced)
    assert any(p.endswith("lonely_orphan_mod.py") for p in orphaned)
    # the orphan record carries a low_confidence flag (bool)
    rec = next(o for o in out["orphaned"] if o["path"].endswith("lonely_orphan_mod.py"))
    assert isinstance(rec["low_confidence"], bool)


# ===========================================================================
# D. Recommendations — ad-hoc skills ranked by graph centrality
# ===========================================================================

def test_recommendations_only_ad_hoc_skills_ranked_by_centrality():
    recs = cc.recommendations(_REPO_ROOT)
    out = cc.classify_skills(_REPO_ROOT)
    adhoc = set(out["ad_hoc_only"])
    assert recs, "expected at least one ad-hoc skill to recommend"
    # every recommended skill is ad-hoc-only (never an already-orchestrated one)
    for rec in recs:
        assert rec["skill"] in adhoc
        assert isinstance(rec["centrality"], int)
    # sorted by centrality descending (the promote-first ordering)
    centralities = [r["centrality"] for r in recs]
    assert centralities == sorted(centralities, reverse=True)


# ===========================================================================
# E. RUNTIME — events.jsonl signals (seeded tmp workspace) + honest labeling
# ===========================================================================

def test_read_events_tolerates_malformed_lines(tmp_path):
    ws = tmp_path / "ws"
    path = ws / "projects" / "demo" / "_state" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"event_kind": "audit", "audit_target": "Bash"}) + "\n"
        + "{ not json at all\n"
        + json.dumps({"event_kind": "provenance", "target_excel_sheet": "schema"}) + "\n",
        encoding="utf-8",
    )
    events = cc.read_events(path)
    assert len(events) == 2  # the malformed line is skipped, not fatal


def test_read_events_missing_file_is_empty(tmp_path):
    assert cc.read_events(tmp_path / "nope" / "events.jsonl") == []


def test_observed_mcp_tools_from_audit_target_token():
    events = [
        {"event_kind": "audit", "audit_target": "mcp__gsc__search_analytics:site=x"},
        {"event_kind": "audit", "audit_target": "Bash"},  # not a tool
        {"event_kind": "audit", "audit_target": "invariants:20"},  # not a tool
    ]
    observed = cc.observed_mcp_tools(events)
    assert "gsc__search_analytics" in observed
    assert len(observed) == 1


def test_observed_mcp_tools_unions_coverage_observed_mcp():
    events = []
    coverage_records = [{"steps": [{"observed_mcp": ["mcp__dataforseo__on_page_lighthouse"]}]}]
    observed = cc.observed_mcp_tools(events, coverage_records=coverage_records)
    assert "dataforseo__on_page_lighthouse" in observed


def test_observed_mcp_tools_skips_external_higgsfield():
    events = [{"event_kind": "audit", "audit_target": "mcp__higgsfield__generate_image:x"}]
    assert cc.observed_mcp_tools(events) == set()


def test_sheet_writer_map_maps_orchestrated_sheets():
    m = cc.sheet_writer_map()
    assert m["gsc_performance"] == "gsc-pull"
    assert m["tech_seo"] == "tech-audit"
    assert m["schema"] == "schema-audit"


def test_runtime_coverage_sheet_proxy_and_unattributed(tmp_path):
    ws = tmp_path / "ws"
    _write_events(ws, "demo", [
        {"event_kind": "audit", "audit_target": "mcp__gsc__search_analytics:site=x"},
        {"event_kind": "provenance", "target_excel_sheet": "gsc_performance", "rows_written": 9},
        {"event_kind": "provenance", "target_excel_sheet": "redirect_404", "rows_written": 3},
    ])
    rt = cc.runtime_coverage(ws, "demo")
    assert "gsc__search_analytics" in rt["observed_mcp_tools"]
    # gsc_performance -> gsc-pull writer (sheet proxy)
    assert "gsc-pull" in rt["observed_writer_skills"]
    # redirect_404 is owned by no orchestrated writer -> honestly unattributed
    assert "redirect_404" in rt["unattributed_sheets"]
    assert isinstance(rt["note"], str) and rt["note"]


def test_runtime_coverage_missing_project_is_empty_not_crash(tmp_path):
    rt = cc.runtime_coverage(tmp_path / "ws", "ghost")
    assert rt["observed_mcp_tools"] == []
    assert rt["observed_writer_skills"] == []


# ===========================================================================
# F. coverage_report + render_report
# ===========================================================================

def test_coverage_report_static_only_has_no_runtime():
    report = cc.coverage_report(_REPO_ROOT)
    assert report["runtime"] is None
    assert report["skills"]["total"] == 45
    assert set(report["mcp"].keys()) >= {"orchestrated", "declared_only", "unused"}
    assert "scripts" in report and "recommendations" in report


def test_coverage_report_with_workspace_has_runtime(tmp_path):
    ws = tmp_path / "ws"
    _write_events(ws, "demo", [
        {"event_kind": "provenance", "target_excel_sheet": "gsc_performance", "rows_written": 5},
    ])
    report = cc.coverage_report(_REPO_ROOT, workspace_root=ws, slug="demo")
    assert report["runtime"] is not None
    assert report["runtime"]["slug"] == "demo"
    assert "gsc-pull" in report["runtime"]["observed_writer_skills"]


def test_render_report_contains_headline_counts_and_categories():
    report = cc.coverage_report(_REPO_ROOT)
    out = cc.render_report(report)
    assert "45" in out  # the skill total
    # the three skill buckets are surfaced (Turkish operator labels)
    assert "orchestrated" in out.lower() or "orkestr" in out.lower()
    assert "ad-hoc" in out.lower()
    # a genuinely-unused MCP tool is named so the operator sees dormant capability
    assert "dataforseo__backlinks_summary" in out


def test_render_report_is_deterministic():
    report = cc.coverage_report(_REPO_ROOT)
    assert cc.render_report(report) == cc.render_report(report)


# ===========================================================================
# G. READ-ONLY proof — the module source contains NO write primitive
# ===========================================================================

def test_module_has_zero_write_primitives():
    src = Path(cc.__file__).read_text(encoding="utf-8")
    forbidden = [
        "os.replace", ".write_text(", ".write_bytes(", "json.dump(",
        ".write_coverage", ".reserve(", ".confirm(", ".release(",
        "events_writer", "transaction.append", "transaction.replace",
    ]
    for token in forbidden:
        assert token not in src, f"read-only violation: {token!r} present in module"
    # no file opened in a write/append mode
    assert re.search(r"open\([^)]*['\"][wax]", src) is None


def test_module_is_parents2_anchored_not_plugin_root():
    src = Path(cc.__file__).read_text(encoding="utf-8")
    assert "parents[2]" in src
    # the 0c bare-CLI lesson: ROOT is computed from parents[2], NEVER read from the
    # installed-plugin env var (a docstring explaining why we avoid it is fine —
    # pb1/3a do the same; READING it for path resolution is the anti-pattern).
    assert "environ" not in src
    assert "getenv" not in src


def test_module_reuses_pb1_and_3a():
    src = Path(cc.__file__).read_text(encoding="utf-8")
    assert "skill_graph_consistency" in src  # pb1 parse_graph
    assert "skill_mcp_usage" in src           # 3a declared_tools


# ===========================================================================
# H. CLI — exit 0 always (never fails a build), like orchestration_metrics
# ===========================================================================

def test_main_static_exit_zero(capsys):
    assert cc.main([]) == 0
    out = capsys.readouterr().out
    assert "45" in out


def test_main_with_workspace_exit_zero(tmp_path, capsys):
    ws = tmp_path / "ws"
    _write_events(ws, "demo", [
        {"event_kind": "provenance", "target_excel_sheet": "schema", "rows_written": 1},
    ])
    assert cc.main(["--workspace-root", str(ws), "--slug", "demo"]) == 0
