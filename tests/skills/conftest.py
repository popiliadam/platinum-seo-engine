"""Make repo root importable for `from scripts.* import ...` in skill tests.

Mirrors tests/scripts/conftest.py — PEP 420 namespace bootstrap so the
test suite can run from any cwd.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
