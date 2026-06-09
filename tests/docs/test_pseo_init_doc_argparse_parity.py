"""Batch-E finding 14 — /pseo-init doc must not advertise flags the script
rejects, and its documented sf-block default must match the code.

  * pseo-init.md (argument-hint + the "Schema version" section) advertised
    `--schema-version`, but scripts/state/bootstrap_project.py's argparse has no
    such option — so passing it makes argparse exit non-zero ("unrecognized
    arguments"). The command forwards extra `--flags` verbatim (`$EXTRA`), so an
    operator who copies the advertised flag gets a hard error.
  * pseo-init.md documented the sf-block default
    `allowed_directory: "/Users/apple/seo_spider_mcp_server"`, but
    bootstrap_project.DEFAULT_SF_MCP_BLOCK emits `allowed_directory: None`
    (operator overrides per project — D-SF-18).

Both cites read GROUND TRUTH (the live argparse option strings + the live
default dict), so the doc cannot drift from the script again.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.state import bootstrap_project

_ROOT = Path(__file__).resolve().parents[2]
_DOC = (_ROOT / "commands" / "pseo-init.md").read_text(encoding="utf-8")
_SRC = (_ROOT / "scripts" / "state" / "bootstrap_project.py").read_text(encoding="utf-8")


def _argparse_flags() -> set[str]:
    """The real long options bootstrap_project.py accepts (ground truth)."""
    return set(re.findall(r'add_argument\(\s*["\'](--[a-z][a-z-]*)', _SRC))


def _doc_flags() -> set[str]:
    """Every `--flag` token the doc mentions (argument-hint + body)."""
    # Exclude the shell splice `--${ARGUMENTS#*--}` (not a literal flag).
    return {f for f in re.findall(r'--[a-z][a-z-]+', _DOC)}


def test_every_documented_flag_exists_in_argparse() -> None:
    real = _argparse_flags()
    documented = _doc_flags()
    unsupported = documented - real
    assert not unsupported, (
        f"pseo-init.md advertises flags bootstrap_project.py rejects: "
        f"{sorted(unsupported)}. Either implement them in argparse or remove "
        f"them from the doc."
    )


def test_schema_version_flag_not_advertised() -> None:
    # Explicit regression pin for the headline drift: argparse has no
    # --schema-version, so the doc must not advertise it.
    assert "--schema-version" not in _argparse_flags()
    assert "--schema-version" not in _DOC, (
        "pseo-init.md must not advertise --schema-version (bootstrap_project.py "
        "emits SCHEMA_VERSION natively; there is no such CLI flag)."
    )


def test_sf_allowed_directory_default_doc_matches_code() -> None:
    default = bootstrap_project.DEFAULT_SF_MCP_BLOCK["mcp"]["allowed_directory"]
    # Code default is None → the doc must not present a hardcoded path AS the
    # bootstrap default.
    assert default is None, "test assumes code default None; update if changed"
    assert '"/Users/apple/seo_spider_mcp_server"' not in _DOC, (
        "pseo-init.md documents a hardcoded sf allowed_directory default, but "
        "bootstrap_project.py emits null (operator overrides per project)."
    )
    # And it should explicitly say the default is null/None somewhere in the
    # sf-block description.
    assert re.search(r"allowed_directory.{0,12}\b(null|None)\b", _DOC), (
        "pseo-init.md must document allowed_directory's real default (null)."
    )
