# Phase 15 W1 — Engine Repo Audit Brief

> **Karar Verici:** Fresh session (14. ardışık, Phase 11+...+14W3W3β paterni reuse)
> **Tarih:** 2026-05-05
> **Bağlam:** v1.0.0 release tag PUSHED. Phase 15 Audit Milestone W1 başlangıcı.
> **Worker tip:** Audit read-only → `general-purpose` Agent (tüm araçlar mevcut, ancak
> dosya yazma YASAK: Write / Edit tool kullanılmaz. Bash `echo >` redirect de YOK.)

---

## Section 1: Verify State (v1.0.0 baseline — 2026-05-05 doğrulandı)

| Metrik | Beklenen | Doğrulandı |
|---|---|---|
| Engine HEAD | `1da7cf0` closeout | ✓ |
| Git tag | `v1.0.0` annotated → commit `6214a56` | ✓ |
| Workspace HEAD | `3bb7258` | ✓ |
| `docs/DECISIONS.md` | 5877B (6144B cap, margin 267B) | ✓ |
| `find skills -name SKILL.md` | 43 | ✓ |
| `ls rules/` | 18 | ✓ |
| `find schemas -name "*.json"` | 19 | ✓ |
| `python3 -m pytest --tb=no -q` | 610 passed (lokal) | ✓ |
| `.mcp.json` servers | 3 [ScraplingServer, dataforseo, gsc] (F-16 invariant, 20 commit) | ✓ |
| CI latest run | SUCCESS (id: 25392730652) | ✓ |
| GitHub Release | v1.0.0 public, created 2026-05-05T17:39:59Z | ✓ |

**Not:** CI 606 PASS + 4 skipped (workspace-staging guard) ≠ lokal 610 PASS. Bu fark
F-14W3W3β-4 + lesson 66 environment-specific runtime cross-check bulgusu (beklenen).

---

## Section 2: Hedef + Deliverable

**Hedef:** Engine repo (platinum-seo-engine) kapsamlı v1 release post-launch audit.
8 kategori × 5-10 alt-check. Read-only. Kod değişikliği YOK, schema bump YOK, SKILL.md
body değişikliği YOK.

**Deliverable:**
```
/Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/outputs/reports/
v1-audit-2026-05-05/01-engine-repo/
├── cat1-skill-compliance.md
├── cat2-schema-cross-check.md
├── cat3-adr-decisions.md
├── cat4-memory-docs.md
├── cat5-test-infrastructure.md
├── cat6-repo-hygiene.md
├── cat7-migration-history.md
└── cat8-rules-templates.md
```

8 alt-report karar verici (manager) tarafından yukarıdaki path'e yazılır.
(Worker'lar findings'i manager'a rapor eder; manager workspace'e write eder.)

**Atomic 18'inci kanıt aday:** Phase 7+8+9+10+11W1+11W2+12W1+12W2+13+14W1+14W2+
14W3W1+14W3W2A+14W3W2B+14W3W2Ca+14W3W2Cb+14W3W3α+14W3W3β + **15W1** = 19 phase
consecutive. Engine repo DEĞİŞMEZ → workspace commit = atomic deliverable.

---

## Section 3: Worker Dispatch (4 Paralel Audit Worker)

Tüm worker'lar `general-purpose` Agent. Engine repo yolu:
`/Users/apple/Documents/platinum-seo-engine`

### Worker W-R1 — Kategori 1+2: SKILL.md Compliance + Schema Cross-Check

**Görev:**

**Kategori 1: 43 SKILL.md Compliance**

Her skill kategorisi için:
```
skills/discovery/    (kaç SKILL.md?)
skills/governance/   (kaç SKILL.md?)
skills/ingestion/    (kaç SKILL.md?)
skills/meta/         (kaç SKILL.md?)
skills/planning/     (kaç SKILL.md?)
skills/production/   (kaç SKILL.md?)
skills/publishing/   (kaç SKILL.md?)
skills/reporting/    (kaç SKILL.md?)
```

Her SKILL.md için kontrol:
1. **Frontmatter compliance** — `schemas/skill-frontmatter.schema.json` authority:
   ```bash
   python3 -m pytest tests/skills/test_*.py --tb=short -q 2>&1 | head -20
   # NOT: test PASS = frontmatter validation var
   ```
   Manuel: `grep -c "^---$" skills/<cat>/<skill>/SKILL.md` → ≥2 (open + close)
