# AMO Batch 3a — Skill MCP `body ⊆ declared` Lint + `sf_load_crawl` Registry Fix (WORKER PROMPT)

> **Manager note (not part of the prompt):** Faz 0+1+2 are shipped (HEAD `c5123d8`, suite **2036 pass / 8 skip /
> 0 fail**, tree clean). This is the FIRST Faz-3 batch — spec §4 **mastery lint #1** (the STATIC `body ⊆ declared`
> MCP check). It is scoped to lint #1 only: lint #2 (`observed ⊆ declared`, the RUNTIME events.jsonl
> reconciliation) + the drift-F-rule + the secret-bytes scan are DISTINCT data domains → their own later batches.
> The manager ran a proto-lint and GROUNDED the exact gaps below (7 candidate skills; the precise detector will
> flag fewer/cleaner). Paste the fenced block into a fresh Claude Code session (Opus 4.8, 1M context) at the
> engine repo.

---

```text
You are a WORKER building ONE self-contained batch in the Platinum SEO Engine (Python, pytest).
Repo root: /Users/apple/Documents/platinum-seo-engine. This is batch 3a of the AMO initiative, managed from
another session. Work ONLY within this batch's scope. Do NOT git commit/push — when done, STOP and print the
REPORT (the manager reviews + commits). No sibling workers are active; stay scope-locked anyway.

HARD ENVIRONMENT RULES (non-negotiable):
- Do NOT use the Task or Agent tools (they FAIL here: MCP registry too large -> "Prompt is too long").
  Do ALL work inline yourself.
- Do NOT git commit/push/branch or alter git state.
- Baseline-first: run
  `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q 2>&1 | tail -5`
  and record the exact "N passed, M skipped" (N == 2036 at HEAD c5123d8) BEFORE any change. END green with
  passed strictly >= N (your new tests add to it) and 0 failed. EVERY existing test under tests/schemas/ MUST
  stay green — especially tests/schemas/test_skill_mcp_tools_exist_in_registry.py (declared ⊆ registry) and
  tests/schemas/test_mcp_registry_versions_match_mcp_json.py.
- TDD: failing test FIRST, watch it fail, then implement. Never fake red.
- House style: immutability (no mutation — build new objects); no leftover debug prints; small functions
  (<50 lines); files 200-400 lines; clear names; no hardcoded secrets.
- Scope-lock: create/modify ONLY the files in SCOPE. Anything else → STOP + report.

WHY THIS BATCH EXISTS (read carefully):
Spec §4 delivers "the system knows all its parts" WITHOUT a capability graph, via two cheap targeted lints.
ONE half already exists: tests/schemas/test_skill_mcp_tools_exist_in_registry.py enforces `declared ⊆ registry`
— every MCP tool a skill DECLARES in its SKILL.md `mcp_tools.required/optional` frontmatter must exist in
mcp-tool-registry.json. This batch builds the COMPLEMENT — lint #1: `body ⊆ declared`. Every MCP tool a skill
actually INVOKES in its SKILL.md body must be DECLARED in that skill's mcp_tools. Together they close the
triangle: used ⊆ declared ⊆ registry — an undeclared MCP dependency can no longer hide.

Today this is violated by the Screaming-Frog native-MCP opt-in skills. They call SF tools through SfMcpClient
(`client.call_tool("sf_list_crawls")`, `client.load_crawl(...)`) but do NOT declare them in mcp_tools — and
`sf_load_crawl` isn't even in the registry. These are invisible undeclared MCP deps. This batch makes them
visible (the lint) and fixes them (add the declarations + add sf_load_crawl to the registry).

CONFIRMED FACTS (verified against the code 2026-06-08 — do NOT re-derive):
- 45 skills live at skills/<category>/<name>/SKILL.md. ALL 45 have an `mcp_tools:` frontmatter block (some with
  empty required/optional). Frontmatter is YAML between the FIRST two lines that are exactly `---`; the BODY is
  everything after the 2nd `---`. (A skill body can contain markdown `---` horizontal rules — so split on the
  FIRST TWO `---`-only lines, line-based; do NOT naive-split on every `---`.)
- Skill frontmatter declares MCP tools in QUALIFIED form, e.g.
    mcp_tools:
      required:
        - "mcp__gsc__search_analytics"
      optional:
        - "mcp__sf__sf_list_crawls"
  schema schemas/skill-frontmatter.schema.json pins items to `^mcp__[a-zA-Z0-9_]+__[a-zA-Z0-9_]+$`.
- The EXISTING declared-side parser you must MIRROR (don't fight it) lives in
  tests/schemas/test_skill_mcp_tools_exist_in_registry.py:
    * `_MCP_TOOLS_BLOCK_RE = re.compile(r"(?ms)^mcp_tools:[ \t]*$\n(.*?)^(?:[A-Za-z_][A-Za-z0-9_-]*:|---)")`
    * `_TOOL_RE = re.compile(r"mcp__([A-Za-z0-9]+)__([A-Za-z0-9_]+)")`
    * server-alias `_ALIAS = {"ScraplingServer": "scrapling"}`; external-skip `_EXTERNAL_SERVERS = {"higgsfield"}`
    * registry key form = `f"{alias(server)}__{tool}"` (e.g. mcp__gsc__search_analytics -> "gsc__search_analytics";
      mcp__sf__sf_load_crawl -> "sf__sf_load_crawl"). Registry tool_names live at servers.<k>.tools[].tool_name.
- mcp-tool-registry.json `servers.sf.tools[]` ALREADY has: sf__sf_crawl, sf__sf_crawl_progress,
  sf__sf_generate_report, sf__sf_generate_bulk_export, sf__sf_export_seo_element_urls, sf__sf_list_crawls,
  sf__sf_list_allowed_base_directory. It is MISSING sf__sf_load_crawl. (scripts/util/sf_mcp_client.py line ~435
  calls `call_tool("sf_load_crawl", ...)`; the convenience method `SfMcpClient.load_crawl(...)` wraps it.)
- Native SF tools are invoked two ways in skill BODIES: (i) qualified `mcp__sf__sf_list_crawls(...)`
  (sf-crawl-orchestrator), and (ii) native via SfMcpClient — `client.call_tool("sf_list_crawls")` (string
  literal) and `client.load_crawl(crawl_id)` (a wrapper method → the sf_load_crawl tool). The native tool name
  has NO mcp__ prefix; its registry key is `sf__<native_name>` (e.g. "sf_list_crawls" -> "sf__sf_list_crawls").
- events.jsonl source.mcp_tool uses the REGISTRY form ("gsc__search_analytics") — NOT relevant to this batch
  (that's lint #2, a later batch). This batch is STATIC: it reads SKILL.md text only.

- MANAGER PROTO-LINT RESULT (a crude bare-token scan — your PRECISE detector will flag FEWER, cleaner tools).
  Use this as the ground truth of where to look, and as the false-positive test oracle:
    on-page-audit : sf_list_crawls, sf_load_crawl  (+ sf_export_seo_element_urls via SF_EXPORT_DISPATCH)
    schema-audit  : sf_list_crawls, sf_load_crawl  (+ sf_export_seo_element_urls via SF_EXPORT_DISPATCH)
    tech-audit    : sf_list_crawls, sf_load_crawl  (+ sf_generate_report via SF_EXPORT_DISPATCH)
    internal-links: sf_list_crawls, sf_load_crawl  (+ sf_generate_bulk_export via SF_EXPORT_DISPATCH)
    drift-check   : sf_crawl_progress  ← LIKELY A PROSE MENTION (verify; the audit skills LOAD a completed crawl,
                    they do not poll progress) → if it's not a real invocation, the precise detector must NOT
                    flag it and you must NOT modify drift-check.
  TWO PRECISION TRAPS the precise detector MUST get right (these are the whole point of "invocation-precise"):
    (1) FALSE POSITIVE — monthly-report SKILL.md line ~95: `` `mcp__gsc__search_analytics` tool MAY be invoked
        opportunistically by … `` — a backtick PROSE MENTION, NO call-parens. Must NOT be flagged. monthly-report
        is model_attested and must stay UNCHANGED.
    (2) ARTIFACT — `client.call_tool(tool, file_path=…)` (sf-crawl-orchestrator + the audit skills'
        SF_EXPORT_DISPATCH) passes a VARIABLE, not a string literal → unresolvable statically → must NOT be
        flagged (the bare-token proto-lint mis-emitted a bogus "sf__sf_" from this). sf-crawl-orchestrator
        ALREADY declares its qualified mcp__sf__ tools → it must end up with ZERO gaps.

ORIENT FIRST (read, do not change yet):
- tests/schemas/test_skill_mcp_tools_exist_in_registry.py IN FULL (the declared-side parser you mirror).
- schemas/skill-frontmatter.schema.json (the mcp_tools shape + the item regex).
- scripts/util/sf_mcp_client.py — enumerate the PUBLIC wrapper methods that map 1:1 to an sf_ tool (at minimum
  `load_crawl` -> "sf_load_crawl"; confirm whether any other public method, e.g. health, maps to a distinct
  sf_ tool or not — only map methods that correspond to a real registry sf_ tool).
- The bodies of the 5 candidate skills (on-page-audit, schema-audit, tech-audit, internal-links, drift-check)
  AND the two trap skills (monthly-report, sf-crawl-orchestrator) — see exactly how each tool is invoked vs
  merely mentioned, so your detector's regexes match invocations and skip mentions/variables.
- mcp-tool-registry.json servers.sf block (the shape of a tool entry you will add).

SCOPE — create/modify ONLY these files:
  NEW  scripts/validation/skill_mcp_usage.py            (the reusable parser: declared/invoked/gap)
  NEW  tests/validation/test_skill_mcp_usage.py         (unit tests for the parser incl. BOTH precision traps)
  NEW  tests/schemas/test_skill_body_mcp_subset_declared.py  (the lint: per-skill body ⊆ declared, parametrized)
  EDIT mcp-tool-registry.json                           (add the sf__sf_load_crawl tool entry)
  EDIT skills/discovery/on-page-audit/SKILL.md          (declare the SF tools it genuinely uses)
  EDIT skills/discovery/schema-audit/SKILL.md
  EDIT skills/discovery/tech-audit/SKILL.md
  EDIT skills/planning/internal-links/SKILL.md
  (drift-check + any OTHER skill: edit ONLY if your PRECISE detector flags a REAL invocation. If the precise
   detector flags something you believe is a genuine false-positive, FIX THE DETECTOR — never suppress with an
   allowlist of skills. If a flag is ambiguous and you can't resolve it without guessing, STOP + report it.)

SPEC — scripts/validation/skill_mcp_usage.py (pure, no side effects, no I/O beyond reading the given paths):
  Public API (keep functions <50 lines; reuse the EXISTING regexes/alias above so declared-parsing is identical
  to the registry test):
    split_frontmatter_body(text: str) -> tuple[str, str]
        # frontmatter, body — line-based on the FIRST TWO `---`-only lines; if <2, treat whole text as body
        # and "" frontmatter (a malformed skill has no declarations — that's a real gap, not a crash).
    declared_tools(frontmatter: str) -> set[str]
        # registry-key set from the mcp_tools block (mirror _MCP_TOOLS_BLOCK_RE + _TOOL_RE + _ALIAS).
    invoked_tools(body: str) -> set[str]
        # registry-key set of ACTUAL INVOCATIONS (not mentions). An invocation is ANY of:
        #   A) qualified call: `mcp__<server>__<tool>` immediately followed by optional ws then `(`
        #      -> alias-normalize; skip server in {"higgsfield"}. (Backtick mention w/o `(` is NOT a call.)
        #   B) native literal: `call_tool(` with a STRING-LITERAL first arg (positional OR tool_name="..."):
        #      regex ~ `call_tool\(\s*(?:tool_name\s*=\s*)?["']([a-z][a-z0-9_]+)["']` -> key "sf__<name>".
        #      A non-literal first arg (`call_tool(tool, ...)`, `call_tool(f"sf_{x}")`) is UNRESOLVABLE -> skip.
        #   C) wrapper method: a known SfMcpClient method call `\.<method>\s*\(` for each method in a small
        #      curated map you build from sf_mcp_client.py (at minimum {"load_crawl": "sf_load_crawl"})
        #      -> key "sf__<tool>".
    body_not_declared(skill_path) -> set[str]
        # invoked_tools(body) - declared_tools(frontmatter)   (the gap for one skill)
    iter_skill_gaps(root) -> dict[str, set[str]]   # {skill_relpath: gap_set} for non-empty gaps (helper for the test)
  Anchor file paths file-relative (pathlib.Path(__file__).resolve().parents[N]); do NOT rely on
  CLAUDE_PLUGIN_ROOT (an installed-plugin copy could shadow the working tree — see the 0c bare-CLI lesson).

  REGISTRY FIX — add to mcp-tool-registry.json servers.sf.tools (match the existing entry shape exactly):
    {
      "tool_name": "sf__sf_load_crawl",
      "description": "Load a previously-identified completed SF crawl by crawl_id (instanceDirName) into the SF
        GUI so element/report exports operate on it. Native SfMcpClient.load_crawl wrapper; used by the D-SF-11
        opt-in live-crawl path in schema-audit / on-page-audit / tech-audit / internal-links.",
      "category": "platform_detection",
      "used_by_mappings": ["internal"],
      "cache_ttl_hours": 0
    }
  (Adds a tool to an EXISTING server — does NOT change server count, version_lock, or .mcp.json → must not
   regress test_mcp_registry_versions_match_mcp_json.py. After this, declared ⊆ registry stays satisfiable.)

  DECLARATION FIXES — for each skill the precise detector flags, ADD the used tools to mcp_tools.OPTIONAL
  (SF live-crawl is D-SF-11 OPT-IN with an AMBER file-based fallback — "NEVER hard fail per R9" — so it is
  semantically OPTIONAL, not required). Use the QUALIFIED form `mcp__sf__<tool>`. Expected end-state (confirm
  against each skill's real flow; the FIRST two are detector-forced, the SF_EXPORT_DISPATCH one is a genuine dep
  you ADD for declaration completeness even though call_tool(var) makes it statically invisible to the lint):
    on-page-audit  optional += mcp__sf__sf_list_crawls, mcp__sf__sf_load_crawl, mcp__sf__sf_export_seo_element_urls
    schema-audit   optional += mcp__sf__sf_list_crawls, mcp__sf__sf_load_crawl, mcp__sf__sf_export_seo_element_urls
    tech-audit     optional += mcp__sf__sf_list_crawls, mcp__sf__sf_load_crawl, mcp__sf__sf_generate_report
    internal-links optional += mcp__sf__sf_list_crawls, mcp__sf__sf_load_crawl, mcp__sf__sf_generate_bulk_export
  Preserve each skill's existing required/optional entries + ordering; only APPEND the missing ones (dedupe).
  Do NOT touch any skill the precise detector does not flag. In the REPORT, separate "lint-forced" tools from
  "declaration-completeness" tools (SF_EXPORT_DISPATCH variable-dispatched) so the manager can verify.

SPEC — tests/schemas/test_skill_body_mcp_subset_declared.py (the lint):
  - Parametrize over sorted(ROOT.glob("skills/**/SKILL.md")) (one test per skill → a clean failure name).
  - assert body_not_declared(skill) == set(), with a message listing the offending tools + the skill path AND
    the remediation ("declare these in mcp_tools.required/optional, or fix the registry if absent").
  - After your fixes this is fully GREEN. (This is the lint that future skills are held to.)

SPEC — tests/validation/test_skill_mcp_usage.py (unit tests for the parser; inline string fixtures, no real files):
  Cover at minimum:
    - declared_tools parses required+optional, applies the ScraplingServer->scrapling alias.
    - invoked_tools class A: `x = mcp__gsc__search_analytics(args)` -> {"gsc__search_analytics"}.
    - PRECISION TRAP 1 (mention): a body line `` `mcp__gsc__search_analytics` tool MAY be invoked `` (backticks,
      no parens) -> invoked_tools == set() (NOT flagged).
    - invoked_tools class B: `client.call_tool("sf_list_crawls")` -> {"sf__sf_list_crawls"};
      `call_tool(tool_name="sf_crawl_progress")` -> {"sf__sf_crawl_progress"}.
    - PRECISION TRAP 2 (variable): `client.call_tool(tool, file_path=p)` -> set() (NOT flagged, no bogus sf__).
    - invoked_tools class C: `client.load_crawl(crawl_id)` -> {"sf__sf_load_crawl"}.
    - higgsfield excluded: `mcp__higgsfield__generate_image(x)` -> set().
    - split_frontmatter_body: a body containing a markdown `---` rule does NOT truncate the body; the mcp_tools
      block in frontmatter is NOT counted as an invocation.
    - body_not_declared on a fixture where the body invokes a declared tool -> set(); invokes an UNdeclared tool
      -> that tool.

TDD ORDER:
  1. Baseline pytest (record N == 2036).
  2. Write tests/validation/test_skill_mcp_usage.py FIRST (RED — module doesn't exist). Watch it fail.
  3. Implement scripts/validation/skill_mcp_usage.py → unit tests GREEN.
  4. Add tests/schemas/test_skill_body_mcp_subset_declared.py (RED — the 4-5 real skills fail with REAL gaps;
     paste the failing tool list into your REPORT — this is the proof the lint works before any fix).
  5. Apply the registry fix + the declaration fixes → the lint goes GREEN.
  6. Full suite: passed >= 2036, 0 failed. Re-run test_skill_mcp_tools_exist_in_registry.py (declared ⊆ registry
     still green — your new sf_load_crawl declarations resolve because you added it to the registry).
  7. Self-review (@code-reviewer + @verifier, inline): detector is invocation-precise (quote the trap tests —
     mention NOT flagged, variable NOT flagged); fixes are append-only to optional; monthly-report +
     sf-crawl-orchestrator UNCHANGED and ZERO-gap; no file outside SCOPE; immutability; no D10 (no new
     command/schema/.json-schema; new module is under scripts/validation/, NOT a wired hook, so it is NOT a
     RUNTIME_HOOK_SCRIPTS entry and does NOT touch tests/hooks/test_hook_scripts_runtime_vs_ci.py).

DURUR (stop + report, do not guess):
  - The precise detector flags a skill you did NOT expect, and you can't tell invocation from mention without
    guessing → STOP + report the skill + line.
  - A skill genuinely invokes a tool that is NOT in the registry and is NOT sf_load_crawl → STOP + report (a
    second registry gap is a manager decision, not a silent add).
  - Adding the declarations breaks test_skill_mcp_tools_exist_in_registry.py for a tool you can't resolve → STOP.
  - Any out-of-scope file needs editing → STOP + report (do NOT broaden scope).

REPORT (print verbatim when DONE):
  - Baseline N and the final pytest line (passed/skipped/failed); the new test counts (unit + lint).
  - The RED proof: the exact per-skill gap list the lint emitted BEFORE the fixes.
  - The detector rules (quote invoked_tools' 3 match classes) + confirm BOTH precision traps pass (monthly-report
    mention NOT flagged; call_tool(var) NOT flagged; sf-crawl-orchestrator ZERO gap).
  - Per skill edited: the exact tools added to optional, split into "lint-forced" vs "declaration-completeness".
  - The registry diff (sf__sf_load_crawl entry).
  - Confirm: monthly-report + sf-crawl-orchestrator UNCHANGED; declared ⊆ registry still green; no file outside
    SCOPE; no D10; no new RUNTIME_HOOK_SCRIPTS entry.
  - Any DURUR hit, out-of-scope need, or assumption you made.
```
