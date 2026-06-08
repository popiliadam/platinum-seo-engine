# AMO batch 4f — cross-cutting consolidation: ACTIVE_PROJECTS_MAX → ONE module sourced from schema maxItems

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> the engine repo `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note:** spec §8 cross-cutting deliverable — "lift the constant into ONE module sourced from
> schema `maxItems`; kill the copy." `ACTIVE_PROJECTS_MAX = 12` is hand-copied into 4 reporting files (a
> drift hazard — a future cap raise would silently miss a file). This is a BEHAVIOR-PRESERVING refactor: the
> value stays 12 (the schema's `active_projects.maxItems`), every importer's tests stay byte-green, and a new
> guard test forbids the copy from ever returning. QA caliber = equivalence (the constant is byte-identical
> before/after + the reporting outputs unchanged), NOT just "tests pass." No schema/command added → NO D10.
> (This is OPTIONAL hygiene — Süleyman may run it before or after the D11 live acceptance; it doesn't gate D11.)

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE batch: consolidate
the ACTIVE_PROJECTS_MAX constant into ONE module sourced from the schema. Follow every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools (they FAIL here). Work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations. The MANAGER commits after reviewing your REPORT.
3. BASELINE-FIRST. Run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Record what you SEE (>= 2241 + any merged 4c/4d/4e tests). End state: passed >= your baseline + your new
   tests, failed == 0. This is behavior-preserving → NO existing test should need editing; if one does, STOP
   + report WHY (it would mean the refactor changed behavior).
4. TDD / EQUIVALENCE-FIRST. The value MUST stay 12. Write the assertion (ACTIVE_PROJECTS_MAX == 12 == the
   schema's maxItems) + the no-second-definition guard FIRST, watch them drive the change, keep every
   pre-existing reporting test green WITHOUT editing it.
5. SCOPE-LOCK. Modify ONLY the files in SCOPE. Anything else → STOP + report.
6. BEHAVIOR-PRESERVING. Same input → byte-identical output from every reporting script. You are ONLY changing
   WHERE the constant comes from (a literal → an import), never its value or any logic. No other refactor
   rides along.
7. Python discipline: the new module is pure (a module-level constant read once from the schema); anchor the
   repo root the SAME way the reporting scripts do (`Path(__file__).resolve().parents[2]`), NOT
   `CLAUDE_PLUGIN_ROOT` (avoid an installed-plugin copy shadowing the working tree). Fail-LOUD if the schema
   is missing/malformed (it is a committed contract — do not silently default to 12).

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY (spec §8 — ACTIVE_PROJECTS_MAX consolidation)
═══════════════════════════════════════════════════════════════════════════════════════════════
The portfolio cap (12) is the single source of "how many projects the system manages." It is currently a
copy-pasted literal in 4 reporting modules. When the portfolio grows past 12 (10 projects exist today), the
cap will be raised via a schema-first migration — and a copy-pasted literal is exactly the kind of thing a
migration silently misses, leaving reporting modules disagreeing about the cap. Consolidating to ONE module
sourced from the schema's `maxItems` makes the cap have a single home that a schema bump updates everywhere
at once. This is the spec's "lift the constant into ONE module sourced from schema maxItems; kill the copy."

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified — DO grep to find EVERY occurrence yourself before editing)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. The source of truth: `schemas/portfolio-config.schema.json` →
   `properties.active_projects.maxItems` == 12. (Also `schemas/project-memory.schema.json` has a `maxItems:12`
   — that is a DIFFERENT field; do NOT touch it. Source ACTIVE_PROJECTS_MAX from portfolio-config ONLY.)
B. The copies to kill (manager grep `ACTIVE_PROJECTS_MAX\s*=` — but RE-GREP yourself to catch any I missed):
   - `scripts/reporting/portfolio_monthly_roundup.py`
   - `scripts/reporting/portfolio_overview.py`
   - `scripts/reporting/portfolio_heatmap.py`
   - `scripts/reporting/portfolio_kpi_trend.py`
   Also `grep -rn "ACTIVE_PROJECTS_MAX" scripts/` for any module that REFERENCES it (e.g.
   portfolio_task_heatmap.py) and may need the import too. Convert EVERY definition to the import; leave every
   USE site unchanged (the name stays `ACTIVE_PROJECTS_MAX`).
C. House pattern: those reporting modules anchor `_REPO_ROOT = Path(__file__).resolve().parents[2]` and read
   schemas relative to it. Mirror that exactly in the new module. Some already `import json` + read schemas.
D. This is ADDITIVE + behavior-preserving: a new module + a swap of `= 12` → `from ... import
   ACTIVE_PROJECTS_MAX`. No schema/command/manifest change → NO D10. No logic change anywhere.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create/modify
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NEW    `scripts/state/active_projects.py`        (the single home — reads schema maxItems → the constant)
2. NEW    `tests/state/test_active_projects.py`     (value==12==schema + no-second-definition guard)
3. MODIFY each reporting module that DEFINES `ACTIVE_PROJECTS_MAX = 12` → replace the literal with
   `from scripts.state.active_projects import ACTIVE_PROJECTS_MAX` (keep import ordering/style clean).
Nothing else. Do NOT edit the reporting modules' existing tests (they must stay green untouched). If one
goes red, STOP + report (it means the refactor wasn't behavior-preserving).

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC — `scripts/state/active_projects.py`
═══════════════════════════════════════════════════════════════════════════════════════════════
  - Module docstring: "single source of the portfolio cap, sourced from
    schemas/portfolio-config.schema.json#/properties/active_projects/maxItems (spec §8 consolidation)."
  - `_REPO_ROOT = Path(__file__).resolve().parents[2]`.
  - Read the schema once at import; extract `["properties"]["active_projects"]["maxItems"]`; assign
    `ACTIVE_PROJECTS_MAX: int = <that value>`. Raise a clear error at import if the schema is missing or the
    key path is absent (fail-loud — a committed contract must be present; do NOT silently default to 12).
  - Optionally expose `active_projects_max() -> int` returning the same value (a function form some callers
    may prefer) — but the module-level `ACTIVE_PROJECTS_MAX` is the primary API the importers use.
  - Pure: no side effects beyond the one schema read at import; no clock/RNG; functions < 50 lines.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD
═══════════════════════════════════════════════════════════════════════════════════════════════
  • `ACTIVE_PROJECTS_MAX == 12` AND `== schemas/portfolio-config.schema.json
    #/properties/active_projects/maxItems` (read both, assert equal — the value is sourced, not hard-coded).
  • NO-SECOND-DEFINITION guard: grep `scripts/` → the ONLY line matching `^ACTIVE_PROJECTS_MAX\s*=` is in
    `scripts/state/active_projects.py` (every reporting module now IMPORTS it). This guard is what keeps the
    copy from ever returning.
  • import-fail-loud: point the loader at a missing/garbage schema path (a tmp copy / monkeypatch) → it
    RAISES, not silently 12. (If reading happens at import, test via a helper function that re-reads, so the
    test can exercise the failure path without breaking the module import.)
  • Every importer still works: import each modified reporting module + assert it exposes the SAME
    `ACTIVE_PROJECTS_MAX` (== 12) and its existing tests are untouched + green.
  Run RED first (module absent / copies still present), then GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest.
