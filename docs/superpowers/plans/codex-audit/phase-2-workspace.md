# Phase 2 — Workspace Contract (ENGINE ONLY) — Worker Brief

## 0. READ FIRST (worker onboarding)

- You are a **fresh worker session**. This brief is complete — do NOT explore the whole repo.
- Engine repo: `/Users/apple/Documents/platinum-seo-engine`.
- **This phase is ENGINE-ONLY. You must NOT modify the workspace repo** (`/Users/apple/Documents/platinum-seo-workspace`).
  You only READ workspace files for read-only verification. The live migration of workspace
  `project.config.json` files is a SEPARATE manager-overseen step — do NOT attempt it here.
- **Invoke `superpowers:test-driven-development`** and follow it. Then `superpowers:verification-before-completion`.
- **Branch:** `git checkout -b fix/codex-audit-phase-2-workspace`. Base it on `main` IF Phase 1
  (`fix/codex-audit-phase-1-governance`) has been merged to main; otherwise base it on
  `fix/codex-audit-phase-1-governance` (so you inherit Phase 1). Confirm with `git log --oneline -3`.
- **Hard rules** (same as Phase 1): NO subagents (Task/Agent fail here — "Prompt is too long"); atomic
  commits; never commit `AUDIT_FINDINGS_FOR_CLAUDE_CODE.md`; never touch `main`, never push; preserve
  unrelated files.
- **Baseline:** `PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q`
  must stay ≥ **1457 passed, 8 skipped** (post-Phase-1) + your new tests. (If you branched off `main`
  WITHOUT Phase 1, the baseline is 1449/8 — note which in your report.)

## 1. GOAL + findings this phase closes

**Goal:** Make the workspace state contract honest — the manager-session summary must read the
canonical active-project key, and the portfolio schema must admit the real portfolio size.

- **P0-02** — `scripts/state/dump_workspace.py` reads legacy `slug`; the live `shared/active.json`
  uses `active_project` → the manager summary errors out unless `--project` is passed.
- **P0-04 (engine part only)** — `schemas/portfolio-config.schema.json` caps `active_projects` at 8;
  the live portfolio has 10 → schema validation FAILs. Raise to 12 (D2).
- **P2-05** — clarify (doc) that config `schema_version` (1.5) is distinct from the engine release
  version (v1.9.4).

## 2. EVIDENCE (verified)

- `scripts/state/dump_workspace.py` `_resolve_slug` (~lines 45–65): `slug = data.get("slug")` then
  raises `"shared/active.json has no 'slug' key"` if absent. Live `active.json` =
  `{"active_project": "dentnotion", "updated_at": "..."}`. Cross-check: `commands/pseo-active.md`
  WRITES `active_project`, and `commands/pseo-schema-audit.md` READS `.active_project` via jq — so
  dump_workspace is the lone laggard. ADR-032 treats `active_project` as canonical.
- `tests/scripts/test_dump_workspace.py` `_write_active_json` (~line 120–125) writes
  `{"slug": slug}` (masks the bug); `test_dump_uses_active_json_when_slug_none` relies on it.
- `schemas/portfolio-config.schema.json`: `properties.active_projects.maxItems = 8`. Live
  `shared/portfolio.json` has 10 `active_projects` (validation: "active_projects is too long").
- `schemas/project-config.schema.json`: `schema_version` const = "1.5" with a long description of
  the migration history; engine README says v1.9.4. The two version axes are not explicitly contrasted.

## 3. DECISIONS already made (do NOT re-litigate) — D2

- Raise `active_projects.maxItems` 8 → **12**, and add a description/comment noting it is a
  **documented soft cap** (not a hard product limit; raised when the active portfolio reached 10).
- dump_workspace: read `active_project` FIRST, fall back to legacy `slug` with a stderr warning
  (backward compatibility).

## 4. FILE MAP

- Modify: `scripts/state/dump_workspace.py` (`_resolve_slug`)
- Modify: `tests/scripts/test_dump_workspace.py` (fixture → `active_project`; + canonical test; + legacy-fallback test)
- Modify: `schemas/portfolio-config.schema.json` (`active_projects.maxItems` 8→12 + description note)
- Create: `tests/schemas/test_portfolio_config_maxitems.py`
- Modify (P2-05, doc-only): `schemas/project-config.schema.json` `schema_version.description` (append a sentence contrasting config-schema-version vs engine-version) — no behavior change.

## 5. TASKS (TDD)

### Part A — P0-02 (commit 1)

- [ ] **2.1 RED.** In `tests/scripts/test_dump_workspace.py`: change `_write_active_json` to write
  `{"active_project": slug}` (canonical). Add:

```python
def test_dump_reads_active_project_canonical(dump_module, tmp_path):
    _make_workspace(tmp_path, slug="demo")
    (tmp_path / "shared").mkdir(parents=True, exist_ok=True)
    (tmp_path / "shared" / "active.json").write_text(
        json.dumps({"active_project": "demo", "updated_at": "2026-06-03T00:00:00Z"}), encoding="utf-8")
    assert dump_module.dump_workspace(workspace_root=tmp_path, project_slug=None)["project"] == "demo"

def test_dump_legacy_slug_still_resolves(dump_module, tmp_path):
    _make_workspace(tmp_path, slug="demo")
    (tmp_path / "shared").mkdir(parents=True, exist_ok=True)
    (tmp_path / "shared" / "active.json").write_text(json.dumps({"slug": "demo"}), encoding="utf-8")
    assert dump_module.dump_workspace(workspace_root=tmp_path, project_slug=None)["project"] == "demo"
```

  Run `python3 -m pytest tests/scripts/test_dump_workspace.py -q` → `test_dump_reads_active_project_canonical`
  FAILS (code reads `slug`); the edited fixture also makes `test_dump_uses_active_json_when_slug_none` fail.
