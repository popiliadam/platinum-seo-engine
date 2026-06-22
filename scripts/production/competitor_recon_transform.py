#!/usr/bin/env python3
"""
competitor_recon_transform.py — pure transform: raw DFS SERP (top-10 organic)
+ Claude-scraped competitor DOM → competitor coverage inventory (CCE batch B1).

Part of the Competitive Content Engine "Silahlanma Motoru" (arming engine).
Builds one record per scraped competitor page describing WHAT it covers — the
heading tree, answered questions, candidate entities, and its structural
ceiling (meaningful tables/lists, word count). ``build_brief`` consumes these
records to compute the coverage gap + structure ceiling the writer must beat.

MCP boundary (load-bearing):
    This script NEVER calls MCP. Claude (the skill) calls
    ``mcp__dataforseo__serp_organic_live_advanced`` (depth=10) for the organic
    URL list and ``mcp__ScraplingServer__stealthy_fetch`` for each page's DOM,
    writes the raw JSON / HTML to disk, and this transform ``json.load``s it
    via the CLI. Everything here is pure Python (argparse CLI + transform).
    Pattern reference: scripts/ingestion/dfs_pull.py.

HTML parsing:
    Uses the Python stdlib ``html.parser`` (zero dependency), mirroring
    scripts/validation/content_validator.py. BeautifulSoup is intentionally
    NOT used — it is not a declared/installed dependency, and stdlib keeps the
    transform hermetic and the test-suite zero-install.

Determinism:
    - ``tables`` counts only MEANINGFUL tables: ≥2 rows AND ≥2 columns.
    - ``lists`` counts only MEANINGFUL lists: a <ul>/<ol> with ≥3 <li>
      (each list attributed its own direct <li>, so a nested 2-li list does
      not inflate its parent).
    - ``questions`` = headings ending with "?" + FAQPage JSON-LD mainEntity
      names (deduplicated, case-insensitive).
    - ``entities`` = H2/H3 texts + <strong>/<b> texts (deduplicated,
      case-insensitive). Deterministic candidates only; SEMANTIC matching is
      batch B4's job (design §14 R1).
    - SERP order ranks the competitors; pages not present in the organic list
      keep their input order after ranked ones. A malformed/empty SERP never
      blocks the analysis — it only forfeits ordering.

Pure function discipline (mirrors dfs_pull.py / new_content_plan_transform.py):
    - No state mutation.
    - No file write side-effects when imported as a module (CLI only).
    - Idempotent: same input → byte-identical output (no timestamps).

CLI:
    python3 scripts/production/competitor_recon_transform.py \\
        --raw-serp inbox/cce/{date}-serp-{slug}.json \\
        --scraped-pages inbox/cce/{date}-scraped-{slug}.json \\
        [--market TR] \\
        [--output _state/cce/{run}/competitors.json]

    --scraped-pages is a JSON list of {"url": str, "html": str}.
    Stdout (or --output file): the competitors[] JSON list.

Refs: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md
(§4a competitor_recon), docs/superpowers/plans/2026-06-22-competitive-content-
engine.md (Brief Paketi schema — the B1↔B2↔B4 contract boundary).
"""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

# scripts/ is a namespace package; ensure repo root on sys.path so the absolute
# import of the DFS shape normaliser resolves when invoked as a script.
# ScriptDir = scripts/production → repo_root = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (NOT copy) — the DFS dual-shape normaliser is owned by
# scripts.ingestion.dfs_pull (D-003). Reusing it means any future shape fix is
# inherited automatically. Used here to tolerate REST-envelope OR flat-wrapper
# SERP payloads when extracting the organic URL ordering.
from scripts.ingestion.dfs_pull import _normalize_dfs_response  # noqa: E402

