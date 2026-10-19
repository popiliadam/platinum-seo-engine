#!/usr/bin/env python3
"""local_seo.py — rank grid, landing-page checks, service × city planner (O-10, O-23, O-25).

* ``grid_points(lat, lng, size, step_km)`` — a size×size grid around the
  business for DFS maps checks (O-10).
* ``top3_share(grid_ranks)`` — share of grid points where we rank 1-3, and our
  ratio to the leader (O-23 "top-3%").
* ``landing_checks(html, category, city, nap)`` — the 7 checks for the page the
  Business Profile links to: category + city in title and H1, a Google Maps
  embed, secondary categories as H2, a reviews block, NAP identical to the
  profile, LocalBusiness JSON-LD (O-23).
* ``service_city_matrix(services, places, metrics, cap)`` — candidate
  "service + place" pages ranked by commercial value with a per-project cap
  (dozens, not hundreds); every chosen page needs 3 combination-specific
  elements (local price, case, photo, review) per R-146 — never a doorway (O-25).
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

from scripts.discovery.nap_consistency import compare_nap
from scripts.util.text_fold import fold_key

UNIQUE_ELEMENTS_REQUIRED = 3
MATRIX_CAP_DEFAULT = 30


def grid_points(lat: float, lng: float, *, size: int = 5, step_km: float = 1.0) -> list[tuple[float, float]]:
    half = (size - 1) / 2
    dlat = step_km / 111.0
    dlng = step_km / (111.0 * math.cos(math.radians(lat)) or 1e-9)
    return [(round(lat + (i - half) * dlat, 6), round(lng + (j - half) * dlng, 6))
            for i in range(size) for j in range(size)]


def top3_share(grid_ranks: Sequence[Mapping[str, Any]]) -> dict:
    """grid_ranks: {point, ours: rank|None, leader: rank of the best competitor}."""
    n = len(grid_ranks)
    ours = sum(1 for g in grid_ranks if g.get("ours") and g["ours"] <= 3)
    leader = sum(1 for g in grid_ranks if g.get("leader") and g["leader"] <= 3)
    return {"points": n, "top3_share": round(ours / n, 3) if n else None,
            "leader_top3_share": round(leader / n, 3) if n else None,
            "ratio_to_leader": round(ours / leader, 3) if leader else None}


def _texts(pattern: str, html: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", m).strip() for m in re.findall(pattern, html or "", re.S | re.I)]


def landing_checks(html: str, *, category: str, city: str, secondary_categories: Sequence[str],
                   nap: Mapping[str, Any]) -> dict[str, bool]:
    title = " ".join(_texts(r"<title[^>]*>(.*?)</title>", html))
    h1 = " ".join(_texts(r"<h1[^>]*>(.*?)</h1>", html))
    h2 = [fold_key(t) for t in _texts(r"<h2[^>]*>(.*?)</h2>", html)]
    has = lambda text, word: fold_key(word) in fold_key(text)  # noqa: E731
    text = re.sub(r"<[^>]+>", " ", html or "")
    phone = re.search(r"tel:([+\d][\d\s()-]{6,})", html or "")
    observed = {"business_name": nap.get("business_name"), "phone": phone.group(1) if phone else None,
                "address": nap.get("address") if fold_key(str(nap.get("address", ""))[:12]) in fold_key(text) else None,
                "source": "landing_page"}
    return {
        "title_has_category_and_city": has(title, category) and has(title, city),
        "h1_has_category_and_city": has(h1, category) and has(h1, city),
        "google_maps_embed": bool(re.search(r"google\.[a-z.]+/maps|maps\.google\.", html or "", re.I)),
        "secondary_categories_as_h2": all(any(fold_key(s) in h for h in h2) for s in secondary_categories),
        "reviews_block": bool(re.search(r"(yorum|review|değerlendirme)", text, re.I)),
        "nap_matches_profile": observed["phone"] is not None and observed["address"] is not None
                               and not compare_nap(dict(nap), observed),
        "local_business_schema": bool(re.search(r'"@type"\s*:\s*"[A-Za-z]*(LocalBusiness|Dentist|'
                                                r'MedicalClinic|HomeAndConstructionBusiness)', html or "")),
    }


def service_city_matrix(services: Sequence[str], places: Sequence[str],
                        metrics: Mapping[str, Mapping[str, Any]], *,
                        cap: int = MATRIX_CAP_DEFAULT, min_volume: int = 10) -> dict:
    """metrics: {"<service> <place>": {volume, cpc}} from DFS. Returns chosen + skipped."""
    cands = []
    for s in services:
        for p in places:
            kw = f"{s} {p}"
            m = metrics.get(kw) or {}
            vol, cpc = m.get("volume"), m.get("cpc")
            if vol is None or vol < min_volume:
                continue
            cands.append({"keyword": kw, "service": s, "place": p, "volume": vol,
                          "cpc": cpc or 0.0, "value": round(vol * (cpc or 0.0), 2),
                          "unique_elements_required": UNIQUE_ELEMENTS_REQUIRED,
                          "unique_elements_plan": ["yerel fiyat", "o bölgeden vaka", "fotoğraf", "yorum"]})
    cands.sort(key=lambda c: (-c["value"], -c["volume"], c["keyword"]))
    return {"chosen": cands[:cap], "over_cap": len(cands[cap:]), "cap": cap,
            "rule": "R-146: each page needs >= 3 elements unique to its service + place; no doorway pages"}


__all__ = ("grid_points", "top3_share", "landing_checks", "service_city_matrix")
