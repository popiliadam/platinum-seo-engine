# Phase 15 W3 — Cross-Repo + Pipeline + MCP Audit Brief

> **Karar Verici:** Fresh session (15. ardışık, Phase 15 W2 tamamlandı → W3 devam)
> **Tarih:** 2026-05-05
> **Bağlam:** Phase 15 W2 workspace audit PUSHED (60e851d, 20 phase consecutive).
> **Worker tip:** `general-purpose` Agent — audit read-only (Write/Edit/Bash echo-redirect YOK).

---

## Section 1: Verify State (W3 Baseline — 2026-05-05 doğrulandı)

| Metrik | Değer | Kaynak |
|---|---|---|
| Engine HEAD | `1da7cf0` (v1.0.0 closeout, unchanged) | doğrulandı |
| Workspace HEAD | `60e851d` (Phase 15 W2 audit) | doğrulandı |
| Engine commits | 61 | `git log --oneline \| wc -l` |
| requirements.txt deps | 4 (jsonschema + pytest + openpyxl + pyyaml) | doğrulandı |
| check_budget.py path | `scripts/budget/check_budget.py` | doğrulandı (NOT scripts/check_budget.py) |
| .env file | EXISTS in engine root | security check scope |
| CI actions | actions/checkout@v4 + setup-python@v5 | SemVer pin (not SHA) |
| PSEO_WORKSPACE_ROOT | env var in reporting scripts | path resolution pattern |

**Pre-dispatch findings:**
- F-W3-pre-1: `check_budget.py` path correction — at `scripts/budget/check_budget.py` not `scripts/check_budget.py`. Worker W-C4 brief path updated accordingly.
- F-W3-pre-2: `.env` file exists in engine root — security check needed (G-16).

---

## Section 2: Hedef + Deliverable

**Hedef:** Cross-repo dependency + pipeline compliance + security + external deps + CI + MCP + cost/budget audit.
7 kategori × 5-10 alt-check. Read-only.

**Deliverable:**
```
/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/
v1-audit-2026-05-05/03-cross-repo-pipeline-mcp/
├── cat14-dependency.md
├── cat15-spec-compliance.md
├── cat16-security-kvkk.md
├── cat17-external-dependency.md
├── cat18-ci-pipeline.md
├── cat19-mcp-integration.md
└── cat20-cost-budget.md
```

7 alt-report manager tarafından workspace'e yazılır.

**Atomic 20'inci kanıt aday:** Phase 7+...+15W2+**15W3** = 21 phase consecutive.

---

## Section 3: Worker Dispatch (4 Paralel Audit Worker)

Engine root: `/Users/apple/Documents/platinum-seo-engine`
Workspace root: `/Users/apple/Documents/platinum-seo-workspace`
demo-dental project: `/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental`

### Worker W-C1 — Kategori 14+15: Dependency + Spec Compliance

**Kategori 14: Engine ↔ Workspace Dependency**

PSEO_WORKSPACE_ROOT env var usage pattern:
```bash
grep -rn "PSEO_WORKSPACE_ROOT\|PSEO_PORTFOLIO_ROOT\|workspace_root" \
  /Users/apple/Documents/platinum-seo-engine/scripts/ | grep -v "__pycache__\|\.pyc" | head -20
```

Path hardcoding check (no absolute paths to workspace in engine):
```bash
grep -rn "platinum-seo-workspace\|/Documents/.*demo-dental\|/Users/.*workspace" \
  /Users/apple/Documents/platinum-seo-engine/skills/ \
  /Users/apple/Documents/platinum-seo-engine/scripts/ \
  --include="*.py" --include="*.md" --include="*.json" | grep -v "__pycache__" | head -20
```

workspace_root resolution logic (confirm env-var based):
```bash
grep -n "PSEO_WORKSPACE_ROOT\|os.environ\|getenv" \
  /Users/apple/Documents/platinum-seo-engine/scripts/reporting/portfolio_overview.py | head -15
grep -n "PSEO_WORKSPACE_ROOT\|os.environ\|getenv" \
  /Users/apple/Documents/platinum-seo-engine/scripts/state/events_writer.py | head -15
```

