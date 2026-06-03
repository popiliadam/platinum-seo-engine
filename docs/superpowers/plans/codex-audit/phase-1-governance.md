# Phase 1 — Governance Authority — Worker Brief

## 0. READ FIRST (worker onboarding)

- You are a **fresh worker session**. This brief is complete — do NOT explore the whole repo.
- Engine repo: `/Users/apple/Documents/platinum-seo-engine`. (This phase does NOT touch the workspace repo.)
- **Invoke `superpowers:test-driven-development` and follow it.** Red → green → commit, per task.
- **Branch first:** `git checkout -b fix/codex-audit-phase-1-governance` (off `main`).
- **Atomic commits:** one logical change per commit (this phase = ~3 commits: P0-01, P0-03, P1-13).
- **Constraints:** never commit `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; do NOT push or touch `main`;
  preserve unrelated changes; engine-only (no workspace edits this phase).
- **Baseline to preserve:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  → must stay ≥ **1449 passed, 8 skipped** (plus your new tests).

## 1. GOAL + findings this phase closes

**Goal:** Make the governance surface (cross-sheet invariant registry + MCP tool registry) tell the
truth about what is actually enforced, and lock that truth with tests so it cannot drift again.

- **P0-01** — `schemas/cross-sheet-invariants.json` (registry) and `scripts/validation/validate_invariants.py`
  (implementation) assign the SAME F-IDs to DIFFERENT rules (~12 IDs). The existing sync test only
  checks ID-sets + a severity literal it can't always see — it never checks rule *meaning*.
- **P0-03** — MCP registry `mcp-tool-registry.json` is version-lagged (`dataforseo` lock `2.8.9` vs
  `.mcp.json` `@2.8.10`), incomplete (33 tool entries; skills reference more DataForSEO tools), and
  has a `scrapling` vs `.mcp.json` `ScraplingServer` key-alias the schema doesn't formalize.
- **P1-13** — `skills/production/generate-images/SKILL.md` (`status: active`) requires
  `mcp__higgsfield__generate_image` but Higgsfield is intentionally NOT in `.mcp.json`/registry; the
  registry has no way to represent a user-level external dependency.

## 2. EVIDENCE (verified current state)

**P0-01 — the ~12 colliding IDs.** `validate_invariants.py` returns a `rule` string per check (the
truth). The registry's `rule` for the same ID says something else. Target = rewrite registry to the
code's `rule` text + align `severity`:

| ID | Code `rule` (TRUTH — set registry to this) | Code severity | Registry currently says (WRONG) | Reg sev |
|----|--------------------------------------------|---------------|---------------------------------|---------|
| F-01 | `master_task.status ⊆ statusEnum {TODO,ONGOING,EXISTS,DONE,BLOCKED,DEFERRED,CANCELED}` | CRITICAL | `master_task.url ⊆ (crawl_sitemap.url ∪ external_urls)` | CRITICAL |
| F-02 | ``dashboard sheet contains no live `=COUNTIF(...)` formulas`` | CRITICAL | `count(master_task WHERE status=DONE) == dashboard.R48` | CRITICAL |
| F-03 | ``dashboard sheet contains no live `=SUMIF(...)` formulas`` | CRITICAL | `count(master_task WHERE status=TODO) == dashboard.R49` | CRITICAL |
| F-04 | ``dashboard sheet contains no live `=AVERAGEIF(...)` formulas`` | **CRITICAL** | `count(master_task WHERE status=ONGOING) == dashboard.R50` | **HIGH** ← sev drift |
| F-05 | `every sheet present in workbook matches its master-excel.schema header column count` | CRITICAL | `completed_work.task_id ⊆ master_task WHERE status=DONE` | CRITICAL |
| F-08 | `quick_wins.url ⊆ (crawl_sitemap.url ∪ gsc_performance.url)` | HIGH | `quick_wins.target_url ⊆ (crawl_sitemap ∪ gsc_performance)` | HIGH |
| F-09 | `master_task.task_id is unique across all rows` | HIGH | `cluster_keywords.assigned_url ⊆ topical_map.assigned_url` | HIGH |
| F-10 | `url_normalizer(x) == x for every quick_wins.url (D-03 idempotent)` | HIGH | `cannibalization.pages ⊆ crawl_sitemap.url` | HIGH |
| F-11 | `every _state/workflows/*.json has schema_version == "1.0"` | HIGH | `schema.url ⊆ crawl_sitemap.url` | HIGH |
| F-12 | `events.jsonl line count is monotonically non-decreasing` | HIGH | `redirect_404.from_url ⊆ sf_response_codes WHERE status IN (301,302,404)` | HIGH |
| F-13 | `every event_kind=provenance row has run_id of integer type` | HIGH | `robots_txt.disallowed == crawl_sitemap WHERE indexability='Non-indexable (robots)'` | HIGH |
| F-14 | `every event_kind=workflow row has workflow_run_id matching {slug}-YYYY-MM-DD-{hash4}` | HIGH | `gsc_performance.page ⊆ (crawl_sitemap ∪ redirect_targets)` | HIGH |

IDs that ALREADY match (do not touch): F-15, F-16, F-17, F-18, F-19, F-20, F-21, F-22, F-23, F-24, F-25, F-26.
IDs declared in registry but intentionally unimplemented: F-06, F-07 (in test `KNOWN_SCHEMA_ONLY`).
Registry-only design rules with NO implementation: `D-01, D-02, D-03, M-01, M-02` (and the *original*
meanings of F-01..F-05/F-09..F-14 above).

- Code truth source: `scripts/validation/validate_invariants.py` (functions `check_F_*`, list `_RULE_FUNCTIONS`).
- The way to read a function's canonical `rule`/`severity`: call it on an empty workbook + tmp workspace
  and read `result["rule"]` / `result["severity"]` (missing sheets → SKIP, but the dict still carries them).
- Existing sync test (keep its ID/severity-set tests, FIX its blind spot): `tests/schemas/test_cross_sheet_invariants_sync.py`.
  Its `test_severity_consistency_for_implemented_rules` uses `re.search(r'severity="(\w+)"', source)` —
  this MISSES F-02/03/04 (severity lives in helper `_check_no_excel_formula`, not the function body), which
  is why the F-04 CRITICAL-vs-HIGH drift went undetected.

**P0-03 — MCP registry.**
- `.mcp.json`: `dataforseo` → `dataforseo-mcp-server@2.8.10`; server keys `gsc, dataforseo, ScraplingServer, sf`.
- `mcp-tool-registry.json`: servers `gsc(8 tools, lock none), dataforseo(9, lock "2.8.9"), scrapling(9, lock none), sf(7, lock "24.0.0")` = 33 tool entries; no higgsfield.
- `schemas/mcp-tool-registry.schema.json:5` description hardcodes `const '2.8.9'`; `:24` says server keys = `.mcp.json` keys (violated by `scrapling` vs `ScraplingServer` — only saved at runtime by `validate_invariants.py` `_MCP_JSON_KEY_ALIASES = {"ScraplingServer": "scrapling"}`).
- Skill frontmatter references ~47 unique `mcp__*` tools (many DataForSEO/Scrapling) — more than the registry's 33 enumerate.

**P1-13 — Higgsfield.** `generate-images/SKILL.md` frontmatter: `status: active`,
`mcp__higgsfield__generate_image` `required: true`, `mcp__higgsfield__job_status` optional. Tests keep
Higgsfield out of `.mcp.json` deliberately. F-24 compares `.mcp.json` keys to `registry.servers` keys, so
Higgsfield must NOT be added under `registry.servers` (would trip F-24 orphan_inventory).

## 3. DECISIONS already made (do NOT re-litigate)

- **D1 = Registry → match code.** Rewrite the 12 mismatched registry entries to the code's exact `rule`
  text + align severity. PRESERVE the displaced original design rules (the "WRONG" column above + D-01..D-03,
  M-01, M-02) by moving them into a NEW top-level registry array `deferred_design_rules` (same object shape,
  add `"status": "deferred"`, `"note": "cross-sheet join rule; not yet enforced at validate_invariants row
  level — consistency_check tool scope"`). Do not delete them — they encode design.md §17.2 intent.
- Higgsfield stays OUT of `.mcp.json` and OUT of `registry.servers`; represent it as an external user dep.

## 4. FILE MAP

- Modify: `schemas/cross-sheet-invariants.json` (rewrite 12 `rule`+`severity`; add `deferred_design_rules`)
- Modify: `mcp-tool-registry.json` (dataforseo lock 2.8.9→2.8.10; add missing skill-used tools; scrapling alias field; external_user_dependencies)
- Modify: `schemas/mcp-tool-registry.schema.json` (allow `deferred_design_rules`? NO — that's the invariants schema; here: update version const wording, allow alias + external dep fields)
- Modify: `schemas/cross-sheet-invariants.json` may need its own `$schema`/top-level to allow `deferred_design_rules` — check `additionalProperties` at root (it declares `additionalProperties` — confirm it permits the new key or add it to the schema-of-schema if one exists).
- Modify: `scripts/validation/validate_invariants.py` ONLY if the docstring count ("24 hand-coded rules") needs a note — do NOT change check behavior.
- Modify: `skills/production/generate-images/SKILL.md` (add external-dep preflight note; no tool removal)
- Create/Modify test: `tests/schemas/test_cross_sheet_invariants_sync.py` (add semantic-binding test; fix severity blind spot)
- Create test: `tests/schemas/test_mcp_registry_versions_match_mcp_json.py`
- Create test: `tests/schemas/test_skill_mcp_tools_exist_in_registry.py`
- Create test: `tests/skills/test_generate_images_external_dep.py`

## 5. TASKS (TDD)

### PART A — P0-01 (commit 1)

**Task 1.1 — Semantic-binding test (RED).** Add to `tests/schemas/test_cross_sheet_invariants_sync.py`:

```python
import openpyxl

def _code_rule_meta() -> dict[str, dict]:
    """Invoke each implemented check on an empty workbook + tmp workspace and
    capture its canonical id/rule/severity from the returned result dict."""
    import tempfile, pathlib
    wb = openpyxl.Workbook()
    if wb.active is not None:
        wb.remove(wb.active)            # truly empty -> checks SKIP but still return rule/severity
    out: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as td:
        ws_root = pathlib.Path(td)
        (ws_root / "projects" / "demo" / "_state").mkdir(parents=True, exist_ok=True)
        for fn in validate_invariants._RULE_FUNCTIONS:
            res = fn(wb, "demo", workspace_root=ws_root)
            out[res["id"]] = {"rule": res["rule"], "severity": res["severity"]}
    return out

def test_registry_rule_text_binds_to_implementation():
    """Every IMPLEMENTED F-ID's registry `rule` text MUST equal the string the
    implementation returns. Prevents the silent semantic drift where F-01 means
    'status enum' in code but 'url subset' in the registry."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    reg = {r["id"]: r for r in schema["rules"]}
    code = _code_rule_meta()
    mism = []
    for rid, meta in code.items():
        if rid not in reg:
            continue  # Direction-A test already guards missing-from-schema
        if reg[rid]["rule"].strip() != meta["rule"].strip():
            mism.append(f"{rid}: registry={reg[rid]['rule']!r} vs code={meta['rule']!r}")
    assert not mism, "cross-sheet-invariants.json rule text drifted from implementation:\n" + "\n".join(mism)

def test_registry_severity_binds_to_implementation():
    """Severity must match too — read from the RESULT dict (not a source regex),
    so helper-delegated severities (F-02/03/04) are no longer a blind spot."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    reg = {r["id"]: r["severity"] for r in schema["rules"]}
    code = _code_rule_meta()
    mism = [f"{rid}: registry={reg[rid]!r} vs code={m['severity']!r}"
            for rid, m in code.items() if rid in reg and reg[rid] != m["severity"]]
    assert not mism, "severity drift:\n" + "\n".join(mism)
```

- [ ] **Step 1:** add the two tests above.
- [ ] **Step 2:** Run `python3 -m pytest tests/schemas/test_cross_sheet_invariants_sync.py -q`.
      Expected: FAIL — the 12 mismatched IDs + F-04 severity listed.
- [ ] **Step 3 (GREEN):** edit `schemas/cross-sheet-invariants.json`: for each of F-01,02,03,04,05,08,09,
      10,11,12,13,14, set `rule` to the exact code text (table §2) and `severity` to the code severity
      (F-04 → `CRITICAL`). Move each displaced ORIGINAL rule (the WRONG-column text) + the existing
      `D-01,D-02,D-03,M-01,M-02` objects into a new top-level `"deferred_design_rules": [ ... ]` array,
      adding `"status":"deferred"` + the `"note"` from §3 to each. Keep `computed_by` on the deferred
      copies; on the now-code-matching active entries set `computed_by` to `"validate_invariants"`.
- [ ] **Step 4:** Run the same test → PASS. Then run the FULL suite → still ≥1449 + your new tests.
      (Watch the OLD `test_severity_consistency_for_implemented_rules` — if it now contradicts, replace its
      body to delegate to `_code_rule_meta()` rather than the source regex.)
- [ ] **Step 5:** `git add -A && git commit -m "fix(governance): bind cross-sheet-invariants.json rule text+severity to implementation (P0-01)"`

### PART B — P0-03 (commit 2)

**Task 1.2 — version lock test (RED→GREEN).** Create `tests/schemas/test_mcp_registry_versions_match_mcp_json.py`:

```python
import json, re, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _dataforseo_version_from_mcp_json() -> str:
    cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    args = cfg["mcpServers"]["dataforseo"]["args"]
    m = re.search(r"dataforseo-mcp-server@([0-9][0-9.]*)", " ".join(args))
    assert m, "could not find dataforseo-mcp-server@<ver> in .mcp.json"
    return m.group(1)

def test_dataforseo_version_lock_matches_mcp_json():
    reg = json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))
    lock = reg["servers"]["dataforseo"]["version_lock"]
    assert lock == _dataforseo_version_from_mcp_json(), (
        f"registry dataforseo version_lock={lock!r} != .mcp.json version "
        f"{_dataforseo_version_from_mcp_json()!r}")
```

- [ ] Run → FAIL (2.8.9 != 2.8.10). Fix: set `mcp-tool-registry.json` `servers.dataforseo.version_lock`
      = `"2.8.10"`; update `schemas/mcp-tool-registry.schema.json` description that hardcodes `'2.8.9'`
      (make it reference the current lock or drop the specific number). Run → PASS.

**Task 1.3 — skill-tools-in-registry test (RED→GREEN).** Create
`tests/schemas/test_skill_mcp_tools_exist_in_registry.py`: parse every `skills/**/SKILL.md`
frontmatter `mcp_tools.required` + `.optional`; normalize the alias `mcp__ScraplingServer__X` →
`scrapling__X` and `mcp__<server>__<tool>` → registry tool key; EXCLUDE `mcp__higgsfield__*` (external,
Task 1.5); assert every required tool exists in the registry. Run → FAIL (missing DataForSEO/Scrapling
tools). Fix: add the missing tool entries to `mcp-tool-registry.json` under the right server with minimal
capability metadata matching the schema (`schemas/mcp-tool-registry.schema.json` `servers[].tools[]` shape).
Re-run → PASS.

**Task 1.4 — scrapling alias.** Add an explicit alias field to the registry's `scrapling` server entry
(e.g. `"mcp_json_key": "ScraplingServer"`) and update `schemas/mcp-tool-registry.schema.json` to permit it;
add an assertion in Task 1.3's test (or a small new test) that for every `.mcp.json` server key K, either K
is a registry server key OR some registry server's `mcp_json_key == K`. Run → PASS.

- [ ] **Commit 2:** `git commit -am "fix(governance): sync MCP registry version + tools + scrapling alias to runtime (P0-03)"`

### PART C — P1-13 (commit 3)

**Task 1.5 — external user dependency.** Add a top-level `"external_user_dependencies"` object to
`mcp-tool-registry.json` (NOT under `servers`): e.g.
`{"higgsfield": {"transport": "user_external", "not_in_mcp_json": true, "tools": ["generate_image","job_status"], "required_by_skills": ["generate-images"], "note": "user-level MCP; plugin does not install it"}}`.
Update `schemas/mcp-tool-registry.schema.json` to allow this top-level key. Add
`tests/skills/test_generate_images_external_dep.py`:

```python
import json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_generate_images_higgsfield_declared_as_external():
    reg = json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))
    ext = reg.get("external_user_dependencies", {}).get("higgsfield", {})
    assert "generate_image" in (ext.get("tools") or []), "Higgsfield generate_image must be declared external"
    assert "higgsfield" not in reg.get("servers", {}), "Higgsfield must NOT be a plugin .mcp.json server (F-24)"

