"""tests/ci/test_requirements_lock.py — P2-04 requirements/lock drift guard.

requirements.txt declares the DIRECT engine deps; requirements-lock.txt pins
the resolved versions CI installs (.github/workflows/ci.yml). These tests keep
the two — and the codebase — in agreement:

  * every direct dep is actually pinned in the lock;
  * `requests` is pinned IFF a real engine module imports it (it does not —
    the only `import requests` lives in a dfs-pull SKILL.md *snippet*; the
    engine HTTP client is httpx). This stops a bare `pip freeze` from leaking
    an unrelated global back into the lock;
  * the lock header documents the regeneration command + Python target.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REQUIREMENTS = _REPO_ROOT / "requirements.txt"
_LOCK = _REPO_ROOT / "requirements-lock.txt"


def _normalize(name: str) -> str:
    """PEP 503-style name normalization (case + separator folding)."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def _requirement_names(path: Path, sep_pattern: str) -> set[str]:
    names: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(sep_pattern, line)
        if m:
            names.add(_normalize(m.group(1)))
    return names


def _base_requirements() -> set[str]:
    # e.g. "httpx>=0.27,<1.0" -> "httpx"
    return _requirement_names(_REQUIREMENTS, r"^([A-Za-z0-9_.-]+)")


def _lock_packages() -> set[str]:
    # e.g. "httpx==0.28.1" -> "httpx"
    return _requirement_names(_LOCK, r"^([A-Za-z0-9_.-]+)==")


def _engine_imports_requests() -> bool:
    pattern = re.compile(r"^\s*(import requests|from requests)", re.M)
    for py in (_REPO_ROOT / "scripts").rglob("*.py"):
        if pattern.search(py.read_text(encoding="utf-8")):
            return True
    return False


def test_every_base_requirement_is_pinned_in_lock() -> None:
    """Every direct dep in requirements.txt must have a pin in the lock CI
    installs, else a fresh dep ships unpinned."""
    missing = _base_requirements() - _lock_packages()
    assert not missing, (
        f"requirements.txt deps not pinned in requirements-lock.txt: "
        f"{sorted(missing)}"
    )


def test_requests_pinned_iff_a_real_engine_module_imports_it() -> None:
    """P2-04: `requests` may only be pinned if a real engine .py imports it.
    Today none do (the engine uses httpx); the SKILL.md snippet is
    illustrative, not executed."""
    locked = "requests" in _lock_packages()
    imported = _engine_imports_requests()
    assert locked == imported, (
        "requirements-lock.txt pins `requests` but no engine .py imports it "
        "(only the dfs-pull SKILL.md snippet does; the engine uses httpx) — "
        "drop it from the lock."
        if locked and not imported else
        "an engine module imports `requests` but it is not pinned in "
        "requirements-lock.txt (and likely absent from requirements.txt too) "
        "— add it to both."
    )


def test_lock_documents_generation_command_and_python_target() -> None:
    """The lock header must document the Python target + a clean-venv
    regeneration command (a bare `pip freeze` is what leaked the phantom
    `requests`) + its relationship to requirements.txt."""
    header = "\n".join(
        line for line in _LOCK.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    )
    assert "3.14" in header, "Python target not documented in lock header"
    assert "venv" in header, (
        "clean-venv regeneration command not documented — a bare pip freeze "
        "re-introduces phantom global packages"
    )
    assert "requirements.txt" in header, (
        "lock <- requirements.txt relationship not documented"
    )
