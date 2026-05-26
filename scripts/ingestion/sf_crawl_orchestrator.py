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

import json
import shutil
from pathlib import Path
from typing import Any, NamedTuple

from scripts.ingestion.sf_import import TIER1_REQUIRED, TIER2_RECOMMENDED

__all__ = (
    "ProgressState",
    "SfCrawlOrchestratorError",
    "enumerate_reports",
    "move_with_rollback",
    "parse_progress_response",
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
