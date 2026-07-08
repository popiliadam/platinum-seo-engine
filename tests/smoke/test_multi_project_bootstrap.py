"""Multi-project end-to-end smoke test for bootstrap_project.py.

Q-V1.4-BOOTSTRAP-PATHS-01 Tier 3: subprocess + tmp_path filesystem cycle
verifies bootstrap modernize fix at the integration boundary that the
in-process unit tests (tests/scripts/test_bootstrap_project.py) cannot
exercise. Specifically: file write + idempotent rerun + multi-project
isolation + demo-hvac workaround obsolete kanıt + init-project §Step 4 paterni.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from tests._live_fixtures import live_project_dir, live_slug

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "state" / "bootstrap_project.py"


def _bootstrap(
    slug: str,
    ws_root: Path,
    *,
    domain: str = "https://test.example/",
    platform: str = "wordpress",
    profile: str = "local-service",
    force: bool = False,
) -> Path:
    """Run bootstrap_project.py CLI for `slug` into `ws_root`. Mirrors
    init-project SKILL.md §Step 4 invocation contract (--out explicit
    + PSEO_WORKSPACE_ROOT env)."""
    out = ws_root / "projects" / slug / "project.config.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, str(SCRIPT),
        "--project", slug,
        "--domain", domain,
        "--market", "TR",
        "--locale", "tr-TR",
        "--currency", "TRY",
        "--platform", platform,
        "--profile", profile,
        "--out", str(out),
    ]
    if force:
        cmd.append("--force")
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": str(ws_root)}
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=15)
    assert res.returncode == 0, (
        f"bootstrap_project.py failed: rc={res.returncode}\n"
        f"stdout={res.stdout}\nstderr={res.stderr}"
    )
    return out


def test_multi_project_independent_configs(tmp_path: Path) -> None:
    """2 farklı proje aynı workspace içinde bootstrap; workspace_root +
    project_id + profiles bağımsız ama kalan 6 path field bire-bir aynı
    (modern convention invariant)."""
    out_3 = _bootstrap("test-mp-3", tmp_path)
    out_4 = _bootstrap("test-mp-4", tmp_path, profile="e-commerce")
    cfg_3 = json.loads(out_3.read_text("utf-8"))
    cfg_4 = json.loads(out_4.read_text("utf-8"))
    assert cfg_3["paths"]["workspace_root"] == f"{tmp_path}/projects/test-mp-3"
    assert cfg_4["paths"]["workspace_root"] == f"{tmp_path}/projects/test-mp-4"
    assert cfg_3["paths"]["workspace_root"] != cfg_4["paths"]["workspace_root"]
    assert cfg_3["project_id"] == "test-mp-3"
    assert cfg_4["project_id"] == "test-mp-4"
    assert cfg_3["profiles"] == ["local-service"]
    assert cfg_4["profiles"] == ["e-commerce"]
    # 6 modern convention path field identical across projects
    for field in (
        "excel_filename", "sf_exports_dir", "staging_dir",
        "reports_dir", "blog_dir", "backups_dir",
    ):
        assert cfg_3["paths"][field] == cfg_4["paths"][field], (
            f"paths.{field} drift: {cfg_3['paths'][field]!r} vs {cfg_4['paths'][field]!r}"
        )


def test_idempotent_rerun_unchanged(tmp_path: Path) -> None:
    """Same params + --force → bootstrap output byte-byte idempotent."""
    out = _bootstrap("test-idempotent", tmp_path)
    orig_bytes = out.read_bytes()
    out_rerun = _bootstrap("test-idempotent", tmp_path, force=True)
    assert out_rerun.read_bytes() == orig_bytes, "Bootstrap output changed across reruns"


def test_demo_hvac_rerun_obsolete_workaround() -> None:
    """demo-hvac workaround obsolete kanıt: bootstrap çıktısı mevcut demo-hvac
    canonical paths ile bire-bir uyum (post-fix manuel post-process patch
    artık gerekli değil; rerun idempotent = workaround obsolete)."""
    demo_hvac_actual_path = live_project_dir(live_slug("demo-hvac")) / "project.config.json"
    if not demo_hvac_actual_path.exists():
        pytest.skip(f"demo-hvac config not found at {demo_hvac_actual_path}")
    demo_hvac_actual = json.loads(demo_hvac_actual_path.read_text("utf-8"))
    ws_root = "~/Documents/platinum-seo-workspace"
    cmd = [
        sys.executable, str(SCRIPT),
        "--project", "demo-hvac",
        "--domain", demo_hvac_actual["domain"],
        "--market", demo_hvac_actual["market"],
        "--locale", demo_hvac_actual["language"]["content_locale"],
        "--currency", demo_hvac_actual["currency"],
        "--platform", demo_hvac_actual["platform"],
        "--profile", demo_hvac_actual["profiles"][0],
        "--dry-run",
    ]
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": ws_root}
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=15)
    assert res.returncode == 0, res.stderr
    bootstrap_out = json.loads(res.stdout)
    for field, expected in demo_hvac_actual["paths"].items():
        assert bootstrap_out["paths"][field] == expected, (
            f"paths.{field} drift: bootstrap={bootstrap_out['paths'][field]!r} "
            f"vs demo_hvac_actual={expected!r}"
        )


def test_force_flag_required_for_overwrite(tmp_path: Path) -> None:
    """--force flag yoksa existing config overwrite refuse (idempotency
    guard; init-project SKILL.md DURUR condition #6 paterni)."""
    out = _bootstrap("test-overwrite", tmp_path)
    assert out.exists()
    cmd = [
        sys.executable, str(SCRIPT),
        "--project", "test-overwrite",
        "--domain", "https://test.example/",
        "--market", "TR", "--locale", "tr-TR", "--currency", "TRY",
        "--platform", "wordpress",
        "--profile", "local-service",
        "--out", str(out),
    ]
    env = {**os.environ, "PSEO_WORKSPACE_ROOT": str(tmp_path)}
    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=15)
    assert res.returncode != 0


def test_schema_validate_e2e_roundtrip(tmp_path: Path) -> None:
    """End-to-end: bootstrap output file project-config.schema.json v1.3
    valid (file write + schema load + jsonschema.validate cycle)."""
    out = _bootstrap("test-schema-e2e", tmp_path)
    cfg = json.loads(out.read_text("utf-8"))
    schema = json.loads(
        (REPO_ROOT / "schemas" / "project-config.schema.json").read_text("utf-8")
    )
    jsonschema.validate(cfg, schema)
