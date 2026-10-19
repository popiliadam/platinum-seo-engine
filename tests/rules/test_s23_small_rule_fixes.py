"""S-23 — small rule corrections (non-validator part).

R-58 said noindex blocks crawling (it does not); the content-version meta tag is
not a standard any engine reads; hreflang "en-gb" was rejected although values
are case-insensitive; the 990px description cap was generous; decay had no
volume floor and read only ``profile`` so YMYL projects fell silently to the
default thresholds; R-85 and R-88 each had three conflicting definitions.
"""
from __future__ import annotations

from pathlib import Path

from scripts.discovery import content_decay_transform as cd
from scripts.discovery import hreflang_audit_transform as ha

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_r58_noindex_does_not_block_crawling() -> None:
    text = _read("rules/content-html-discipline.md")
    assert "crawl etmesin" not in text and "taramayı ENGELLEMEZ" in text


def test_no_content_version_meta_on_pages() -> None:
    for rel in ("templates/content/new-blog.template.html",
                "templates/content/upload-instructions.template.md",
                "skills/production/revise-content/SKILL.md"):
        assert '<meta name="content-version"' not in _read(rel), rel
    assert "version.json" in _read("rules/content-llm-discipline.md")


def test_hreflang_lowercase_region_is_valid() -> None:
    assert ha._code_issue("en-gb") is None and ha._code_issue("en-GB") is None
    assert ha._code_issue("en-uk") is not None


def test_description_cap_is_920px() -> None:
    assert "≤ 920px" in _read("rules/content-html-discipline.md")
    assert "990px" not in _read("skills/production/new-blog/SKILL.md")


def _payload(rows):
    return {"rows": [{"keys": [u], "clicks": c, "impressions": i, "position": p} for u, c, i, p in rows]}


def test_decay_volume_floor() -> None:
    prev = _payload([("https://x.test/a", 3, 100, 4.0), ("https://x.test/b", 100, 1000, 4.0)])
    cur = _payload([("https://x.test/a", 1, 60, 12.0), ("https://x.test/b", 40, 900, 12.0)])
    out = cd.transform(recent=cur, previous=prev, profile_config={})
    trend = {r["url"]: r["trend"] for r in out["content_decay"]}
    assert trend["https://x.test/a"] == "STABLE" and trend["https://x.test/b"] == "DECAY"
    assert out["meta"]["min_previous_clicks"] == 10


def test_ymyl_thresholds_read_from_profiles_list_and_reported() -> None:
    clicks, pos = cd._resolve_thresholds({"profiles": ["ymyl-high", "local-service"]})
    assert (clicks, pos) == (-20.0, 3.0)
    assert cd._threshold_profile({"profiles": ["ymyl-high"]})["threshold_profile"] == "ymyl"
    none = cd._threshold_profile({})
    assert none["threshold_profile_source"] == "none" and "default" in none["threshold_profile_note"]


def test_r85_r88_single_definitions_cited() -> None:
    rules = _read("rules/content-update-discipline.md")
    assert rules.count("TEK TANIM") >= 2
    revise = _read("skills/production/revise-content/SKILL.md")
    assert "clicks_delta < -20%" not in revise and "word_delta == 0" not in revise
    assert "abs(word_delta) < 50" in revise and "abs(word_delta) < 50" in rules
    remediation = _read("skills/production/content-remediation/SKILL.md")
    assert "3/5" not in remediation
