#!/usr/bin/env python3
"""gsc_window.py — one shared definition of GSC date windows and row limits.

D-01: the GSC MCP tools return 1,000 rows unless ``rowLimit`` is passed (max
25,000) and they cannot page (no ``startRow``). Every pull passes
``rowLimit=GSC_ROW_LIMIT``; a result whose row count sits exactly on a known
cap is flagged truncated — the caller narrows the request (shorter window, a
page/query filter) instead of treating the first N rows as the whole site.

D-04: windows used to be ``[today-N, today]`` and ``[today-2N, today-N]``: the
boundary day sat in both, and the last 2-3 days (not yet in GSC) dragged every
comparison down by ~7-10 %. Windows now end ``GSC_LAG_DAYS`` before today and
never overlap.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

GSC_ROW_LIMIT = 25000
KNOWN_ROW_CAPS = (1000, 25000)
GSC_LAG_DAYS = 3


@dataclass(frozen=True)
class Window:
    start: date
    end: date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def as_params(self) -> dict:
        return {"startDate": self.start.isoformat(), "endDate": self.end.isoformat()}


def recent_window(today: date, days: int, *, lag: int = GSC_LAG_DAYS) -> Window:
    """The latest ``days`` complete days of GSC data (ends ``lag`` days ago)."""
    if days < 1:
        raise ValueError("days must be >= 1")
    end = today - timedelta(days=lag)
    return Window(end - timedelta(days=days - 1), end)


def comparison_windows(today: date, days: int, *, lag: int = GSC_LAG_DAYS) -> tuple[Window, Window]:
    """(recent, previous): equal length, adjacent, never overlapping."""
    recent = recent_window(today, days, lag=lag)
    prev_end = recent.start - timedelta(days=1)
    return recent, Window(prev_end - timedelta(days=days - 1), prev_end)


def row_count(payload) -> int:
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    return len(rows) if isinstance(rows, list) else 0


def truncation(payload, *, row_limit: int = GSC_ROW_LIMIT) -> dict:
    """``{"rows", "truncated", "warning"}`` for one GSC response."""
    n = row_count(payload)
    truncated = n >= row_limit or n in KNOWN_ROW_CAPS
    warning = None
    if truncated:
        warning = (f"GSC returned exactly {n} rows — the response is cut at the row "
                   "limit; narrow the window or add a page/query filter (D-01)")
    return {"rows": n, "truncated": truncated, "warning": warning}


__all__ = ("GSC_ROW_LIMIT", "KNOWN_ROW_CAPS", "GSC_LAG_DAYS", "Window", "recent_window",
           "comparison_windows", "row_count", "truncation")