2. `grep -rn "ACTIVE_PROJECTS_MAX" scripts/` — enumerate EVERY definition + use. READ
   `schemas/portfolio-config.schema.json` + one reporting module (e.g. portfolio_overview.py) for the anchor
   pattern.
3. Write the new module + its tests (RED → GREEN). Then swap each definition to the import.
4. FULL suite → passed >= baseline, 0 failed; confirm NO reporting test needed editing (behavior-preserving)
   + NO count guard tripped (no schema/command added).
5. Self-review: value still 12 + sourced from the schema? exactly ONE definition left (guard green)? every
   use site unchanged? fail-loud on a bad schema? no logic touched? no D10?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• A reporting module's existing test goes red (the swap changed behavior — describe it; do NOT edit the test
  to pass).
• An occurrence of ACTIVE_PROJECTS_MAX is used in a way an import can't satisfy (describe it).
• The schema maxItems is NOT 12 / the key path differs from fact A (quote what you found).
• You'd need to edit a schema/command/manifest (you should NOT — if you think you do, STOP + explain).

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE (tail-5).
2. ENUMERATION: the full `grep -rn ACTIVE_PROJECTS_MAX scripts/` before — every definition + use site.
3. NEW MODULE: active_projects.py sources the value from the schema (show value==12==schema) + fails loud on
   a bad schema (the test).
4. NO-SECOND-DEFINITION: the guard test green — exactly ONE `ACTIVE_PROJECTS_MAX =` definition remains.
5. BEHAVIOR-PRESERVING PROOF: confirm ZERO reporting tests were edited + all green (the swap changed only the
   constant's SOURCE, not its value or any logic).
6. NO D10: confirm no schema/command/manifest changed.
7. FULL SUITE: final tail-5 (passed >= baseline, 0 failed, no count guard tripped).
8. ANYTHING you decided or that surprised you.
```
