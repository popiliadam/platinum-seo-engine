#!/usr/bin/env python3
"""
gsc_pull.py — pure transform: GSC search_analytics + enhanced_search_analytics
JSON → schema-shaped rows for master.xlsx#gsc_performance.

Reads the raw response of mcp__gsc__search_analytics (recent window) plus
optionally mcp__gsc__enhanced_search_analytics (the previous window of equal
length used for delta computation), normalizes URLs per D-03 (lowercase
scheme+host, strip default ports, collapse trailing slash except root,
sort+filter query string, drop fragment, IDN -> punycode), aggregates
metrics per page across the recent and previous windows, and emits a row
list shaped for master.xlsx#gsc_performance (12 schema-locked columns
defined in schemas/master-excel.schema.json).

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same input -> same output. Re-running with the same
    --raw and --enriched files writes byte-identical outputs.

CLI (two modes):
  # 1) gsc_performance transform (default)
  python3 scripts/ingestion/gsc_pull.py \
      --raw inbox/gsc/2026-04-30-search_analytics-{slug}.json \
      [--enriched inbox/gsc/2026-04-30-enhanced_search_analytics-{slug}.json] \
      [--output-dir .]

  # 2) weekly ISO-week ledger append (GAP-M4 D1 — anomaly-detection history)
  python3 scripts/ingestion/gsc_pull.py --append-weekly-ledger \
      --daily inbox/gsc/{date}-search_analytics_daily-{slug}.json \
      --ledger projects/{slug}/_state/metrics/gsc-weekly.jsonl \
      --today 2026-06-10

Stdout: JSON {"gsc_performance": [...], "meta": {...}} (mode 1) or
{"appended": [...], "skipped": [...], "ledger": "..."} (mode 2).
With --output-dir set (mode 1): also writes gsc_performance.json into that dir
and prints the absolute path.

Refs: schemas/master-excel.schema.json (gsc_performance sheet
required_columns), schemas/gsc-tool-mapping.schema.json (D-03 URL
normalization invariant + url_original + url_normalized staging),
spec §6 + §12.2 (raw JSON inbox + transform stage), spec §16.5
(MCP discipline).
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)

# ---------------------------------------------------------------------------
# Constants — schema-aligned column names (master-excel.schema.json#gsc_performance)
# ---------------------------------------------------------------------------

GSC_PERFORMANCE_COLUMNS = (
    "url",
    "clicks_recent",
    "clicks_previous",
    "clicks_delta",
    "clicks_delta_pct",
    "impressions_recent",
    "impressions_previous",
    "impressions_delta",
    "ctr_recent",
    "position_recent",
    "position_previous",
    "note",
)

# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class GscPullError(ValueError):
    """Base class for explicit DURUR conditions in gsc_pull transform."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant)
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Adapter wrapping :class:`URLNormalizeError` into :class:`GscPullError`
    so call-site DURUR semantics stay backward-compatible after K-01
    dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError as exc:
        raise GscPullError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Aggregator helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _PageMetrics:
    """Aggregated metrics for one normalized URL across one window."""
    clicks: int
    impressions: int
    # ctr is recomputed downstream from clicks/impressions; we keep the raw
    # weighted-position aggregate for accurate page-level position mean.
    position_weighted_sum: float


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _aggregate_window(payload: dict | None) -> dict[str, _PageMetrics]:
    """
    Aggregate a search_analytics-shaped MCP payload to per-URL metrics.

    Accepts payloads of the shape:
      {"rows": [{"keys": [<page>, ...], "clicks": N, "impressions": M,
                 "ctr": x, "position": y}, ...]}

    or:
      {"data": [...]}  (alternate envelope)

    URL is taken from keys[0] (when single dimension == page) or by
    locating the first http(s) entry in keys (defensive: dimension order
    is caller-controlled).

    Empty payload -> empty dict (caller decides if this is fatal).
    """
    if not payload:
        return {}
    rows = payload.get("rows") or payload.get("data") or []
    if not isinstance(rows, list):
        raise GscPullError(
            f"search_analytics payload 'rows' must be a list, got {type(rows).__name__}"
        )

    bucket: dict[str, dict[str, float]] = {}
    for entry in rows:
        if not isinstance(entry, dict):
            continue
        keys = entry.get("keys") or []
        if not isinstance(keys, list) or not keys:
            continue
        # Find the first key that looks like a URL (case-insensitive scheme).
        page_raw: str | None = None
        for k in keys:
            if isinstance(k, str):
                k_stripped = k.strip()
                if k_stripped[:7].lower() == "http://" or \
                   k_stripped[:8].lower() == "https://":
                    page_raw = k_stripped
                    break
        if page_raw is None:
            continue
        try:
            url_n = normalize_url(page_raw)
        except GscPullError:
            continue

        clicks = _safe_int(entry.get("clicks")) or 0
        impressions = _safe_int(entry.get("impressions")) or 0
        position = _safe_float(entry.get("position")) or 0.0

        slot = bucket.setdefault(url_n, {
            "clicks": 0,
            "impressions": 0,
            "pos_w_sum": 0.0,
        })
        slot["clicks"] += clicks
        slot["impressions"] += impressions
        # Position weighted by impressions for accurate page-level mean.
        slot["pos_w_sum"] += position * impressions

    return {
        url_n: _PageMetrics(
            clicks=int(v["clicks"]),
            impressions=int(v["impressions"]),
            position_weighted_sum=float(v["pos_w_sum"]),
        )
        for url_n, v in bucket.items()
    }


