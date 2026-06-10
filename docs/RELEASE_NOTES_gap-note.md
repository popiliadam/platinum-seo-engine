# Release-Notes Numbering Gap Note — v1.2.0 · v1.9.1 · v1.9.2

> Authored 2026-06-10 (unified-FIX-N hygiene pack). This note exists so the
> `docs/RELEASE_NOTES_*` sequence and the `git tag` list read as complete:
> the three version numbers below have **no release-notes file**, and none of
> them was ever annotated-tagged — so no per-version stub is owed (stubs are
> written from `git log <prev>..<tag>`, which requires a tag to exist).
> Everything below is derived from git history; nothing is reconstructed
> from memory.

## v1.2.0 — never existed (pure numbering jump)

- No commit in repo history ever set `"version": "1.2.0"` in
  `.claude-plugin/plugin.json` (`git log --all -S '"version": "1.2.0"'` →
  no hits), and no `1.2.0` content trace exists in README or manifest
  history (`git log --all -G '1\.2\.0' -- README.md .claude-plugin/` →
  no hits).
- [RELEASE_NOTES_v1.3.0.md](RELEASE_NOTES_v1.3.0.md) names v1.1.0
  (2026-05-06) as the **direct predecessor** of v1.3.0 (2026-05-07,
  `dffd5c1`) and describes the version transition as "plugin.json 1.1.0 →
  1.3.0 bump".
- No rationale for skipping the number is recorded anywhere in history or
  docs. It is recorded here as a numbering jump, not a lost release.

## v1.9.1 + v1.9.2 — real releases, untagged, documented inside v1.9.3

Both shipped as in-repo version bumps on 2026-06-02 and were consolidated
into the v1.9.3 tagged release the same day. Their full release
documentation lives in [RELEASE_NOTES_v1.9.3.md](RELEASE_NOTES_v1.9.3.md)
(sections 1–2), which states: "v1.9.1 + v1.9.2 were committed earlier in the
cycle; v1.9.3 bundles them with the orchestrator + load + smoke work into a
single tagged release".

| Version | Commit | Date | Content |
|---|---|---|---|
| v1.9.1 | `c6c0268` | 2026-06-02 | SF MCP client — MCP Streamable-HTTP transport (live-verified) |
| v1.9.2 | `65c5c52` | 2026-06-02 | SF MCP client — retry-on-busy (transient Spider-busy after load/crawl) |
| v1.9.3 | `ae27ac2` (tag `v1.9.3`) | 2026-06-02 | Consolidating release: transport + retry + 29/29 live-exercise + orchestrator dispatch + resilient load |

## Related context (covered elsewhere; listed for completeness)

- v1.3.0 and v1.4.0 **have** release-notes files but **no git tags**: both
  notes record the decision verbatim — "_no annotated tag — repo PRIVATE,
  Wave 4 deferred Süleyman karar 2026-05-07_". Annotated tagging resumes at
  v1.5.0.
- Every other version in the `docs/RELEASE_NOTES_*` sequence (v1.0.0,
  v1.1.0, v1.5.0 through v2.0.0) has both a notes file and an annotated tag.

> Pinned by `tests/docs/test_fix_n_hygiene.py`. This file deliberately does
> NOT match the `RELEASE_NOTES_v*.md` glob — `tests/ci/test_version_sync.py`
> derives the latest release version from that glob.
