# Codex Audit Remediation — MCP / Dependencies / Doc-Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate the 8 findings (P0-01…P2-08) from the 2026-06-04 Codex "MCP / dependencies / doc-hygiene" audit, fixing the two real defects (Pillow manifest gap, SF MCP HTTP transport) and permanently test-locking the documentation/contract drift so it cannot recur.

**Architecture:** Two-repo system. Engine = `/Users/apple/Documents/platinum-seo-engine` (the plugin/motor). Workspace = `/Users/apple/Documents/platinum-seo-workspace` (operational data/state). Every fix is TDD: write a failing guard test → make it pass → commit. Each finding's regression test stays in CI so the drift class never returns. Engine and workspace changes are kept in separate commits/repos.

**Tech Stack:** Python 3.14, pytest, jsonschema, openpyxl, Pillow (to be added), Claude Code plugin MCP (`.mcp.json` HTTP+stdio), GitHub Actions CI.

---

## Audit Verdict Summary (independently verified, 6 parallel agents, 2026-06-04)

| ID | Codex finding | Codex sev | **Verified verdict** | **Reassessed sev** | Action |
|----|---------------|-----------|----------------------|--------------------|--------|
| P0-02 | Pillow missing from requirements | P0 | **CONFIRMED** | **P1 / High** | Batch A1 — fix |
| P0-01 | SF MCP declared but not live-registered (`{url}` lacks `type:http`) | P0 | **CONFIRMED** | **Medium** | Batch A2 — fix (cascade) |
| P1-04A | whats-next `hooks:[SessionStart]` misleading | P1 | **CONFIRMED** (nuance) | Low | Batch B (B6 test) |
| P1-04B | load-context `manual:[/pseo-active]` overloaded | P1 | **CONFIRMED** | Low | Batch B (B6 test) |
| P1-05 | ARCHITECTURE.md cites fictional `plugin_version_constraint` | P1 | **CONFIRMED** | Cosmetic | Batch B3 — fix |
| P2-07 | marketplace.json stale pytest count (1427) | P2 | **CONFIRMED** | Cosmetic | Batch B4 — fix |
| P1-03 | `.codex/config.toml` not parity with `.mcp.json` | P1 | **PARTIAL** (framing REFUTED) | ~Zero | Batch C1 — accept/optional |
| P2-06 | portfolio `plugin_version:1.1.0` stale | P2 | **PARTIAL** (framing REFUTED) | P3 cosmetic | Batch C3 — accept/optional |
| P2-08 | workspace dirty operational state | P2 | **CONFIRMED** | Informational | Batch C2 — DECISION required |

**Why the severity downgrades are justified (evidence):**
- **P0-01 → Medium, not P0:** the underlying SF transport works — `scripts/util/sf_mcp_client.py` (an httpx Streamable-HTTP client) hits `:11435/mcp` directly, bypassing the plugin MCP layer; the live smoke test exercises that path. What is actually broken is (a) the *documented interactive* `/pseo-sf-crawl` flow that calls `mcp__sf__*` wrappers which only exist if the plugin registers `sf`, and (b) README/INSTALL promising `claude mcp list` shows `sf`. Optional feature, file-drop CSV fallback preserved (D-SF-07). Real bug, bounded blast radius.
- **P0-02 → P1/High, not P0:** Pillow absent from BOTH `requirements.txt` AND `requirements-lock.txt`; CI installs the lock (`ci.yml:29`) so CI is broken on a clean machine. But the local dev env has `PIL 12.1.1`, masking it; trivially fixed. CI-reproducibility defect, not data corruption.
- **P1-03 → ~zero, framing REFUTED:** `.codex/config.toml` is **git-ignored and never tracked** (`.gitignore:124-125` under `# External tool configs (out-of-scope, F-16 plugin agnostik)`). Codex is **not** a supported runtime (no AGENTS.md, zero codex mentions in install docs; product ships as a Claude Code plugin). "Higgsfield parity" is a category error — Higgsfield is in neither config. Nothing to bring to parity.
- **P2-06 → P3, framing REFUTED:** the schema **already** documents it — `portfolio-config.schema.json:26` description = `"Plugin version this portfolio config was authored against (advisory; not enforced)."` The only residual nit is that the field *name* `plugin_version` reads like a live requirement. Schema-documented advisory metadata; non-breaking.