2. **use_when** field mevcut: `grep "use_when:" skills/<cat>/<skill>/SKILL.md`
3. **skill_name** field mevcut: `grep "skill_name:" skills/<cat>/<skill>/SKILL.md`
4. **Body executable** — Python block var: `grep -c '^\`\`\`python$' skills/<cat>/<skill>/SKILL.md`
   (Bazı skills prompt-only: 0 Python block da geçerli — SKILL.md body'de "Python" kelimesi
   veya helper_scripts reference varsa executable demektir)
5. **Kategori-bazlı functional smoke** — Her kategori için 1 örnek skill seç, SKILL.md
   Step 1-3'ü oku ve "is this self-contained executable?" evaluate et

Özellikle kontrol: `skills/governance/drift-check/SKILL.md` (Section 12 baseline 8/8 FULL
inspect precedent), `skills/governance/schema-validate/SKILL.md`, `skills/governance/
glossary-audit/SKILL.md`.

**Kategori 2: 19 Schema Cross-Check + Cascade + Version Compatibility**

```bash
# Tüm schemas valid JSON mi?
for f in schemas/*.json; do python3 -c "import json; json.load(open('$f'))" && echo "$f: OK" || echo "$f: FAIL"; done
```

Spesifik cross-check'ler:
1. `schemas/master-excel.schema.json` ↔ `schemas/cross-sheet-invariants.json`:
   Her sheet'in `required_columns` var mı? `header_row` + `data_start_row` tanımlı mı?
2. `schemas/events.schema.json` — event_type 10-closed-enum intact:
   ```bash
   jq '.definitions.event_type.enum' schemas/events.schema.json
   # Beklenen: ["content_new","content_revise","content_improve","content_remove",
   # "template_apply","scrape_run","audit_run","budget_event","sync_run","manual"]
   ```
3. `schemas/skill-frontmatter.schema.json` — required fields list:
   `jq '.required' schemas/skill-frontmatter.schema.json`
4. `schemas/project-config.schema.json` — version field:
   `jq '.properties.schema_version' schemas/project-config.schema.json`
5. Cascade chain: `scripts/migrations/0001_*.py` → `scripts/migrations/0002_*.py`:
   Her migration dosyasının `if __name__ == "__main__"` bloğu var mı?
   ```bash
   grep -l "__main__" scripts/migrations/0001_project_config_1.0_to_1.1.py
   grep -l "__main__" scripts/migrations/0002_project_config_1.1_to_1.2.py
   ```
