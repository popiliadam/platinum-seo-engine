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


def test_build_project_config_rejects_traversal_slug(env_with_ws_root: str) -> None:
    """The project slug flows straight into the on-disk workspace_root path, so it
    must not be able to escape projects/ via traversal / absolute / separator
    chars (deep-audit defense-in-depth at the write boundary)."""
    for bad in ("../evil", "../../etc/passwd", "/abs/path", "a/b", "Foo", ""):
        with pytest.raises(SystemExit):
            build_project_config(_make_args(project=bad))


def test_build_project_config_accepts_valid_kebab_slug(env_with_ws_root: str) -> None:
    """Regression: a normal kebab-case slug still builds without error."""
    cfg = build_project_config(_make_args(project="demo-dental"))
    assert cfg["project_id"] == "demo-dental"


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
    assert cfg["schema_version"] == "1.5"
    assert "paths" in cfg and "gsc" in cfg and "dataforseo" in cfg
    assert cfg["profiles"] == ["local-service"]
    # v1.8 Phase 1 D-SF-12: bootstrap emits the sf block alongside dataforseo.
    assert cfg["sf"]["mcp"]["enabled"] is False
    assert cfg["sf"]["mcp"]["url"] == "http://127.0.0.1:11435/mcp"


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


# ─────────────────────────────────────────────────────────────────────────────
# Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01 — main() default --out PSEO_WORKSPACE_ROOT-aware
# (CLI direct invocation pollution bypass; init-project SKILL §Step 4 already
# uses --out explicit so production runtime unaffected; CLI direct kullanıcı
# trap eliminated). Option (a) applied: --out > PSEO_PROJECTS_DIR > PSEO_WORKSPACE_ROOT/projects.
# ─────────────────────────────────────────────────────────────────────────────


def test_default_out_uses_workspace_root_when_no_projects_dir_env(tmp_path: Path) -> None:
    """No --out + no PSEO_PROJECTS_DIR → output goes to
    PSEO_WORKSPACE_ROOT/projects/{slug}/project.config.json (NOT cwd-relative).

    Critical: cwd ≠ PSEO_WORKSPACE_ROOT to disambiguate the pre-fix bug
    (cwd-relative "projects/" pollution) from correct env-aware default."""
    env = {k: v for k, v in os.environ.items() if k not in {"PSEO_PROJECTS_DIR"}}
    ws_root = tmp_path / "workspace"
    cwd = tmp_path / "engine_cwd"  # SEPARATE dir from ws_root
    ws_root.mkdir()
    cwd.mkdir()
    env["PSEO_WORKSPACE_ROOT"] = str(ws_root)
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-default-out",
         "--domain", "https://test.example/",
         "--profile", "local-service"],
        capture_output=True, text=True, timeout=15,
        cwd=str(cwd),  # different from ws_root — pollution would land here pre-fix
        env=env,
    )
    assert result.returncode == 0, result.stderr
    expected_path = ws_root / "projects" / "test-default-out" / "project.config.json"
    pollution_path = cwd / "projects" / "test-default-out" / "project.config.json"
    assert expected_path.exists(), (
        f"bootstrap MUST write to PSEO_WORKSPACE_ROOT/projects ({expected_path}); "
        f"stderr={result.stderr}"
    )
    assert not pollution_path.exists(), (
        f"cwd-relative pollution detected at {pollution_path} — "
        f"main() output path NOT PSEO_WORKSPACE_ROOT-aware (Q-V1.4-BOOTSTRAP-DEFAULT-OUT-01)"
    )
    cfg = json.loads(expected_path.read_text("utf-8"))
    assert cfg["project_id"] == "test-default-out"


def test_pseo_projects_dir_env_takes_precedence(tmp_path: Path) -> None:
    """PSEO_PROJECTS_DIR explicit override → trumps PSEO_WORKSPACE_ROOT/projects
    default (backward compat for explicit env-driven workflows)."""
    ws_root = tmp_path / "workspace"
    projects_dir = tmp_path / "custom-projects"
    ws_root.mkdir()
    projects_dir.mkdir()
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": str(ws_root),
           "PSEO_PROJECTS_DIR": str(projects_dir)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-projects-dir-env",
         "--domain", "https://test.example/",
         "--profile", "local-service"],
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    expected_path = projects_dir / "test-projects-dir-env" / "project.config.json"
    not_expected_path = ws_root / "projects" / "test-projects-dir-env" / "project.config.json"
    assert expected_path.exists(), (
        f"PSEO_PROJECTS_DIR override should write to {expected_path}; stderr={result.stderr}"
    )
    assert not not_expected_path.exists(), (
        f"PSEO_WORKSPACE_ROOT/projects should NOT be written when PSEO_PROJECTS_DIR is set"
    )


def test_explicit_out_takes_precedence(tmp_path: Path) -> None:
    """args.out explicit → trumps both PSEO_PROJECTS_DIR and PSEO_WORKSPACE_ROOT
    (init-project SKILL §Step 4 paterni invariant intact)."""
    ws_root = tmp_path / "workspace"
    projects_dir = tmp_path / "custom-projects"
    explicit_out = tmp_path / "explicit" / "config.json"
    ws_root.mkdir()
    projects_dir.mkdir()
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": str(ws_root),
           "PSEO_PROJECTS_DIR": str(projects_dir)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project", "test-explicit-out",
         "--domain", "https://test.example/",
         "--profile", "local-service",
         "--out", str(explicit_out)],
        capture_output=True, text=True, timeout=15,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert explicit_out.exists(), (
        f"--out explicit should write to {explicit_out}; stderr={result.stderr}"
    )
    # Neither env-driven path should be touched
    assert not (projects_dir / "test-explicit-out").exists()
    assert not (ws_root / "projects" / "test-explicit-out").exists()
