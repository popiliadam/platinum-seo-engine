#!/usr/bin/env python3
"""serp_snapshot.py — one monthly DFS SERP pull, three reports (O-04, O-12, O-21).

The only AI-Overview measurement ran once (2026-08-20); SERP features and
third-party "best X" lists were never tracked. From DFS
``serp/google/organic/live/advanced`` items (``type`` organic / ai_overview /
local_pack / featured_snippet / people_also_ask / …):

* ``snapshot(keyword, items, domain)`` — one row: AIO present, our domain cited
  in the AIO references, who else is cited, which SERP features exist and who
  owns them, our organic rank, and list/guide pages in the top 10 (O-21).
* ``ai_visibility(rows)``   — AIO rate, our citation rate (O-04).
* ``feature_history(snapshots_by_month)`` — per keyword, features gained/lost
  month over month (O-12).
* ``fanout_queries(keyword, city)`` — "en iyi … 2026", "… yorumları",
  "… alternatifi", "… {city}" and English pairs, the queries assistants run
  before answering (O-21). Paid placement / PBN are never suggested.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

LIST_TITLE = re.compile(r"(\ben iyi\b|\bbest\b|\btop\s*\d+|\b\d+\s+(?:en iyi|best)|\brehber|\bguide\b|\blist)",
                        re.IGNORECASE)


def _host(url_or_domain: str) -> str:
    s = str(url_or_domain or "").lower()
    host = urlparse(s).hostname if "://" in s else s.split("/")[0]
    return (host or "").removeprefix("www.")


def _is_ours(candidate: str, domain: str) -> bool:
    h, d = _host(candidate), _host(domain)
    return bool(h) and (h == d or h.endswith("." + d))


def snapshot(keyword: str, items: Sequence[Mapping[str, Any]], domain: str) -> dict:
    features: dict[str, list[str]] = {}
    organic_rank = None
    aio_refs: list[str] = []
    lists = []
    for it in items:
        kind = str(it.get("type") or "")
        if kind == "organic":
            if organic_rank is None and _is_ours(it.get("url") or it.get("domain") or "", domain):
                organic_rank = it.get("rank_group")
            rank = it.get("rank_group") or 99
            if rank <= 10 and LIST_TITLE.search(str(it.get("title") or "")):
                lists.append({"url": it.get("url"), "title": it.get("title"), "rank": rank,
                              "client_listed": None})
            continue
        owners = []
        if kind == "ai_overview":
            refs = it.get("references") or []
            aio_refs = [_host(r.get("domain") or r.get("url") or "") for r in refs]
            owners = aio_refs
        else:
            sub = it.get("items") if isinstance(it.get("items"), list) else [it]
            owners = [_host(s.get("domain") or s.get("url") or "") for s in sub if isinstance(s, dict)]
        features.setdefault(kind, [])
        features[kind] = sorted({o for o in features[kind] + owners if o})
    return {
        "keyword": keyword,
        "aio_present": "ai_overview" in features or bool(aio_refs),
        "aio_cited": any(_is_ours(r, domain) for r in aio_refs),
        "aio_cited_competitors": sorted({r for r in aio_refs if r and not _is_ours(r, domain)}),
        "features": features,
        "organic_rank": organic_rank,
        "list_pages": lists,
    }


def ai_visibility(rows: Sequence[Mapping[str, Any]]) -> dict:
    n = len(rows)
    with_aio = [r for r in rows if r.get("aio_present")]
    cited = [r for r in with_aio if r.get("aio_cited")]
    return {"keywords": n, "aio_rate": round(len(with_aio) / n, 3) if n else None,
            "cited_rate": round(len(cited) / len(with_aio), 3) if with_aio else None,
            "aio_keywords": len(with_aio), "cited_keywords": len(cited)}


def feature_history(by_month: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, list[dict]]:
    """{month: [snapshot rows]} → {keyword: [{month, gained, lost, features}]}."""
    out: dict[str, list[dict]] = {}
    prev: dict[str, set] = {}
    for month in sorted(by_month):
        for r in by_month[month]:
            kw, feats = r["keyword"], set((r.get("features") or {}).keys())
            before = prev.get(kw)
            out.setdefault(kw, []).append({
                "month": month, "features": sorted(feats),
                "gained": sorted(feats - before) if before is not None else [],
                "lost": sorted(before - feats) if before is not None else []})
            prev[kw] = feats
    return out


def fanout_queries(keyword: str, *, city: str | None = None, year: int = 2026) -> list[str]:
    q = [f"en iyi {keyword} {year}", f"{keyword} yorumları", f"{keyword} alternatifi",
         f"best {keyword} {year}", f"{keyword} reviews"]
    if city:
        q += [f"{keyword} {city}", f"en iyi {keyword} {city}"]
    return q


def mark_client_listed(snap: Mapping[str, Any], listed_urls: Iterable[str]) -> dict:
    """After fetching each list page: client_listed True/False per page (outreach list)."""
    listed = set(listed_urls)
    pages = [{**p, "client_listed": p.get("url") in listed} for p in snap.get("list_pages", [])]
    return {**snap, "list_pages": pages}


__all__ = ("snapshot", "ai_visibility", "feature_history", "fanout_queries", "mark_client_listed")
