#!/usr/bin/env python3
"""
update_calendar.py — pure reader for the Google Search core-update calendar.

Loads the engine seed (google-update-calendar.json at repo root) optionally
unioned with a workspace overlay (shared/cache/google-update-calendar.json,
written at runtime by the report skills), and answers ONE measurement question:
does a given report window overlap a Google *Ranking* update (core / spam /
ranking-affecting), including a settling buffer after rollout completes?

This is the read side of R-137 (core-update overlap annotation). The WRITE side
(fetching status.search.google.com/incidents.json and refreshing the file) is
deliberately elsewhere: the network fetch happens in the report SKILL via the
ScraplingServer MCP, and the parse/merge happens in
scripts/maintenance/refresh_update_calendar.py. This module therefore imports
NO network library (grep-sentinel enforced) — it is pure parse + date math.

Pure-function discipline:
  - No state mutation, no file writes.
  - All dates are arguments (rules/time-discipline.md — never date.today()).
  - Deterministic: same inputs -> same output.

Refs: docs/superpowers/plans/amo/2026-06-10-gap-specs-measurement-ai.md (GAP-M1
D1), rules/measurement-discipline.md (R-137), schemas/google-update-calendar.schema.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Date helpers (Python 3.10-safe: fromisoformat there rejects a 'Z' suffix)
# ---------------------------------------------------------------------------

def _parse_iso(value: str) -> datetime:
    """Parse a UTC ISO-8601 timestamp into an aware UTC datetime.

    Tolerant of the two on-disk shapes ('...Z' seed/overlay and '...+00:00'
    dashboard) plus naive strings (assumed UTC). Raises ValueError on garbage.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"not an ISO timestamp: {value!r}")
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_bound(value: str) -> datetime:
    """Parse a period bound. Accepts a bare date ('YYYY-MM-DD' → 00:00 UTC) or
    a full ISO timestamp."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"not a date bound: {value!r}")
    s = value.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return _parse_iso(s)


# ---------------------------------------------------------------------------
# Calendar loading (engine seed ∪ workspace overlay; overlay wins by id)
# ---------------------------------------------------------------------------

def _read_updates(path: Path | str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    updates = data.get("updates")
    if not isinstance(updates, list):
        raise ValueError(f"{path}: 'updates' must be a list")
    return updates


def load_calendar(
    engine_path: Path | str,
    overlay_path: Path | str | None = None,
) -> list[dict]:
    """Union the engine seed with an optional workspace overlay, keyed by `id`.

    Overlay entries WIN on id collision (they are freshly fetched at runtime and
    carry e.g. a now-known rollout `end`). Engine-only and overlay-only entries
    are both kept. Output is sorted newest-first by `begin` (ties broken by id)
    for deterministic downstream rendering.
    """
    merged: dict[str, dict] = {}
    for u in _read_updates(engine_path):
        uid = u.get("id")
        if uid:
            merged[uid] = u
    if overlay_path is not None and Path(overlay_path).exists():
        for u in _read_updates(overlay_path):
            uid = u.get("id")
            if uid:
                merged[uid] = u  # overlay wins
    return sorted(
        merged.values(),
        key=lambda u: (u.get("begin", ""), u.get("id", "")),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Overlap detection (R-137)
# ---------------------------------------------------------------------------

def overlaps(
    period_start: str,
    period_end: str,
    updates: Iterable[dict],
    settle_buffer_days: int = 7,
) -> list[dict]:
    """Return Ranking updates whose rollout overlaps [period_start, period_end],
    or whose rollout completed within `settle_buffer_days` before period_start.

    Each hit: {id, name, begin, end, overlap_days, phase} where
      phase == "rolling"            → update.end is null (still rolling out),
      phase == "rollout_in_period"  → the active rollout window overlaps the period,
      phase == "settling"           → rollout completed just before the period
                                       (within the settle buffer); overlap_days == 0.

    Filters to service_name == "Ranking" (R-137): a stray Serving/Indexing entry
    in the calendar is ignored here even if it slipped past the build filter.
    """
    ps = _parse_bound(period_start)
    pe = _parse_bound(period_end)
    buffer = timedelta(days=int(settle_buffer_days))
    hits: list[dict] = []

    for u in updates:
        if u.get("service_name") and u["service_name"] != "Ranking":
            continue
        try:
            begin = _parse_iso(u["begin"])
        except (KeyError, ValueError):
            continue  # malformed begin → skip (never fabricate a date)

        raw_end = u.get("end")
        end = None
        if raw_end is not None:
            try:
                end = _parse_iso(raw_end)
            except ValueError:
                end = None

        if end is None:
            # Rolling: overlaps the period iff it started on/before period end.
            if begin <= pe:
                lo = max(begin, ps)
                overlap_days = max(0, (pe - lo).days)
                hits.append(_hit(u, begin, raw_end, overlap_days, "rolling"))
            continue

        # Finished rollout: compute the [begin,end] ∩ [period_start,period_end].
        lo = max(begin, ps)
        hi = min(end, pe)
        if hi > lo:
            hits.append(_hit(u, begin, raw_end, (hi - lo).days, "rollout_in_period"))
        elif end < ps and (ps - end) <= buffer:
            hits.append(_hit(u, begin, raw_end, 0, "settling"))
        # else: no overlap and outside settle buffer → not a hit.

    return hits


def _hit(u: dict, begin: datetime, raw_end, overlap_days: int, phase: str) -> dict:
    return {
        "id": u.get("id"),
        "name": u.get("name"),
        "begin": u.get("begin"),
        "end": raw_end,
        "overlap_days": int(overlap_days),
        "phase": phase,
    }


__all__ = ("load_calendar", "overlaps")
