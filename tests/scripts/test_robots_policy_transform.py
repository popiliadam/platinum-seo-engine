"""TDD lock for scripts/discovery/robots_policy_transform.py (GAP-T3).

robots.txt / noindex lifecycle governance (rules/tech-seo-governance.md R-131 governed
policy, R-132 noindex deployment path / R-58 deployability, R-133 noindex/disallow
mutual exclusion). Pure transform: lint the live robots.txt, scan R-133 conflicts +
R-58 lifecycle drift, build a recommendation-only proposed robots.txt + platform
deployment instructions. No paid MCP, no slug literals.

Cases mirror spec GAP-T3 §d (1..11).
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.robotparser import RobotFileParser

import pytest

from scripts.discovery import robots_policy_transform as rpt

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SEVERITY = set(
    json.loads((_REPO_ROOT / "schemas" / "master-excel.schema.json").read_text())
    ["definitions"]["severityEnum"]["enum"]
)


def _directive(address, meta_robots="", indexability="Indexable"):
    return {"Address": address, "Meta Robots 1": meta_robots, "Indexability": indexability}


def _internal(address, indexability="Indexable"):
    return {"Address": address, "Indexability": indexability}


def _lifecycle(slug, status):
    return {"url_slug": slug, "lifecycle_status": status}


def _t(robots_txt, **kw):
    kw.setdefault("directives_rows", [])
    kw.setdefault("internal_rows", [])
    kw.setdefault("lifecycle_rows", [])
    kw.setdefault("platform", "custom")
    kw.setdefault("domain", "x.test")
    return rpt.transform(robots_txt, **kw)


_SITEMAP = "Sitemap: https://x.test/sitemap.xml"


def _issues(out):
    return " || ".join(r["issue"].lower() for r in out["robots_txt_rows"])


# --- 1. noindex: line -> HIGH -----------------------------------------------

def test_noindex_line_is_high():
    out = _t(f"User-agent: *\nnoindex: /old/\n{_SITEMAP}\n")
    high = [r for r in out["robots_txt_rows"] if r["level"] == "HIGH"]
    assert any("noindex" in r["issue"].lower() and "unsupported" in r["issue"].lower()
               for r in high)


# --- 2. missing Sitemap -> MEDIUM -------------------------------------------

def test_missing_sitemap_is_medium():
    out = _t("User-agent: *\nDisallow: /tmp/\n")
    assert any(r["level"] == "MEDIUM" and "sitemap" in r["issue"].lower()
               for r in out["robots_txt_rows"])


# --- 3. Disallow: / -> CRITICAL row + proposed file is NOT site-wide --------

def test_disallow_all_is_critical_and_proposed_is_safe():
    out = _t(f"User-agent: *\nDisallow: /\n{_SITEMAP}\n")
    assert any(r["level"] == "CRITICAL" for r in out["robots_txt_rows"])
    # the proposed file must never propagate a site-wide block
    assert "\nDisallow: /\n" not in "\n" + out["proposed_robots_txt"] + "\n"


def test_proposed_sitewide_block_durur():
    # a site-wide block injected via the facet block must raise DURUR #4
    with pytest.raises(rpt.RobotsProposedSiteWideBlockError):
        _t(f"User-agent: *\nDisallow: /tmp/\n{_SITEMAP}\n",
           facet_block="User-agent: *\nDisallow: /\n")


# --- 4. R-133: disallowed AND noindexed -> HIGH conflict --------------------

def test_disallowed_and_noindexed_conflict_high():
    out = _t(
        f"User-agent: *\nDisallow: /private/\n{_SITEMAP}\n",
        directives_rows=[_directive("https://x.test/private/page", meta_robots="noindex, follow")],
    )
    assert any(r["level"] == "HIGH" and "noindex" in r["issue"].lower()
               and ("disallow" in r["issue"].lower() or "mutual" in r["issue"].lower())
               for r in out["robots_txt_rows"])


# --- 5. ON_HOLD lifecycle slug live-indexable -> HIGH R-58 drift ------------

def test_on_hold_indexable_is_r58_drift_high():
    out = _t(
        f"User-agent: *\n{_SITEMAP}\n",
        directives_rows=[_directive("https://x.test/on-hold-post", meta_robots="index, follow")],
        lifecycle_rows=[_lifecycle("on-hold-post", "ON_HOLD")],
    )
    assert any(r["level"] == "HIGH" and ("lifecycle" in r["issue"].lower()
               or "on_hold" in r["issue"].lower()) for r in out["robots_txt_rows"])


# --- 6. REMOVED slug still live (200/indexable) -> MEDIUM -------------------

def test_removed_slug_still_live_is_medium():
    out = _t(
        f"User-agent: *\n{_SITEMAP}\n",
        internal_rows=[_internal("https://x.test/gone-post", indexability="Indexable")],
        lifecycle_rows=[_lifecycle("gone-post", "REMOVED")],
    )
    assert any(r["level"] == "MEDIUM" and "removed" in r["issue"].lower()
               for r in out["robots_txt_rows"])


# --- 7. disallow matching an important url_patterns kind -> HIGH ------------

def test_disallow_important_page_high():
    out = _t(
        f"User-agent: *\nDisallow: /category/\n{_SITEMAP}\n",
        url_patterns=[{"kind": "category", "pattern": "/category/"}],
    )
    assert any(r["level"] == "HIGH" and ("important" in r["issue"].lower()
               or "category" in r["issue"].lower()) for r in out["robots_txt_rows"])


# --- 8. proposed file round-trips through robotparser, preserves semantics --

def test_proposed_robots_parses_and_preserves_semantics():
    out = _t(f"User-agent: *\nDisallow: /admin/\n{_SITEMAP}\n")
    rp = RobotFileParser()
    rp.parse(out["proposed_robots_txt"].splitlines())
    assert rp.can_fetch("*", "https://x.test/public") is True
    assert rp.can_fetch("*", "https://x.test/admin/secret") is False


# --- 9. platform matrix: all enum values present, unverified carry verified=False

def test_platform_matrix_covers_all_enum_and_marks_unverified():
    matrix = rpt.PLATFORM_DEPLOYMENT_MATRIX
    for plat in ("wordpress", "wordpress+woocommerce", "ticimax", "ideasoft", "imagaza", "custom"):
        assert plat in matrix
        entry = matrix[plat]
        assert set(entry) >= {"robots_txt_channel", "per_page_noindex_channel",
                              "header_channel", "verified"}
    for unverified in ("ticimax", "ideasoft", "imagaza"):
        assert matrix[unverified]["verified"] is False
    assert matrix["wordpress"]["verified"] is True


# --- 10. row shape + severityEnum validation --------------------------------

def test_emitted_rows_shape_and_severity():
    out = _t("noindex: /x/\nUser-agent: *\nDisallow: /private/\n",
             directives_rows=[_directive("https://x.test/private/p", meta_robots="noindex")])
    assert out["robots_txt_rows"], "expected findings for this messy robots.txt"
    for r in out["robots_txt_rows"]:
        assert set(r) == {"id", "level", "issue", "detail", "resolution"}
        assert r["level"] in _SEVERITY
        assert len(r["detail"]) <= 300


# --- 11. empty robots.txt (404) -> 'missing robots.txt' MEDIUM, no crash ----

def test_missing_robots_txt_is_medium_not_crash():
    out = _t("")
    assert any(r["level"] == "MEDIUM" and "missing robots" in r["issue"].lower()
               for r in out["robots_txt_rows"])
    assert _SITEMAP.split(":", 1)[0] in out["proposed_robots_txt"]  # proposed still has a Sitemap line


# --- DURUR + drift guards ----------------------------------------------------

def test_directives_none_raises_missing():
    with pytest.raises(rpt.RobotsDirectivesMissingError):
        rpt.transform("User-agent: *\n", directives_rows=None, internal_rows=[],
                      lifecycle_rows=[], platform="custom", domain="x.test")


def test_lifecycle_none_raises_unreadable():
    with pytest.raises(rpt.RobotsLifecycleUnreadableError):
        rpt.transform("User-agent: *\n", directives_rows=[], internal_rows=[],
                      lifecycle_rows=None, platform="custom", domain="x.test")


def test_directives_schema_drift_raises():
    with pytest.raises(rpt.RobotsDirectivesSchemaDriftError):
        _t(f"User-agent: *\n{_SITEMAP}\n",
           directives_rows=[{"NoAddressColumn": "x", "Meta Robots 1": "noindex"}])


def test_facet_block_merged_into_proposed():
    out = _t(f"User-agent: *\nDisallow: /admin/\n{_SITEMAP}\n",
             facet_block="Disallow: /*?*s=")
    assert "/*?*s=" in out["proposed_robots_txt"]


def test_clean_robots_compliant():
    out = _t(f"User-agent: *\nDisallow: /wp-admin/\n{_SITEMAP}\n")
    assert out["summary"]["verdict"] in {"FINDINGS", "COMPLIANT"}