---

## File Structure / Impact Map

**Batch A1 — Pillow (engine):**
- Modify: `requirements.txt` (add `Pillow>=10.0`)
- Modify: `requirements-lock.txt` (regenerate with `Pillow==<resolved>`)
- Create test: `tests/ci/test_pillow_declared.py` (root-cause guard)

**Batch A2 — SF MCP type:http (engine, CASCADE — controlled F-16 break):**
- Modify: `.mcp.json:21-23` (add `"type": "http"` to `sf`)
- Modify: `tests/skills/test_brand_onboarding.py:56` (`MCP_JSON_BYTES_BASELINE = 543` → new) + line 28 comment + any md5 constant
- Modify: `docs/ARCHITECTURE.md:154` (543B + md5 → new)
- Modify: `docs/INSTALL.md:3` (543B reference → new)
- Modify: `docs/DECISIONS.md` (append ADR-040 controlled break)
- Modify: `README.md:196` (`.mcp.json` snippet → include `type:http`)
- Create test: `tests/schemas/test_mcp_http_transport_declared.py` (root-cause guard)
- **Manual gate:** re-run `claude mcp list` after plugin refresh — confirm `sf` now present.

**Batch B — Trigger + doc hygiene (engine):**
- B3 Modify: `docs/ARCHITECTURE.md:26` (`plugin_version_constraint` → `schema_version`)
- B3 Create test: `tests/docs/test_architecture_no_fictional_config.py`
- B4 Modify: `.claude-plugin/marketplace.json:16` (remove hardcoded pytest count)
- B4 Create test: `tests/docs/test_marketplace_no_hardcoded_pytest_count.py`
- B6 Modify: `skills/meta/whats-next/SKILL.md:42` + `skills/governance/load-context/SKILL.md:43` (trigger truthfulness)
- B6 Create test: `tests/skills/test_trigger_declaration_parity.py` (closes the structural blind spot for P1-04A+B)

**Batch C — Accept / decision (no auto-edit):**
- C1: `.codex/config.toml` — optional 1-line local disclaimer (git-ignored, never committed)
- C2: workspace dirty state — **Süleyman decision** (commit / gitignore / archive)
- C3: portfolio `plugin_version` rename — optional cross-repo P3 (engine schema + workspace data)

---

## BATCH A — Real Fixes (must-do)

### Task A1: Pillow dependency manifest (P0-02)

**Files:**
- Create: `tests/ci/test_pillow_declared.py`
- Modify: `requirements.txt`
- Modify: `requirements-lock.txt`

- [ ] **Step 1: Write the failing test**

`tests/ci/test_pillow_declared.py`:
```python
"""Guard: Pillow must be declared in the dependency manifests.

Root-cause regression guard for the 2026-06-04 Codex P0-02 finding. PIL is
imported unconditionally by scripts/util/iptc_metadata.py (R-78 AI-image
disclosure) and skills/production/generate-images (R-76 format cascade), but
piexif — though declared — does NOT pull Pillow transitively, so a clean
`pip install -r requirements-lock.txt` previously crashed pytest collection
with ModuleNotFoundError: No module named 'PIL'.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pillow_in_requirements() -> None:
    reqs = (ROOT / "requirements.txt").read_text().lower()
    assert "pillow" in reqs, (
        "Pillow must be declared in requirements.txt — PIL is a hard runtime "
        "dependency (iptc_metadata.py / generate-images) not pulled by piexif"
    )


def test_pillow_pinned_in_lock() -> None:
    lock = (ROOT / "requirements-lock.txt").read_text().lower()
    assert "pillow" in lock, (
        "Pillow must be pinned in requirements-lock.txt (CI installs the lock)"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/ci/test_pillow_declared.py -v`
Expected: FAIL on both — `Pillow must be declared in requirements.txt` / `...in requirements-lock.txt`.

- [ ] **Step 3: Add Pillow to requirements.txt**

Append to `requirements.txt` (keep alphabetical-ish grouping near `piexif`):
```
Pillow>=10.0
```

- [ ] **Step 4: Regenerate the lock the way its header mandates (clean venv, not bare freeze)**

