"""S-02 / S-03 — scaled-content guard and the human verification gate.

S-02 (critical): the engine mass-produces content with no publishing cap, no
      near-duplicate check and no "what does this page add for the user" field
      (Google spam policy: scaled content abuse; 2026-08-28 text also covers
      manipulating generative-AI answers).
S-03 (critical): Google (2026-10-01) — AI-generated content, including title,
      meta description, structured data and alt text, must be checked by a
      person before publishing. A package without a complete verification
      record is never "ready".
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from scripts.production import publication_guard as pg

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
VALUE = "Compares the three heating options by real running cost in our region, with our own installation data."


def _event(days_ago: float, event_type: str = "content_new") -> dict:
    ts = NOW.timestamp() - days_ago * 86400
    return {"event_kind": "work", "event_type": event_type,
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")}


def test_counts_only_new_pages_in_the_last_7_days() -> None:
    events = [_event(1), _event(6.9), _event(8), _event(2, "content_revise"), _event(3, "pillar_launch")]
    assert pg.recent_publications(events, now=NOW) == 3


def test_weekly_cap_stops_new_content() -> None:
    result = pg.check_new_content(draft_text="a b c d e f g", user_value=VALUE, existing={},
                                  publications_last_7d=pg.WEEKLY_PUBLISH_CAP_DEFAULT)
    assert not result.ok and any("weekly" in r for r in result.reasons)


def test_near_duplicate_of_an_existing_page_is_stopped() -> None:
    base = " ".join(f"word{i}" for i in range(200))
    variant = base.replace("word150", "other150")
    result = pg.check_new_content(draft_text=variant, user_value=VALUE,
                                  existing={"https://x.test/a": base}, publications_last_7d=0)
    assert not result.ok and any("https://x.test/a" in r for r in result.reasons)


def test_missing_user_value_is_stopped() -> None:
    result = pg.check_new_content(draft_text="x", user_value="  ", existing={}, publications_last_7d=0)
    assert not result.ok and any("user value" in r for r in result.reasons)


def test_distinct_valuable_page_under_cap_passes() -> None:
    result = pg.check_new_content(draft_text="completely different text here", user_value=VALUE,
                                  existing={"https://x.test/a": "unrelated words entirely"},
                                  publications_last_7d=1)
    assert result.ok and result.reasons == ()


# --- S-03 -------------------------------------------------------------------------

def _record(**over) -> dict:
    rec = {"verified_by": "Ayşe Yılmaz", "verified_at": "2026-10-19T10:00:00Z",
           "checked": ["text", "title", "meta_description", "structured_data", "alt_text"]}
    rec.update(over)
    return {"human_verification": rec}


def test_complete_verification_is_ready() -> None:
    assert pg.verification_status(_record()) == (True, ())


@pytest.mark.parametrize("over, missing", [
    ({"verified_by": ""}, "verified_by"),
    ({"verified_at": None}, "verified_at"),
    ({"checked": ["text", "title"]}, "structured_data"),
])
def test_incomplete_verification_is_not_ready(over: dict, missing: str) -> None:
    ready, problems = pg.verification_status(_record(**over))
    assert not ready and any(missing in p for p in problems)


def test_missing_record_is_not_ready() -> None:
    ready, problems = pg.verification_status({})
    assert not ready and problems


def test_blank_template_is_not_ready() -> None:
    ready, _ = pg.verification_status(pg.blank_verification_record())
    assert not ready


def test_naive_now_and_aware_events_do_not_crash() -> None:
    from datetime import datetime
    from scripts.production.publication_guard import recent_publications
    events = [{"event_kind": "work", "event_type": "content_new", "timestamp": "2026-10-18T10:00:00Z"}]
    assert recent_publications(events, now=datetime(2026, 10, 19, 9, 0)) == 1
