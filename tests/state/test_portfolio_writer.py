"""tests/state/test_portfolio_writer.py — concurrency + shape contract for the
flock-guarded shared/portfolio.json registrar (AMO batch 0e2).

The registrar replaces the lock-free read-modify-write previously inlined in
skills/meta/init-project/SKILL.md Step 6, which lost updates when two parallel
init-project runs raced (each read the same pre-state, each appended only its
own slug, the second write clobbered the first). These tests prove:

  1. Concurrency — N threads each registering a DISTINCT slug all land (no lost
     update); the file stays valid JSON with exactly N projects. Each call opens
     the file independently, so fcntl.flock(LOCK_EX) conflicts serialize the
     read-modify-write even within one process.
  2. Idempotency — re-registering the same slug is a no-op (dedup on slug;
     first write wins, created_at preserved).
  3. Append-only — registering a new slug preserves prior entries.
  4. Shape — top-level {schema_version, projects[]}, each project the exact four
     keys {slug, domain, market, created_at}, indent=2, trailing newline,
     ensure_ascii=False.

Discipline: tmp_path only — the real workspace is never touched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from scripts.state.portfolio_writer import register_project

REPO_ROOT = Path(__file__).resolve().parents[2]
_CREATED_AT = "2026-06-05T00:00:00.000000Z"


def _read(workspace_root: Path) -> dict:
    return json.loads((workspace_root / "shared" / "portfolio.json").read_text("utf-8"))


def _run_concurrent(workspace_root: Path, slugs: list[str]) -> list[BaseException]:
    """Register every slug from its own thread, released together by a barrier
    to maximize lock contention. Returns any exceptions raised in workers."""
    barrier = threading.Barrier(len(slugs))
    errors: list[BaseException] = []

    def _worker(slug: str) -> None:
        try:
            barrier.wait()  # release all threads into the critical section together
            register_project(
                workspace_root, slug, f"https://{slug}.example/", "TR",
                created_at=_CREATED_AT,
            )
        except Exception as exc:  # surface worker failures for the assert below
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(s,)) for s in slugs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


def test_two_concurrent_threads_both_land(tmp_path: Path) -> None:
    """Two threads register distinct slugs simultaneously; the flock serializes
    the read-modify-write so NEITHER update is lost (the original bug)."""
    errors = _run_concurrent(tmp_path, ["slug-0", "slug-1"])
    assert not errors, f"worker raised: {errors}"

    data = _read(tmp_path)
    assert {p["slug"] for p in data["active_projects"]} == {"slug-0", "slug-1"}, \
        "a concurrent update was lost"
    assert len(data["active_projects"]) == 2


def test_high_contention_no_lost_update(tmp_path: Path) -> None:
    """Ten threads, ten distinct slugs, all hitting the lock at once — every
    one must survive (exactly 10 projects, no duplicates, no losses)."""
    slugs = [f"p-{i}" for i in range(10)]
    errors = _run_concurrent(tmp_path, slugs)
    assert not errors, f"worker raised: {errors}"

    data = _read(tmp_path)
    assert len(data["active_projects"]) == 10, "lost update under contention"
    assert {p["slug"] for p in data["active_projects"]} == set(slugs)


def test_reregister_same_slug_is_idempotent(tmp_path: Path) -> None:
    """Re-registering a slug already present is a no-op: no duplicate, and the
    original entry (incl. created_at) is preserved — first write wins."""
    register_project(tmp_path, "alpha", "https://alpha.example/", "TR",
                     created_at=_CREATED_AT)
    register_project(tmp_path, "alpha", "https://alpha.example/", "TR",
                     created_at="2030-01-01T00:00:00.000000Z")

    data = _read(tmp_path)
    assert len(data["active_projects"]) == 1, "duplicate slug entry created"
    assert data["active_projects"][0]["slug"] == "alpha"
    assert data["active_projects"][0]["created_at"] == _CREATED_AT, "dedup overwrote the original"


def test_append_only_preserves_prior_entries(tmp_path: Path) -> None:
    """A second, distinct slug appends without removing the first."""
    register_project(tmp_path, "alpha", "https://alpha.example/", "TR",
                     created_at=_CREATED_AT)
    register_project(tmp_path, "beta", "https://beta.example/", "NG",
                     created_at=_CREATED_AT)

    data = _read(tmp_path)
    assert [p["slug"] for p in data["active_projects"]] == ["alpha", "beta"]


def test_shape_matches_contract(tmp_path: Path) -> None:
    """The serialized file matches the exact shape readers expect:
    {schema_version, projects[]} of four-key entries, indent=2, trailing \\n."""
    path = register_project(tmp_path, "gamma", "https://gamma.example/", "TR",
                            created_at=_CREATED_AT)
    raw = path.read_text("utf-8")

    assert raw.endswith("\n") and not raw.endswith("\n\n"), \
        "exactly one trailing newline expected"
    assert '\n  "schema_version": "1.0"' in raw, "indent=2 pretty-printing expected"

    data = json.loads(raw)
    assert set(data.keys()) == {"schema_version", "active_projects"}
    assert data["schema_version"] == "1.0"
    assert data["active_projects"][0] == {
        "slug": "gamma",
        "domain": "https://gamma.example/",
        "market": "TR",
        "created_at": _CREATED_AT,
    }


def test_ensure_ascii_false_preserves_unicode(tmp_path: Path) -> None:
    """ensure_ascii=False keeps unicode literal in the file (not \\uXXXX)."""
    path = register_project(tmp_path, "uni", "https://exämple.test/", "TR",
                            created_at=_CREATED_AT)
    raw = path.read_text("utf-8")
    assert "exämple" in raw, "ensure_ascii=False must keep the unicode literal"
    assert "\\u00e4" not in raw


def test_returns_portfolio_path(tmp_path: Path) -> None:
    """register_project returns the concrete portfolio.json path it wrote."""
    returned = register_project(tmp_path, "delta", "https://delta.example/", "TR",
                                created_at=_CREATED_AT)
    assert returned == tmp_path / "shared" / "portfolio.json"
    assert returned.exists()


def test_cli_register_subprocess(tmp_path: Path) -> None:
    """The documented `python3 -m scripts.state.portfolio_writer register ...`
    CLI registers a slug, writes the contract shape, and prints the path."""
    res = subprocess.run(
        [sys.executable, "-m", "scripts.state.portfolio_writer", "register",
         "cli-slug", "--domain", "https://cli.example/", "--market", "TR",
         "--workspace", str(tmp_path), "--created-at", _CREATED_AT],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert res.returncode == 0, f"CLI failed: {res.stderr}"

    data = _read(tmp_path)
    assert data["active_projects"][0] == {
        "slug": "cli-slug",
        "domain": "https://cli.example/",
        "market": "TR",
        "created_at": _CREATED_AT,
    }
    assert str(tmp_path / "shared" / "portfolio.json") in res.stdout
