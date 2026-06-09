"""scripts/release/version_bump.py — Y-05 ADR-036 5-file version sync.

Bumps the engine version across the 5 files that ADR-036 declares as
authoritative for plugin discovery + installer-banner trust:

  1. .claude-plugin/plugin.json         (top-level "version")
  2. .claude-plugin/marketplace.json    (metadata.version
                                         + plugins[0].description "v<semver> — " prefix)
  3. README.md                          ("> Status: **v<semver>**" banner;
                                         unified with INSTALL.md after v1.6
                                         Phase-1.5b — see test_version_sync.py)
  4. docs/INSTALL.md                    ("> Status: **v<semver>**" blockquote banner)
  5. docs/RELEASE_NOTES_v<semver>.md    (existence check; WARN if missing,
                                         NEVER auto-create — manual authoring required)

Default mode is dry-run; ``--apply`` is the opt-in for actual writes. The
RELEASE_NOTES file is never created — its body is product information that
automation cannot synthesize.

Usage::

    python3 scripts/release/version_bump.py --to 1.5.0            # dry-run
    python3 scripts/release/version_bump.py --to 1.5.0 --apply    # write

Authority: ADR-036 (DECISIONS.md), tests/ci/test_version_sync.py (runtime invariant).
Brief: docs/superpowers/plans/v1.5-audit-closure-brief.md Phase 3 Tier 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[2]

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$")

README_BANNER_RE = re.compile(
    # Unified with INSTALL_BANNER_RE after v1.6 Phase-1.5b — the README
    # banner was rewritten to the blockquote+inline-bold form
    # ("> Status: **v<semver>** — ...") and tests/ci/test_version_sync.py
    # exercises BOTH files with the same regex. Y-05 must do the same.
    r"(Status:\s+\*\*v)\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?(\*\*)"
)

INSTALL_BANNER_RE = re.compile(
    r"(Status:\s+\*\*v)\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?(\*\*)"
)

MARKETPLACE_DESC_PREFIX_RE = re.compile(
    r"^v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?\s+—\s+"
)

# Version-keyed RELEASE_NOTES link, e.g. docs/RELEASE_NOTES_v1.5.0.md (F12). A
# banner bump alone left these pointing at the previous release.
RELEASE_NOTES_LINK_RE = re.compile(
    r"RELEASE_NOTES_v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?\.md"
)


def _validate_semver(version: str) -> None:
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(
            f"target version is not a valid semver MAJOR.MINOR.PATCH[-PRE]: "
            f"{version!r}"
        )


def _bump_plugin_json(
    path: Path, target: str, apply: bool
) -> Tuple[str, str] | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data.get("version", "")
    if old == target:
        return None
    if apply:
        data["version"] = target
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return (old, target)


def _bump_marketplace_json(
    path: Path, target: str, apply: bool
) -> List[Tuple[str, str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    changes: List[Tuple[str, str, str]] = []

    old_meta = data.get("metadata", {}).get("version", "")
    if old_meta != target:
        changes.append(("metadata.version", old_meta, target))
        if apply:
            data["metadata"]["version"] = target

    plugins = data.get("plugins", [])
    if plugins:
        old_desc = plugins[0].get("description", "")
        m = MARKETPLACE_DESC_PREFIX_RE.match(old_desc)
        if m:
            new_desc = MARKETPLACE_DESC_PREFIX_RE.sub(
                f"v{target} — ", old_desc, count=1
            )
            if old_desc != new_desc:
                changes.append(
                    (
                        "plugins[0].description",
                        m.group(0).rstrip(),
                        f"v{target} —",
                    )
                )
                if apply:
                    data["plugins"][0]["description"] = new_desc

    if apply and changes:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changes


def _bump_readme_banner(
    path: Path, target: str, apply: bool
) -> Tuple[str, str] | None:
    """README banner bump — unified with INSTALL handler.

    Both README and INSTALL carry the ``> Status: **v<semver>**`` banner
    after v1.6 Phase-1.5b unification. The regex captures the prefix in
    group(1) and the trailing ``**`` in group(2); replace mid-section with
    the target semver and keep both groups intact.
    """
    text = path.read_text(encoding="utf-8")
    m = README_BANNER_RE.search(text)
    if m is None:
        return None
    old = m.group(0)
    new = f"{m.group(1)}{target}{m.group(2)}"
    if old == new:
        return None
    if apply:
        new_text = README_BANNER_RE.sub(rf"\g<1>{target}\g<2>", text, count=1)
        path.write_text(new_text, encoding="utf-8")
    return (old, new)


def _bump_install_banner(
    path: Path, target: str, apply: bool
) -> Tuple[str, str] | None:
    text = path.read_text(encoding="utf-8")
    m = INSTALL_BANNER_RE.search(text)
    if m is None:
        return None
    old = m.group(0)
    new = f"{m.group(1)}{target}{m.group(2)}"
    if old == new:
        return None
    if apply:
        new_text = INSTALL_BANNER_RE.sub(rf"\g<1>{target}\g<2>", text, count=1)
        path.write_text(new_text, encoding="utf-8")
    return (old, new)


def _bump_release_notes_links(
    path: Path, target: str, apply: bool
) -> List[Tuple[str, str]]:
    """Bump every version-keyed RELEASE_NOTES link in ``path`` to the target (F12).

    A banner bump alone left links like ``docs/RELEASE_NOTES_v1.4.0.md`` pointing at
    the previous release. Rewrites every ``RELEASE_NOTES_v<semver>.md`` reference to
    ``RELEASE_NOTES_v<target>.md``; returns the (old, new) deltas (deduped,
    order-preserving). No-op (``[]``) on a file with no such link or links already
    on target.
    """
    text = path.read_text(encoding="utf-8")
    target_ref = f"RELEASE_NOTES_v{target}.md"
    stale = [
        m.group(0)
        for m in RELEASE_NOTES_LINK_RE.finditer(text)
        if m.group(0) != target_ref
    ]
    if not stale:
        return []
    if apply:
        path.write_text(
            RELEASE_NOTES_LINK_RE.sub(target_ref, text), encoding="utf-8"
        )
    return [(old, target_ref) for old in dict.fromkeys(stale)]


def check_release_consistency(
    repo_root: Path = REPO_ROOT_DEFAULT, target_version: str = ""
) -> List[str]:
    """READ-ONLY audit (F12): every managed version surface that does NOT agree with
    ``target_version``. A clean post-apply state returns ``[]``; any entry means a
    bump LEFT a stale version surface or a stale RELEASE_NOTES link.

    Surfaces: plugin.json version, marketplace metadata.version + plugins[0]
    description ``v<target> —`` prefix, README + INSTALL ``Status: **v<target>**``
    banners, and every ``RELEASE_NOTES_v<semver>.md`` link in README + INSTALL. The
    target RELEASE_NOTES FILE's existence is NOT a consistency error (that stays an
    authoring WARNING in :func:`bump`).
    """
    repo_root = Path(repo_root)
    problems: List[str] = []

    plugin_json = repo_root / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        v = json.loads(plugin_json.read_text(encoding="utf-8")).get("version", "")
        if v != target_version:
            problems.append(
                f".claude-plugin/plugin.json version {v!r} != target {target_version!r}"
            )

    mkt = repo_root / ".claude-plugin" / "marketplace.json"
    if mkt.exists():
        data = json.loads(mkt.read_text(encoding="utf-8"))
        meta_v = data.get("metadata", {}).get("version", "")
        if meta_v != target_version:
            problems.append(
                f".claude-plugin/marketplace.json metadata.version {meta_v!r} != "
                f"target {target_version!r}"
            )
        plugins = data.get("plugins", [])
        if plugins:
            desc = plugins[0].get("description", "")
            if not desc.startswith(f"v{target_version} —"):
                problems.append(
                    "marketplace.json plugins[0].description prefix is not "
                    f"'v{target_version} —': {desc[:32]!r}"
                )

    for rel, path, banner_re in (
        ("README.md", repo_root / "README.md", README_BANNER_RE),
        ("docs/INSTALL.md", repo_root / "docs" / "INSTALL.md", INSTALL_BANNER_RE),
    ):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        m = banner_re.search(text)
        if m is not None:
            found = re.search(r"v(\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?)", m.group(0))
            if found and found.group(1) != target_version:
                problems.append(
                    f"{rel} Status banner v{found.group(1)} != target v{target_version}"
                )
        for link in RELEASE_NOTES_LINK_RE.finditer(text):
            if link.group(0) != f"RELEASE_NOTES_v{target_version}.md":
                problems.append(
                    f"{rel} stale release link {link.group(0)} != "
                    f"RELEASE_NOTES_v{target_version}.md"
                )
    return problems


def bump(
    target_version: str,
    repo_root: Path = REPO_ROOT_DEFAULT,
    apply: bool = False,
) -> dict:
    _validate_semver(target_version)

    repo_root = Path(repo_root)
    changes: List[Tuple[str, str, str]] = []
    warnings: List[str] = []

    plugin_json = repo_root / ".claude-plugin" / "plugin.json"
    if plugin_json.exists():
        delta = _bump_plugin_json(plugin_json, target_version, apply)
        if delta is not None:
            changes.append((".claude-plugin/plugin.json", delta[0], delta[1]))
    else:
        warnings.append(f"plugin.json not found at {plugin_json}")

    mkt_json = repo_root / ".claude-plugin" / "marketplace.json"
    if mkt_json.exists():
        for subpath, old, new in _bump_marketplace_json(
            mkt_json, target_version, apply
        ):
            changes.append(
                (f".claude-plugin/marketplace.json::{subpath}", old, new)
            )
    else:
        warnings.append(f"marketplace.json not found at {mkt_json}")

    readme = repo_root / "README.md"
    if readme.exists():
        delta = _bump_readme_banner(readme, target_version, apply)
        if delta is not None:
            changes.append(("README.md", delta[0], delta[1]))
        for old, new in _bump_release_notes_links(readme, target_version, apply):
            changes.append(("README.md::release_notes_link", old, new))
    else:
        warnings.append(f"README.md not found at {readme}")

    install = repo_root / "docs" / "INSTALL.md"
    if install.exists():
        delta = _bump_install_banner(install, target_version, apply)
        if delta is not None:
            changes.append(("docs/INSTALL.md", delta[0], delta[1]))
        for old, new in _bump_release_notes_links(install, target_version, apply):
            changes.append(("docs/INSTALL.md::release_notes_link", old, new))
    else:
        warnings.append(f"docs/INSTALL.md not found at {install}")

    release_notes = repo_root / "docs" / f"RELEASE_NOTES_v{target_version}.md"
    if not release_notes.exists():
        warnings.append(
            f"docs/RELEASE_NOTES_v{target_version}.md missing — manual "
            "authoring required (no auto-create per ADR-036 / brief Phase 3 "
            "Tier 1 step 2.5)."
        )

    return {
        "applied": apply and bool(changes),
        "changes": changes,
        "warnings": warnings,
        # F12: post-state audit — on --apply this must be empty (no stale surface
        # left); on dry-run it reflects the current pre-bump drift vs target.
        "consistency": check_release_consistency(repo_root, target_version),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="version_bump.py",
        description="Bump version across the ADR-036 5-file sync set.",
    )
    parser.add_argument(
        "--to",
        required=True,
        dest="target",
        help="Target semver (MAJOR.MINOR.PATCH[-PRE])",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply writes (default: dry-run; safer)",
    )
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT_DEFAULT),
        help="Repository root (default: auto-detected from script path)",
    )
    args = parser.parse_args(argv)

    try:
        result = bump(
            target_version=args.target,
            repo_root=Path(args.repo_root),
            apply=args.apply,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] target version: v{args.target}")
    print(f"[{mode}] {len(result['changes'])} change(s) proposed:")
    for path, old, new in result["changes"]:
        print(f"  - {path}: {old!r} -> {new!r}")
    if result["warnings"]:
        print(f"[{mode}] {len(result['warnings'])} warning(s):", file=sys.stderr)
        for w in result["warnings"]:
            print(f"  ! {w}", file=sys.stderr)
    if not args.apply:
        print(f"[{mode}] no files written (use --apply to commit).")
        return 0

    # F12: an --apply must not LEAVE a stale version surface / release link.
    consistency = result.get("consistency", [])
    if consistency:
        print(
            f"[{mode}] FAILED: apply left {len(consistency)} stale version "
            "surface(s) — fix before release:",
            file=sys.stderr,
        )
        for c in consistency:
            print(f"  ✗ {c}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
