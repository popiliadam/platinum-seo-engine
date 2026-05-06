# Phase 15 W5 — Strategic + UX + i18n Audit Brief

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Final Phase 15 audit wave — atıl alan (dead code/orphan), UX smoke test, i18n compliance, convention codification, and v1.1+ backlog prioritization. READ-ONLY audit: no file mutations except writing report files.

**Architecture:** 3 parallel workers (W-E1 + W-E2 + W-E3). Engine + workspace repos read-only. Write 5 alt-reports to workspace output directory. This is the final wave before the executive summary (00-master-report.md).

**Tech Stack:** Python (grep, file analysis), bash, find, wc. No MCP server calls needed.

---

## Section 1: Worker Assignment

| Worker | Kategoriler | Scope |
|---|---|---|
| W-E1 | 26 + 27 | Atıl alan tespiti + UX smoke test |
| W-E2 | 28 + 29 | i18n audit + Convention codifier |
| W-E3 | 30 | v1.1+ backlog priority |

Output directory:
`/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/05-strategic-ux-i18n/`

Report files: `cat26-atil-alan.md`, `cat27-ux-smoke.md`, `cat28-i18n.md`, `cat29-convention-codifier.md`, `cat30-v11-backlog.md`

**Key paths:**
- Engine root: `/Users/apple/Documents/platinum-seo-engine/`
- Workspace root: `/Users/apple/Documents/platinum-seo-workspace/`
- Skills: `/Users/apple/Documents/platinum-seo-engine/skills/` (8 categories: discovery, governance, ingestion, meta, planning, production, publishing, reporting)
- Scripts: `/Users/apple/Documents/platinum-seo-engine/scripts/` (52 Python files)
- Rules: `/Users/apple/Documents/platinum-seo-engine/rules/` (18 files)
- Schemas: `/Users/apple/Documents/platinum-seo-engine/schemas/` (18 schemas)
- WORKFLOWS.md: `/Users/apple/Documents/platinum-seo-engine/docs/WORKFLOWS.md` (132 lines)
- OPEN_QUESTIONS.md: `/Users/apple/Documents/platinum-seo-engine/docs/OPEN_QUESTIONS.md`
- Prior W1-W4 reports: `outputs/reports/v1-audit-2026-05-05/01-engine-repo/` through `04-discipline-lesson/`

---

## Section 2: Output Format

```markdown
# Kategori N: [Name]
**Audit Date:** 2026-05-05
**Phase:** 15 W5 — Strategic + UX + i18n Audit
**Verdict:** PASS | AMBER | RED
**Worker:** W-Ex

## N.1 [Sub-check]
...

## Gate G-N Verdict: [PASS|AMBER|RED]
| Sub-check | Result |
|---|---|
...
```

---

## Section 3: Worker Briefs

---

### W-E1: Kategori 26 + 27

#### Kategori 26: Atıl Alan Tespiti (Dead Code + Orphan References)

**Purpose:** Find unused scripts, orphaned templates, dead config entries, or duplicate artifacts.

**26.1 — Script Inventory vs Skills**

Count scripts per domain and check if every transform script has a corresponding skill:
```bash
ls /Users/apple/Documents/platinum-seo-engine/scripts/discovery/
ls /Users/apple/Documents/platinum-seo-engine/scripts/ingestion/
ls /Users/apple/Documents/platinum-seo-engine/scripts/planning/
ls /Users/apple/Documents/platinum-seo-engine/scripts/production/
ls /Users/apple/Documents/platinum-seo-engine/scripts/publishing/
ls /Users/apple/Documents/platinum-seo-engine/scripts/reporting/
```

For each transform script (e.g., `cannibalization_transform.py`), check if a corresponding skill folder exists:
```bash
ls /Users/apple/Documents/platinum-seo-engine/skills/discovery/
```

Identify any orphaned transform scripts (script exists but no skill folder) or orphaned skills (skill folder exists but no transform script). Note: not all skills require a transform script (some are prompt-only).

**26.2 — Template Inventory**

```bash
find /Users/apple/Documents/platinum-seo-engine/templates -type f | sort
find /Users/apple/Documents/platinum-seo-engine/templates -type f | wc -l
```

For each template, check if it's referenced in at least 1 SKILL.md:
```bash
grep -rl "templates/" /Users/apple/Documents/platinum-seo-engine/skills/ | head -20
```

