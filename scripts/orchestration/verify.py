"""Raw-drop identity + content + freshness gate for the AMO orchestrator spine.

The model makes a step's MCP call and writes a raw artifact to an
orchestrator-dictated path (the path embeds run_id, so a misnamed / wrong-project
drop simply is not where the gate looks). ``verify_raw_drop`` is the CODE gate
that runs before the pure transform + commit: it confirms the drop's provenance
matches what THIS step expected (identity), is recent enough (freshness), and is
not truncated (content) — RETURNING a stable reason code on any defect. It never
raises for an *expected* bad drop; exceptions are reserved for programmer error.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Stable reason codes (the coverage record + denetçi key on these strings):
#   missing_file parse_error no_provenance run_id_mismatch slug_mismatch
#   site_url_mismatch window_mismatch tool_mismatch stale truncated


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of gating one raw drop.

    On failure ``reason`` is a stable code and ``rows`` / ``input_count`` stay
    None; on success ``ok`` is True, ``rows`` is the verified row list and
    ``input_count`` is its length.
    """

    ok: bool
    reason: str | None = None
    rows: list[dict] | None = None
    input_count: int | None = None


def _parse_iso_to_epoch(value: Any) -> float | None:
    """Parse an ISO-8601 timestamp to a POSIX epoch; None if unparseable.

    Accepts a trailing ``Z`` (Python 3.10's ``fromisoformat`` does not) and
    treats a naive timestamp as UTC. Pure — reads no wall clock.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _identity_reason(
    prov: dict,
    *,
    expected_run_id: str,
    expected_slug: str,
    expected_site_url: str | None,
    expected_window: str | None,
    expected_tool: str | None,
) -> str | None:
    """First provenance-identity mismatch reason, or None if all match.

    The path embeds run_id, but the provenance block is verified to agree.
    site_url / window / tool are checked ONLY when the caller declared an
    expectation (None means "this step does not pin that field").
    """
    if prov.get("run_id") != expected_run_id:
        return "run_id_mismatch"
    if prov.get("slug") != expected_slug:
        return "slug_mismatch"
    if expected_site_url is not None and prov.get("site_url") != expected_site_url:
        return "site_url_mismatch"
    if expected_window is not None and prov.get("window") != expected_window:
        return "window_mismatch"
    if expected_tool is not None and prov.get("tool") != expected_tool:
        return "tool_mismatch"
    return None


def _is_stale(prov: dict, path: Path, now_epoch: float, max_age_seconds: float) -> bool:
    """True if the file's mtime OR the declared fetched_at is older than max_age."""
    if (now_epoch - os.path.getmtime(path)) > max_age_seconds:
        return True
    fetched_epoch = _parse_iso_to_epoch(prov.get("fetched_at"))
    return fetched_epoch is not None and (now_epoch - fetched_epoch) > max_age_seconds


def verify_raw_drop(
    raw_path: Path | str,
    *,
    expected_run_id: str,
    expected_slug: str,
    now_epoch: float,
    expected_site_url: str | None = None,
    expected_window: str | None = None,
    expected_tool: str | None = None,
    max_age_seconds: float = 86_400,
) -> VerifyResult:
    """Gate one model-dropped raw artifact.

    Returns a not-ok ``VerifyResult`` with a stable reason code for any expected
    defect (never raises for a bad drop), checking in order: existence, parse,
    structure, identity, freshness, truncation. On success the returned ``rows``
    is the drop's row list and ``input_count`` its length. Builds a new result;
    never mutates inputs.
    """
    path = Path(raw_path)
    if not path.exists():
        return VerifyResult(ok=False, reason="missing_file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return VerifyResult(ok=False, reason="parse_error")
    if not isinstance(data, dict):
        return VerifyResult(ok=False, reason="parse_error")

    prov = data.get("provenance")
    if not isinstance(prov, dict):
        return VerifyResult(ok=False, reason="no_provenance")
    rows = data.get("rows")
    if not isinstance(rows, list):
        return VerifyResult(ok=False, reason="parse_error")

    identity = _identity_reason(
        prov,
        expected_run_id=expected_run_id,
        expected_slug=expected_slug,
        expected_site_url=expected_site_url,
        expected_window=expected_window,
        expected_tool=expected_tool,
    )
    if identity is not None:
        return VerifyResult(ok=False, reason=identity)
    if _is_stale(prov, path, now_epoch, max_age_seconds):
        return VerifyResult(ok=False, reason="stale")
    if prov.get("declared_count") != len(rows):
        return VerifyResult(ok=False, reason="truncated")

    return VerifyResult(ok=True, rows=rows, input_count=len(rows))


def silent_skip_exceeds(
    input_count: int, scored_count: int, *, max_ratio: float = 0.5
) -> bool:
    """True iff the step silently dropped more than ``max_ratio`` of its input.

    The high-silent-skip HARD-FAIL gate (spec section 7-1b): a transform that
    received ``input_count`` rows but committed far fewer has likely swallowed
    errors. False when ``input_count`` is 0 (nothing to skip).
    """
    if input_count <= 0:
        return False
    return (input_count - scored_count) / input_count > max_ratio
