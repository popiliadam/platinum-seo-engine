#!/usr/bin/env python3
"""
build_brief.py — pure transform: competitor inventory + keyword/AIO intel +
our existing coverage → the Brief Paketi (CCE batch B1, the contract boundary).

The Brief Paketi is the single source of truth the writer (B4 orchestrator) and
the quality gates (B2) consume. This module computes the two derived signals:

  - gap         = competitor coverage union − our existing coverage. What the
                  writer MUST cover to beat the field (headings / questions /
                  entities). Deterministic, case-insensitive subtraction; the
                  SEMANTIC "do these mean the same thing?" pass is B4's job.
  - structure_ceiling = per-dimension max over competitors (tables, lists,
                  heading count, best word count). The writer must clear it +1
                  (design §9 yapı matematiği / §6 gate 2).

When ``our_existing`` is None, nothing is subtracted — the entire competitor
coverage is the gap (greenfield content).

MCP boundary: pure Python; no MCP, no I/O on import (CLI only). Idempotent —
the ONLY run-to-run variable is ``generated_at``, which is INJECTED (never
produced from the clock), so same input + same arg → byte-identical output.

CLI:
    python3 scripts/production/build_brief.py \\
        --competitors _state/cce/{run}/competitors.json \\
        --keyword-aio _state/cce/{run}/keyword_aio.json \\
        [--our-existing _state/cce/{run}/our_existing.json] \\
        --topic _state/cce/{run}/topic.json \\
        [--generated-at 2026-06-22T10:00:00+00:00] \\
        [--output _state/cce/{run}/brief.json]

    Stdout (or --output file): the full Brief Paketi JSON.

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§7 Brief Paketi schema), docs/superpowers/plans/2026-06-22-competitive-content-
engine.md (Brief Paketi schema — B1↔B2↔B4 contract). Produced by
competitor_recon_transform + keyword_aio_intel_transform (sibling B1 modules).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

#: Brief Paketi schema version (the B1↔B2↔B4 contract version).
SCHEMA_VERSION = "1.0"

#: Allowed content types (Brief topic.content_type enum).
_CONTENT_TYPE_ENUM: frozenset[str] = frozenset({
    "guide", "comparison", "listicle", "research", "tutorial", "review",
})

#: Required topic keys.
_TOPIC_KEYS: tuple[str, ...] = ("primary_keyword", "content_type", "locale", "market")

#: Exact competitor record field order (mirrors competitor_recon_transform).
_COMPETITOR_KEYS: tuple[str, ...] = (
    "url", "h2_h3", "questions", "entities", "tables", "lists", "word_count",
)

_ABSENT_AIO: dict[str, Any] = {"present": False, "answer_points": [], "cited_sources": []}


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _as_int(x: Any) -> int:
    """Coerce to int; bools and non-numerics become 0."""
    if isinstance(x, bool):
        return 0
    if isinstance(x, int):
        return x
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _str_list(x: Any) -> list[str]:
    """Keep only the non-empty trimmed strings of a list; else []."""
    if not isinstance(x, list):
        return []
    return [s.strip() for s in x if isinstance(s, str) and s.strip()]


def _union_ci(competitor_lists: Iterable[list[str]]) -> list[str]:
    """Union of competitor coverage lists, case-insensitive dedup, first-seen
    order across competitors preserved."""
    out: list[str] = []
    seen: set[str] = set()
    for lst in competitor_lists:
        for s in lst:
            key = s.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(s)
    return out


def _subtract_ci(union: list[str], existing: list[str]) -> list[str]:
    """union − existing, matched case-insensitively, preserving union order."""
    ex = {s.casefold() for s in existing}
    return [s for s in union if s.casefold() not in ex]


def _project_competitor(c: Any) -> dict:
    """Project an arbitrary competitor dict to the exact 7-field schema with
    type-safe defaults (defensive — guarantees gap/ceiling math is sound)."""
    c = c if isinstance(c, dict) else {}
    url = c.get("url")
    return {
        "url": url if isinstance(url, str) else "",
        "h2_h3": _str_list(c.get("h2_h3")),
        "questions": _str_list(c.get("questions")),
        "entities": _str_list(c.get("entities")),
        "tables": _as_int(c.get("tables")),
        "lists": _as_int(c.get("lists")),
        "word_count": _as_int(c.get("word_count")),
    }


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def _build_topic(topic: Any) -> dict:
    if not isinstance(topic, dict):
        raise ValueError(f"topic must be a dict, got {type(topic).__name__}")
    missing = [k for k in _TOPIC_KEYS if k not in topic]
    if missing:
        raise ValueError(f"topic missing required keys: {missing}")
    content_type = topic.get("content_type")
    if content_type not in _CONTENT_TYPE_ENUM:
        raise ValueError(
            f"topic.content_type must be one of {sorted(_CONTENT_TYPE_ENUM)}, "
            f"got {content_type!r}"
        )
    return {k: topic[k] for k in _TOPIC_KEYS}


def _build_gap(competitors: list[dict], our_existing: dict | None) -> dict:
    headings = _union_ci(c["h2_h3"] for c in competitors)
    questions = _union_ci(c["questions"] for c in competitors)
    entities = _union_ci(c["entities"] for c in competitors)

    if our_existing is None:
        our_h, our_q, our_e = [], [], []
    else:
        if not isinstance(our_existing, dict):
            raise ValueError(
                f"our_existing must be a dict or None, got {type(our_existing).__name__}"
            )
        our_h = _str_list(our_existing.get("headings"))
        our_q = _str_list(our_existing.get("questions"))
        our_e = _str_list(our_existing.get("entities"))

    return {
        "must_cover_headings": _subtract_ci(headings, our_h),
        "must_answer_questions": _subtract_ci(questions, our_q),
        "must_mention_entities": _subtract_ci(entities, our_e),
    }


def _build_structure_ceiling(competitors: list[dict]) -> dict:
    return {
        "tables": max((c["tables"] for c in competitors), default=0),
        "lists": max((c["lists"] for c in competitors), default=0),
        # The competitor record flattens h2+h3 into one list, so the heading
        # ceiling is the max heading count (semantic h2/h3 split is deferred to B4).
        "h2": max((len(c["h2_h3"]) for c in competitors), default=0),
        "best_competitor_word_count": max((c["word_count"] for c in competitors), default=0),
    }


def build(
    competitors: list[dict],
    keyword_aio: dict,
    our_existing: dict | None,
    *,
    topic: dict,
    generated_at: str | None = None,
) -> dict:
    """Assemble the Brief Paketi from the B1 transform outputs.

    Args:
        competitors: competitor_recon_transform.transform output (list of
            {url, h2_h3, questions, entities, tables, lists, word_count}).
        keyword_aio: keyword_aio_intel_transform.transform output
            ({keyword_set, aio}).
        our_existing: {"headings": [str], "questions": [str], "entities": [str]}
            describing our current/planned content, or None (greenfield → all
            competitor coverage is gap).
        topic: {primary_keyword, content_type, locale, market}. content_type
            must be in the Brief enum.
        generated_at: ISO-8601 timestamp string, or None → the field is null.
            INJECTED (never produced from the clock) so the transform stays
            idempotent: same input + same arg → byte-identical output.

    Returns:
        The full Brief Paketi dict (schema_version="1.0"), keys in schema order.

    Raises:
        ValueError: topic invalid (missing key or bad content_type),
            keyword_aio / our_existing wrong type, or generated_at not a string.
    """
    if generated_at is not None and not isinstance(generated_at, str):
        raise ValueError(
            f"generated_at must be a string or None, got {type(generated_at).__name__}"
        )
    if not isinstance(keyword_aio, dict):
        raise ValueError(
            f"keyword_aio must be a dict, got {type(keyword_aio).__name__}"
        )
    if not isinstance(competitors, list):
        raise ValueError(
            f"competitors must be a list, got {type(competitors).__name__}"
        )

    topic_block = _build_topic(topic)
    projected = [_project_competitor(c) for c in competitors]

    keyword_set = keyword_aio.get("keyword_set")
    keyword_set = keyword_set if isinstance(keyword_set, list) else []
    aio = keyword_aio.get("aio")
    aio = aio if isinstance(aio, dict) else dict(_ABSENT_AIO)

    return {
        "schema_version": SCHEMA_VERSION,
        "topic": topic_block,
        "keyword_set": keyword_set,
        "aio": aio,
        "competitors": projected,
        "gap": _build_gap(projected, our_existing),
        "structure_ceiling": _build_structure_ceiling(projected),
        # GSC signal is supplied by the skill layer (master.xlsx / live MCP),
        # not this transform — emitted with empty defaults so the schema is
        # complete. (Open question for the manager: wire a gsc input if B4
        # needs it threaded through build().)
        "gsc": {"real_queries": [], "current_position": None},
        "generated_at": generated_at,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="build_brief.py",
        description="Assemble the Brief Paketi from competitor inventory + "
                    "keyword/AIO intel + our existing coverage (CCE arming engine, B1).",
    )
    p.add_argument("--competitors", required=True,
                   help="Path to competitors[] JSON (competitor_recon output).")
    p.add_argument("--keyword-aio", required=True,
                   help="Path to {keyword_set, aio} JSON (keyword_aio_intel output).")
    p.add_argument("--our-existing", default=None,
                   help="Optional path to {headings, questions, entities} JSON.")
    p.add_argument("--topic", required=True,
                   help="Path to topic JSON {primary_keyword, content_type, locale, market}.")
    p.add_argument("--generated-at", default=None,
                   help="ISO-8601 timestamp for generated_at (default: null). "
                        "INJECTED for idempotency — never read from the clock.")
    p.add_argument("--output", default=None,
                   help="If set, write the Brief Paketi JSON here; else stdout.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    for label, path_str in (("competitors", args.competitors),
                            ("keyword-aio", args.keyword_aio),
                            ("topic", args.topic)):
        if not Path(path_str).exists():
            print(f"{label} JSON not found: {path_str}", file=sys.stderr)
            return 2

    competitors = _read_json(Path(args.competitors))
    keyword_aio = _read_json(Path(args.keyword_aio))
    topic = _read_json(Path(args.topic))
    our_existing = None
    if args.our_existing and Path(args.our_existing).exists():
        our_existing = _read_json(Path(args.our_existing))

    try:
        brief = build(
            competitors, keyword_aio, our_existing,
            topic=topic, generated_at=args.generated_at,
        )
    except ValueError as exc:
        print(f"build_brief failed: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(brief, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps({"brief_path": str(out_path.resolve())}, ensure_ascii=False))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "SCHEMA_VERSION",
    "build",
    "main",
)
