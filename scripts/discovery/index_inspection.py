#!/usr/bin/env python3
"""index_inspection.py — read a URL Inspection API result correctly (S-21).

verify-indexing compared the raw ``coverageState`` sentence ("Submitted and
indexed", "Crawled - currently not indexed", …) with its own enum
(indexed / not_indexed / crawled_not_indexed), so every URL came out as a
mismatch, and it capped runs at 200 URLs a day although the URL Inspection
API allows 2,000 a day (600 a minute) per property.

``classify`` decides from ``indexStatusResult.verdict`` first (PASS = in the
index) and uses ``coverageState`` only to tell "crawled, not indexed" apart.
A response without an index status is ``unknown`` — never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

URL_INSPECTION_DAILY_QUOTA = 2000   # per property per day (Search Console API limits)
URL_INSPECTION_PER_MINUTE = 600
STATUSES = ("indexed", "not_indexed", "crawled_not_indexed", "unknown")


@dataclass(frozen=True)
class Inspection:
    status: str
    verdict: str
    coverage_state: str
    reason: str


def classify(raw: dict) -> Inspection:
    """URL Inspection API response → one of STATUSES (pure)."""
    result = ((raw or {}).get("inspectionResult") or {}).get("indexStatusResult")
    if not isinstance(result, dict):
        return Inspection("unknown", "", "", "no indexStatusResult in the response")
    verdict = str(result.get("verdict") or "")
    coverage = str(result.get("coverageState") or "")
    lowered = coverage.casefold()
    if verdict == "PASS":
        return Inspection("indexed", verdict, coverage, coverage or "verdict PASS")
    if "crawled" in lowered and "not indexed" in lowered:
        return Inspection("crawled_not_indexed", verdict, coverage, coverage)
    if verdict in ("FAIL", "NEUTRAL", "PARTIAL") or coverage:
        reason = coverage or f"verdict {verdict}"
        indexing_state = result.get("indexingState")
        if indexing_state and indexing_state != "INDEXING_ALLOWED":
            reason = f"{reason} ({indexing_state})"
        return Inspection("not_indexed", verdict, coverage, reason)
    return Inspection("unknown", verdict, coverage, "verdict unspecified")


def run_cap(requested: int, *, used_today: int = 0,
            daily_quota: int = URL_INSPECTION_DAILY_QUOTA) -> int:
    """How many URLs this run may inspect without exceeding the daily quota."""
    return max(0, min(requested, daily_quota - used_today))


__all__ = ("URL_INSPECTION_DAILY_QUOTA", "URL_INSPECTION_PER_MINUTE", "STATUSES",
           "Inspection", "classify", "run_cap")
