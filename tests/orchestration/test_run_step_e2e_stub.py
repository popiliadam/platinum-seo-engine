"""End-to-end STUB harness for the orchestrator spine (AMO batch 1b HEADLINE).

Feeds canned raw-drop JSONs (correct / stale / wrong-project / truncated /
missing) through run_step with a FAKE commit_fn — NO live model, NO MCP, NO real
workbook — and asserts the coverage STEP STATUS per scenario, plus the
silent-skip gate. Then run_sequence over a sequence proves verdict derivation and
that the WRITTEN coverage record validates against coverage.schema.json.

The committer is INJECTABLE (commit_fn) precisely so this harness need not stand
up a real workbook; test_committer.py exercises the REAL transaction.replace wrap.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from jsonschema import Draft7Validator

from scripts.orchestration import coverage
from scripts.orchestration.run_step import StepSpec, run_sequence, run_step

RUN_ID = "vento-2026-06-05-a1b2"
SLUG = "vento"
NOW = 1_750_000_000
SHEET = "topical_map"

ROOT = Path(__file__).resolve().parents[2]
COVERAGE_SCHEMA = json.loads(
    (ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8")
)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _drop(
    path: Path,
    *,
    run_id: str = RUN_ID,
    slug: str = SLUG,
    rows: list[dict] | None = None,
    declared_count: int | None = None,
    fetched_at: str | None = None,
    mtime: float = NOW - 60,
) -> Path:
    rows = [{"q": f"kw{i}"} for i in range(10)] if rows is None else rows
    payload = {
        "provenance": {
            "run_id": run_id,
            "slug": slug,
            "site_url": "https://vento.example",
            "window": "2026-05",
            "tool": "mcp__gsc__search_analytics",
            "fetched_at": _iso(NOW - 60) if fetched_at is None else fetched_at,
            "declared_count": len(rows) if declared_count is None else declared_count,
        },
        "rows": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _fake_commit(workbook_path, sheet, rows, *, run_id, project_slug, schema_path=None):
    """WriteResult-like: run_step reads only .rows_affected. No real workbook."""
    return SimpleNamespace(rows_affected=len(rows))


def _identity(rows: list[dict]) -> list[dict]:
    return list(rows)


def _spec(raw_path: Path, *, name: str = "fetch_gsc", transform=_identity) -> StepSpec:
    return StepSpec(
        name=name, raw_path=raw_path, sheet=SHEET, transform=transform,
        observed_mcp=("mcp__gsc__search_analytics",),
    )


def _run(spec: StepSpec, tmp_path: Path) -> dict:
    return run_step(
        spec, run_id=RUN_ID, project_slug=SLUG, workspace_root=tmp_path,
        workbook_path=tmp_path / "master.xlsx", now_epoch=NOW, commit_fn=_fake_commit,
    )


# --- per-scenario coverage step status -------------------------------------

def test_correct_drop_satisfied(tmp_path: Path) -> None:
    step = _run(_spec(_drop(tmp_path / "d.json")), tmp_path)
    assert step["status"] == "satisfied"
    assert step["verification_class"] == "code_verified"
    assert step["input_count"] == 10
    assert step["scored_count"] == 10
    assert step["observed_mcp"] == ["mcp__gsc__search_analytics"]
    # The injectable fake committer means NO real workbook was ever written.
    assert not (tmp_path / "master.xlsx").exists()


def test_stale_drop_failed(tmp_path: Path) -> None:
    step = _run(_spec(_drop(tmp_path / "d.json", mtime=NOW - 200_000)), tmp_path)
    assert step["status"] == "failed"
    assert "input_count" not in step  # gate rejected the drop before any transform


def test_wrong_project_drop_failed(tmp_path: Path) -> None:
    step = _run(_spec(_drop(tmp_path / "d.json", slug="other-project")), tmp_path)
    assert step["status"] == "failed"


def test_truncated_drop_failed(tmp_path: Path) -> None:
    step = _run(_spec(_drop(tmp_path / "d.json", declared_count=99)), tmp_path)
    assert step["status"] == "failed"


def test_missing_file_drop_missing(tmp_path: Path) -> None:
    step = _run(_spec(tmp_path / "nope.json"), tmp_path)
    assert step["status"] == "missing"


def test_silent_skip_drop_failed(tmp_path: Path) -> None:
    # correct drop (10 rows) but the transform drops >50% (keeps 4) -> failed.
    drop = _drop(tmp_path / "d.json")
    step = _run(_spec(drop, transform=lambda rows: list(rows)[:4]), tmp_path)
    assert step["status"] == "failed"
    assert step["input_count"] == 10
    assert step["scored_count"] == 4


# --- run_sequence: verdict derivation + written record validates -----------

def test_run_sequence_incomplete_with_missing_step(tmp_path: Path) -> None:
    correct = _spec(_drop(tmp_path / "c.json"), name="fetch_gsc")
    missing = _spec(tmp_path / "nope.json", name="fetch_decay")
    record = run_sequence(
        [correct, missing], run_id=RUN_ID, project_slug=SLUG, workspace_root=tmp_path,
        workbook_path=tmp_path / "master.xlsx", now_epoch=NOW, commit_fn=_fake_commit,
    )
    assert record["verdict"] == "incomplete"
    assert record["required_satisfied"] is False
    assert [s["status"] for s in record["steps"]] == ["satisfied", "missing"]

    # The WRITTEN coverage record validates against the frozen schema.
    path = coverage.coverage_path(tmp_path, SLUG, RUN_ID)
    assert path.exists()
    written = json.loads(path.read_text(encoding="utf-8"))
    assert list(Draft7Validator(COVERAGE_SCHEMA).iter_errors(written)) == []


def test_run_sequence_pass_when_all_satisfied(tmp_path: Path) -> None:
    record = run_sequence(
        [_spec(_drop(tmp_path / "c.json"))], run_id=RUN_ID, project_slug=SLUG,
        workspace_root=tmp_path, workbook_path=tmp_path / "master.xlsx",
        now_epoch=NOW, commit_fn=_fake_commit, write=False,
    )
    assert record["verdict"] == "pass"
    assert record["required_satisfied"] is True


def test_run_sequence_does_not_abort_on_failed_step(tmp_path: Path) -> None:
    # a failing first step must NOT prevent later steps from being recorded.
    stale = _spec(_drop(tmp_path / "a.json", mtime=NOW - 200_000), name="s1")
    good = _spec(_drop(tmp_path / "b.json"), name="s2")
    record = run_sequence(
        [stale, good], run_id=RUN_ID, project_slug=SLUG, workspace_root=tmp_path,
        workbook_path=tmp_path / "master.xlsx", now_epoch=NOW, commit_fn=_fake_commit,
        write=False,
    )
    assert [s["status"] for s in record["steps"]] == ["failed", "satisfied"]
    assert record["verdict"] == "failed"
