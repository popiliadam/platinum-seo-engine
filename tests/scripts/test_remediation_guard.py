"""S-25 / S-12 — the delete/410 decision is checked in CODE, not left to the model.

S-25: a page with real value (600+ words, clicks in the last 16 months, or
      external links) can never be deleted or 410'd; the request becomes a merge
      (301 to a target) or a rewrite. Missing signals cannot prove a page safe.
      Prune candidates: 0 clicks and < 50 impressions in 90 days, not published
      in the last 3 months.
S-12: a 410'd URL must stay crawlable (no robots Disallow), otherwise Google
      never sees the 410.
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts.production.remediation_guard import PageSignals, guard

TODAY = date(2026, 10, 19)


def _page(**kw) -> PageSignals:
    base = dict(url="https://x.test/p", word_count=300, clicks_16m=0, external_links=0,
                clicks_90d=0, impressions_90d=10, published=date(2025, 1, 1))
    base.update(kw)
    return PageSignals(**base)


def test_thin_dead_old_page_may_be_deleted() -> None:
    d = guard("delete", _page(), today=TODAY, merge_target=None)
    assert d.action == "delete" and d.removal_allowed
    assert d.robots_disallow is False  # S-12: never block a 410'd URL


@pytest.mark.parametrize("signals, reason", [
    ({"word_count": 800}, "600"),
    ({"clicks_16m": 3}, "16"),
    ({"external_links": 2}, "external"),
])
def test_valuable_page_cannot_be_deleted(signals: dict, reason: str) -> None:
    d = guard("delete", _page(**signals), today=TODAY, merge_target=None)
    assert d.action == "rewrite" and not d.removal_allowed
    assert any(reason in r for r in d.reasons)


def test_valuable_page_with_a_target_is_merged() -> None:
    d = guard("prune", _page(word_count=1200), today=TODAY, merge_target="https://x.test/hub")
    assert d.action == "merge" and d.target == "https://x.test/hub"


@pytest.mark.parametrize("missing", ["word_count", "clicks_16m", "external_links"])
def test_unknown_signal_vetoes_removal(missing: str) -> None:
    d = guard("delete", _page(**{missing: None}), today=TODAY, merge_target=None)
    assert not d.removal_allowed


@pytest.mark.parametrize("signals", [
    {"clicks_90d": 1},
    {"impressions_90d": 50},
    {"published": date(2026, 9, 1)},
])
def test_prune_needs_the_low_activity_filter(signals: dict) -> None:
    d = guard("prune", _page(**signals), today=TODAY, merge_target=None)
    assert not d.removal_allowed


def test_redirect_is_not_a_removal() -> None:
    d = guard("redirect", _page(word_count=2000), today=TODAY, merge_target="https://x.test/t")
    assert d.action == "redirect" and d.robots_disallow is False