8-slug consistency check (engine knows only abstract slug, not demo-dental literal):
```bash
# Slug pattern: should use variable/config, not hardcoded "demo-dental"
grep -rn '"demo-dental"\|demo-dental_slug\|slug.*demo-dental' \
  /Users/apple/Documents/platinum-seo-engine/scripts/ | grep -v "__pycache__" | head -10

# How does engine discover project slug? (via active.json or env var)
grep -rn "active\.json\|project_id\|project_slug" \
  /Users/apple/Documents/platinum-seo-engine/scripts/ | grep -v "__pycache__" | head -15
```

active.json pattern (workspace → engine context):
```bash
cat /Users/apple/Documents/platinum-seo-workspace/shared/active.json 2>/dev/null || \
  echo "shared/active.json not found"
ls /Users/apple/Documents/platinum-seo-workspace/shared/ 2>/dev/null
```

**Kategori 15: Spec §17 + §18 13-Madde Compliance**

Spec §17 + §18 acceptance criteria check (v1 release must have 13/13 PASS):
```bash
grep -n "§17\|§18\|acceptance_criteria\|acceptance criteria" \
  /Users/apple/Documents/platinum-seo-engine/docs/CONTEXT_LEDGER.md | head -20
grep -n "§17\|§18" \
  /Users/apple/Documents/platinum-seo-engine/docs/PHASE_STATUS.md 2>/dev/null | head -20
```

v1 acceptance criteria from AUDIT_KICKOFF_v1.md (if exists):
```bash
cat /Users/apple/Documents/platinum-seo-engine/AUDIT_KICKOFF_v1.md 2>/dev/null || \
  find /Users/apple/Documents/platinum-seo-engine -name "AUDIT_KICKOFF*" | head -5
```

RELEASE_NOTES_v1.0.0.md check (13/13 criteria listed?):
```bash
cat /Users/apple/Documents/platinum-seo-engine/RELEASE_NOTES_v1.0.0.md 2>/dev/null | head -80
```

Phase 14 deliverable verification (spec §18 madde 7):
```bash
# Check if v1-audit-2026-05-05/01-engine-repo/ + 02-workspace-repo/ exist
ls /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/
```

**Output format (W-C1 → manager):**
```markdown
## W-C1 Audit Findings

### Kategori 14: Engine ↔ Workspace Dependency
- PSEO_WORKSPACE_ROOT usage: [env-var based / hardcoded]
- Hardcoded workspace paths in engine: [0 PASS / XX FAIL]
- active.json pattern: [present / absent]
- Slug resolution: [env/config-driven PASS / hardcoded FAIL]

### Kategori 15: Spec §17+§18 Compliance
- RELEASE_NOTES_v1.0.0.md: [present / absent]
- §17+§18 criteria: [13/13 PASS / XX/13]
- AUDIT_KICKOFF_v1.md: [present / absent]
- Notable findings: [list]
```

---

### Worker W-C2 — Kategori 16+17: Security + KVKK + External Dependency

**Kategori 16: Security + KVKK**

Secret grep (CRITICAL — check_secrets.sh komutunu kopyala, yoksa manual):
```bash
/Users/apple/Documents/platinum-seo-engine/scripts/security/check_secrets.sh \
  /Users/apple/Documents/platinum-seo-engine 2>&1 | head -40
```

If check_secrets.sh fails, manual grep:
```bash
grep -rn "sk-[a-zA-Z0-9]\{20,\}\|AKIA[A-Z0-9]\{16\}\|ghp_[a-zA-Z0-9]\{36\}" \
  /Users/apple/Documents/platinum-seo-engine/ \
  --exclude-dir=".git" --exclude-dir="__pycache__" | grep -v "\.env\.example\|check_secrets" | head -20

grep -rn "password.*=.*['\"][^'\"]\{8,\}\|api_key.*=.*['\"][^'\"]\{8,\}" \
  /Users/apple/Documents/platinum-seo-engine/ \
  --include="*.py" --include="*.json" --include="*.yml" \
  --exclude-dir=".git" --exclude-dir="__pycache__" | grep -v "example\|test\|\.env" | head -20
```

