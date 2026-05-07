"""scripts/util/dfs_response.py — Y-02 endpoint-aware DFS response normalize.

DataForSEO API responses surface in production with three top-level shapes
plus two endpoint-specific inline payload shapes. Three transform/ingestion
modules previously each maintained their own ``_normalize_dfs_response``
variant with semantic divergence between keyword and Lighthouse endpoints
(Lesson 38 v2 #34-35 by-design extension). Y-02 collapses the three
local copies into one endpoint-aware dispatcher and the call-sites
adapt-wrap :class:`DFSResponseError` into their own domain-specific
exception classes (paterni K-01 reuse).

Canonical shapes the dispatcher accepts:

    1. REST envelope (upstream / direct HTTP / well-behaved wrappers)
         {"tasks": [{"result": [{"items": [...]}]}]}
    2. Flat wrapper (dataforseo-mcp-server@2.8.9 flattening — labs +
       on_page endpoints both observed in live tests)
         {"items": [...]}
    3. Inline keyword (DFS labs endpoints inline keyword fields directly
       on result entries when there is no ``items`` wrapper)
         {"tasks": [{"result": [{"keyword": "...", "search_volume": ...}]}]}
    4. Inline Lighthouse (on_page_lighthouse inline page audits at the
       per-result level — performance scores live on the result entry)
         {"tasks": [{"result": [{"url": ..., "lighthouse": ..., "page_metrics": ...}]}]}
    5. Top-level Lighthouse audits (some MCP wrappers strip the envelope
       entirely and surface the audit payload directly)
         {"lighthouse": ..., "audits": ...}

Endpoint dispatcher semantics:
    * ``endpoint_type=None`` — broadest tolerance, accept all inline shapes.
    * ``endpoint_type="keyword"`` — only inline ``keyword`` key counted;
      Lighthouse inline payloads are skipped (matches dfs_pull semantic).
    * ``endpoint_type="lighthouse"`` — only inline ``lighthouse`` /
      ``page_metrics`` counted (matches tech_audit semantic).

DURUR triggers (raise :class:`DFSResponseError`, extends :class:`ValueError`):
    * top-level not a dict
    * none of the above shapes recognisable

Refs:
    * spec §11.5 (DFS keyword endpoints) + §11.6 (DFS Lighthouse)
    * 2026-05-07 v1.6-Phase-3 Y-02 + O-03 (this module + 2 transform migrate)
    * Lesson 38 v2 #34-35 v1.5-Phase-1 (semantic divergence by-design)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DFSResponseError",
    "normalize_dfs_response",
    "safe_int",
    "safe_float",
    "safe_str",
]


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class DFSResponseError(ValueError):
    """Raised on invalid input to :func:`normalize_dfs_response`.

    Extends :class:`ValueError` so legacy callers that expected a bare
    ``ValueError`` (pre-Y-02 ``_normalize_dfs_response``) continue to
    work.  Domain-specific call-sites wrap this into their own exception
    class via the import-adapter pattern (paterni K-01 reuse).
    """


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def normalize_dfs_response(
    raw: dict,
    *,
    endpoint_type: str | None = None,
    expected_endpoint: str | None = None,
) -> list[dict]:
    """Return a list of item dicts from a DataForSEO ``raw`` response.

    See module docstring for the full shape list and dispatcher semantics.
    Pure function — no I/O, no state mutation, idempotent.
    """
    if not isinstance(raw, dict):
        raise DFSResponseError(
            "Unrecognized DFS response shape: top-level must be a dict, "
            f"got {type(raw).__name__}"
        )

    include_keyword_inline = endpoint_type in (None, "keyword")
    include_lighthouse_inline = endpoint_type in (None, "lighthouse")

    # 1. REST envelope: tasks[].result[].items (preferred — closest to
    #    the upstream DataForSEO REST contract).
    tasks = raw.get("tasks")
    if isinstance(tasks, list) and tasks:
        items: list[dict] = []
        saw_result = False
        for task in tasks:
            if not isinstance(task, dict):
                continue
            result = task.get("result")
            if isinstance(result, list):
                saw_result = True
                for r in result:
                    if not isinstance(r, dict):
                        continue
                    inner = r.get("items")
                    if isinstance(inner, list):
                        items.extend(x for x in inner if isinstance(x, dict))
                    # Endpoint-specific inline detection. ``elif`` prevents
                    # double-counting if a result entry happens to carry
                    # both a keyword key and a lighthouse payload (defensive
                    # — production responses don't mix these contracts).
                    if include_keyword_inline and r.get("keyword") is not None:
                        items.append(r)
                    elif include_lighthouse_inline and (
                        r.get("lighthouse") is not None
                        or r.get("page_metrics") is not None
                    ):
                        items.append(r)
        if saw_result:
            return items
        # tasks[] present but no result[] — fall through to flat check.

    # 2. Flat wrapper: top-level items list.
    flat_items = raw.get("items")
    if isinstance(flat_items, list):
        return [x for x in flat_items if isinstance(x, dict)]

    # 5. Top-level Lighthouse audit (some MCP wrappers strip the envelope).
    if include_lighthouse_inline and (
        raw.get("lighthouse") is not None or raw.get("audits") is not None
    ):
        return [raw]

    # 6. Neither shape recognised.
    suffix = f" (endpoint={expected_endpoint!r})" if expected_endpoint else ""
    raise DFSResponseError(
        f"Unrecognized DFS response shape{suffix}: expected REST envelope "
        f"`tasks[0].result[0].items`, flat wrapper `items`, or inline "
        f"payload, got top-level keys={sorted(raw.keys())}"
    )


# ---------------------------------------------------------------------------
# Typed coercion helpers (None / empty-string safe)
# ---------------------------------------------------------------------------


def safe_int(value: Any, default: int = 0) -> int:
    """Coerce ``value`` to ``int`` with safe fallback.

    ``None`` and empty-string short-circuit to ``default``; non-numeric
    strings (``"abc"``) and uncoercible types also return ``default``.
    Float inputs are truncated via ``int()`` (Python semantics).
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce ``value`` to ``float`` with safe fallback.

    ``None`` and empty-string short-circuit to ``default``; non-numeric
    strings and uncoercible types also return ``default``.
    """
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Coerce ``value`` to ``str`` with safe fallback.

    ``None`` short-circuits to ``default``; everything else is run
    through ``str()``. Note: empty-string input returns ``""`` (not
    ``default``) — only ``None`` triggers the fallback.
    """
    if value is None:
        return default
    return str(value)
