#!/usr/bin/env python3
"""remediation_guard.py — code veto on deleting / 410-ing a page (S-25, S-12).

content-remediation's 301/410 decision used to rest on the model's judgement,
and a model can propose removing a real, valuable article. This module is the
deterministic gate the skill must pass before Step 4 (R-91 decision tree):

  * A page with value — more than 600 words, any click in the last 16 months,
    or any external link — is NEVER deleted or 410'd. The request becomes
    ``merge`` (301 into ``merge_target``) when a target exists, else ``rewrite``
    (hand-off to revise-content). A missing signal cannot prove a page safe, so
    it vetoes too.
  * ``prune`` additionally requires the low-activity filter: 0 clicks and fewer
    than 50 impressions in the last 90 days, and not published in the last
    3 months.
  * A 410'd URL stays crawlable: the decision never carries a robots Disallow
    (S-12 / R-133 — a disallowed URL's 410 is never seen by Google).

Pure: no IO, ``today`` is passed in.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

VETO_MIN_WORDS = 600
PRUNE_MAX_IMPRESSIONS_90D = 50
PRUNE_MIN_AGE = timedelta(days=90)
REMOVAL_ACTIONS = frozenset({"delete", "prune"})


@dataclass(frozen=True)
class PageSignals:
    """What the guard needs to know about one URL (None = unknown)."""

    url: str
    word_count: int | None
    clicks_16m: int | None
    external_links: int | None
    clicks_90d: int | None
    impressions_90d: int | None
    published: date | None


@dataclass(frozen=True)
class GuardDecision:
    """The action content-remediation may carry out, and why."""

    action: str               # delete | prune | redirect | merge | rewrite
    removal_allowed: bool     # True only when a 410 may be served
    target: str | None        # 301 target for merge / redirect
    reasons: tuple[str, ...]
    robots_disallow: bool = False  # S-12: always False — keep 410 URLs crawlable


def _value_reasons(page: PageSignals) -> list[str]:
    reasons: list[str] = []
    if page.word_count is None or page.word_count > VETO_MIN_WORDS:
        reasons.append(f"word count {page.word_count} > {VETO_MIN_WORDS} (or unknown)")
    if page.clicks_16m is None or page.clicks_16m > 0:
        reasons.append(f"clicks in the last 16 months: {page.clicks_16m} (or unknown)")
    if page.external_links is None or page.external_links > 0:
        reasons.append(f"external links: {page.external_links} (or unknown)")
    return reasons


def _prune_filter_reasons(page: PageSignals, today: date) -> list[str]:
    reasons: list[str] = []
    if page.clicks_90d is None or page.clicks_90d > 0:
        reasons.append(f"clicks in 90 days: {page.clicks_90d} (prune needs 0)")
    if page.impressions_90d is None or page.impressions_90d >= PRUNE_MAX_IMPRESSIONS_90D:
        reasons.append(
            f"impressions in 90 days: {page.impressions_90d} "
            f"(prune needs < {PRUNE_MAX_IMPRESSIONS_90D})"
        )
    if page.published is None or today - page.published < PRUNE_MIN_AGE:
        reasons.append(f"published {page.published} (prune needs 3+ months)")
    return reasons


def guard(
    action: str, page: PageSignals, *, today: date, merge_target: str | None,
) -> GuardDecision:
    """Return the action content-remediation may take for ``page``.

    Non-removal actions (``redirect``) pass through. A removal that the value
    veto or the prune filter blocks is converted to ``merge`` / ``rewrite`` with
    the reasons, so the report can say exactly why the page was kept.
    """
    if action not in REMOVAL_ACTIONS:
        return GuardDecision(action, False, merge_target, ())
    blocked = _value_reasons(page)
    if action == "prune":
        blocked += _prune_filter_reasons(page, today)
    if not blocked:
        return GuardDecision(action, True, None, ())
    fallback = "merge" if merge_target else "rewrite"
    return GuardDecision(fallback, False, merge_target, tuple(blocked))


__all__ = ("PageSignals", "GuardDecision", "guard", "VETO_MIN_WORDS")
