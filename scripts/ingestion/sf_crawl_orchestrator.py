"""scripts/ingestion/sf_crawl_orchestrator.py — sf-crawl-orchestrator pure-transform helpers.

Pure transform helpers for v1.8 sf-crawl-orchestrator skill. MCP HTTP calls
happen in `skills/ingestion/sf-crawl-orchestrator/SKILL.md` body (via Claude's
``mcp__sf__sf_*`` wrappers); this module provides only the deterministic
helpers the body and tests share:

* ``enumerate_reports(include_tier3=False)`` — return ordered list of canonical
  report names sourced from ``sf_import.TIER1_REQUIRED`` + ``TIER2_RECOMMENDED``
  (SSoT discipline per rules/single-source-of-truth.md). When ``include_tier3``
  is True, Tier 3 names sourced from ``schemas/sf-required-reports.schema.json``
  `definitions.canonicalName.enum` minus T1+T2.
* ``move_with_rollback(src, dst)`` — wrap ``shutil.move`` with explicit error
  surfacing so the orchestrator body can decide rollback vs continue.
* ``parse_progress_response(raw)`` — coerce sf_crawl_progress JSON-RPC result
  into a stable ``ProgressState`` namedtuple (status + urls_crawled +
  raw_payload retained for forensics).

Mirrors ``scripts/ingestion/gsc_pull.py`` / ``scripts/ingestion/dfs_pull.py``
pattern: pure functions only, no MCP I/O. Tested independently.

Refs:
    * D-SF-06 — orchestrator is NEW skill; helpers here, MCP body in SKILL.md
    * D-SF-16 — atomic crawl semantics; move_with_rollback supports rollback
    * Q-SF-MCP-10 — Tier 3 default False (24 reports); include_tier3=True → 40
    * schemas/sf-required-reports.schema.json — canonicalName enum (40)
    * scripts/ingestion/sf_import.py — TIER1_REQUIRED (14) + TIER2_RECOMMENDED (10) SSoT
"""

from __future__ import annotations

import csv
import io
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from scripts.ingestion.sf_import import TIER1_REQUIRED, TIER2_RECOMMENDED

__all__ = (
    "ProgressState",
    "SfExportSpec",
    "SfCrawlOrchestratorError",
    "build_export_plan",
    "enumerate_reports",
    "export_returns_ndjson",
    "move_with_rollback",
    "ndjson_to_csv",
    "parse_progress_response",
    "SF_EXPORT_DISPATCH",
    "TIER1_COUNT",
    "TIER2_COUNT",
    "TIER3_COUNT",
)


# ---------------------------------------------------------------------------
# Constants — declarative summaries, but the lists themselves come from SSoT.
# ---------------------------------------------------------------------------

#: 14 Tier 1 mandatory reports (sf-import RED FAIL if any missing).
TIER1_COUNT: int = 14

#: 10 Tier 2 recommended reports (sf-import AMBER warning if any missing).
TIER2_COUNT: int = 10

#: 16 Tier 3 optional reports (40 canonicalName enum − T1 − T2).
TIER3_COUNT: int = 16


# Cached on first access (small set, immutable).
_TIER3_CACHE: frozenset[str] | None = None


def _repo_root() -> Path:
    """Return the engine repository root (one parents up from scripts/)."""
    return Path(__file__).resolve().parents[2]


