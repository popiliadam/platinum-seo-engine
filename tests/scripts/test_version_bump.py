"""tests/scripts/test_version_bump.py — Y-05 v1.5-Phase-3 Tier 1
ADR-036 5-file version sync automation (scripts/release/version_bump.py).

Target file set (per ADR-036 + tests/ci/test_version_sync.py runtime authority):
  1. .claude-plugin/plugin.json -> top-level "version"
  2. .claude-plugin/marketplace.json -> metadata.version + plugins[0].description
     "v<semver> — ..." prefix
  3. README.md -> "**Status:** v<semver> — ..." banner (line 8 baseline)
  4. docs/INSTALL.md -> "> Status: **v<semver>** — ..." blockquote banner
  5. docs/RELEASE_NOTES_v<semver>.md -> existence check (WARN if missing,
     no auto-create — manual authoring required per brief Section "Phase 3"
     Tier 1 step 2.5).

CLI semantics:
  - dry-run is the DEFAULT (safer; ADR-036 5-file sync invariant must not
    be corrupted by accidental writes).
  - --apply is opt-in for destructive write.

Coverage:
  1. dry-run does not modify any of the 5 files
  2. dry-run warns when target RELEASE_NOTES file is missing
  3. dry-run silent when target RELEASE_NOTES file already drafted
  4. apply updates plugin.json version
  5. apply updates marketplace.json metadata.version
  6. apply updates marketplace plugins[0].description "v<semver> — " prefix
  7. apply updates README **Status:** banner
  8. apply updates INSTALL > Status: ** banner (blockquote+inline-bold form)
  9. apply WARNs but does NOT auto-create missing RELEASE_NOTES file
  10. apply is idempotent when target version already matches
  11. apply preserves test_version_sync invariant (4 banner regexes hold)
  12. invalid semver input raises ValueError
  13. module exposes main() for CLI usage
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO / "scripts" / "release" / "version_bump.py"


@pytest.fixture(scope="module")
def bump_module():
    spec = importlib.util.spec_from_file_location("version_bump", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, (
        f"scripts/release/version_bump.py not loadable: {SCRIPT_PATH}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_5_file_workspace(root: Path, current_version: str = "1.4.0") -> None:
    """Synthesize a minimal 5-file ADR-036 workspace at root."""
    plugin_dir = root / ".claude-plugin"
    plugin_dir.mkdir(parents=True)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True)

    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "name": "platinum-seo-engine",
                "version": current_version,
                "description": "fake plugin description for tests",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (plugin_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "platinum-seo-marketplace",
                "metadata": {
                    "description": "fake marketplace description",
                    "version": current_version,
                },
                "plugins": [
                    {
                        "name": "platinum-seo-engine",
                        "source": "./",
                        "description": (
                            f"v{current_version} — fake plugin description "
                            "with status info that should be preserved across bump."
                        ),
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        f"# Platinum SEO Engine\n\n"
        f"**Status:** v{current_version} — fake banner — "
        f"[Release Notes](docs/RELEASE_NOTES_v{current_version}.md)\n",
        encoding="utf-8",
    )

    (docs_dir / "INSTALL.md").write_text(
        f"# Install\n\n"
        f"> Status: **v{current_version}** — fake banner — production-ready.\n",
        encoding="utf-8",
    )

    (docs_dir / f"RELEASE_NOTES_v{current_version}.md").write_text(
        f"# v{current_version} Release Notes\n\nFake notes for the current version.\n",
        encoding="utf-8",
    )


# ---------- 1. dry-run does not modify files ----------


def test_dry_run_default_does_not_modify_files(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)
    snapshots = {
        p: (tmp_path / p).read_text("utf-8")
        for p in [
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "README.md",
            "docs/INSTALL.md",
            "docs/RELEASE_NOTES_v1.4.0.md",
        ]
    }

    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=False)

    for path, before in snapshots.items():
        after = (tmp_path / path).read_text("utf-8")
        assert before == after, f"dry-run modified {path}"
    assert result["applied"] is False
    assert len(result["changes"]) >= 4, (
        f"dry-run must propose >=4 changes (4 file edits), got: {result['changes']}"
    )


# ---------- 2. dry-run warns when RELEASE_NOTES missing ----------


def test_dry_run_warns_when_release_notes_missing(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=False)

    warnings = result.get("warnings", [])
    assert any("RELEASE_NOTES_v1.5.0.md" in w for w in warnings), (
        f"Missing release notes WARN expected, got warnings: {warnings}"
    )


# ---------- 3. dry-run silent when RELEASE_NOTES exists ----------


def test_dry_run_silent_when_release_notes_exists(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)
    (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").write_text(
        "# v1.5.0 Release Notes\n\nDraft.\n", "utf-8"
    )

    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=False)

    warnings = result.get("warnings", [])
    assert not any("RELEASE_NOTES_v1.5.0.md" in w for w in warnings), (
        f"No release-notes warning expected when file exists, got: {warnings}"
    )


# ---------- 4. apply: plugin.json version ----------


def test_apply_updates_plugin_json_version(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    data = json.loads((tmp_path / ".claude-plugin" / "plugin.json").read_text("utf-8"))
    assert data["version"] == "1.5.0"


# ---------- 5. apply: marketplace.json metadata.version ----------


def test_apply_updates_marketplace_metadata_version(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    data = json.loads(
        (tmp_path / ".claude-plugin" / "marketplace.json").read_text("utf-8")
    )
    assert data["metadata"]["version"] == "1.5.0"


# ---------- 6. apply: marketplace plugins[0].description semver prefix ----------


def test_apply_updates_marketplace_plugin_description_semver_prefix(
    bump_module, tmp_path
):
    _write_5_file_workspace(tmp_path)

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    data = json.loads(
        (tmp_path / ".claude-plugin" / "marketplace.json").read_text("utf-8")
    )
    desc = data["plugins"][0]["description"]
    assert desc.startswith("v1.5.0 — "), (
        f"plugins[0].description semver prefix not bumped, got: {desc[:40]!r}"
    )
    # body content preserved (no description rewriting beyond prefix)
    assert "fake plugin description" in desc, "description body must be preserved"


# ---------- 7. apply: README banner ----------


def test_apply_updates_readme_status_banner(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    body = (tmp_path / "README.md").read_text("utf-8")
    assert "**Status:** v1.5.0 —" in body, "README banner not bumped"
    assert "**Status:** v1.4.0" not in body, "old README banner persists"


# ---------- 8. apply: INSTALL banner (blockquote + inline-bold) ----------


def test_apply_updates_install_banner_blockquote(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    body = (tmp_path / "docs" / "INSTALL.md").read_text("utf-8")
    assert "> Status: **v1.5.0**" in body, (
        "INSTALL banner (blockquote+inline-bold) not bumped"
    )
    assert "**v1.4.0**" not in body, "old INSTALL banner version persists"


# ---------- 9. apply: RELEASE_NOTES missing -> WARN, no auto-create ----------


def test_apply_warns_release_notes_missing_no_auto_create(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)
    # target version's RELEASE_NOTES file deliberately NOT created

    result = bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    assert not (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").exists(), (
        "apply MUST NOT auto-create RELEASE_NOTES (manual authoring required)"
    )
    warnings = result.get("warnings", [])
    assert any("RELEASE_NOTES_v1.5.0.md" in w for w in warnings), (
        f"missing release notes warning expected, got: {warnings}"
    )


# ---------- 10. idempotent ----------


def test_apply_idempotent_when_target_already_set(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path, current_version="1.5.0")
    (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").write_text("# v1.5.0\n", "utf-8")
    snapshot = {
        p: (tmp_path / p).read_text("utf-8")
        for p in [
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            "README.md",
            "docs/INSTALL.md",
        ]
    }

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    for path, before in snapshot.items():
        after = (tmp_path / path).read_text("utf-8")
        assert before == after, f"idempotent apply changed {path}"


# ---------- 11. test_version_sync invariant preserved ----------


def test_apply_preserves_test_version_sync_invariant_format(bump_module, tmp_path):
    """After apply, plugin.json + README + INSTALL banner versions agree
    (the same invariant tests/ci/test_version_sync.py asserts)."""
    _write_5_file_workspace(tmp_path)
    (tmp_path / "docs" / "RELEASE_NOTES_v1.5.0.md").write_text(
        "# v1.5.0\n\nDraft.\n", "utf-8"
    )

    bump_module.bump(target_version="1.5.0", repo_root=tmp_path, apply=True)

    plugin = json.loads(
        (tmp_path / ".claude-plugin" / "plugin.json").read_text("utf-8")
    )
    readme = (tmp_path / "README.md").read_text("utf-8")
    install = (tmp_path / "docs" / "INSTALL.md").read_text("utf-8")

    plug_v = plugin["version"]
    readme_m = re.search(
        r"\*\*Status:\*\*\s+v(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)", readme
    )
    install_m = re.search(
        r"Status:\s+\*\*v(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)\*\*", install
    )

    assert plug_v == "1.5.0"
    assert readme_m is not None and readme_m.group(1) == plug_v, (
        f"README banner ({readme_m.group(1) if readme_m else None!r}) "
        f"!= plugin.json ({plug_v!r}) post-apply"
    )
    assert install_m is not None and install_m.group(1) == plug_v, (
        f"INSTALL banner ({install_m.group(1) if install_m else None!r}) "
        f"!= plugin.json ({plug_v!r}) post-apply"
    )


# ---------- 12. invalid semver ----------


def test_invalid_semver_raises_value_error(bump_module, tmp_path):
    _write_5_file_workspace(tmp_path)

    with pytest.raises(ValueError, match=r"semver|version"):
        bump_module.bump(
            target_version="not-a-semver", repo_root=tmp_path, apply=False
        )


# ---------- 13. main() entry for CLI ----------


def test_module_exposes_main_for_cli(bump_module):
    assert hasattr(bump_module, "main"), (
        "module must expose main() callable for CLI invocation"
    )
    assert callable(bump_module.main)