6. Version compatibility: `project-config.schema.json`'da `schema_version: "1.2"` ✓
7. Q-W3W2C-A-LAYOUT-01 bulgusu kontrol: master.xlsx'teki header row layout normalizasyonu
   ADR aday olarak tescillenmiş mi? (`docs/OPEN_QUESTIONS.md`'de var mı?)

**Output format (W-R1 → manager):**
```markdown
## W-R1 Audit Findings

### Kategori 1: SKILL.md Compliance
- Toplam: 43/43 check
- PASS: XX  FAIL: YY  N/A: ZZ
- Failing skills: [listele]
- Notable: [önemli bulgular]

### Kategori 2: Schema Cross-Check
- JSON valid: XX/19
- event_type enum: [intact/mismatch]
- Notable: [önemli bulgular, Q-XXX bağlantıları]
```

---

### Worker W-R2 — Kategori 3+4: ADR + Memory/Docs

**Görev:**

**Kategori 3: 4 ADR Active + 25 Archive + Cumulative Consistency**

```bash
wc -c docs/DECISIONS.md  # → 5877 (beklenen)
wc -c docs/DECISIONS_ARCHIVE.md
grep -c "^## ADR-" docs/DECISIONS.md      # 4 active
grep -c "^## ADR-" docs/DECISIONS_ARCHIVE.md  # 25 archive
```

Active ADR'ler kontrol (DECISIONS.md body inspect):
- ADR-026: hard cap 6144B — current 5877B → margin 267B ✓
- ADR-027: transform size policy <1500 satır
- ADR-028: tech_seo schema enum + Web Vitals 2024
- ADR-029: budget convention per-run estimated_credits

Q-CD-01 paterni 17'inci uygulama hedef:
```bash
git log --oneline | grep -c "DECISIONS unchanged\|Q-CD-01"
# veya: git log --all --oneline | wc -l  # total commit count
```

ADR-004 soak status kontrol: `docs/DECISIONS.md`'de ADR-004 mevcut mu?
(NOT: ADR-004 = eski repo silme timing, soak window 2026-05-05..2026-05-12)

ADR-005 RESOLVED kontrol: `docs/DECISIONS.md`'de ADR-005 RESOLVED olarak işaretli mi?

**Kategori 4: Memory + Manager Docs + Spec Docs + GLOSSARY/REFERENCE_INDEX**

```bash
# Manager dosyaları (12 adet, docs/ root)
ls docs/*.md | wc -l
ls docs/*.md
```

Her manager doc boyut kontrolü:
```bash
wc -c docs/ARCHITECTURE.md   # <8KB hedef
wc -c docs/CONTEXT_LEDGER.md
wc -c docs/GLOSSARY.md
wc -c docs/PHASE_STATUS.md
wc -c docs/OPEN_QUESTIONS.md
wc -c docs/SESSION_PROTOCOL.md
wc -c docs/WORKER_PROMPTS.md
wc -c docs/WORKFLOWS.md
wc -c docs/REFERENCE_INDEX.md
wc -c docs/CONTRIBUTING.md
wc -c docs/INSTALL.md
wc -c docs/AUDIT_KICKOFF_v1.md
wc -c docs/RELEASE_NOTES_v1.0.0.md
```

GLOSSARY kontrol:
- "22-token whitelist" kuralı güncel mi? (`grep "token" docs/GLOSSARY.md | head -5`)
- Yeni terimler eklenmiş mi son commit'lerde? (`git log --oneline -5 docs/GLOSSARY.md`)

REFERENCE_INDEX kontrol:
- `docs/REFERENCE_INDEX.md` son güncellenme tarihi? (`git log -1 --format="%ad" docs/REFERENCE_INDEX.md`)
- Var olmayan dosyalara referans var mı? (`grep -o "skills/[^)]*" docs/REFERENCE_INDEX.md | while read f; do [ -e "$f" ] || echo "DEAD: $f"; done`)

SESSION_PROTOCOL + WORKER_PROMPTS güncelliği:
- Son Phase 15'i yansıtıyor mu? (`grep "Phase 15\|v1.0.0" docs/SESSION_PROTOCOL.md`)

Spec docs varlık kontrolü:
```bash
ls docs/superpowers/specs/ 2>/dev/null | wc -l  # spec dosyaları
```

Memory files (engine repo'da değil, ~/.claude/ altında → worker okuyabilir):
```bash
ls /Users/apple/.claude/projects/-Users-apple-Documents-platinum-seo-engine/memory/
wc -c /Users/apple/.claude/projects/-Users-apple-Documents-platinum-seo-engine/memory/MEMORY.md
```

Q-W3W2Cb-003 audit aday: master_task task_id pattern `MT-W3W2B-001` vs `^T-[0-9]{4,}$` — açık sorun olarak belgelenmiş mi `docs/OPEN_QUESTIONS.md`'de?

**Output format (W-R2 → manager):**
```markdown
## W-R2 Audit Findings

### Kategori 3: ADR + DECISIONS
- DECISIONS.md: 5877B [OK/FAIL]
- Active ADR count: XX (beklenen: 4)
- Archive ADR count: XX (beklenen: 25)
- ADR-026 margin: XXX B
- ADR-004 soak: [mevcut/eksik]
- Notable: [bulgular]

### Kategori 4: Memory + Docs
- Manager doc count: XX
- ARCHITECTURE.md: XX bytes [<8KB: OK/FAIL]
- Dead references in REFERENCE_INDEX: XX
- Notable: [bulgular]
```

---

### Worker W-R3 — Kategori 5+6: Test Infrastructure + Repo Hygiene

**Görev:**

**Kategori 5: pytest Coverage + Test Infrastructure Quality**

```bash
python3 -m pytest --tb=no -q 2>&1 | tail -3
# Beklenen: 610 passed in ~5s
```

Test dosyası envanteri (MIXED layout — lesson 38 v2 alt-boyut Q-CI-W3-04 scope):
```bash
find tests -name "test_*.py" | sort | wc -l   # → 54 dosya
find tests -name "test_*.py" | sort
```

Test layout consistency:
```bash
# Subdirectory kullanan testler:
find tests/skills -type d  # governance/ subdirectory VAR (normal)
# Flat olanlar:
ls tests/skills/test_*.py | wc -l  # flat skill test count
# Governance subdirectory:
ls tests/skills/governance/ # test_glossary_audit.py + test_load_context.py + test_schema_validate.py
```

Q-CI-W3-04 açık soru audit (local-only fixture skipif marker):
```bash
grep -l "skipif\|pytest.mark.skip" tests/skills/test_quick_wins.py tests/skills/test_sf_import.py
# Bu iki dosyada @pytest.mark.skipif marker olmalı (cascade fix 6214a56)
grep "skipif" tests/skills/test_quick_wins.py
grep "skipif" tests/skills/test_sf_import.py
```

Test coverage kalite kontrolü:
```bash
# Her test dosyasında en az 1 test var mı?
for f in $(find tests -name "test_*.py"); do
  count=$(grep -c "^def test_" "$f" 2>/dev/null || echo 0)
  [ "$count" -eq 0 ] && echo "EMPTY: $f"
done
```

Lesson 29 self-extending test pattern:
```bash
# Test count evolution (en az 600+ test var mı?)
python3 -m pytest --collect-only -q 2>&1 | tail -3
```

CI test compliance:
```bash
cat .github/workflows/ci.yml | grep -A5 "pytest"
# Step 4 = pytest, continue-on-error: false beklenen
```

**Kategori 6: Repository Hygiene**

```bash
git status  # clean working tree beklenen
git branch -a  # main only (veya clean branches)
git log --oneline -10  # commit convention <type>: <description>
git tag -l  # v1.0.0 mevcut
git log --oneline v1.0.0  # tag → commit zinciri
```

Commit convention check:
```bash
git log --oneline -20 | grep -v "^[a-f0-9]\{7\} \(feat\|fix\|refactor\|docs\|test\|chore\|perf\|ci\):"
# Bu komut convention-dışı commit mesajları listeler (sonuç: NONE beklenen)
```

.gitignore kapsamı:
```bash
grep -E "inbox|\.json|\.csv" .gitignore  # inbox/**/*.json + *.csv cover edilmeli
```

secrets kontrolü:
```bash
python3 scripts/ci/check_secrets.sh 2>/dev/null || bash scripts/ci/check_secrets.sh
```

F-16 invariant son verifikasyon:
```bash
wc -c .mcp.json   # → 469 bytes beklenen
jq '.mcpServers | keys' .mcp.json  # → ["ScraplingServer","dataforseo","gsc"]
git log --oneline | wc -l  # total commit count
```

**Output format (W-R3 → manager):**
```markdown
## W-R3 Audit Findings

### Kategori 5: Test Infrastructure
- Total tests: 610 passed [OK/FAIL]
- Test file count: 54
- Q-CI-W3-04 skipif marker: test_quick_wins.py [✓/✗] + test_sf_import.py [✓/✗]
- Empty test files: XX (beklenen: 0)
- Notable: [bulgular]

### Kategori 6: Repo Hygiene
- Working tree: [clean/dirty]
- Branch state: [clean/stale branches]
- Commit convention: [XX violations]
- .mcp.json: 469B [OK/FAIL]
- Secrets: [PASS/FAIL]
- Notable: [bulgular]
```

---

### Worker W-R4 — Kategori 7+8: Migration + Rules/Templates

**Görev:**

**Kategori 7: Migration History + Idempotent + Backup**

```bash
ls scripts/migrations/
# → 0001_project_config_1.0_to_1.1.py
# → 0002_project_config_1.1_to_1.2.py
```

Migration chain integrity:
```bash
python3 scripts/migrations/0001_project_config_1.0_to_1.1.py --help 2>/dev/null || python3 -c "import ast; ast.parse(open('scripts/migrations/0001_project_config_1.0_to_1.1.py').read()); print('SYNTAX OK')"
python3 scripts/migrations/0002_project_config_1.1_to_1.2.py --help 2>/dev/null || python3 -c "import ast; ast.parse(open('scripts/migrations/0002_project_config_1.1_to_1.2.py').read()); print('SYNTAX OK')"
```

Idempotent check:
```bash
grep "idempotent\|--force\|if.*exists\|skip" scripts/migrations/0001_project_config_1.0_to_1.1.py | head -5
grep "idempotent\|--force\|if.*exists\|skip" scripts/migrations/0002_project_config_1.1_to_1.2.py | head -5
```

Workspace backup kontrolü (workspace repo'da):
```bash
ls /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/_state/backups/ 2>/dev/null | wc -l
# Son backup var mı?
ls -la /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/_state/backups/ 2>/dev/null | tail -5
```

Transaction.py atomic check:
```bash
grep -n "def.*backup\|def.*restore\|def.*rollback" scripts/transaction.py | head -10
```

events.jsonl append-only check:
```bash
wc -l /Users/apple/Documents/platinum-seo-workspace/projects/demo-dental/_state/events.jsonl
# Line count (her satır = 1 event)
```

**Kategori 8: Rules + Templates + R-XX Cumulative**

Rules envanter:
```bash
ls rules/ | wc -l  # → 18 beklenen
ls rules/
```

Her rule dosyası boyut kontrolü:
```bash
for f in rules/*.md; do wc -c "$f"; done
```

R-XX kural sayısı kontrolü:
```bash
grep -rh "^- \*\*R-[0-9]" rules/ | wc -l  # veya
grep -rh "R-[0-9][0-9][0-9]" rules/ | grep -o "R-[0-9]\+" | sort -u | wc -l
# Not: 110 R-XX cumulative memory'de kayıtlı — gerçek sayı kaç?
```

Content rules (kritik 4):
```bash
grep -l "R-02\|R-27\|R-100\|R-114" rules/*.md  # Bu 4 kural hangi dosyada?
```

Template envanter:
```bash
ls templates/content/ 2>/dev/null | wc -l
ls templates/project/ 2>/dev/null | wc -l
ls templates/reports/ 2>/dev/null | wc -l
ls templates/scrapling/ 2>/dev/null | wc -l
```

rules/events-writer.md (W3-W3-α deliverable):
```bash
wc -l rules/events-writer.md   # ~143 satır beklenen
grep "^## " rules/events-writer.md   # Section başlıkları
```

rules/skills.md (W3-W3-α deliverable):
```bash
wc -l rules/skills.md   # ~109 satır beklenen
grep "^## " rules/skills.md   # Section başlıkları
```

Foundational Principles:
```bash
grep -rh "Foundational Principles\|foundational_principles" rules/ | wc -l
# 3 Foundational Principles aktif mi?
```

**Output format (W-R4 → manager):**
```markdown
## W-R4 Audit Findings

### Kategori 7: Migration + Backup
- Migration 0001: [syntax OK/FAIL]
- Migration 0002: [syntax OK/FAIL]
- Idempotent markers: [found/missing]
- Workspace backups: XX dosya
- events.jsonl lines: XX
- Notable: [bulgular]

### Kategori 8: Rules + Templates
- Rules count: 18 [OK/FAIL]
- R-XX cumulative count: XX (memory: 110)
- Template count: XX
- rules/events-writer.md: XX satır
- rules/skills.md: XX satır
- Notable: [bulgular]
```

---

## Section 4: DURUR Conditions

Herhangi bir worker aşağıdaki durumlarla karşılaşırsa DERHAL durur ve manager'a rapor eder:

| # | Durum | Aksiyon |
|---|---|---|
| D-1 | Worker Write/Edit tool kullanmaya çalışırsa | STOP → read-only audit ihlali → manager'a bildir |
| D-2 | `docs/DECISIONS.md` 6144B limitini aşarsa (boyut artışı tespit edilirse) | STOP → Q-CD kritik → Süleyman onay gerekir |
| D-3 | `.mcp.json` değiştirilmiş ise (469B ≠ gerçek boyut) | STOP → F-16 ihlali → manager'a acil bildir |
| D-4 | secrets veya API key commit history'de bulunursa | STOP → security finding → acil rapor |
| D-5 | Drift scope >50 satır gerektiren kritik bulgu | STOP → manager'a escalate, karar verici yönlendirir |

---

## Section 5: Acceptance Gates

| Gate | Kategori | Pass Kriteri |
|---|---|---|
| G-1 | SKILL.md | 43/43 frontmatter valid + 0 kritik body ihlali |
| G-2 | Schema | 19/19 JSON valid + events event_type 10-enum intact |
| G-3 | ADR | 4 active intact + 5877B DECISIONS.md + Q-CD-01 28 commit unchanged |
| G-4 | Memory/Docs | ARCHITECTURE.md <8KB + 0 dead REFERENCE_INDEX ref |
| G-5 | Tests | 610 PASS + Q-CI-W3-04 skipif marker confirmed |
| G-6 | Repo hygiene | clean working tree + 3 server .mcp.json 469B |
| G-7 | Migration | 0001+0002 syntax OK + workspace backup mevcut |
| G-8 | Rules/Templates | 18 rules + R-XX sayısı 110 ≤ XX ≤ 130 |

**Atomic 18'inci kanıt PASS kriteri:** Tüm 8 gate PASS + workspace commit yapıldı.
AMBER (1-2 gate minor finding) → manager yönlendirir, commit yapılır.
RED (kritik gate fail) → Süleyman onay + fix önce.

---

## Section 6: Commit Protocol (Workspace Only)

**Engine repo: 0 yeni commit** (read-only audit).
**DECISIONS.md: byte-byte unchanged** (Q-CD-01 paterni 17'inci uygulama hedef).
**.mcp.json: byte-byte unchanged** (F-16 invariant 20 → 21+ commit hedef).

**Workspace commit** (atomic 18'inci kanıt):
```
chore: Phase 15 W1 engine repo audit (8 kategori, 19 phase consecutive)
```

Commit içeriği:
- `projects/demo-dental/outputs/reports/v1-audit-2026-05-05/01-engine-repo/` 8 alt-report
- `projects/demo-dental/_state/events.jsonl` +1 audit_run event (event_type="audit_run")

**events.jsonl audit event şablonu** (events.schema.json allOf compliance):
```json
{
  "event_id": "<next_run_id>",
  "run_id": "<next_run_id>",
  "timestamp": "2026-05-05T<time>Z",
  "event_kind": "audit",
  "event_type": "audit_run",
  "project_id": "demo-dental",
  "actor": "manager",
  "action": "phase_15_w1_engine_audit",
  "status": "completed",
  "details": "Phase 15 W1 8 kategori engine repo audit completed. 8 alt-report workspace."
}
```

---

## Section 7: Süleyman Onay Matrisi (Phase 15 W1)

**W1 Tek Onay:** "Phase 15 W1 audit tamamlandı, workspace commit onayı"
- Manager tüm 8 gate sonucunu özetler (PASS/AMBER/RED)
- Drift-catch listesi (varsa) gösterir
- Süleyman push onayı verir → workspace commit pushed

---

## Section 8: 9-Boyutlu Schema Cross-Check (Audit Adaptation, 12'inci ardışık)

**Boyut 1 — type/format uyumu:** events.schema.json `event_type` type string (not object/array)?
`jq '.definitions.event_type.type // .definitions.event_type."$ref"' schemas/events.schema.json`
Beklenen: `"string"` veya `enum` array.

**Boyut 2 — items uyumu:** master-excel.schema.json `sheets` property array type?
`jq '.properties.sheets.type' schemas/master-excel.schema.json` → `"array"` beklenen.

**Boyut 3 — properties uyumu:** project-config.schema.json `schema_version` field var?
`jq '.properties.schema_version' schemas/project-config.schema.json` → not null beklenen.

**Boyut 4 — enum uyumu (KRİTİK):** events.schema.json event_type 10-closed-enum intact?
`jq '.definitions.event_type.enum | length' schemas/events.schema.json` → 10 beklenen.
Audit read-only → enum değişimi YASAK (bu audit boyunca).

**Boyut 5 — nullable uyumu:** skill-frontmatter.schema.json nullable fields doğru?
`jq '.properties | keys' schemas/skill-frontmatter.schema.json` → field list.

**Boyut 6 — additionalProperties uyumu:** events.schema.json `additionalProperties: false` var?
`jq '.additionalProperties' schemas/events.schema.json`

**Boyut 7 — required uyumu:** master-excel.schema.json required list `schema_version` + `sheets` içeriyor mu?
`jq '.required' schemas/master-excel.schema.json`

**Boyut 8 — pattern uyumu:** events.schema.json `run_id` pattern field var?
`grep "run_id" schemas/events.schema.json | head -5`

**Boyut 9 — allOf rules uyumu:** events.schema.json `allOf` branch matrix content_new event
için `url` + `url_normalized` + `after` + `pillar` required cross-check.
`jq '[.definitions | to_entries[] | select(.key | test("content_new"))] | length' schemas/events.schema.json`

**12'inci ardışık aday** (Phase 11W1+W2+12W1+W2+13+14W1+W2+W3W1+W3W2A+W3W2B+W3W2Ca+W3W2Cb+
W3W3α+W3W3β → +W1=12'inci): tüm 9 boyut kontrol edildi.

---

## Section 9: Brief Internal Consistency (11'inci Uygulama)

| Check | Beklenen | Doğrulama |
|---|---|---|
| Kategori count | 8 | Section 3'de 4 worker × 2 kategori = 8 ✓ |
| Gate count | 8 | Section 5'de G-1..G-8 = 8 ✓ |
| Alt-report count | 8 | Section 2 deliverable 8 dosya ✓ |
| Worker count | 4 (W-R1..W-R4) | Section 3 W-R1+W-R2+W-R3+W-R4 = 4 ✓ |
| Atomic kanıt | 18'inci | 17 previous + W1 = 18 ✓ |
| Workspace commit | 1 | Section 6 "workspace only, 0 engine" ✓ |
| Süleyman onay | 1 (W1 push) | Section 7 "1 tek onay" ✓ |
| DECISIONS.md | unchanged | Section 6 "0 yeni ADR" ✓ |
| .mcp.json | 469B unchanged | Section 6 + Section 4 D-3 ✓ |

**9/9 PASS** — brief internal consistency confirmed.

---

## Section 10: Brief Infrastructure Convention (10'uncu Uygulama, Lesson 38 v2 7'inci Ardışık)

**Path conventions (lesson 38 v2 enforce — frozen assumption YASAK):**

| Kaynak | Yol | Doğrulama Komutu |
|---|---|---|
| Engine repo | `/Users/apple/Documents/platinum-seo-engine` | `git -C /Users/.../platinum-seo-engine remote get-url origin` |
| Workspace repo | `/Users/apple/Documents/platinum-seo-workspace` | `git -C /Users/.../platinum-seo-workspace log -1 --oneline` |
| Audit output | workspace: `projects/demo-dental/outputs/reports/v1-audit-2026-05-05/01-engine-repo/` | `ls /Users/.../platinum-seo-workspace/projects/demo-dental/outputs/` |
| Skills | `skills/{discovery,governance,ingestion,meta,planning,production,publishing,reporting}/` | `ls skills/` |
| Tests (MIXED!) | `tests/skills/governance/test_*.py` + `tests/skills/test_*.py` | `find tests -name "test_*.py" \| sort` |
| Schemas | `schemas/*.json` (19 files) | `find schemas -name "*.json" \| wc -l` |
| Rules | `rules/*.md` (18 files) | `ls rules/ \| wc -l` |
| Templates | `templates/{content,project,reports,scrapling}/` | `ls templates/` |
| Migrations | `scripts/migrations/0001_*.py` + `0002_*.py` | `ls scripts/migrations/` |

**KRİTİK lesson 38 v2 alt-boyutlar (7 ardışık, Phase 15 enforce default):**
1. Infrastructure convention dynamic state (SSH→HTTPS remote URL)
2. Partial inspect YASAK — full file body inspect ZORUNLU
3. Test infrastructure path convention (MIXED: governance/ subdir + flat)
4. Dynamic state cross-check post-wave (execute mode + populate state)
5. Runtime cross-check (frozen assumption YASAK runtime kanıt gerekir)
6. **Environment-specific runtime cross-check (lokal vs CI runner state divergence)** — lesson 66 doğum belgesi, Phase 15 enforce CRITICAL: "lokal kanıt = CI kanıt" frozen assumption YASAK

**Test layout NOT (F-14W3W2Ca-1 + lesson 54 codify):**
- `tests/skills/governance/` subdirectory: 3 dosya (test_glossary_audit + test_load_context + test_schema_validate)
- `tests/skills/test_drift_check.py` = FLAT (governance category ama flat naming)
- Diğer tüm skill testleri = FLAT `tests/skills/test_*.py`
- Governance subdir = içeriden management skills için, skill testleri flat convention

---

## Section 11: Brief CI Runtime Requirements (9'uncu Uygulama)

**Audit = read-only → NO engine commit → CI trigger YOK bu wave'de.**

| Kriter | Durum |
|---|---|
| Engine commit | YOK (audit read-only) → CI trigger YOK |
| Workspace commit | VAR (audit deliverable) → workspace CI yok (konfigüre edilmedi) |
| pytest command | `python3 -m pytest --tb=no -q` (NOT bare `pytest` — PATH issue) |
| CI last baseline | Run 25392730652 SUCCESS (clean) |
| Environment delta | Lokal 610 PASS ≠ CI 606 PASS+4 skip (lesson 66, normal beklenen) |

**EXCEPTION path:** Worker W-R3/W-R4 kritik engine bug bulurussa → engine fix commit gerekebilir.
Bu durumda: Section 13 active, CI Run trigger eder, W-R3/W-R4 CI run'ı monitor eder.

**Dependency manifest:** Audit worker'ların `jq` komutunu kullanması gerekiyor:
```bash
which jq  # mevcut mu kontrol
jq --version
```

---

## Section 12: Brief Skill Spec Invocation Behavior (8'inci Uygulama, Audit Adaptation)

**Audit = read-only → skill execution YOK. Ama her kategori kendi "check protocol" var.**

| Kategori | Check Protocol | Invocation Type |
|---|---|---|
| SKILL.md compliance | `grep "skill_name:" SKILL.md` + frontmatter manual inspect | Bash grep (passive) |
| Schema cross-check | `jq . schemas/*.json` + `python3 -c "import json; json.load(...)"` | Python one-liner |
| ADR compliance | `wc -c docs/DECISIONS.md` + `grep "^## ADR-"` | Bash wc + grep |
| Test infrastructure | `python3 -m pytest --tb=no -q` | python3 module invoke |
| Migration syntax | `python3 -c "import ast; ast.parse(open('...').read())"` | Python AST check |
| Schema validate script | `python3 scripts/validation/validate_schema.py --help` | Script passive invoke |

**NOT (lesson 38 v2 full inspect ZORUNLU):** Her worker kendi kategorisi için tam dosya okur.
Worker W-R1: tüm 43 SKILL.md'yi sistematik kontrol eder (spot-check YASAK).

**validate_frontmatter.py YOK** — SKILL.md frontmatter compliance için:
```bash
python3 -c "
import json, glob
schema = json.load(open('schemas/skill-frontmatter.schema.json'))
print('required fields:', schema.get('required', []))
"
```
Sonra her SKILL.md frontmatter'ını bu required fields'a göre kontrol et.

---

## Section 13: Brief CI Step Verdict Integrity (7'inci Uygulama, Audit Adaptation)

**Audit W1 CI domain: "domain natural N/A" — engine commit yok → CI trigger yok.**

Bu section aktif hale gelir sadece:
- Worker bulgusu engine fix commit gerektiriyorsa
- Karar verici engine fix onaylarsa

**Lesson 65 baseline (CI Run 13 = 25392208959):** 7/7 step GREEN:
1. drift-check ✓ continue-on-error: false
2. schema-validate ✓ continue-on-error: false
3. glossary-audit ✓ continue-on-error: false
4. pytest ✓ (606 PASS + 4 skip, continue-on-error: false)
5. plugin-agnostik-grep ✓ continue-on-error: false
6. secret-grep ✓ continue-on-error: false
7. frontmatter-compile ✓ continue-on-error: false

**F-14W3W3β-4 lesson (environment-specific runtime kanıt scope):**
- Lokal pytest 610 PASS ≠ CI pytest 606 PASS+4 skip = NORMAL (workspace-staging guard)
- "lokal kanıt = CI kanıt" frozen assumption YASAK (lesson 66 doğum belgesi)
- Herhangi bir yeni engine commit → CI Run trigger → 7/7 step GREEN beklenmeli

**Q-CI-W3-04 audit verification (W1 kategori #5 scope):**
```bash
grep -c "skipif\|pytest.mark.skip" tests/skills/test_quick_wins.py
grep -c "skipif\|pytest.mark.skip" tests/skills/test_sf_import.py
# Her biri ≥1 beklenen (cascade fix 6214a56)
```

**Phase 15 W2+ için not:** Workspace commit CI trigger etmez (workspace CI konfigürasyonu yok).
Bu section W2+ engine-touching operation'larda active olabilir.

---

## Versiyon + Meta

| Alan | Değer |
|---|---|
| Brief version | Phase 15 W1 v1.0 |
| Yazılma tarihi | 2026-05-05 |
| Karar verici session | 14. ardışık fresh manager |
| 14-boyutlu cross-check | Section 8+9+10+11+12+13 COMPLETE |
| Lesson 8 v8 uygulama | 12'inci ardışık Section 8 / Section 13 N/A (domain natural) |
| Lesson 38 v2 | 7'inci ardışık, 6 alt-boyut cumulative |
| Önceki phase | Phase 14 W3-W3-β (v1.0.0 PUSHED 2026-05-05) |
| Sonraki phase | Phase 15 W2 (workspace repo audit) |
| Q-CD-01 | 17'inci uygulama hedef (DECISIONS unchanged, 28 → 29 commit) |
| F-16 invariant | 20 → 21 commit hedef (engine .mcp.json unchanged) |
