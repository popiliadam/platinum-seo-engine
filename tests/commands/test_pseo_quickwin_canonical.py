"""H11 (FIX-H): /pseo-quickwin canonical band (11-20) + report filename.

The skill defaults and the page-2 uplift model target positions 11-20; the
report template is ``quickwin.template.md`` -> ``{date}-quickwin.md``. The
command doc's trigger phrase lagged at '8-20' and one narrative line used the
non-canonical '{date}-quick-wins.md'. Canonical band = 11-20 (verified against
the skill defaults), canonical report name = {date}-quickwin.md (verified
against tests/skills/test_quick_wins.py).
"""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
CMD = ROOT / "commands" / "pseo-quickwin.md"


def test_quickwin_band_is_11_20_not_8_20():
    t = CMD.read_text(encoding="utf-8")
    assert "8-20" not in t, "quick-win band canonical is 11-20 (page-2 uplift), not 8-20"
    assert ("11-20" in t) or ("11–20" in t), "command must state the canonical 11-20 band"


def test_quickwin_report_filename_canonical():
    t = CMD.read_text(encoding="utf-8")
    assert "{date}-quickwin.md" in t, "report filename must match template quickwin.template.md"
    assert "{date}-quick-wins.md" not in t, (
        "non-canonical '{date}-quick-wins.md' must be aligned to '{date}-quickwin.md'"
    )