.env file check (should NOT be committed):
```bash
git -C /Users/apple/Documents/platinum-seo-engine check-ignore .env && echo ".env GITIGNORED (PASS)" || echo ".env NOT gitignored (FAIL)"
git -C /Users/apple/Documents/platinum-seo-engine log --all --full-history -- ".env" | head -5
# Check if .env was ever committed:
git -C /Users/apple/Documents/platinum-seo-engine log --oneline --all -- ".env" | head -5
```

.env content check (is it empty template or has real values?):
```bash
# Only check structure, NOT the values
grep -c "=" /Users/apple/Documents/platinum-seo-engine/.env 2>/dev/null && \
  grep "^[A-Z_]*=" /Users/apple/Documents/platinum-seo-engine/.env | sed 's/=.*/=<REDACTED>/' 2>/dev/null | head -10
```

.gitignore coverage:
```bash
cat /Users/apple/Documents/platinum-seo-engine/.gitignore | grep -E "\.env|secret|credential|*.key" | head -10
```

KVKK consent check (demo-dental data — does any workspace data contain personal health identifiers?):
```bash
# Check inbox data for PII patterns (patient names, TC No, phone)
grep -rn "\b[0-9]\{11\}\b\|hasta.*ad[ıi]\|patient.*name\|T\.C\." \
  /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/inbox/ \
  --include="*.json" --include="*.csv" --include="*.md" 2>/dev/null | grep -v "__pycache__" | head -10
```

**Kategori 17: External Dependency**

requirements.txt pinning:
```bash
cat /Users/apple/Documents/platinum-seo-engine/requirements.txt
# Check: are versions pinned (>=) or exact (==)?
```

Python version compatibility:
```bash
python3 --version
# Check if engine requires specific Python version
grep -rn "python_requires\|python3\." /Users/apple/Documents/platinum-seo-engine/setup.py 2>/dev/null | head -5
grep -rn "python-version" /Users/apple/Documents/platinum-seo-engine/.github/workflows/ci.yml | head -5
```

GitHub Actions SemVer vs SHA pin:
```bash
grep "uses:" /Users/apple/Documents/platinum-seo-engine/.github/workflows/ci.yml
# Expected: @v4/@v5 SemVer (not SHA — both acceptable for internal tools)
# RED flag: @main or unpinned
```

MCP server dependency versions:
```bash
jq '.' /Users/apple/Documents/platinum-seo-engine/.mcp.json
# Check MCP server command/args for version locks
```

openpyxl version check (master.xlsx ops depend on this):
```bash
python3 -c "import openpyxl; print('openpyxl:', openpyxl.__version__)"
python3 -c "import jsonschema; print('jsonschema:', jsonschema.__version__)"
python3 -c "import pytest; print('pytest:', pytest.__version__)"
```

**Output format (W-C2 → manager):**
```markdown
## W-C2 Audit Findings

### Kategori 16: Security + KVKK
- Secret grep: [0 hits PASS / XX hits FAIL]
- .env gitignored: [PASS/FAIL]
- .env ever committed: [NO PASS / YES FAIL]
- .env structure: [XX vars, names only]
- KVKK PII: [0 hits PASS / concern FAIL]
- Notable findings: [list]

### Kategori 17: External Dependency
- requirements.txt: 4 deps [OK], pins: [>= soft / == exact]
- Python version: [X.X]
- CI python-version: [X.X]
- GitHub Actions pins: [SemVer / SHA / unpinned]
- MCP servers: [version/command]
- Notable findings: [list]
```

---

### Worker W-C3 — Kategori 18+19: CI Pipeline + MCP Integration

**Kategori 18: CI Pipeline Run History**

CI workflow structure:
```bash
cat /Users/apple/Documents/platinum-seo-engine/.github/workflows/ci.yml
```

