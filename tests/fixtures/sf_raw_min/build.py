#!/usr/bin/env python3
"""Generate the synthetic SF export in this folder (K-05). Run from anywhere:

    python3 tests/fixtures/sf_raw_min/build.py
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = "https://example.test"

PAGES = [  # path, status, indexable, title, meta, h1
    ("/", 200, True, "Example Home", "Example home page.", "Welcome"),
    ("/kombi/", 200, True, "Kombi Servisi", "Kombi bakım ve onarım.", "Kombi Servisi"),
    ("/klima/", 200, True, "", "Klima montajı.", "Klima"),
    ("/blog/bakim/", 200, True, "Bakım Rehberi", "", "Bakım Rehberi"),
    ("/etiket/eski/", 200, False, "Etiket", "Etiket sayfası.", "Etiket"),
]


def _write(name: str, header: list[str], rows: list[list]) -> None:
    with (HERE / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerows(rows)


def _idx(ok: bool) -> list[str]:
    return ["Indexable", ""] if ok else ["Non-Indexable", "noindex"]


def build() -> None:
    _write("internal_all",
           ["Address", "Content Type", "Status Code", "Status", "Indexability",
            "Indexability Status", "Title 1", "Meta Description 1", "H1-1", "Inlinks"],
           [[H + p, "text/html; charset=UTF-8", s, "OK", *_idx(i), t, m, h, 3]
            for p, s, i, t, m, h in PAGES]
           + [[H + "/img/logo.png", "image/png", 200, "OK", "Indexable", "", "", "", "", 5],
              [H + "/style.css", "text/css", 200, "OK", "Indexable", "", "", "", "", 5],
              [H + "/app.js", "application/javascript", 200, "OK", "Indexable", "", "", "", "", 5]])
    _write("sitemaps_all",
           ["Address", "Content Type", "Status Code", "Status", "Indexability", "Indexability Status"],
           [[H + p, "text/html", 200, "OK", *_idx(i)] for p, _s, i, *_ in PAGES[:4]])
    _write("response_codes_all",
           ["Address", "Content Type", "Status Code", "Status", "Indexability",
            "Indexability Status", "Inlinks", "Response Time", "Redirect URL", "Redirect Type"],
           [[H + "/eski-kombi/", "text/html", 301, "Moved Permanently", "Non-Indexable",
             "Redirected", 4, 0.1, H + "/kombi/", "HTTP Redirect"],
            [H + "/yok/", "text/html", 404, "Not Found", "Non-Indexable", "Client Error",
             2, 0.1, "", ""],
            ["https://other.test/x", "text/html", 301, "Moved Permanently", "Non-Indexable",
             "Redirected", 1, 0.1, "https://other.test/y", "HTTP Redirect"]]
           + [[H + p, "text/html", 200, "OK", *_idx(i), 3, 0.1, "", ""] for p, _s, i, *_ in PAGES])
    _write("structured_data_all",
           ["Address", "Errors", "Warnings", "Total Types", "Unique Types", "Type-1", "Type-2",
            "Indexability", "Indexability Status"],
           [[H + "/", 0, 0, 2, 2, "Organization", "WebSite", "Indexable", ""],
            [H + "/kombi/", 1, 2, 1, 1, "Service", "", "Indexable", ""],
            [H + "/blog/bakim/", 0, 1, 1, 1, "Article", "", "Indexable", ""]])
    _write("page_titles_all",
           ["Address", "Occurrences", "Title 1", "Title 1 Length", "Title 1 Pixel Width",
            "Indexability", "Indexability Status"],
           [[H + p, 1, t, len(t), len(t) * 8, *_idx(i)] for p, _s, i, t, *_ in PAGES])
    _write("meta_description_all",
           ["Address", "Occurrences", "Meta Description 1", "Meta Description 1 Length",
            "Meta Description 1 Pixel Width", "Indexability", "Indexability Status"],
           [[H + p, 1, m, len(m), len(m) * 6, *_idx(i)] for p, _s, i, _t, m, _h in PAGES])
    _write("h1_all",
           ["Address", "Occurrences", "H1-1", "H1-1 Length", "Indexability", "Indexability Status"],
           [[H + p, 1, h, len(h), *_idx(i)] for p, _s, i, _t, _m, h in PAGES])
    _write("issues_overview_report",
           ["Issue Name", "Issue Type", "Issue Priority", "URLs", "% of Total",
            "Description", "How To Fix"],
           [["Page Titles: Missing", "Issue", "High", 1, 20.0,
             "Pages without a title.", "Add a unique title."],
            ["Meta Description: Missing", "Opportunity", "Medium", 1, 20.0,
             "Pages without a meta description.", "Write a meta description."],
            ["Response Codes: Internal Client Error (4xx)", "Issue", "High", 1, 10.0,
             "Internal URLs returning 4xx.", "Fix or redirect the URL."],
            ["Directives: Noindex", "Warning", "Low", 1, 20.0,
             "Pages carrying noindex.", "Check the noindex is intended."]])


if __name__ == "__main__":
    build()
