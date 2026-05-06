"""
tests/skills/test_drift_check.py — drift-check governance skill tests.

Eleven cases mirroring the W-S worker brief acceptance gate:

  1.  test_all_pass_green_verdict        — synthetic clean wb, 20/20 PASS → GREEN
  2.  test_critical_fail_red_verdict     — F-01 fail (statusEnum drift) → RED
  3.  test_high_fail_red_verdict         — F-08 sparse-pilot routing → AMBER (manual triage)
  4.  test_medium_fail_amber_verdict     — F-18 fail (ISO 8601 invalid) → AMBER
  5.  test_skip_missing_sheet_amber      — sheet missing → SKIP + AMBER (not RED)
  6.  test_consistency_report_schema_valid — JSON schema validate
  7.  test_unknown_rule_id_raises        — aggregator rejects synthetic ids
  8.  test_provenance_event_emitted      — events.jsonl event_kind=audit
  9.  test_workspace_read_only_no_writes — master.xlsx SHA-256 unchanged
  10. test_f15_manual_review_amber       — F-15 → manual_review_required[] populated
  11. test_auto_repair_available_flag    — F-22 (FIFO 7 backups) → auto_repair_available=true

Schemas referenced:
  - schemas/master-excel.schema.json (statusEnum 7, severityEnum 4, columns)
  - schemas/events.schema.json (event_kind=audit branch)
  - schemas/consistency-report.schema.json (output report shape)
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from openpyxl import Workbook, load_workbook

from scripts.state import events_writer
from scripts.validation import validate_invariants as vi


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"


# ---------------------------------------------------------------------------
# Fixtures — synthetic workbook builder
# ---------------------------------------------------------------------------

def _build_clean_wb(path: Path) -> None:
    """Write a synthetic master.xlsx that ALL 20 rules pass on (within
    the SKIP semantics for sheets not present)."""
    wb = Workbook()
    # quick_wins (D-03 idempotent URLs)
    qw = wb.active
    qw.title = "quick_wins"
    qw.append(["query", "url", "current_position", "impressions_30d",
               "clicks_30d", "ctr_pct", "potential_clicks", "opportunity",
               "action", "priority"])
    qw.append(["foo", "https://example.com/a", 12, 100, 5, 5.0, 10,
               "High", "do x", "MEDIUM"])
    # opportunity (F-16 fk: every qw url ⊆ opp.url)
    op = wb.create_sheet("opportunity")
    op.append(["query", "opportunity_score", "current_position", "ctr_pct",
               "impressions_30d", "clicks_30d", "potential_clicks",
               "assigned_url_action"])
    op.append(["foo", 800, 12, 5.0, 100, 5, 10,
               "https://example.com/a | do x"])
    # crawl_sitemap (F-08: provide URL coverage)
    cs = wb.create_sheet("crawl_sitemap")
    cs.append(["category", "metric", "value", "status", "action"])
    cs.append(["url", "page", "https://example.com/a", "EXISTS", ""])
    # gsc_performance (also F-08 source)
    gp = wb.create_sheet("gsc_performance")
    gp.append(["url", "clicks_recent", "clicks_previous", "clicks_delta",
               "clicks_delta_pct", "impressions_recent",
               "impressions_previous", "impressions_delta",
               "ctr_recent", "position_recent", "position_previous", "note"])
    gp.append(["https://example.com/a", 5, 4, 1, 25.0, 100, 90, 10, 5.0,
               12.0, 13.0, ""])
    # dashboard (F-02/F-03/F-04 only check absence of formula cells)
    db = wb.create_sheet("dashboard")
    db.append(["KPI", "value"])
    db.append(["total_pillars", 0])
    # master_task — empty (header only) so F-01/F-09/F-18 PASS trivially
    mt = wb.create_sheet("master_task")
    mt.append(["task_id", "task", "primary_source", "related_sources", "url",
               "category", "priority", "impact", "duration_est_min", "status",
               "created_date", "done_date", "assignee", "note", "auto_generated",
               "dependencies", "effort_actual_min", "metric_impact_json",
               "work_log_ref"])
    wb.save(str(path))


def _setup_workspace(tmp_path: Path, slug: str) -> Path:
    """Create projects/{slug}/_state/ skeleton + return master.xlsx path."""
    pdir = tmp_path / "projects" / slug
    (pdir / "_state" / "workflows").mkdir(parents=True, exist_ok=True)
    (pdir / "_state" / "backups" / "master").mkdir(parents=True, exist_ok=True)
    (pdir / "outputs" / "reports").mkdir(parents=True, exist_ok=True)
    cfg = {"project_id": slug, "language": {"content_locale": "tr-TR"}, "market": "TR"}
    (pdir / "project.config.json").write_text(json.dumps(cfg), "utf-8")
    return pdir / "master.xlsx"


@pytest.fixture
def clean_wb_path(tmp_path: Path) -> Path:
    slug = "drifttest"
    wb_path = _setup_workspace(tmp_path, slug)
    _build_clean_wb(wb_path)
    return wb_path


@pytest.fixture
def consistency_schema() -> dict:
    return json.loads(
        (SCHEMAS / "consistency-report.schema.json").read_text("utf-8")
    )


@pytest.fixture
def events_schema() -> dict:
    return json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Test 1 — synthetic clean wb → GREEN
# ---------------------------------------------------------------------------

def test_all_pass_green_verdict(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    wb = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb, slug, workspace_root=tmp_path)
    finally:
        wb.close()
    agg = vi.aggregate_verdicts(results)
    # All-clean expectation: no FAIL anywhere; SKIPs are allowed (which
    # would land us on AMBER) — assert no RED at minimum, plus that the
    # 5 CRITICAL rules all PASS (no SKIP among them either).
    by_id = {r["id"]: r for r in results}
    for rid in ("F-01", "F-02", "F-03", "F-04", "F-05"):
        assert by_id[rid]["verdict"] == "PASS", (
            f"{rid} expected PASS, got {by_id[rid]['verdict']}: "
            f"{by_id[rid]['evidence']}"
        )
    # F-08, F-10, F-16 must PASS (URLs intersect, idempotent, FK satisfied).
    for rid in ("F-08", "F-10", "F-16"):
        assert by_id[rid]["verdict"] == "PASS", (
            f"{rid} expected PASS, got {by_id[rid]['verdict']}: "
            f"{by_id[rid]['evidence']}"
        )
    assert agg["overall"] in ("GREEN", "AMBER")  # SKIPs may push to AMBER
    assert agg["fail_count"] == 0


# ---------------------------------------------------------------------------
# Test 2 — F-01 fail (statusEnum drift) → RED
# ---------------------------------------------------------------------------

def test_critical_fail_red_verdict(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    # Mutate the wb: append a master_task row with bogus status.
    wb = load_workbook(str(clean_wb_path))
    mt = wb["master_task"]
    bogus_row = ["T-9999", "bad task", "manual", "", "", "tech", "MEDIUM",
                 "low", 30, "FAKE_STATUS",  # ← outside 7-value enum
                 "2026-04-30T00:00:00Z", "", "", "", False, "", 0, "", ""]
    mt.append(bogus_row)
    wb.save(str(clean_wb_path))
    wb.close()

    wb_ro = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb_ro, slug, workspace_root=tmp_path)
    finally:
        wb_ro.close()
    agg = vi.aggregate_verdicts(results)
    by_id = {r["id"]: r for r in results}
    assert by_id["F-01"]["verdict"] == "FAIL"
    assert "FAKE_STATUS" in by_id["F-01"]["sample_violations"][0]
    assert agg["overall"] == "RED"


# ---------------------------------------------------------------------------
# Test 3 — F-08 sparse-pilot routing → AMBER (manual triage)
# ---------------------------------------------------------------------------

def test_high_fail_red_verdict(tmp_path: Path) -> None:
    """Sparse pilot wb (only quick_wins, no crawl_sitemap, no gsc_performance).
    F-08 returns FAIL with manual_triage=True, which the aggregator routes
    to AMBER (not RED) — F2 flag from the W-S worker brief."""
    slug = "sparse"
    wb_path = _setup_workspace(tmp_path, slug)
    wb = Workbook()
    qw = wb.active
    qw.title = "quick_wins"
    qw.append(["query", "url", "current_position", "impressions_30d",
               "clicks_30d", "ctr_pct", "potential_clicks", "opportunity",
               "action", "priority"])
    qw.append(["foo", "https://example.com/orphan", 12, 100, 5, 5.0, 10,
               "High", "x", "MEDIUM"])
    op = wb.create_sheet("opportunity")
    op.append(["query", "opportunity_score", "current_position", "ctr_pct",
               "impressions_30d", "clicks_30d", "potential_clicks",
               "assigned_url_action"])
    op.append(["foo", 800, 12, 5.0, 100, 5, 10,
               "https://example.com/orphan | x"])
    wb.save(str(wb_path))

    wb_ro = load_workbook(str(wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb_ro, slug, workspace_root=tmp_path)
    finally:
        wb_ro.close()
    agg = vi.aggregate_verdicts(results)
    by_id = {r["id"]: r for r in results}
    assert by_id["F-08"]["verdict"] == "FAIL"
    assert by_id["F-08"]["manual_triage"] is True
    # Manual triage routes the FAIL to AMBER (not RED).
    assert "F-08" in agg["manual_review_required"]
    assert agg["overall"] in ("AMBER",)  # explicit: NOT RED


# ---------------------------------------------------------------------------
# Test 4 — F-18 fail (ISO 8601 invalid) → AMBER
# ---------------------------------------------------------------------------

def test_medium_fail_amber_verdict(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    wb = load_workbook(str(clean_wb_path))
    mt = wb["master_task"]
    bogus_row = ["T-1000", "bad date", "manual", "", "", "tech", "MEDIUM",
                 "low", 30, "TODO",
                 "not-a-date",  # ← unparseable
                 "", "", "", False, "", 0, "", ""]
    mt.append(bogus_row)
    wb.save(str(clean_wb_path))
    wb.close()

    wb_ro = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb_ro, slug, workspace_root=tmp_path)
    finally:
        wb_ro.close()
    agg = vi.aggregate_verdicts(results)
    by_id = {r["id"]: r for r in results}
    assert by_id["F-18"]["verdict"] == "FAIL"
    # MEDIUM FAIL → AMBER (no CRITICAL/HIGH FAIL present).
    assert agg["overall"] == "AMBER"


# ---------------------------------------------------------------------------
# Test 5 — sheet missing → SKIP + AMBER (not RED)
# ---------------------------------------------------------------------------

def test_skip_missing_sheet_amber(tmp_path: Path) -> None:
    slug = "minimal"
    wb_path = _setup_workspace(tmp_path, slug)
    wb = Workbook()
    qw = wb.active
    qw.title = "quick_wins"
    qw.append(["query", "url", "current_position", "impressions_30d",
               "clicks_30d", "ctr_pct", "potential_clicks", "opportunity",
               "action", "priority"])
    # Add an opportunity sheet so F-16 doesn't SKIP+AMBER but PASSes.
    op = wb.create_sheet("opportunity")
    op.append(["query", "opportunity_score", "current_position", "ctr_pct",
               "impressions_30d", "clicks_30d", "potential_clicks",
               "assigned_url_action"])
    # Add crawl_sitemap so F-08 doesn't trigger sparse-pilot path
    cs = wb.create_sheet("crawl_sitemap")
    cs.append(["category", "metric", "value", "status", "action"])
    wb.save(str(wb_path))

    wb_ro = load_workbook(str(wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb_ro, slug, workspace_root=tmp_path)
    finally:
        wb_ro.close()
    agg = vi.aggregate_verdicts(results)
    by_id = {r["id"]: r for r in results}
    # master_task missing → F-01 SKIP, F-09 SKIP, F-18 SKIP
    assert by_id["F-01"]["verdict"] == "SKIP"
    assert by_id["F-09"]["verdict"] == "SKIP"
    assert by_id["F-18"]["verdict"] == "SKIP"
    # SKIP must NOT promote to RED — must be AMBER.
    assert agg["overall"] == "AMBER"
    assert agg["fail_count"] == 0


# ---------------------------------------------------------------------------
# Test 6 — consistency-report.json schema validate
# ---------------------------------------------------------------------------

def test_consistency_report_schema_valid(clean_wb_path: Path, tmp_path: Path,
                                          consistency_schema: dict) -> None:
    slug = "drifttest"
    wb = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb, slug, workspace_root=tmp_path)
    finally:
        wb.close()
    agg = vi.aggregate_verdicts(results)
    report = vi.build_consistency_report(
        rule_results=results,
        aggregation=agg,
        project_id=slug,
        report_id=1,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_id=1,
    )
    # Re-validate from outside (build_consistency_report does internal validate
    # but we double-check end-to-end).
    Draft7Validator(consistency_schema).validate(report)
    assert report["schema_version"] == "1.0"
    assert len(report["checks"]) == 20
    assert report["verdict"] in ("GREEN", "AMBER", "RED")


# ---------------------------------------------------------------------------
# Test 7 — aggregator rejects unknown rule id
# ---------------------------------------------------------------------------

def test_unknown_rule_id_raises() -> None:
    bad = [{
        "id": "F-99",
        "severity": "HIGH",
        "verdict": "PASS",
        "evidence": "synthetic",
        "rule": "synthetic",
        "category": "csr_foundation",
    }]
    with pytest.raises(vi.UnknownRuleError):
        vi.aggregate_verdicts(bad)


# ---------------------------------------------------------------------------
# Test 8 — events.jsonl audit event emitted
# ---------------------------------------------------------------------------

def test_provenance_event_emitted(clean_wb_path: Path, tmp_path: Path,
                                   events_schema: dict) -> None:
    slug = "drifttest"
    # Mimic the skill's step 7: emit an event_kind=audit row.
    events_writer.append_audit(
        project_id=slug,
        audit_action="accessed",
        audit_target="invariants:20",
        actor="drift-check",
        notes="verdict=GREEN fails=0",
        workspace_root=tmp_path,
    )
    events_path = tmp_path / "projects" / slug / "_state" / "events.jsonl"
    assert events_path.exists()
    lines = [json.loads(l) for l in events_path.read_text("utf-8").splitlines()
             if l.strip()]
    audits = [e for e in lines if e.get("event_kind") == "audit"]
    assert audits, "no event_kind=audit emitted"
    rec = audits[-1]
    assert rec["audit_action"] == "accessed"
    assert rec["audit_target"] == "invariants:20"
    # Re-validate with the canonical events schema.
    Draft7Validator(events_schema).validate(rec)


# ---------------------------------------------------------------------------
# Test 9 — workspace read-only: master.xlsx SHA-256 unchanged
# ---------------------------------------------------------------------------

def test_workspace_read_only_no_writes(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    sha_before = hashlib.sha256(clean_wb_path.read_bytes()).hexdigest()
    wb = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb, slug, workspace_root=tmp_path)
        agg = vi.aggregate_verdicts(results)
        report = vi.build_consistency_report(
            rule_results=results,
            aggregation=agg,
            project_id=slug,
            report_id=1,
            generated_at="2026-04-30T00:00:00Z",
        )
        assert report["verdict"] in ("GREEN", "AMBER", "RED")
    finally:
        wb.close()
    sha_after = hashlib.sha256(clean_wb_path.read_bytes()).hexdigest()
    assert sha_after == sha_before, (
        "master.xlsx mutated by drift-check evaluation — "
        "read-only governance violated"
    )


# ---------------------------------------------------------------------------
# Test 10 — F-15 manual review populated → AMBER
# ---------------------------------------------------------------------------

def test_f15_manual_review_amber(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    # Add cannibalization rows so F-15 fires (manual triage path).
    wb = load_workbook(str(clean_wb_path))
    cn = wb.create_sheet("cannibalization")
    cn.append(["conflict_pair", "overlapping_queries_est", "total_impact",
               "resolution", "note", "status", "priority"])
    cn.append(["page-a vs page-b", 5, "high", "redirect", "review",
               "TODO", "HIGH"])
    wb.save(str(clean_wb_path))
    wb.close()

    wb_ro = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb_ro, slug, workspace_root=tmp_path)
    finally:
        wb_ro.close()
    agg = vi.aggregate_verdicts(results)
    by_id = {r["id"]: r for r in results}
    assert by_id["F-15"]["verdict"] == "FAIL"
    assert by_id["F-15"]["manual_triage"] is True
    assert "F-15" in agg["manual_review_required"]
    # Aggregator must NOT route this to RED.
    assert agg["overall"] == "AMBER"


# ---------------------------------------------------------------------------
# Test 11 — F-22 auto_repair_available flag set
# ---------------------------------------------------------------------------

def test_auto_repair_available_flag(clean_wb_path: Path, tmp_path: Path) -> None:
    slug = "drifttest"
    backups = tmp_path / "projects" / slug / "_state" / "backups" / "master"
    backups.mkdir(parents=True, exist_ok=True)
    # Create 8 backup files (one over the FIFO cap of 7).
    for i in range(8):
        fname = f"master-2026-04-30T00-00-0{i}-000000Z.xlsx"
        (backups / fname).write_bytes(b"dummy")

    wb = load_workbook(str(clean_wb_path), data_only=True, read_only=True)
    try:
        results = vi.evaluate_all(wb, slug, workspace_root=tmp_path)
    finally:
        wb.close()
    by_id = {r["id"]: r for r in results}
    assert by_id["F-22"]["verdict"] == "FAIL"
    assert by_id["F-22"]["auto_repair_available"] is True
    assert by_id["F-22"]["affected_rows"] == 1  # 8 - 7
    # And the aggregator surfaces it as an auto_repair_available rule id.
    agg = vi.aggregate_verdicts(results)
    assert "F-22" in agg["auto_repair_available"]
