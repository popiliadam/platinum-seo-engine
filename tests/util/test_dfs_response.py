"""tests/util/test_dfs_response.py — Y-02 endpoint-aware DFS response normalize.

Single canonical implementation lives in :mod:`scripts.util.dfs_response`.
Three transform/ingestion modules previously each maintained their own
``_normalize_dfs_response`` variant with semantic divergence between
keyword and Lighthouse endpoints (Lesson 38 v2 #34-35 by-design extension).
Y-02 collapses them into one endpoint-aware dispatcher.

Canonical shapes the dispatcher must accept:

    1. REST envelope (upstream / direct HTTP / well-behaved wrappers)
         {"tasks": [{"result": [{"items": [...]}]}]}
    2. Flat wrapper (dataforseo-mcp-server@2.8.9 flattening)
         {"items": [...]}
    3. Inline keyword (DFS labs endpoints inline keyword on result entries)
         {"tasks": [{"result": [{"keyword": ..., "search_volume": ...}]}]}
    4. Inline Lighthouse (on_page_lighthouse inline page audit on result)
         {"tasks": [{"result": [{"url": ..., "lighthouse": ..., "page_metrics": ...}]}]}
    5. Top-level Lighthouse audits (some MCP wrappers strip the envelope)
         {"lighthouse": ..., "audits": ...}

Endpoint dispatcher semantics:
    * endpoint_type=None — broadest tolerance (accept all inline shapes)
    * endpoint_type="keyword" — only inline `keyword` key counted
    * endpoint_type="lighthouse" — only inline lighthouse/page_metrics counted

DURUR triggers (raise DFSResponseError, extends ValueError):
    * top-level not a dict
    * none of the above shapes recognisable

Refs:
    * spec §11.5 (DFS keyword endpoints) + §11.6 (DFS Lighthouse)
    * 2026-05-07 v1.6-Phase-3 Y-02 + O-03 (this module + 2 transform migrate)
    * Lesson 38 v2 #34-35 v1.5-Phase-1 (semantic divergence by-design)
"""

from __future__ import annotations

import pytest

from scripts.util.dfs_response import (
    DFSResponseError,
    normalize_dfs_response,
    safe_float,
    safe_int,
    safe_str,
)


# ---------------------------------------------------------------------------
# Shape 1 — REST envelope (tasks[].result[].items)
# ---------------------------------------------------------------------------