CI step count and modes:
```bash
grep -n "name:\|continue-on-error\|run:" /Users/apple/Documents/platinum-seo-engine/.github/workflows/ci.yml | head -50
```

GitHub Actions run history (requires gh CLI):
```bash
gh run list --repo popiliadam/platinum-seo-engine --limit 15 2>/dev/null | head -30
# If gh not available:
echo "gh CLI check: $(which gh 2>/dev/null || echo 'not found')"
```

Latest run status:
```bash
gh run view --repo popiliadam/platinum-seo-engine 2>/dev/null | head -30
```

CI step verdicts (strict vs report-only breakdown):
```bash
# From ci.yml: which steps are continue-on-error: false (strict)?
grep -A3 "continue-on-error" /Users/apple/Documents/platinum-seo-engine/.github/workflows/ci.yml | head -30
```

**Kategori 19: MCP Integration Audit**

MCP server full config:
```bash
python3 -m json.tool /Users/apple/Documents/platinum-seo-engine/.mcp.json
```

MCP server tool inventory (3 servers: ScraplingServer, dataforseo, gsc):
```bash
# For each server, check what command is used and what env vars are required
jq '.mcpServers | keys' /Users/apple/Documents/platinum-seo-engine/.mcp.json
jq '.mcpServers.gsc' /Users/apple/Documents/platinum-seo-engine/.mcp.json
jq '.mcpServers.dataforseo' /Users/apple/Documents/platinum-seo-engine/.mcp.json
jq '.mcpServers.ScraplingServer' /Users/apple/Documents/platinum-seo-engine/.mcp.json
```

Paket-spec env naming convention (env vars must follow paket-spec):
```bash
# From .env.example: GOOGLE_APPLICATION_CREDENTIALS + DATAFORSEO_USERNAME + DATAFORSEO_PASSWORD + SCRAPLING_BIN
# Check if .mcp.json env references match .env.example
jq '.mcpServers | .. | .env? | select(. != null)' /Users/apple/Documents/platinum-seo-engine/.mcp.json 2>/dev/null
```

MCP wrapper pattern check (skills use MCP via python, not direct):
```bash
grep -rn "mcp\|MCP\|DataForSEO\|ScraplingServer" \
  /Users/apple/Documents/platinum-seo-engine/skills/ \
  --include="*.md" | grep -v "docs\|memory\|__pycache__" | head -15
```

**Output format (W-C3 → manager):**
```markdown
## W-C3 Audit Findings

### Kategori 18: CI Pipeline
- ci.yml steps: XX total
- Strict steps (continue-on-error: false): [list]
- Report-only steps (continue-on-error: true): [list]
- Latest run status: [SUCCESS/FAIL]
- Run history (last 10): [table]
- AMBER signals: [list]

### Kategori 19: MCP Integration
- Servers: 3 [OK/FAIL]
- ScraplingServer: [command + env vars]
- dataforseo: [command + env vars]
- gsc: [command + env vars]
- Env naming (paket-spec): [PASS/FAIL]
- Skills use MCP via wrapper: [PASS/note]
- Notable findings: [list]
```

---

### Worker W-C4 — Kategori 20: Cost + Budget Audit

**Kategori 20: DataForSEO Credit Usage + Budget**

check_budget.py exists and runs:
```bash
# NOTE: check_budget.py is at scripts/budget/ NOT scripts/ root
python3 /Users/apple/Documents/platinum-seo-engine/scripts/budget/check_budget.py --help 2>/dev/null | head -20 || \
  python3 /Users/apple/Documents/platinum-seo-engine/scripts/budget/check_budget.py 2>/dev/null | head -20
```

estimated_credits per skill (budget convention):
```bash
grep -rn "estimated_credits\|budget_credits\|max_credits" \
  /Users/apple/Documents/platinum-seo-engine/skills/ \
  --include="*.md" | grep -v "__pycache__" | head -20
```

Budget field in project.config.json:
```bash
python3 -c "
import json
cfg = json.load(open('/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/config/project.config.json'))
dfs = cfg.get('dataforseo', {})
print('dataforseo config:', json.dumps(dfs, indent=2))
"
```

