#!/usr/bin/env python3
"""
migration_map_transform.py — pure site-migration / redirect-map playbook.

Two modes, both pure (no I/O, no slug literals, BOM-safe reads), per
``rules/tech-seo-governance.md`` (R-134 redirect-map contract, R-135 phase gate,
R-136 post-migration verification):

  * ``build_map`` — expand explicit ``old→new`` pairs + ordered regex rules over
    the FULL old-site crawl inventory; lint loops / self-redirects (RED),
    chains > 3 hops, homepage-collapse %, traffic-critical-unmapped, duplicate
    target fan-in; emit ``redirect_404``-shaped rows. **Silent drops are
    forbidden** (R-134): every inventory URL is either a redirect row OR listed
    in ``unmapped`` — never discarded.
  * ``verify_map`` — per R-136, confirm each 301 map row resolves old → single-hop
    301 → 200; flag 302/307-leaks, chains > 3 hops, 4xx/5xx regressions, and
    redirect-to-homepage drift. Header-tolerant on SF ``redirect_chains.csv``
    columns with a ``RedirectChainsSchemaDriftError`` guard.

Key facts encoded (Google Search Central — Site moves / Redirects):
  - one-to-one mapping; do NOT mass-redirect to the homepage (topical collapse);
  - server-side 301 is the strongest signal; keep chains ≤ 3 hops, loops forbidden;
  - redirect to the FINAL destination — a 302 where a 301 belongs leaks signal.

R-134 fixes the chain ceiling at "≤ 3 hops"; this transform flags a resolved
chain with **> 3 hops** (edges). Homepage targets are detected by an empty / ``/``
path. The engine produces the map + verification; the OPERATOR deploys (R-135) —
this transform writes nothing.

Refs: schemas/master-excel.schema.json (redirect_404 5-col shape + statusEnum),
schemas/migration-mapping.schema.json (the optional rules file this expands),
scripts/util/sheet_merge.py (merge_keyed_rows the SKILL uses to land rows),
rules/tech-seo-governance.md (R-134..R-136),
https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes.
"""

from __future__ import annotations

import re
from typing import Any, Iterable
from urllib.parse import urlsplit

_MAX_HOPS = 3  # R-134/R-136 ceiling: chains must resolve in ≤ 3 hops
_SAFETY_HOPS = 64  # guard against pathological maps while resolving chains
_DOLLAR_GROUP_RE = re.compile(r"\$(\d+)")  # $1 -> \1 (operator-friendly dialect)


# ---------------------------------------------------------------------------
# Exceptions (DURUR hierarchy — mirrors the GAP-T2/T3 transforms)
# ---------------------------------------------------------------------------

class MigrationMapError(Exception):
    """Base class for migration-map transform errors."""


class RedirectChainsSchemaDriftError(MigrationMapError):
    """SF redirect_chains rows carry no recognisable Address column (verify drift guard)."""


# ---------------------------------------------------------------------------
# BOM-safe helpers (mirror sf_projection / facet_nav_audit_transform)
# ---------------------------------------------------------------------------

def _clean_key(key: Any) -> str:
    return str(key or "").lstrip("﻿").strip().strip('"').lower()


def _normalize_row(row: dict) -> dict:
    return {_clean_key(k): v for k, v in row.items()}


def _to_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _is_homepage(url: str) -> bool:
    """True when ``url`` is a site root: empty / ``/`` path and no query."""
    if not url:
        return False
    split = urlsplit(str(url).strip())
    return split.path in ("", "/") and not split.query


def _expand_replace(template: str, pattern: str, address: str) -> str:
    """Apply a single regex rule, supporting both ``$1`` and ``\\1`` group refs."""
    converted = _DOLLAR_GROUP_RE.sub(r"\\\1", str(template or ""))
    return re.sub(pattern, converted, address, count=1)


# ---------------------------------------------------------------------------
# build_map (plan mode)
# ---------------------------------------------------------------------------