def test_keyword_response_envelope_REST():
    raw = {
        "tasks": [
            {
                "result": [
                    {
                        "items": [
                            {"keyword": "kedi kumu", "search_volume": 1200},
                            {"keyword": "kedi maması", "search_volume": 5400},
                        ]
                    }
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw, endpoint_type="keyword")
    assert len(items) == 2
    assert items[0]["keyword"] == "kedi kumu"
    assert items[1]["search_volume"] == 5400


# ---------------------------------------------------------------------------
# Shape 2 — Flat wrapper (top-level items list)
# ---------------------------------------------------------------------------


def test_keyword_response_flat_wrapper():
    """dataforseo-mcp-server@2.8.9 flattens labs + on_page endpoints."""
    raw = {"items": [{"keyword": "kedi", "search_volume": 100}]}
    items = normalize_dfs_response(raw, endpoint_type="keyword")
    assert len(items) == 1
    assert items[0]["keyword"] == "kedi"


# ---------------------------------------------------------------------------
# Shape 3 — Inline keyword detection (DFS labs endpoint)
# ---------------------------------------------------------------------------


def test_endpoint_dispatcher_keyword_detection():
    """endpoint_type='keyword' captures inline `keyword` at result-level."""
    raw = {
        "tasks": [
            {
                "result": [
                    {"keyword": "kedi kumu", "search_volume": 1200},
                    {"keyword": "kedi maması", "search_volume": 5400},
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw, endpoint_type="keyword")
    assert len(items) == 2
    assert items[0]["keyword"] == "kedi kumu"


# ---------------------------------------------------------------------------
# Shape 4 — Inline Lighthouse (on_page_lighthouse result-level audit payload)
# ---------------------------------------------------------------------------


def test_lighthouse_response_envelope():
    raw = {
        "tasks": [
            {
                "result": [
                    {
                        "url": "https://example.com/",
                        "page_metrics": {"performance_score": 0.85},
                        "lighthouse": {"audits": {"largest-contentful-paint": {}}},
                    }
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw, endpoint_type="lighthouse")
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/"
    assert "lighthouse" in items[0]


def test_endpoint_dispatcher_lighthouse_detection():
    """endpoint_type='lighthouse' captures inline lighthouse/page_metrics
    at result-level."""
    raw = {
        "tasks": [
            {
                "result": [
                    {
                        "url": "https://example.com/page",
                        "page_metrics": {"performance_score": 0.5},
                    }
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw, endpoint_type="lighthouse")
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/page"


# ---------------------------------------------------------------------------
# Shape 5 — Top-level Lighthouse fallback (some MCP wrappers strip envelope)
# ---------------------------------------------------------------------------


def test_lighthouse_response_top_level_fallback():
    raw = {"lighthouse": {"audits": {}}, "url": "https://example.com/"}
    items = normalize_dfs_response(raw, endpoint_type="lighthouse")
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/"


# ---------------------------------------------------------------------------
# Endpoint dispatcher — explicit endpoint_type filters inline detection
# ---------------------------------------------------------------------------


def test_endpoint_dispatcher_keyword_skips_lighthouse_inline():
    """endpoint_type='keyword' must NOT capture Lighthouse inline payloads."""
    raw = {
        "tasks": [
            {
                "result": [
                    {
                        "items": [{"keyword": "kedi"}],
                        "lighthouse": {"audits": {}},
                        "page_metrics": {"performance_score": 0.5},
                    }
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw, endpoint_type="keyword")
    # Only the inner "items" list — Lighthouse inline at result-level skipped.
    assert len(items) == 1
    assert items[0]["keyword"] == "kedi"


def test_endpoint_dispatcher_unknown_falls_back():
    """endpoint_type=None tolerates BOTH inline shapes (broadest)."""
    raw = {
        "tasks": [
            {
                "result": [
                    {
                        "items": [{"keyword": "kedi"}],
                        "lighthouse": {"audits": {}},
                    }
                ]
            }
        ]
    }
    items = normalize_dfs_response(raw)  # endpoint_type defaults to None
    # 1 keyword item + 1 Lighthouse inline result entry = 2.
    assert len(items) == 2


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_top_level_not_dict_raises():
    with pytest.raises(DFSResponseError, match="must be a dict"):
        normalize_dfs_response([])  # type: ignore[arg-type]


def test_unrecognized_shape_raises():
    with pytest.raises(DFSResponseError, match="Unrecognized DFS response shape"):
        normalize_dfs_response({"unknown_key": "value"})


def test_unrecognized_shape_includes_endpoint_in_error():
    with pytest.raises(DFSResponseError, match="endpoint='keyword_overview'"):
        normalize_dfs_response(
            {"unknown_key": "v"},
            endpoint_type="keyword",
            expected_endpoint="keyword_overview",
        )


def test_dfs_response_error_extends_value_error():
    """Legacy callers expecting bare ValueError continue to work
    (paterni K-01 reuse — adapter at call-site wraps into domain error)."""
    assert issubclass(DFSResponseError, ValueError)


# ---------------------------------------------------------------------------
# safe_int / safe_float / safe_str helpers
# ---------------------------------------------------------------------------


def test_safe_int_edge_cases():
    assert safe_int(None) == 0
    assert safe_int("") == 0
    assert safe_int("42") == 42
    assert safe_int(42) == 42
    assert safe_int(42.5) == 42
    assert safe_int("abc") == 0
    assert safe_int(None, default=10) == 10


def test_safe_float_edge_cases():
    assert safe_float(None) == 0.0
    assert safe_float("") == 0.0
    assert safe_float("3.14") == pytest.approx(3.14)
    assert safe_float(3.14) == pytest.approx(3.14)
    assert safe_float("abc") == 0.0
    assert safe_float(None, default=1.5) == 1.5


def test_safe_str_edge_cases():
    assert safe_str(None) == ""
    assert safe_str("") == ""
    assert safe_str(42) == "42"
    assert safe_str("text") == "text"
    assert safe_str(None, default="N/A") == "N/A"


# ---------------------------------------------------------------------------
# Module exports surface
# ---------------------------------------------------------------------------


def test_dfs_response_module_exports():
    """__all__ pins the public surface."""
    import scripts.util.dfs_response as mod

    expected = {
        "DFSResponseError",
        "normalize_dfs_response",
        "safe_int",
        "safe_float",
        "safe_str",
    }
    assert set(mod.__all__) == expected


# ---------------------------------------------------------------------------
# Edge cases — empty containers
# ---------------------------------------------------------------------------


def test_empty_items_list_returns_empty():
    raw = {"items": []}
    assert normalize_dfs_response(raw, endpoint_type="keyword") == []


def test_envelope_with_empty_result_returns_empty():
    """saw_result=True semantic — preserve tech_audit/dfs_pull invariant."""
    raw = {"tasks": [{"result": []}]}
    assert normalize_dfs_response(raw, endpoint_type="keyword") == []


def test_envelope_without_result_falls_through_to_flat():
    """tasks[] present but no result[] — fall through to flat handler."""
    raw = {
        "tasks": [{"id": "task-1"}],
        "items": [{"keyword": "kedi"}],
    }
    items = normalize_dfs_response(raw, endpoint_type="keyword")
    assert len(items) == 1
    assert items[0]["keyword"] == "kedi"
