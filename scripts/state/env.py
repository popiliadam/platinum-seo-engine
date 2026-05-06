"""scripts/state/env.py — workspace root env var resolver (ADR-035).

Canonical env var: ``PSEO_WORKSPACE_ROOT``.
Deprecated alias (1-year shim, removal deadline 2027-05-06): ``PSE_WORKSPACE_PATH``.

Use ``get_workspace_root()`` from new code instead of reading the env var
directly. Existing scripts that already read ``PSEO_WORKSPACE_ROOT`` keep
working as long as the canonical name is set; the alias is a soft
migration aid for users who have not yet updated their ``.env``.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

CANONICAL = "PSEO_WORKSPACE_ROOT"
DEPRECATED_ALIAS = "PSE_WORKSPACE_PATH"
DEPRECATION_DEADLINE = "2027-05-06"  # ADR-035: 1-year shim window from 2026-05-06.


def get_workspace_root() -> Path | None:
    """Return the resolved workspace root path, or ``None`` if unbound.

    Resolution order:
    1. ``PSEO_WORKSPACE_ROOT`` (canonical, ADR-035).
    2. ``PSE_WORKSPACE_PATH`` (deprecated alias, emits a ``DeprecationWarning``;
       removal scheduled ``2027-05-06``).
    """
    raw = os.environ.get(CANONICAL)
    if raw is None:
        legacy = os.environ.get(DEPRECATED_ALIAS)
        if legacy is None:
            return None
        warnings.warn(
            f"{DEPRECATED_ALIAS} is a deprecated alias for {CANONICAL} "
            f"(ADR-035; removal {DEPRECATION_DEADLINE}). "
            f"Update your .env to use {CANONICAL}.",
            DeprecationWarning,
            stacklevel=2,
        )
        raw = legacy
    return Path(os.path.expanduser(raw))
