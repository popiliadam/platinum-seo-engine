# AMO Batch 3-gov-driftF — F-27 drift rule: declared OUTWARD MCP tool ⊆ 2b gate matcher (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 3, governance batch 1 of 3 (manager SPLIT 3-gov → driftF + secret-bytes
> + lint#2, distinct subsystems). HEAD `baf53cf`, suite **2127 / 0**. This adds the Faz-2-carried drift rule: a new
> drift-check F-rule (F-27, `csr_mcp`) that FAILS if a skill declares an OUTWARD MCP tool the 2b outward-action gate
> doesn't cover — closing the "ungated outward action" hole the spec §7-2b flagged. **Focused, single-concern**
> (one F-rule + its 4-way registration + a test). Reuses 3a's `skill_mcp_usage` + the 2b gate constant. Sized for a
> max-effort Opus-4.8 1M worker. Paste the fenced block into a fresh Claude Code session at the engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3-gov-driftF of the AMO initiative, managed
from another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2127 at HEAD baf53cf; a single MCP-availability-gated test may
  make it read 2126/8 — the floor is the passed+skipped TOTAL, which must not drop) BEFORE any change. END green
  with passed strictly >= your measured N and 0 failed. EVERY existing test MUST stay green — especially
  tests/schemas/test_cross_sheet_invariants_sync.py (the 4-way sync enforcer) and the tests/scripts/test_validate_invariants_*.py cluster.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (build new objects, never mutate inputs); no leftover debug prints; small functions
  (<50 lines); files stay reasonable; clear names; no hardcoded secrets.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
Batch 2b/2f shipped the outward-action consent gate (scripts/hooks/outward_action_gate.py): it DENIES an
irreversible/outward action (git push, rm, curl POST, the GSC sitemap-submit MCP tool, the Indexing-API host)
unless the session consented. The gate's ONLY gated MCP tool is `mcp__gsc__submit_sitemap` (its
`_MCP_SUBMIT_TOOL` constant). Spec §7-2b flagged a drift risk: "a drift F-rule fails if a skill declares an
outward MCP tool not covered by a gate matcher." If someone later adds a skill that declares a NEW outward MCP
tool (a future indexing `URL_UPDATED` submit, a publish tool, …) WITHOUT adding a matching gate matcher, that
outward action ships UNGATED — a silent hole in the consent wall (Süleyman's Indexing hard-constraint). This
batch adds that drift rule as a new drift-check F-rule, F-27 (category `csr_mcp`), so CI catches the hole.

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):
- The drift-check F-rule framework lives in scripts/validation/validate_invariants.py. Rules are functions
  `def check_F_NN(workbook, project_slug, *, workspace_root=None, **_) -> dict` that build a result via the
  module's `_make_result(id_=, severity=, verdict=, evidence=, rule=, category=, sample_violations=, affected_rows=)`.
  Verdicts are "PASS" | "FAIL" | "SKIP". Highest existing rule = F-26.
- F-24 is your TEMPLATE — an ENGINE-self-governance, "sets-comparison" rule (category `csr_mcp`). It ignores the
  workbook + workspace_root, reads engine repo-root files (`_REPO_ROOT / ".mcp.json"`, `_REPO_ROOT /
  "mcp-tool-registry.json"`), normalizes, diffs two sets, and FAILs (HIGH) on any orphan. Read it IN FULL
  (~lines 1050-1125) and mirror its shape: rule-string + SKIP-on-missing + FAIL-on-unparseable + FAIL-on-set-delta
  + PASS. `_REPO_ROOT = Path(__file__).resolve().parents[2]` (tests patch this / use a tmp tree — see ORIENT).
