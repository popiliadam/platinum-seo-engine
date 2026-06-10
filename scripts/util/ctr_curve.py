#!/usr/bin/env python3
"""ctr_curve.py — pure loader for the versioned position-CTR + AIO-discount curve.

Reads ``ctr-curve.json`` (engine root) into an immutable :class:`Curve`.
The curve provides:

  * ``expected_ctr(position)`` — linear interpolation between listed
    positions, clamped at the ends.
  * ``aio_factor(position, aio_presence)`` — multiplicative CTR discount
    applied ONLY when ``aio_presence == "present"``; ``not_detected`` and
    ``unchecked`` return ``1.0`` (honesty: unknown is flagged, not penalised
    — measurement-discipline R-140).

Why a data file instead of literals: measurement-discipline R-139 forbids
copying CTR/AIO constants into Python/SKILL bodies — they live here with
provenance so the numbers can be re-sourced when a newer study lands without
silent code/data drift.

Pure-function discipline: no state mutation, no network, stdlib only. A
missing or structurally-invalid file raises :class:`CurveLoadError`
(``ValueError`` subclass) so callers DURUR instead of silently falling back
to a legacy formula (quick-wins DURUR #11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CurveLoadError(ValueError):
    """Raised when the curve file is missing, unreadable, or structurally invalid."""


@dataclass(frozen=True)
class Curve:
    """Immutable CTR curve + AIO discount table."""

    positions: tuple[tuple[float, float], ...]  # ascending (position, ctr)
    aio_by_position: dict[str, float]
    aio_default: float
    aio_fallback_11_20: float
    curve_version: str

    def expected_ctr(self, position: float) -> float:
        """Expected organic CTR at ``position`` (clean SERP).

        Linear interpolation between listed anchor positions; clamps to the
        first/last anchor outside the listed range.
        """
        p = float(position)
        pts = self.positions
        if p <= pts[0][0]:
            return pts[0][1]
        if p >= pts[-1][0]:
            return pts[-1][1]
        for (p0, c0), (p1, c1) in zip(pts, pts[1:]):
            if p0 <= p <= p1:
                if p1 == p0:
                    return c0
                frac = (p - p0) / (p1 - p0)
                return c0 + frac * (c1 - c0)
        return pts[-1][1]  # unreachable (clamped above)

    def aio_factor(self, position: float, aio_presence: str) -> float:
        """Multiplicative CTR discount for an AIO-``present`` target position.

        ``not_detected`` / ``unchecked`` → ``1.0`` (no discount): an
        unproven/unknown AIO is flagged, never penalised (R-140). Factor is
        always in ``(0, 1]``.
        """
        if aio_presence != "present":
            return 1.0
        p = int(round(float(position)))
        if p < 1:
            p = 1
        key = str(p)
        if key in self.aio_by_position:
            return self.aio_by_position[key]
        if p >= 11:
            return self.aio_fallback_11_20
        return self.aio_default


def build_curve(data: Any) -> Curve:
    """Build a :class:`Curve` from a parsed JSON object (pure; no I/O)."""
    if not isinstance(data, dict):
        raise CurveLoadError("ctr-curve payload must be a JSON object")

    raw_positions = data.get("positions")
    if not isinstance(raw_positions, list) or not raw_positions:
        raise CurveLoadError("ctr-curve.positions must be a non-empty array")

    pts: list[tuple[float, float]] = []
    last: float | None = None
    for entry in raw_positions:
        if not isinstance(entry, dict):
            raise CurveLoadError("ctr-curve.positions entries must be objects")
        try:
            pos = float(entry["position"])
            ctr = float(entry["ctr"])
        except (KeyError, TypeError, ValueError) as exc:
            raise CurveLoadError(f"invalid position entry: {entry!r}") from exc
        if not (0.0 < ctr < 1.0):
            raise CurveLoadError(f"ctr out of range (0,1): {ctr}")
        if last is not None and pos <= last:
            raise CurveLoadError("positions must be strictly increasing")
        last = pos
        pts.append((pos, ctr))

    aio = data.get("aio_discount") or {}
    by_position = {
        str(k): float(v) for k, v in (aio.get("by_position") or {}).items()
    }
    default = float(aio.get("default", 0.5))
    fallback = float(aio.get("fallback_11_20", default))
    for label, value in (
        *(("by_position", v) for v in by_position.values()),
        ("default", default),
        ("fallback_11_20", fallback),
    ):
        if not (0.0 < value <= 1.0):
            raise CurveLoadError(f"aio {label} factor out of range (0,1]: {value}")

    version = str(data.get("curve_version") or "").strip()
    if not version:
        raise CurveLoadError("ctr-curve missing curve_version")

    return Curve(
        positions=tuple(pts),
        aio_by_position=by_position,
        aio_default=default,
        aio_fallback_11_20=fallback,
        curve_version=version,
    )


def load_curve(path: Any) -> Curve:
    """Load and validate the curve at ``path`` → :class:`Curve` (DURUR on bad input)."""
    p = Path(path)
    if not p.exists():
        raise CurveLoadError(f"ctr-curve.json not found: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurveLoadError(f"ctr-curve.json unreadable: {p}: {exc}") from exc
    return build_curve(data)


__all__ = ("Curve", "CurveLoadError", "build_curve", "load_curve")
