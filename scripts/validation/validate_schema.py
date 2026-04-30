#!/usr/bin/env python3
"""
validate_schema.py — generic JSON Schema validator (Draft 7).

Usage:
    validate_schema.py <data.json> <schema.json>

Exit codes:
    0  data is valid against schema
    1  data is invalid OR file/parse error

Stdout: empty on success (machine-parseable; reserved for future structured output).
Stderr: concise human-readable error message on failure.

Schemas in this repo declare $schema=http://json-schema.org/draft-07/schema# (ADR-012,
HTTP variant). We pin the validator to Draft7Validator to keep behavior deterministic
even if a schema omits the $schema declaration.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft7Validator


def _load_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        print(f"file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"invalid JSON in {path}: {exc.msg} (line {exc.lineno})", file=sys.stderr)
        sys.exit(1)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: validate_schema.py <data.json> <schema.json>", file=sys.stderr)
        return 1

    data_path = Path(argv[1])
    schema_path = Path(argv[2])

    data = _load_json(data_path)
    schema = _load_json(schema_path)

    try:
        Draft7Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        print(f"schema is malformed: {exc.message}", file=sys.stderr)
        return 1

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.absolute_path) or "<root>"
        print(f"validation failed at {location}: {first.message}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