DataForSEO budget_credits_per_day (schema check):
```bash
jq '.properties.dataforseo' /Users/apple/Documents/platinum-seo-engine/schemas/project-config.schema.json 2>/dev/null | head -20
```

Skill estimated_credits summary (count skills that declare budget):
```bash
grep -rh "estimated_credits" \
  /Users/apple/Documents/platinum-seo-engine/skills/ \
  --include="*.md" | sort | uniq -c | sort -rn | head -20
```

Budget enforcement in skills (does any skill check budget before running?):
```bash
grep -rn "check_budget\|budget_check\|credits_remaining" \
  /Users/apple/Documents/platinum-seo-engine/skills/ \
  --include="*.md" | head -10
grep -rn "check_budget\|budget_check\|credits_remaining" \
  /Users/apple/Documents/platinum-seo-engine/scripts/ \
  --include="*.py" | grep -v "__pycache__" | head -10
```

Actual DFS usage from events.jsonl (provenance events with dfs source):
```bash
python3 -c "
import json
events = []
with open('/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/_state/events.jsonl') as f:
    for line in f:
        events.append(json.loads(line))

# Count DFS-related events
dfs_events = [e for e in events if 'dfs' in str(e.get('source','')).lower() or 
              'dataforseo' in str(e.get('source','')).lower() or
              'dfs' in str(e.get('event_type','')).lower()]
print(f'DFS-related events: {len(dfs_events)}')
for e in dfs_events[:5]:
    print(f'  run_id={e.get(\"run_id\")}, type={e.get(\"event_type\")}, source={e.get(\"source\")}')
"
```

**Output format (W-C4 → manager):**
```markdown
## W-C4 Audit Findings

### Kategori 20: Cost + Budget
- check_budget.py: [present + runnable / error]
- estimated_credits in skills: XX/43 skills declare budget
- project.config.json dataforseo: [budget_credits_per_day: XX]
- Budget enforcement in skills: [YES/NO]
- DFS events in events.jsonl: XX
- Notable findings: [list]
```

---

## Section 4: DURUR Conditions

| # | Durum | Aksiyon |
|---|---|---|
| D-1 | Secret found in committed files | STOP → RED finding, escalate |
| D-2 | .env committed in git history | STOP → RED finding, escalate |
| D-3 | Real patient PII in workspace data | STOP → KVKK concern, escalate |
| D-4 | Spec §17+§18 < 11/13 criteria | AMBER → document gap |
| D-5 | CI latest run FAIL | AMBER → document failing step |

---

## Section 5: Acceptance Gates

| Gate | Kategori | Pass Kriteri |
|---|---|---|
| G-14 | Dependency | PSEO_WORKSPACE_ROOT env-var based (no hardcoded paths) |
| G-15 | Spec §17+§18 | 13/13 criteria met (RELEASE_NOTES + Phase 14 deliverables) |
| G-16 | Security | 0 secrets in code + .env gitignored + 0 PII in workspace |
| G-17 | External dep | requirements.txt 4 deps + CI SemVer/SHA pinned (no @main) |
| G-18 | CI Pipeline | Last run SUCCESS + strict mode 3 governance steps intact |
| G-19 | MCP | 3 servers configured + paket-spec env naming + wrapper pattern |
| G-20 | Cost/Budget | check_budget.py runnable + estimated_credits in DataForSEO skills |

**Atomic 20'inci kanıt PASS kriteri:** Tüm 7 gate PASS/AMBER + workspace commit.

---

## Section 6: Commit Protocol (Workspace Only)

**Engine repo: 0 yeni commit** (Q-CD-01 paterni 18→19 uygulama hedef, DECISIONS unchanged).
**.mcp.json: byte-byte unchanged** (F-16 invariant 22→23 commit hedef).

**Workspace commit:**
```
chore: Phase 15 W3 cross-repo+pipeline+MCP audit (7 kategori, 21 phase consecutive)
```

