"""O-03 — weekly URL × query GSC history and the per-page update-impact report."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts.ingestion import gsc_history as gh

TODAY = date(2026, 10, 19)  # Monday; lag 3 -> last complete week ends Sun 2026-10-11


def test_weeks_to_pull_are_complete_and_skip_existing() -> None:
    weeks = gh.weeks_to_pull([], today=TODAY, back=3)
    assert [w["iso_week"] for w in weeks] == ["2026-W39", "2026-W40", "2026-W41"]
    assert weeks[-1]["startDate"] == "2026-10-05" and weeks[-1]["endDate"] == "2026-10-11"
    assert gh.weeks_to_pull([{"iso_week": "2026-W41"}], today=TODAY, back=3)[-1]["iso_week"] == "2026-W40"


def test_rows_are_normalized_and_appended(tmp_path: Path) -> None:
    rows = gh.rows_for_week("2026-W41", {"rows": [
        {"keys": ["kombi", "https://X.test/kombi/"], "clicks": 3, "impressions": 40, "position": 6.0}]})
    assert rows == [{"iso_week": "2026-W41", "page": "https://x.test/kombi", "query": "kombi",
                     "clicks": 3, "impressions": 40, "position": 6.0}]
    path = tmp_path / "h.jsonl"
    gh.append_rows(path, rows)
    gh.append_rows(path, rows)
    assert len(gh.read_ledger(path)) == 2


def test_update_impact_names_the_losing_pages() -> None:
    update = {"name": "September 2026 spam update", "begin": "2026-09-24T16:15:00Z",
              "end": "2026-10-08T08:00:00Z"}
    ledger = []
    for w in ("2026-W35", "2026-W36", "2026-W37", "2026-W38"):      # 4 weeks before begin
        ledger += [{"iso_week": w, "page": "https://x.test/a", "clicks": 50, "impressions": 500},
                   {"iso_week": w, "page": "https://x.test/b", "clicks": 10, "impressions": 100}]
    for w in ("2026-W42", "2026-W43", "2026-W44", "2026-W45"):      # 4 weeks after end
        ledger += [{"iso_week": w, "page": "https://x.test/a", "clicks": 20, "impressions": 400},
                   {"iso_week": w, "page": "https://x.test/b", "clicks": 15, "impressions": 120}]
    rep = gh.update_impact(ledger, update)
    assert rep["complete"] and rep["losers"][0]["page"] == "https://x.test/a"
    assert rep["losers"][0]["clicks_delta"] == -120 and rep["gainers"][0]["page"] == "https://x.test/b"