Identify templates with 0 SKILL.md references (orphaned templates).

**26.3 — Schema Inventory**

```bash
ls /Users/apple/Documents/platinum-seo-engine/schemas/
ls /Users/apple/Documents/platinum-seo-engine/schemas/ | wc -l
```

Cross-check schemas vs WORKFLOWS.md or project.config.json. Find any schema file that's not referenced in any script, schema-validate, or SKILL.md:
```bash
for s in /Users/apple/Documents/platinum-seo-engine/schemas/*.json; do
  name=$(basename $s)
  count=$(grep -rl "$name" /Users/apple/Documents/platinum-seo-engine/ --include="*.py" --include="*.md" --include="*.json" 2>/dev/null | grep -v __pycache__ | grep -v ".git" | wc -l)
  echo "$count $name"
done
```

**26.4 — WORKFLOWS.md Stale Status Column**

```bash
grep -c "planned\|active\|deprecated" /Users/apple/Documents/platinum-seo-engine/docs/WORKFLOWS.md
head -50 /Users/apple/Documents/platinum-seo-engine/docs/WORKFLOWS.md
```

Expected: All 43 skills show `planned` (known stale from W2 audit). Confirm count. This is the Q-PHASE15-DOC-STALE-01 finding.

**26.5 — .bak or Temp Files**

```bash
find /Users/apple/Documents/platinum-seo-engine -name "*.bak" -o -name "*.tmp" -o -name "*.swp" | grep -v .git | head -10
find /Users/apple/Documents/platinum-seo-workspace -name "*.bak" -o -name "*.tmp" | grep -v .git | head -10
```

Expected: 0 orphaned temp files.

**Gate G-26 sub-checks:**
- Script vs skill alignment (orphan count)
- Template orphans (0-reference templates)
- Schema reference coverage
- WORKFLOWS.md stale status confirmed (known Q-PHASE15-DOC-STALE-01)
- No temp/bak files

---

#### Kategori 27: UX Smoke Test + Onboarding Completeness

**Purpose:** Audit from Süleyman's perspective — can a new user follow README+INSTALL+CONTRIBUTING to get started? Does the quick-start workflow make sense?

**27.1 — README.md Completeness**

```bash
cat /Users/apple/Documents/platinum-seo-engine/README.md
```

Check for: (a) Quick Start section, (b) Prerequisites, (c) Skill invocation example, (d) Workspace setup pointer, (e) Version badge (v1.0.0), (f) CI status badge.

Note any missing sections or outdated content.

**27.2 — INSTALL.md Completeness**

```bash
cat /Users/apple/Documents/platinum-seo-engine/docs/INSTALL.md
```

Check: (a) Python version requirement stated, (b) pip install instructions, (c) .env.example reference, (d) MCP server setup (3 servers), (e) Quick verification command.

**27.3 — CONTRIBUTING.md Completeness**

```bash
cat /Users/apple/Documents/platinum-seo-engine/docs/CONTRIBUTING.md
```

Check: (a) How to add a new skill, (b) Commit convention, (c) CI requirements, (d) Test requirements.

**27.4 — plugin.json or CLAUDE.md**

```bash
ls /Users/apple/Documents/platinum-seo-engine/plugin.json 2>/dev/null && echo "plugin.json: PRESENT" || echo "plugin.json: ABSENT"
ls /Users/apple/Documents/platinum-seo-engine/.claude/ 2>/dev/null && ls /Users/apple/Documents/platinum-seo-engine/.claude/
```

Check if engine has plugin.json (Phase 4 baseline schema artifact). Present or absent?

**27.5 — Workspace Quick Start**

```bash
cat /Users/apple/Documents/platinum-seo-workspace/README.md 2>/dev/null | head -60
```

Check: (a) workspace setup instructions, (b) engine plugin reference, (c) demo-dental pilot project pointer.

**27.6 — .env.example Completeness**

```bash
cat /Users/apple/Documents/platinum-seo-engine/.env.example
```

Expected 4 vars: GOOGLE_APPLICATION_CREDENTIALS, DATAFORSEO_USERNAME, DATAFORSEO_PASSWORD, SCRAPLING_BIN. Verify.

