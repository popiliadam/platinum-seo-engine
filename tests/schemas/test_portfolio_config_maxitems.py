"""Regression: portfolio-config schema active_projects.maxItems must admit the
real portfolio size (P0-04, engine part).

Codex audit P0-04: schemas/portfolio-config.schema.json capped active_projects
at maxItems=8, but the live shared/portfolio.json carries 10 entries, so schema
validation FAILed ("active_projects is too long"). Decision D2: raise the cap to
12 as a documented SOFT cap (not a hard product limit) — raise further as the
portfolio grows. The live-workspace migration of project.config.json files is a
SEPARATE manager-overseen step; this test guards the ENGINE schema only.

Test data builds fully-valid ActiveProjectEntry items (matching the schema's
required keys + every per-item constraint, e.g. priority maximum 10) inside a
complete portfolio document (all top-level required fields present), so the ONLY
differentiator between a passing and failing validation is the maxItems cap.
"""

import json
import pathlib

from jsonschema import Draft7Validator

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "schemas" / "portfolio-config.schema.json").read_text(encoding="utf-8")
)


def _item(i):
    """A fully-valid ActiveProjectEntry. priority is folded into the schema's
    1..10 range via modulo (duplicates are fine — active_projects declares no
    uniqueItems / per-priority uniqueness constraint)."""
    return {
        "slug": f"p{i}",
        "display_name": f"P{i}",
        "domain": f"https://p{i}.com/",
        "market": "TR",
        "workspace_path": f"projects/p{i}",
        "profile": ["e-commerce"],
        "platform": "wordpress",
        "priority": (i % 10) + 1,
        "last_sync_at": "2026-06-03T00:00:00Z",
    }


def _portfolio(n):
    """A complete, otherwise-valid portfolio doc with n active_projects, so the
    only constraint exercised by the count is active_projects.maxItems."""
    return {
        "schema_version": "1.1",
        "portfolio_id": "demo-portfolio",
        "display_name": "Demo Portfolio",
        "active_projects": [_item(i) for i in range(n)],
        "slas": {"weekly_sync_max_days": 7, "monthly_roundup_target_dom": 5},
        "cadence": {
            "weekly_brief": {"day": "Monday", "hour": 9},
            "monthly_roundup": {"day_of_month": 5, "hour": 9},
        },
    }


def test_maxitems_is_12():
    assert SCHEMA["properties"]["active_projects"]["maxItems"] == 12


def test_twelve_projects_validate():
    assert not list(Draft7Validator(SCHEMA).iter_errors(_portfolio(12)))


def test_thirteen_projects_fail():
    assert list(Draft7Validator(SCHEMA).iter_errors(_portfolio(13)))