# IMPORT discipline (NOT copy) — the meaningful-structure thresholds are owned
# by scripts.production.structure_metrics (B4 single source of truth), so this
# arming engine (B1) and the gate engine (B2) measure tables/lists on the SAME
# ruler. See that module's header for the asymmetry it fixes.
from scripts.production.structure_metrics import (  # noqa: E402
    MIN_LIST_ITEMS,
    MIN_TABLE_COLS,
    MIN_TABLE_ROWS,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Exact output field order for each competitor record (the B1↔B2↔B4 contract).
COMPETITOR_COLUMNS: tuple[str, ...] = (
    "url",
    "h2_h3",
    "questions",
    "entities",
    "tables",
    "lists",
    "word_count",
)

_HEADING_TAGS: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
_ENTITY_HEADING_TAGS: frozenset[str] = frozenset({"h2", "h3"})
_STRONG_TAGS: frozenset[str] = frozenset({"strong", "b"})
_LIST_TAGS: frozenset[str] = frozenset({"ul", "ol"})
#: Tags whose character data is NOT human-visible (excluded from word_count and
#: never treated as heading/strong text). <script type="ld+json"> is captured
#: separately for FAQ extraction before being skipped.
_SKIP_TAGS: frozenset[str] = frozenset({"script", "style", "template", "noscript"})

# The meaningful-table (MIN_TABLE_ROWS × MIN_TABLE_COLS) and meaningful-list
# (MIN_LIST_ITEMS) thresholds are imported from structure_metrics above —
# single source of truth shared with the B2 gate engine (B4 alignment).


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------

def _collapse_ws(text: str) -> str:
    """Collapse all runs of whitespace to single spaces and strip the edges."""
    return " ".join(text.split())


def _dedup_ci(seq: Iterable[str]) -> list[str]:
    """Case-insensitive dedup preserving first-seen order + original casing."""
    out: list[str] = []
    seen: set[str] = set()
    for item in seq:
        s = item.strip()
        if not s:
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _norm_url(url: Any) -> str:
    """Lightweight URL key for SERP↔scrape matching (strip a trailing slash)."""
    if not isinstance(url, str):
        return ""
    return url.rstrip("/")


# ---------------------------------------------------------------------------
# FAQ JSON-LD extraction
# ---------------------------------------------------------------------------

def _extract_faq_questions(data: Any) -> list[str]:
    """Pull FAQPage mainEntity[].name question strings from a parsed JSON-LD
    blob. Tolerates a bare node, a list of nodes, or an ``@graph`` container,
    and @type given as a string or a list."""
    if isinstance(data, list):
        nodes = data
    elif isinstance(data, dict):
        graph = data.get("@graph")
        nodes = graph if isinstance(graph, list) else [data]
    else:
        return []

    out: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw_type = node.get("@type")
        types = raw_type if isinstance(raw_type, list) else [raw_type]
        if not any(isinstance(t, str) and t.casefold() == "faqpage" for t in types):
            continue
        main = node.get("mainEntity")
        if isinstance(main, dict):
            entities = [main]
        elif isinstance(main, list):
            entities = main
        else:
            entities = []
        for q in entities:
            if not isinstance(q, dict):
                continue
            name = q.get("name")
            if isinstance(name, str) and name.strip():
                out.append(_collapse_ws(name))
    return out


# ---------------------------------------------------------------------------
# Single-pass structural parser
# ---------------------------------------------------------------------------

class _ReconParser(HTMLParser):
    """One feed() pass collects every signal a competitor record needs:
    heading tree, <strong>/<b> texts, meaningful table/list counts, FAQ
    JSON-LD questions, and visible text for the word count. Robust to
    malformed HTML — unclosed tables/lists/headings are flushed on close()."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[str, str]] = []
        self.strong_texts: list[str] = []
        self.faq_questions: list[str] = []
        self.tables_meaningful = 0
        self.lists_meaningful = 0
        self._text_chunks: list[str] = []

        self._skip_depth = 0
        self._cur_heading_tag: str | None = None
        self._cur_heading_chunks: list[str] = []
        self._strong_depth = 0
        self._cur_strong_chunks: list[str] = []
        self._table_stack: list[dict[str, int]] = []
        self._list_stack: list[int] = []
        self._in_ldjson = False
        self._ldjson_chunks: list[str] = []

    # -- start tags --------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list) -> None:
        tag = tag.lower()
        if tag == "script":
            ad = {(k or "").lower(): (v or "") for k, v in attrs}
            if "ld+json" in ad.get("type", "").lower():
                self._in_ldjson = True
                self._ldjson_chunks = []
            self._skip_depth += 1
            return
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in _HEADING_TAGS:
            self._cur_heading_tag = tag
            self._cur_heading_chunks = []
        elif tag in _STRONG_TAGS:
            self._strong_depth += 1
            if self._strong_depth == 1:
                self._cur_strong_chunks = []
        elif tag == "table":
            self._table_stack.append({"rows": 0, "max_cols": 0, "cur_cols": 0})
        elif tag == "tr":
            if self._table_stack:
                top = self._table_stack[-1]
                top["rows"] += 1
                top["cur_cols"] = 0
        elif tag in ("td", "th"):
            self._count_cell()
        elif tag in _LIST_TAGS:
            self._list_stack.append(0)
        elif tag == "li":
            if self._list_stack:
                self._list_stack[-1] += 1

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        # Self-closing cells / list items still contribute to the structure.
        tag = tag.lower()
        if tag in ("td", "th"):
            self._count_cell()
        elif tag == "li" and self._list_stack:
            self._list_stack[-1] += 1

    def _count_cell(self) -> None:
        if not self._table_stack:
            return
        top = self._table_stack[-1]
        top["cur_cols"] += 1
        if top["cur_cols"] > top["max_cols"]:
            top["max_cols"] = top["cur_cols"]

    # -- end tags ----------------------------------------------------------

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "script":
            if self._in_ldjson:
                self._consume_ldjson()
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if tag in _SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if tag in _HEADING_TAGS:
            if self._cur_heading_tag is not None:
                self.headings.append(
                    (self._cur_heading_tag, _collapse_ws("".join(self._cur_heading_chunks)))
                )
                self._cur_heading_tag = None
                self._cur_heading_chunks = []
        elif tag in _STRONG_TAGS:
            if self._strong_depth > 0:
                self._strong_depth -= 1
                if self._strong_depth == 0:
                    text = _collapse_ws("".join(self._cur_strong_chunks))
                    if text:
                        self.strong_texts.append(text)
                    self._cur_strong_chunks = []
        elif tag == "table":
            if self._table_stack:
                self._finish_table(self._table_stack.pop())
        elif tag in _LIST_TAGS:
            if self._list_stack:
                self._finish_list(self._list_stack.pop())

    def _finish_table(self, table: dict[str, int]) -> None:
        if table["rows"] >= MIN_TABLE_ROWS and table["max_cols"] >= MIN_TABLE_COLS:
            self.tables_meaningful += 1

    def _finish_list(self, li_count: int) -> None:
        if li_count >= MIN_LIST_ITEMS:
            self.lists_meaningful += 1

    def _consume_ldjson(self) -> None:
        raw = "".join(self._ldjson_chunks).strip()
        self._in_ldjson = False
        self._ldjson_chunks = []
        if not raw:
            return
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return
        self.faq_questions.extend(_extract_faq_questions(data))

    # -- data --------------------------------------------------------------

    def handle_data(self, data: str) -> None:
        if self._in_ldjson:
            self._ldjson_chunks.append(data)
            return
        if self._skip_depth > 0:
            return
        self._text_chunks.append(data)
        if self._cur_heading_tag is not None:
            self._cur_heading_chunks.append(data)
        if self._strong_depth > 0:
            self._cur_strong_chunks.append(data)

    # -- close: flush any unclosed structures ------------------------------

    def close(self) -> None:
        super().close()
        if self._cur_heading_tag is not None:
            self.headings.append(
                (self._cur_heading_tag, _collapse_ws("".join(self._cur_heading_chunks)))
            )
            self._cur_heading_tag = None
        if self._strong_depth > 0:
            text = _collapse_ws("".join(self._cur_strong_chunks))
            if text:
                self.strong_texts.append(text)
            self._strong_depth = 0
        while self._table_stack:
            self._finish_table(self._table_stack.pop())
        while self._list_stack:
            self._finish_list(self._list_stack.pop())
        if self._in_ldjson:
            self._consume_ldjson()


# ---------------------------------------------------------------------------
# Per-page → competitor record
# ---------------------------------------------------------------------------

def _parse_page(url: str, html: str) -> dict:
    """Parse one competitor page's HTML into a schema-shaped record."""
    parser = _ReconParser()
    parser.feed(html or "")
    parser.close()

    h2_h3 = [
        text
        for (tag, text) in parser.headings
        if tag in _ENTITY_HEADING_TAGS and text
    ]
    question_candidates = [
        text for (_tag, text) in parser.headings if text.endswith("?")
    ]
    question_candidates.extend(parser.faq_questions)
    questions = _dedup_ci(question_candidates)
    entities = _dedup_ci(h2_h3 + parser.strong_texts)
    # Join with a space, not "" — element boundaries are word boundaries, so
    # minified markup like "</h2><p>" must not glue "Heading" onto the next
    # word. (A word split mid-token by an inline tag is the rarer case and
    # only nudges an approximate count.)
    word_count = len(" ".join(parser._text_chunks).split())

    return {
        "url": url,
        "h2_h3": h2_h3,
        "questions": questions,
        "entities": entities,
        "tables": parser.tables_meaningful,
        "lists": parser.lists_meaningful,
        "word_count": word_count,
    }


# ---------------------------------------------------------------------------
# SERP organic ordering
# ---------------------------------------------------------------------------

def _organic_urls(serp_json: Any) -> list[str]:
    """Extract the ordered organic result URLs from a SERP payload. Tolerant:
    an unrecognised / empty shape yields [] (ordering is forfeited, never an
    error — SERP is auxiliary to the HTML parse)."""
    if not isinstance(serp_json, dict):
        return []
    try:
        items = _normalize_dfs_response(serp_json)
    except (ValueError, TypeError):
        return []
    urls: list[str] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("type") == "organic":
            u = it.get("url")
            if isinstance(u, str) and u:
                urls.append(u)
    return urls


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def transform(serp_json: dict, scraped_pages: list[dict], *, market: str) -> list[dict]:
    """Build the competitor coverage inventory from raw SERP + scraped DOM.

    Args:
        serp_json: raw DFS ``serp_organic_live_advanced`` payload. Source of
            the top-10 organic URL ordering. Tolerates REST-envelope or
            flat-wrapper shape; an unparseable payload forfeits ordering only.
        scraped_pages: ``[{"url": str, "html": str}, ...]`` — the DOM Claude
            fetched with Scrapling for each organic competitor.
        market: project market code (e.g. "TR"). Required, non-empty.

    Returns:
        competitors[] — one record per scraped page, ordered by SERP rank
        (pages absent from the organic list keep their relative input order
        after ranked ones). Each record:
            {url, h2_h3, questions, entities, tables, lists, word_count}.

    Raises:
        ValueError: market is not a non-empty string, or scraped_pages is not
            a list.
    """
    if not isinstance(market, str) or not market.strip():
        raise ValueError("market must be a non-empty string")
    if not isinstance(scraped_pages, list):
        raise ValueError(
            f"scraped_pages must be a list, got {type(scraped_pages).__name__}"
        )

    organic = _organic_urls(serp_json)
    rank: dict[str, int] = {}
    for i, u in enumerate(organic):
        rank.setdefault(_norm_url(u), i)
    unranked = len(organic) + 1  # sorts after every ranked competitor

    indexed: list[tuple[int, int, dict]] = []
    for idx, page in enumerate(scraped_pages):
        if not isinstance(page, dict):
            continue
        url = page.get("url")
        url = url if isinstance(url, str) else ""
        html = page.get("html")
        html = html if isinstance(html, str) else ""
        record = _parse_page(url, html)
        position = rank.get(_norm_url(url), unranked)
        indexed.append((position, idx, record))

    indexed.sort(key=lambda t: (t[0], t[1]))
    return [record for _pos, _idx, record in indexed]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="competitor_recon_transform.py",
        description="Transform raw DFS SERP + scraped competitor DOM → "
                    "competitor coverage inventory (CCE arming engine, B1).",
    )
    p.add_argument("--raw-serp", required=True,
                   help="Path to raw serp_organic_live_advanced JSON.")
    p.add_argument("--scraped-pages", required=True,
                   help='Path to a JSON list of {"url": str, "html": str}.')
    p.add_argument("--market", default="TR",
                   help="Project market code (default: TR).")
    p.add_argument("--output", default=None,
                   help="If set, write competitors[] JSON here; else stdout.")
    return p.parse_args(list(argv))


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    serp_path = Path(args.raw_serp)
    if not serp_path.exists():
        print(f"raw SERP JSON not found: {serp_path}", file=sys.stderr)
        return 2
    pages_path = Path(args.scraped_pages)
    if not pages_path.exists():
        print(f"scraped-pages JSON not found: {pages_path}", file=sys.stderr)
        return 2

    serp_json = _read_json(serp_path)
    scraped_pages = _read_json(pages_path)
    if not isinstance(scraped_pages, list):
        print(
            f"--scraped-pages must be a JSON list, got {type(scraped_pages).__name__}",
            file=sys.stderr,
        )
        return 2

    try:
        competitors = transform(serp_json, scraped_pages, market=args.market)
    except ValueError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(competitors, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(json.dumps(
            {"competitors_path": str(out_path.resolve()), "count": len(competitors)},
            ensure_ascii=False,
        ))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "COMPETITOR_COLUMNS",
    "transform",
    "main",
)