def _delta_pct(recent: int, previous: int) -> float:
    """
    Percent change = (recent - previous) / previous * 100, rounded 2dp.

    Edge cases:
      previous == 0 and recent == 0  -> 0.0    (no change, no signal)
      previous == 0 and recent > 0   -> 100.0  (capped, "new arrival")
      previous == 0 and recent < 0   -> -100.0 (defensive; clicks can't be neg)
    """
    if previous == 0:
        if recent == 0:
            return 0.0
        return 100.0 if recent > 0 else -100.0
    return round((recent - previous) / float(previous) * 100.0, 2)


def _avg_position(metrics: _PageMetrics) -> float:
    if metrics.impressions <= 0:
        return 0.0
    return round(metrics.position_weighted_sum / metrics.impressions, 2)


def _avg_ctr_pct(metrics: _PageMetrics) -> float:
    if metrics.impressions <= 0:
        return 0.0
    return round(metrics.clicks / float(metrics.impressions) * 100.0, 4)


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(
    raw: dict,
    *,
    enriched: dict | None = None,
) -> dict:
    """
    Transform GSC search_analytics raw payloads into schema-shaped
    gsc_performance row list.

    Args:
        raw:      Parsed JSON from mcp__gsc__search_analytics for the
                  RECENT window (today - days_back .. today). Must be a
                  dict with a 'rows' (or 'data') list.
        enriched: Optional parsed JSON from
                  mcp__gsc__enhanced_search_analytics (or a second
                  search_analytics call) for the PREVIOUS window of equal
                  length. Used to compute per-URL deltas. None means the
                  transform produces previous-window zeros (acceptable
                  for first-run).

    Returns:
        {"gsc_performance": [<row>, ...], "meta": {...}}.

    DURUR triggers (raises GscPullError, do NOT silently fallback):
      - raw is not a dict
      - raw['rows'] is present but not a list
      - URL normalization output drifts (idempotency check fails)
    """
    if not isinstance(raw, dict):
        raise GscPullError(f"raw must be a dict, got {type(raw).__name__}")

    recent = _aggregate_window(raw)
    previous = _aggregate_window(enriched)

    rows: list[dict] = []
    # Stable URL ordering: union of both windows, sorted asc for determinism.
    all_urls = sorted(set(recent.keys()) | set(previous.keys()))
    for url_n in all_urls:
        # D-03 idempotency self-check (defensive — raises if drift slips
        # into the schema-shaped output).
        if normalize_url(url_n) != url_n:
            raise GscPullError(
                f"URL normalization drift detected: {url_n!r} is not "
                f"idempotent under normalize_url; D-03 invariant broken"
            )

        rcur = recent.get(url_n)
        rprev = previous.get(url_n)

        clicks_recent = rcur.clicks if rcur else 0
        clicks_previous = rprev.clicks if rprev else 0
        clicks_delta = clicks_recent - clicks_previous
        clicks_delta_pct = _delta_pct(clicks_recent, clicks_previous)

        impressions_recent = rcur.impressions if rcur else 0
        impressions_previous = rprev.impressions if rprev else 0
        impressions_delta = impressions_recent - impressions_previous

        ctr_recent = _avg_ctr_pct(rcur) if rcur else 0.0
        position_recent = _avg_position(rcur) if rcur else 0.0
        position_previous = _avg_position(rprev) if rprev else 0.0

        # Note column carries a short trend hint; deterministic from the
        # delta values, no creativity, sheet-template friendly.
        if clicks_delta_pct > 20:
            note = "rising"
        elif clicks_delta_pct < -20:
            note = "decay"
        elif clicks_recent == 0 and clicks_previous == 0:
            note = "no-clicks"
        else:
            note = "stable"

        rows.append({
            "url": url_n,
            "clicks_recent": clicks_recent,
            "clicks_previous": clicks_previous,
            "clicks_delta": clicks_delta,
            "clicks_delta_pct": clicks_delta_pct,
            "impressions_recent": impressions_recent,
            "impressions_previous": impressions_previous,
            "impressions_delta": impressions_delta,
            "ctr_recent": ctr_recent,
            "position_recent": position_recent,
            "position_previous": position_previous,
            "note": note,
        })

    # Stable sort: clicks_recent desc, then url asc for determinism.
    rows.sort(key=lambda r: (-r["clicks_recent"], r["url"]))

    # Schema-locked column projection (drops any stray keys).
    gsc_perf_rows = [
        {k: r[k] for k in GSC_PERFORMANCE_COLUMNS}
        for r in rows
    ]

    return {
        "gsc_performance": gsc_perf_rows,
        "meta": {
            "recent_url_count": len(recent),
            "previous_url_count": len(previous),
            "merged_url_count": len(gsc_perf_rows),
            "enriched_used": enriched is not None,
        },
    }


