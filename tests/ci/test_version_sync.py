"""tests/ci/test_version_sync.py — version sync invariant (ADR-036).

`.claude-plugin/plugin.json` ``version``, ``README.md`` banner semver,
the latest ``docs/RELEASE_NOTES_v*.md`` filename, and (when present)
the most recent annotated git tag MUST agree exactly.  Drift between
any two breaks ``/plugin add`` discovery or installer-banner trust.

Test scope (CI-friendly):
  - plugin.json + README banner + RELEASE_NOTES file presence parity.
  - INSTALL.md status banner parity.
  - Git tag parity is asserted only when the tag is present locally
    (skipped on fresh clones / pre-tag builds).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PLUGIN_JSON = REPO / ".claude-plugin" / "plugin.json"
README = REPO / "README.md"
INSTALL = REPO / "docs" / "INSTALL.md"
RELEASE_NOTES_GLOB = "RELEASE_NOTES_v*.md"

SEMVER = re.compile(r"v?(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)")


def _plugin_json_version() -> str:
    data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    version = data.get("version")
    assert isinstance(version, str) and version, "plugin.json missing 'version'"
    return version


def _readme_banner_version() -> str:
    """Extract the Status: **v<semver>** banner version from README.md.

    README and INSTALL share the same banner format after the public-
    release README rewrite: ``Status: **v<semver>** — ...`` (plain
    label, bold version). One regex = one invariant across both files.
    """
    text = README.read_text(encoding="utf-8")
    m = re.search(r"Status:\s+\*\*v(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)\*\*", text)
    assert m, "README.md missing Status: **v<semver>** banner"
    return m.group(1)


def _install_banner_version() -> str:
    text = INSTALL.read_text(encoding="utf-8")
    m = re.search(r"Status:\s+\*\*v(\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?)\*\*", text)
    assert m, "INSTALL.md missing Status: **v<semver>** banner"
    return m.group(1)


def _latest_release_notes_version() -> str:
    files = sorted((REPO / "docs").glob(RELEASE_NOTES_GLOB))
    assert files, f"No RELEASE_NOTES_v*.md under docs/"
    # files are sorted lexically; semver normally lexically sorts correctly for
    # MAJOR.MINOR.PATCH within the same major. For multi-major sort, take the
    # one whose embedded semver is lexically max (good enough for v1.x).
    best = max(files, key=lambda p: p.stem)
    m = SEMVER.search(best.stem)
    assert m, f"Cannot parse semver from {best.name}"
    return m.group(1)


def _git_tag_version() -> str | None:
    """Return latest annotated git tag's semver or None when absent / git missing."""
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    tag = out.stdout.strip()
    if not tag:
        return None
    m = SEMVER.search(tag)
    return m.group(1) if m else None


def test_plugin_json_version_present_and_semver() -> None:
    version = _plugin_json_version()
    assert SEMVER.fullmatch(version), f"plugin.json version not semver: {version!r}"


def test_readme_banner_matches_plugin_json() -> None:
    assert _readme_banner_version() == _plugin_json_version(), (
        f"README **Status:** banner ({_readme_banner_version()!r}) != "
        f"plugin.json version ({_plugin_json_version()!r})"
    )


def test_install_banner_matches_plugin_json() -> None:
    assert _install_banner_version() == _plugin_json_version(), (
        f"INSTALL.md banner ({_install_banner_version()!r}) != "
        f"plugin.json version ({_plugin_json_version()!r})"
    )


def test_release_notes_file_matches_plugin_json() -> None:
    assert _latest_release_notes_version() == _plugin_json_version(), (
        f"Latest RELEASE_NOTES_v{_latest_release_notes_version()}.md != "
        f"plugin.json version ({_plugin_json_version()!r})"
    )


def _semver_tuple(s: str) -> tuple[int, int, int]:
    """Parse MAJOR.MINOR.PATCH (ignore pre-release suffix for ordering)."""
    core = s.split("-", 1)[0]
    parts = core.split(".")
    return (int(parts[0]), int(parts[1]), int(parts[2]))


def test_git_tag_matches_plugin_json_when_present() -> None:
    """Git tag parity asserted only when the tag is at or ahead of plugin.json.

    During mid-release development the tag lags plugin.json (we bump the json
    first, tag the release later — Task 3.7).  Skip in that lagging window.
    """
    tag = _git_tag_version()
    if tag is None:
        pytest.skip("No annotated git tag yet (pre-release or fresh clone)")
    plug = _plugin_json_version()
    if _semver_tuple(tag) < _semver_tuple(plug):
        pytest.skip(
            f"Latest git tag (v{tag}) lags plugin.json (v{plug}) — mid-release dev."
        )
    assert tag == plug, (
        f"Latest git tag (v{tag}) != plugin.json version (v{plug}) — "
        "tag must be bumped to match plugin.json before release."
    )