**Gate G-27 sub-checks:**
- README.md: Quick Start + badges + skill invocation example
- INSTALL.md: Python version + pip + .env.example + MCP setup
- CONTRIBUTING.md: new skill guide + commit convention + CI requirements
- plugin.json presence
- workspace README quick start
- .env.example 4 vars

---

### W-E2: Kategori 28 + 29

#### Kategori 28: i18n Audit

**Purpose:** Verify Turkish locale compliance — content_locale, market targeting, brand tone, YMYL formality.

**28.1 — project.config.json i18n Fields**

```bash
python3 -c "
import json
with open('/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/project.config.json') as f:
    config = json.load(f)
print('content_locale:', config.get('content_locale'))
print('location_code:', config.get('dataforseo', {}).get('location_code'))
print('location_name:', config.get('dataforseo', {}).get('location_name'))
print('language_code:', config.get('dataforseo', {}).get('language_code'))
print('ymyl_level:', config.get('ymyl_level'))
"
```

Expected: content_locale="tr-TR", location_code=2792 (Turkey), language_code="tr", ymyl_level="high".

**28.2 — Brand Tone in project.config.json**

```bash
python3 -c "
import json
with open('/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/project.config.json') as f:
    config = json.load(f)
brand = config.get('brand_identity', {})
print('formality:', brand.get('formality'))
print('tone_descriptors:', brand.get('tone_descriptors', []))
print('pronoun_preference:', brand.get('pronoun_preference'))
"
```

Expected for dental YMYL site: formality="formal", pronoun_preference="siz" (R-102 rule).

**28.3 — rules/content-quality.md i18n Rules**

```bash
grep -n "tr-TR\|Turkish\|Türkçe\|siz\|YMYL\|ymyl\|formality\|pronoun" /Users/apple/Documents/platinum-seo-engine/rules/content-quality.md | head -20
```

Verify R-102 (pronoun rule "siz" for YMYL) is present.

**28.4 — Production Content i18n Check**

Check the produced content in workspace for Turkish compliance:
```bash
ls /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/content/ 2>/dev/null && \
find /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/content -name "*.md" | head -5
```

If content files exist, spot-check first 50 lines for English content (should be Turkish for demo-dental):
```bash
find /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/content -name "*.md" | head -3 | xargs head -30 2>/dev/null
```

**28.5 — DataForSEO TR Config Compliance**

From W3 cat20-cost-budget.md (already written), verify:
- location_code: 2792 (Turkey)
- language_code: "tr"
Report as PASS (already confirmed in W3).

**Gate G-28 sub-checks:**
- content_locale="tr-TR"
- location_code=2792 (Turkey)
- ymyl_level="high"
- brand pronoun_preference="siz" or similar formal Turkish
- R-102 rule present in content-quality.md
- Produced content in Turkish (if available)

---

#### Kategori 29: Convention Codifier Paired Discipline

**Purpose:** Audit whether the convention codification discipline (lesson 11 v3.1) is consistently applied — that findings from prior phases are actually codified into rules/SKILL.mds/schemas, not just noted.

**29.1 — Lesson 11 v3.1 Codification Audit**

From W4 cat21 report (already written), Foundational Principles have 3 artifacts. Check that Phase 14 key findings were codified:

- Phase 14 W3-W3-α: rules/events-writer.md (143 lines) + rules/skills.md (109 lines) → NEW files created
- Phase 14 W3-W2-C-a: validate_invariants.py _resolve_header_row helper → new function
- Phase 14 W3-W1: governance SKILL.md standalone-executable → 4 files updated

```bash
wc -l /Users/apple/Documents/platinum-seo-engine/rules/events-writer.md
wc -l /Users/apple/Documents/platinum-seo-engine/rules/skills.md
grep -c "_resolve_header_row" /Users/apple/Documents/platinum-seo-engine/scripts/validation/validate_invariants.py 2>/dev/null || \
grep -c "_resolve_header_row" $(find /Users/apple/Documents/platinum-seo-engine/scripts -name "validate_invariants.py")
```

**29.2 — Open Questions → ADR Conversion Rate**

Count: total OQ raised in Phase 15 W1-W4 vs OQs that were resolved (→ ADR or DECISIONS):
```bash
grep -c "Q-PHASE15-" /Users/apple/Documents/platinum-seo-engine/docs/OPEN_QUESTIONS.md
grep -c "RESOLVED\|→ ADR\|→ DECISIONS" /Users/apple/Documents/platinum-seo-engine/docs/OPEN_QUESTIONS.md
```

