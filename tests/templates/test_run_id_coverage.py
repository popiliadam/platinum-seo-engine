"""Regression: every templates/reports/*.md MUST carry both
`$run_id` placeholder AND `## Kanıt zinciri` H2 audit-trail section.

Locks K-06 (11/26 reports missing run_id) + K-07 (7/26 reports missing
Kanıt zinciri H2) audit findings. Audit trail discipline keeps replay
deterministic per Süleyman feedback_decisions_workflow ("kanıta dayalı").

After v1.4-deep-audit-fix Tier 3 Step 1: 26/26 PASS expected.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent
REPORTS_DIR = ROOT / "templates" / "reports"


@pytest.mark.parametrize("report_path", sorted(REPORTS_DIR.glob("*.md")))
def test_report_has_run_id(report_path):
    """Every report template MUST reference $run_id (string.Template syntax)
    so render-time hook can inject events.jsonl.next_run_id integer."""
    text = report_path.read_text(encoding="utf-8")
    assert re.search(r"\$run_id\b", text), (
        f"{report_path.name}: missing $run_id placeholder; per K-06 "
        f"audit-trail discipline, every report MUST emit run_id for replay."
    )


@pytest.mark.parametrize("report_path", sorted(REPORTS_DIR.glob("*.md")))
def test_report_has_kanit_zinciri(report_path):
    """Every report template MUST have a `## Kanıt zinciri` H2 section
    enumerating raw payload + run_id + skill provenance."""
    text = report_path.read_text(encoding="utf-8")
    assert re.search(r"^## Kanıt zinciri", text, re.MULTILINE), (
        f"{report_path.name}: missing `## Kanıt zinciri` H2 section; "
        f"per K-07 audit-trail discipline, every report MUST end with the "
        f"provenance block (raw_json_path + run_id + skill + timestamp)."
    )
