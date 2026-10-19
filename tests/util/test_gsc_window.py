"""D-01 / D-04 — GSC row limit, truncation flag and non-overlapping windows."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from scripts.util import gsc_window as gw

ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 10, 19)


def test_windows_end_three_days_ago_and_do_not_overlap() -> None:
    recent, prev = gw.comparison_windows(TODAY, 28)
    assert recent.end == date(2026, 10, 16) and recent.days == prev.days == 28
    assert prev.end < recent.start and (recent.start - prev.end).days == 1


def test_truncation_flags_known_caps() -> None:
    rows = [{"keys": [str(i)]} for i in range(1000)]
    assert gw.truncation({"rows": rows})["truncated"]
    assert gw.truncation({"rows": rows * 25})["truncated"]
    assert not gw.truncation({"rows": rows[:999]})["truncated"]
    assert gw.truncation({"rows": rows[:999] * 2})["rows"] == 1998


def _gsc_calls(text: str) -> list[str]:
    return re.findall(r"mcp__gsc__(?:enhanced_)?search_analytics\((.*?)\n\)", text, re.S)


def test_every_documented_gsc_call_passes_row_limit_and_lagged_window() -> None:
    calls = 0
    for path in list((ROOT / "skills").rglob("SKILL.md")) + list((ROOT / "commands").glob("*.md")):
        for block in _gsc_calls(path.read_text(encoding="utf-8")):
            calls += 1
            assert "rowLimit" in block, path
            assert "endDate=today.isoformat()" not in block, path
    assert calls >= 6
    for path in (ROOT / "skills").rglob("SKILL.md"):
        text = path.read_text(encoding="utf-8")
        if "mcp__gsc__search_analytics" in text or "mcp__gsc__enhanced_search_analytics" in text:
            assert "rowLimit" in text and "gsc_window" in text, path


def test_transforms_report_truncation() -> None:
    from scripts.discovery import cannibalization_transform as cn
    rows = [{"keys": [f"q{i}", f"https://x.test/p{i % 7}"], "clicks": 1, "impressions": 20,
             "ctr": 0.05, "position": 5.0} for i in range(1000)]
    meta = cn.transform({"rows": rows})["meta"]
    assert meta["gsc_truncation"]["truncated"] is True
