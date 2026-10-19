#!/usr/bin/env python3
"""commercial_priority.py — rank work by business value, not traffic (O-17).

Tasks were ordered by opportunity / traffic, so informational queries that sell
nothing rose to the top and nobody looked at which page TYPE wins the SERP.

* ``page_type(url)``  — category / product / service / blog / home / other from
  the URL path (TR + EN path words).
* ``serp_intent(top_urls)`` — commercial when at least 2 of the top 3 organic
  results are category, product or service pages; informational when 2+ are
  blog; else mixed.
* ``priority_score`` = intent weight × winnability × value, where winnability
  falls with the current position (1.0 at #1, 0.5 at #11) and value is the CPC
  advertisers pay (a value signal, not a difficulty signal; missing CPC = 0.1).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

_TYPE_WORDS = {
    "blog": ("blog", "yazi", "yazilar", "haber", "rehber", "makale", "news", "guide", "article"),
    "product": ("urun", "urunler", "product", "products", "p"),
    "category": ("kategori", "category", "product-category", "collections", "shop", "magaza"),
    "service": ("hizmet", "hizmetler", "hizmetlerimiz", "service", "services", "tedavi", "tedaviler"),
}
INTENT_WEIGHT = {"commercial": 1.0, "mixed": 0.6, "informational": 0.3}
DEFAULT_CPC = 0.1


def page_type(url: str) -> str:
    path = urlparse(str(url or "")).path.strip("/").lower()
    if not path:
        return "home"
    parts = path.split("/")
    for kind, words in _TYPE_WORDS.items():
        if any(p in words for p in parts[:-1] or parts[:1]):
            return kind
    if path.endswith(".html") and len(parts) == 1:
        return "product"
    return "other"


def serp_intent(top_urls: Sequence[str]) -> str:
    kinds = [page_type(u) for u in list(top_urls)[:3]]
    if sum(k in ("category", "product", "service") for k in kinds) >= 2:
        return "commercial"
    if sum(k == "blog" for k in kinds) >= 2:
        return "informational"
    return "mixed"


def winnability(position: float | None) -> float:
    if position is None or position <= 0:
        return 0.3  # not ranking yet
    return round(1.0 / (1.0 + (max(position, 1.0) - 1.0) / 10.0), 3)


def priority_score(intent: str, position: float | None, cpc: float | None) -> float:
    value = float(cpc) if cpc not in (None, "") and float(cpc) > 0 else DEFAULT_CPC
    return round(INTENT_WEIGHT.get(intent, 0.6) * winnability(position) * value, 4)


def rank(rows: Iterable[Mapping[str, Any]]) -> list[dict]:
    """rows: {keyword, position, cpc, top_urls: [...]} → same + intent, serp_types, score, sorted."""
    out = []
    for r in rows:
        tops = list(r.get("top_urls") or [])
        intent = serp_intent(tops)
        out.append({**dict(r), "intent": intent, "serp_types": [page_type(u) for u in tops[:3]],
                    "score": priority_score(intent, r.get("position"), r.get("cpc"))})
    out.sort(key=lambda x: -x["score"])
    return out


__all__ = ("page_type", "serp_intent", "winnability", "priority_score", "rank")