- The 4-WAY REGISTRATION a new F-rule needs (the sync test enforces it — do ALL four or it goes red):
  1. The `check_F_27` function (in validate_invariants.py).
  2. Add `check_F_27` to the `_RULE_FUNCTIONS` tuple (~line 1680; it currently ends at check_F_26). Place it with
     the HIGH-severity rules (next to check_F_23/24/25, the other csr_mcp engine rules).
  3. Add `"check_F_27"` to the `__all__` list (~line 1910).
  4. Add an F-27 entry to schemas/cross-sheet-invariants.json `rules` array (31 entries today, last id F-26).
     Entry keys MIRROR F-24's: {id:"F-27", rule:"<the rule string, verbatim equal to the function's `rule`>",
     severity:"HIGH", category:"csr_mcp", rationale:"<why>", computed_by:"check_F_27"}.
  `tests/schemas/test_cross_sheet_invariants_sync.py` asserts the cross-sheet-invariants.json rule ids ↔ the
  check_F_* functions stay in sync (+ likely that each rule's `rule` text matches). So (1)+(2)+(3)+(4) must agree.
- The category `csr_mcp` is a VALID enum value (schemas/consistency-report.schema.json `category` enum: csr_foundation,
  csr_data, csr_mcp, …) — F-23/F-24/F-25 already use it. No schema-enum change needed.
- The 2b gate's outward-MCP matcher set (the source of truth for "what's gated"): scripts/hooks/outward_action_gate.py
  defines `_MCP_SUBMIT_TOOL = "mcp__gsc__submit_sitemap"` and `classify(tool_name, tool_input)` returns
  `("mcp_submit", …)` ONLY for that tool. So the gate's gated-MCP-tool set = `{ "mcp__gsc__submit_sitemap" }`.
  IMPORT the constant (`from scripts.hooks.outward_action_gate import _MCP_SUBMIT_TOOL`) so the rule can NEVER
  drift from the gate. (All the gate's OTHER outward actions are Bash — git push / rm / curl POST — NOT MCP
  tools, so they are out of scope for "declared MCP tool ⊆ gate matcher".)
- Enumerate skills' DECLARED MCP tools by REUSING batch 3a's module:
  `from scripts.validation.skill_mcp_usage import split_frontmatter_body, declared_tools`. `declared_tools(fm)`
  returns the registry-key set (e.g. `gsc__submit_sitemap`, alias-normalized, higgsfield excluded) from a
  skill's `mcp_tools` frontmatter. The 47 skills live at skills/**/SKILL.md. NOTE the FORM mismatch: declared
  tools come back as REGISTRY keys (`gsc__submit_sitemap`); the gate constant is the QUALIFIED form
  (`mcp__gsc__submit_sitemap`). Normalize to ONE form before comparing (e.g. strip the `mcp__` prefix off the
  gate constant → `gsc__submit_sitemap`).
- `_make_result` also accepts `sample_violations` (list[str], ≤20) + `affected_rows` (int) — use them to list the
  offending (skill, tool) pairs on FAIL, like F-24 lists orphans.

ORIENT FIRST (read, do not change yet):
- scripts/validation/validate_invariants.py — check_F_24 IN FULL (template) + check_F_23/F-25 (the other csr_mcp
  engine rules) + `_make_result` signature + the `_RULE_FUNCTIONS` tuple + `__all__` + `_REPO_ROOT`.
- scripts/hooks/outward_action_gate.py — `_MCP_SUBMIT_TOOL` + `classify` (confirm it is the ONLY gated MCP tool).
- scripts/validation/skill_mcp_usage.py — `split_frontmatter_body` + `declared_tools` (batch 3a; the parser you reuse).
- schemas/cross-sheet-invariants.json — the `rules` array + an F-24/F-23 entry (the shape you append F-27 in).
- tests/schemas/test_cross_sheet_invariants_sync.py — see EXACTLY what it asserts (id sync? rule-text match?) so
  your 4-way registration keeps it green.
- An existing F-rule test e.g. tests/scripts/test_validate_invariants_F19.py — the test pattern (how it drives a
  check_F_* + patches `_REPO_ROOT` / a tmp tree to force PASS/FAIL).

SCOPE — create/modify ONLY these files:
  EDIT scripts/validation/validate_invariants.py        (check_F_27 + register in _RULE_FUNCTIONS + __all__)
  EDIT schemas/cross-sheet-invariants.json              (add the F-27 rule entry — the 4th sync point)
  NEW  tests/scripts/test_validate_invariants_F27.py    (PASS on current tree + FAIL/AMBER synthetic cases)

SPEC — check_F_27 (mirror F-24's engine-governance "sets-comparison" shape):
  Rule string (use VERBATIM in both the function `rule=` and the cross-sheet-invariants.json `rule`):
    "every OUTWARD MCP tool a skill declares in mcp_tools (required|optional) MUST be covered by an
     outward_action_gate matcher (the gate's gated-MCP set); an ungated declared outward MCP tool is a hole in the
     consent wall"
  Logic:
    1. gate_matchers = { _strip_mcp_prefix(_MCP_SUBMIT_TOOL) }  (registry-key form, e.g. "gsc__submit_sitemap").
    2. Curated OUTWARD set + heuristic (the rule's knowledge of which declared tools are OUTWARD):
       - `_OUTWARD_MCP_TOOLS` = a documented frozenset of registry-key tool names that perform an outward/write
         action. TODAY exactly { "gsc__submit_sitemap" } (the only outward MCP tool that exists). Document that
         adding a new outward MCP tool means adding it here AND to the gate.
       - `_OUTWARD_NAME_RE` = a precise outward-verb pattern for FUTURE tools the curated set hasn't caught —
         match submit / publish / ping / indexnow / url_updated, and EXCLUDE read verbs (inspect / list / get /
         search / detect / analytics / overview / suggestions / ideas / keywords / volume / parsing / lighthouse).
         TUNE it to ZERO false-positives against the real 47 skills (esp. do NOT flag `gsc__index_inspect`,
         `gsc__list_sitemaps`, `gsc__get_sitemap` — they are reads). (Mirror the 3a invocation-precision discipline.)
    3. declared = union of declared_tools(fm) over all skills/**/SKILL.md (registry keys; reuse 3a).
    4. FAIL (HIGH, csr_mcp) if any tool in (declared ∩ _OUTWARD_MCP_TOOLS) is NOT in gate_matchers
       (an outward tool a skill declares but the gate doesn't cover). Also FAIL if _OUTWARD_MCP_TOOLS ⊄ gate_matchers
       (a known outward tool the gate forgot — a gate hole). sample_violations = the offending tool(s) + which skill(s).
    5. WARN/AMBER (severity MEDIUM, verdict "FAIL" maps MEDIUM→AMBER per §17.2; OR use the SKIP/AMBER convention F-26
       uses — match the framework's AMBER mechanism) if a declared tool matches `_OUTWARD_NAME_RE` but is NOT in
       `_OUTWARD_MCP_TOOLS` → "review: classify this tool; if outward, add to _OUTWARD_MCP_TOOLS + a gate matcher"
       (future-proofing — catches a new outward-looking tool nobody classified). If you cannot cleanly express
       AMBER in this framework, make it a FAIL with MEDIUM severity (which §17.2 maps to AMBER) — confirm against
       F-26's AMBER pattern and REPORT which mechanism you used.
    6. PASS (today's expected state: skills declare `gsc__submit_sitemap`, it IS gated, no unclassified
       outward-looking tool) → PASS with evidence listing the declared-outward set + that all are gated.
  Engine-governance: ignore `workbook` (read skills + the gate constant only). Make the skills-root readable in a
  test-patchable way (mirror F-24's `_REPO_ROOT`-relative reads, OR accept an injectable skills-root kwarg
  defaulting to `_REPO_ROOT / "skills"`) so the test can force PASS/FAIL/AMBER with a tmp skill tree. Keep functions <50 lines.

SPEC — schemas/cross-sheet-invariants.json:
  Append one `rules` entry {id:"F-27", rule:"<verbatim rule string above>", severity:"HIGH", category:"csr_mcp",
  rationale:"<the ungated-outward-MCP-tool hole in the consent wall; Süleyman Indexing hard-constraint>",
  computed_by:"check_F_27"}. Match the existing entries' key shape EXACTLY (F-24's keys). The sync test must stay green.

SPEC — tests/scripts/test_validate_invariants_F27.py (mirror an existing F-rule test):
  - PASS on the REAL tree: check_F_27 over the actual skills + gate → verdict PASS (today the only outward MCP
    tool `gsc__submit_sitemap` is declared AND gated). This is the live regression lock.
  - FAIL synthetic: a tmp skills tree with a skill declaring an OUTWARD tool NOT in the gate matchers (either add a
    fake tool to `_OUTWARD_MCP_TOOLS` in the test via monkeypatch, OR — cleaner — seed a skill declaring
    `mcp__gsc__submit_sitemap` while monkeypatching the gate matcher set to empty) → verdict FAIL + the tool in
    sample_violations.
  - AMBER synthetic: a skill declaring a tool whose name matches `_OUTWARD_NAME_RE` but is not in
    `_OUTWARD_MCP_TOOLS` → the AMBER/WARN verdict.
  - PRECISION: a skill declaring only READ tools (`gsc__index_inspect`, `gsc__list_sitemaps`) → PASS (NOT flagged) —
    locks the read-verb exclusion against false-positives.

TDD ORDER:
  1. Baseline pytest (record N).
  2. Write test_validate_invariants_F27.py FIRST (RED — check_F_27 doesn't exist). Watch it fail.
  3. Implement check_F_27 + the 4-way registration + the cross-sheet-invariants.json entry → GREEN.
  4. Full suite: passed >= N, 0 failed. Re-run test_cross_sheet_invariants_sync.py + the
     tests/scripts/test_validate_invariants_*.py cluster explicitly (the sync must stay green).
  5. Self-review (@code-reviewer + @verifier, inline): check_F_27 mirrors F-24 (engine-governance, ignores
     workbook, _make_result); the gate matcher is IMPORTED (no drift); the read-verb exclusion gives ZERO
     false-positives on the real 47 skills (quote the PASS-on-real-tree test); the 4-way registration is complete
     (sync test green); the rule string is byte-identical in the function + the json; immutability; no file outside
     SCOPE; no D10 (no new command/schema FILE — cross-sheet-invariants.json is an EXISTING file, a rule is added
     inside it, NOT a new schemas/*.json file → the draft-count/plugin.json guards are untouched; CONFIRM by running
     tests/docs/test_count_consistency.py + tests/schemas/test_json_schema_draft_consistency.py).

DURUR (stop + report, do not guess):
  - The read-verb exclusion can't reach ZERO false-positives against the real skills without an ad-hoc per-skill
    allowlist → STOP + report (the outward classification needs a manager decision, like a registry `outward` flag).
  - test_cross_sheet_invariants_sync.py asserts something your 4-way registration can't satisfy (e.g. a field you
    didn't anticipate) → STOP + report.
  - Adding the rule requires editing the consistency-report.schema enum or any frozen schema → STOP (csr_mcp is
    already valid; you should not need to).
  - The gate exposes more than one gated MCP tool, or `_MCP_SUBMIT_TOOL` is not importable → STOP + report.
  - Any out-of-scope file needs editing, or a NEW command/schema file is required → STOP + report.

REPORT (print verbatim when DONE):
  - Baseline N + final pytest line (passed/skipped/failed) + the new F27 test count + sync-test green.
  - check_F_27: quote the rule string + the gate-matcher import + the FAIL/AMBER/PASS branches; confirm it mirrors
    F-24 (engine-governance, ignores workbook).
  - The 4-way registration: confirm function + `_RULE_FUNCTIONS` + `__all__` + cross-sheet-invariants.json all
    carry F-27 and the sync test is green; quote the json entry.
  - PASS-on-real-tree proof: check_F_27 over the actual skills returns PASS (the only outward MCP tool is gated) +
    the read-verb exclusion gives ZERO false-positives (quote the read-only-skill test).
  - FAIL + AMBER synthetic proofs (the rule FIRES on an ungated outward declared tool; AMBER on an unclassified
    outward-looking tool).
  - Confirm: gate matcher IMPORTED (no drift); no consistency-report-enum change; no file outside SCOPE; no D10
    (count_consistency + json_schema_draft_consistency green); the AMBER mechanism you used.
  - Any DURUR hit, out-of-scope need, or assumption (esp. the `_OUTWARD_MCP_TOOLS` curated set + the `_OUTWARD_NAME_RE`
    verb/read-exclusion choice).
```
