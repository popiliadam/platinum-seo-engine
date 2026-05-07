"""tests/ci/test_python_version_consistency.py — O-04 + D-05 v1.5-Phase-2
Tier 3 CI Python version + requirements-lock synchronization invariant.

Coverage:
  1. ci.yml matrix python-version array contains both 3.10 (floor) and
     3.14 (current cache evidence) — Süleyman karar 2026-05-07 Karar 1 = A.
  2. ci.yml install step is lock-driven (``pip install -r
     requirements-lock.txt``); the legacy floor-only install
     (``pip install jsonschema pytest openpyxl pyyaml``) is gone.
  3. requirements-lock.txt header carries a concrete Python version
     (``Python: 3.X``) — the placeholder ``Python: 3.x`` is forbidden
     post-D-05 closure.
  4. Every package floor-pinned in requirements.txt is hard-pinned in
     requirements-lock.txt — no floor drift unmoored from the lock.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
REQ_LOCK = REPO / "requirements-lock.txt"
REQ = REPO / "requirements.txt"


def _parse_lock_pkgs() -> set[str]:
    pkgs: set[str] = set()
    for line in REQ_LOCK.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)==", line)
        if m:
            pkgs.add(m.group(1).lower())
    return pkgs


def _parse_floor_pkgs() -> set[str]:
    pkgs: set[str] = set()
    for line in REQ.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if m:
            pkgs.add(m.group(1).lower())
    return pkgs


def test_ci_matrix_dual_python_versions():
    """Matrix MUST cover both 3.10 (floor LTS) and 3.14 (current/local cache)."""
    ci = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))
    versions = ci["jobs"]["ci"]["strategy"]["matrix"]["python-version"]
    assert isinstance(versions, list), "python-version must be a list"
    assert "3.10" in versions, "3.10 floor LTS missing from matrix"
    assert "3.14" in versions, "3.14 current/local cache version missing"


def test_ci_install_uses_lockfile():
    """Install step MUST drive from requirements-lock.txt (D-05)."""
    body = CI_YML.read_text(encoding="utf-8")
    assert "pip install -r requirements-lock.txt" in body, (
        "ci.yml install step must use requirements-lock.txt for reproducibility"
    )
    # Legacy floor install must be gone
    assert "pip install jsonschema pytest openpyxl pyyaml" not in body, (
        "legacy floor-only install must be removed; lock-driven only"
    )


def test_lock_header_specifies_concrete_python():
    """Lock header must specify a concrete Python: X.Y, not the placeholder
    ``Python: 3.x``."""
    head = REQ_LOCK.read_text(encoding="utf-8")
    assert "Python: 3.x" not in head, (
        "lock header still carries placeholder 'Python: 3.x' "
        "(D-05: cache evidence is 3.14)"
    )
    assert re.search(r"Python: \d+\.\d+", head), (
        "lock header must specify a concrete 'Python: X.Y' line"
    )


def test_lock_header_cross_references_matrix():
    """Lock header should cross-reference the CI matrix list so both files
    advance together (drift catch)."""
    head = REQ_LOCK.read_text(encoding="utf-8")
    assert "CI matrix:" in head, (
        "lock header should cite the CI matrix (drift cross-ref)"
    )


def test_lock_pinned_subset_of_requirements_floor():
    """Every package in requirements.txt floor MUST be hard-pinned in lock.
    Floor drift unmoored from the lock breaks reproducibility."""
    floor = _parse_floor_pkgs()
    lock = _parse_lock_pkgs()
    missing = floor - lock
    assert not missing, (
        f"requirements.txt floor packages not pinned in lock: {missing}"
    )
