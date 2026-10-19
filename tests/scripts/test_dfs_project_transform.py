"""K-15 — dfs_project_transform had no test although it writes master.xlsx.

Pure builders are exercised on REST-envelope shaped payloads, and every row is
checked against the master schema the transaction writer enforces.
"""
from __future__ import annotations

from scripts.excel import transaction
from scripts.ingestion import dfs_project_transform as dpt


def _env(items: list[dict]) -> dict:
    return {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [{"items": items}]}]}


RANKED = _env([
    {"keyword_data": {"keyword": "kombi servisi", "keyword_info": {"search_volume": 900, "cpc": 1.2, "competition": 0.4}},
     "ranked_serp_element": {"serp_item": {"rank_group": 7, "rank_absolute": 9, "url": "https://x.test/kombi",
                                           "etv": 31.5, "title": "Kombi Servisi"}}},
    {"keyword_data": {"keyword": "klima", "keyword_info": {}},
     "ranked_serp_element": {"serp_item": {"rank_group": 2, "rank_absolute": 2, "url": "https://x.test/klima"}}},
])
REF = _env([{"target": "x.test", "referring_domains": 40, "referring_main_domains": 35,
             "referring_domains_nofollow": 6}])
SPAM = _env([{"target": "x.test", "spam_score": 3}])
RELEVANT = _env([
    {"page_address": "https://x.test/a", "metrics": {"organic": {"count": 4, "etv": 9.0, "pos_2_3": 1}}},
    {"page_address": "https://x.test/b", "metrics": {"organic": {"count": 12, "etv": 30.0}}},
])


def _valid(sheet: str, rows: list[dict]) -> None:
    schema = transaction._load_schema(str(transaction._DEFAULT_SCHEMA_PATH))
    validator = transaction._build_row_validator(schema, sheet)
    for row in rows:
        assert not [e.message for e in validator.iter_errors(row)], (sheet, row)


def test_ranked_rows_sorted_by_rank_and_missing_metrics_stay_none() -> None:
    rows = dpt.build_ranked_rows(RANKED, data_source="dataforseo")
    assert [r["keyword"] for r in rows] == ["klima", "kombi servisi"]
    assert rows[0]["search_volume"] is None and rows[1]["search_volume"] == 900
    _valid("dfs_ranked_keywords", rows)


def test_backlinks_summary_joins_spam_score() -> None:
    rows = dpt.build_backlinks_rows(REF, SPAM, data_source="dataforseo", last_updated="2026-10-19")
    assert rows == [{"target": "x.test", "referring_domains": 40, "referring_main_domains": 35,
                     "referring_domains_nofollow": 6, "spam_score": 3,
                     "data_source": "dataforseo", "last_updated": "2026-10-19"}]
    _valid("backlinks", rows)


def test_relevant_pages_sorted_by_keyword_count() -> None:
    rows = dpt.build_relevant_rows(RELEVANT, data_source="dataforseo")
    assert [r["url"] for r in rows] == ["https://x.test/b", "https://x.test/a"]
    _valid("dfs_relevant_pages", rows)


def test_empty_payloads_give_no_rows() -> None:
    assert dpt.build_ranked_rows({}, data_source="d") == []
    assert dpt.build_backlinks_rows(None, None, data_source="d", last_updated="x") == []