def _load_tier3() -> frozenset[str]:
    """Tier 3 = canonicalName enum minus TIER1 + TIER2.

    Loaded from ``schemas/sf-required-reports.schema.json``; cached after first
    call. SSoT discipline: we do not hardcode the 16 names; we derive them.
    """
    global _TIER3_CACHE
    if _TIER3_CACHE is not None:
        return _TIER3_CACHE
    schema_path = _repo_root() / "schemas" / "sf-required-reports.schema.json"
    raw = json.loads(schema_path.read_text("utf-8"))
    enum = raw["definitions"]["canonicalName"]["enum"]
    full = frozenset(enum)
    _TIER3_CACHE = full - TIER1_REQUIRED - TIER2_RECOMMENDED
    return _TIER3_CACHE


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class SfCrawlOrchestratorError(Exception):
    """Base class for sf_crawl_orchestrator transform errors."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ProgressState(NamedTuple):
    """Normalized shape returned by ``parse_progress_response``.

    Attributes:
        status: One of ``"IN_PROGRESS"``, ``"DONE"``, ``"FAILED"`` (per SF MCP
            sf_crawl_progress contract). Unknown values pass through verbatim
            so the orchestrator's status check still surfaces them clearly.
        urls_crawled: Best-effort URL counter (0 if not reported).
        raw: The original JSON-RPC result dict, retained for forensics so the
            orchestrator can include it in DURUR error messages.
    """

    status: str
    urls_crawled: int
    raw: dict


def enumerate_reports(include_tier3: bool = False) -> list[str]:
    """Return the canonical report names the orchestrator must export.

    Default (Tier 1 + Tier 2 = 24): sourced from
    ``scripts.ingestion.sf_import.TIER1_REQUIRED`` and ``TIER2_RECOMMENDED``
    frozensets. With ``include_tier3=True``, Tier 3 names (16) are appended,
    yielding 40 total.

    Names are returned in deterministic alphabetical order within each tier so
    the export loop is reproducible across runs.

    Args:
        include_tier3: When True, append the 16 Tier 3 optional report names.

    Returns:
        List of canonical report name strings.
    """
    tier1_sorted = sorted(TIER1_REQUIRED)
    tier2_sorted = sorted(TIER2_RECOMMENDED)
    if not include_tier3:
        return tier1_sorted + tier2_sorted
    tier3_sorted = sorted(_load_tier3())
    return tier1_sorted + tier2_sorted + tier3_sorted


def move_with_rollback(src: Path | str, dst: Path | str) -> bool:
    """Move a file from ``src`` to ``dst``; surface failures via exception.

    Wraps ``shutil.move`` with explicit pre-flight target-exists check so the
    orchestrator can decide its own rollback action when DURUR-orch-5 or -6
    fires (the orchestrator deletes the temp staging directory and surfaces
    the failure; this helper itself does not delete state).

    Args:
        src: Source path (file). Must exist; raises ``SfCrawlOrchestratorError``
            otherwise.
        dst: Destination path (file). Must NOT already exist; we refuse to
            overwrite (operator-must-archive policy mirrors DURUR-orch-5 at
            the directory level).

    Returns:
        True on success (matches the orchestrator's binary "moved or didn't"
        expectation). Caller should treat any exception as a hard failure.
    """
    src_p = Path(src)
    dst_p = Path(dst)
    if not src_p.exists():
        raise SfCrawlOrchestratorError(
            f"move_with_rollback: source missing {src_p}"
        )
    if dst_p.exists():
        raise SfCrawlOrchestratorError(
            f"move_with_rollback: target already exists {dst_p}"
        )
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(src_p), str(dst_p))
    except OSError as exc:
        raise SfCrawlOrchestratorError(
            f"move_with_rollback: shutil.move failed src={src_p} dst={dst_p}: {exc}"
        ) from exc
    return True


def parse_progress_response(raw: Any) -> ProgressState:
    """Normalize a sf_crawl_progress response into ``ProgressState``.

    Accepts the JSON-RPC ``result`` envelope returned by
    ``mcp__sf__sf_crawl_progress``. Tolerates two shapes observed in
    SF 24 MCP across versions:

    1. Flat dict: ``{"status": "IN_PROGRESS", "urls_crawled": 1234, ...}``
    2. Nested ``progress`` dict: ``{"progress": {"status": ..., "urls_crawled": ...}}``

    Unknown status strings pass through verbatim so the orchestrator's
    DURUR-orch-3 fail path can include them in the error message.

    Args:
        raw: Anything returned by ``mcp__sf__sf_crawl_progress``. Non-dict
            inputs raise ``SfCrawlOrchestratorError``.

    Returns:
        ProgressState with status (str), urls_crawled (int), raw (dict).
    """
    if not isinstance(raw, dict):
        raise SfCrawlOrchestratorError(
            f"parse_progress_response: expected dict, got {type(raw).__name__}"
        )

    nested = raw.get("progress") if isinstance(raw.get("progress"), dict) else None
    src = nested or raw

    status = src.get("status")
    if not isinstance(status, str) or not status:
        raise SfCrawlOrchestratorError(
            f"parse_progress_response: missing/empty status in payload keys "
            f"{sorted(src.keys())!r}"
        )

    urls_raw = src.get("urls_crawled", 0)
    try:
        urls_int = int(urls_raw)
    except (TypeError, ValueError):
        urls_int = 0

    return ProgressState(status=status, urls_crawled=urls_int, raw=raw)


# ---------------------------------------------------------------------------
# SF export dispatch — engine canonical names → real SF MCP tools/categories.
# ---------------------------------------------------------------------------
#
# The 24 engine canonical report names (internal_all, page_titles_all, …) are
# NOT Screaming Frog identifiers. They map to a MIX of three real SF MCP export
# tools, each with its own arg shape (Manager-probed live against the SF 24 MCP):
#
#   * ``sf_generate_report``         — ``category`` ("Cat:Subcat" colon form
#     from sf_list_available_reports) + ``export_type`` ("CSV"|"NDJSON").
#   * ``sf_generate_bulk_export``    — identical shape; ``category`` sourced
#     from sf_list_available_bulk_exports.
#   * ``sf_export_seo_element_urls`` — ``seo_element_name`` (enum) +
#     ``filter_name`` ("All" valid for every element). This tool has NO
#     ``export_type`` arg (writes CSV by default).
#
# All three operate on the *currently-loaded* crawl and write to ``file_path``
# (relative to the SF allowed base directory). There is NO crawl_id /
# report_name / save_report / output_directory arg on any of them — the prior
# SKILL.md loop was wrong. The orchestrator caller adds ``file_path`` itself,
# always ``f"{canonical}.csv"`` so sf_import's ``normalize_filename`` matches.
#
# Each value is ``(tool_name, call_kwargs_without_file_path)``. Keep readable
# and one-line-per-canonical so a Manager live-validation pass can correct any
# single category string in place. ``build_export_plan`` attaches the tier.

#: One reusable seo-element-urls kwargs builder (no export_type — tool lacks it).
def _seo(element: str, filter_name: str = "All") -> tuple[str, dict[str, str]]:
    return ("sf_export_seo_element_urls",
            {"seo_element_name": element, "filter_name": filter_name})


def _report(category: str) -> tuple[str, dict[str, str]]:
    return ("sf_generate_report", {"category": category, "export_type": "CSV"})


def _bulk(category: str) -> tuple[str, dict[str, str]]:
    return ("sf_generate_bulk_export", {"category": category, "export_type": "CSV"})


#: canonical → (tool, call_kwargs). Covers exactly the 24 (T1 14 + T2 10).
#: Tier 3 is intentionally absent (orchestrator default include_tier3=False);
#: build_export_plan raises NotImplementedError for any unmapped canonical.
SF_EXPORT_DISPATCH: dict[str, tuple[str, dict[str, str]]] = {
    # --- Tier 1 (14) ------------------------------------------------------
    "internal_all": _seo("Internal"),
    "all_inlinks": _bulk("Links:All Inlinks"),
    "all_outlinks": _bulk("Links:All Outlinks"),
    "response_codes_all": _seo("Response Codes"),
    "issues_overview_report": _report("Issues Overview"),
    "page_titles_all": _seo("Page Titles"),
    "meta_description_all": _seo("Meta Description"),
    "h1_all": _seo("H1"),
    "canonicals_all": _seo("Canonicals"),
    "directives_all": _seo("Directives"),
    # SF has no dedicated Indexability tab; Internal carries Indexability cols.
    "indexability": _seo("Internal"),
    "structured_data_all": _seo("Structured Data"),
    "sitemaps_all": _seo("Sitemaps"),
    "redirect_chains": _report("Redirects:Redirect Chains"),
    # --- Tier 2 (10) ------------------------------------------------------
    "h2_all": _seo("H2"),
    "images_all": _seo("Images"),
    "hreflang_all": _seo("Hreflang"),
    "orphan_pages": _report("Orphan Pages"),
    "all_anchor_text": _bulk("Links:All Anchor Text"),
    "near_duplicates_report": _bulk("Content:Near Duplicates"),
    "exact_duplicates_report": _bulk("Content:Exact Duplicates"),
    "search_console_all": _seo("Search Console"),
    # SF has no crawl-depth tab; Internal carries the Crawl Depth column.
    "crawl_depth": _seo("Internal"),
    "pagination_all": _seo("Pagination"),
}


@dataclass(frozen=True)
class SfExportSpec:
    """One SF export instruction for a single engine canonical report.

    Attributes:
        canonical: Engine canonical report name (e.g. ``"internal_all"``).
            The caller writes the export to ``f"{canonical}.csv"`` so
            ``sf_import.normalize_filename`` matches downstream.
        tool: Which SF MCP tool to call — one of ``"sf_generate_report"``,
            ``"sf_generate_bulk_export"``, ``"sf_export_seo_element_urls"``.
        call_kwargs: SF call kwargs WITHOUT ``file_path`` (the caller adds
            ``file_path=f"{canonical}.csv"``). For report/bulk tools this is
            ``{"category": ..., "export_type": "CSV"}``; for the seo-element
            tool it is ``{"seo_element_name": ..., "filter_name": ...}`` (that
            tool has no ``export_type`` arg).
        tier: ``"tier1"`` (DURUR-orch-8 rollback on fail) or ``"tier2"``
            (AMBER warning on fail), mirroring sf-import tier policy.
    """

    canonical: str
    tool: str
    call_kwargs: dict[str, str] = field(default_factory=dict)
    tier: str = "tier1"


def build_export_plan(include_tier3: bool = False) -> list[SfExportSpec]:
    """Return the ordered SF export plan — one spec per canonical report.

    Pure function: no MCP, no I/O. Specs are emitted in ``enumerate_reports``
    order (Tier 1 sorted, then Tier 2 sorted) so the orchestrator export loop
    is reproducible and tiers stay contiguous. Each call returns fresh objects
    (no shared mutable state) so a caller cannot corrupt the next invocation.

    The caller turns each spec into an actual SF call by adding
    ``file_path=f"{spec.canonical}.csv"`` and dispatching on ``spec.tool``
    with ``**spec.call_kwargs``.

    Args:
        include_tier3: When True, also plan the 16 Tier 3 reports. These have
            no live-validated dispatch yet (orchestrator default is False), so
            any Tier 3 canonical not present in ``SF_EXPORT_DISPATCH`` raises
            ``NotImplementedError`` rather than inventing a mapping.

    Returns:
        List of ``SfExportSpec`` covering exactly ``enumerate_reports`` names.

    Raises:
        NotImplementedError: a requested canonical has no dispatch entry
            (only reachable with ``include_tier3=True``).
    """
    plan: list[SfExportSpec] = []
    for canonical in enumerate_reports(include_tier3=include_tier3):
        mapping = SF_EXPORT_DISPATCH.get(canonical)
        if mapping is None:
            raise NotImplementedError(
                f"build_export_plan: no SF dispatch mapping for canonical "
                f"{canonical!r} (Tier 3 dispatch is a documented TODO; the "
                f"orchestrator default include_tier3=False covers the 24-set)"
            )
        tool, base_kwargs = mapping
        tier = "tier1" if canonical in TIER1_REQUIRED else "tier2"
        # Copy call_kwargs so each spec owns an independent dict (immutability:
        # callers never share the module-level constant's nested dicts).
        plan.append(SfExportSpec(
            canonical=canonical,
            tool=tool,
            call_kwargs=dict(base_kwargs),
            tier=tier,
        ))
    return plan


def export_returns_ndjson(spec: SfExportSpec) -> bool:
    """True when this spec's SF tool emits NDJSON (caller must convert to CSV).

    Only ``sf_export_seo_element_urls`` lacks an ``export_type`` arg and always
    writes NDJSON; ``sf_generate_report`` / ``sf_generate_bulk_export`` honor
    ``export_type="CSV"``. Live-verified against SF 24 (2026-06-02): a Page
    Titles element export returned ``{"format":"NDJSON",...}`` while Issues
    Overview / Links:All Inlinks returned real CSV. The orchestrator converts
    the 16 seo-element exports via :func:`ndjson_to_csv` before the atomic move
    so sf_import (CSV-only, header-matched) consumes a uniform CSV ``raw/`` set.
    """
    return spec.tool == "sf_export_seo_element_urls"


def _csv_cell(value: Any) -> Any:
    """Render one NDJSON value for a CSV cell: None→'', dict/list→compact JSON."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def ndjson_to_csv(ndjson_text: str) -> str:
    """Convert an SF NDJSON export (one flat JSON object per line) to CSV text.

    sf_import consumes CSV (``normalize_filename`` + header matching); the
    seo-element export tool only emits NDJSON, so the orchestrator converts
    those reports before the atomic move. Column order = first-seen key order
    across all rows (SF emits stable keys per export). ``None`` → empty cell;
    dict/list values → compact JSON so no row is silently dropped.

    Returns "" for empty/whitespace input (a legitimately empty SF export, e.g.
    search_console_all when GSC is not connected — a Tier 2 AMBER case).
    """
    rows = [json.loads(line) for line in ndjson_text.splitlines() if line.strip()]
    if not rows:
        return ""
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({col: _csv_cell(row.get(col)) for col in columns})
    return buffer.getvalue()
