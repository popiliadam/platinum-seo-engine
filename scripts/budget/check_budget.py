#!/usr/bin/env python3
"""
check_budget.py — pre-flight budget guardrail (§16.8).

Reads `dataforseo.budget_credits_per_day` from project.config.json and sums
DataForSEO credit usage from the last 24h of events.jsonl. Emits a single-line
JSON object on stdout for machine consumption.

Usage:
    check_budget.py [--project-config <path>] [--events <path>]

Defaults (relative to current working dir / workspace):
    --project-config  project.config.json
    --events          _state/events.jsonl

Stdout (single line JSON):
    {"budget_per_day": 500, "used_24h": 120, "remaining": 380, "exceeded": false}

Exit codes:
    0  within budget (or events.jsonl missing → zero usage)
    1  exceeded OR config error

Event matching (per schemas/events.schema.json — ADR-017 schema-first):
  - PROVENANCE events with `source.kind == "dataforseo_mcp"` and a populated
    `cost.credits` are summed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _parse_ts(raw: str) -> datetime | None:
    if not isinstance(raw, str):
        return None
    # Accept trailing 'Z' as UTC.
    txt = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _extract_credits(event: dict) -> float:
    """Return credit cost of a DataForSEO event, or 0 if unrelated."""
    src = event.get("source") or {}
    cost = event.get("cost") or {}
    if (
        event.get("event_kind") == "provenance"
        and isinstance(src, dict)
        and src.get("kind") == "dataforseo_mcp"
        and isinstance(cost, dict)
    ):
        credits = cost.get("credits")
        if isinstance(credits, (int, float)):
            return float(credits)
    return 0.0


def _sum_last_24h(events_path: Path, now: datetime) -> float:
    if not events_path.exists():
        _log(f"events file missing ({events_path}); treating usage as 0")
        return 0.0
    cutoff = now - timedelta(hours=24)
    total = 0.0
    with events_path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                _log(f"skipping malformed JSON at {events_path}:{lineno}")
                continue
            ts = _parse_ts(event.get("timestamp", ""))
            if ts is None or ts < cutoff:
                continue
            total += _extract_credits(event)
    return total


class BudgetGateError(RuntimeError):
    """Raised by a skill when a pre-flight budget check gates a paid MCP call.

    The skill orchestrator catches/propagates this to transition a workflow run
    to ``awaiting_approval`` instead of silently downgrading to a free path
    (the false-success failure mode skills explicitly forbid). It is defined
    here so the importable contract — ``preflight()`` + ``BudgetGateError`` —
    lives in one module (content-decay Step 4b depends on both, B6-01).
    """


def preflight(
    project_config_path: Path | str,
    events_path: Path | str,
    estimated_credits: float = 0,
    now: datetime | None = None,
) -> dict:
    """Pre-flight budget envelope for an *about-to-run* paid MCP call.

    Unlike :func:`main` (a CLI that reports current trailing-24h usage), this is
    the importable contract skills depend on: it folds ``estimated_credits`` —
    the cost the proposed call would add — into the trailing-24h DataForSEO
    spend and reports whether the *projected* total would breach the per-day
    cap. It is pure: no stdout, no ``sys.exit`` — raising/gating is the caller's
    decision (see :class:`BudgetGateError`).

    Returns an envelope (superset of :func:`main`'s keys)::

        {"budget_per_day", "used_24h", "estimated_credits",
         "projected", "remaining", "exceeded"}

    where ``projected = used_24h + estimated_credits``,
    ``remaining = budget_per_day - projected`` (may be negative), and
    ``exceeded`` is True iff ``projected > budget_per_day``.

    Raises ``BudgetGateError`` when the project-config is unreadable (missing,
    malformed, or an invalid budget): ``_load_budget`` ``sys.exit``s for the CLI
    path, but a library caller must get a catchable exception, never a process
    kill — so that ``SystemExit`` is converted here (the "no sys.exit escapes"
    contract this function promises).
    """
    if estimated_credits < 0:
        raise ValueError(
            f"estimated_credits must be >= 0, got {estimated_credits!r}"
        )
    if now is None:
        now = datetime.now(timezone.utc)

    try:
        budget = _load_budget(Path(project_config_path))
    except SystemExit as exc:
        raise BudgetGateError(
            f"budget pre-flight: project-config unreadable "
            f"({project_config_path}): exit={exc.code}"
        ) from exc
    used = _sum_last_24h(Path(events_path), now)
    projected = used + estimated_credits
    remaining = budget - projected

    def _fmt(n: float) -> int | float:
        return int(n) if float(n).is_integer() else n

    return {
        "budget_per_day": budget,
        "used_24h": _fmt(used),
        "estimated_credits": _fmt(estimated_credits),
        "projected": _fmt(projected),
        "remaining": _fmt(remaining),
        "exceeded": projected > budget,
    }


def _load_budget(config_path: Path) -> int:
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except FileNotFoundError:
        _log(f"project-config not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        _log(f"project-config malformed: {exc.msg} (line {exc.lineno})")
        sys.exit(1)
    dfs = cfg.get("dataforseo") or {}
    budget = dfs.get("budget_credits_per_day", 500)
    if not isinstance(budget, int) or budget < 0:
        _log(f"invalid budget_credits_per_day: {budget!r}")
        sys.exit(1)
    return budget


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Budget pre-flight check (§16.8)")
    parser.add_argument(
        "--project-config", default="project.config.json",
        help="path to project config (default: project.config.json — projects/{slug}/project.config.json per ADR-033)"
    )
    parser.add_argument(
        "--events", default="_state/events.jsonl",
        help="path to events.jsonl (default: _state/events.jsonl)"
    )
    args = parser.parse_args(argv)

    budget = _load_budget(Path(args.project_config))
    used = _sum_last_24h(Path(args.events), datetime.now(timezone.utc))
    remaining = budget - used
    exceeded = used > budget

    # Normalize to int when whole; preserve float otherwise (credits may be fractional).
    def _fmt(n: float) -> int | float:
        return int(n) if float(n).is_integer() else n

    payload = {
        "budget_per_day": budget,
        "used_24h": _fmt(used),
        "remaining": _fmt(remaining),
        "exceeded": exceeded,
    }
    print(json.dumps(payload, separators=(",", ":")))
    return 1 if exceeded else 0


if __name__ == "__main__":
    sys.exit(main())
