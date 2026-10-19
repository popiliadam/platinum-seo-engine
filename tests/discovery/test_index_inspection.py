"""S-21 — verify-indexing reads the URL Inspection result from the right fields.

It compared the raw coverageState sentence with its own enum (so everything
looked like a mismatch) and capped runs at 200/day although the API allows
2,000/day per property.
"""
from __future__ import annotations

from pathlib import Path

from scripts.discovery import index_inspection as ii


def _raw(verdict: str | None, coverage: str | None, state: str | None = "INDEXING_ALLOWED") -> dict:
    isr = {k: v for k, v in (("verdict", verdict), ("coverageState", coverage),
                              ("indexingState", state)) if v is not None}
    return {"inspectionResult": {"indexStatusResult": isr}}


def test_sample_responses_map_to_the_right_status() -> None:
    assert ii.classify(_raw("PASS", "Submitted and indexed")).status == "indexed"
    assert ii.classify(_raw("PASS", "Indexed, not submitted in sitemap")).status == "indexed"
    assert ii.classify(_raw("NEUTRAL", "Crawled - currently not indexed")).status == "crawled_not_indexed"
    assert ii.classify(_raw("NEUTRAL", "Discovered - currently not indexed")).status == "not_indexed"
    blocked = ii.classify(_raw("FAIL", "Excluded by ‘noindex’ tag", "BLOCKED_BY_META_TAG"))
    assert blocked.status == "not_indexed" and "BLOCKED_BY_META_TAG" in blocked.reason


def test_missing_index_status_is_unknown_not_guessed() -> None:
    assert ii.classify({}).status == "unknown"
    assert ii.classify(_raw("VERDICT_UNSPECIFIED", None, None)).status == "unknown"


def test_quota_is_the_real_api_limit() -> None:
    assert ii.URL_INSPECTION_DAILY_QUOTA == 2000
    assert ii.run_cap(500) == 500
    assert ii.run_cap(500, used_today=1800) == 200


def test_skill_uses_the_classifier_and_real_quota() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "skills" / "publishing" / "verify-indexing" / "SKILL.md").read_text(encoding="utf-8")
    assert "index_inspection.classify" in text and "2,000" in text
    assert '.get("coverageState", "unknown")' not in text
    assert "max 200 URL" not in text
