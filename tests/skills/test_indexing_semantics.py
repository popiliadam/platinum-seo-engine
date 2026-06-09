"""tests/skills/test_indexing_semantics.py — Audit#2 F4 indexing call semantics.

F4: the *wired* Google-side path in `indexing-ping` is `mcp__gsc__submit_sitemap`
— a **sitemap-level submission**, not a per-URL notification. Yet the skill docs
recorded the emitted provenance event as `indexing_ping.call_type=URL_UPDATED`
(indexing-ping Step 7 table; verify-indexing's upstream-emit note). `URL_UPDATED`
is the Google **per-URL Indexing API** notification type — claiming it on a
sitemap submission conflates two different mechanisms.

Fix (doc-only, no schema change): the sitemap path emits an `indexing_ping`
sub-object WITHOUT `call_type` (it is optional), described as a
**sitemap_submission**; the `call_type` enum values `URL_UPDATED` / `URL_DELETED`
stay RESERVED for the unbuilt, consent-gated per-URL Google Indexing API.

DURUR lock: the events.schema.json `indexing_ping.call_type` enum is asserted
UNCHANGED here — proof the fix needed NO schema edit (no D10 schema-count change).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEXING_PING = ROOT / "skills" / "publishing" / "indexing-ping" / "SKILL.md"
VERIFY_INDEXING = ROOT / "skills" / "publishing" / "verify-indexing" / "SKILL.md"
EVENTS_SCHEMA = ROOT / "schemas" / "events.schema.json"

# The misuse form: an emitted event that ASSIGNS call_type = URL_UPDATED on the
# wired sitemap path. Tolerates optional whitespace/backticks around the '='.
_CALL_TYPE_URL_UPDATED_RE = re.compile(r"call_type`?\s*=\s*`?URL_UPDATED")


def test_sitemap_path_never_emits_call_type_url_updated_indexing_ping() -> None:
    """The wired `mcp__gsc__submit_sitemap` path must NOT document emitting
    `call_type=URL_UPDATED` — that is a per-URL Indexing API semantic."""
    text = INDEXING_PING.read_text(encoding="utf-8")
    m = _CALL_TYPE_URL_UPDATED_RE.search(text)
    assert m is None, (
        "indexing-ping documents emitting call_type=URL_UPDATED on the wired "
        "sitemap path (mcp__gsc__submit_sitemap is a sitemap submission, NOT a "
        f"per-URL URL_UPDATED notification): ...{text[max(0, m.start()-40):m.end()+40]!r}"
        if m else ""
    )


def test_sitemap_path_never_emits_call_type_url_updated_verify_indexing() -> None:
    """verify-indexing's note about what indexing-ping emits must match the
    sitemap-submission semantics (no call_type=URL_UPDATED claim)."""
    text = VERIFY_INDEXING.read_text(encoding="utf-8")
    assert _CALL_TYPE_URL_UPDATED_RE.search(text) is None, (
        "verify-indexing claims the upstream indexing-ping emits "
        "call_type=URL_UPDATED — but the wired path is a sitemap submission"
    )


def test_indexing_ping_documents_sitemap_submission_semantics() -> None:
    """The wired path is documented with sitemap-submission semantics and the
    per-URL `URL_UPDATED` path is explicitly RESERVED (not the emitted value)."""
    text = INDEXING_PING.read_text(encoding="utf-8")
    assert "sitemap_submission" in text, (
        "indexing-ping must label the wired path's emitted event as a "
        "sitemap_submission (the honest semantics for mcp__gsc__submit_sitemap)"
    )
    # The reservation of URL_UPDATED for the unbuilt per-URL API must survive.
    assert "URL_UPDATED" in text and re.search(
        r"URL_UPDATED.{0,80}(reserv|not yet wired|per-URL)|"
        r"(reserv|per-URL|unbuilt).{0,80}URL_UPDATED",
        text, re.IGNORECASE | re.DOTALL,
    ), "indexing-ping must reserve URL_UPDATED for the unbuilt per-URL Indexing API"


def test_verify_indexing_documents_sitemap_submission_semantics() -> None:
    text = VERIFY_INDEXING.read_text(encoding="utf-8")
    assert "sitemap_submission" in text, (
        "verify-indexing must describe the upstream emit as a sitemap_submission"
    )


def test_call_type_enum_unchanged_no_schema_edit() -> None:
    """DURUR lock: the fix is doc-only. events.schema.json indexing_ping.call_type
    MUST remain the closed 2-value enum reserved for the per-URL Indexing API —
    no enum value added (e.g. no `sitemap_submission` shoehorned into call_type),
    so no schema-count / D10 surface change."""
    schema = json.loads(EVENTS_SCHEMA.read_text(encoding="utf-8"))
    call_type = schema["properties"]["indexing_ping"]["properties"]["call_type"]
    assert call_type["enum"] == ["URL_UPDATED", "URL_DELETED"], (
        "indexing_ping.call_type enum must stay reserved for the per-URL Indexing "
        f"API (URL_UPDATED/URL_DELETED); got {call_type.get('enum')!r}"
    )
