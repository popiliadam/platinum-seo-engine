# AMO batch 3-gov-lint2 (Option B′) — static workflow-tool ⊆ skill-declared ⊆ registry

> Paste everything inside the fenced block below into a fresh **Opus-4.8 1M-context** worker session at
> `/Users/apple/Documents/platinum-seo-engine`. Relay the worker's REPORT back verbatim.
>
> **Manager note (why B′, not the spec's runtime B):** I verified the real data before authoring. The
> events.jsonl "observed MCP" signal (`source.mcp_tool`) is recorded in only ~3 of 3000+ historical events,
> is inconsistently formatted, and the orchestrator does NOT write it going forward — so a runtime
> `observed ⊆ declared` lint would be vacuous or false-RED. Süleyman approved the static realization (B′):
> assert every workflow's declared-required MCP tool is declared by its owning skill AND in the registry.
> This closes `workflow-required ⊆ skill-declared ⊆ registry` (extending 3a's triangle up to the
> orchestrator) — deterministic, self-contained, GREEN today, catches future drift. This batch is
> FILE-DISJOINT from 3-gov-secrets (can run in parallel).

```text
You are a worker session on the Platinum SEO Engine (a Claude Code plugin). Implement ONE self-contained
batch: a STATIC lint that the orchestrator's workflow steps cannot require an MCP tool their owning skill
does not declare. Follow every rule below EXACTLY.

═══════════════════════════════════════════════════════════════════════════════════════════════
HARD RULES (violating any one = STOP and report)
═══════════════════════════════════════════════════════════════════════════════════════════════
1. NO Task/Agent tools. They FAIL in this repo ("Prompt is too long" — the MCP registry is too large).
   Do ALL work inline with Read/Edit/Write/Bash/Grep.
2. NO git operations of any kind. The MANAGER commits after reviewing your REPORT. You only edit + test.
3. BASELINE-FIRST. Before touching anything, run EXACTLY this and record the numbers:
      PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5
   Expected baseline: 2175 passed, 7 skipped, 0 failed — OR HIGHER if batch 3-gov-secrets has already
   merged (it adds tests; that is fine — measure YOUR baseline and end strictly >= it, 0 failed). One
   MCP-availability-gated test may flip pass<->skip; total stays stable — not a regression.
4. TDD, RED FIRST. Write the tests, RUN them, SHOW they FAIL for the right reason (the module does not
   exist yet → ImportError; the synthetic-gap case detects a planted violation), THEN implement.
5. SCOPE-LOCK. Create/modify ONLY the two files in SCOPE. Anything else → STOP + report. In particular:
   you must NOT need to edit any SKILL.md, any workflow module, the registry, a command, a schema, or a
   manifest — the lint is GREEN against the current tree (manager pre-verified). If a real gap appears,
   STOP and report it (do NOT "fix" a skill to make the lint pass — that is a separate decision).
6. Python discipline: pure functions, no side effects beyond reading files / importing workflow modules;
   immutability (no mutation of shared structures); functions < 50 lines; no debug prints; type hints.

═══════════════════════════════════════════════════════════════════════════════════════════════
WHY
═══════════════════════════════════════════════════════════════════════════════════════════════
batch 3a shipped lint #1 (`scripts/validation/skill_mcp_usage.py`) closing `body ⊆ declared ⊆ registry`
for SKILLS. The orchestrator (Faz 1/3) adds a layer ABOVE skills: each workflow's `STEPS` tuple pins, per
step, the MCP `tool` that step requires (e.g. monthly's gsc_pull requires `mcp__gsc__search_analytics`).
Nothing yet guarantees that a workflow-required tool is actually DECLARED by the skill that runs that step,
or even exists in the registry. This lint closes that gap statically:

    workflow STEPS[].tool   ⊆   owning-skill declared mcp_tools   ⊆   registry tool_name set

A drift it catches: someone adds/edits a workflow step to require a tool the skill doesn't declare (or
renames a tool in a skill while a workflow still pins the old name) → the orchestrator and the skill are
out of sync → CAUGHT at author time, deterministically, with no runtime/events dependency.

═══════════════════════════════════════════════════════════════════════════════════════════════
CONFIRMED FACTS (manager-verified against the real tree — do NOT re-derive; DO re-read the files)
═══════════════════════════════════════════════════════════════════════════════════════════════
A. ⚠️ THE KEY-SPACE NORMALIZATION TRAP (the manager hit this — get it exactly right):
   • workflow `STEPS[].tool` is the QUALIFIED form:  `mcp__gsc__search_analytics`
   • `skill_mcp_usage.declared_tools()` returns the `server__tool` form:  `gsc__search_analytics`
   • registry `tool_name` keys are the same `server__tool` form:  `gsc__search_analytics`
   The bridge = strip the leading `mcp__` prefix, which is **5 characters** (m, c, p, _, _ — DOUBLE
   underscore). Use `tool.removeprefix("mcp__")`. A naive `tool[4:]` yields `_gsc__search_analytics`
   (leading underscore) → false-FAIL on EVERYTHING. After stripping, also apply the SAME server alias
   `skill_mcp_usage` uses — `{"ScraplingServer": "scrapling"}` — to the server segment, so the key space
   matches `declared_tools()` exactly. (No current workflow uses a ScraplingServer tool, but be correct.)

B. The 3a module you REUSE (`scripts/validation/skill_mcp_usage.py`):
   • `split_frontmatter_body(text) -> (frontmatter, body)` — splits on the first two `---` fences.
   • `declared_tools(frontmatter) -> set[str]` — the registry-key set a skill declares (required ∪
     optional), e.g. `{"gsc__search_analytics", ...}`. Import and reuse these — do NOT re-parse frontmatter.

C. The registry (repo-root `mcp-tool-registry.json`). Canonical tool-key extraction (mirror
   `tests/schemas/test_skill_mcp_tools_exist_in_registry.py::_registry_tool_names`):
       reg = json.loads(Path("mcp-tool-registry.json").read_text())
       names = { t["tool_name"] for srv in reg["servers"].values() for t in srv["tools"] }
   This yields `server__tool` keys (e.g. `gsc__search_analytics`). Use SET MEMBERSHIP, not substring.

D. The workflow modules live at `scripts/orchestration/workflows/*.py`. Each data-workflow module has a
   module-level `STEPS: tuple[dict, ...]`. A step dict has keys incl. `name`, `writer`, and `tool`
   (a qualified `mcp__...` string OR `None`). The artifact-driver `content_pipeline.py` STEPS have NO
   `tool` key at all (`dict.get("tool")` → None). The EXACT current tool-bearing steps (manager-verified,
   all GREEN today):
       monthly_maintenance:  gsc_pull→mcp__gsc__search_analytics (writer gsc-pull),
                             quick_wins→mcp__gsc__detect_quick_wins (quick-wins),
                             content_decay→mcp__gsc__enhanced_search_analytics (content-decay)
       audit_suite:          tech_audit→mcp__dataforseo__on_page_lighthouse (tech-audit),
                             schema_audit→tool=None [SKIP],
                             on_page_audit→mcp__dataforseo__on_page_content_parsing (on-page-audit),
                             cannibalization→mcp__gsc__search_analytics (cannibalization)
       new_project_setup:    topical_map→mcp__dataforseo__dataforseo_labs_google_keyword_ideas (topical-map),
                             cluster_map→mcp__dataforseo__dataforseo_labs_google_keyword_suggestions (cluster-map),
                             new_content_plan→tool=None [SKIP]
       content_pipeline:     new_blog / generate_images / faq_optimization → NO tool key [SKIP all]
   Steps with `tool is None` (or no tool key) are SKIPPED — they make no MCP data call.

E. writer→skill resolution: a step's `writer` (e.g. `"gsc-pull"`, `"tech-audit"`, `"cannibalization"`,
   `"topical-map"`) maps to a skill directory NESTED BY CATEGORY:
       skills/<category>/<writer>/SKILL.md     (e.g. skills/ingestion/gsc-pull/SKILL.md)
   Resolve by glob: `sorted(ROOT.glob(f"skills/**/{writer}/SKILL.md"))` → take the single match. Manager
   verified all 8 writers above resolve to exactly one skill dir, and each declares its required tool.
   A writer that resolves to ZERO or MULTIPLE skill dirs is itself a lint FAILURE (surface it, don't crash).

F. This is the SAME HOME + SHAPE as 3a: a pure module in `scripts/validation/` + a per-item parametrized
   test in `tests/schemas/`. NO new command, NO new schema, NO manifest, NO hook → **no D10 count-guard
   bump, no RUNTIME_HOOK_SCRIPTS entry.** (You add only a validation module + a test.)

G. Importing workflow modules: in pytest the repo root is on `sys.path`, so
   `importlib.import_module("scripts.orchestration.workflows.monthly_maintenance")` works (manager
   confirmed — no env vars / workspace needed to import; STEPS is a plain module-level tuple). The module
   you write is imported only by its test (NOT standalone-loaded by any hook), so the D16(a) standalone
   sys.path trap does NOT apply here — but anchor `ROOT = Path(__file__).resolve().parents[2]` (file-
   relative, NOT CLAUDE_PLUGIN_ROOT) per the 0c bare-CLI lesson, same as skill_mcp_usage.

═══════════════════════════════════════════════════════════════════════════════════════════════
SCOPE — the ONLY files you may create
═══════════════════════════════════════════════════════════════════════════════════════════════
1. `scripts/validation/workflow_tool_declared.py`            (the lint module)
2. `tests/schemas/test_workflow_tool_subset_declared.py`     (the test)
Nothing else.

═══════════════════════════════════════════════════════════════════════════════════════════════
SPEC — the lint module (pure; mirror skill_mcp_usage.py's style)
═══════════════════════════════════════════════════════════════════════════════════════════════
`scripts/validation/workflow_tool_declared.py`:
  • `ROOT = Path(__file__).resolve().parents[2]`.
  • `_SERVER_ALIAS = {"ScraplingServer": "scrapling"}` (mirror skill_mcp_usage._ALIAS).
  • `normalize_tool(qualified: str) -> str`: strip `mcp__` (removeprefix), split into server/tool on the
    FIRST `__`, alias the server, return `f"{server}__{tool}"`. (Reuses skill_mcp_usage's key space.)
  • `registry_tool_names(root=ROOT) -> set[str]`: the canonical extraction from fact C.
  • `resolve_skill(writer: str, root=ROOT) -> Path | None`: the glob from fact E (None if 0 or >1 matches).
  • `iter_workflow_tool_steps(root=ROOT) -> Iterator[tuple[str,str,str,str]]`: DISCOVER every
    `scripts/orchestration/workflows/*.py` (skip `__init__.py`), import it, read `getattr(mod,"STEPS",())`;
    for each step dict, if `step.get("tool")` is not None, yield
    `(workflow_module_name, step["name"], step["writer"], normalize_tool(step["tool"]))`. A module without
    STEPS, or a step without/None tool, is simply skipped. (Glob-discovery so a future workflow is
    auto-covered — do NOT hardcode the 4 module names.)
  • `workflow_tool_violations(root=ROOT) -> dict[str, list[str]]`: the gap map keyed by
    `f"{workflow}.{step}"`; each value is the list of reasons among:
        - `"writer '<w>' resolves to no/multiple skill dir"`     (resolve_skill is None)
        - `"tool <T> not declared by skill <relpath>"`           (normalized tool ∉ declared_tools of the
                                                                   owning skill's frontmatter)
        - `"tool <T> absent from registry"`                      (normalized tool ∉ registry_tool_names())
    A step with an empty reason list is GREEN and omitted. Reuse skill_mcp_usage.split_frontmatter_body +
    declared_tools for the declared check.
  Keep every function < 50 lines, pure, no prints.

═══════════════════════════════════════════════════════════════════════════════════════════════
TDD — `tests/schemas/test_workflow_tool_subset_declared.py`
═══════════════════════════════════════════════════════════════════════════════════════════════
Mirror the 3a test's shape (parametrize per item so a regression names the offending step):
  • UNIT: `normalize_tool("mcp__gsc__search_analytics") == "gsc__search_analytics"` AND it does NOT start
    with "_" (locks the 5-char strip — a `[4:]` regression would FAIL this).
  • UNIT: `normalize_tool("mcp__ScraplingServer__sf_load_crawl") == "scrapling__sf_load_crawl"` (alias).
  • UNIT: `registry_tool_names()` contains `gsc__search_analytics` and `dataforseo__on_page_lighthouse`.
  • UNIT: `resolve_skill("gsc-pull")` is not None and ends with `gsc-pull/SKILL.md`;
    `resolve_skill("definitely-not-a-skill")` is None.
  • DISCOVERY: `set(iter_workflow_tool_steps())` has exactly the 8 tool-bearing steps from fact D
    (assert the count == 8 and that `schema_audit`/`new_content_plan`/content steps are absent).
  • MAIN (the lint, parametrized per tool-bearing step): for each `(workflow, step, writer, tool)` from
    `iter_workflow_tool_steps()`, assert that step's reasons list in `workflow_tool_violations()` is empty
    — i.e. the whole tree is GREEN. Use an id like `f"{workflow}.{step}"`.
  • TEETH (synthetic NEGATIVE — proves the lint is not vacuous): build a tiny in-test fake — e.g. call a
    small helper that checks one synthetic `(writer="gsc-pull", tool="mcp__gsc__NONEXISTENT_TOOL")` triple
    through the SAME declared/registry predicates and assert it produces BOTH "not declared" and "absent
    from registry" reasons. (Construct the synthetic tool name dynamically; do not commit a real-looking
    secret — irrelevant here, but keep fixtures synthetic.) This guarantees a real future drift is caught.
Run UNIT + TEETH + MAIN: MAIN/UNIT/DISCOVERY are RED before the module exists (ImportError); TEETH proves
detection. Then implement → all GREEN.

═══════════════════════════════════════════════════════════════════════════════════════════════
METHOD
═══════════════════════════════════════════════════════════════════════════════════════════════
1. Baseline pytest (rule 3).
2. Read `scripts/validation/skill_mcp_usage.py`, `tests/schemas/test_skill_body_mcp_subset_declared.py`,
   `tests/schemas/test_skill_mcp_tools_exist_in_registry.py` (registry extraction), and the four
   `scripts/orchestration/workflows/*.py` STEPS tuples.
3. Write the test file (UNIT+DISCOVERY+MAIN+TEETH) → run → SHOW RED (ImportError + TEETH detecting).
4. Implement `workflow_tool_declared.py`.
5. New test → GREEN. FULL suite → passed >= your baseline, 0 failed.
6. Self-review: pure/no-side-effect? normalize uses removeprefix (5-char)? glob-discovery (no hardcoded
   module list)? no SKILL.md/workflow/registry/manifest edited (scope clean)?

═══════════════════════════════════════════════════════════════════════════════════════════════
DURUR — STOP and report if:
═══════════════════════════════════════════════════════════════════════════════════════════════
• The lint goes RED against the real tree (a genuine workflow⊄skill or ⊄registry gap) — report the exact
  step + tool; do NOT edit a skill/workflow/registry to force GREEN (that is a separate manager decision,
  like 3a's sf_load_crawl fix).
• A writer resolves to zero or multiple skill dirs (report which).
• Importing a workflow module has an unexpected side effect or needs workspace env (report it; consider
  reading STEPS without import only if truly necessary — but prefer import per fact G).
• You would need any file outside SCOPE.

═══════════════════════════════════════════════════════════════════════════════════════════════
REPORT — print exactly this back to the manager
═══════════════════════════════════════════════════════════════════════════════════════════════
1. BASELINE: the pytest numbers you measured (note if 3-gov-secrets already merged → higher floor).
2. RED PROOF: the new tests failing before implementation (ImportError on MAIN/UNIT + TEETH detecting the
   synthetic gap).
3. MODULE: the functions you wrote (signatures) + confirm normalize_tool uses a 5-char removeprefix +
   glob-discovery (no hardcoded module list).
4. LINT RESULT: the 8 tool-bearing steps all GREEN (list them) + the 3 skipped (schema_audit /
   new_content_plan / content-*). Confirm NO skill/workflow/registry/manifest was edited.
5. TEETH: the synthetic-gap case proving the lint detects an undeclared/absent tool.
6. FULL SUITE: the final `tail -5` (passed/skipped/failed) — passed >= baseline, 0 failed.
7. ANYTHING you had to decide or that surprised you.
```
