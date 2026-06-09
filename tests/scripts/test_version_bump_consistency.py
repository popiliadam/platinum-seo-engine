"""tests/scripts/test_version_bump_consistency.py — Audit#2 F12-code.

F12: version_bump bumped the version banner + marketplace prefix but left
count-bearing bodies and version-keyed RELEASE_NOTES LINKS stale — a bump to
v1.5.0 could leave README pointing at ``RELEASE_NOTES_v1.4.0.md``. A release that
silently leaves stale version surfaces breaks installer-banner trust.

Fix (this worker owns the version_bump CODE + its test; the RELEASE_NOTES prose is
the DOCS worker's): version_bump now (a) bumps the RELEASE_NOTES link to the target
version, and (b) exposes ``check_release_consistency`` — a read-only audit that a
bump cannot leave a managed version surface or a release link pointing at the wrong
version. main() fails non-zero if an --apply leaves an inconsistency.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO / "scripts" / "release" / "version_bump.py"


@pytest.fixture(scope="module")
def bump_module():
    spec = importlib.util.spec_from_file_location("version_bump_f12", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_workspace(root: Path, version: str = "1.4.0", *, release_link: str | None = None) -> None:
    """Minimal ADR-036 5-file workspace. ``release_link`` overrides the README
    RELEASE_NOTES link version (for crafting a deliberately-stale link)."""
    link_v = release_link or version
    plugin_dir = root / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    docs = root / "docs"
    docs.mkdir(parents=True)

    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "pse", "version": version}, indent=2) + "\n", encoding="utf-8"
    )
    (plugin_dir / "marketplace.json").write_text(
        json.dumps({
            "name": "pse-mkt",
            "metadata": {"version": version},
            "plugins": [{"name": "pse", "source": "./",
                         "description": f"v{version} — fake body preserved across bump."}],
        }, indent=2) + "\n", encoding="utf-8",
    )
    (root / "README.md").write_text(
        f"# PSE\n\n> Status: **v{version}** — banner — "
        f"[Release Notes](docs/RELEASE_NOTES_v{link_v}.md)\n", encoding="utf-8",
    )
    (docs / "INSTALL.md").write_text(
        f"# Install\n\n> Status: **v{version}** — banner.\n", encoding="utf-8",
    )
    (docs / f"RELEASE_NOTES_v{version}.md").write_text(
        f"# v{version}\n", encoding="utf-8",
    )


# ---- the bump now bumps the RELEASE_NOTES link -------------------------------

def test_apply_bumps_release_notes_link_in_readme(bump_module, tmp_path) -> None:
    _write_workspace(tmp_path, "1.4.0")
    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)
    readme = (tmp_path / "README.md").read_text("utf-8")
    assert "RELEASE_NOTES_v1.5.0.md" in readme, "release-notes link not bumped"
    assert "RELEASE_NOTES_v1.4.0.md" not in readme, "stale release-notes link remains"


# ---- check_release_consistency -----------------------------------------------

def test_bump_result_exposes_consistency_key(bump_module, tmp_path) -> None:
    _write_workspace(tmp_path, "1.4.0")
    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=False)
    assert "consistency" in result
    assert isinstance(result["consistency"], list)


def test_check_release_consistency_clean_after_apply(bump_module, tmp_path) -> None:
    _write_workspace(tmp_path, "1.4.0")
    (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").write_text("# v1.5.0\n", "utf-8")
    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)
    problems = bump_module.check_release_consistency(tmp_path, "1.5.0")
    assert problems == [], f"clean apply must leave no stale surfaces: {problems}"


def test_apply_result_consistency_empty_for_clean_bump(bump_module, tmp_path) -> None:
    _write_workspace(tmp_path, "1.4.0")
    (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").write_text("# v1.5.0\n", "utf-8")
    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)
    assert result["consistency"] == [], result["consistency"]


def test_check_release_consistency_flags_stale_release_link(bump_module, tmp_path) -> None:
    # every version SURFACE is 1.5.0, but the README release link still points at
    # 1.4.0 — exactly the F12 stale-release-link the check must catch.
    _write_workspace(tmp_path, "1.5.0", release_link="1.4.0")
    problems = bump_module.check_release_consistency(tmp_path, "1.5.0")
    assert any("RELEASE_NOTES_v1.4.0.md" in p for p in problems), problems


def test_check_release_consistency_flags_version_surface_mismatch(bump_module, tmp_path) -> None:
    # nothing bumped: plugin.json + banners are 1.4.0 while target is 1.5.0.
    _write_workspace(tmp_path, "1.4.0")
    problems = bump_module.check_release_consistency(tmp_path, "1.5.0")
    assert problems, "stale version surfaces must be flagged"
    assert any("plugin.json" in p for p in problems), problems