events.jsonl +1 audit event (run_id=64):
```json
{
  "event_kind": "audit",
  "audit_action": "accessed",
  "audit_target": "cross_repo:1da7cf0+60e851d:phase_15_w3_audit",
  "actor": "manager",
  "run_id": 64,
  "notes": "Phase 15 W3 cross-repo+pipeline+MCP audit. 7 kategori. Gate verdicts TBD.",
  "schema_version": "1.0",
  "project_id": "demo-dental"
}
```

---

## Section 7: Süleyman Onay Matrisi (W3)

**Otonom yetki aktif** — W3 push otonom (Phase 15 blanket yetki). W3 RED gate (D-1 secret / D-2 .env committed) bulunursa: Süleyman'a rapor + karar sor.

---

## Section 8: 9-Boyutlu Schema Cross-Check (Audit Adaptation, 14'üncü ardışık aday)

**Boyut 1:** project-config.schema.json `dataforseo.budget_credits_per_day` field defined?
`jq '.properties.dataforseo.properties.budget_credits_per_day' schemas/project-config.schema.json`

**Boyut 2:** events.schema.json `audit_target` format (string? pattern?):
`jq '.properties.audit_target' schemas/events.schema.json`

**Boyut 3:** cross-sheet-invariants.json rules key (not invariants) — confirmed W2:
`jq '.rules | length' schemas/cross-sheet-invariants.json` → 20

**Boyut 4 (KRİTİK):** events.schema.json event_type 10-enum intact:
`jq '.properties.event_type.enum | length' schemas/events.schema.json` → 10

**Boyut 5:** skill-frontmatter.schema.json `estimated_credits` field defined?
`jq '.properties.estimated_credits' schemas/skill-frontmatter.schema.json 2>/dev/null || echo "not in frontmatter schema"`

**Boyut 6:** project-config.schema.json `gsc` section:
`jq '.properties.gsc' schemas/project-config.schema.json | keys`

**Boyut 7:** workflow-run.schema.json compliance (CI pipeline runs):
`jq '.properties' schemas/workflow-run.schema.json | keys`

**Boyut 8:** project-memory.schema.json phase tracking:
`jq '.properties | keys' schemas/project-memory.schema.json`

**Boyut 9:** master-excel.schema.json `schema_version`:
`jq '.schema_version' schemas/master-excel.schema.json`

**14'üncü ardışık aday** (Section 8-13 complete brief writing).

---

## Section 9: Brief Internal Consistency (13'üncü Uygulama)

| Check | Beklenen | Doğrulama |
|---|---|---|
| Kategori count | 7 (14-20) | Section 3: W-C1(2)+W-C2(2)+W-C3(2)+W-C4(1) = 7 ✓ |
| Gate count | 7 (G-14..G-20) | Section 5 ✓ |
| Alt-report count | 7 | Section 2 deliverable ✓ |
| Worker count | 4 (W-C1..W-C4) | Section 3 ✓ |
| Atomic kanıt | 20'inci | W2 19'uncu + W3 = 20 ✓ |
| check_budget.py path | scripts/budget/ | F-W3-pre-1 correction ✓ |

**6/6 PASS ✓**

---

## Section 10: Brief Infrastructure Convention (12'inci Uygulama, Lesson 38 v2 9'uncu Ardışık)

**Cross-repo paths (lesson 38 v2: frozen assumption YASAK):**

| Kaynak | Yol | Pre-dispatch Verify |
|---|---|---|
| Engine root | `/Users/apple/Documents/platinum-seo-engine` | 1da7cf0 HEAD confirmed |
| Workspace root | `/Users/apple/Documents/platinum-seo-workspace` | 60e851d HEAD confirmed |
| check_budget.py | `scripts/budget/check_budget.py` | ls confirmed (NOT scripts/check_budget.py) |
| .env | `/Users/apple/Documents/platinum-seo-engine/.env` | EXISTS (check gitignore) |
| CI workflow | `.github/workflows/ci.yml` | single file confirmed |
| MCP config | `.mcp.json` | 469B 3-server F-16 confirmed |

