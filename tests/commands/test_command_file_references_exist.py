"""tests/commands/test_command_file_references_exist.py — P1-14 lock.

Two slash commands carried dangling references that mislead any reader (or
skill) that follows them:
  - pseo-cannibalization.md cited ``schemas/gsc-mapping.schema.json``
    (real file: ``schemas/gsc-tool-mapping.schema.json``);
  - pseo-schema-audit.md cited ``schemas/dataforseo-mapping.schema.json``
    (real: ``schemas/dataforseo-endpoint-mapping.schema.json``) AND used the
    provenance token ``source.kind=sf_export``, which is NOT in the
    events.schema enum — the file-based SF source kind is ``sf_csv``.

These tests assert every ``schemas/*.json`` reference in a command resolves on
disk, and every ``source.kind=<value>`` token is a member of the events.schema
source-kind enum (parsed from the schema, so it tracks future enum changes).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMMANDS = REPO / "commands"
EVENTS_SCHEMA = REPO / "schemas" / "events.schema.json"

# A schemas/<file>.json path (fragment like '#gbp_audit' is naturally excluded
# because '#' is outside the character class).
_SCHEMA_REF = re.compile(r"schemas/[A-Za-z0-9_.-]+\.json")
_SOURCE_KIND = re.compile(r"source\.kind\s*=\s*([a-z_]+)")


def _command_files() -> list[Path]:
    return sorted(p for p in COMMANDS.glob("*.md") if p.is_file())


def _find_enum(node: object, *required: str) -> list | None:
    """Recursively find an ``enum`` list containing all ``required`` members."""
    if isinstance(node, dict):
        enum = node.get("enum")
        if isinstance(enum, list) and all(r in enum for r in required):
            return enum
        for value in node.values():
            found = _find_enum(value, *required)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_enum(value, *required)
            if found:
                return found
    return None


def _source_kind_enum() -> set[str]:
    schema = json.loads(EVENTS_SCHEMA.read_text(encoding="utf-8"))
    enum = _find_enum(schema, "sf_csv", "gsc_mcp")
    assert enum, "could not locate the source.kind enum in events.schema.json"
    return set(enum)


def test_scanners_find_something() -> None:
    """Anchor: the regexes must actually match real references (no vacuous green)."""
    blob = "".join(p.read_text(encoding="utf-8") for p in _command_files())
    assert _SCHEMA_REF.findall(blob), "no schemas/*.json references found at all"
    assert _SOURCE_KIND.findall(blob), "no source.kind tokens found at all"
    assert _source_kind_enum() >= {"sf_csv", "gsc_mcp"}


def test_command_schema_references_resolve() -> None:
    """Every schemas/*.json a command references must exist on disk."""
    missing: dict[str, list[str]] = {}
    for path in _command_files():
        text = path.read_text(encoding="utf-8")
        for ref in sorted(set(_SCHEMA_REF.findall(text))):
            if not (REPO / ref).is_file():
                missing.setdefault(path.name, []).append(ref)
    assert not missing, (
        "Command files reference schema files that do not exist:\n"
        + "\n".join(f"  {name}: {refs}" for name, refs in sorted(missing.items()))
    )


def test_command_source_kind_tokens_valid() -> None:
    """Every source.kind=<value> token must be in the events.schema enum."""
    valid = _source_kind_enum()
    offenders: dict[str, list[str]] = {}
    for path in _command_files():
        text = path.read_text(encoding="utf-8")
        for kind in sorted(set(_SOURCE_KIND.findall(text))):
            if kind not in valid:
                offenders.setdefault(path.name, []).append(kind)
    assert not offenders, (
        f"Command files use source.kind values outside the events.schema enum "
        f"{sorted(valid)}:\n"
        + "\n".join(f"  {name}: {kinds}" for name, kinds in sorted(offenders.items()))
    )