def test_generate_images_skill_preflight_mentions_external():
    txt = (ROOT / "skills/production/generate-images/SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"higgsfield", txt, re.I) and re.search(r"external|user-level|preflight", txt, re.I)
```

- [ ] Run → FAIL. Fix: add the external dep block + a short preflight section in
      `generate-images/SKILL.md` stating Higgsfield is a user-level MCP that must exist in the user env, and
      the skill fails clearly if absent. Run → PASS.
- [ ] **Commit 3:** `git commit -am "feat(governance): represent Higgsfield as external user MCP dependency + preflight (P1-13)"`

## 6. TEST GATE (must all hold before reporting DONE)

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/schemas/test_cross_sheet_invariants_sync.py \
  tests/schemas/test_mcp_registry_versions_match_mcp_json.py \
  tests/schemas/test_skill_mcp_tools_exist_in_registry.py \
  tests/skills/test_generate_images_external_dep.py -v
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # ≥1449 passed, 8 skipped (+ new)
python3 -c "import json; json.load(open('mcp-tool-registry.json')); json.load(open('schemas/cross-sheet-invariants.json')); print('JSON ok')"
```

Also sanity-run drift-check on a real project to prove no verdict regression (read-only):
```bash
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace \
  python3 -c "from scripts.validation import validate_invariants as v; print('rule fns:', len(v._RULE_FUNCTIONS))"
```

## 7. OUT OF SCOPE (do NOT touch — other phases own these)

- `dump_workspace.py` / workspace schemas / portfolio cap (Phase 2)
- commands/*.md / hooks/*.json (Phase 3)
- `validate_schema.py` FormatChecker / events.schema / additionalProperties (Phase 4)
- transaction.py / workflow_runner.py / events_writer.py (Phase 5)
- docs counts / brand-onboarding / templates (Phase 6)
- Do NOT change any `check_F_*` BEHAVIOR — only the registry, schema wording, registry tests, and the
  generate-images preflight text.

## 8. COMPLETION REPORT (fill in and return to the manager)

```
# Phase 1 Completion Report
- Branch: fix/codex-audit-phase-1-governance | Base: <sha> | Head: <sha>
- Status: DONE | BLOCKED | PARTIAL
- Findings closed: [P0-01, P0-03, P1-13] | deferred: [...]
- Commits: <sha> fix(governance) … ; <sha> … ; <sha> …
- Tests: full suite = "<N passed, M skipped>"; new tests: [the 4 files]; all green? Y/N
- drift-check sanity: rule fns count = <n>; any verdict regression seen? Y/N
- Deviations / judgment calls (e.g. exact alias field name, tool metadata): <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>
```
