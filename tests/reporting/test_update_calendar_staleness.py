"""S-17 — a period the calendar was never refreshed for is 'unknown', not 'clean'.

google-update-calendar.json was last retrieved 2026-06-10, so June/August/
September 2026 spam updates were missing and the monthly report called those
months clean. The report now compares the calendar's retrieved_at with the
period end, and the bundled seed is refreshed from the official feed.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.reporting import monthly_report as mr
from scripts.reporting import update_calendar as uc

ROOT = Path(__file__).resolve().parents[2]
OLD = [{"id": "a", "name": "May 2026 core update", "begin": "2026-05-01T00:00:00Z",
        "end": "2026-05-15T00:00:00Z", "service_name": "Ranking"}]


def _quality(retrieved_at: str | None, period_end: str = "2026-09-30") -> str:
    ctx = mr._build_measurement_context("2026-09-01", period_end, OLD, None,
                                        calendar_retrieved_at=retrieved_at)
    return ctx["measurement_quality"], ctx["notes"]


def test_period_after_retrieval_is_calendar_stale() -> None:
    quality, notes = _quality("2026-06-10T00:00:00Z")
    assert quality == "calendar_stale"
    assert "2026-06-10" in notes


def test_period_covered_by_retrieval_can_be_clean() -> None:
    assert _quality("2026-10-15T00:00:00Z")[0] == "clean"


def test_retrieved_at_is_the_latest_of_seed_and_overlay(tmp_path: Path) -> None:
    seed = tmp_path / "seed.json"
    overlay = tmp_path / "overlay.json"
    seed.write_text(json.dumps({"retrieved_at": "2026-06-10T00:00:00Z", "updates": []}))
    overlay.write_text(json.dumps({"retrieved_at": "2026-10-01T00:00:00Z", "updates": []}))
    assert uc.calendar_retrieved_at(seed, overlay) == "2026-10-01T00:00:00Z"
    assert uc.calendar_retrieved_at(seed, tmp_path / "missing.json") == "2026-06-10T00:00:00Z"


def test_bundled_seed_has_the_september_2026_spam_update() -> None:
    data = json.loads((ROOT / "google-update-calendar.json").read_text(encoding="utf-8"))
    names = [u["name"].lower() for u in data["updates"]]
    assert any("2026" in n and "spam" in n and ("september" in n or "eylül" in n) for n in names), names
    assert data["retrieved_at"] >= "2026-10-01"


def test_schema_allows_calendar_stale() -> None:
    schema = json.loads((ROOT / "schemas" / "monthly-report.schema.json").read_text())
    text = json.dumps(schema)
    assert '"calendar_stale"' in text
