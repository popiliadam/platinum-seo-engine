"""codex-audit finding 4: project-config dataforseo.language_code was an
unconstrained string, so numeric locale junk ("1001", "1031") passed schema
validation and could be forwarded to DataForSEO as an invalid language token
(triggering the US/en fallback for Turkish-market projects — Q-DFS-MCP-01).
Constrain it to an ISO-like language code and reject numeric/garbage values.

The pattern intentionally allows 2-3 letter primary subtags plus an optional
script/region subtag (e.g. "en", "tr", "es", "en-us", "zh-Hant") so it does not
over-constrain legitimate DataForSEO language codes, while rejecting digits and
uppercase-primary garbage.
"""
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
DFS_SUBSCHEMA = json.loads(
    (ROOT / "schemas" / "project-config.schema.json").read_text("utf-8")
)["properties"]["dataforseo"]


def _validate(language_code):
    """Validate the dataforseo sub-schema in isolation for a given language_code."""
    jsonschema.Draft7Validator(DFS_SUBSCHEMA).validate(
        {"location_code": 2792, "language_code": language_code}
    )


@pytest.mark.parametrize("good", ["tr", "en", "es", "en-us", "zh-Hant"])
def test_language_code_accepts_iso(good):
    _validate(good)


@pytest.mark.parametrize("bad", ["1001", "1031", "2792", "TR", "turkish", ""])
def test_language_code_rejects_non_iso(bad):
    with pytest.raises(jsonschema.ValidationError):
        _validate(bad)
