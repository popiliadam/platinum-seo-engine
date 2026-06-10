#!/usr/bin/env python3
"""
refresh_update_calendar.py — pure parse/merge of the Google Search Status
Dashboard incidents feed into the engine's update calendar.

Input: a raw `incidents.json` (a JSON array exactly as served by
https://status.search.google.com/incidents.json). This script does NOT fetch it
— the fetch is the report SKILL's job (ScraplingServer MCP, free + read-only).
Keeping the network out of here is deliberate (orchestration-in-skills rule):
this module is pure parse/merge so it is unit-testable and deterministic, and
imports NO network library (grep-sentinel enforced by
tests/reporting/test_update_calendar.py).

What it does:
  1. parse_incidents()  — filter to service_name=="Ranking", map dashboard
     fields (external_desc→name, begin/end normalized to UTC 'Z') to the
     calendar-update shape. end=null (still-rolling) is preserved, never faked.
  2. merge_by_id()      — union an existing calendar with the parsed updates;
     INCOMING (freshly parsed) wins on id collision (picks up a now-known end).
  3. filter_recent()    — keep the trailing `months` window (default 24).
  4. build_calendar()   — assemble the schema-shaped file dict.
  5. CLI validates the result against schemas/google-update-calendar.schema.json
     and DURURs (exit 1) on mismatch (dashboard-shape drift guard).

Who runs it:
  - engine release: maintainer downloads incidents.json, runs with --write to
    refresh the bundled google-update-calendar.json seed.
  - runtime: the monitoring/monthly report skill drops the fetched feed to
    inbox/calendar/, then runs with --write-overlay {workspace}/shared/cache/...

Refs: GAP-M1 D1 (measurement spec), rules/measurement-discipline.md (R-137),
rules/time-discipline.md (UTC 'Z' storage), schemas/google-update-calendar.schema.json.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schemas" / "google-update-calendar.schema.json"
_DEFAULT_SOURCE_URL = "https://status.search.google.com/incidents.json"

RANKING_SERVICE = "Ranking"
SOURCE_TAG = "google_status_dashboard"


# ---------------------------------------------------------------------------
# Timestamp normalization (UTC 'Z'; 3.10-safe)
# ---------------------------------------------------------------------------

def _normalize_ts(value) -> str | None:
    """Normalize a dashboard timestamp to UTC ISO-8601 with a 'Z' suffix.

    Fast paths the two real shapes ('...+00:00' dashboard, '...Z' already
    normalized). null stays null (rolling update — never fabricated). Other
    offsets are converted to UTC.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        return s
    if s.endswith("+00:00"):
        return s[:-6] + "Z"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _months_before(dt: datetime, months: int) -> datetime:
    """Subtract `months` calendar months, clamping the day to month length."""
    total = (dt.year * 12 + (dt.month - 1)) - int(months)
    year, month0 = divmod(total, 12)
    month = month0 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Pure parse / merge / filter / build
# ---------------------------------------------------------------------------

def parse_incidents(
    incidents: Iterable[dict],
    *,
    source_filter: str = RANKING_SERVICE,
    source_tag: str = SOURCE_TAG,
) -> list[dict]:
    """Filter dashboard incidents to the ranking service and map to the
    calendar-update shape. Entries missing id/external_desc/begin are skipped
    (no fabricated rows)."""
    out: list[dict] = []
    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        if inc.get("service_name") != source_filter:
            continue
        uid = inc.get("id")
        name = inc.get("external_desc")
        begin = _normalize_ts(inc.get("begin"))
        if not (uid and name and begin):
            continue
        rec: dict = {
            "id": uid,
            "name": name,
            "begin": begin,
            "end": _normalize_ts(inc.get("end")),
            "service_name": inc.get("service_name"),
            "source": source_tag,
        }
        sev = inc.get("severity")
        if sev is not None:
            rec["severity"] = sev
        out.append(rec)
    return out


def merge_by_id(existing: Iterable[dict], incoming: Iterable[dict]) -> list[dict]:
    """Union two update lists keyed by id; INCOMING wins on collision. Sorted
    newest-first by begin (ties by id)."""
    merged: dict[str, dict] = {}
    for u in existing:
        if u.get("id"):
            merged[u["id"]] = u
    for u in incoming:
        if u.get("id"):
            merged[u["id"]] = u
    return sorted(
        merged.values(),
        key=lambda u: (u.get("begin", ""), u.get("id", "")),
        reverse=True,
    )


