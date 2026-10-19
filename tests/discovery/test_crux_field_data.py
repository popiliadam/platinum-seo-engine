"""S-19 — real-user (CrUX, mobile p75) Core Web Vitals are the primary source.

The tech audit used only Lighthouse lab data, desktop by default, with TBT as
an INP stand-in. Field data from the CrUX API now reaches the report with its
source named; lab stays diagnostic.
"""
from __future__ import annotations

from pathlib import Path

from scripts.discovery import crux_field as cf
from scripts.discovery import tech_audit_transform as tat

URL = "https://x.test/kombi/"


def _resp(*, inp=310, lcp=2100, cls="0.31", ttfb=700, scope="url") -> dict:
    key = {"formFactor": "PHONE", scope: URL if scope == "url" else "https://x.test"}
    return {"record": {"key": key, "metrics": {
        "interaction_to_next_paint": {"percentiles": {"p75": inp}},
        "largest_contentful_paint": {"percentiles": {"p75": lcp}},
        "cumulative_layout_shift": {"percentiles": {"p75": cls}},
        "experimental_time_to_first_byte": {"percentiles": {"p75": ttfb}},
        "round_trip_time": {"percentiles": {"p75": 90}},
    }}}


def test_google_thresholds() -> None:
    assert cf.rate("interaction_to_next_paint", 200) == "good"
    assert cf.rate("interaction_to_next_paint", 201) == "needs_improvement"
    assert cf.rate("interaction_to_next_paint", 501) == "poor"
    assert cf.rate("largest_contentful_paint", 4001) == "poor"
    assert cf.rate("cumulative_layout_shift", 0.1) == "good"


def test_parse_record_reads_p75_including_string_cls() -> None:
    sig = cf.parse_record(_resp())
    by = {m.name: m for m in sig.metrics}
    assert set(by) == {"INP", "LCP", "CLS", "TTFB"}
    assert by["CLS"].p75 == 0.31 and by["CLS"].rating == "poor"
    assert sig.scope == "url" and sig.form_factor == "PHONE"
    assert cf.parse_record({}) is None


def test_report_carries_field_inp_and_its_source() -> None:
    out = tat.transform(lighthouse_raw=None, content_parsing_raw=None, crux_raw=[_resp()])
    perf = next(r for r in out["tech_seo"] if r["issue_category"] == "Performance")
    assert "Field INP 310ms" in perf["detail"] and "CrUX url-level p75, phone" in perf["detail"]
    layout = next(r for r in out["tech_seo"] if r["issue_category"] == "Layout Stability")
    assert layout["impact"] == "HIGH" and "Field CLS 0.31" in layout["detail"]
    assert out["meta"]["field_url_count"] == 1


def test_origin_fallback_is_labelled() -> None:
    out = tat.transform(lighthouse_raw=None, content_parsing_raw=None,
                        crux_raw=[_resp(scope="origin")])
    assert "CrUX origin-level p75" in out["tech_seo"][0]["detail"]


def test_all_good_field_data_adds_no_rows() -> None:
    good = _resp(inp=150, lcp=1800, cls="0.02", ttfb=500)
    out = tat.transform(lighthouse_raw=None, content_parsing_raw=None, crux_raw=[good])
    assert out["tech_seo"] == [] and out["meta"]["field_url_count"] == 1


def test_no_fid_left_in_tech_audit() -> None:
    root = Path(__file__).resolve().parents[2]
    src = (root / "scripts" / "discovery" / "tech_audit_transform.py").read_text(encoding="utf-8")
    assert "FID/INP" not in src
    skill = (root / "skills" / "discovery" / "tech-audit" / "SKILL.md").read_text(encoding="utf-8")
    assert "crux_raw" in skill and "CRUX_API_KEY" in skill
    assert "CrUX field-data\nintegration is deferred" not in skill