- [ ] **2.2 GREEN.** In `_resolve_slug`, replace the `slug = data.get("slug")` block with:

```python
    slug = data.get("active_project") or data.get("slug")
    if not slug:
        raise FileNotFoundError(
            f"shared/active.json has no 'active_project' key: {active}"
        )
    if "active_project" not in data and "slug" in data:
        print(
            f"warning: shared/active.json uses legacy 'slug' key; rename to "
            f"'active_project' ({active})",
            file=sys.stderr,
        )
    return str(slug)
```

  Run → all `test_dump_workspace.py` tests pass.
- [ ] **2.3 Commit 1:** `git commit -am "fix(state): dump_workspace reads canonical active_project, legacy slug fallback (P0-02)"`

### Part B — P0-04 maxItems (commit 2)

- [ ] **2.4 RED.** Create `tests/schemas/test_portfolio_config_maxitems.py`. Build a VALID
  `active_projects` item by matching the schema's `properties.active_projects.items.required`
  (read the schema; use the live `shared/portfolio.json` entries as the template — fields:
  slug, display_name, domain, market, workspace_path, profile, platform, priority, last_sync_at):

```python
import json, pathlib
from jsonschema import Draft7Validator
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "portfolio-config.schema.json").read_text(encoding="utf-8"))

def _item(i):
    return {"slug": f"p{i}", "display_name": f"P{i}", "domain": f"https://p{i}.com/",
            "market": "TR", "workspace_path": f"projects/p{i}", "profile": ["e-commerce"],
            "platform": "wordpress", "priority": i + 1, "last_sync_at": "2026-06-03T00:00:00Z"}

def _portfolio(n):
    return {"schema_version": "1.1", "active_projects": [_item(i) for i in range(n)]}

def test_maxitems_is_12():
    assert SCHEMA["properties"]["active_projects"]["maxItems"] == 12

def test_twelve_projects_validate():
    assert not list(Draft7Validator(SCHEMA).iter_errors(_portfolio(12)))

def test_thirteen_projects_fail():
    assert list(Draft7Validator(SCHEMA).iter_errors(_portfolio(13)))
```

  Run → `test_maxitems_is_12` FAILS (currently 8). If the item shape is wrong, fix `_item` to satisfy
  the schema's required keys (do NOT relax the schema).
- [ ] **2.5 GREEN.** In `schemas/portfolio-config.schema.json` set `active_projects.maxItems: 12` and
  add to that property's `description`: "soft cap (raised 8→12 when active portfolio reached 10); not
  a hard product limit — raise further as the portfolio grows." Run → pass + full suite green.
- [ ] **2.6 Commit 2:** `git commit -am "fix(schema): raise portfolio active_projects maxItems 8->12 (P0-04 engine)"`

### Part C — P2-05 doc (commit 3)

- [ ] **2.7.** Append one clarifying sentence to `schemas/project-config.schema.json`
  `schema_version.description`: that this is the **config contract version** (bumped by migration
  scripts), distinct from the **engine release version** (e.g. v1.9.4); they version different things.
  No behavior change; no new test required (optional: assert the description contains "engine" if trivial).
- [ ] **2.8 Commit 3:** `git commit -am "docs(schema): clarify config schema_version vs engine version (P2-05)"`

## 6. TEST GATE (all must hold)

```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m pytest tests/scripts/test_dump_workspace.py tests/schemas/test_portfolio_config_maxitems.py -v
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 -m pytest -q   # >= 1457/8 + new
# READ-ONLY end-to-end proofs (these only READ the live workspace, never write it):
PSEO_WORKSPACE_ROOT=/Users/apple/Documents/platinum-seo-workspace python3 scripts/state/dump_workspace.py --json | head    # now SUCCEEDS (dentnotion), no "no 'slug' key"
python3 scripts/validation/validate_schema.py /Users/apple/Documents/platinum-seo-workspace/shared/portfolio.json schemas/portfolio-config.schema.json    # now PASSES (no "is too long")
```

## 7. OUT OF SCOPE (do NOT touch)

- **Do NOT migrate workspace `project.config.json` files** (the 1.3/1.4→1.5 migration of 8 live
  projects is a SEPARATE manager-overseen step on live client data).
- **Do NOT modify the workspace repo at all** — read-only proofs only.
- Commands/hooks (Phase 3); validate_schema FormatChecker/events.schema/additionalProperties (Phase 4);
  transaction/workflow_runner/events_writer (Phase 5); docs counts/brand-onboarding/templates (Phase 6).

## 8. COMPLETION REPORT (fill in and return to the manager)

```
# Phase 2 Completion Report
- Branch: fix/codex-audit-phase-2-workspace | Base: <main or phase-1 sha> | Head: <sha>
- Status: DONE | PARTIAL | BLOCKED
- Findings closed: [P0-02, P0-04(engine), P2-05] | deferred: [P0-04 workspace migration = separate step]
- Commits: <sha> fix(state)… ; <sha> fix(schema)… ; <sha> docs(schema)…
- Tests: full suite = "<N passed, M skipped>"; new tests: [test_portfolio_config_maxitems + 2 dump tests]; all green? Y/N
- Read-only proofs: dump_workspace --json now succeeds? Y/N ; portfolio validate_schema now passes? Y/N
- Confirm: workspace repo NOT modified (git -C /Users/apple/Documents/platinum-seo-workspace status --short unchanged by you)? Y/N
- Deviations / judgment calls: <...>
- Blockers / questions for manager: <none | ...>
- git diff --stat: <paste>
```
