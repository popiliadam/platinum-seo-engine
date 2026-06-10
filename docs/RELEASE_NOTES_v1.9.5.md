# Release Notes — v1.9.5

**Date:** 2026-06-03 · **Type:** Patch (quality / correctness — no new features, no breaking changes)

## Summary

v1.9.5 closes a full cross-repo audit (`AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`, Codex, 2026-06-03; archived 2026-06-10 at `docs/audits/2026-06-03_codex_cross_repo_audit_handoff.md`):
**30 of 31 findings fixed, 1 refuted (P2-08)**. The release is a governance/correctness hardening
pass — it makes validators, registries, commands, hooks, schemas, docs, and workspace state agree on
the same contracts, and locks each contract with a regression test so the same drift cannot silently
return.

- Test suite: **1449 → 1560** (+111 regression/lock tests), 8 skipped, **zero regressions**.
- No feature changes; no breaking changes. Engine runtime behavior of `validate_invariants` (drift-check
  verdicts) is byte-unchanged — the governance fix corrected the *registry/docs* to match the implementation.

## Fixed by area

**Governance authority**
- P0-01 — `cross-sheet-invariants.json` rewritten to match `validate_invariants.py` (the runtime truth) for
  ~13 colliding F-IDs; original design rules preserved in a new `deferred_design_rules` block; added a
  semantic-binding test (registry rule text + severity must equal the implementation) that also fixes the
  helper-indirection blind spot which had hidden an F-04 CRITICAL/HIGH severity drift.
- P0-03 — MCP registry `dataforseo` version_lock synced 2.8.9 → 2.8.10; missing skill-referenced DataForSEO
  tools added (33 → 47); `ScraplingServer`↔`scrapling` alias formalized + tested.
- P1-13 — Higgsfield represented as an explicit `external_user_dependencies` entry (user-level MCP, not a
  plugin server) + generate-images preflight note.

**Workspace contract**
- P0-02 — `dump_workspace.py` reads the canonical `active_project` key (legacy `slug` fallback + warning).
- P0-04 — `portfolio-config.schema.json` `active_projects` cap raised 8 → 12 (documented soft cap); all 8
  stale project configs migrated 1.3/1.4 → 1.5 with verified zero data loss.
- P2-05 — config schema_version vs engine-release version distinction documented.

**Commands & hook UX**
- P0-05 — all shell programs used in command bodies now declared in `allowed-tools` (7 commands).
- P0-06 — `/pseo-sf-crawl` corrected to the real `sf_import.py` contract (dropped the invalid
  `--source-run-id`; fixed `save_report`; completed the SF MCP tool list).
- P1-05 — hooks reference the existing `/pseo-init` (was the nonexistent `/pseo-bootstrap-project`).
- P1-08 — slug passed to inline Python via env var + regex-validated (no source interpolation/injection).
- P1-14 — corrected schema-file references + `source.kind` enum token (`sf_export` → `sf_csv`).

**Schema hardening**
- P1-01 — JSON-Schema Draft 7 locked across docs/schemas/validator by test.
- P1-02 — `format` (uri/date-time/date) now enforced via an inline `FormatChecker` (no new dependency).
- P1-03 — high-risk `project-config.schema.json` nested objects closed (`additionalProperties:false`) to
  reject typos, without breaking any live config.
- P1-04 — event-schema conditionals require `event_kind` (a missing-kind event now yields one clean error);
  description corrected to four kinds.

**State / write & audit**
- P1-06 — PostToolUse classifies Bash audit actions via `normalize_audit_action` (rm/cp/redirect no longer
  logged as mere "accessed"); audit-emit failures surfaced instead of silently swallowed.
- P1-07 — PreToolUse Excel owner-lock covers quoted/spaced/`~` paths.
- P1-09 — Excel transactions honor the schema `header_row` and reject unknown row keys by default
  (`allow_extra` opt-in).
- P1-10 — workflow `pause` reason / `approve` notes persisted; `retry` preserves prior terminal timing.
- P1-11 — event `run_id` allocated under the append lock (race-free).

**Docs / skills / templates / cleanup**
- P1-12, P2-01, P2-02, P2-03, P2-04, P2-06, P2-07, P3-01, P3-02, P3-03 — brand-onboarding refs/year/banner;
  workspace docs aligned; stale counts corrected and locked by a count-consistency test (skills 45,
  invariants 31); template-dialect manifest; requirements/lock reconciled (phantom `requests` removed);
  hook-script CI-vs-runtime documented; secret-policy wording clarified; historical SF docs labeled.

## Refuted

- P2-08 — all 10 project configs are git-tracked; only runtime outputs are untracked. Not a defect.

## Deferred (principled)

- P1-09(c) — writer-registry enforcement on mutation remains advisory (spec Risk R6 reserves enforcement
  for v2.0; enforcing now would contradict a published contract).

## Notes

Remediation record (roadmap, manager/worker system, per-phase briefs, closeout) lives under
`docs/superpowers/plans/codex-audit/`.
