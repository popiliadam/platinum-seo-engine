"""D-15 — the monthly report reads the schema header row, keeps column positions,
and warns when GSC data is older than 7 days."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from openpyxl import Workbook

from scripts.reporting import monthly_report as mr


def test_stray_title_and_blank_header_cell_do_not_shift_columns(tmp_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "gsc_performance"
    ws.append(["GSC Performance — rapor"])          # row 1: stray title
    ws.append([])
    ws.append([])
    ws.append(["url", None, "clicks_recent"])        # row 4 = schema header_row, blank cell
    ws.append(["https://x.test/a", "ignored", 42])
    path = tmp_path / "fixture-report.xlsx"
    wb.save(path)
    rows = mr.read_workbook(workbook_path=path, sheets=["gsc_performance"])["gsc_performance"]
    assert rows == [{"url": "https://x.test/a", "clicks_recent": 42}]


def test_header_row_comes_from_schema() -> None:
    assert mr.schema_header_rows()["gsc_performance"] == 4


def test_gsc_age_warning(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"source": {"kind": "gsc_mcp"},
                                  "timestamp": "2026-10-01T10:00:00Z"}) + "\n", encoding="utf-8")
    age = mr.gsc_data_age_days(events, date(2026, 10, 19))
    assert age == 18
    ctx = mr._build_measurement_context("2026-09-01", "2026-09-30", [], None, gsc_age_days=age)
    assert "18 gün önce" in ctx["notes"]
    fresh = mr._build_measurement_context("2026-09-01", "2026-09-30", [], None, gsc_age_days=3)
    assert "gün önce" not in fresh["notes"]
