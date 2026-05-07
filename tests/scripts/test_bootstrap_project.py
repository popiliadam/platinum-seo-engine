"""Smoke test + path regression-lock for scripts/state/bootstrap_project.py.

Q-V1.4-BOOTSTRAP-PATHS-01 Tier 2: 7 path field default modern convention
regression-lock + workspace_root env-required contract test (F-16 invariant
strict, no engine repo path fallback).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "state" / "bootstrap_project.py"

WS_ROOT_FOR_TESTS = "~/Documents/platinum-seo-workspace"

sys.path.insert(0, str(REPO_ROOT))
from scripts.state.bootstrap_project import build_project_config  # noqa: E402


def _env_with_ws_root(ws_root: str = WS_ROOT_FOR_TESTS) -> dict:
    """Return env dict with PSEO_WORKSPACE_ROOT set (Q-V1.4-BOOTSTRAP-PATHS-01:
    workspace_root env is REQUIRED — no engine repo path fallback)."""
    return {**os.environ, "PSEO_WORKSPACE_ROOT": ws_root}


def _make_args(**overrides: object) -> argparse.Namespace:
    """Build argparse.Namespace mock matching parse_args() defaults
    so build_project_config() can be called in-process (no subprocess)."""
    defaults: dict = dict(
        project="test-slug",
        domain="https://test.example/",
        market="TR",
        locale="tr-TR",
        currency="TRY",
        platform="wordpress",
        platform_seo_plugin=None,
        profile=["local-service"],
        ymyl_level="none",
        gsc_site_url=None,
        dfs_location_code=2792,
        dfs_language_code="tr",
        dfs_location_name=None,
        display_name=None,
        out=None,
        dry_run=True,
        force=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


@pytest.fixture
def env_with_ws_root(monkeypatch: pytest.MonkeyPatch) -> str:
    """Set PSEO_WORKSPACE_ROOT for in-process build_project_config() calls."""
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", WS_ROOT_FOR_TESTS)
    return WS_ROOT_FOR_TESTS


def test_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "--project" in result.stdout


def test_dry_run_emits_valid_json() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-slug",
         "--domain", "https://test.example/",
         "--profile", "local-service",
         "--dry-run"],
        capture_output=True, text=True, timeout=15,
        env=_env_with_ws_root(),
    )
    assert result.returncode == 0, result.stderr
    cfg = json.loads(result.stdout)
    assert cfg["project_id"] == "test-slug"
    assert cfg["schema_version"] == "1.3"
    assert "paths" in cfg and "gsc" in cfg and "dataforseo" in cfg
    assert cfg["profiles"] == ["local-service"]


def test_missing_project_arg_fails() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0


def test_missing_workspace_root_env_fails() -> None:
    """PSEO_WORKSPACE_ROOT env is REQUIRED — bootstrap exits 2 with clear
    error message when unset (no engine repo path fallback; F-16 invariant)."""
    env = {k: v for k, v in os.environ.items() if k != "PSEO_WORKSPACE_ROOT"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-slug",
         "--domain", "https://test.example/",
         "--profile", "local-service",
         "--dry-run"],
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    assert result.returncode == 2, result.stderr
    assert "PSEO_WORKSPACE_ROOT" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# Q-V1.4-BOOTSTRAP-PATHS-01 Tier 2 — 7 path field modern convention
# regression-lock (in-process build_project_config calls; subprocess-free
# for speed + clarity).
# ─────────────────────────────────────────────────────────────────────────────


def test_build_project_config_paths_modern_convention(env_with_ws_root: str) -> None:
    """7 path field default values match modern workspace convention bire-bir
    (demo-dental canonical reference)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"] == {
        "workspace_root": f"{env_with_ws_root}/projects/test-slug",
        "excel_filename": "master.xlsx",
        "sf_exports_dir": "inbox/sf",
        "staging_dir": "_state/cache",
        "reports_dir": "outputs/reports",
        "blog_dir": "outputs/content/drafts",
        "backups_dir": "_state/backups",
    }


