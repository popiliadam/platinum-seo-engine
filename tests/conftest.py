"""Shared fixtures for the test suite.

Provides workspace scaffolding and mock-fixture primitives used by Phase 3
``brand-onboarding`` Stage A/B/C tests (Tasks 3.2 / 3.3 / 3.4) and any
future skill tests that need a stand-in for the DataForSEO + Scrapling
MCP surface.

Fixtures here apply to *every* test directory below ``tests/``. Directory-
local fixtures (e.g. ``tests/skills/conftest.py``) extend without
shadowing — pytest walks conftest.py files from the rootdir down.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable

import pytest

# PEP 420 — make ``scripts.*`` importable when pytest is run from any cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# --------------------------------------------------------------------------
# Workspace factory — builds a minimal but schema-valid v1.5 project pack
# under a tmp_path. Used by Phase 3 brand-onboarding tests. v1.8 Phase 1
# bumped 1.4 → 1.5 alongside the project-config schema's sf-block addition.
# --------------------------------------------------------------------------

@pytest.fixture
def tmp_workspace_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[..., Path]:
    """Returns a callable that builds a per-call workspace.

    Usage:
        project_dir = tmp_workspace_factory(
            slug="test", profiles=["ymyl"], domain="https://example.com/"
        )

    Side effects:
        - Sets PSEO_WORKSPACE_ROOT env var to the freshly created root.
        - Writes a v1.5 project.config.json with the four required-ish
          fields populated to satisfy ``brand-onboarding`` lookups.

    Returns the ``projects/{slug}/`` directory.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PSEO_WORKSPACE_ROOT", str(workspace_root))

    def _build(
        slug: str = "test",
        profiles: list[str] | None = None,
        domain: str = "https://example.com/",
        market: str = "TR",
    ) -> Path:
        project_dir = workspace_root / "projects" / slug
        project_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "schema_version": "1.5",
            "project_id": slug,
            "domain": domain,
            "market": market,
            "language": {"content_locale": "tr-TR"},
            "currency": "TRY",
            "platform": "wordpress",
            "profiles": profiles or ["e-commerce"],
            "paths": {
                "workspace_root": str(workspace_root / "projects" / slug),
                "excel_filename": "master.xlsx",
                "sf_exports_dir": "inbox/sf",
                "staging_dir": "_state/cache",
                "reports_dir": "outputs/reports",
                "blog_dir": "outputs/content/drafts",
                "backups_dir": "_state/backups",
            },
            "gsc": {"site_url": domain},
            "dataforseo": {"location_code": 2792, "language_code": "tr"},
            "content_settings": {
                "experience_database": [],
                "original_research_database": [],
            },
        }
        (project_dir / "project.config.json").write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return project_dir

    return _build


# --------------------------------------------------------------------------
# MCP mock fixtures — discovery.py reads from these monkeypatch slots.
# Generic mocks return empty / None; named variants return canned shapes.
# --------------------------------------------------------------------------

@pytest.fixture
def mock_dfs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generic DFS mock: every _fetch_* returns ``None`` / empty list.
    Discovery output: empty drafts + empty topic_candidates."""
    from scripts.meta import brand_onboarding_discovery as d
    monkeypatch.setattr(d, "_fetch_whois_creation_year", lambda domain: None)
    monkeypatch.setattr(d, "_fetch_about_page", lambda domain: None)
    monkeypatch.setattr(d, "_fetch_business_listing", lambda domain, config: None)
    monkeypatch.setattr(d, "_fetch_top_keywords", lambda domain, config: [])


@pytest.fixture
def mock_scrapling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Generic Scrapling mock: case study fetch returns empty list."""
    from scripts.meta import brand_onboarding_discovery as d
    monkeypatch.setattr(d, "_fetch_case_study_pages", lambda domain: [])


@pytest.fixture
def mock_dfs_whois_2018(monkeypatch: pytest.MonkeyPatch) -> None:
    """DFS WHOIS returns domain creation year 2018."""
    from scripts.meta import brand_onboarding_discovery as d
    monkeypatch.setattr(d, "_fetch_whois_creation_year", lambda domain: 2018)
    monkeypatch.setattr(d, "_fetch_about_page", lambda domain: None)
    monkeypatch.setattr(d, "_fetch_business_listing", lambda domain, config: None)
    monkeypatch.setattr(d, "_fetch_top_keywords", lambda domain, config: [])


@pytest.fixture
def mock_dfs_keywords_top20(monkeypatch: pytest.MonkeyPatch) -> None:
    """DFS keywords-for-site returns a top-20 keyword list."""
    from scripts.meta import brand_onboarding_discovery as d
    top20 = [f"keyword-{i}" for i in range(1, 21)]
    monkeypatch.setattr(d, "_fetch_whois_creation_year", lambda domain: None)
    monkeypatch.setattr(d, "_fetch_about_page", lambda domain: None)
    monkeypatch.setattr(d, "_fetch_business_listing", lambda domain, config: None)
    monkeypatch.setattr(d, "_fetch_top_keywords", lambda domain, config: top20)


@pytest.fixture
def mock_dfs_budget_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    """DFS budget pre-flight returns False — discovery DURUR awaiting_approval."""
    from scripts.meta import brand_onboarding_discovery as d
    monkeypatch.setattr(d, "_budget_preflight", lambda: False)