Identify which Phase 15 OQs are MEDIUM or HIGH priority (require action before v1.1).

**29.3 — Commit Message Convention**

```bash
git -C /Users/apple/Documents/platinum-seo-engine log --oneline -10
git -C /Users/apple/Documents/platinum-seo-workspace log --oneline -10
```

Check commit message format: `<type>: <description>` convention followed (feat/fix/docs/chore/refactor/test/ci/perf). Count violations.

**29.4 — DECISIONS.md ADR Closure Candidates**

```bash
head -100 /Users/apple/Documents/platinum-seo-engine/docs/DECISIONS.md
```

Identify ADR-004 and ADR-005 status:
- ADR-004: soak 2026-05-05..2026-05-12. If today = 2026-05-05, soak just started.
- ADR-005: workspace created Phase 14 → condition met, pending formal close commit.

State closure timelines.

**Gate G-29 sub-checks:**
- Phase 14 key findings codified (rules/events-writer.md + rules/skills.md present)
- _resolve_header_row helper in validate_invariants.py
- Phase 15 OQ count vs HIGH/MEDIUM priority
- Commit message convention followed (≤1 violation)
- ADR-004 + ADR-005 closure timeline documented

---

### W-E3: Kategori 30

#### Kategori 30: v1.1+ Backlog Priority

**Purpose:** Synthesize all Phase 15 findings into a v1.1 backlog with prioritized action items.

**30.1 — Phase 15 W1-W4 Finding Inventory**

Read all prior W1-W4 gate summaries to build a comprehensive AMBER/RED finding list:

```bash
grep -rn "AMBER\|RED" /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/01-engine-repo/ | grep "Gate G-\|G-[0-9].*AMBER\|G-[0-9].*RED"
grep -rn "AMBER\|RED" /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/02-workspace-repo/ | grep "Gate G-\|G-[0-9].*AMBER\|G-[0-9].*RED"
grep -rn "AMBER\|RED" /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/03-cross-repo-pipeline-mcp/ | grep "Gate G-\|G-[0-9].*AMBER\|G-[0-9].*RED"
grep -rn "AMBER\|RED" /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/04-discipline-lesson/ | grep "Gate G-\|G-[0-9].*AMBER\|G-[0-9].*RED"
```

Build a table: Gate | Wave | Verdict | Finding summary.

**30.2 — OPEN_QUESTIONS.md HIGH/MEDIUM Inventory**

```bash
grep -n "\[HIGH\]\|\[MEDIUM\]" /Users/apple/Documents/platinum-seo-engine/docs/OPEN_QUESTIONS.md | head -20
```

List all HIGH/MEDIUM OQs. These become v1.1 must-do candidates.

**30.3 — v1.1 Priority Matrix**

Based on W1-W4 findings and OQs, create a priority matrix:

**P0 (Before 2026-06-02 — hard deadline):**
- Q-PHASE15-NODEJS-01: Update GitHub Actions Node.js 20 → 24 (deadline 2026-06-02)

**P1 (v1.1 must-have):**
- Q-PHASE15-BUDGET-COST-01: dfs_pull.py populate cost.credits (budget guard inactive)
- Any HIGH OQs from OPEN_QUESTIONS.md

**P2 (v1.1 should-have):**
- MEDIUM OQs from Phase 15 + W1-W4
- WORKFLOWS.md status column update (Q-PHASE15-DOC-STALE-01)

**P3 (v1.1 nice-to-have / v1.2 backlog):**
- LOW OQs: npm pin, lockfile, context ledger compression, lesson 28 stale desc

**30.4 — ADR-004 + ADR-005 Closure Action Items**

State clearly:
- ADR-004 closure: Can proceed after 2026-05-12 (1 week soak completes). Action: `git -C /Users/apple/Documents/platinum-seo-engine tag v1.0.0-soak-complete` + DECISIONS.md update (after soak).
- ADR-005 closure: Workspace created → condition met. Action: next engine commit after Phase 15 complete.

**30.5 — Phase 15 Audit Score Summary**

