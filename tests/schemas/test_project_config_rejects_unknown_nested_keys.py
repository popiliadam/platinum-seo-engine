"""P1-03: high-risk nested objects in project-config reject typo'd keys.

Several critical nested objects (`language`, `paths`, `gsc`, `dataforseo`,
`brand`, `thresholds`, `workflow`, and the bank-entry item objects under
`content_settings`) were OPEN (no `additionalProperties: false`), so a
misspelled nested key (`content_localee`, `site_urll`, a typo'd R-121 bank
field, ...) passed validation silently and the value was quietly dropped at
read time. This locks those objects closed.

Scope note (SELECTIVE pass): `brand.mention_range`, `workflow.quality_iteration`
and the `disclaimer_templates` map are intentionally left OPEN here — the
brief closes only the named high-risk objects + the content_settings bank-entry
items; the remaining open objects are a separate lower-risk pass.

Uses the engine's real `build_validator` so the test exercises the exact
validation path the CLI uses (draft + format enforcement).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validation.validate_schema import build_validator

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schemas" / "project-config.schema.json"

# A minimal, schema-valid v1.5 config (mirrors tests/conftest.py factory).
BASE: dict = {
    "schema_version": "1.5",
    "project_id": "demo",
    "domain": "https://example.com/",
    "market": "TR",
    "language": {"content_locale": "tr-TR"},
    "currency": "TRY",
    "platform": "wordpress",
    "profiles": ["e-commerce"],
    "paths": {
        "workspace_root": "/tmp/projects/demo",
        "excel_filename": "master.xlsx",
        "sf_exports_dir": "inbox/sf",
        "staging_dir": "_state/cache",
        "reports_dir": "outputs/reports",
        "blog_dir": "outputs/content/drafts",
        "backups_dir": "_state/backups",
    },
    "gsc": {"site_url": "https://example.com/"},
    "dataforseo": {"location_code": 2792, "language_code": "tr"},
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _errors(config: dict) -> list:
    return list(build_validator(_schema()).iter_errors(config))


def _with(**override) -> dict:
    """Deep-copy BASE and shallow-merge dict overrides (so we can inject a
    typo'd key into a nested object while keeping its required keys)."""
    cfg = copy.deepcopy(BASE)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg[key], **value}
        else:
            cfg[key] = value
    return cfg


# (case-id, config-with-a-single-typo'd-nested-key)
TYPO_CASES = [
    ("language", _with(language={"content_localee": "tr-TR"})),
    ("paths", _with(paths={"blog_dirr": "x"})),
    ("gsc", _with(gsc={"site_urll": "https://example.com/"})),
    ("dataforseo", _with(dataforseo={"locationn_code": 1})),
    ("brand", _with(brand={"patterns": [], "patternss": []})),
    ("thresholds", _with(thresholds={"quality_gate_pass_scoree": 70})),
    ("workflow", _with(workflow={"quality_iterationn": {}})),
    ("content_settings.original_research_database.item",
     _with(content_settings={"original_research_database": [{"id": "r1", "title": "t", "bogus_field": 1}]})),
    ("content_settings.experience_database.item",
     _with(content_settings={"experience_database": [{"id": "e1", "context": "c", "bogus_field": 1}]})),
    ("content_settings.video_database.item",
     _with(content_settings={"video_database": [{"id": "v1", "title": "t", "url": "https://example.com/v", "bogus_field": 1}]})),
]


def test_base_config_is_valid() -> None:
    """Guard: the minimal config must validate — closures must not break it."""
    assert not _errors(BASE), f"BASE config should validate: {[e.message for e in _errors(BASE)]}"


@pytest.mark.parametrize("case_id, config", TYPO_CASES, ids=[c[0] for c in TYPO_CASES])
def test_typo_nested_key_rejected(case_id: str, config: dict) -> None:
    errors = _errors(config)
    assert errors, f"{case_id}: a misspelled nested key must be rejected (object should be closed)"


def test_legit_brand_metadata_keys_accepted() -> None:
    """niche + description are real keys used by a live config (miningaa-com);
    closing `brand` must keep accepting them (added to properties), not break."""
    cfg = _with(brand={
        "patterns": ["Demo"],
        "niche": "bebek-guvenlik-bakim",
        "description": "demo brand description",
        "mention_range": {"min": 4, "max": 7},
    })
    assert not _errors(cfg), f"legit brand keys must validate: {[e.message for e in _errors(cfg)]}"
