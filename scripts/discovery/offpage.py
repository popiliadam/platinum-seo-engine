#!/usr/bin/env python3
"""offpage.py — link gap, unlinked mentions, dead-link swaps, PR prospects (O-09, O-22, O-26).

Off-page work had 1 finished task across the portfolio; DFS domain
intersection was used by hand and the backlinks / content_analysis endpoints
never. Pure functions over normalized DFS rows; the skill fetches. Every output
is an OUTREACH CANDIDATE LIST — the engine never sends e-mail, and paid
placements must carry rel="sponsored" (Google link-spam policy).

* ``link_gap(intersections, client_domains)`` — referring domains linking to
  at least ``min_competitors`` competitors but not to the client (O-09).
* ``unlinked_mentions(mentions, domain)`` — pages naming the brand without a
  link to the client domain (O-22).
* ``dead_link_swaps(dead_links, our_pages)`` — pages still linking to an expired
  niche site, matched to our closest page by title words (O-22).
* ``pr_queries(sector, lang)`` — "yazar ol" / "misafir yazı" / "write for us"
  searches for the monthly prospect list (O-26).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from scripts.util.text_fold import fold_tokens


def _host(value: str) -> str:
    s = str(value or "").lower()
    s = s.split("://", 1)[-1].split("/", 1)[0]
    return s.removeprefix("www.")


def link_gap(intersections: Iterable[Mapping[str, Any]], client_domains: Iterable[str], *,
             min_competitors: int = 2) -> list[dict]:
    """intersections: {referring_domain, target} rows (DFS domain_intersection, flattened)."""
    clients = {_host(d) for d in client_domains}
    targets_by_ref: dict[str, set] = defaultdict(set)
    for r in intersections:
        targets_by_ref[_host(r.get("referring_domain"))].add(_host(r.get("target")))
    out = []
    for ref, targets in targets_by_ref.items():
        if not ref or targets & clients:
            continue
        if len(targets) >= min_competitors:
            out.append({"referring_domain": ref, "links_competitors": sorted(targets),
                        "competitor_count": len(targets)})
    out.sort(key=lambda r: (-r["competitor_count"], r["referring_domain"]))
    return out


def unlinked_mentions(mentions: Iterable[Mapping[str, Any]], domain: str) -> list[dict]:
    """mentions: {url, links: [href…]} pages that name the brand (DFS content_analysis)."""
    d = _host(domain)
    out = []
    for m in mentions:
        if _host(m.get("url")) == d:
            continue
        if not any(_host(h) == d or _host(h).endswith("." + d) for h in m.get("links") or []):
            out.append({"url": m.get("url"), "title": m.get("title"), "action": "ask for a link"})
    return out


def dead_link_swaps(dead_links: Iterable[Mapping[str, Any]], our_pages: Mapping[str, str], *,
                    min_overlap: int = 1) -> list[dict]:
    """dead_links: {referring_page, dead_target, anchor/title}; our_pages: {url: title}."""
    ours = [(u, fold_tokens(t)) for u, t in our_pages.items()]
    out = []
    for d in dead_links:
        words = fold_tokens(f"{d.get('anchor') or ''} {d.get('title') or ''}")
        best = max(ours, key=lambda o: len(words & o[1]), default=None)
        if best and len(words & best[1]) >= min_overlap:
            out.append({"referring_page": d.get("referring_page"), "dead_target": d.get("dead_target"),
                        "replacement": best[0], "shared_words": sorted(words & best[1])})
    return out


def pr_queries(sector: str, *, lang: str = "tr") -> list[str]:
    tr = [f"{sector} yazar ol", f"{sector} misafir yazı", f"{sector} \"bize yazın\"",
          f"{sector} uzman görüşü", f"{sector} konuk yazar"]
    en = [f"{sector} \"write for us\"", f"{sector} guest post", f"{sector} \"contribute\""]
    return tr + en if lang == "tr" else en


__all__ = ("link_gap", "unlinked_mentions", "dead_link_swaps", "pr_queries")