Run:
```bash
cd /Users/apple/Documents/platinum-seo-engine
python3 -m venv /tmp/pseo-lock
/tmp/pseo-lock/bin/pip install --upgrade pip >/dev/null
/tmp/pseo-lock/bin/pip install -r requirements.txt
/tmp/pseo-lock/bin/pip freeze
```
Take the `pip freeze` output and paste the package lines UNDER the existing comment header (lines 1-18) of `requirements-lock.txt`, preserving that header verbatim (`test_lock_documents_generation_command_and_python_target` asserts `3.14`, `venv`, `requirements.txt` remain in it). Confirm a `Pillow==<resolved>` line now appears (e.g. `Pillow==12.1.1`).

- [ ] **Step 5: Run the Pillow guard + the lock-pinning + lock-doc tests**

Run: `python3 -m pytest tests/ci/test_pillow_declared.py tests/ci/test_requirements_lock.py -v`
Expected: PASS — Pillow declared + pinned; `test_every_base_requirement_is_pinned_in_lock` green; lock header preserved.

- [ ] **Step 6: Verify the original symptom is gone in a truly clean venv**

Run:
```bash
python3 -m venv /tmp/pseo-clean
/tmp/pseo-clean/bin/pip install -r requirements-lock.txt
/tmp/pseo-clean/bin/python -c "import PIL; print('PIL', PIL.__version__)"
/tmp/pseo-clean/bin/python -m pytest tests/util/test_iptc_metadata.py tests/util/test_piexif_smoke.py -q
```
Expected: PIL imports; both util tests PASS (no `ModuleNotFoundError`).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt requirements-lock.txt tests/ci/test_pillow_declared.py
git commit -m "fix(deps): declare Pillow in requirements + lock (clean-install/CI fix) [codex-audit P0-02]"
```

---

### Task A2: SF MCP HTTP transport + F-16 controlled break (P0-01)

> **CASCADE WARNING:** adding `"type": "http"` grows `.mcp.json` past its pinned 543-byte F-16 baseline, which IS enforced by `tests/skills/test_brand_onboarding.py` (`MCP_JSON_BYTES_BASELINE = 543` + md5). This is a deliberate "controlled break" exactly like ADR-039 (v1.8, 482B→543B). All baseline references must be re-synced in the SAME commit.

**Files:**
- Modify: `.mcp.json` (line 21-23)
- Create: `tests/schemas/test_mcp_http_transport_declared.py`
- Modify: `tests/skills/test_brand_onboarding.py` (lines 28, 56, + md5 if asserted)
- Modify: `docs/ARCHITECTURE.md:154`, `docs/INSTALL.md:3`, `README.md:196`
- Modify: `docs/DECISIONS.md` (append ADR-040)

- [ ] **Step 1: Write the failing root-cause guard test**

`tests/schemas/test_mcp_http_transport_declared.py`:
```python
"""Guard: HTTP MCP servers in .mcp.json must declare type:http.

Root-cause regression guard for the 2026-06-04 Codex P0-01 finding. Claude
Code defaults an entry's transport to stdio when `type` is absent; a bare
{"url": ...} entry (like `sf` since v1.8) therefore silently fails to register
and never appears in `claude mcp list`, even though the other 3 stdio servers
do. Any entry that has a `url` and no `command` MUST declare "type": "http".
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_url_only_mcp_servers_declare_http_type() -> None:
    cfg = json.loads((ROOT / ".mcp.json").read_text())
    for name, spec in cfg["mcpServers"].items():
        if "url" in spec and "command" not in spec:
            assert spec.get("type") == "http", (
                f"MCP server {name!r} has a url but no 'type': 'http' — Claude "
                f"Code defaults to stdio and the server fails to register"
            )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/schemas/test_mcp_http_transport_declared.py -v`
Expected: FAIL — `MCP server 'sf' has a url but no 'type': 'http'`.

- [ ] **Step 3: Edit `.mcp.json` — add type:http to sf**

Change lines 21-23 from:
```json
    "sf": {
      "url": "http://127.0.0.1:11435/mcp"
    }
```
to:
```json
    "sf": {
      "type": "http",
      "url": "http://127.0.0.1:11435/mcp"
    }
```

- [ ] **Step 4: Capture the NEW byte count + md5 (needed for baseline re-sync)**

Run:
```bash
cd /Users/apple/Documents/platinum-seo-engine
wc -c .mcp.json          # note NEW_BYTES (was 543)
md5 -q .mcp.json         # note NEW_MD5 (macOS); on Linux: md5sum .mcp.json
python3 -c "import json;json.load(open('.mcp.json'));print('valid json')"
```
Record `NEW_BYTES` and `NEW_MD5` — they feed Steps 5-7.

- [ ] **Step 5: Re-sync the F-16 byte baseline in the test**

In `tests/skills/test_brand_onboarding.py`:
- Line 56: `MCP_JSON_BYTES_BASELINE = 543` → `MCP_JSON_BYTES_BASELINE = <NEW_BYTES>`
- Line 28 comment: `.mcp.json byte sentinel pinned at 543 bytes / md5` → `... pinned at <NEW_BYTES> bytes / md5`
- If the test asserts an md5 literal anywhere (check around lines 50-60 and 485-495), update it to `<NEW_MD5>`. (Run the test in Step 8; if md5 is only computed-not-asserted, no change needed there.)

- [ ] **Step 6: Re-sync the doc baselines**

- `docs/ARCHITECTURE.md:154`: change `New baseline: 543B (was 482B); new md5 \`93523d41e14f90916fefb86d346bd702\`.` → `New baseline: <NEW_BYTES>B (was 543B at v1.8); new md5 \`<NEW_MD5>\` (v1.9.x SF type:http, ADR-040).`
- `docs/INSTALL.md:3`: change `F-16 invariant intentionally reset to 543B baseline at v1.8 per ADR-039` → `F-16 invariant reset to <NEW_BYTES>B at v1.9.x per ADR-040 (sf type:http; prior 543B at v1.8/ADR-039)`.
- `README.md:196`: update the `.mcp.json` snippet's `sf` entry to include `"type": "http"` so the doc matches the file.

- [ ] **Step 7: Append ADR-040 to `docs/DECISIONS.md`**

After the ADR-039 block, append:
```markdown
### ADR-040 — SF MCP HTTP transport made explicit (`type:http`); second controlled F-16 break

**Context:** v1.8 added `sf` to `.mcp.json` as `{"url": "..."}` (ADR-039, 543B). Claude Code defaults transport to stdio when `type` is absent, so `sf` silently failed to register — absent from `claude mcp list`, and the `/pseo-sf-crawl` skill's `mcp__sf__*` wrappers (plus README/INSTALL "should show sf connected") were broken. Codex audit 2026-06-04 P0-01.

**Decision:** Add `"type": "http"` to the `sf` entry. This is the second deliberate F-16 byte-invariant break since v1.5 (482B→543B at v1.8; 543B→<NEW_BYTES>B at v1.9.x). New baseline `<NEW_BYTES>B` + md5 `<NEW_MD5>`. The httpx client (`sf_mcp_client.py`, D-SF-14) was unaffected; this fix restores the plugin-registered `mcp__sf__*` path. F-16 drift resumes from the new baseline.
```

- [ ] **Step 8: Run the affected tests**

Run: `python3 -m pytest tests/schemas/test_mcp_http_transport_declared.py tests/skills/test_brand_onboarding.py tests/docs/test_count_consistency.py tests/scripts/test_validate_invariants_F16.py -v`
Expected: PASS — http-transport guard green; brand_onboarding byte/md5 baseline matches `<NEW_BYTES>`/`<NEW_MD5>`; count + F-16 invariant tests green.

- [ ] **Step 9: Manual empirical gate (NOT CI-automatable) — does the fix actually register sf?**

> The engine runs as an **installed plugin** (`plugin:platinum-seo-engine:*` in `claude mcp list`). Editing the repo `.mcp.json` updates the SOURCE; the installed plugin cache must be refreshed to pick it up. Refresh the plugin (reinstall / update via the marketplace, or restart Claude Code), then:
```bash
claude mcp list 2>&1 | grep -i sf
curl -sf -m 3 http://127.0.0.1:11435/mcp; echo "EXIT=$?"
```
Expected: an `sf` (or `plugin:platinum-seo-engine:sf`) line now APPEARS. If the SF GUI is off, its status is `down`/`failed to connect` (curl EXIT=7) — that is correct ("configured but down" ≠ "absent"). 
**If `sf` is STILL absent after type:http + plugin refresh:** the root cause is plugin-cache packaging, not transport — escalate: inspect the installed plugin copy under `~/.claude/plugins/.../`, confirm it shipped the new `.mcp.json`, and file a follow-up. Do NOT claim P0-01 resolved until `sf` appears in a real `claude mcp list`.

- [ ] **Step 10: Commit**

```bash
git add .mcp.json tests/schemas/test_mcp_http_transport_declared.py tests/skills/test_brand_onboarding.py docs/ARCHITECTURE.md docs/INSTALL.md docs/DECISIONS.md README.md
git commit -m "fix(mcp): declare sf type:http so it registers in claude mcp list; ADR-040 F-16 re-sync [codex-audit P0-01]"
```

---

## BATCH B — Doc / Contract Hygiene (should-do; permanently test-locked)

### Task B3: Remove fictional `plugin_version_constraint` from ARCHITECTURE.md (P1-05)

**Files:**
- Create: `tests/docs/test_architecture_no_fictional_config.py`
- Modify: `docs/ARCHITECTURE.md:26`

- [ ] **Step 1: Write the failing test**

`tests/docs/test_architecture_no_fictional_config.py`:
```python
"""Guard: ARCHITECTURE.md must not cite project.config.json fields that the
schema does not define (additionalProperties:false would reject them anyway).
Codex P1-05: 'plugin_version_constraint' is fictional — never in schema, never
in any of the 10 workspace configs, referenced only in docs.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_architecture_does_not_cite_plugin_version_constraint() -> None:
    arch = (ROOT / "docs/ARCHITECTURE.md").read_text()
    schema = json.loads((ROOT / "schemas/project-config.schema.json").read_text())
    allowed = set(schema.get("properties", {}).keys())
    assert "plugin_version_constraint" not in allowed  # sanity: still fictional
    assert "plugin_version_constraint" not in arch, (
        "ARCHITECTURE.md cites 'plugin_version_constraint', which is not a real "
        "project.config.json field; cite 'schema_version' (the field configs "
        "actually carry) instead"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/docs/test_architecture_no_fictional_config.py -v`
Expected: FAIL — `ARCHITECTURE.md cites 'plugin_version_constraint'`.

- [ ] **Step 3: Fix the doc line to cite the real field**

`docs/ARCHITECTURE.md:26` — change:
```
- Versionlama: Plugin SemVer (`plugin.json`); workspace proje config'leri `plugin_version_constraint` taşır.
```
to:
```
- Versionlama: Plugin SemVer (`plugin.json`); workspace proje config'leri `schema_version` taşır (config şema sürümü — şu an tüm projelerde `"1.5"`).
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/docs/test_architecture_no_fictional_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/ARCHITECTURE.md tests/docs/test_architecture_no_fictional_config.py
git commit -m "docs(architecture): cite real schema_version field, not fictional plugin_version_constraint [codex-audit P1-05]"
```

> NOTE: the frozen design spec `docs/superpowers/specs/2026-04-30-...-design.md:53` also mentions the field. Leave the spec untouched (it is an intentionally frozen historical artifact); the guard test targets ARCHITECTURE.md only.

---

### Task B4: Remove stale hardcoded pytest count from marketplace.json (P2-07)

**Files:**
- Create: `tests/docs/test_marketplace_no_hardcoded_pytest_count.py`
- Modify: `.claude-plugin/marketplace.json:16`

- [ ] **Step 1: Write the failing test**

`tests/docs/test_marketplace_no_hardcoded_pytest_count.py`:
```python
"""Guard: marketplace.json must not embed a hardcoded 'pytest NNNN passed'
count. The version-bump tool preserves the description body verbatim, so any
count silently rots every release (Codex P2-07: claimed 1427, real ~1582).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_hardcoded_pytest_count() -> None:
    mp = (ROOT / ".claude-plugin/marketplace.json").read_text()
    assert not re.search(r"pytest\s+\d{3,}\s+passed", mp), (
        "Remove the hardcoded 'pytest NNNN passed' string from marketplace.json "
        "— it is never reconciled with the real suite and rots every release"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/docs/test_marketplace_no_hardcoded_pytest_count.py -v`
Expected: FAIL — stale `pytest 1427 passed` present.

- [ ] **Step 3: Edit marketplace.json:16 — drop the count, keep the regression-clean claim qualitative**

Open `.claude-plugin/marketplace.json`, line 16. Remove only the `pytest 1427 passed + 11 skipped` fragment, replacing with a count-free phrasing, e.g. `full pytest suite green (regression sıfır; ...)`. Preserve the rest of the description body and valid JSON. (Do NOT introduce a new number — the whole point is no hardcoded count.)

- [ ] **Step 4: Run the guard + structural-count consistency**

Run: `python3 -m pytest tests/docs/test_marketplace_no_hardcoded_pytest_count.py tests/docs/test_count_consistency.py -v`
Expected: PASS — count gone; structural skill/command/schema counts still consistent.

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json tests/docs/test_marketplace_no_hardcoded_pytest_count.py
git commit -m "docs(marketplace): drop stale hardcoded pytest count; guard against recurrence [codex-audit P2-07]"
```

---

### Task B6: Trigger-declaration parity — fix whats-next + load-context, close the blind spot (P1-04A + P1-04B)

> One parity test drives BOTH fixes. It asserts that a skill's declared `triggers.manual` / `triggers.hooks` correspond to a command/hook that actually references the skill (or is explicitly marked advisory). This is the structural guard the suite lacked (schema types `hooks`/`manual` as free-form arrays with no wiring check).

**Files:**
- Create: `tests/skills/test_trigger_declaration_parity.py`
- Modify: `skills/meta/whats-next/SKILL.md:42`
- Modify: `skills/governance/load-context/SKILL.md:43`

- [ ] **Step 1: Write the failing parity test**

`tests/skills/test_trigger_declaration_parity.py`:
```python
"""Guard: skill frontmatter triggers must be truthful (Codex P1-04).

(A) Every triggers.manual "/pseo-X" must resolve to commands/X.md.
(B) Every triggers.hooks event must be an event some hook JSON actually binds.
This closes the blind spot where skill-frontmatter.schema.json types hooks/
manual as free-form arrays with zero wiring cross-check, letting whats-next
declare hooks:[SessionStart] (the SessionStart hook never invokes it) and
load-context declare manual:[/pseo-active] (that command only switches the
active-project marker).
"""
import json
import re
from pathlib import Path

import yaml  # pyyaml is already a dependency

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = ROOT / "commands"
HOOKS = ROOT / "hooks"


def _frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text()
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(m.group(1)) if m else {}


def _bound_hook_events() -> set[str]:
    events: set[str] = set()
    for hj in HOOKS.glob("*.json"):
        data = json.loads(hj.read_text())
        # plugin hook JSONs key the event at top level (e.g. {"SessionStart":[...]})
        events.update(k for k in data.keys() if k[:1].isupper())
    return events


def test_manual_triggers_resolve_to_real_commands() -> None:
    offenders = []
    for skill_md in ROOT.glob("skills/**/SKILL.md"):
        fm = _frontmatter(skill_md)
        for trig in (fm.get("triggers", {}) or {}).get("manual", []) or []:
            name = trig.lstrip("/").strip()
            if not name.startswith("pseo-"):
                continue
            cmd = COMMANDS / f"{name}.md"
            if not cmd.exists():
                offenders.append(f"{skill_md.relative_to(ROOT)} -> {trig} (no commands/{name}.md)")
                continue
            # The command must reference this skill OR the skill must not be the
            # sole owner of a command that does something unrelated.
            skill_dir = skill_md.parent.name
            if skill_dir not in cmd.read_text():
                offenders.append(
                    f"{skill_md.relative_to(ROOT)} declares manual {trig} but "
                    f"commands/{name}.md never references skill '{skill_dir}'"
                )
    assert not offenders, "Untruthful manual triggers:\n" + "\n".join(offenders)


def test_hook_triggers_name_a_bound_event() -> None:
    bound = _bound_hook_events()
    offenders = []
    for skill_md in ROOT.glob("skills/**/SKILL.md"):
        fm = _frontmatter(skill_md)
        for ev in (fm.get("triggers", {}) or {}).get("hooks", []) or []:
            if ev not in bound:
                offenders.append(f"{skill_md.relative_to(ROOT)} -> hooks:[{ev}] not bound by any hooks/*.json")
    assert not offenders, "Hook events declared but not bound:\n" + "\n".join(offenders)
```

- [ ] **Step 2: Run test to verify it fails (on exactly the two P1-04 findings)**

Run: `python3 -m pytest tests/skills/test_trigger_declaration_parity.py -v`
Expected: FAIL —
- `load-context ... declares manual /pseo-active but commands/pseo-active.md never references skill 'load-context'` (P1-04B).
- (If `SessionStart` IS bound by `session-start.json`, the hook test may pass on event-binding alone; the manual test is the firm failure. Confirm which fails and proceed.)

- [ ] **Step 3: Fix load-context (P1-04B) — drop the misleading manual trigger**

`skills/governance/load-context/SKILL.md:43` — remove `/pseo-active` from `manual`. The natural-language triggers (`"load context"`, `"wakeup"`, `"manager session aç"`) already cover invocation. Change:
```yaml
  manual: ["/pseo-active"]
```
to (if other manual entries exist keep them; if this was the only one, use an empty list or the skill's own intended surface):
```yaml
  manual: []
```
> Switching the active project (`/pseo-active`) and loading a 15KB manager-context bundle are deliberately distinct ops — do NOT make `/pseo-active` chain load-context.

- [ ] **Step 4: Fix whats-next (P1-04A) — point the hook trigger at reality**

`skills/meta/whats-next/SKILL.md:42` — the actual advisory pointer to whats-next lives in `hooks/user-prompt-submit.json` ("Drift router: … invoke the meta:whats-next skill"), NOT `session-start.json`. Change:
```yaml
  hooks: ["SessionStart"]
```
to:
```yaml
  hooks: ["UserPromptSubmit"]   # advisory routing only — the hook SUGGESTS, never invokes (see skill body)
```

- [ ] **Step 5: Run test to verify both pass**

Run: `python3 -m pytest tests/skills/test_trigger_declaration_parity.py -v`
Expected: PASS — manual triggers truthful; hook events bound.

- [ ] **Step 6: Guard against breaking existing skill tests**

Run: `python3 -m pytest tests/skills/governance/test_load_context.py tests/skills/ -k "whats_next or load_context or trigger" -v`
Expected: PASS (no test asserted the old `/pseo-active` manual literal for load-context; if one does, update it to match the corrected frontmatter).

- [ ] **Step 7: Commit**

```bash
git add tests/skills/test_trigger_declaration_parity.py skills/meta/whats-next/SKILL.md skills/governance/load-context/SKILL.md
git commit -m "fix(skills): make trigger declarations truthful + parity guard [codex-audit P1-04]"
```

---

## BATCH C — Accept / Decision (no auto-edit)

### C1 — `.codex/config.toml` parity (P1-03): ACCEPT (recommended)

Evidence: file is **git-ignored, never tracked** (`.gitignore:124-125`, "External tool configs (out-of-scope, F-16 plugin agnostik)"); Codex is not a supported runtime (no AGENTS.md; product ships as a Claude Code plugin); Higgsfield is in neither config (category error). No fix needed.
**Optional (purely local, not committed — file is git-ignored):** prepend one comment line to `.codex/config.toml`:
```toml
# Local dev convenience only — NOT shipped, NOT parity-tracked with .mcp.json (F-16 out-of-scope). Source of truth: .mcp.json
```
Recommendation: **accept**; do the 1-liner only if you personally use Codex locally.

### C2 — Workspace dirty operational state (P2-08): **DECISION REQUIRED (Süleyman)**

Verified: 7 modified tracked files (events.jsonl ×3 are **append-only** ✓ constraint satisfied; master.xlsx ×2; consistency_report.json; active.json switched demo-dental→demo-construction-insaat-tr) + 10 untracked deliverables (2 PDF, 2 HTML, 1 audit .md, 5 report .md). Engine repo is clean. This is legitimate production output — **do NOT revert**.
Options to choose from:
1. **Commit as a workspace state snapshot** — `chore(state): snapshot 2026-06-04 (demo-construction/demo-baby/demo-dental outputs + active switch)`. Keeps history.
2. **Gitignore the heavy deliverables** (PDF/HTML) like the existing raw-SF-CSV precedent, commit only state+reports.
3. **Leave local** — no git action.
Recommendation: **(1) commit state + reports, (2) gitignore PDF/HTML** if they're regenerable. Keep entirely separate from the engine commits above.

### C3 — Portfolio `plugin_version` rename (P2-06): OPTIONAL P3 (cross-repo)

Schema already documents it as `"authored against (advisory; not enforced)"` — non-breaking. Only the field *name* is mildly confusing. If you want the cleanup:
- Engine: in `schemas/portfolio-config.schema.json` rename property `plugin_version` → `authored_against_version` (+ keep the description).
- Workspace: rename the key in `shared/portfolio.json:5` in lockstep (else validation breaks).
- Two separate commits, two repos.
Recommendation: **defer/accept** — lowest priority, touches the live workspace; do only as a dedicated tidy-up if naming clarity matters to you.

---

## Validation Commands (run from engine repo after Batch A+B)

Full clean-venv reproduction (proves P0-02 closed):
```bash
python3 -m venv /tmp/pseo-clean
/tmp/pseo-clean/bin/pip install -r requirements-lock.txt
/tmp/pseo-clean/bin/pytest -q
```
Expected: all pass, no `ModuleNotFoundError: PIL`.

Targeted parity + new guards:
```bash
python3 -m pytest \
  tests/ci/test_pillow_declared.py \
  tests/ci/test_requirements_lock.py \
  tests/schemas/test_mcp_http_transport_declared.py \
  tests/skills/test_brand_onboarding.py \
  tests/skills/test_trigger_declaration_parity.py \
  tests/docs/test_architecture_no_fictional_config.py \
  tests/docs/test_marketplace_no_hardcoded_pytest_count.py \
  tests/docs/test_count_consistency.py \
  tests/scripts/test_validate_invariants_F16.py \
  -q
```

MCP manual gate (post plugin refresh):
```bash
claude mcp list 2>&1 | grep -i sf            # sf must now appear
curl -sf -m 3 http://127.0.0.1:11435/mcp; echo "EXIT=$?"   # EXIT=7 if GUI off = configured-but-down (OK)
```

---

## Self-Review (writing-plans checklist)

1. **Spec coverage:** all 8 findings mapped — P0-02→A1, P0-01→A2, P1-05→B3, P2-07→B4, P1-04A+B→B6, P1-03→C1, P2-08→C2, P2-06→C3. ✓
2. **Placeholder scan:** `<NEW_BYTES>`/`<NEW_MD5>` are intentional runtime-computed values with the exact command to obtain them (Step A2-4), not lazy placeholders. All test code is complete. ✓
3. **Type consistency:** test module names, the `MCP_JSON_BYTES_BASELINE` constant, and the `url`/`type` keys match across A2 tasks; `schema_version` is the real field confirmed in all 10 configs. ✓
4. **Cascade completeness:** A2 enumerates the ONLY hardcoded 543 baseline (`test_brand_onboarding.py`) + 3 doc refs (ARCHITECTURE.md:154, INSTALL.md:3, DECISIONS.md) + README snippet; `validate_invariants.py`/`test_monitoring_weekly.py` confirmed to NOT hardcode 543. ✓

---

## Suggested Execution Order

1. **A1 Pillow** (CI-blocking on clean machine; smallest, highest leverage).
2. **A2 SF MCP** (cascade — do as one atomic commit; manual gate before claiming resolved).
3. **B6 triggers**, **B3 architecture**, **B4 marketplace** (independent doc/contract guards; any order).
4. **C2 workspace** — ask Süleyman, separate repo/commit.
5. **C1 / C3** — accept or optional, lowest priority.

## Constraints (carried from handoff)
- Do NOT push without explicit Süleyman approval.
- Do NOT revert/clean workspace dirty changes (production data).
- Keep engine and workspace fixes in separate commits/repos.
- Small commits by concern (one per task above).
