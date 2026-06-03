"""tests/reporting/test_template_dialect.py — P2-03 template dialect lock.

The engine has TWO placeholder dialects:

  * ``string.Template`` ``$var`` / ``${var}`` — rendered by
    ``scripts/reporting/render_template.py`` (stdlib). Used by the
    reporting templates under ``templates/reports/``.
  * ``{{PLACEHOLDER}}`` double-brace — filled skill-side by the
    content-generation skills. Used by ``templates/content/``.

``render_template.py`` (string.Template) silently leaves ``{{...}}`` tokens
verbatim, and the content skills leave ``$var`` tokens verbatim — so a
template fed to the WRONG renderer ships with unresolved placeholders and
no error. ``templates/manifest.json`` declares which dialect each family
owns; these tests enforce that contract so the drift cannot return.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _REPO_ROOT / "templates" / "manifest.json"

# The only two placeholder dialects in the engine.
_DOUBLE_BRACE = re.compile(r"\{\{[^}\n]+\}\}")
_DOLLAR_VAR = re.compile(r"\$\{?[A-Za-z_][A-Za-z0-9_]*\}?")

# dialect name -> (the placeholder syntax it MUST use,
#                  the FOREIGN syntax it MUST NOT contain).
_DIALECT_RULES = {
    "string.Template": (_DOLLAR_VAR, _DOUBLE_BRACE),
    "double-brace": (_DOUBLE_BRACE, _DOLLAR_VAR),
}


def _manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _family_files(family: dict) -> list[Path]:
    return sorted((_REPO_ROOT / family["root"]).glob(family["glob"]))


def test_manifest_exists_and_declares_known_dialects() -> None:
    """The manifest must exist and every family must declare a dialect this
    test knows how to enforce, with the required descriptive keys."""
    manifest = _manifest()
    families = manifest.get("families")
    assert families, "templates/manifest.json declares no families"
    for fam in families:
        for key in ("name", "root", "glob", "dialect", "renderer"):
            assert key in fam, f"family {fam.get('name')!r} missing key {key!r}"
        assert fam["dialect"] in _DIALECT_RULES, (
            f"family {fam['name']!r} declares unknown dialect {fam['dialect']!r}"
        )


def test_every_template_matches_its_declared_dialect() -> None:
    """Each template in a family must (a) contain at least one placeholder of
    its declared dialect and (b) contain NO foreign-dialect placeholder that
    the family's renderer would leave unresolved."""
    checked = 0
    for fam in _manifest()["families"]:
        want, forbid = _DIALECT_RULES[fam["dialect"]]
        files = _family_files(fam)
        assert files, f"family {fam['name']!r} glob matched no templates"
        for path in files:
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(_REPO_ROOT)
            assert want.search(text), (
                f"{rel}: declared dialect {fam['dialect']!r} but no matching "
                f"placeholder found — is it really a {fam['dialect']} template?"
            )
            stray = forbid.search(text)
            # Message is evaluated only on failure, where ``stray`` is a Match.
            assert stray is None, (
                f"{rel}: declared {fam['dialect']!r} but contains foreign "
                f"placeholder {stray.group(0)!r} — the {fam['renderer']} "
                f"renderer would leave it unresolved"
            )
            checked += 1
    assert checked >= 5, "expected to scan several templates"


def test_no_template_is_orphaned_from_the_manifest() -> None:
    """Every ``*.template.*`` file on disk must belong to a declared family,
    so adding a new template family without a manifest entry (the exact
    P2-03 root cause: no dialect declaration) fails loudly."""
    declared: set[Path] = set()
    for fam in _manifest()["families"]:
        declared.update(_family_files(fam))
    on_disk = set((_REPO_ROOT / "templates").rglob("*.template.*"))
    orphans = sorted(str(p.relative_to(_REPO_ROOT)) for p in on_disk - declared)
    assert not orphans, f"templates not covered by manifest: {orphans}"
