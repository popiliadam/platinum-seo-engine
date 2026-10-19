#!/usr/bin/env python3
"""index_rotation.py — keep the index status of priority URLs fresh (O-06).

URL Inspection was ad hoc (largest batch 43 URLs; sites up to 1,767 URLs) and
verify-indexing was wip. The URL Inspection API is the legitimate answer to
"is it indexed?" (not the Indexing API). This picks, within the daily quota,
which URLs to inspect today and turns the results into work:

* priority  — new content > money pages (category / product / service) >
  recently changed (DONE tasks in 30 days) > everything else;
* due       — never inspected, or last inspected more than ``STALE_DAYS`` ago;
* ledger    — ``_state/metrics/index_inspection.jsonl`` (append-only), one line
  per inspection with ``index_inspection.classify`` status;
* clusters  — URLs whose latest status is ``crawled_not_indexed`` or
  ``not_indexed`` grouped by first path segment → one task per cluster.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from scripts.discovery.commercial_priority import page_type
from scripts.discovery.index_inspection import URL_INSPECTION_DAILY_QUOTA, classify

STALE_DAYS = 14
RANK = {"new": 0, "money": 1, "changed": 2, "other": 3}


def _d(value: Any) -> date | None:
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def latest(ledger: Iterable[Mapping[str, Any]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in ledger:
        cur = out.get(r["url"])
        if cur is None or str(r.get("inspected_on")) >= str(cur.get("inspected_on")):
            out[r["url"]] = dict(r)
    return out


def pick(urls: Sequence[Mapping[str, Any]], ledger: Iterable[Mapping[str, Any]], *,
         today: date, quota: int = URL_INSPECTION_DAILY_QUOTA) -> list[dict]:
    """urls: {url, kind?: new|changed} → today's inspection list, highest priority first."""
    last = latest(ledger)
    due = []
    for u in urls:
        url = u["url"]
        seen = _d(last.get(url, {}).get("inspected_on"))
        if seen is not None and (today - seen).days <= STALE_DAYS:
            continue
        kind = u.get("kind") or ("money" if page_type(url) in ("category", "product", "service") else "other")
        due.append({"url": url, "kind": kind, "last_inspected": seen.isoformat() if seen else None})
    due.sort(key=lambda d: (RANK.get(d["kind"], 3), d["last_inspected"] or "", d["url"]))
    return due[:max(0, quota)]


def ledger_row(url: str, raw: Mapping[str, Any], *, today: date) -> dict:
    res = classify(raw)
    return {"url": url, "inspected_on": today.isoformat(), "status": res.status,
            "coverage_state": res.coverage_state, "reason": res.reason}


def freshness(urls: Sequence[str], ledger: Iterable[Mapping[str, Any]], *, today: date) -> dict:
    """Share of priority URLs whose status is <= STALE_DAYS old (goal: all)."""
    last = latest(ledger)
    fresh = sum(1 for u in urls if (d := _d(last.get(u, {}).get("inspected_on"))) and (today - d).days <= STALE_DAYS)
    return {"urls": len(urls), "fresh": fresh, "share": round(fresh / len(urls), 3) if urls else None}


def not_indexed_clusters(ledger: Iterable[Mapping[str, Any]]) -> list[dict]:
    groups: dict[str, list[str]] = defaultdict(list)
    for url, r in latest(ledger).items():
        if r.get("status") in ("crawled_not_indexed", "not_indexed"):
            seg = urlparse(url).path.strip("/").split("/")[0] or "/"
            groups[f"{r['status']}:{seg}"].append(url)
    out = [{"cluster": k, "status": k.split(":", 1)[0], "path_segment": k.split(":", 1)[1],
            "urls": sorted(v), "count": len(v)} for k, v in groups.items()]
    out.sort(key=lambda c: -c["count"])
    return out


__all__ = ("pick", "ledger_row", "freshness", "not_indexed_clusters", "STALE_DAYS")