**Lesson 38 v2 9'uncu ardışık alt-boyut aday:**
1-8 önceki (SSH/HTTPS + partial inspect + test path + dynamic state + runtime + env-specific + audit ≠ kanıt + ls shallow subdir count)
**9'uncu aday:** check_budget.py path — scripts/check_budget.py vs scripts/budget/check_budget.py. Brief expects scripts/ root; actual is scripts/budget/. Lesson: script path assumptions YASAK, `find` ile verify ZORUNLU.

---

## Section 11: Brief CI Runtime Requirements (11'inci Uygulama)

| Kriter | Durum |
|---|---|
| Engine commit | YOK → CI Run trigger YOK |
| Workspace commit | VAR (audit output only) → workspace CI yok |
| gh CLI | Gerekli for CI run history (kategori 18). `which gh` ile verify. |
| python3 | Mevcut (openpyxl/jsonschema tests için) |
| jq command | Mevcut (W2'de confirmed) |

**CI baseline:** Run 25392730652 SUCCESS (engine, W3-W3-β). Phase 15 W1 audit workspace commit = no engine CI trigger (engine unchanged). W3 audit workspace commit → same pattern → no CI trigger.

---

## Section 12: Brief Skill Spec Invocation Behavior (10'uncu Uygulama, Audit Adaptation)

**W3 audit = cross-repo reads + gh CLI + security grep + python stdlib. Skill execution YOK.**

| Check | Protocol |
|---|---|
| Secret grep | `check_secrets.sh` or manual grep pattern |
| CI run history | `gh run list` (requires gh CLI + authenticated session) |
| MCP config | `jq` + python3 json.tool |
| Budget check | `python3 scripts/budget/check_budget.py` |
| events.jsonl | python3 json.loads per line |

**Lesson 68 pattern (schema-first for this brief):** Worker W-C4 should verify check_budget.py interface before assuming `--help` works. If script has no argparse, `--help` may raise error — use `python3 check_budget.py 2>&1` to capture all output.

**Q-W3W3α-EVENTSCHEMA-01 scope (W3 audit):** Worker W-C3 MCP integration audit will cross-check if monitoring-weekly SKILL.md references `event_type: audit_run` — confirming the docs inconsistency found in W2. Not a red flag, documentation only.

---

## Section 13: Brief CI Step Verdict Integrity (9'uncu Uygulama, Audit Adaptation)

**W3 = cross-repo audit → engine commit YOK → CI trigger YOK.**

Worker W-C3 Kategori 18 audits the CI pipeline itself:
- Step inventory: strict (continue-on-error: false) vs report-only (continue-on-error: true)
- Last run verdict: CI Run 25392730652 was SUCCESS (Phase 14 W3-W3-β, 7/7 steps GREEN)
- W3 audit will verify: is current ci.yml consistent with the `7 strict steps` milestone from Phase 14?

**Expected CI step breakdown (Phase 14 W3-W3-β final state):**
- 3 strict governance steps: drift-check + schema-validate + glossary-audit (continue-on-error: false)
- 4 report-only steps: pytest + plugin-agnostik-grep + secret-grep + frontmatter-compile (continue-on-error: true OR always-run)

Worker W-C3 should independently verify this count from ci.yml source.

---

## Versiyon + Meta

| Alan | Değer |
|---|---|
| Brief version | Phase 15 W3 v1.0 |
| Yazılma tarihi | 2026-05-05 |
| Karar verici session | 15. ardışık |
| 14-boyutlu cross-check | Section 8+9+10+11+12+13 COMPLETE |
| Lesson 38 v2 | 9'uncu ardışık aday (check_budget.py path + ls shallow) |
| Q-CD-01 | 18→19 uygulama hedef (DECISIONS unchanged) |
| F-16 invariant | 22→23 commit hedef |
| Önceki phase | Phase 15 W2 (workspace repo, 20'inci kanıt) |
| Sonraki phase | Phase 15 W4 (discipline + lesson audit) |
