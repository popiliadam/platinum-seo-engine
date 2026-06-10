"""tests/reporting/test_update_calendar.py — GAP-M-1a (Wave 1a) calendar core.

Covers the two NEW pure modules that implement the Google Search core-update
calendar (GAP-M1 D1):

  - scripts/reporting/update_calendar.py    — load_calendar() + overlaps()
  - scripts/maintenance/refresh_update_calendar.py — parse_incidents() + merge
    (pure parse/merge of status.search.google.com/incidents.json; NO network)

plus the bundled engine seed `google-update-calendar.json` validating against
the new Draft-07 schema.

Rule authority: R-137 (core-update overlap annotation) in
rules/measurement-discipline.md. All-synthetic fixtures; frozen dates passed
as args (rules/time-discipline.md — no date.today() inside the modules).

Provenance of the real data shape: the incidents.json fixture below mirrors the
exact field set of a live status.search.google.com/incidents.json entry
(id/number/begin/end/external_desc/severity/service_name/affected_products),
web-verified 2026-06-10.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from scripts.maintenance import refresh_update_calendar as refresh
from scripts.reporting import update_calendar


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "google-update-calendar.schema.json"
CALENDAR_PATH = REPO_ROOT / "google-update-calendar.json"
UPDATE_CAL_SRC = REPO_ROOT / "scripts" / "reporting" / "update_calendar.py"
REFRESH_SRC = REPO_ROOT / "scripts" / "maintenance" / "refresh_update_calendar.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def synthetic_incidents() -> list[dict]:
    """3 entries: a Ranking update (kept), a Serving outage (filtered out),
    and a rolling Ranking update with end=null (kept, end stays None)."""
    return [
        {
            "id": "RANK-MAY",
            "number": "1",
            "begin": "2026-05-21T15:40:00+00:00",
            "end": "2026-06-02T12:40:00+00:00",
            "external_desc": "May 2026 core update",
            "severity": "low",
            "service_name": "Ranking",
            "affected_products": [{"title": "Ranking", "id": "x"}],
        },
        {
            "id": "SERV-OUT",
            "number": "2",
            "begin": "2026-02-25T03:55:00+00:00",
            "end": "2026-02-25T04:10:00+00:00",
            "external_desc": "Serving was experiencing an issue",
            "severity": "medium",
            "service_name": "Serving",
            "affected_products": [{"title": "Serving", "id": "y"}],
        },
        {
            "id": "RANK-ROLL",
            "number": "3",
            "begin": "2026-06-08T10:00:00+00:00",
            "end": None,
            "external_desc": "Hypothetical rolling core update",
            "severity": "low",
            "service_name": "Ranking",
            "affected_products": [{"title": "Ranking", "id": "x"}],
        },
    ]


@pytest.fixture()
def may_calendar() -> list[dict]:
    """A one-entry calendar shaped like the load_calendar() output."""
    return [
        {
            "id": "RANK-MAY",
            "name": "May 2026 core update",
            "begin": "2026-05-21T15:40:00Z",
            "end": "2026-06-02T12:40:00Z",
            "service_name": "Ranking",
            "severity": "low",
            "source": "google_status_dashboard",
        }
    ]


# ---------------------------------------------------------------------------
# Test 1 — refresh.parse_incidents filters to Ranking, maps the shape,
#          preserves end=null (rolling)
# ---------------------------------------------------------------------------

def test_parse_incidents_filters_ranking_only(synthetic_incidents: list[dict]) -> None:
    updates = refresh.parse_incidents(synthetic_incidents)
    # Serving entry filtered out → 2 Ranking entries remain.
    ids = sorted(u["id"] for u in updates)
    assert ids == ["RANK-MAY", "RANK-ROLL"], f"Serving entry not filtered: {ids}"

    by_id = {u["id"]: u for u in updates}

    may = by_id["RANK-MAY"]
    assert may["name"] == "May 2026 core update"   # external_desc → name
    assert may["service_name"] == "Ranking"
    assert may["severity"] == "low"
    assert may["source"] == "google_status_dashboard"
    # Timestamps normalized to 'Z' suffix (time-discipline UTC storage).
    assert may["begin"] == "2026-05-21T15:40:00Z"
    assert may["end"] == "2026-06-02T12:40:00Z"

    # Rolling update: end stays None (never fabricated into a date).
    roll = by_id["RANK-ROLL"]
    assert roll["end"] is None, "rolling update end=null must be preserved"

    # parse_incidents output validates as calendar-update shape.
    for u in updates:
        assert set(["id", "name", "begin", "service_name"]).issubset(u.keys())


# ---------------------------------------------------------------------------
# Test 2 — overlaps(): rollout_in_period (overlap_days==8) + settling buffer
# ---------------------------------------------------------------------------

def test_overlaps_rollout_in_period(may_calendar: list[dict]) -> None:
    hits = update_calendar.overlaps("2026-05-25", "2026-06-20", may_calendar)
    assert len(hits) == 1
    hit = hits[0]
    assert hit["name"] == "May 2026 core update"
    # [05-25 .. 06-02] inclusive of the active rollout window = 8 days.
    assert hit["overlap_days"] == 8, f"expected 8, got {hit['overlap_days']}"
    assert hit["phase"] == "rollout_in_period"
    assert hit["begin"] == "2026-05-21T15:40:00Z"
    assert hit["end"] == "2026-06-02T12:40:00Z"


def test_overlaps_settling_buffer(may_calendar: list[dict]) -> None:
    # Period starts 2026-06-05; May update ENDED 2026-06-02 (3 days earlier,
    # within the default 7-day settle buffer) → phase 'settling', overlap 0.
    hits = update_calendar.overlaps("2026-06-05", "2026-06-30", may_calendar)
    assert len(hits) == 1
    assert hits[0]["phase"] == "settling"
    assert hits[0]["overlap_days"] == 0


def test_overlaps_outside_buffer_excluded(may_calendar: list[dict]) -> None:
    # Period far after the update's end (and beyond the settle buffer) → no hit.
    hits = update_calendar.overlaps("2026-07-01", "2026-07-31", may_calendar)
    assert hits == []


def test_overlaps_rolling_no_end(may_calendar: list[dict]) -> None:
    rolling = [{
        "id": "ROLL", "name": "Rolling update",
        "begin": "2026-06-08T10:00:00Z", "end": None,
        "service_name": "Ranking",
    }]
    hits = update_calendar.overlaps("2026-06-05", "2026-06-20", rolling)
    assert len(hits) == 1
    assert hits[0]["phase"] == "rolling"
    assert hits[0]["end"] is None


def test_overlaps_ignores_non_ranking(may_calendar: list[dict]) -> None:
    # Even if a non-Ranking entry sneaks into the calendar, overlaps() filters
    # on service_name == "Ranking" (R-137 statement).
    mixed = may_calendar + [{
        "id": "SERV", "name": "Serving blip",
        "begin": "2026-05-26T00:00:00Z", "end": "2026-05-27T00:00:00Z",
        "service_name": "Serving",
    }]
    hits = update_calendar.overlaps("2026-05-25", "2026-06-20", mixed)
    names = {h["name"] for h in hits}
    assert names == {"May 2026 core update"}, f"non-Ranking leaked: {names}"


# ---------------------------------------------------------------------------
# Test 3 — load_calendar(): overlay wins on id collision, union otherwise
# ---------------------------------------------------------------------------

def test_load_calendar_overlay_wins(tmp_path: Path) -> None:
    engine = {
        "schema_version": "1.0",
        "source_url": "https://status.search.google.com/incidents.json",
        "updates": [
            {"id": "A", "name": "engine-A", "begin": "2026-01-01T00:00:00Z",
             "end": "2026-01-10T00:00:00Z", "service_name": "Ranking"},
            {"id": "B", "name": "engine-B", "begin": "2026-02-01T00:00:00Z",
             "end": "2026-02-10T00:00:00Z", "service_name": "Ranking"},
        ],
    }
    overlay = {
        "schema_version": "1.0",
        "source_url": "https://status.search.google.com/incidents.json",
        "updates": [
            # id A collides → overlay wins (fresher rollout end).
            {"id": "A", "name": "overlay-A", "begin": "2026-01-01T00:00:00Z",
             "end": "2026-01-12T00:00:00Z", "service_name": "Ranking"},
            # id C is overlay-only → added.
            {"id": "C", "name": "overlay-C", "begin": "2026-03-01T00:00:00Z",
             "end": None, "service_name": "Ranking"},
        ],
    }
    engine_path = tmp_path / "engine.json"
    overlay_path = tmp_path / "overlay.json"
    engine_path.write_text(json.dumps(engine), encoding="utf-8")
    overlay_path.write_text(json.dumps(overlay), encoding="utf-8")

    merged = update_calendar.load_calendar(engine_path, overlay_path)
    by_id = {u["id"]: u for u in merged}
    assert set(by_id) == {"A", "B", "C"}, "union by id failed"
    assert by_id["A"]["name"] == "overlay-A", "overlay did not win on collision"
    assert by_id["B"]["name"] == "engine-B", "engine-only entry dropped"
    assert by_id["C"]["name"] == "overlay-C", "overlay-only entry dropped"


def test_load_calendar_engine_only(tmp_path: Path) -> None:
    engine = {
        "schema_version": "1.0",
        "source_url": "https://status.search.google.com/incidents.json",
        "updates": [
            {"id": "A", "name": "engine-A", "begin": "2026-01-01T00:00:00Z",
             "end": "2026-01-10T00:00:00Z", "service_name": "Ranking"},
        ],
    }
    engine_path = tmp_path / "engine.json"
    engine_path.write_text(json.dumps(engine), encoding="utf-8")
    merged = update_calendar.load_calendar(engine_path)  # no overlay
    assert [u["id"] for u in merged] == ["A"]


# ---------------------------------------------------------------------------
# Test 4 — bundled engine seed validates against the schema
# ---------------------------------------------------------------------------

def test_bundled_calendar_validates_against_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    data = json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft7Validator(schema).iter_errors(data),
                    key=lambda e: list(e.absolute_path))
    assert not errors, (
        "bundled google-update-calendar.json invalid: "
        + "; ".join(f"{list(e.absolute_path)}: {e.message}" for e in errors)
    )
    # The seed must carry the May 2026 core update (web-verified real entry).
    names = {u["name"] for u in data["updates"]}
    assert "May 2026 core update" in names
    # Every seeded entry is a Ranking entry (filter applied at build time).
    assert all(u["service_name"] == "Ranking" for u in data["updates"])


def test_schema_id_http_convention() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["$id"] == "http://platinum-seo-engine/schemas/google-update-calendar"
    assert schema.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# Test 5 — grep sentinel: NO network import in either pure module
# ---------------------------------------------------------------------------

def test_no_network_imports_in_pure_modules() -> None:
    """R-137/orchestration-in-skills: the calendar parse/merge modules are
    pure — network fetch is the skill's job (ScraplingServer MCP). Neither
    module may import requests / urllib / http(.client)."""
    import re as _re
    forbidden = [
        r"^\s*import\s+requests\b",
        r"^\s*from\s+requests\b",
        r"^\s*import\s+urllib\b",
        r"^\s*from\s+urllib\b",
        r"^\s*import\s+http\b",
        r"^\s*from\s+http\b",
    ]
    for src in (UPDATE_CAL_SRC, REFRESH_SRC):
        text = src.read_text(encoding="utf-8")
        for pat in forbidden:
            assert not _re.search(pat, text, _re.MULTILINE), (
                f"{src.name} must not import network libs; matched {pat!r}"
            )


# ---------------------------------------------------------------------------
# Test 6 — refresh.build_calendar + merge round-trip validates vs schema
# ---------------------------------------------------------------------------

def test_build_calendar_round_trip_validates(synthetic_incidents: list[dict]) -> None:
    updates = refresh.parse_incidents(synthetic_incidents)
    cal = refresh.build_calendar(
        updates,
        source_url="https://status.search.google.com/incidents.json",
        retrieved_at="2026-06-10T00:00:00Z",
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = list(Draft7Validator(schema).iter_errors(cal))
    assert not errors, [e.message for e in errors]
    assert cal["schema_version"] == "1.0"
    assert cal["source_url"].startswith("https://")


def test_merge_by_id_incoming_wins() -> None:
    existing = [{"id": "A", "name": "old", "begin": "2026-01-01T00:00:00Z",
                 "end": None, "service_name": "Ranking"}]
    incoming = [{"id": "A", "name": "new", "begin": "2026-01-01T00:00:00Z",
                 "end": "2026-01-15T00:00:00Z", "service_name": "Ranking"},
                {"id": "B", "name": "added", "begin": "2026-02-01T00:00:00Z",
                 "end": None, "service_name": "Ranking"}]
    merged = refresh.merge_by_id(existing, incoming)
    by_id = {u["id"]: u for u in merged}
    assert by_id["A"]["name"] == "new"      # incoming wins
    assert by_id["A"]["end"] == "2026-01-15T00:00:00Z"
    assert by_id["B"]["name"] == "added"
