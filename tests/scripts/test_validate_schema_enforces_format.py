"""P1-02: validate_schema must actually ENFORCE JSON Schema `format`.

`Draft7Validator(schema)` without a `format_checker` treats `format` as a pure
annotation — `{"format": "uri"}` accepts any string. The schemas in this repo
use `format: uri | date-time | date` (see `rg '"format"' schemas/`) and expect
those to be enforced. This locks real enforcement via the CLI's own validator
factory (`build_validator`) so the contract can't silently regress.

We import `build_validator` — the exact factory `main()` uses — so the unit
test exercises the same construction path as the CLI.
"""
from __future__ import annotations

from scripts.validation.validate_schema import build_validator

URI_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"u": {"type": "string", "format": "uri"}},
}
DATETIME_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"d": {"type": "string", "format": "date-time"}},
}
DATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {"d": {"type": "string", "format": "date"}},
}


def _errors(schema: dict, data: dict) -> list:
    return list(build_validator(schema).iter_errors(data))


def test_rejects_bad_uri() -> None:
    assert _errors(URI_SCHEMA, {"u": "not a uri"}), "format:uri must reject a scheme-less string"


def test_accepts_good_uri() -> None:
    assert not _errors(URI_SCHEMA, {"u": "https://example.com/path"}), "absolute https URL must validate"


def test_rejects_bad_date_time() -> None:
    assert _errors(DATETIME_SCHEMA, {"d": "nonsense"}), "format:date-time must reject a non-timestamp"


def test_accepts_good_date_time() -> None:
    # both Z and explicit-offset RFC 3339 forms must pass
    assert not _errors(DATETIME_SCHEMA, {"d": "2026-06-03T00:00:00Z"})
    assert not _errors(DATETIME_SCHEMA, {"d": "2026-06-03T12:34:56+03:00"})


def test_rejects_bad_date() -> None:
    assert _errors(DATE_SCHEMA, {"d": "not-a-date"}), "format:date must reject a non-date"
    assert _errors(DATE_SCHEMA, {"d": "2026-06-03T00:00:00Z"}), "format:date must reject a full timestamp"


def test_accepts_good_date() -> None:
    assert not _errors(DATE_SCHEMA, {"d": "2026-06-03"}), "YYYY-MM-DD must validate"


def test_non_string_values_skip_format() -> None:
    # `format` applies only to strings; a null/number reaching a format-only
    # property (no `type`) must be skipped, not crash the custom checker.
    uri_only = {"$schema": URI_SCHEMA["$schema"], "type": "object", "properties": {"u": {"format": "uri"}}}
    date_only = {"$schema": DATE_SCHEMA["$schema"], "type": "object", "properties": {"d": {"format": "date"}}}
    assert not _errors(uri_only, {"u": None})
    assert not _errors(date_only, {"d": 123})
