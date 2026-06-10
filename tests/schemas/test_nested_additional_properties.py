"""FIX-J: every `type: object` node in every schema MUST declare
`additionalProperties` explicitly (set to false during FIX-J unless allowlisted).

Audit evidence (re-derived 2026-06-10): 13+ schemas accepted unknown fields in
NESTED objects — e.g. `portfolio-config.schema.json::cadence.weekly_brief`
silently accepted an UNKNOWN_FIELD. A typo'd nested key validated and the value
was dropped at read time. This test locks every object node closed, with a
small audited allowlist for nodes that MUST stay open.

Scope decision (deliberate): the invariant targets nodes that carry an explicit
`type: object` (or a type union containing "object"). It does NOT touch the
property-bearing-but-typeless subschemas inside `if`/`allOf` discriminator
clauses (events / workflow-run / mcp-tool-registry / intent-marker / schedule):
an `if` block is a boolean MATCH condition, not a type constraint — adding
`additionalProperties: false` there would make the conditional match only objects
that have *exactly* the discriminator key, breaking the conditional. Those nodes
have no `type: object` and so are correctly out of scope.

Allowlist (`nested_additional_properties_allowlist.json`) holds the intentionally
open nodes, each with a one-line justification. The test also fails if an
allowlist entry is stale (node gone / already closed) or lacks a justification,
so the allowlist cannot silently rot.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
ALLOWLIST_PATH = Path(__file__).parent / "nested_additional_properties_allowlist.json"

# JSON-Schema keywords whose values contain subschemas.
_SCHEMA_MAP_KW = ("properties", "patternProperties", "definitions", "$defs")
_SCHEMA_LIST_KW = ("allOf", "anyOf", "oneOf")
_SCHEMA_SINGLE_KW = (
    "not", "if", "then", "else", "contains", "propertyNames",
    "additionalItems", "items", "additionalProperties",
)


def _pointer(path: list) -> str:
    return "#/" + "/".join(str(p) for p in path) if path else "#"


def _open_object_nodes(schema: dict) -> list[str]:
    """Return canonical JSON-pointers to every `type: object` node that does NOT
    declare `additionalProperties`."""
    found: list[str] = []

    def walk(node, path: list) -> None:
        if not isinstance(node, dict):
            return
        t = node.get("type")
        is_object = t == "object" or (isinstance(t, list) and "object" in t)
        if is_object and "additionalProperties" not in node:
            found.append(_pointer(path))
        for kw in _SCHEMA_MAP_KW:
            sub = node.get(kw)
            if isinstance(sub, dict):
                for name, child in sub.items():
                    walk(child, path + [kw, name])
        for kw in _SCHEMA_LIST_KW:
            sub = node.get(kw)
            if isinstance(sub, list):
                for i, child in enumerate(sub):
                    walk(child, path + [kw, i])
        for kw in _SCHEMA_SINGLE_KW:
            sub = node.get(kw)
            if isinstance(sub, dict):
                walk(sub, path + [kw])
        if isinstance(node.get("items"), list):
            for i, child in enumerate(node["items"]):
                walk(child, path + ["items", i])
        deps = node.get("dependencies")
        if isinstance(deps, dict):
            for name, child in deps.items():
                if isinstance(child, dict):
                    walk(child, path + ["dependencies", name])

    walk(schema, [])
    return found


def _schema_files() -> list[Path]:
    return sorted(SCHEMAS_DIR.glob("*.schema.json"))


def _load_allowlist() -> dict:
    data = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


ALLOWLIST = _load_allowlist()


@pytest.mark.parametrize("schema_path", _schema_files(), ids=lambda p: p.name)
def test_every_object_node_declares_additional_properties(schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    open_nodes = _open_object_nodes(schema)
    allowed = ALLOWLIST.get(schema_path.name, {})
    offenders = [ptr for ptr in open_nodes if ptr not in allowed]
    assert not offenders, (
        f"{schema_path.name}: {len(offenders)} type:object node(s) omit "
        f"`additionalProperties` and are not allowlisted:\n"
        + "\n".join(f"  - {p}" for p in offenders)
        + "\n(Set `additionalProperties: false`, or add to "
        "nested_additional_properties_allowlist.json with a justification.)"
    )


def test_allowlist_entries_are_live_and_justified() -> None:
    """Every allowlisted (schema, pointer) must still resolve to an actually-open
    node, and carry a non-empty justification. Prevents allowlist rot."""
    stale: list[str] = []
    unjustified: list[str] = []
    for schema_name, nodes in ALLOWLIST.items():
        schema_path = SCHEMAS_DIR / schema_name
        assert schema_path.exists(), f"allowlist names missing schema {schema_name!r}"
        open_nodes = set(_open_object_nodes(json.loads(schema_path.read_text(encoding="utf-8"))))
        for ptr, justification in nodes.items():
            if ptr not in open_nodes:
                stale.append(f"{schema_name} :: {ptr}")
            if not isinstance(justification, str) or len(justification.strip()) < 10:
                unjustified.append(f"{schema_name} :: {ptr}")
    assert not stale, (
        "Stale allowlist entries (node closed or removed — drop them):\n"
        + "\n".join(f"  - {s}" for s in stale)
    )
    assert not unjustified, (
        "Allowlist entries missing a one-line justification:\n"
        + "\n".join(f"  - {u}" for u in unjustified)
    )
