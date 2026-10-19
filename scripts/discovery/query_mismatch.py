#!/usr/bin/env python3
"""query_mismatch.py — the query Google gives a page vs the one it targets (O-16).

Many pages earn their impressions for a different query than the keyword they
were written for; quick-wins and cannibalization never compared the two.

For every page with a target keyword (new_content_plan / topical_map) and GSC
query×page rows:

* top query = the query with the most impressions for that page;
* mismatch  = Jaccard overlap of the target and top-query words is below 0.5
  (Turkish-folded);
* position 8-15  → ``rewrite``: H1, meta description and the first 100 words
  toward the top query, and check the body really answers it;
* position 1-3 with CTR under ``LOW_CTR`` → ``check_aio``: do NOT touch the
  title — first check whether an AI Overview took the clicks (S-18);
* anything else → ``watch``.
Pure; the skill passes rows and writes the report.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from scripts.util.text_fold import fold_tokens
from scripts.util.url_normalize import normalize_url

OVERLAP_MIN = 0.5
REWRITE_BAND = (8.0, 15.0)
TOP3_MAX = 3.0
LOW_CTR = 0.05


def _norm(url: Any) -> str | None:
    try:
        return normalize_url(str(url)) if url else None
    except ValueError:
        return None


def overlap(target: str, query: str) -> float:
    """Jaccard word overlap (symmetric): 'kombi bakımı nasıl yapılır' vs
    'kombi bakımı fiyat' = 2/5 — different intent, below the 0.5 bar."""
    t, q = fold_tokens(target), fold_tokens(query)
    return len(t & q) / len(t | q) if t | q else 0.0


def top_queries(gsc_rows: Iterable[Mapping[str, Any]]) -> dict[str, dict]:
    """page → {query, impressions, clicks, position} of its highest-impression query."""
    agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"impressions": 0, "clicks": 0, "pos_w": 0.0})
    for r in gsc_rows:
        keys = r.get("keys") or []
        if len(keys) < 2:
            continue
        query, page = str(keys[0]), _norm(keys[1])
        if not page:
            continue
        imp = int(r.get("impressions") or 0)
        a = agg[(page, query)]
        a["impressions"] += imp
        a["clicks"] += int(r.get("clicks") or 0)
        a["pos_w"] += float(r.get("position") or 0) * imp
    best: dict[str, dict] = {}
    for (page, query), a in agg.items():
        if a["impressions"] <= 0:
            continue
        cur = best.get(page)
        if cur is None or a["impressions"] > cur["impressions"]:
            best[page] = {"query": query, "impressions": a["impressions"], "clicks": a["clicks"],
                          "position": round(a["pos_w"] / a["impressions"], 1)}
    return best


def find_mismatches(targets: Mapping[str, str], gsc_rows: Iterable[Mapping[str, Any]]) -> list[dict]:
    """Rows: url, target_keyword, top_query, position, ctr, action, suggestion."""
    tops = top_queries(gsc_rows)
    out = []
    for raw_url, target in targets.items():
        url = _norm(raw_url)
        top = tops.get(url) if url else None
        if not top or not target or overlap(target, top["query"]) >= OVERLAP_MIN:
            continue
        pos, ctr = top["position"], top["clicks"] / top["impressions"]
        if REWRITE_BAND[0] <= pos <= REWRITE_BAND[1]:
            action = "rewrite"
            suggestion = (f"H1, meta description ve ilk 100 kelimeyi '{top['query']}' sorgusuna göre "
                          "yeniden yaz; gövdenin bu soruyu gerçekten cevapladığını kontrol et")
        elif pos <= TOP3_MAX and ctr < LOW_CTR:
            action = "check_aio"
            suggestion = "başlığa dokunma — önce bu sorguda AI Overview var mı bak (S-18)"
        else:
            action = "watch"
            suggestion = "izle"
        out.append({"url": url, "target_keyword": target, "top_query": top["query"],
                    "position": pos, "ctr": round(ctr, 4), "impressions": top["impressions"],
                    "action": action, "suggestion": suggestion})
    out.sort(key=lambda r: (r["action"] != "rewrite", -r["impressions"]))
    return out


__all__ = ("overlap", "top_queries", "find_mismatches")