# ---------------------------------------------------------------------------
# Weekly ISO-week ledger (GAP-M4 D1) — pre/post anomaly-detection history store
# ---------------------------------------------------------------------------
#
# master.xlsx#gsc_performance is a recent-vs-previous SNAPSHOT (no date column,
# rewritten on every run), so it cannot hold a weekly time series. The anomaly
# detector (scripts/reporting/weekly_anomaly.py, R-141) needs one. This module
# owns an append-only sidecar ledger at projects/{slug}/_state/metrics/
# gsc-weekly.jsonl, one line per COMPLETE ISO week, fed from a free site-level
# daily GSC series (dimensions=["date"]).
#
# Append discipline mirrors scripts/state/anomaly_recorder._atomic_append_line
# (O_APPEND + flock + fsync) — append-only-state rule, never rewrites a line.

LEDGER_SOURCE = "gsc_mcp"
_GSC_DATA_LAG_DAYS = 2  # GSC daily data lags ~2 days; the most-recent week is unsafe


def _as_date(value: Any) -> date:
    """Coerce a date / 'YYYY-MM-DD' / ISO datetime string to a date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    return date.fromisoformat(s[:10])


def _iso_week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _week_bounds(d: date) -> tuple[date, date]:
    """Monday (start) and Sunday (end) of the ISO week containing `d`."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def aggregate_iso_weeks(daily_rows: Iterable[dict], today: Any) -> list[dict]:
    """Aggregate a site-level daily GSC series into COMPLETE ISO-week rows.

    Args:
        daily_rows: GSC search_analytics rows with dimensions=["date"]:
            {"keys": ["2026-06-01"], "clicks": N, "impressions": M, "position": p}.
        today: anchor date (frozen arg; rules/time-discipline.md). The week
            containing `today` is excluded, AND any week whose Sunday is within
            `_GSC_DATA_LAG_DAYS` of `today` is excluded (data-lag guard).

    Returns weekly dicts (newest-week LAST, ascending iso_week) shaped for the
    ledger: {iso_week, week_start, week_end, clicks, impressions, ctr,
    avg_position, source}. Pure + deterministic.
    """
    today_d = _as_date(today)
    cutoff = today_d - timedelta(days=_GSC_DATA_LAG_DAYS)

    buckets: dict[str, dict] = {}
    for row in daily_rows:
        if not isinstance(row, dict):
            continue
        keys = row.get("keys") or []
        if not keys:
            continue
        try:
            d = _as_date(keys[0])
        except (ValueError, TypeError):
            continue
        clicks = _safe_int(row.get("clicks")) or 0
        impressions = _safe_int(row.get("impressions")) or 0
        position = _safe_float(row.get("position")) or 0.0
        label = _iso_week_label(d)
        monday, sunday = _week_bounds(d)
        b = buckets.setdefault(label, {
            "clicks": 0, "impressions": 0, "pos_w_sum": 0.0,
            "monday": monday, "sunday": sunday,
        })
        b["clicks"] += clicks
        b["impressions"] += impressions
        b["pos_w_sum"] += position * impressions

    out: list[dict] = []
    for label in sorted(buckets):
        b = buckets[label]
        if not (b["sunday"] < cutoff):   # week not fully elapsed past the lag → skip
            continue
        impressions = b["impressions"]
        ctr = round(b["clicks"] / impressions, 4) if impressions > 0 else 0.0
        avg_position = round(b["pos_w_sum"] / impressions, 2) if impressions > 0 else 0.0
        out.append({
            "iso_week": label,
            "week_start": b["monday"].isoformat(),
            "week_end": b["sunday"].isoformat(),
            "clicks": b["clicks"],
            "impressions": impressions,
            "ctr": ctr,
            "avg_position": avg_position,
            "source": LEDGER_SOURCE,
        })
    return out


