#!/usr/bin/env python3
"""brief_signals.py — small content-planning signals (O-20, O-15, O-08).

* ``secondary_queries(ranked_rows, top_url)`` (O-20) — the queries the current
  #1 URL also ranks top-5 for (DFS ranked_keywords): Google treats them as the
  same page, so one page should target them together. Added to the brief.
* ``preferred_sources_task(profiles, has_blog)`` (O-15) — Google's "preferred
  sources" now covers every language, AI Overviews / AI Mode and has its own
  button (2026-08-20): a blog/publisher project gets a recommendation task.
* ``indexnow_key_live(host, key, fetch)`` (O-08) — IndexNow is only accepted
  when https://host/<key>.txt serves the key; check before enabling pings.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Sequence

from scripts.util.url_normalize import normalize_url


def _n(url: Any) -> str:
    try:
        return normalize_url(str(url))
    except ValueError:
        return str(url or "")


def secondary_queries(ranked_rows: Iterable[Mapping[str, Any]], top_url: str, *,
                      primary: str | None = None, max_rank: int = 5, limit: int = 15) -> list[dict]:
    """ranked_rows: {keyword, url, rank_absolute|rank_group, search_volume}."""
    target = _n(top_url)
    out = []
    for r in ranked_rows:
        rank = r.get("rank_absolute") or r.get("rank_group")
        if _n(r.get("url")) != target or rank is None or rank > max_rank:
            continue
        if primary and str(r.get("keyword", "")).strip().lower() == primary.strip().lower():
            continue
        out.append({"keyword": r.get("keyword"), "rank": rank, "search_volume": r.get("search_volume")})
    out.sort(key=lambda x: (-(x["search_volume"] or 0), x["rank"]))
    return out[:limit]


def preferred_sources_task(profiles: Sequence[str], *, has_blog: bool) -> dict | None:
    if not has_blog and not any(p in ("publisher", "media", "blog") for p in profiles):
        return None
    return {"task": "Preferred sources: add Google's 'preferred source' button/link on the blog "
                    "and ask returning readers to pick the site (covers AI Overviews / AI Mode)",
            "primary_source": "manual", "why_now": "feature extended to all languages + AI surfaces in 2026"}


def indexnow_key_live(host: str, key: str, fetch: Callable[[str], tuple[int, str, dict]]) -> tuple[bool, str]:
    url = f"https://{host.strip('/')}/{key}.txt"
    status, body, _ = fetch(url)
    if status != 200:
        return False, f"{url} answers HTTP {status}"
    if body.strip() != key:
        return False, f"{url} does not contain the key"
    return True, "key file live"


__all__ = ("secondary_queries", "preferred_sources_task", "indexnow_key_live")
