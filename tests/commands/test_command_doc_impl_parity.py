"""codex-audit finding 10: three commands documented one interface but their
inline shell implemented another.
  10a pseo-init: prose says extra flags pass via $ARGUMENTS, but the dry-run
      invocation only forwarded --project/$DOMAIN_FLAG (flags silently dropped).
  10b pseo-quickwin: referenced a sheet 'gsc_landing_query' that does not exist
      (real sheet is 'gsc_performance').
  10c pseo-cannibalization: argument-hint advertises --days-back/--min-impressions
      but the body read positional $2/$3 (so the flag form mis-bound).
"""
from pathlib import Path

CMD = Path(__file__).resolve().parents[2] / "commands"


def test_pseo_init_dryrun_forwards_extra_flags():
    t = (CMD / "pseo-init.md").read_text("utf-8")
    inv = [ln for ln in t.splitlines() if "bootstrap_project.py" in ln and "python3" in ln]
    assert inv, "no python3 bootstrap_project.py invocation found"
    assert any("$EXTRA" in ln or "$ARGUMENTS" in ln for ln in inv), (
        "dry-run invocation must forward the extra flags ($EXTRA/$ARGUMENTS), "
        "not just --project/$DOMAIN_FLAG"
    )


def test_pseo_quickwin_uses_real_sheet_name():
    t = (CMD / "pseo-quickwin.md").read_text("utf-8")
    assert "gsc_landing_query" not in t, "references non-existent sheet gsc_landing_query"
    assert "gsc_performance" in t


def test_pseo_cannibalization_flag_doc_matches_parsing():
    t = (CMD / "pseo-cannibalization.md").read_text("utf-8")
    advertises_flags = "--days-back" in t and "--min-impressions" in t
    reads_positional = "${2:-" in t or "${3:-" in t
    # either parse the advertised flags, or stop advertising them — not both
    assert not (advertises_flags and reads_positional), (
        "advertises --days-back/--min-impressions but reads positional $2/$3"
    )