Count from W1-W4:
- Total gates: W1(8) + W2(5) + W3(7) + W4(5) = 25 gates
- PASS count: ?
- AMBER count: ?
- RED count: 0 (no RED gates in any wave)
- Overall verdict: PASS (0 RED)

```bash
# Count PASS/AMBER/RED from all gate summary lines
grep -h "Gate G-.*Verdict:" /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/01-engine-repo/*.md \
  /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/02-workspace-repo/*.md \
  /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/03-cross-repo-pipeline-mcp/*.md \
  /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/04-discipline-lesson/*.md 2>/dev/null
```

**30.6 — v1.1 Feature Backlog**

Based on atıl alan (dead code from cat26), UX gaps (cat27), i18n gaps (cat28), and convention gaps (cat29), list v1.1 feature/improvement candidates beyond fixes. Examples:
- Cross-skill coordination improvements
- New skill candidates (if any skill gap found)
- Performance improvements (brief length optimization)

**Gate G-30 sub-checks:**
- W1-W4 AMBER gate inventory built
- HIGH/MEDIUM OQ list compiled
- v1.1 priority matrix (P0/P1/P2/P3)
- ADR-004 + ADR-005 closure timeline stated
- Overall Phase 15 score (0 RED confirmed)

---

## Section 4: Lesson 38 v2 Pre-Dispatch Path Verification

Confirmed before dispatch:
- Engine root exists: `/Users/apple/Documents/platinum-seo-engine/`
- Skills: 8 categories confirmed
- Scripts: 52 Python files confirmed
- WORKFLOWS.md: 132 lines confirmed
- Rules: 18 files confirmed
- All prior W1-W4 reports written and pushed

**Script path correction from W4:** `scripts/validation/` (not `scripts/ci/`) for validate_*.py files.

W5 output directory — create before writing:
```bash
mkdir -p /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/v1-audit-2026-05-05/05-strategic-ux-i18n/
```

---

## Section 5: Commit Plan (Karar Verici)

After collecting all 5 worker reports:

1. Append `events.jsonl` run_id=66: `event_kind=audit, audit_action=accessed, audit_target=strategic_ux_i18n:{engine-HEAD}:{workspace-HEAD}:phase_15_w5_audit`
2. Git add + commit workspace: `chore: Phase 15 W5 strategic+UX+i18n audit (5 kategori, 23 phase consecutive)` — FINAL AUDIT WAVE
3. Verify engine invariants: HEAD=6cfc18c, DECISIONS.md=5877B, .mcp.json=469B
4. Write `00-master-report.md` executive summary
5. Update memory files: W5 DONE, Phase 15 COMPLETE

---

## Section 6: Gate Verdicts Expected

| Gate | Expected |
|---|---|
| G-26 Atıl Alan | AMBER (WORKFLOWS.md stale known) |
| G-27 UX Smoke | AMBER (Q-WS-02 quick start convention) |
| G-28 i18n | PASS (TR market configured) |
| G-29 Convention Codifier | PASS (Phase 14 codifications confirmed) |
| G-30 v1.1 Backlog | PASS (P0/P1/P2/P3 matrix compiled) |

---

## Section 7: New OQ Candidates

Workers may surface new OQs. Format: `**Q-PHASE15-W5-XXX-01 [PRIORITY]:**`

---

## Section 8: 14-Boyutlu Cross-Check (Lesson 8 v8)

**Section 8 (schema, dims 1-9):** N/A — W5 no schema mutations.
**Section 9 (brief consistency, dim 10):** Workers: W-E1(cat26+27), W-E2(cat28+29), W-E3(cat30) = 5 kategoriler / 3 workers correct.
**Section 10 (infrastructure, dim 11):** Paths use `/Users/apple/...` absolute. `scripts/validation/` (not `scripts/ci/`) per W4 override.
**Section 11 (CI runtime, dim 12):** W5 no CI step needed (read-only).
**Section 12 (skill spec, dim 13):** No skill invocations.
**Section 13 (CI step verdict, dim 14):** No engine commit expected in W5. N/A.

---

## Section 9: Scope Boundaries

**W5 IS:** Audit of README/INSTALL/CONTRIBUTING, script/template/schema inventory, i18n config, v1.1 backlog synthesis.
**W5 IS NOT:** Running skills, modifying master.xlsx, making engine code changes, creating new ADRs.
