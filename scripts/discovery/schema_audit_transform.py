#!/usr/bin/env python3
"""
schema_audit_transform.py — pure transform: Screaming Frog (SF) structured
data CSV/JSON (+ optional DFS on_page_content_parsing) → schema-shaped
rows for master.xlsx#schema.

Reads Screaming Frog `structured_data_all` style export (already parsed
into a list-of-dict envelope by the upstream sf-import skill OR a CSV
loaded by the helper here), normalizes URLs per D-03, parses the
JSON-LD / microdata blobs surfaced by SF per URL, identifies schema_type
+ required-prop coverage, and emits 5-column rows shaped per the schema
sheet of master-excel.schema.json (schema_type, status, location, scope,
remaining_work).

Optional cross-validation layer: when a DFS on_page_content_parsing
payload is provided, we extract its `schema` block per URL and confirm
the SF-detected types are also visible live (DFS `schema_org` field).
The cross-check only enriches `remaining_work` notes — it never silently
flips a status. Budget pre-flight (`scripts.budget.check_budget`) is
mandatory whenever the optional DFS branch is invoked; on FAIL we raise
BudgetExceededError, NOT silently fall back to SF-only.

Pure function discipline:
  - No state mutation.
  - No file write side-effects when imported as a module (CLI only).
  - Idempotent: same inputs → byte-identical output.
  - Does NOT import scripts.excel.transaction (orchestration layer only).

Aggregation: when multiple URLs share the same (schema_type, gap)
signature site-wide (≥3 URLs and the gap is identical), the rows are
collapsed into a single aggregated row whose `scope` is "site-wide" and
whose `location` summarises the pattern (e.g. "12 URLs"). Per-URL rows
are emitted otherwise (`scope` = "page-level").

Errors raised:
  - SchemaAuditError: malformed input (not a dict / not a list).
  - JsonLdParseError: JSON-LD blob is malformed AND strict mode is on.
    Default mode silently DROPS the malformed blob with no row emission;
    the skill SKILL.md DURUR #3 documents which mode is canonical.
  - RowSchemaError: emitted row drifts from the locked 5-col tuple.
  - BudgetExceededError: subprocess `check_budget.py --check` exited 1.

CLI:
  python3 scripts/discovery/schema_audit_transform.py \
      --raw-sf inbox/sf/{date}-schema-{slug}.json \
      [--raw-dfs inbox/dfs/{date}-content_parsing-schema-{slug}.json] \
      [--strict-parse] \
      [--output-dir _state/transform/{run_id}/]

Refs: schemas/master-excel.schema.json (schema sheet 5 required_columns
+ statusEnum), schemas/cross-sheet-invariants.json (D-03 URL canonical),
schemas/events.schema.json (source.kind=sf_csv | dataforseo_mcp,
target_excel_sheet=schema), spec §16.5 (raw inbox + transform),
§16.8 (budget pre-flight).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
# scripts is a namespace package; ensure repo root on sys.path so absolute
# imports resolve when invoked as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.util.url_normalize import (  # noqa: E402  (sys.path mutation)
    URLNormalizeError as _URLNormalizeError,
    normalize_url as _canonical_normalize_url,
)

# ---------------------------------------------------------------------------
# Constants — schema-aligned column names
# (master-excel.schema.json#schema required_columns; 5 cols, NOT 6)
# ---------------------------------------------------------------------------

SCHEMA_AUDIT_COLUMNS = (
    "schema_type",
    "status",
    "location",
    "scope",
    "remaining_work",
)

# statusEnum allowed values (master-excel.schema.json#/definitions/statusEnum).
_STATUS_ENUM = frozenset({
    "TODO", "ONGOING", "EXISTS", "DONE",
    "BLOCKED", "DEFERRED", "CANCELED",
})

# DFS on_page_content_parsing per-URL credit estimate (paid; same as
# on_page_audit transform for parity — single round-trip per URL).
CREDITS_PER_URL_CONTENT_PARSING = 3.0

# Aggregation threshold — same (schema_type, gap) across ≥N URLs collapses
# into a single site-wide row.
_AGGREGATION_MIN_URLS = 3

# Required-property minimums per schema_type. Missing any → status=TODO.
# Conservative subset; extend via ADR rather than silently drift.
_REQUIRED_PROPS: dict[str, frozenset[str]] = {
    "Article":         frozenset({"headline", "author", "datePublished"}),
    "NewsArticle":     frozenset({"headline", "author", "datePublished"}),
    "BlogPosting":     frozenset({"headline", "author", "datePublished"}),
    "Product":         frozenset({"name", "image", "offers"}),
    "Organization":    frozenset({"name", "url"}),
    "LocalBusiness":   frozenset({"name", "address", "telephone"}),
    "BreadcrumbList":  frozenset({"itemListElement"}),
    "FAQPage":         frozenset({"mainEntity"}),
    "Recipe":          frozenset({"name", "recipeIngredient", "recipeInstructions"}),
    "Event":           frozenset({"name", "startDate", "location"}),
    "Person":          frozenset({"name"}),
    "WebSite":         frozenset({"name", "url"}),
    "WebPage":         frozenset({"name"}),
}

# Optional-but-recommended props — presence-as-recommendation only.
_RECOMMENDED_PROPS: dict[str, frozenset[str]] = {
    "Product":         frozenset({"aggregateRating", "review", "brand"}),
    "Article":         frozenset({"image", "publisher"}),
    "BreadcrumbList":  frozenset({"itemListElement.position"}),
}


# ---------------------------------------------------------------------------
# Exceptions (DURUR-style explicit)
# ---------------------------------------------------------------------------

class SchemaAuditError(ValueError):
    """Base class for explicit DURUR conditions in schema_audit transform."""


class JsonLdParseError(SchemaAuditError):
    """A JSON-LD blob is malformed; strict mode raises, default drops."""


class RowSchemaError(SchemaAuditError):
    """A produced row drifts from the master-excel schema sheet contract."""


class BudgetExceededError(SchemaAuditError):
    """Budget pre-flight (`check_budget.py --check`) exited non-zero."""


# ---------------------------------------------------------------------------
# URL normalization (D-03 invariant — same rule as cannibalization_transform)
# ---------------------------------------------------------------------------

def _normalize_url(url: Any) -> str:
    """Tolerant D-03 URL normalize via :mod:`scripts.util.url_normalize`.

    Returns the empty string for any un-parseable input rather than
    raising — schema audit drops the row instead of aborting the whole
    batch when one URL in a SF export is malformed. Cross-sheet joins
    (cannibalization ↔ schema) remain bit-stable because the canonical
    helper is the same one cannibalization adapts to.

    K-01 dedup (v1.5-Phase-1 Tier 1).
    """
    try:
        return _canonical_normalize_url(url)
    except _URLNormalizeError:
        return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _coerce_type(t: Any) -> str:
    """Extract the schema.org @type as a string. Lists → first entry."""
    if isinstance(t, list):
        for entry in t:
            s = _safe_str(entry)
            if s:
                return s
        return ""
    return _safe_str(t)


@dataclass(frozen=True)
class _SchemaInstance:
    """One parsed JSON-LD / microdata schema markup instance per URL."""
    url: str
    schema_type: str
    props: frozenset
    raw_type_value: str = ""

    @property
    def is_conflicting(self) -> bool:
        """Multi-type with mixed top-level types is treated as conflict."""
        if not self.raw_type_value:
            return False
        # If the raw @type was a list with ≥2 distinct non-empty entries,
        # mark as conflicting. We compare against the chosen schema_type.
        if "|" in self.raw_type_value:
            parts = [p.strip() for p in self.raw_type_value.split("|") if p.strip()]
            return len(set(parts)) >= 2
        return False


def _flatten_jsonld(node: Any) -> list[dict]:
    """Flatten a JSON-LD doc into the list of typed nodes.

    Handles the three common shapes:
      - bare object with @type
      - {"@graph": [ ... ]}
      - top-level list of typed objects
    Untyped nodes are skipped.
    """
    out: list[dict] = []
    if isinstance(node, dict):
        graph = node.get("@graph")
        if isinstance(graph, list):
            for child in graph:
                out.extend(_flatten_jsonld(child))
        if "@type" in node:
            out.append(node)
    elif isinstance(node, list):
        for child in node:
            out.extend(_flatten_jsonld(child))
    return out


def _parse_jsonld_blob(
    blob: str, *, strict: bool,
) -> tuple[list[dict], int]:
    """Parse a single JSON-LD string into (nodes, parse_error_count).

    Strict mode: malformed JSON raises JsonLdParseError. Default mode:
    malformed blobs return ([], 1) so the caller can surface the
    drift count in `meta.parse_errors` (the upstream SF row is dropped
    but its existence is tracked).
    """
    if not isinstance(blob, str) or not blob.strip():
        return [], 0
    try:
        doc = json.loads(blob)
    except (TypeError, ValueError) as exc:
        if strict:
            raise JsonLdParseError(
                f"JSON-LD parse error: {exc} :: {blob[:120]!r}"
            ) from exc
        return [], 1
    return _flatten_jsonld(doc), 0


def _extract_schema_instances(
    sf_row: dict, *, strict: bool,
) -> tuple[list[_SchemaInstance], int]:
    """Pull every schema markup instance out of a single SF structured-data row.

    SF `structured_data_all.csv` exports per-URL columns like:
      Address, Type, Format, Errors, Warnings, JSON-LD Blob, Microdata Items, ...
    The exact column layout differs across SF versions; we accept several
    common keys defensively. Either:
      - `json_ld` / `JSON-LD` / `jsonld_blob` carries one or more JSON
        documents concatenated — we split on the document boundary by
        attempting `json.loads` per line and accumulate.
      - `schema_types` / `Type` carries a comma- or pipe-separated list
        of schema.org types (no props), used as a presence-only fallback.
    """
    url_raw = (
        sf_row.get("address")
        or sf_row.get("Address")
        or sf_row.get("url")
        or sf_row.get("URL")
        or ""
    )
    url_n = _normalize_url(_safe_str(url_raw))
    if not url_n:
        return [], 0

    out: list[_SchemaInstance] = []
    parse_err = 0

    # --- Path A: full JSON-LD blob ------------------------------------------------
    blob = (
        sf_row.get("json_ld")
        or sf_row.get("JSON-LD")
        or sf_row.get("jsonld_blob")
        or sf_row.get("JSON-LD Blob")
        or sf_row.get("structured_data")
        or ""
    )
    blob_str = _safe_str(blob)
    if blob_str:
        nodes, errs = _parse_jsonld_blob(blob_str, strict=strict)
        parse_err += errs
        for node in nodes:
            t_raw = node.get("@type")
            schema_type = _coerce_type(t_raw)
            if not schema_type:
                continue
            props = frozenset(
                k for k in node.keys()
                if isinstance(k, str) and not k.startswith("@")
            )
            # Encode multi-type info into raw_type_value for conflict detection.
            if isinstance(t_raw, list) and len(t_raw) >= 2:
                raw_type_value = "|".join(_safe_str(x) for x in t_raw if _safe_str(x))
            else:
                raw_type_value = ""
            out.append(_SchemaInstance(
                url=url_n,
                schema_type=schema_type,
                props=props,
                raw_type_value=raw_type_value,
            ))

    # --- Path B: presence-only types list (fallback when no blob) ---------
    if not out:
        types_field = (
            sf_row.get("schema_types")
            or sf_row.get("Type")
            or sf_row.get("types")
            or ""
        )
        types_str = _safe_str(types_field)
        if types_str:
            for token in _split_types(types_str):
                if not token:
                    continue
                out.append(_SchemaInstance(
                    url=url_n, schema_type=token,
                    props=frozenset(), raw_type_value="",
                ))

    return out, parse_err


def _split_types(s: str) -> list[str]:
    """Split a 'Type' column value on common SF separators."""
    for sep in ("|", ","):
        if sep in s:
            return [t.strip() for t in s.split(sep) if t.strip()]
    return [s.strip()]


# ---------------------------------------------------------------------------
# Status / remaining_work derivation
# ---------------------------------------------------------------------------

def _derive_status_and_work(
    instance: _SchemaInstance,
    *,
    dfs_confirmed: bool | None,
    default_status: str = "TODO",
) -> tuple[str, str]:
    """Map a parsed schema instance + DFS confirmation flag → (status, remaining_work).

    - Conflicting top-level @type → BLOCKED.
    - Required props missing → TODO; remaining_work names the missing props.
    - Required all present, recommended missing → EXISTS; remaining_work names
      the recommended gap.
    - Required all present, recommended all present (or none defined) → DONE.

    DFS confirmation only enriches `remaining_work` (e.g. "(DFS confirmed)" /
    "(DFS missing live)"); it never silently downgrades a TODO to DONE.
    """
    if instance.is_conflicting:
        note = (
            f"resolve conflicting @type ({instance.raw_type_value}); "
            "schema.org allows multi-type but mixed top-level types break rich results"
        )
        return "BLOCKED", _decorate_dfs(note, dfs_confirmed)

    required = _REQUIRED_PROPS.get(instance.schema_type, frozenset())
    missing_required = sorted(required - instance.props)
    if required and not instance.props:
        # Presence-only fallback (no blob) — we know the type exists but
        # cannot prove props, so no per-row gap analysis is possible. Seed
        # the status from default_status (the SKILL.md input; frontmatter
        # default "TODO", operator-overridable) rather than hardcoding it.
        note = (
            f"verify {instance.schema_type} required props "
            f"({', '.join(sorted(required))}) — SF reported type only, no JSON-LD blob"
        )
        return default_status, _decorate_dfs(note, dfs_confirmed)

    if missing_required:
        note = (
            f"add missing required prop(s) to {instance.schema_type}: "
            f"{', '.join(missing_required)}"
        )
        return "TODO", _decorate_dfs(note, dfs_confirmed)

    recommended = _RECOMMENDED_PROPS.get(instance.schema_type, frozenset())
    missing_recommended = sorted(recommended - instance.props)
    if missing_recommended:
        note = (
            f"recommend adding {', '.join(missing_recommended)} to "
            f"{instance.schema_type} for richer SERP eligibility"
        )
        return "EXISTS", _decorate_dfs(note, dfs_confirmed)

    return "DONE", _decorate_dfs("schema complete", dfs_confirmed)


def _decorate_dfs(note: str, dfs_confirmed: bool | None) -> str:
    """Append a DFS cross-validation note when available."""
    if dfs_confirmed is True:
        return f"{note} (DFS confirmed live)"
    if dfs_confirmed is False:
        return f"{note} (DFS did not echo live — verify rendering)"
    return note


# ---------------------------------------------------------------------------
# DFS cross-validation
# ---------------------------------------------------------------------------

def _index_dfs_schemas(dfs_payload: dict | None) -> dict[str, frozenset[str]]:
    """Build {normalized_url: frozenset(schema_type, ...)} from a DFS payload.

    DFS on_page_content_parsing items expose schema_org markup either as a
    list of dicts with `type` keys or as a `schema_org` block. We accept
    several shapes defensively (mirrors on_page_audit_transform tolerance).
    """
    if dfs_payload is None:
        return {}
    if not isinstance(dfs_payload, dict):
        return {}

    items: list[dict] = []
    tasks = dfs_payload.get("tasks")
    if isinstance(tasks, list):
        for t in tasks:
            if isinstance(t, dict):
                result = t.get("result")
                if isinstance(result, list):
                    for r in result:
                        if isinstance(r, dict):
                            inner = r.get("items") or [r]
                            if isinstance(inner, list):
                                items.extend(x for x in inner if isinstance(x, dict))
    if not items:
        flat = dfs_payload.get("items") or dfs_payload.get("data") or []
        if isinstance(flat, list):
            items = [x for x in flat if isinstance(x, dict)]

    out: dict[str, frozenset[str]] = {}
    for it in items:
        url = _normalize_url(_safe_str(
            it.get("url") or it.get("page_url") or it.get("target")
        ))
        if not url:
            continue
        types: set[str] = set()
        for key in ("schema_org", "structured_data", "schema"):
            block = it.get(key)
            if isinstance(block, list):
                for entry in block:
                    if isinstance(entry, dict):
                        t = _coerce_type(entry.get("@type") or entry.get("type"))
                        if t:
                            types.add(t)
            elif isinstance(block, dict):
                t = _coerce_type(block.get("@type") or block.get("type"))
                if t:
                    types.add(t)
        if types:
            out[url] = frozenset(types)
    return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class _Candidate:
    """One pre-aggregation row candidate."""
    schema_type: str
    status: str
    location: str
    scope: str
    remaining_work: str
    _agg_key: tuple = field(default=())


def _aggregate(candidates: list[_Candidate]) -> list[dict]:
    """Collapse candidates that share the same (schema_type, status,
    remaining_work) signature across ≥_AGGREGATION_MIN_URLS distinct URLs
    into a single site-wide row. Per-URL rows are emitted otherwise.
    """
    by_key: dict[tuple, list[_Candidate]] = {}
    for c in candidates:
        key = (c.schema_type, c.status, c.remaining_work)
        by_key.setdefault(key, []).append(c)

    out_rows: list[dict] = []
    for key, group in by_key.items():
        urls = sorted({c.location for c in group})
        if len(urls) >= _AGGREGATION_MIN_URLS:
            row = {
                "schema_type": key[0],
                "status": key[1],
                "location": f"{len(urls)} URLs",
                "scope": "site-wide",
                "remaining_work": key[2],
            }
            _validate_row_shape(row)
            out_rows.append(row)
        else:
            for c in group:
                row = {
                    "schema_type": c.schema_type,
                    "status": c.status,
                    "location": c.location,
                    "scope": c.scope,
                    "remaining_work": c.remaining_work,
                }
                _validate_row_shape(row)
                out_rows.append(row)

    # Deterministic sort: status priority (BLOCKED > TODO > EXISTS > DONE), then
    # schema_type, then location.
    status_priority = {
        "BLOCKED": 0, "TODO": 1, "ONGOING": 2, "EXISTS": 3,
        "DONE": 4, "DEFERRED": 5, "CANCELED": 6,
    }
    out_rows.sort(key=lambda r: (
        status_priority.get(r["status"], 99),
        r["schema_type"],
        r["location"],
    ))
    return out_rows


def _validate_row_shape(row: dict) -> None:
    """Self-check: row keys must equal the locked 5-col tuple, status in enum."""
    if tuple(row.keys()) != SCHEMA_AUDIT_COLUMNS:
        raise RowSchemaError(
            f"row column drift: got {tuple(row.keys())}, "
            f"expected {SCHEMA_AUDIT_COLUMNS}"
        )
    if row["status"] not in _STATUS_ENUM:
        raise RowSchemaError(
            f"status must be in statusEnum, got {row['status']!r}"
        )


# ---------------------------------------------------------------------------
# Core transform
# ---------------------------------------------------------------------------

def _iter_sf_rows(raw_sf: dict) -> Iterable[dict]:
    """Tolerate the two SF envelope shapes used across the codebase:

      - `{"rows": [ {url|address, json_ld, ...}, ... ]}` (flat envelope)
      - `{"_meta": {...}, "files": [{"canonical_name": "structured_data_all",
        "rows": [...]}]}` (sf-import envelope; we extract the
        structured_data rows specifically)
    """
    if not isinstance(raw_sf, dict):
        raise SchemaAuditError(
            f"raw_sf must be a dict, got {type(raw_sf).__name__}"
        )

    rows = raw_sf.get("rows")
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict):
                yield r
        return

    files = raw_sf.get("files")
    if isinstance(files, list):
        for f in files:
            if not isinstance(f, dict):
                continue
            canonical = _safe_str(f.get("canonical_name"))
            if canonical and canonical != "structured_data_all":
                continue
            f_rows = f.get("rows")
            if isinstance(f_rows, list):
                for r in f_rows:
                    if isinstance(r, dict):
                        yield r
        return

    # Empty / no recognised envelope → no rows.
    return


def transform(
    raw_sf: dict,
    raw_dfs: dict | None = None,
    *,
    strict_parse: bool = False,
    default_status: str = "TODO",
) -> dict:
    """Transform SF structured-data export (+ optional DFS payload) into
    schema-shaped rows for master.xlsx#schema.

    Args:
        raw_sf: Parsed SF envelope (`{"rows": [...]}` flat OR sf-import
                envelope with `files: [{canonical_name: "structured_data_all"
                ,rows: [...]}]`). Per-row keys tolerate `address`/`url`,
                `JSON-LD`/`json_ld`/`jsonld_blob`, `Type`/`schema_types`.
        raw_dfs: Optional parsed DFS on_page_content_parsing response.
                 When present, the transform uses it to enrich
                 `remaining_work` notes — never to silently flip status.
        strict_parse: When True, malformed JSON-LD blobs raise
                JsonLdParseError. When False (default) malformed rows are
                dropped silently (the inbox-recovery file is the durable
                witness; SKILL.md DURUR #3 documents this).
        default_status: statusEnum seed for type-only rows (SF detected the
                schema type but no JSON-LD blob, so props can't be verified).
                Frontmatter default "TODO"; operator-overridable. Must be a
                statusEnum member or SchemaAuditError is raised.

    Returns: {"schema": [<row>, ...], "meta": {...}}.

    Raises:
        SchemaAuditError on bad input (incl. default_status outside statusEnum).
        JsonLdParseError on malformed JSON-LD when strict_parse=True.
        RowSchemaError on column / statusEnum drift.
    """
    if not isinstance(raw_sf, dict):
        raise SchemaAuditError(
            f"raw_sf must be a dict, got {type(raw_sf).__name__}"
        )
    if raw_dfs is not None and not isinstance(raw_dfs, dict):
        raise SchemaAuditError(
            f"raw_dfs must be a dict or None, got {type(raw_dfs).__name__}"
        )
    if default_status not in _STATUS_ENUM:
        raise SchemaAuditError(
            f"default_status must be in statusEnum {sorted(_STATUS_ENUM)}, "
            f"got {default_status!r}"
        )

    dfs_index = _index_dfs_schemas(raw_dfs) if raw_dfs is not None else {}

    candidates: list[_Candidate] = []
    sf_row_count = 0
    instance_count = 0
    parse_errors = 0

    for sf_row in _iter_sf_rows(raw_sf):
        sf_row_count += 1
        try:
            instances, errs = _extract_schema_instances(
                sf_row, strict=strict_parse,
            )
        except JsonLdParseError:
            if strict_parse:
                raise
            parse_errors += 1
            continue
        parse_errors += errs

        for inst in instances:
            instance_count += 1
            dfs_types = dfs_index.get(inst.url)
            if dfs_types is None:
                dfs_confirmed: bool | None = None
            else:
                dfs_confirmed = inst.schema_type in dfs_types

            status, remaining = _derive_status_and_work(
                inst, dfs_confirmed=dfs_confirmed,
                default_status=default_status,
            )

            candidates.append(_Candidate(
                schema_type=inst.schema_type,
                status=status,
                location=inst.url,
                scope="page-level",
                remaining_work=remaining,
            ))

    schema_rows = _aggregate(candidates)

    return {
        "schema": schema_rows,
        "meta": {
            "sf_row_count": sf_row_count,
            "instance_count": instance_count,
            "parse_errors": parse_errors,
            "row_count": len(schema_rows),
            "dfs_used": raw_dfs is not None,
            "dfs_url_count": len(dfs_index),
        },
    }


# ---------------------------------------------------------------------------
# Budget pre-flight (paid DFS branch)
# ---------------------------------------------------------------------------

def estimate_credits(url_count: int) -> float:
    """Estimate DFS credits for cross-validating N URLs via on_page_content_parsing."""
    if url_count is None or url_count < 0:
        return 0.0
    return float(url_count) * CREDITS_PER_URL_CONTENT_PARSING


def preflight_budget(
    *,
    estimated_credits: float,
    project_config_path: str,
    events_path: str,
) -> dict:
    """Run the §16.8 budget pre-flight via the in-process check_budget
    helpers and DURUR if exceeded. Mirrors `on_page_audit_transform.preflight_budget`
    boundary semantics so the skill orchestrator code is identical.
    """
    try:
        from scripts.budget import check_budget as _cb
    except ImportError as exc:
        raise BudgetExceededError(
            "scripts.budget.check_budget unavailable — pre-flight "
            f"integration is mandatory for paid MCPs ({exc})"
        ) from exc

    from datetime import datetime, timezone

    cfg_path = Path(project_config_path)
    evt_path = Path(events_path)

    try:
        budget = _cb._load_budget(cfg_path)  # type: ignore[attr-defined]
    except SystemExit as exc:
        raise BudgetExceededError(
            f"budget pre-flight: project-config unreadable ({cfg_path}): "
            f"exit={exc.code}"
        ) from exc

    used = _cb._sum_last_24h(  # type: ignore[attr-defined]
        evt_path, datetime.now(timezone.utc),
    )
    projected = float(used) + float(estimated_credits)
    payload = {
        "budget_per_day": int(budget),
        "used_24h": used,
        "estimated_credits": float(estimated_credits),
        "projected_used": projected,
        "remaining_after": float(budget) - projected,
        "exceeded": projected > float(budget),
    }
    if payload["exceeded"]:
        raise BudgetExceededError(
            f"budget pre-flight FAIL: projected={projected:.2f} > "
            f"budget={budget} (used_24h={used}, estimate={estimated_credits})"
        )
    return payload


# ---------------------------------------------------------------------------
# CSV loader (helper for ad-hoc CLI / tests)
# ---------------------------------------------------------------------------

def load_sf_csv(path: Path) -> dict:
    """Load a SF `structured_data_all.csv` style export into the flat
    envelope shape `{"rows": [ {col: val, ...}, ... ]}`. Header row is
    used verbatim as keys (case-preserved). Blank rows are skipped.
    """
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if any(_safe_str(v) for v in row.values()):
                rows.append({k: v for k, v in row.items() if k is not None})
    return {"rows": rows}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="schema_audit_transform.py",
        description=(
            "Transform SF structured-data export (+ optional DFS "
            "content_parsing) → master.xlsx#schema rows."
        ),
    )
    p.add_argument(
        "--raw-sf", required=True,
        help="Path to parsed SF structured-data JSON envelope OR a CSV.",
    )
    p.add_argument(
        "--raw-dfs", default=None,
        help="Optional path to mcp__dataforseo__on_page_content_parsing JSON.",
    )
    p.add_argument(
        "--strict-parse", action="store_true",
        help="Raise JsonLdParseError on malformed JSON-LD (default: drop row).",
    )
    p.add_argument(
        "--default-status", default="TODO",
        help="statusEnum seed for type-only rows (SF type detected, no JSON-LD "
             "blob); default TODO. Per the SKILL.md default_status input.",
    )
    p.add_argument(
        "--output-dir", default=None,
        help="If set, write schema_audit.json into this directory.",
    )
    return p.parse_args(list(argv))


def _read_json_or_csv(path: Path) -> dict:
    if path.suffix.lower() == ".csv":
        return load_sf_csv(path)
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def main(argv: list[str]) -> int:
    args = _parse_args(argv)

    sf_path = Path(args.raw_sf)
    if not sf_path.exists():
        print(f"raw SF file not found: {sf_path}", file=sys.stderr)
        return 2
    raw_sf = _read_json_or_csv(sf_path)

    raw_dfs: dict | None = None
    if args.raw_dfs:
        dfs_path = Path(args.raw_dfs)
        if not dfs_path.exists():
            print(f"raw DFS file not found: {dfs_path}", file=sys.stderr)
            return 2
        with dfs_path.open("r", encoding="utf-8") as fh:
            raw_dfs = json.load(fh)

    try:
        result = transform(
            raw_sf, raw_dfs,
            strict_parse=args.strict_parse,
            default_status=args.default_status,
        )
    except SchemaAuditError as exc:
        print(f"transform failed: {exc}", file=sys.stderr)
        return 1

    if args.output_dir:
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "schema_audit.json"
        out_path.write_text(
            json.dumps(result["schema"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps({
            "schema_audit_path": str(out_path.resolve()),
            "meta": result["meta"],
        }, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


__all__ = (
    "SCHEMA_AUDIT_COLUMNS",
    "CREDITS_PER_URL_CONTENT_PARSING",
    "SchemaAuditError",
    "JsonLdParseError",
    "RowSchemaError",
    "BudgetExceededError",
    "transform",
    "estimate_credits",
    "preflight_budget",
    "load_sf_csv",
    "main",
)