def _atomic_append_line(path: Path, payload: bytes) -> None:
    """Append one line atomically (O_APPEND + flock + fsync).

    Copied from scripts/state/anomaly_recorder._atomic_append_line (append-only-
    state discipline) to keep gsc_pull free of a private cross-module import.
    """
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            written = os.write(fd, payload)
            if written != len(payload):
                raise GscPullError(
                    f"short write on {path}: {written} of {len(payload)} bytes"
                )
            os.fsync(fd)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:  # pragma: no cover
                pass
    finally:
        os.close(fd)


def append_weekly_ledger(
    ledger_path: Path | str,
    weeks: Iterable[dict],
    *,
    source: str = LEDGER_SOURCE,
) -> dict:
    """Append only the missing weeks to the ISO-week ledger (idempotent).

    Dedup key is `iso_week`: a week already present is skipped, so re-running is
    a no-op and existing lines are NEVER rewritten (append-only-state). Each new
    row gains a `written_at` UTC stamp at append time.
    """
    ledger = Path(ledger_path)
    existing: set[str] = set()
    if ledger.exists():
        for line in ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                wk = json.loads(line).get("iso_week")
            except json.JSONDecodeError:
                continue
            if wk:
                existing.add(wk)

    appended: list[str] = []
    skipped: list[str] = []
    ledger.parent.mkdir(parents=True, exist_ok=True)
    for wk in sorted(weeks, key=lambda w: str(w.get("iso_week", ""))):
        label = wk.get("iso_week")
        if not label:
            continue
        if label in existing:
            skipped.append(label)
            continue
        rec = dict(wk)
        rec.setdefault("source", source)
        rec["written_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = (json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        _atomic_append_line(ledger, payload)
        existing.add(label)
        appended.append(label)

    return {"appended": appended, "skipped": skipped, "ledger": str(ledger)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="gsc_pull.py",
        description="Transform GSC search_analytics JSON -> gsc_performance rows, "
                    "or append the weekly ISO-week ledger (--append-weekly-ledger).",
    )
    # Default mode: gsc_performance transform. --raw is required ONLY here, so
    # validation moves to main() to keep the ledger sub-mode argument-free of it.
    p.add_argument("--raw", default=None,
                   help="Path to raw mcp__gsc__search_analytics JSON (recent window).")
    p.add_argument("--enriched", default=None,
                   help="Optional path to enhanced_search_analytics JSON (previous window).")
    p.add_argument("--output-dir", default=None,
                   help="If set, write gsc_performance.json here.")
    # Weekly-ledger sub-mode (GAP-M4 D1).
    p.add_argument("--append-weekly-ledger", action="store_true",
                   help="Aggregate a daily series into complete ISO weeks and "
                        "append the missing ones to --ledger.")
    p.add_argument("--daily", default=None,
                   help="Daily site-level search_analytics JSON (dimensions=['date']).")
    p.add_argument("--ledger", default=None,
                   help="Path to the projects/{slug}/_state/metrics/gsc-weekly.jsonl ledger.")
    p.add_argument("--today", default=None,
                   help="UTC date anchor (YYYY-MM-DD) for complete-week computation.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    # ---- Weekly-ledger sub-mode (GAP-M4 D1) -------------------------------
    if args.append_weekly_ledger:
        missing = [f for f, v in (("--daily", args.daily),
                                  ("--ledger", args.ledger),
                                  ("--today", args.today)) if not v]
        if missing:
            print(f"--append-weekly-ledger requires {', '.join(missing)}",
                  file=sys.stderr)
            return 2
        daily_path = Path(args.daily)
        if not daily_path.exists():
            print(f"daily JSON not found: {daily_path}", file=sys.stderr)
            return 2
        daily_payload = _read_json(daily_path)
        daily_rows = daily_payload.get("rows") or daily_payload.get("data") or []
        weeks = aggregate_iso_weeks(daily_rows, args.today)
        result = append_weekly_ledger(args.ledger, weeks)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # ---- Default mode: gsc_performance transform --------------------------
    if not args.raw:
        print("--raw is required (gsc_performance transform mode)", file=sys.stderr)
        return 2
    raw_path = Path(args.raw)
    if not raw_path.exists():
        print(f"raw JSON not found: {raw_path}", file=sys.stderr)
        return 2
    raw = _read_json(raw_path)

    enriched: dict | None = None
    if args.enriched:
        enriched_path = Path(args.enriched)
        if enriched_path.exists():
            enriched = _read_json(enriched_path)

    try:
        result = transform(raw, enriched=enriched)
    except GscPullError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "gsc_performance.json"
        out_path.write_text(
            json.dumps(result["gsc_performance"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "gsc_performance_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "GSC_PERFORMANCE_COLUMNS",
    "GscPullError",
    "normalize_url",
    "transform",
    "aggregate_iso_weeks",
    "append_weekly_ledger",
    "main",
)
