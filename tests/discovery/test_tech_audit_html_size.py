"""S-20 — Googlebot reads only the first 2 MB of an HTML file; flag pages near it.

The tech audit had no page-size check. SF's internal_all export carries the
uncompressed response size per URL ("Size (bytes)"); HTML over 1.5 MB is a
MEDIUM warning, over 2 MB is HIGH (content past the cut-off is not indexed).
"""
from __future__ import annotations

from scripts.discovery.tech_audit_transform import transform

MB = 1024 * 1024


def _rows(sizes: list[tuple[str, int, str]]) -> list[dict]:
    page_sizes = [{"Address": u, "Size (bytes)": str(b), "Content Type": ct} for u, b, ct in sizes]
    return transform(lighthouse_raw=None, content_parsing_raw=None, page_sizes=page_sizes)["tech_seo"]


def test_html_over_2mb_is_high() -> None:
    rows = _rows([("https://x.test/big", int(2.3 * MB), "text/html; charset=utf-8")])
    perf = [r for r in rows if "2 MB" in r["detail"] or "MB HTML" in r["detail"]]
    assert perf and perf[0]["impact"] == "HIGH"
    assert "https://x.test/big" in perf[0]["affected_urls"]


def test_html_over_1_5mb_is_medium() -> None:
    rows = _rows([("https://x.test/heavy", int(1.7 * MB), "text/html")])
    assert rows and rows[0]["impact"] == "MEDIUM"


def test_small_pages_and_non_html_are_ignored() -> None:
    assert _rows([("https://x.test/ok", 300_000, "text/html"),
                  ("https://x.test/video.mp4", 50 * MB, "video/mp4")]) == []


def test_no_page_sizes_keeps_old_behaviour() -> None:
    out = transform(lighthouse_raw=None, content_parsing_raw=None)
    assert out["tech_seo"] == []
