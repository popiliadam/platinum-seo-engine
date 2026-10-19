#!/usr/bin/env python3
"""gsc_history.py — append-only weekly GSC history per URL × query (O-03).

Only a site-total weekly series existed, and gsc_performance is replaced on
every refresh, so it was impossible to say which pages a core / spam update
hit. This keeps one line per (ISO week, page, query) in
``_state/metrics/gsc_url_query_weekly.jsonl``:

* ``weeks_to_pull(ledger, today, back)`` — complete ISO weeks (Mon-Sun, ended
  ``GSC_LAG_DAYS`` ago) not yet in the ledger, newest last; each is ONE
  ``dimensions="query,page"`` pull with ``rowLimit=GSC_ROW_LIMIT`` (D-01).
* ``rows_for_week(iso_week, payload)`` — ledger lines from one answer.
* ``update_impact(ledger, update, weeks=4)`` — per page, clicks/impressions in
  the 4 complete weeks before the update began vs the 4 after it ended:
  biggest losers and gainers (the "which page did the September 2026 spam
  update hit" report).
"""
from __future__ import annotations

import fcntl
import json
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from scripts.util.gsc_window import GSC_LAG_DAYS
from scripts.util.url_normalize import normalize_url

LEDGER_REL = Path("_state") / "metrics" / "gsc_url_query_weekly.jsonl"


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_bounds(label: str) -> tuple[date, date]:
    monday = datetime.strptime(label + "-1", "%G-W%V-%u").date()
    return monday, monday + timedelta(days=6)


def weeks_to_pull(ledger: Iterable[Mapping[str, Any]], *, today: date, back: int = 16) -> list[dict]:
    have = {r.get("iso_week") for r in ledger}
    cutoff = today - timedelta(days=GSC_LAG_DAYS)
    last_sunday = cutoff - timedelta(days=(cutoff.weekday() + 1) % 7)
    out = []
    for i in range(back - 1, -1, -1):
        sunday = last_sunday - timedelta(weeks=i)
        label = iso_week(sunday)
        if label not in have:
            start, end = week_bounds(label)
            out.append({"iso_week": label, "startDate": start.isoformat(), "endDate": end.isoformat()})
    return out


def rows_for_week(label: str, payload: Mapping[str, Any] | None) -> list[dict]:
    out = []
    for r in (payload or {}).get("rows") or []:
        keys = r.get("keys") or []
        if len(keys) < 2:
            continue
        try:
            page = normalize_url(str(keys[1]))
        except ValueError:
            continue
        out.append({"iso_week": label, "page": page, "query": str(keys[0]),
                    "clicks": int(r.get("clicks") or 0), "impressions": int(r.get("impressions") or 0),
                    "position": float(r["position"]) if r.get("position") is not None else None})
    return out


def read_ledger(path: Path) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError:
        return []
    out = []
    for line in lines:
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def append_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode()
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)


def _to_date(value: str) -> date:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def update_impact(ledger: Iterable[Mapping[str, Any]], update: Mapping[str, Any], *,
                  weeks: int = 4, top: int = 20) -> dict:
    """Pages' clicks/impressions in the N weeks before ``begin`` vs N weeks after ``end``."""
    begin, end = _to_date(update["begin"]), _to_date(update.get("end") or update["begin"])
    before_weeks = {iso_week(begin - timedelta(weeks=i + 1)) for i in range(weeks)}
    after_weeks = {iso_week(end + timedelta(weeks=i + 1)) for i in range(weeks)}
    agg: dict[str, dict] = defaultdict(lambda: {"before_clicks": 0, "after_clicks": 0,
                                                "before_impressions": 0, "after_impressions": 0})
    seen = set()
    for r in ledger:
        w = r.get("iso_week")
        side = "before" if w in before_weeks else "after" if w in after_weeks else None
        if side is None:
            continue
        seen.add(side)
        a = agg[r["page"]]
        a[f"{side}_clicks"] += int(r.get("clicks") or 0)
        a[f"{side}_impressions"] += int(r.get("impressions") or 0)
    rows = [{"page": p, **v, "clicks_delta": v["after_clicks"] - v["before_clicks"]} for p, v in agg.items()]
    rows.sort(key=lambda r: r["clicks_delta"])
    complete = seen == {"before", "after"}
    return {"update": update.get("name"), "weeks": weeks, "complete": complete,
            "losers": [r for r in rows if r["clicks_delta"] < 0][:top],
            "gainers": [r for r in reversed(rows) if r["clicks_delta"] > 0][:top]}


__all__ = ("iso_week", "week_bounds", "weeks_to_pull", "rows_for_week", "read_ledger",
           "append_rows", "update_impact", "LEDGER_REL")
