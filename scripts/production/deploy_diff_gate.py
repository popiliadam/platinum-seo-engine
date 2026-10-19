#!/usr/bin/env python3
"""deploy_diff_gate.py — pre-deploy element diff: live page vs new version (S-24).

A revision (revise-content, content-remediation, a WordPress REST deploy
script) used to publish without looking at what the live page carries, so the
element that gives the page its value — a comparison table, a calculator form,
an embedded video, a real photo, internal links, an H2 section, a JSON-LD type —
could vanish silently. This gate inventories both versions and lists every
element the new version LOST. Additions are fine. A non-empty list stops the
deploy; the report's first line says why. It is a quality gate (fix the new
version and retry), not a consent step.

Pure (stdlib ``html.parser``); CLI:

    python3 scripts/production/deploy_diff_gate.py --live live.html --new article.html --host example.com
    → report on stdout; exit 0 (nothing lost) / 1 (something lost) / 2 (usage / IO)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Inventory:
    tables: int
    forms: int
    iframes: int
    images: int
    internal_links: int
    h2: tuple[str, ...]
    jsonld_types: frozenset[str]


class _Collector(HTMLParser):
    def __init__(self, site_host: str) -> None:
        super().__init__(convert_charrefs=True)
        self.site_host = site_host.lower()
        self.counts = {"table": 0, "form": 0, "iframe": 0, "img": 0}
        self.links: set[str] = set()
        self.h2: list[str] = []
        self.jsonld: list[str] = []
        self._h2_buf: list[str] | None = None
        self._ld_buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.counts:
            self.counts[tag] += 1
        elif tag == "a":
            href = (a.get("href") or "").strip()
            host = (urlparse(href).hostname or "").lower()
            if href and not href.startswith(("#", "mailto:", "tel:")) and (
                not host or host == self.site_host or host.endswith("." + self.site_host)
            ):
                self.links.add(urlparse(href).path.rstrip("/") or "/")
        elif tag == "h2":
            self._h2_buf = []
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._ld_buf = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "h2" and self._h2_buf is not None:
            self.h2.append(" ".join("".join(self._h2_buf).split()).casefold())
            self._h2_buf = None
        elif tag == "script" and self._ld_buf is not None:
            self.jsonld.append("".join(self._ld_buf))
            self._ld_buf = None

    def handle_data(self, data):
        if self._h2_buf is not None:
            self._h2_buf.append(data)
        if self._ld_buf is not None:
            self._ld_buf.append(data)


def _jsonld_types(blobs: list[str]) -> frozenset[str]:
    types: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            t = node.get("@type")
            for value in t if isinstance(t, list) else [t]:
                if isinstance(value, str) and value:
                    types.add(value)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except ValueError:
            continue
    return frozenset(types)


def inventory(html: str, *, site_host: str) -> Inventory:
    """Count the value-carrying elements of one HTML version."""
    c = _Collector(site_host)
    c.feed(html or "")
    c.close()
    return Inventory(
        tables=c.counts["table"], forms=c.counts["form"], iframes=c.counts["iframe"],
        images=c.counts["img"], internal_links=len(c.links), h2=tuple(c.h2),
        jsonld_types=_jsonld_types(c.jsonld),
    )


@dataclass(frozen=True)
class DiffResult:
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing

    def report(self) -> str:
        if self.ok:
            return "OK: the new version keeps every element of the live page"
        return "\n".join(
            [f"BLOCKED: the new version loses {len(self.missing)} element(s) of the live page"]
            + [f"  - {m}" for m in self.missing]
        )


_COUNTED = (("table", "tables"), ("form", "forms"), ("iframe / embed", "iframes"),
            ("image", "images"), ("internal link", "internal_links"))


def compare(live_html: str, new_html: str, *, site_host: str) -> DiffResult:
    """Every element the new version lost relative to the live page."""
    old = inventory(live_html, site_host=site_host)
    new = inventory(new_html, site_host=site_host)
    missing: list[str] = []
    for label, field in _COUNTED:
        before, after = getattr(old, field), getattr(new, field)
        if after < before:
            missing.append(f"{label}: {before} → {after}")
    for heading in old.h2:
        if heading not in new.h2:
            missing.append(f"H2 section removed: '{heading}'")
    for jtype in sorted(old.jsonld_types - new.jsonld_types):
        missing.append(f"JSON-LD type removed: {jtype}")
    return DiffResult(tuple(missing))


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="deploy_diff_gate.py")
    p.add_argument("--live", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--host", required=True)
    try:
        args = p.parse_args(argv)
        live = Path(args.live).read_text(encoding="utf-8")
        new = Path(args.new).read_text(encoding="utf-8")
    except SystemExit:
        return 2
    except OSError as exc:
        print(f"cannot read input: {exc}", file=sys.stderr)
        return 2
    result = compare(live, new, site_host=args.host)
    print(result.report())
    return 0 if result.ok else 1


__all__ = ("Inventory", "DiffResult", "inventory", "compare")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
