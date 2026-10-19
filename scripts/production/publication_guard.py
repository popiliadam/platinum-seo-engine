#!/usr/bin/env python3
"""publication_guard.py — scaled-content guard + human verification gate (S-02, S-03).

Two deterministic gates the content pipeline (new-blog, revise-content, any
programmatic page generator) must pass:

1. ``check_new_content`` (S-02, R-154) — before a NEW page is produced:
     * weekly cap: new pages published in the last 7 days (``content_new`` /
       ``pillar_launch`` work events) must stay under the cap;
     * near-duplicate: the draft's 5-word shingle overlap with any existing
       page must stay below ``SIMILARITY_MAX``;
     * user value: a non-empty statement of what the page adds for the user.
   Google's spam policy treats mass-produced, low-value pages as scaled content
   abuse (and since 2026-08-28 also attempts to manipulate generative-AI
   answers), so these stop the run instead of warning.

2. ``verification_status`` (S-03, R-155) — before a package is "ready": a person
   has checked the text, title, meta description, structured data and alt
   text (Google's gen-AI guidance, 2026-10-01). The record lives only in the
   engine (``verification.json`` next to the package); nothing visible is
   added to the page.

Pure functions (no IO) + a tiny CLI: ``verify <verification.json>`` exits 0
when ready, 1 otherwise.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

WEEKLY_PUBLISH_CAP_DEFAULT = 5
SIMILARITY_MAX = 0.5
SHINGLE_WORDS = 5
NEW_PAGE_EVENT_TYPES = frozenset({"content_new", "pillar_launch"})
REQUIRED_CHECKS = ("text", "title", "meta_description", "structured_data", "alt_text")

_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reasons: tuple[str, ...]


def _parse_ts(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def recent_publications(events, *, now: datetime, days: int = 7) -> int:
    """New pages (content_new / pillar_launch work events) in the last ``days``."""
    if now.tzinfo is None:  # naive == UTC; never compare naive with aware
        now = now.replace(tzinfo=timezone.utc)
    since = now - timedelta(days=days)
    count = 0
    for event in events:
        if not isinstance(event, dict) or event.get("event_kind") != "work":
            continue
        if event.get("event_type") not in NEW_PAGE_EVENT_TYPES:
            continue
        ts = _parse_ts(event.get("timestamp"))
        if ts is not None and since <= ts <= now:
            count += 1
    return count


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = [w.lower() for w in _WORD_RE.findall(text or "")]
    if len(words) < SHINGLE_WORDS:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def similarity(a: str, b: str) -> float:
    """Jaccard overlap of 5-word shingles (0 = unrelated, 1 = identical)."""
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def check_new_content(
    *,
    draft_text: str,
    user_value: str,
    existing: dict[str, str],
    publications_last_7d: int,
    cap: int = WEEKLY_PUBLISH_CAP_DEFAULT,
) -> GuardResult:
    """Whether a new page may be produced (S-02). Every failed check is a reason."""
    reasons: list[str] = []
    if publications_last_7d >= cap:
        reasons.append(
            f"weekly publishing cap reached ({publications_last_7d}/{cap} new pages "
            "in 7 days) — schedule for next week"
        )
    if not (user_value or "").strip():
        reasons.append("user value missing — state what this page adds for the user "
                       "that existing pages do not")
    worst_url, worst = None, 0.0
    for url, text in existing.items():
        score = similarity(draft_text, text)
        if score > worst:
            worst_url, worst = url, score
    if worst_url is not None and worst >= SIMILARITY_MAX:
        reasons.append(
            f"near-duplicate of {worst_url} (overlap {worst:.0%}) — improve that page "
            "instead of publishing another"
        )
    return GuardResult(ok=not reasons, reasons=tuple(reasons))


def blank_verification_record() -> dict:
    """The verification.json a package starts with (not ready until filled)."""
    return {"human_verification": {"verified_by": "", "verified_at": None, "checked": []}}


def verification_status(record: dict) -> tuple[bool, tuple[str, ...]]:
    """(ready, problems) for a package's human verification record (S-03)."""
    hv = record.get("human_verification") if isinstance(record, dict) else None
    if not isinstance(hv, dict):
        return False, ("human_verification record missing",)
    problems: list[str] = []
    if not str(hv.get("verified_by") or "").strip():
        problems.append("verified_by empty — who checked it")
    if _parse_ts(hv.get("verified_at")) is None:
        problems.append("verified_at missing — when it was checked")
    checked = set(hv.get("checked") or [])
    missing = [c for c in REQUIRED_CHECKS if c not in checked]
    if missing:
        problems.append("not checked yet: " + ", ".join(missing))
    return not problems, tuple(problems)


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "verify":
        print("usage: publication_guard.py verify <verification.json>", file=sys.stderr)
        return 2
    try:
        record = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"NOT READY: cannot read {argv[1]}: {exc}")
        return 1
    ready, problems = verification_status(record)
    print("READY" if ready else "NOT READY: " + "; ".join(problems))
    return 0 if ready else 1


__all__ = (
    "WEEKLY_PUBLISH_CAP_DEFAULT", "SIMILARITY_MAX", "REQUIRED_CHECKS", "GuardResult",
    "recent_publications", "similarity", "check_new_content",
    "blank_verification_record", "verification_status",
)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
