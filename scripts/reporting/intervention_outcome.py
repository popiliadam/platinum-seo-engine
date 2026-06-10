#!/usr/bin/env python3
"""
intervention_outcome.py — pure treated-vs-control outcome for quick-wins (R-138).

Reads a quick-wins cohort snapshot (the treated + control groups written by the
quick-wins skill Step 7b — `_state/metrics/quickwin-cohorts/{date}-cohort.json`)
plus a LATER-dated GSC payload (a `detect_quick_wins` or `search_analytics`
inbox snapshot), and answers ONE measurement question honestly: did the engine's
quick-win interventions move the needle MORE than a matched, untouched control
set?

This is the read side of R-138 (intervention cohort tagging). The honesty
contract is the whole point:

  - The reported outcome is the treated-vs-control DIFFERENCE in percentage
    points (Σclicks delta %), NEVER a raw treated delta — a treated-only rise
    could be pure seasonality/Google-update noise the engine didn't cause.
  - |difference| < 10pp ⇒ ``indistinguishable`` (n<30 — directional only); no
    p-values, no significance theater at these sample sizes.
  - Rows missing from the post payload are DROPPED from the medians and counted
    in ``attrition`` — never fabricated.
  - The median position delta is reported as supporting evidence; the verdict
    threshold is on the pp metric (clicks delta %).

Pure-function discipline:
  - No state mutation, no implicit network/clock. All dates are arguments
    (rules/time-discipline.md — no date.today() inside the module).
  - Deterministic: same inputs -> byte-identical output.
  - stdlib only (statistics.median) — no scipy/numpy/statsmodels.

CLI:
  python3 scripts/reporting/intervention_outcome.py \
      --cohort-dir projects/{slug}/_state/metrics/quickwin-cohorts/ \
      --post inbox/gsc/{date}-search_analytics-{slug}.json \
      --today 2026-06-10 [--min-age-days 21] [--output <path>]

  (or --cohort <single file> for one cohort)

Stdout / --output: a JSON ARRAY of outcome objects, shaped for
``monthly_report.py --cohort-results`` (the monthly report's
``measurement_context.intervention_outcomes``).

Refs: docs/superpowers/plans/amo/2026-06-10-gap-specs-measurement-ai.md (GAP-M1
D3), rules/measurement-discipline.md (R-138).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


# Honesty constants — directional-only at n<30 (R-138). These are method
# parameters (override via kwarg), not curve/discount data (so outside R-139).
DEFAULT_THRESHOLD_PP: float = 10.0
DIRECTIONAL_CAVEAT: str = "n<30 — directional evidence only"


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------

def _to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _index_post(payload: Any) -> dict[str, dict]:
    """Map ``query -> {"position", "clicks"}`` from a GSC payload.

    Tolerant of both the detect_quick_wins shape (``quickWins``/``quick_wins``
    rows with ``currentPosition``/``position`` + ``currentClicks``/``clicks``)
    and the search_analytics shape (``rows``/``data`` with ``keys[0]`` = query).
    Unparseable rows are skipped (never fabricated).
    """
    rows: Iterable[Any]
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        rows = (
            payload.get("quickWins")
            or payload.get("quick_wins")
            or payload.get("rows")
            or payload.get("data")
            or []
        )
    else:
        rows = []

    out: dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, Mapping):
            continue
        q = r.get("query")
        if q is None:
            keys = r.get("keys")
            if isinstance(keys, (list, tuple)) and keys:
                q = keys[0]
        if q is None:
            continue
        pos = r.get("currentPosition")
        if pos is None:
            pos = r.get("position")
        clk = r.get("currentClicks")
        if clk is None:
            clk = r.get("clicks")
        out[str(q)] = {"position": _to_float(pos), "clicks": _to_float(clk)}
    return out


def _group_stats(
    rows: Sequence[Mapping[str, Any]], post_index: Mapping[str, dict],
) -> tuple[dict, int]:
    """Median position delta + Σclicks delta % over rows present in the post
    payload. Returns (stats, missing_count). Missing rows are excluded from
    BOTH medians and the clicks sums (and counted as missing)."""
    pos_deltas: list[float] = []
    clicks_before = 0.0
    clicks_after = 0.0
    missing = 0
    for row in rows:
        q = str(row.get("query"))
        post = post_index.get(q)
        if post is None:
            missing += 1
            continue
        cohort_pos = _to_float(row.get("position"))
        if post["position"] is not None and cohort_pos is not None:
            pos_deltas.append(post["position"] - cohort_pos)
        clicks_before += _to_float(row.get("clicks_30d")) or 0.0
        clicks_after += post["clicks"] or 0.0

    n = len(rows) - missing
    med = round(median(pos_deltas), 4) if pos_deltas else None
    clicks_delta_pct = (
        round((clicks_after - clicks_before) / clicks_before * 100.0, 4)
        if clicks_before > 0 else 0.0
    )
    return (
        {
            "n": n,
            "median_position_delta": med,
            "clicks_before": int(round(clicks_before)),
            "clicks_after": int(round(clicks_after)),
            "clicks_delta_pct": clicks_delta_pct,
        },
        missing,
    )


# ---------------------------------------------------------------------------
# Core outcome (R-138)
# ---------------------------------------------------------------------------

def compute_outcome(
    cohort: Mapping[str, Any],
    post_payload: Any,
    *,
    post_date: str = "",
    threshold_pp: float = DEFAULT_THRESHOLD_PP,
) -> dict:
    """Treated-vs-control outcome for one cohort.

    ``difference_pp`` = treated.clicks_delta_pct − control.clicks_delta_pct.
    Verdict (R-138): ``engine_positive`` when difference ≥ +threshold_pp,
    ``engine_negative`` when ≤ −threshold_pp, else ``indistinguishable``. The
    caveat is always the directional-only string (no p-values at n<30).
    """
    treated_rows = cohort.get("treated") or []
    control_rows = cohort.get("controls") or cohort.get("control") or []
    post_index = _index_post(post_payload)

    treated_stats, treated_missing = _group_stats(treated_rows, post_index)
    control_stats, control_missing = _group_stats(control_rows, post_index)

    difference_pp = round(
        treated_stats["clicks_delta_pct"] - control_stats["clicks_delta_pct"], 4
    )
    if difference_pp >= threshold_pp:
        verdict = "engine_positive"
    elif difference_pp <= -threshold_pp:
        verdict = "engine_negative"
    else:
        verdict = "indistinguishable"

    return {
        "cohort_date": str(cohort.get("cohort_date") or ""),
        "score_version": str(cohort.get("score_version") or ""),
        "post_date": str(post_date or ""),
        "treated": treated_stats,
        "control": control_stats,
        "difference_pp": difference_pp,
        "verdict": verdict,
        "caveat": DIRECTIONAL_CAVEAT,
        "attrition": {
            "treated_missing": treated_missing,
            "control_missing": control_missing,
        },
    }


# ---------------------------------------------------------------------------
# Cohort-file selection (pure; today as arg)
# ---------------------------------------------------------------------------

def _iso_date(value: str):
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def select_cohort_files(
    cohort_dir: Path | str, *, today: str, min_age_days: int = 21,
) -> list[Path]:
    """Return ``*-cohort.json`` files whose ``cohort_date`` is at least
    ``min_age_days`` before ``today`` (so a real post-window exists). Pure: the
    cutoff is computed from the ``today`` ARGUMENT, never the wall clock.
    Unreadable / mis-dated files are skipped."""
    cutoff = _iso_date(today) - timedelta(days=int(min_age_days))
    picked: list[Path] = []
    base = Path(cohort_dir)
    if not base.is_dir():
        return picked
    for p in sorted(base.glob("*-cohort.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            cd = data.get("cohort_date") or p.name.split("-cohort")[0]
            if _iso_date(str(cd)) <= cutoff:
                picked.append(p)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return picked


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="intervention_outcome.py",
        description=(
            "Treated-vs-control quick-wins outcome (R-138). Emits a JSON array "
            "for monthly_report.py --cohort-results."
        ),
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--cohort", default=None,
                   help="Path to a single {date}-cohort.json file.")
    g.add_argument("--cohort-dir", default=None,
                   help="Directory of {date}-cohort.json files (age-filtered).")
    p.add_argument("--post", required=True,
                   help="Path to the later-dated GSC payload "
                        "(search_analytics or detect_quick_wins shape).")
    p.add_argument("--today", default=None,
                   help="ISO YYYY-MM-DD; required with --cohort-dir "
                        "(age filter). Frozen date — no wall clock.")
    p.add_argument("--min-age-days", type=int, default=21,
                   help="Minimum cohort age in days for --cohort-dir (default 21).")
    p.add_argument("--post-date", default="",
                   help="ISO date of the post payload (recorded in each outcome).")
    p.add_argument("--threshold-pp", type=float, default=DEFAULT_THRESHOLD_PP,
                   help=f"Indistinguishable band in pp (default {DEFAULT_THRESHOLD_PP}).")
    p.add_argument("--output", default=None,
                   help="If set, write the JSON array here; else print to stdout.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    post_path = Path(args.post)
    if not post_path.is_file():
        print(f"post payload not found: {post_path}", file=sys.stderr)
        return 2
    post_payload = _read_json(post_path)

    cohort_paths: list[Path]
    if args.cohort:
        cohort_paths = [Path(args.cohort)]
    else:
        if not args.today:
            print("--today is required with --cohort-dir", file=sys.stderr)
            return 2
        cohort_paths = select_cohort_files(
            args.cohort_dir, today=args.today, min_age_days=args.min_age_days,
        )

    outcomes: list[dict] = []
    for cp in cohort_paths:
        if not cp.is_file():
            print(f"cohort file not found: {cp}", file=sys.stderr)
            return 2
        cohort = _read_json(cp)
        outcomes.append(compute_outcome(
            cohort, post_payload,
            post_date=args.post_date, threshold_pp=args.threshold_pp,
        ))

    blob = json.dumps(outcomes, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(blob, encoding="utf-8")
        print(json.dumps({"cohort_results_path": str(out_path.resolve()),
                          "outcomes": len(outcomes)}, ensure_ascii=False))
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "DEFAULT_THRESHOLD_PP",
    "DIRECTIONAL_CAVEAT",
    "compute_outcome",
    "select_cohort_files",
    "main",
)
