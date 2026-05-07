"""Regression: cross-schema enum drift detection.

K-05 from docs/audits/v1.4-rules-schemas-templates-2026-05-07.md:
events.schema.json work.primary_source MUST be ⊇ master-excel.schema.json
master_task.primary_source (events MUST contain at least all values present
in master, since work events reference master_task rows).

Per ADR-018 additive policy, master tarafı bumped 9→10→11 ile resolves
Q-V1.2-MASTER-TASK-PRIMARY-SOURCE-01 — events.schema sync was skipped.

Authority cross-refs:
- master-excel.schema.json sheets.master_task.required_columns[2].enum
- events.schema.json properties.primary_source.enum + .related_sources.items.enum
"""
import json
from pathlib import Path

SCHEMAS = Path(__file__).parent.parent.parent / "schemas"


def _events_primary_source() -> set[str]:
    with (SCHEMAS / "events.schema.json").open() as f:
        d = json.load(f)
    return set(d["properties"]["primary_source"]["enum"])


def _events_related_sources() -> set[str]:
    with (SCHEMAS / "events.schema.json").open() as f:
        d = json.load(f)
    return set(d["properties"]["related_sources"]["items"]["enum"])


def _master_primary_source() -> set[str]:
    with (SCHEMAS / "master-excel.schema.json").open() as f:
        d = json.load(f)
    cols = d["sheets"]["master_task"]["required_columns"]
    ps_col = next(c for c in cols if c.get("name") == "primary_source")
    return set(ps_col["enum"])


def test_events_primary_source_superset_of_master():
    events = _events_primary_source()
    master = _master_primary_source()
    missing = master - events
    assert not missing, (
        f"events.schema.json primary_source missing values present in "
        f"master-excel.schema.json: {sorted(missing)}. "
        f"Per ADR-018 additive policy, events MUST mirror master superset."
    )


def test_events_related_sources_superset_of_master():
    events = _events_related_sources()
    master = _master_primary_source()
    missing = master - events
    assert not missing, (
        f"events.schema.json related_sources missing values: {sorted(missing)}. "
        f"Should match primary_source enum (related_sources is array of same)."
    )