def build_map(
    inventory_rows: Iterable[dict] | None,
    mapping_pairs: Iterable[dict] | None,
    mapping_rules: Iterable[dict] | None,
    gsc_rows: Iterable[dict] | None,
    *,
    homepage_collapse_pct: float = 5.0,
    unmatched_default: str = "flag",
) -> dict:
    """Expand pairs + ordered regex rules over the inventory into redirect_404 rows.

    Returns ``{"redirect_rows", "unmapped", "lint"}``. ``redirect_rows`` carry the
    full ``redirect_404`` shape (``url/inlinks/action/target_url/status``) with
    ``status="TODO"``; 410 rows carry an empty ``target_url``. ``unmatched_default``
    is ``"flag"`` (list unmapped URLs for triage — R-134 never-drop) or ``"410"``
    (emit a 410 row for every otherwise-unmatched inventory URL).
    """
    inventory = [_normalize_row(r) for r in (inventory_rows or [])]
    pairs = [_normalize_row(r) for r in (mapping_pairs or [])]
    rules = sorted(
        (_normalize_row(r) for r in (mapping_rules or [])),
        key=lambda r: _to_int(r.get("order")),
    )
    gsc_clicks = {
        str(_normalize_row(r).get("url") or "").strip(): _to_int(_normalize_row(r).get("clicks"))
        for r in (gsc_rows or [])
    }

    inlinks_of: dict[str, int] = {}
    inv_addresses: list[str] = []
    for nrow in inventory:
        addr = str(nrow.get("address") or "").strip()
        if not addr:
            continue
        inv_addresses.append(addr)
        inlinks_of[addr] = _to_int(nrow.get("inlinks") or nrow.get("unique inlinks"))

    redirect_rows: list[dict] = []
    unmapped: list[str] = []
    pair_olds: set[str] = set()

    # 1. explicit pairs are authoritative (emitted even if absent from inventory).
    for p in pairs:
        old = str(p.get("old_url") or "").strip()
        if not old:
            continue
        action = str(p.get("action") or "301").strip()
        new = str(p.get("new_url") or "").strip()
        pair_olds.add(old)
        redirect_rows.append(_redirect_row(old, new, action, inlinks_of.get(old, 0)))

    # 2. rules over every inventory URL not already pinned by an explicit pair.
    for addr in inv_addresses:
        if addr in pair_olds:
            continue
        matched = False
        for rule in rules:
            pattern = str(rule.get("match") or "")
            if not pattern:
                continue
            try:
                if re.search(pattern, addr):
                    action = str(rule.get("action") or "301").strip()
                    target = "" if action == "410" else _expand_replace(
                        rule.get("replace") or "", pattern, addr
                    )
                    redirect_rows.append(_redirect_row(addr, target, action, inlinks_of.get(addr, 0)))
                    matched = True
                    break
            except re.error:
                # a malformed operator pattern is skipped (next rule); never crash.
                continue
        if matched:
            continue
        # 3. unmatched — never silently dropped (R-134).
        if unmatched_default == "410":
            redirect_rows.append(_redirect_row(addr, "", "410", inlinks_of.get(addr, 0)))
        else:
            unmapped.append(addr)

    lint = _lint_map(redirect_rows, unmapped, gsc_clicks, homepage_collapse_pct)
    return {
        "redirect_rows": redirect_rows,
        "unmapped": sorted(set(unmapped)),
        "lint": lint,
    }


def _redirect_row(url: str, target_url: str, action: str, inlinks: int) -> dict:
    """A redirect_404-shaped row (url/inlinks/action/target_url/status)."""
    return {
        "url": url,
        "inlinks": int(inlinks or 0),
        "action": action if action in ("301", "410") else "301",
        "target_url": "" if action == "410" else str(target_url or ""),
        "status": "TODO",
    }


def _resolve_chain(start: str, target_of: dict[str, str]) -> dict:
    """Follow ``start`` through the map's own 301 graph; detect loops + hop count."""
    seen = [start]
    cur = start
    hops = 0
    while cur in target_of:
        nxt = target_of[cur]
        hops += 1
        if nxt in seen:
            return {"loop": True, "hops": hops, "path": seen + [nxt]}
        seen.append(nxt)
        cur = nxt
        if hops >= _SAFETY_HOPS:
            break
    return {"loop": False, "hops": hops, "path": seen}


