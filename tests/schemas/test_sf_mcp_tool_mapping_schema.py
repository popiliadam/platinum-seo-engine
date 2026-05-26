"""SF MCP Tool Mapping Contract v1.0 schema tests (v1.8 Phase 1 D-SF-08).

Mirrors the pattern of other meta-schema tests (gsc-tool-mapping,
dataforseo-endpoint-mapping, scrapling-output-mapping). Three core
contracts are locked here:

  1. The schema document itself parses as Draft 7 JSON Schema (no
     malformed pattern / enum / oneOf constructs).
  2. The shipped example instance under
     ``templates/sf-mcp/use-case-example.json`` validates against the
     schema (proves the schema accepts a minimal valid use-case registry).
  3. An instance using an unknown use-case key (outside the closed
     useCaseKey enum) is rejected (proves the propertyNames enum gate
     is active — no silent vocabulary drift).

These are the canonical "schema parses Draft7 / valid instance accepts /
unknown enum rejects" trio used across all meta-schemas in the engine.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "schemas" / "sf-mcp-tool-mapping.schema.json"
EXAMPLE_PATH = REPO / "templates" / "sf-mcp" / "use-case-example.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_example() -> dict:
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def test_schema_parses_as_draft7() -> None:
    """The schema document itself MUST be a valid Draft 7 JSON Schema —
    malformed pattern / enum / oneOf would surface here before any
    instance is validated."""
    schema = _load_schema()
    # check_schema raises jsonschema.exceptions.SchemaError on malformed.
    Draft7Validator.check_schema(schema)
    # Sanity-check the meta-schema bookkeeping fields the engine relies on.
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["$id"] == "http://platinum-seo-engine/schemas/sf-mcp-tool-mapping"
    assert schema["properties"]["schema_version"]["const"] == "1.0"
    assert (
        schema["properties"]["contract_for"]["const"]
        == "Screaming Frog 24 native MCP integration"
    )


def test_example_instance_validates() -> None:
    """The shipped ``templates/sf-mcp/use-case-example.json`` MUST validate
    against the schema — proves a minimal valid use-case registry shape is
    accepted and serves as a copy-paste starting point for new authoring."""
    schema = _load_schema()
    instance = _load_example()
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(instance))
    assert not errors, (
        "use-case-example.json must validate clean; got:\n"
        + "\n".join(f"  - {e.message} at {list(e.absolute_path)}" for e in errors)
    )


def test_unknown_use_case_key_rejected() -> None:
    """Instance with a use-case key OUTSIDE the closed useCaseKey enum MUST
    be rejected — propertyNames gate must be active. Vocabulary drift on
    use-case keys is a silent failure surface (orchestrator code switches
    behavior on the key), so the schema enforces it."""
    schema = _load_schema()
    instance = copy.deepcopy(_load_example())
    # Swap in an unknown key alongside the valid one.
    instance["use_cases"]["definitely_not_a_real_use_case"] = (
        instance["use_cases"]["crawl_trigger"]
    )
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = list(validator.iter_errors(instance))
    # propertyNames violations surface as errors against the use_cases
    # property (path = ["use_cases"]) with a message mentioning the key.
    pn_errors = [
        e for e in errors
        if "definitely_not_a_real_use_case" in str(e.message)
        or "propertyNames" in e.validator
    ]
    assert pn_errors, (
        "Expected propertyNames rejection for 'definitely_not_a_real_use_case' "
        f"on use_cases; validator returned: "
        + "; ".join(str(e.message) for e in errors[:5])
    )
