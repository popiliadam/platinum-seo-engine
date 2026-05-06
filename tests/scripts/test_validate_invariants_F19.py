"""tests/scripts/test_validate_invariants_F19.py — Wave 2 F-19 fix.

Q-WAVE1-F19-VALIDATOR-01 RESOLVED: validator reads schema 1.3 canonical
``language.content_locale`` (nested) + root ``market``. Pre-Wave-2 read
root ``locale`` / ``defaults.locale`` (schema 1.2 paths) — now forbidden
by ``additionalProperties: false`` after Migration 0003.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from scripts.validation.validate_invariants import check_F_19


def _stub_workbook() -> Workbook:
    """F-19 ignores the workbook arg — return a minimal stub."""
    return Workbook()


def _make_workspace(tmp_path: Path, project_slug: str, config: dict) -> Path:
    project_dir = tmp_path / "projects" / project_slug
    (project_dir).mkdir(parents=True)
    cfg_path = project_dir / "project.config.json"
    cfg_path.write_text(json.dumps(config), encoding="utf-8")
    return tmp_path


def test_schema_13_canonical_passes(tmp_path: Path) -> None:
    workspace = _make_workspace(
        tmp_path, "test-1",
        {
            "schema_version": "1.3",
            "market": "TR",
            "language": {"content_locale": "tr-TR"},
        },
    )
    result = check_F_19(_stub_workbook(), "test-1", workspace_root=workspace)
    assert result["verdict"] == "PASS", result


def test_missing_language_fails(tmp_path: Path) -> None:
    workspace = _make_workspace(
        tmp_path, "test-2",
        {"schema_version": "1.3", "market": "TR"},
    )
    result = check_F_19(_stub_workbook(), "test-2", workspace_root=workspace)
    assert result["verdict"] == "FAIL"
    assert "language.content_locale" in result["evidence"]


def test_missing_content_locale_fails(tmp_path: Path) -> None:
    workspace = _make_workspace(
        tmp_path, "test-3",
        {
            "schema_version": "1.3",
            "market": "TR",
            "language": {"content_variant": None},
        },
    )
    result = check_F_19(_stub_workbook(), "test-3", workspace_root=workspace)
    assert result["verdict"] == "FAIL"
    assert "language.content_locale" in result["evidence"]


def test_missing_market_fails(tmp_path: Path) -> None:
    workspace = _make_workspace(
        tmp_path, "test-4",
        {"schema_version": "1.3", "language": {"content_locale": "tr-TR"}},
    )
    result = check_F_19(_stub_workbook(), "test-4", workspace_root=workspace)
    assert result["verdict"] == "FAIL"
    assert "market" in result["evidence"]


def test_legacy_root_locale_no_longer_passes(tmp_path: Path) -> None:
    """Pre-Wave-2 root ``locale`` was accepted; Wave 2 fix only reads 1.3 canonical."""
    workspace = _make_workspace(
        tmp_path, "test-5",
        {
            "schema_version": "1.2",
            "market": "TR",
            "locale": "tr-TR",  # schema 1.2 path
        },
    )
    result = check_F_19(_stub_workbook(), "test-5", workspace_root=workspace)
    assert result["verdict"] == "FAIL"
    assert "language.content_locale" in result["evidence"]


def test_missing_config_skips(tmp_path: Path) -> None:
    project_dir = tmp_path / "projects" / "test-6"
    project_dir.mkdir(parents=True)
    result = check_F_19(_stub_workbook(), "test-6", workspace_root=tmp_path)
    assert result["verdict"] == "SKIP"
