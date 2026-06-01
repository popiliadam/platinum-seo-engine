"""
LC-3 (Q-PHASE15-RXX-COUNT-01) — event_id format codification.

Locks rules/events-writer.md Section 7 to schemas/events.schema.json
properties.event_id (the SSoT). If the schema pattern/length ever drifts
from the documented values these tests FAIL — doc and schema can never
silently diverge.
"""

from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RULES_DOC = _REPO_ROOT / "rules" / "events-writer.md"
_EVENTS_SCHEMA = _REPO_ROOT / "schemas" / "events.schema.json"


def _event_id_schema() -> dict:
    schema = json.loads(_EVENTS_SCHEMA.read_text(encoding="utf-8"))
    return schema["properties"]["event_id"]


def test_rules_doc_documents_event_id_regex_and_bounds() -> None:
    """Section 7 must spell out the regex + 3..128 length bounds."""
    doc = _RULES_DOC.read_text(encoding="utf-8")
    assert "Section 7" in doc and "event_id" in doc
    # The exact regex literal is present.
    assert "^[A-Za-z0-9][A-Za-z0-9_.:-]*$" in doc
    # Length bounds documented.
    assert "minLength" in doc and "maxLength" in doc
    assert "3" in doc and "128" in doc
    # Canonical work-event convention example documented.
    assert "content_new_T-0042_20260420T1030" in doc


def test_schema_event_id_pattern_matches_docs() -> None:
    """events.schema.json event_id pattern + bounds must appear verbatim in the docs."""
    spec = _event_id_schema()
    doc = _RULES_DOC.read_text(encoding="utf-8")

    assert spec["pattern"] == "^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
    assert spec["minLength"] == 3
    assert spec["maxLength"] == 128

    # Doc ↔ schema parity: every authoritative value is present in the doc.
    assert spec["pattern"] in doc
    assert str(spec["minLength"]) in doc
    assert str(spec["maxLength"]) in doc
