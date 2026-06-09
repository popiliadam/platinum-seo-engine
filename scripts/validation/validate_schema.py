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

`format` keywords (uri, date-time, date) are ENFORCED via a custom FormatChecker
with inline check functions (P1-02) — no extra dependency, no silent skip.
"""

from __future__ import annotations

import json
import sys
from datetime import date as _date
from datetime import datetime as _datetime
from pathlib import Path
from urllib.parse import urlparse

import jsonschema
from jsonschema import Draft7Validator, FormatChecker

# --- Format enforcement (P1-02) ---------------------------------------------
# jsonschema treats `format` as a pure annotation unless a FormatChecker is
# supplied AND a checker is registered for that format name (formats whose
# optional backing lib is absent are silently skipped). The schemas in this
# repo use `uri`, `date-time`, and `date` (see `rg '"format"' schemas/`); we
# register INLINE checkers for each so enforcement needs no extra dependency
# and cannot silently degrade. `format` only constrains strings per the spec —
# each checker defers non-strings to `type` by returning True.
_FORMAT_CHECKER = FormatChecker()


@_FORMAT_CHECKER.checks("uri", raises=ValueError)
def _is_uri(value: object) -> bool:
    if not isinstance(value, str):
        return True
    parsed = urlparse(value)
    return bool(parsed.scheme and (parsed.netloc or parsed.path))


@_FORMAT_CHECKER.checks("date-time", raises=ValueError)
def _is_date_time(value: object) -> bool:
    """Storage timestamps MUST be canonical UTC with a 'Z' suffix.

    rules/time-discipline.md §8.10 fixes the storage layer to UTC `…Z` only;
    `format: date-time` is the rule's schema-side enforcement point. So this
    checker REJECTS naive (tz-less) and non-UTC values — `…T12:00:00`,
    `…+03:00`, even `…+00:00` — even though they are structurally valid
    RFC 3339, because they are the exact drift vectors the rule forbids and
    `…Z` is its canonical form. Microseconds ARE allowed (events_writer emits
    `…S.%fZ`). Non-strings defer to `type` (format only constrains strings).
    """
    if not isinstance(value, str):
        return True
    if not value.endswith("Z"):
        raise ValueError("timestamp must be UTC with a 'Z' suffix (rules/time-discipline.md §8.10)")
    # Parse the calendar instant to reject structurally-invalid values. Python
    # 3.10's fromisoformat rejects a bare 'Z', so swap the verified suffix for
    # the equivalent explicit zero offset.
    _datetime.fromisoformat(value[:-1] + "+00:00")
    return True


@_FORMAT_CHECKER.checks("date", raises=ValueError)
def _is_date(value: object) -> bool:
    if not isinstance(value, str):
        return True
    _date.fromisoformat(value)
    return True


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


def build_validator(schema: object) -> Draft7Validator:
    """Construct the Draft 7 validator the CLI uses.

    Extracted so the validator-construction contract (draft + format
    enforcement) is unit-testable in isolation from argv/IO handling.
    """
    return Draft7Validator(schema, format_checker=_FORMAT_CHECKER)


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

    validator = build_validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.absolute_path) or "<root>"
        print(f"validation failed at {location}: {first.message}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
