"""D-07 — the same problem found in two scans is ONE task.

The fingerprint hashed variable text ("12 finding(s): …", "N URLs") and raw
URLs, so every scan opened a new task for an unchanged problem. Old registry
keys are honoured, so the key change does not duplicate existing tasks.
"""
from __future__ import annotations

from scripts.planning import master_task_sync as mts

TECH = next(s for s in mts.SOURCE_DEFS if s.sheet == "tech_seo")
SCHEMA = next(s for s in mts.SOURCE_DEFS if s.sheet == "schema")


def _sig(src, row):
    return mts._extract_signature(src, row)


def test_counts_in_detail_do_not_change_the_task() -> None:
    a = _sig(TECH, {"issue_category": "Performance", "detail": "12 finding(s): LCP slow (3.1s)"})
    b = _sig(TECH, {"issue_category": "Performance", "detail": "13 finding(s): LCP slow (3.4s)"})
    assert a.content_signature == b.content_signature


def test_schema_location_url_count_masked() -> None:
    a = _sig(SCHEMA, {"schema_type": "Product", "location": "4 URLs (sample: /a)"})
    b = _sig(SCHEMA, {"schema_type": "Product", "location": "5 URLs (sample: /a)"})
    assert a.content_signature == b.content_signature


def test_legacy_registry_key_keeps_the_existing_task_id() -> None:
    row = {"issue_category": "Performance", "detail": "12 finding(s): LCP slow"}
    sig = _sig(TECH, row)
    legacy_key = mts._content_signature(sig.primary_source, "", "Performance|12 finding(s): LCP slow")
    assert legacy_key in sig.legacy_signatures and legacy_key != sig.content_signature
