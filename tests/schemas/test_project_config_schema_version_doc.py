"""Regression: project-config schema_version.description must contrast the
config CONTRACT version with the ENGINE RELEASE version (P2-05).

Codex audit P2-05: the const schema_version ("1.5") and the engine release
version (e.g. v1.9.4) version *different things* — the per-project data contract
vs the shipped engine/plugin — but the schema never said so, so readers
conflated the two axes. This guards the clarifying sentence so the distinction
cannot silently drift back out. Doc-only; no engine behavior depends on it.
"""

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads(
    (ROOT / "schemas" / "project-config.schema.json").read_text(encoding="utf-8")
)


def test_schema_version_description_contrasts_engine_release_version():
    desc = SCHEMA["properties"]["schema_version"]["description"].lower()
    assert "engine" in desc, (
        "schema_version.description must contrast the config contract version "
        "with the engine release version (P2-05)"
    )
