#!/usr/bin/env python3
"""post_publish_check.py — is a freshly published URL live and in the sitemap? (O-24)

Pages published from outside the CMS (scripts, REST deploys) may never reach
the sitemap, and nothing noticed. After every publish:

* the URL answers 200;
* the URL is listed in the sitemap (index files are followed one level);
* its ``<lastmod>`` is on or after the publish date.

Pure checks + small sitemap parser; ``fetch`` is injected (the indexing helper
already has one). Issues feed the /pseo-index report as warnings.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Callable, Mapping

from scripts.util.url_normalize import normalize_url

_LOC = re.compile(r"<url>\s*(.*?)\s*</url>", re.S | re.I)
_SITEMAP = re.compile(r"<sitemap>\s*(.*?)\s*</sitemap>", re.S | re.I)
_TAG = lambda name: re.compile(rf"<{name}>\s*([^<]+?)\s*</{name}>", re.I)  # noqa: E731
_LOC_TAG, _LASTMOD_TAG = _TAG("loc"), _TAG("lastmod")

Fetch = Callable[[str], tuple[int, str, dict]]


def _n(url: str) -> str:
    try:
        return normalize_url(url.strip())
    except ValueError:
        return url.strip()


def parse_sitemap(xml: str) -> tuple[dict[str, str | None], list[str]]:
    """({url: lastmod}, [child sitemap urls]) from one sitemap document."""
    entries: dict[str, str | None] = {}
    for block in _LOC.findall(xml or ""):
        loc = _LOC_TAG.search(block)
        if loc:
            mod = _LASTMOD_TAG.search(block)
            entries[_n(loc.group(1))] = mod.group(1)[:10] if mod else None
    children = [m.group(1).strip() for b in _SITEMAP.findall(xml or "") if (m := _LOC_TAG.search(b))]
    return entries, children


def load_sitemap(root_url: str, fetch: Fetch, *, max_children: int = 50) -> dict[str, str | None]:
    status, xml, _ = fetch(root_url)
    if status != 200:
        return {}
    entries, children = parse_sitemap(xml)
    for child in children[:max_children]:
        st, body, _ = fetch(child)
        if st == 200:
            entries.update(parse_sitemap(body)[0])
    return entries


def check(url: str, status: int, sitemap: Mapping[str, str | None], *, published_on: date) -> list[str]:
    issues = []
    if status != 200:
        issues.append(f"HTTP {status} — not live")
    key = _n(url)
    if key not in sitemap:
        issues.append("not in the sitemap — add it or regenerate the sitemap")
    else:
        mod = sitemap[key]
        if mod is None:
            issues.append("sitemap entry has no <lastmod>")
        elif mod < published_on.isoformat():
            issues.append(f"sitemap <lastmod> {mod} is older than the publish date {published_on}")
    return issues


__all__ = ("parse_sitemap", "load_sitemap", "check")
