"""Live-fixture path resolution for tests that read the OPERATOR's real
workspace (gitignored ~1 GB Screaming-Frog crawls, real project configs).

These fixtures live under ``$PSEO_WORKSPACE_ROOT`` on the operator's machine
but are ABSENT on CI runners and fresh clones. Before this helper each test
hardcoded ``/Users/apple/Documents/platinum-seo-workspace/...`` (or the now-
deleted ``platinum-seo-workspace-staging``), so the suite was unportable and
some skip reasons lied ("missing on CI runner" when the path was gone
*everywhere*). Routing every live path through here makes the suite portable:
point ``PSEO_WORKSPACE_ROOT`` at any workspace, or leave it unset and the
dependent tests skip cleanly with an honest reason.

Behavior on the operator's machine is UNCHANGED — ``PSEO_WORKSPACE_ROOT``
already points at the workspace the old literals named.

Usage::

    from tests._live_fixtures import live_project_dir, requires_live

    _RAW = live_project_dir("demo-aluminum-ca") / "sf-exports" / "2026-06-02" / "raw"
    _CSV = _RAW / "issues_overview_report.csv"
    requires_csv = requires_live(_CSV, "staged demo-aluminum-ca SF issues CSV")

    @requires_csv
    def test_something(): ...
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# A guaranteed-absent sentinel so callers can build paths and ``skipif`` on
# ``.exists()`` WITHOUT a None-guard when PSEO_WORKSPACE_ROOT is unset.
_UNSET_SENTINEL = Path(__file__).resolve().parent / "_pseo_workspace_root_unset"


def live_workspace_root() -> Path:
    """The operator's live workspace root from ``PSEO_WORKSPACE_ROOT``.

    Returns a guaranteed-absent sentinel path when the env var is unset, so
    ``live_project_dir(...).exists()`` is simply ``False`` (→ clean skip)
    rather than raising. ``~`` is expanded.
    """
    val = os.environ.get("PSEO_WORKSPACE_ROOT")
    return Path(val).expanduser() if val else _UNSET_SENTINEL


def live_project_dir(slug: str) -> Path:
    """``$PSEO_WORKSPACE_ROOT/projects/{slug}`` (or ``<sentinel>/projects/{slug}``
    when the env var is unset)."""
    return live_workspace_root() / "projects" / slug


def requires_live(path: Path, label: str):
    """A ``pytest.mark.skipif`` that fires when ``path`` is absent.

    The reason names *what* is missing and *how* to make it present (set
    ``PSEO_WORKSPACE_ROOT`` to a workspace that contains it) — replacing the
    old, misleading "missing on CI runner" framing.
    """
    return pytest.mark.skipif(
        not path.exists(),
        reason=(
            f"live fixture absent ({label}): {path} — set PSEO_WORKSPACE_ROOT "
            "to a workspace containing it (gitignored operator data; absent on "
            "CI / fresh clones)"
        ),
    )


def live_slug(alias: str) -> str:
    """Resolve a synthetic slug alias to the operator's real project slug.

    The public repo carries only synthetic ``demo-*`` slugs (client-name
    scrub, 2026-07-08). Operators keep live coverage by mapping aliases to
    real workspace projects via ``PSEO_LIVE_SLUGS``, e.g.::

        export PSEO_LIVE_SLUGS="demo-aluminum-ca=<real>,demo-hvac=<real>"

    Unmapped aliases resolve to themselves, so the dependent tests skip
    cleanly (a synthetic project dir does not exist in a real workspace).
    """
    for pair in os.environ.get("PSEO_LIVE_SLUGS", "").split(","):
        key, _, value = pair.partition("=")
        if key.strip() == alias and value.strip():
            return value.strip()
    return alias