def filter_recent(updates: Iterable[dict], *, now_iso: str, months: int = 24) -> list[dict]:
    """Keep only updates whose begin is within the trailing `months` window."""
    now = _normalize_ts(now_iso)
    cutoff = _months_before(_parse(now), months)
    kept: list[dict] = []
    for u in updates:
        try:
            if _parse(u["begin"]) >= cutoff:
                kept.append(u)
        except (KeyError, ValueError):
            continue
    return kept


def _parse(value: str) -> datetime:
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def build_calendar(
    updates: Iterable[dict],
    *,
    source_url: str,
    retrieved_at: str,
) -> dict:
    """Assemble the schema-shaped calendar file dict (newest-first)."""
    ordered = sorted(
        updates,
        key=lambda u: (u.get("begin", ""), u.get("id", "")),
        reverse=True,
    )
    return {
        "schema_version": "1.0",
        "retrieved_at": _normalize_ts(retrieved_at),
        "source_url": source_url,
        "updates": ordered,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _validate(calendar_dict: dict) -> list[str]:
    """Validate against the bundled schema; return a list of error strings."""
    from jsonschema import Draft7Validator  # lazy: keep import-time light
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    return [
        f"{list(e.absolute_path)}: {e.message}"
        for e in Draft7Validator(schema).iter_errors(calendar_dict)
    ]


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="refresh_update_calendar.py",
        description="Parse status.search.google.com incidents.json into the "
                    "engine update calendar (pure; no network).",
    )
    p.add_argument("--incidents", required=True,
                   help="Path to a raw incidents.json (JSON array).")
    p.add_argument("--calendar", default=str(_REPO_ROOT / "google-update-calendar.json"),
                   help="Existing calendar to merge into (and default --write target).")
    p.add_argument("--write", action="store_true",
                   help="Write the merged result back to --calendar.")
    p.add_argument("--write-overlay", default=None,
                   help="Write the merged result to this overlay path instead.")
    p.add_argument("--source-url", default=_DEFAULT_SOURCE_URL)
    p.add_argument("--retrieved-at", default=None,
                   help="UTC ISO-8601 retrieval timestamp (default: now).")
    p.add_argument("--months", type=int, default=24,
                   help="Trailing window of months to retain (default 24).")
    return p.parse_args(list(argv))


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    incidents_path = Path(args.incidents)
    if not incidents_path.exists():
        print(f"incidents file not found: {incidents_path}", file=sys.stderr)
        return 2
    incidents = json.loads(incidents_path.read_text(encoding="utf-8"))
    if not isinstance(incidents, list):
        print("incidents.json must be a JSON array", file=sys.stderr)
        return 2

    parsed = parse_incidents(incidents)

    existing: list[dict] = []
    cal_path = Path(args.calendar)
    if cal_path.exists():
        try:
            existing = json.loads(cal_path.read_text(encoding="utf-8")).get("updates", [])
        except (OSError, json.JSONDecodeError):
            existing = []

    retrieved_at = args.retrieved_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    merged = merge_by_id(existing, parsed)
    merged = filter_recent(merged, now_iso=retrieved_at, months=args.months)
    cal = build_calendar(merged, source_url=args.source_url, retrieved_at=retrieved_at)

    errors = _validate(cal)
    if errors:
        print("DURUR: built calendar fails schema validation (dashboard shape "
              "drift?):\n  " + "\n  ".join(errors), file=sys.stderr)
        return 1

    blob = json.dumps(cal, ensure_ascii=False, indent=2) + "\n"
    if args.write_overlay:
        overlay = Path(args.write_overlay)
        overlay.parent.mkdir(parents=True, exist_ok=True)
        overlay.write_text(blob, encoding="utf-8")
        print(f"overlay written: {overlay.resolve()} ({len(cal['updates'])} updates)")
    elif args.write:
        cal_path.write_text(blob, encoding="utf-8")
        print(f"calendar written: {cal_path.resolve()} ({len(cal['updates'])} updates)")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "parse_incidents",
    "merge_by_id",
    "filter_recent",
    "build_calendar",
    "main",
)
