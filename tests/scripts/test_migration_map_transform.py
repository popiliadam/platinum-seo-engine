"""TDD lock for scripts/planning/migration_map_transform.py (GAP-T4).

Site-migration / redirect-map playbook (rules/tech-seo-governance.md R-134..R-136).
Pure two-mode transform:
  * build_map — expand explicit old→new pairs + ordered regex rules over the full
    old-site crawl inventory; lint loops / chains>3 / homepage-collapse /
    traffic-critical-unmapped; emit redirect_404-shaped rows. Silent drops are
    forbidden (every old URL is a row OR listed unmapped — R-134).
  * verify_map — per R-136 confirm old→single-hop-301→200; flag 302-leaks, chain>3,
    404 regressions, homepage drift. Header-tolerant with a drift guard.

Cases mirror spec GAP-T4 §d (1..12) + the R-134/R-136 behaviors the spec mandates.
No paid MCP, no slug literals.

Chain-depth note: R-134 fixes the ceiling at "≤ 3 hops"; this transform flags a
resolved chain with > 3 HOPS (edges). The spec's illustrative "A→B→C→D" prose is a
loose example — the binding number is R-134's ≤3, so the violation fixture below
uses a clearly-over-ceiling 4-hop chain (A→B→C→D→E) and the boundary 3-hop chain
is asserted clean.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.planning import migration_map_transform as mmt

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STATUS = set(
    json.loads((_REPO_ROOT / "schemas" / "master-excel.schema.json").read_text())
    ["definitions"]["statusEnum"]["enum"]
)
_REDIRECT_COLS = {"url", "inlinks", "action", "target_url", "status"}


def _inv(address, inlinks=0):
    return {"Address": address, "Inlinks": inlinks}


def _pair(old, new, action="301"):
    return {"old_url": old, "new_url": new, "action": action}


def _rule(match, replace, action="301", order=1):
    return {"match": match, "replace": replace, "action": action, "order": order}


def _gsc(url, clicks=0, impressions=0):
    return {"url": url, "clicks": clicks, "impressions": impressions}


# --- 1. explicit pair expands to a redirect_404 row -------------------------

def test_explicit_pair_expands_to_redirect_row():
    out = mmt.build_map([], [_pair("https://x.test/a", "https://x.test/b")], [], [])
    rows = out["redirect_rows"]
    assert len(rows) == 1
    r = rows[0]
    assert set(r) == _REDIRECT_COLS
    assert r["url"] == "https://x.test/a"
    assert r["target_url"] == "https://x.test/b"
    assert r["action"] == "301"
    assert r["status"] == "TODO"


# --- 2. regex rule maps /old-blog/(.*) -> /blog/$1 --------------------------

def test_regex_rule_expands_over_inventory():
    inv = [_inv("https://x.test/old-blog/foo")]
    out = mmt.build_map(inv, [], [_rule(r"/old-blog/(.*)$", r"/blog/$1")], [])
    rows = out["redirect_rows"]
    assert len(rows) == 1
    assert rows[0]["url"] == "https://x.test/old-blog/foo"
    assert rows[0]["target_url"] == "https://x.test/blog/foo"
    assert rows[0]["action"] == "301"


def test_regex_rule_backslash_group_also_supported():
    inv = [_inv("https://x.test/eski/bar")]
    out = mmt.build_map(inv, [], [_rule(r"/eski/(.*)$", r"/yeni/\1")], [])
    assert out["redirect_rows"][0]["target_url"] == "https://x.test/yeni/bar"


def test_rule_order_first_match_wins():
    inv = [_inv("https://x.test/old-blog/foo")]
    rules = [
        _rule(r"/old-blog/(.*)$", r"/blog/$1", order=2),
        _rule(r"/old-blog/foo$", r"/special", order=1),  # lower order wins
    ]
    out = mmt.build_map(inv, [], rules, [])
    assert out["redirect_rows"][0]["target_url"] == "https://x.test/special"


# --- 3. unmapped URL is listed, never silently dropped ----------------------

def test_unmapped_url_listed_never_dropped():
    inv = [_inv("https://x.test/orphan")]
    out = mmt.build_map(inv, [], [], [])
    assert "https://x.test/orphan" in out["unmapped"]
    # invariant: every inventory URL is either a redirect row or listed unmapped
    mapped = {r["url"] for r in out["redirect_rows"]}
    assert "https://x.test/orphan" in mapped or "https://x.test/orphan" in out["unmapped"]
    assert out["redirect_rows"] == []  # nothing fabricated


# --- 4. loop A->B->A is RED -------------------------------------------------

def test_loop_is_red():
    pairs = [_pair("https://x.test/a", "https://x.test/b"),
             _pair("https://x.test/b", "https://x.test/a")]
    out = mmt.build_map([], pairs, [], [])
    assert out["lint"]["loops"], "A->B->A loop must be detected"
    assert out["lint"]["verdict"] == "RED"


def test_self_redirect_is_red():
    out = mmt.build_map([], [_pair("https://x.test/a", "https://x.test/a")], [], [])
    assert out["lint"]["loops"]
    assert out["lint"]["verdict"] == "RED"


# --- 5. chain depth > 3 hops -> violation -----------------------------------

def test_chain_over_three_hops_flagged():
    pairs = [_pair("https://x.test/a", "https://x.test/b"),
             _pair("https://x.test/b", "https://x.test/c"),
             _pair("https://x.test/c", "https://x.test/d"),
             _pair("https://x.test/d", "https://x.test/e")]  # A resolves in 4 hops
    out = mmt.build_map([], pairs, [], [])
    assert out["lint"]["chains_over_max"], "a 4-hop chain must exceed the ≤3 ceiling"


def test_chain_at_three_hops_is_clean():
    pairs = [_pair("https://x.test/a", "https://x.test/b"),
             _pair("https://x.test/b", "https://x.test/c"),
             _pair("https://x.test/c", "https://x.test/d")]  # exactly 3 hops — OK
    out = mmt.build_map([], pairs, [], [])
    assert not out["lint"]["chains_over_max"]


# --- 6. homepage-collapse > threshold -> HIGH -------------------------------

def test_homepage_collapse_over_threshold_high():
    pairs = [_pair(f"https://x.test/p{i}", f"https://x.test/t{i}") for i in range(18)]
    pairs += [_pair("https://x.test/h1", "https://x.test/"),
              _pair("https://x.test/h2", "https://x.test/")]  # 2/20 = 10% > 5%
    out = mmt.build_map([], pairs, [], [])
    assert out["lint"]["homepage_collapse_pct"] > 5.0
    assert out["lint"]["homepage_collapse_high"] is True


def test_homepage_collapse_under_threshold_not_high():
    pairs = [_pair(f"https://x.test/p{i}", f"https://x.test/t{i}") for i in range(99)]
    pairs += [_pair("https://x.test/h1", "https://x.test/")]  # 1/100 = 1% < 5%
    out = mmt.build_map([], pairs, [], [])
    assert out["lint"]["homepage_collapse_high"] is False


# --- 7. traffic-critical unmapped -> HIGH -----------------------------------

def test_gsc_traffic_unmapped_is_high():
    inv = [_inv("https://x.test/money-page")]
    gsc = [_gsc("https://x.test/money-page", clicks=120, impressions=3000)]
    out = mmt.build_map(inv, [], [], gsc)
    assert "https://x.test/money-page" in out["lint"]["traffic_critical_unmapped"]


def test_gsc_zero_click_unmapped_not_flagged_critical():
    inv = [_inv("https://x.test/dead-page")]
    gsc = [_gsc("https://x.test/dead-page", clicks=0, impressions=0)]
    out = mmt.build_map(inv, [], [], gsc)
    assert "https://x.test/dead-page" not in out["lint"]["traffic_critical_unmapped"]
    assert "https://x.test/dead-page" in out["unmapped"]


# --- 8. 410 action row: empty target, valid shape ---------------------------

def test_410_row_has_empty_target_and_valid_status():
    out = mmt.build_map([], [_pair("https://x.test/gone", "", action="410")], [], [])
    r = out["redirect_rows"][0]
    assert r["action"] == "410"
    assert r["target_url"] == ""
    assert r["status"] in _STATUS


def test_unmatched_default_410_emits_gone_rows():
    inv = [_inv("https://x.test/orphan")]
    out = mmt.build_map(inv, [], [], [], unmatched_default="410")
    rows = [r for r in out["redirect_rows"] if r["url"] == "https://x.test/orphan"]
    assert rows and rows[0]["action"] == "410" and rows[0]["target_url"] == ""
    assert "https://x.test/orphan" not in out["unmapped"]


# --- 9. verify: single-hop 301 -> 200 marks verified ------------------------

def _rrow(url, target, action="301"):
    return {"url": url, "inlinks": 0, "action": action,
            "target_url": target, "status": "TODO"}


def test_verify_single_hop_301_200_verified():
    rows = [_rrow("https://x.test/a", "https://x.test/b")]
    chains = [{"Address": "https://x.test/a", "Redirect Type 1": "301 Moved Permanently",
               "Number of Redirects": 1, "Final Address": "https://x.test/b",
               "Final Status Code": "200"}]
    out = mmt.verify_map(rows, chains, [])
    assert any(v["url"] == "https://x.test/a" for v in out["verified"])
    assert out["violations"] == []


# --- 10. verify: 302 instead of 301 -> violation ----------------------------

def test_verify_302_is_violation():
    rows = [_rrow("https://x.test/a", "https://x.test/b")]
    chains = [{"Address": "https://x.test/a", "Redirect Type 1": "302",
               "Number of Redirects": 1, "Final Address": "https://x.test/b",
               "Final Status Code": "200"}]
    out = mmt.verify_map(rows, chains, [])
    assert any("302" in (v["issue"] + v["detail"]) for v in out["violations"])


def test_verify_404_regression_is_violation():
    rows = [_rrow("https://x.test/a", "https://x.test/b")]
    chains = [{"Address": "https://x.test/a", "Redirect Type 1": "301",
               "Number of Redirects": 1, "Final Address": "https://x.test/b",
               "Final Status Code": "404"}]
    out = mmt.verify_map(rows, chains, [])
    assert any("404" in (v["issue"] + v["detail"]) for v in out["violations"])


def test_verify_chain_over_three_is_violation():
    rows = [_rrow("https://x.test/a", "https://x.test/b")]
    chains = [{"Address": "https://x.test/a", "Redirect Type 1": "301",
               "Number of Redirects": 5, "Final Address": "https://x.test/b",
               "Final Status Code": "200"}]
    out = mmt.verify_map(rows, chains, [])
    assert any("chain" in v["issue"].lower() or "hop" in v["detail"].lower()
               for v in out["violations"])


# --- 11. verify: redirect_chains column drift -> error ----------------------

def test_verify_chain_column_drift_raises():
    rows = [_rrow("https://x.test/a", "https://x.test/b")]
    chains = [{"URL": "https://x.test/a", "Hops": 1}]  # no Address column
    with pytest.raises(mmt.RedirectChainsSchemaDriftError):
        mmt.verify_map(rows, chains, [])


# --- 12. statusEnum / row-shape validation ----------------------------------

def test_emitted_rows_shape_and_status_enum():
    inv = [_inv("https://x.test/old-blog/x", inlinks=4)]
    out = mmt.build_map(inv, [], [_rule(r"/old-blog/(.*)$", r"/blog/$1")], [])
    assert out["redirect_rows"], "rule should have produced a row"
    for r in out["redirect_rows"]:
        assert set(r) == _REDIRECT_COLS
        assert r["status"] in _STATUS
        assert r["action"] in {"301", "410"}
        assert isinstance(r["inlinks"], int)


def test_inlinks_carried_from_inventory():
    inv = [_inv("https://x.test/a", inlinks=42)]
    out = mmt.build_map(inv, [_pair("https://x.test/a", "https://x.test/b")], [], [])
    assert out["redirect_rows"][0]["inlinks"] == 42
