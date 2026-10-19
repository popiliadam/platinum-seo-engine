#!/usr/bin/env python3
"""crawl_log.py — where does Googlebot spend its crawl? (O-14)

Faceted e-commerce sites (lastiksa: 30K products) never measured crawl budget
from server logs. Optional module: parse combined-format access log lines,
keep Googlebot requests, and break them down by URL type — clean pages vs
parameter / facet URLs, plus status codes — to show facet waste.

User-agent strings can be spoofed; the report says the figures are by UA and
recommends reverse-DNS verification before acting on a single IP.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable
from urllib.parse import parse_qs, urlparse

_LINE = re.compile(r'"(?:GET|HEAD|POST) (?P<path>\S+) HTTP/[\d.]+" (?P<status>\d{3}) \S+ "[^"]*" "(?P<ua>[^"]*)"')
FACET_PARAMS = frozenset({"filter", "sort", "order", "orderby", "color", "renk", "beden", "size",
                          "marka", "brand", "price", "fiyat", "page", "sayfa", "q", "s"})


def url_type(path: str) -> str:
    u = urlparse(path)
    if not u.query:
        return "static_asset" if re.search(r"\.(css|js|png|jpe?g|webp|avif|svg|gif|ico|woff2?)$", u.path, re.I) else "clean"
    keys = {k.lower() for k in parse_qs(u.query, keep_blank_values=True)}
    if keys & {"page", "sayfa"} and len(keys) == 1:
        return "pagination"
    return "facet_or_filter" if keys & FACET_PARAMS else "other_parameter"


def googlebot_breakdown(lines: Iterable[str]) -> dict:
    types: Counter = Counter()
    statuses: Counter = Counter()
    total = 0
    for line in lines:
        m = _LINE.search(line)
        if not m or "googlebot" not in m.group("ua").lower():
            continue
        total += 1
        types[url_type(m.group("path"))] += 1
        statuses[m.group("status")] += 1
    waste = types["facet_or_filter"] + types["other_parameter"]
    return {"googlebot_requests": total, "by_type": dict(types), "by_status": dict(statuses),
            "parameter_share": round(waste / total, 3) if total else None,
            "note": "counted by user-agent; verify Googlebot by reverse DNS before blocking anything"}


__all__ = ("url_type", "googlebot_breakdown")