def test_excel_filename_lowercase_master_xlsx(env_with_ws_root: str) -> None:
    """F1 workbook policy: lowercase master.xlsx (legacy {slug}_MASTER.xlsx
    BÜYÜK harf yasak)."""
    cfg = build_project_config(_make_args(project="any-project"))
    assert cfg["paths"]["excel_filename"] == "master.xlsx"
    assert "_MASTER" not in cfg["paths"]["excel_filename"]
    assert cfg["paths"]["excel_filename"] != "any-project_MASTER.xlsx"


def test_sf_exports_dir_nested_inbox(env_with_ws_root: str) -> None:
    """sf_exports_dir = inbox/sf nested (legacy flat 'sf-exports' yasak)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"]["sf_exports_dir"] == "inbox/sf"
    assert cfg["paths"]["sf_exports_dir"] != "sf-exports"


def test_staging_dir_nested_state_cache(env_with_ws_root: str) -> None:
    """staging_dir = _state/cache nested (legacy flat 'staging' yasak)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"]["staging_dir"] == "_state/cache"
    assert cfg["paths"]["staging_dir"] != "staging"


def test_reports_dir_nested_outputs(env_with_ws_root: str) -> None:
    """reports_dir = outputs/reports nested (legacy flat 'reports' yasak)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"]["reports_dir"] == "outputs/reports"
    assert cfg["paths"]["reports_dir"] != "reports"


def test_blog_dir_outputs_content_drafts(env_with_ws_root: str) -> None:
    """blog_dir = outputs/content/drafts (legacy flat 'blog' naming yasak)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"]["blog_dir"] == "outputs/content/drafts"
    assert cfg["paths"]["blog_dir"] != "blog"


def test_backups_dir_nested_state_backups(env_with_ws_root: str) -> None:
    """backups_dir = _state/backups nested (legacy flat '_backups' yasak)."""
    cfg = build_project_config(_make_args())
    assert cfg["paths"]["backups_dir"] == "_state/backups"
    assert cfg["paths"]["backups_dir"] != "_backups"


def test_workspace_root_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """PSEO_WORKSPACE_ROOT env value used as workspace_root parent."""
    custom_root = "/tmp/custom-workspace"
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", custom_root)
    cfg = build_project_config(_make_args(project="custom-slug"))
    assert cfg["paths"]["workspace_root"] == f"{custom_root}/projects/custom-slug"


def test_workspace_root_no_engine_repo_path(env_with_ws_root: str) -> None:
    """F-16 invariant: workspace_root engine repo path içermez; PSEO_WORKSPACE_ROOT
    env value ile başlar + canonical /projects/{slug} suffix."""
    cfg = build_project_config(_make_args(project="any-slug"))
    ws = cfg["paths"]["workspace_root"]
    assert "platinum-seo-engine" not in ws  # legacy fallback yasak
    assert ws.startswith(env_with_ws_root)
    assert ws.endswith("/projects/any-slug")


def test_schema_validate_roundtrip(env_with_ws_root: str) -> None:
    """Bootstrap output project-config.schema.json v1.3 ile valid."""
    jsonschema = pytest.importorskip("jsonschema")
    cfg = build_project_config(_make_args(project="schema-test-slug"))
    schema = json.loads(
        (REPO_ROOT / "schemas" / "project-config.schema.json").read_text("utf-8")
    )
    jsonschema.validate(cfg, schema)  # raises ValidationError if invalid


def test_paths_no_legacy_exact_values(env_with_ws_root: str) -> None:
    """Defensive: no path field reverts to legacy exact value (regression-lock
    against accidental rollback to flat structure)."""
    cfg = build_project_config(_make_args())
    legacy_exact = {
        "sf_exports_dir": "sf-exports",
        "staging_dir": "staging",
        "reports_dir": "reports",
        "blog_dir": "blog",
        "backups_dir": "_backups",
    }
    for field, legacy_value in legacy_exact.items():
        assert cfg["paths"][field] != legacy_value, (
            f"paths.{field} reverted to legacy {legacy_value!r}"
        )
