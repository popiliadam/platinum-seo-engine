"""tests/schemas/test_quickwins_aio_columns.py — GAP-M2 D3 additive AIO columns.

Guards the master-excel schema after quick_wins gains K-N
(aio_presence/aio_own_cited/aio_checked_date/expected_uplift_clicks) and
opportunity gains I-J (aio_presence/expected_uplift_clicks):
  * column letters stay contiguous A.. (no gap typos)
  * the new columns are present with the documented types/enum
  * the transform column tuples stay aligned with the schema (no RowSchemaError
    drift — they must move together, GAP-M2 D3 / DURUR risk #3)
"""

from __future__ import annotations

import json
import string
from pathlib import Path

from scripts.discovery import quickwins_transform

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER_SCHEMA = REPO_ROOT / "schemas" / "master-excel.schema.json"


def _sheet(name: str) -> dict:
    schema = json.loads(MASTER_SCHEMA.read_text("utf-8"))
    return schema["sheets"][name]


def _columns(name: str) -> list[dict]:
    return _sheet(name)["required_columns"]


def test_quick_wins_columns_contiguous_and_aio_present() -> None:
    cols = _columns("quick_wins")
    letters = [c["col"] for c in cols]
    assert letters == list(string.ascii_uppercase[: len(cols)]), (
        f"quick_wins column letters not contiguous A..: {letters}"
    )
    names = [c["name"] for c in cols]
    # Additive K-N (GAP-M2 D3) appended after the legacy 10.
    assert names[10:] == [
        "aio_presence", "aio_own_cited", "aio_checked_date", "expected_uplift_clicks",
    ], names
    by_name = {c["name"]: c for c in cols}
    assert by_name["aio_presence"].get("enum") == ["present", "not_detected", "unchecked"]
    assert by_name["aio_own_cited"].get("type") == "boolean"
    assert by_name["aio_checked_date"].get("type") == "date"
    assert by_name["expected_uplift_clicks"].get("type") == "integer"


def test_opportunity_columns_contiguous_and_aio_present() -> None:
    cols = _columns("opportunity")
    letters = [c["col"] for c in cols]
    assert letters == list(string.ascii_uppercase[: len(cols)]), (
        f"opportunity column letters not contiguous A..: {letters}"
    )
    names = [c["name"] for c in cols]
    assert names[8:] == ["aio_presence", "expected_uplift_clicks"], names
    by_name = {c["name"]: c for c in cols}
    assert by_name["aio_presence"].get("enum") == ["present", "not_detected", "unchecked"]
    assert by_name["expected_uplift_clicks"].get("type") == "integer"


def test_transform_tuples_match_schema_columns() -> None:
    """The transform's column tuples MUST equal the schema column order
    (they move together — GAP-M2 D3 / committer RowSchemaError guard)."""
    qw_schema = [c["name"] for c in _columns("quick_wins")]
    op_schema = [c["name"] for c in _columns("opportunity")]
    assert list(quickwins_transform.QUICK_WINS_COLUMNS) == qw_schema
    assert list(quickwins_transform.OPPORTUNITY_COLUMNS) == op_schema
