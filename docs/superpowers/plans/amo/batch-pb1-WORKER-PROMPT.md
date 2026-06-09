# Worker Prompt — Batch pb1: Skill Dependency-Graph Consistency Lint (rung 1)

> **Initiative:** Path B follow-on (O4 governance ladder, **rung 1** — the T3 prerequisite). Authority:
> `docs/superpowers/specs/2026-06-09-path-b-general-orchestration-research.md` §2.4, §7 (T3), §8 (rung 1).
> **You are a fresh Opus 4.8 (1M-context) worker.** Build ONLY this batch. Report back to the manager.

## Hard rules (non-negotiable)
- **NO `Task`/`Agent` tools — work INLINE.**
- **Baseline-first:** full suite, record exact `pytest` N at start; end strictly ≥, 0 new fails.
- **TDD:** RED → GREEN → REFACTOR; failing test first, for the right reason.
- **Scope-locked:** only the §Scope files. Out-of-scope → STOP + report.
- **No commit** (manager commits after independent re-derivation).
- **Verify, never assume:** for the two dangling-edge fixes, GREP the real skills to find the correct target — do not guess a rename.

## Why this batch exists
`schemas/skill-frontmatter.schema.json` *promises* (in the `consumes`/`produces` field descriptions) that the skill dependency graph is validated "so glossary-audit can build a directed dependency graph" and "detects orphans". **That validation does not exist** — `skills/governance/glossary-audit/` audits GLOSSARY.md *terms* (`glossary_terms - used_set`), not the skill graph (`produces: []`, no cycle/dangling logic). So all 45 skills declare a dependency graph that **nothing checks**: a probe found **2 dangling `produces` edges** (skill names that don't resolve) and confirmed the `consumes` prerequisite graph is currently **acyclic** but unguarded. This batch builds the missing validator. It is pure Path-A governance value today (catches skill-contract drift) AND the hard prerequisite for any future planner (a planner topo-sorts on a *validated* `consumes` DAG).

## Authoritative semantics (from `schemas/skill-frontmatter.schema.json` — read it first)
- `produces`: array of **downstream SKILL NAMES** (schema pattern `^[a-z][a-z0-9-]*$`). Each entry SHOULD resolve to a real skill dir. → a non-resolving entry is a **dangling edge = a real defect**.
- `consumes`: array of upstream refs, each of the form **`{producer-skill}:{artifact}`** (a directed dependency: "to run me, that producer's artifact must exist first"). In practice the prefix is *usually* a skill but sometimes a concept tag (`rules:`, `templates:`, `per-project:`, `init-portfolio:`) — these are NOT skills. → only treat a `consumes` ref as a graph edge when its prefix **resolves to a real skill**; non-resolving prefixes are ADVISORY (possible typo), not a hard fail.
- `outputs`: array of artifact refs (`master.xlsx#sheet`, `outputs/...`, `events.jsonl`). Advisory cross-reference only for this batch.

## Pre-verified ground truth (re-derive it yourself with `yaml.safe_load`; do not trust these blindly)
- **Dangling `produces` (FAIL, fix to green):** exactly 2 today — `content-decay → content-improve` and `master-task-sync → dashboard-refresh`. Investigate each: grep `skills/**` for the intended target (e.g. is `content-improve` a rename of an existing skill like `content-remediation`? is `dashboard-refresh` a real downstream?). **Fix by repointing to the correct existing skill name, or removing the stale edge** — whichever the evidence supports. Document your reasoning per edge.
- **`consumes` prerequisite graph (FAIL-guard, currently GREEN):** building edges `producer → consumer` for every `consumes` ref whose prefix resolves to a skill yields **~111 edges and is ACYCLIC**. Your cycle check must return `[]` on the real tree (a GREEN guard that catches a FUTURE cycle).
- **`produces` graph HAS cycles by design** (`portfolio-overview ↔ portfolio-weekly-brief`, `generate-images ↔ new-blog`, …) and is **77% asymmetric** vs `consumes`. This is EXPECTED (the two fields are different relations, schema-confirmed) → **REPORT it, never FAIL on it.**

## What to build
### `scripts/validation/skill_graph_consistency.py` (NEW — mirror `skill_mcp_usage.py` exactly)
- Pure / no side effects; anchor `ROOT = Path(__file__).resolve().parents[2]` (**NOT `CLAUDE_PLUGIN_ROOT`** — the 0c bare-CLI lesson: an installed copy must never shadow the working tree).
- Reuse `scripts.validation.skill_mcp_usage.split_frontmatter_body` for the FM/body split, then parse the frontmatter with **`yaml.safe_load`** (PyYAML is a declared dep — `requirements.txt:4` `pyyaml>=6.0`; this is the first `scripts/` use, which is fine). A malformed/empty frontmatter → treat as "no declarations" (a real gap, never a crash), matching the sibling's philosophy.
- Discover skills with `sorted(ROOT.glob("skills/**/SKILL.md"))`; a skill's identity is its frontmatter `name` (fall back to the dir name).
- Functions (names indicative; match the sibling style):
  - `parse_graph(root) -> {skill: {"produces":[...], "consumes":[...], "outputs":[...]}}`.
  - `dangling_produces_for(skill_path) -> set[str]` — produces entries that don't resolve to a real skill name. **(the per-skill FAIL unit)**
  - `consumes_edges(root) -> list[(producer, consumer)]` — only refs whose prefix resolves to a skill.
  - `consumes_cycles(root) -> list[list[str]]` — cycles in the consumes prerequisite graph (DFS colour-walk). **(the graph-level FAIL unit; `[]` today)**
  - `graph_health(root) -> dict` — ADVISORY metrics: `{asymmetry_pct, produces_cycles, orphan_consumed_artifacts, unrecognised_consume_prefixes}`. **Never asserted as pass/fail** — it is the governance dashboard the schema's "directed dependency graph" promise refers to.
- Keep it < ~200 lines, single concern, well-docstringed (explain WHY produces-cycles are advisory but consumes-cycles fail — cite the schema semantics).

### `tests/schemas/test_skill_graph_consistency.py` (NEW — mirror `test_skill_body_mcp_subset_declared.py`)
- **Per-skill parametrized** (`ids=` = skill relpath, so a regression names the offending skill): `dangling_produces_for(skill) == set()`. RED first (2 skills fail), GREEN after your 2 fixes.
- **Graph-level:** `consumes_cycles(ROOT) == []` (FAIL on any cycle).
- **TEETH (prove the lint actually catches defects):** construct a tiny synthetic skill tree in `tmp_path` (2–3 fake `SKILL.md` files) with (a) a dangling `produces` and (b) a `consumes` cycle → assert both are detected. Without this, a no-op lint would pass vacuously.
- **Health smoke test:** `graph_health(ROOT)` returns the expected keys and `produces_cycles` is non-empty (today's reality) — asserts the dashboard runs, NOT specific values (so it doesn't become brittle).

### The 2 dangling fixes (≤2 SKILL.md frontmatter edits)
- Edit only the `produces:` list of `content-decay` and `master-task-sync` (repoint or remove, per your grep evidence). Frontmatter-only, behaviour-preserving. If the correct target is genuinely ambiguous, **DURUR and report** rather than guess.

## Scope (touch ONLY these)
- NEW `scripts/validation/skill_graph_consistency.py`
- NEW `tests/schemas/test_skill_graph_consistency.py`
- ≤2 SKILL.md `produces` edits: `skills/**/content-decay/SKILL.md`, `skills/**/master-task-sync/SKILL.md`
- **No** schema/command/MCP/manifest change → **no D10**. Do **not** edit `skill-frontmatter.schema.json`, `glossary-audit`, or the drift-check F-rule set (a future batch may wire an F-rule; not this one).

## DONE when
- Full suite ≥ baseline, 0 new fails; per-skill dangling test GREEN (after the 2 fixes); `consumes_cycles == []` GREEN; the teeth test proves both defect classes are caught; the health smoke test passes.
- The module is pure, `parents[2]`-anchored, reuses `split_frontmatter_body`, uses `yaml.safe_load`.
- `produces`-cycles and asymmetry are REPORTED by `graph_health`, never failed.

## DURUR (stop + report) if
- The real-tree `consumes_cycles(ROOT)` is NOT `[]` (a cycle exists you didn't expect) → STOP, report the cycle; do not "fix" it by deleting an edge without manager sign-off.
- A dangling `produces` target is genuinely ambiguous (you cannot tell from the skills whether to repoint or remove) → STOP, report the candidates.
- Making the per-skill test green would require an allowlist that suppresses a *real* dangling edge (no skill-name suppression — same rule as the 3a lint).
- You find an EXISTING module already validates this graph (re-grep `scripts/` + `glossary-audit` — if reality differs from this prompt, STOP and report; do not duplicate).

## Report back (to the manager)
- Exact baseline N and final N.
- The full module + test diff; the 2 frontmatter fixes with the grep evidence for each repoint/removal decision.
- `graph_health(ROOT)` output (asymmetry %, produces-cycle list, orphan artifacts, unrecognised consume prefixes) — the governance snapshot.
- Confirm: `consumes_cycles == []` on the real tree; teeth test fires on synthetic defects; no schema/command/D10 touched; `parents[2]` anchor; PyYAML use noted.
