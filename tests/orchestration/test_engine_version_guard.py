#!/usr/bin/env python3
"""Tests for the engine-version STAMP + run-start RESUME guard (AMO batch 4g,
spec §8 self-upgrade versioning).

Two behaviours, both ADDITIVE over a fresh run:

  * STAMP — ``run_workflow`` (and ``content_pipeline.run``) now resolve the engine
    version from ``scripts.state.engine_version`` when the caller passes None, so
    every written coverage record carries ``engine_version``. An explicit caller
    value still wins.

  * RESUME GUARD — at run start, BEFORE any step runs or is written, ``run_workflow``
    refuses to resume a run_id whose prior coverage record was stamped by a
    DIFFERENT engine version (fail-loud ``EngineVersionMismatch`` → "regenerate").
    A fresh run (no prior file) or an un-stamped pre-4g prior is allowed → no raise,
    byte-identical to before. The mismatch is detected before the prior record is
    overwritten.

An EMPTY ``steps_table`` is used: it exercises run_workflow's build/derive/stamp/
write path (verdict 'pass' over zero steps) with no commit_fn, raw drop, or
workbook — isolating the version behaviour under test.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.orchestration import coverage
from scripts.orchestration.workflow_driver import EngineVersionMismatch, run_workflow
from scripts.orchestration.workflows import content_pipeline
from scripts.state.engine_version import engine_version

RUN_ID = "demo-furniture-2026-06-09-abcd"
SLUG = "demo-furniture"
NOW = 1_750_000_000.0


def _wb(tmp_path: Path) -> Path:
    return tmp_path / "master.xlsx"


def _written(tmp_path: Path) -> dict:
    return json.loads(
        coverage.coverage_path(tmp_path, SLUG, RUN_ID).read_text(encoding="utf-8")
    )


def _prewrite(tmp_path: Path, *, engine_version_value: str | None) -> None:
    """Pre-write a VALID prior coverage record for RUN_ID (a 'resume' setup)."""
    prior = coverage.build_record(
        run_id=RUN_ID, steps=[], required_satisfied=True, verdict="pass",
        project_slug=SLUG, engine_version=engine_version_value,
    )
    coverage.write_coverage(
        prior, workspace_root=tmp_path, project_slug=SLUG, run_id=RUN_ID
    )


# --- STAMP -----------------------------------------------------------------

def test_fresh_run_stamps_current_engine_version(tmp_path: Path) -> None:
    """A fresh run (engine_version=None) stamps the coverage record with the
    version sourced from plugin.json."""
    record = run_workflow((), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW)
    assert record["engine_version"] == engine_version()
    assert _written(tmp_path)["engine_version"] == engine_version()


def test_explicit_engine_version_overrides_source(tmp_path: Path) -> None:
    """An explicit caller value wins over the plugin.json source."""
    record = run_workflow(
        (), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW, engine_version="9.9.9"
    )
    assert record["engine_version"] == "9.9.9"


def test_content_pipeline_run_stamps_current_engine_version(tmp_path: Path) -> None:
    """The content artifact driver mirrors the data driver: a None engine_version
    is resolved to the plugin.json source on its coverage write."""
    blog = tmp_path / "projects" / SLUG / "outputs" / "blog" / "post"
    record = content_pipeline.run(
        RUN_ID, SLUG, tmp_path, blog, NOW, write=False
    )
    assert record["engine_version"] == engine_version()


# --- RESUME GUARD ----------------------------------------------------------

def test_resume_same_version_does_not_raise(tmp_path: Path) -> None:
    """First run stamps the current version; resuming the same run_id with the
    same version is fine — no raise, normal 'pass'."""
    run_workflow((), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW)
    record = run_workflow((), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW)
    assert record["verdict"] == "pass"
    assert record["engine_version"] == engine_version()


def test_resume_version_mismatch_raises_before_overwrite(tmp_path: Path) -> None:
    """The teeth: a prior stamped with an OLD version + a current run at a NEW
    version → EngineVersionMismatch naming BOTH versions, raised BEFORE the prior
    record is overwritten (it survives on disk unchanged)."""
    _prewrite(tmp_path, engine_version_value="1.9.5")
    with pytest.raises(EngineVersionMismatch) as exc:
        run_workflow(
            (), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW, engine_version="2.0.0"
        )
    message = str(exc.value)
    assert "1.9.5" in message and "2.0.0" in message
    # the prior record was NOT silently overwritten
    assert _written(tmp_path)["engine_version"] == "1.9.5"


def test_resume_unstamped_prior_does_not_raise(tmp_path: Path) -> None:
    """Back-compat: a pre-4g prior with NO engine_version key is treated as
    'unknown' → no raise; the new run stamps the current version."""
    _prewrite(tmp_path, engine_version_value=None)
    assert "engine_version" not in _written(tmp_path)
    record = run_workflow(
        (), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW, engine_version="2.0.0"
    )
    assert record["engine_version"] == "2.0.0"
    assert _written(tmp_path)["engine_version"] == "2.0.0"


def test_no_write_run_does_not_consult_prior(tmp_path: Path) -> None:
    """A dry (write=False) run neither reads nor raises on a mismatched prior — it
    persists nothing, so the resume guard (a write-path concern) is not engaged."""
    _prewrite(tmp_path, engine_version_value="1.9.5")
    record = run_workflow(
        (), RUN_ID, SLUG, tmp_path, _wb(tmp_path), NOW,
        write=False, engine_version="2.0.0",
    )
    assert record["engine_version"] == "2.0.0"
    # the prior on-disk record is untouched
    assert _written(tmp_path)["engine_version"] == "1.9.5"