def _lint_map(
    redirect_rows: list[dict],
    unmapped: list[str],
    gsc_clicks: dict[str, int],
    homepage_collapse_pct: float,
) -> dict:
    rows_301 = [r for r in redirect_rows if r["action"] == "301"]
    target_of = {r["url"]: r["target_url"] for r in rows_301 if r["target_url"]}

    # loops / self-redirects — RED
    loop_signatures: set[frozenset] = set()
    loops: list[dict] = []
    for r in rows_301:
        res = _resolve_chain(r["url"], target_of)
        if res["loop"]:
            sig = frozenset(res["path"])
            if sig not in loop_signatures:
                loop_signatures.add(sig)
                loops.append({"url": r["url"], "path": res["path"]})

    # chains over the ≤3-hop ceiling (non-loop)
    chains_over_max: list[dict] = []
    for r in rows_301:
        res = _resolve_chain(r["url"], target_of)
        if not res["loop"] and res["hops"] > _MAX_HOPS:
            chains_over_max.append({"url": r["url"], "hops": res["hops"]})

    # homepage-collapse %
    homepage_targets = sum(1 for r in rows_301 if _is_homepage(r["target_url"]))
    pct = round(100.0 * homepage_targets / len(rows_301), 2) if rows_301 else 0.0
    homepage_high = pct > float(homepage_collapse_pct)

    # traffic-critical unmapped (old URL with GSC clicks > 0 that has no disposition)
    traffic_critical = sorted(u for u in set(unmapped) if gsc_clicks.get(u, 0) > 0)

    # duplicate-target fan-in stats (informational; consolidation is legitimate)
    fan_in: dict[str, int] = {}
    for r in rows_301:
        if r["target_url"]:
            fan_in[r["target_url"]] = fan_in.get(r["target_url"], 0) + 1
    duplicate_targets = {t: c for t, c in fan_in.items() if c > 1}

    if loops:
        verdict = "RED"
    elif redirect_rows or unmapped:
        verdict = "AMBER"
    else:
        verdict = "CLEAN"

    return {
        "loops": loops,
        "chains_over_max": chains_over_max,
        "homepage_collapse_pct": pct,
        "homepage_collapse_high": homepage_high,
        "traffic_critical_unmapped": traffic_critical,
        "duplicate_targets": duplicate_targets,
        "unmapped_count": len(set(unmapped)),
        "total_rows": len(redirect_rows),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# verify_map (verify mode — R-136)
# ---------------------------------------------------------------------------

def _addr(nrow: dict) -> str:
    return str(nrow.get("address") or "").strip()


def _violation(url: str, issue: str, detail: str) -> dict:
    return {"url": url, "issue": issue, "detail": detail}


def verify_map(
    redirect_rows: Iterable[dict] | None,
    redirect_chain_rows: Iterable[dict] | None,
    response_rows: Iterable[dict] | None,
) -> dict:
    """Confirm each 301 map row resolves old → single-hop 301 → 200 (R-136).

    Returns ``{"verified", "violations", "summary"}``. Flags 302/307-leaks,
    chains > 3 hops, 4xx/5xx regressions, and redirect-to-homepage drift. Reads
    SF ``redirect_chains.csv`` (header-tolerant) joined with
    ``response_codes_all.csv``; raises ``RedirectChainsSchemaDriftError`` when the
    chain export carries no recognisable Address column.
    """
    chains = [_normalize_row(r) for r in (redirect_chain_rows or [])]
    if chains and not any("address" in r for r in chains):
        raise RedirectChainsSchemaDriftError(
            "redirect_chains export has no 'Address' column — re-export "
            "Redirects:Redirect Chains with default columns (verify drift guard)"
        )
    chain_by_addr = {_addr(r): r for r in chains if _addr(r)}
    status_by_addr = {
        _addr(r): str(r.get("status code") or r.get("status") or "").strip()
        for r in (_normalize_row(x) for x in (response_rows or []))
        if _addr(r)
    }

    rows = list(redirect_rows or [])
    verified: list[dict] = []
    violations: list[dict] = []
    checked = 0

    for r in rows:
        if str(r.get("action") or "").strip() != "301":
            continue  # 410 rows have no redirect to verify
        url = str(r.get("url") or "").strip()
        target = str(r.get("target_url") or "").strip()
        crow = chain_by_addr.get(url)
        if crow is None:
            continue  # no post-launch chain data yet → unconfirmed, not a violation
        checked += 1
        first_type = str(
            crow.get("redirect type 1") or crow.get("redirect type") or crow.get("type") or ""
        ).strip()
        n_redirects = _to_int(crow.get("number of redirects") or crow.get("redirects") or 1)
        final_addr = str(crow.get("final address") or crow.get("final url") or "").strip()
        final_status = str(
            crow.get("final status code") or crow.get("status code")
            or status_by_addr.get(final_addr) or status_by_addr.get(url) or ""
        ).strip()

        if "302" in first_type or "307" in first_type:
            violations.append(_violation(
                url, "302 instead of 301 (temporary redirect leaks signal)",
                f"first hop type {first_type!r} → use a permanent 301 to {target or final_addr}",
            ))
            continue
        if n_redirects > _MAX_HOPS:
            violations.append(_violation(
                url, "redirect chain > 3 hops",
                f"{n_redirects} hops to {final_addr or target} — redirect directly to the final URL",
            ))
            continue
        if final_status[:1] in ("4", "5"):
            violations.append(_violation(
                url, f"{final_status} regression at redirect target",
                f"old URL redirects to {final_addr or target} which now returns {final_status}",
            ))
            continue
        if final_addr and _is_homepage(final_addr) and not _is_homepage(target):
            violations.append(_violation(
                url, "redirect-to-homepage drift",
                f"old URL now lands on the homepage {final_addr} instead of {target}",
            ))
            continue
        if final_status in ("200", ""):
            verified.append({"url": url, "target": final_addr or target,
                             "final_status": final_status or "200"})

    if violations:
        verdict = "VIOLATIONS"
    elif verified:
        verdict = "VERIFIED"
    else:
        verdict = "NO_DATA"
    summary = {
        "checked": checked,
        "verified_count": len(verified),
        "violation_count": len(violations),
        "verdict": verdict,
    }
    return {"verified": verified, "violations": violations, "summary": summary}


__all__ = (
    "build_map",
    "verify_map",
    "MigrationMapError",
    "RedirectChainsSchemaDriftError",
)
