#!/usr/bin/env python3
"""
dfs_project_transform.py — projects DataForSEO ranked_keywords + backlinks raw
JSON into master.xlsx (sheets: dfs_ranked_keywords, backlinks).

Closes the "orphan DFS data" gap: dfs-pull (D-003) stages keyword_overview +
search_volume only, and cluster-map consumes that. ranked_keywords /
relevant_pages / backlinks raw responses had NO writer and were left inert in
inbox/staging. This module projects the two highest-value ones into master.xlsx.

- Pure transform functions (build_ranked_rows / build_backlinks_rows) have no
  side effects and are unit-testable.
- CLI reads raw inbox JSON and writes via scripts.excel.transaction.replace
  (idempotent: re-running the same source does not duplicate rows).

Usage:
  python3 -m scripts.ingestion.dfs_project_transform \\
      --project vento \\
      --workspace /path/to/platinum-seo-workspace \\
      --ranked  inbox/dfs/2026-07-24-ranked_keywords-vento.json \\
      --refdomains inbox/dfs/2026-07-24-backlinks_bulk_referring_domains-vento.json \\
      --spam    inbox/dfs/2026-07-24-backlinks_bulk_spam_score-vento.json \\
      --date 2026-07-24
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------- helpers
def _find_items(obj: Any, needle_key: str, depth: int = 0) -> list[dict] | None:
    """Walk the DFS envelope (result/tasks/items nesting) and return the first
    list of dicts whose elements carry `needle_key`."""
    if depth > 8:
        return None
    if isinstance(obj, list) and obj and isinstance(obj[0], dict) and needle_key in obj[0]:
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_items(v, needle_key, depth + 1)
            if found:
                return found
    return None


def _num(v: Any) -> float | int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    return None


def _s(v: Any) -> str:
    return "" if v is None else str(v)


# ---------------------------------------------------------------- transforms
def build_ranked_rows(raw: dict, *, data_source: str) -> list[dict]:
    """ranked_keywords raw → dfs_ranked_keywords rows."""
    items = _find_items(raw, "keyword_data") or []
    rows: list[dict] = []
    for it in items:
        kd = it.get("keyword_data") or {}
        ki = kd.get("keyword_info") or {}
        rse = it.get("ranked_serp_element") or {}
        serp = rse.get("serp_item") or rse
        rows.append({
            "keyword": _s(kd.get("keyword")),
            "rank_group": _num(serp.get("rank_group")),
            "rank_absolute": _num(serp.get("rank_absolute")),
            "url": _s(serp.get("url")),
            "search_volume": _num(ki.get("search_volume")),
            "etv": _num(serp.get("etv")),
            "cpc": _num(ki.get("cpc")),
            "competition": _num(ki.get("competition")),
            "title": _s(serp.get("title"))[:300],
            "data_source": data_source,
        })
    # Stable ordering: best rank first, then keyword (byte-stable re-runs).
    rows.sort(key=lambda r: (r["rank_absolute"] if r["rank_absolute"] is not None else 9999,
                             r["keyword"]))
    return rows


def build_backlinks_rows(raw_refdomains: dict | None,
                         raw_spam: dict | None,
                         *, data_source: str, last_updated: str) -> list[dict]:
    """backlinks bulk_referring_domains + bulk_spam_score raw → backlinks rows
    (one summary row per target)."""
    ref_items = _find_items(raw_refdomains or {}, "referring_domains") or []
    spam_items = _find_items(raw_spam or {}, "spam_score") or []
    spam_by_target = {_s(s.get("target")): _num(s.get("spam_score")) for s in spam_items}
    rows: list[dict] = []
    for it in ref_items:
        target = _s(it.get("target"))
        rows.append({
            "target": target,
            "referring_domains": _num(it.get("referring_domains")),
            "referring_main_domains": _num(it.get("referring_main_domains")),
            "referring_domains_nofollow": _num(it.get("referring_domains_nofollow")),
            "spam_score": spam_by_target.get(target),
            "data_source": data_source,
            "last_updated": last_updated,
        })
    return rows


def build_relevant_rows(raw: dict, *, data_source: str) -> list[dict]:
    """relevant_pages raw → dfs_relevant_pages rows (page → ranked-kw metrics)."""
    items = _find_items(raw, "page_address") or []
    rows: list[dict] = []
    for it in items:
        org = ((it.get("metrics") or {}).get("organic")) or {}
        rows.append({
            "url": _s(it.get("page_address")),
            "ranked_keywords_count": _num(org.get("count")),
            "etv": _num(org.get("etv")),
            "pos_2_3": _num(org.get("pos_2_3")),
            "pos_4_10": _num(org.get("pos_4_10")),
            "pos_11_20": _num(org.get("pos_11_20")),
            "data_source": data_source,
        })
    rows.sort(key=lambda r: -(r["ranked_keywords_count"] or 0))
    return rows


# ---------------------------------------------------------------- CLI
def _load(path: Path) -> dict | None:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Project DFS ranked_keywords + backlinks into master.xlsx")
    ap.add_argument("--project", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--ranked", default=None, help="raw ranked_keywords JSON (relative to project dir or absolute)")
    ap.add_argument("--refdomains", default=None, help="raw backlinks_bulk_referring_domains JSON")
    ap.add_argument("--spam", default=None, help="raw backlinks_bulk_spam_score JSON")
    ap.add_argument("--relevant", default=None, help="raw relevant_pages JSON")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD data snapshot date")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    ws_root = Path(args.workspace)
    proj_dir = ws_root / "projects" / args.project
    master = proj_dir / "master.xlsx"

    def _resolve(p: str | None) -> Path | None:
        if not p:
            return None
        pp = Path(p)
        return pp if pp.is_absolute() else (proj_dir / p)

    ranked_raw = _load(_resolve(args.ranked))
    ref_raw = _load(_resolve(args.refdomains))
    spam_raw = _load(_resolve(args.spam))
    relevant_raw = _load(_resolve(args.relevant))

    ranked_rows = build_ranked_rows(ranked_raw, data_source=f"dataforseo_ranked_keywords {args.date}") if ranked_raw else []
    backlinks_rows = build_backlinks_rows(ref_raw, spam_raw,
                                          data_source=f"dataforseo_backlinks {args.date}",
                                          last_updated=args.date) if ref_raw else []
    relevant_rows = build_relevant_rows(relevant_raw, data_source=f"dataforseo_relevant_pages {args.date}") if relevant_raw else []

    summary = {
        "dfs_ranked_keywords": len(ranked_rows),
        "backlinks": len(backlinks_rows),
        "dfs_relevant_pages": len(relevant_rows),
        "dry_run": bool(args.dry_run),
    }
    if args.dry_run:
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    # Import here so pure-transform imports stay side-effect free.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.excel import transaction

    if ranked_rows:
        transaction.replace(master, "dfs_ranked_keywords", ranked_rows, args.project, writer="dfs-project")
    if backlinks_rows:
        transaction.replace(master, "backlinks", backlinks_rows, args.project, writer="dfs-project")
    if relevant_rows:
        transaction.replace(master, "dfs_relevant_pages", relevant_rows, args.project, writer="dfs-project")

    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
