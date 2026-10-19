"""K-05 — the SF projection path runs on CI against a synthetic export.

The live-crawl tests depend on gitignored operator data and skip everywhere
else, so CI never exercised SF projection. tests/fixtures/sf_raw_min is a small
synthetic export (real SF headers, example.test rows, no client data).
"""
from __future__ import annotations

from pathlib import Path

from scripts.excel import transaction
from scripts.ingestion import sf_import
from scripts.ingestion import sf_projection as P

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sf_raw_min"


def _projected() -> dict:
    return P.project_all(FIXTURE)


def test_every_sheet_has_rows_and_every_row_is_schema_valid() -> None:
    schema = transaction._load_schema(str(transaction._DEFAULT_SCHEMA_PATH))
    out = _projected()
    assert set(out) == set(P.PROJECTED_SHEETS)
    for sheet in P.PROJECTED_SHEETS:
        assert out[sheet], f"{sheet} produced no rows"
        validator = transaction._build_row_validator(schema, sheet)
        for idx, row in enumerate(out[sheet]):
            errors = [e.message for e in validator.iter_errors(row)]
            assert not errors, f"{sheet}[{idx}]: {errors} | {row!r}"
        transaction._check_formula_policy(out[sheet])
        transaction._check_cell_lengths(out[sheet])


def test_crawl_summary_counts_the_html_pages() -> None:
    cs = _projected()["crawl_sitemap"]
    by_metric = {r["metric"]: r["value"] for r in cs if r["category"] != "URL"}
    assert by_metric["html_pages"] == "5" and by_metric["non_indexable"] == "1"
    assert sum(1 for r in cs if r["category"] == "URL") == 5


def test_external_redirect_is_not_an_internal_404_task() -> None:
    rows = _projected()["redirect_404"]
    assert all("other.test" not in " ".join(str(v) for v in r.values()) for r in rows)
    assert len(rows) == 2


def test_sf_import_matches_and_counts_the_fixture() -> None:
    matched, _missing_t1, _missing_t2 = sf_import.match_tiers(FIXTURE)
    counts = {m.canonical_name: m.row_count for m in matched}
    assert counts["internal_all"] == 8 and counts["issues_overview_report"] == 4
