"""Repo-root pytest configuration.

Excludes ``.claude/`` runtime artefacts (worktrees, plugin cache, agent state)
from pytest collection. These directories may contain test-pattern strings —
drift detectors, template refs, README banner regexes — that would false-
positive the forbidden-bare-alias, explicit-template-refs, and other repo-
hygiene gates if walked by collectors.

The ``.claude/`` directory is not (yet) in ``.gitignore`` but is operator-
owned local state. Keep this ignore narrow: pytest skips collection only;
``.claude/`` files remain visible to the rest of the toolchain.
"""

from __future__ import annotations

collect_ignore_glob = [".claude/*"]
