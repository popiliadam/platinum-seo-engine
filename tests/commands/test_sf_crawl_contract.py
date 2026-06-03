"""tests/commands/test_sf_crawl_contract.py — P0-06 lock.

``commands/pseo-sf-crawl.md`` documented an **invalid runtime contract** that
would fail if a reader followed it literally:

  - ``sf_import.py ... --source-run-id {run_id}`` — the sf_import *script* CLI
    accepts only ``--project`` / ``--sf-export-path`` / ``--workspace-root`` /
    ``--dry-run``; ``--source-run-id`` makes argparse **exit 2**
    (``source_run_id`` is an sf-import *skill-frontmatter* input, not a flag).
  - ``save_report=True`` on the SF export step — the real SF export tools
    (``sf_generate_report`` / ``sf_generate_bulk_export`` /
    ``sf_export_seo_element_urls``) have **no** ``save_report`` arg; a report
    persists via ``export_type="CSV"`` + ``file_path`` (orchestrator skill
    SKILL.md §"Dispatch contract").
  - an **incomplete** required-SF-MCP-tools list — it named 5 tools but the
    skill also calls ``sf_generate_bulk_export`` + ``sf_export_seo_element_urls``
    (two of the three real export tools).

These tests pin the contract to the real ``sf_import.py`` argparse surface and
the skill's tool set so the drift cannot return.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SF_CRAWL = REPO / "commands" / "pseo-sf-crawl.md"
SF_IMPORT = REPO / "scripts" / "ingestion" / "sf_import.py"

# Two real SF export tools the orchestrator skill calls but the command omitted.
REQUIRED_NEW_SF_TOOLS = (
    "mcp__sf__sf_generate_bulk_export",
    "mcp__sf__sf_export_seo_element_urls",
)


def _sf_import_argparse_flags() -> set[str]:
    """The flags sf_import.py's argparse actually accepts (source of truth)."""
    src = SF_IMPORT.read_text(encoding="utf-8")
    return set(re.findall(r"""add_argument\(\s*["'](--[a-z0-9-]+)["']""", src))


def test_no_source_run_id_flag() -> None:
    """The bogus --source-run-id flag must not appear (argparse exit 2)."""
    text = SF_CRAWL.read_text(encoding="utf-8")
    assert "--source-run-id" not in text, (
        "pseo-sf-crawl.md still cites sf_import --source-run-id, which makes "
        "argparse exit 2 (source_run_id is a skill-frontmatter input, not a flag)."
    )


def test_no_save_report_true() -> None:
    """The fictional save_report=True arg must not appear."""
    text = SF_CRAWL.read_text(encoding="utf-8")
    assert "save_report=True" not in text, (
        "pseo-sf-crawl.md still cites save_report=True; the SF export tools have "
        'no save_report arg (persistence is export_type="CSV" + file_path).'
    )


def test_sf_import_flags_match_argparse() -> None:
    """Every --flag on an sf_import invocation line must exist in its argparse."""
    valid = _sf_import_argparse_flags()
    assert valid, "could not parse sf_import.py argparse flags"
    text = SF_CRAWL.read_text(encoding="utf-8")
    offenders: dict[int, list[str]] = {}
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "sf_import" not in line:  # underscore = the script, not 'sf-import' skill prose
            continue
        cited = set(re.findall(r"--[a-z0-9-]+", line))
        unknown = cited - valid
        if unknown:
            offenders[lineno] = sorted(unknown)
    assert not offenders, (
        f"pseo-sf-crawl.md cites sf_import flags absent from its argparse "
        f"{sorted(valid)}:\n{offenders}"
    )


def test_required_sf_mcp_tools_complete() -> None:
    """The required-MCP-tools list must include both missing export tools."""
    text = SF_CRAWL.read_text(encoding="utf-8")
    missing = [t for t in REQUIRED_NEW_SF_TOOLS if t not in text]
    assert not missing, (
        "pseo-sf-crawl.md required-MCP-tools list is missing real SF export "
        f"tools the skill calls: {missing}"
    )
