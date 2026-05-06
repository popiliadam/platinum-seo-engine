---
name: Skills
status: enforced
applies_to: [plugin]
spec_section: "§9 + ADR-022"
related: [schema-first, naming, skill-description-discipline]
---

# Skills

Skill body Python block convention + helper exec compatibility kuralları (`scripts/ci/run_skill_python.py` substring-key detection paterni). Phase 14 W3-W1 governance refactor 4 skill paterni reuse + W3-W2-B+ enforce default. Lesson 38 v2 kümülatif 5'inci ardışık production-ready uygulamasında codify edilmiştir (Q-CI-W3-01 birleşik resolve).

## Section 1 — Skill Body 1. Python Block ZORUNLU Prefix Paterni

Her skill SKILL.md'sinin **ilk** ` ```python ` code block'u (varsa Python block'u olan skill için) ya `sys.path.insert(0, os.getcwd())` marker'ını içermeli, ya da helper auto-prepend setup block ekleyerek bu marker'ı garanti etmeli.

- Lesson 21 4'üncü uygulama formal codify (Phase 14 W3-W1 governance refactor 4 governance skill).
- 4 governance skill paterni reuse: `drift-check` + `schema-validate` + `glossary-audit` + `load-context` — hepsi `sys.path.insert(0, os.getcwd())` marker'ını ilk block'ta açıkça veya helper auto-prepend ile sağlar.
- Helper concat exec compatibility: `scripts/ci/run_skill_python.py` block'ları sırayla concat eder ve subprocess olarak çalıştırır; `scripts.*` package import'ları için `sys.path[0]` resolve auto-prepend ile garanti edilir.

## Section 2 — Standalone-Executable Convention

Skill body Python block'ları **sequential dispatch** ile çalışır:

- 1. block: setup (sys.path + os import + base path resolve).
- Sonraki block'lar: domain logic (validate, generate, write).
- Helper concat: tek `concat_script` string + `subprocess.run([sys.executable, "-c", concat_script])`.
- `sys.path[0]` auto-resolve `scripts.*` package import için ZORUNLU (örn `from scripts.governance.validate_invariants import check_F_05`).
- Skill standalone executable: `python3 scripts/ci/run_skill_python.py skills/governance/drift-check/SKILL.md` — exit=0 PASS, exit=1 FAIL.

W3-W3-α CI strict mode geçişi (lesson 8 v8 boyut #14 production-ready 4'üncü uygulama) için 4 governance skill helper exec EXIT=0 4/4 kanıtlanmış zemin oluşturur (drift-check + schema-validate + glossary-audit + load-context).

## Section 3 — Multi-line Format Spec (KRİTİK)

Skill body Python block'larında **multi-line** format ZORUNLU:

```python
import sys
sys.path.insert(0, os.getcwd())
```

Semicolon-tek-satır formattan KAÇIN:

```python
# YASAK — substring-key detection respect etmez
import sys; import os; sys.path.insert(0, os.getcwd())
```

- Helper `extract_python_blocks` (scripts/ci/run_skill_python.py) substring-key detection (`sys.path.insert(0, os.getcwd())`) bazlıdır.
- Multi-line format respect ZORUNLU: F-14W3W3α-4 catch — semicolon-tek-satır marker'ı string olarak content'te bulunsa bile multi-statement parse problem doğurur (governance skill exec subprocess'te SyntaxError YASAK).
- `import os, sys` veya ayrı satır `import os\nimport sys` paterni serbest, marker satırı multi-line korunur.

### Worked Example — drift-check SKILL.md ilk block paterni

```python
# 1. block — setup (marker burada, helper detect eder, prepend skip)
import os, sys
sys.path.insert(0, os.getcwd())

from scripts.governance.validate_invariants import (
    check_F_05, _resolve_header_row, _iter_rows_as_dicts,
)
WORKSPACE_PATH = os.environ.get("WORKSPACE_PATH", "../platinum-seo-workspace")
```

Sonraki block'lar bu setup'ı concat exec'te miras alır:

```python
# 2. block — domain logic
master_xlsx = os.path.join(WORKSPACE_PATH, "data/master/master.xlsx")
result = check_F_05(master_xlsx)
print(f"F-05: {'PASS' if result else 'FAIL'}")
```

### Worked Example — Q-CI-W3-02 helper auto-prepend (marker eksik skill)

Skill body'de hiçbir block `sys.path.insert(0, os.getcwd())` içermiyorsa:

```python
# Skill body — ilk block (marker eksik)
print("Hello from skill")
```

Helper otomatik olarak setup block prepend eder (concat öncesi):

```python
# Helper-injected block (auto-prepend)
import os, sys
sys.path.insert(0, os.getcwd())
# ↑ original block aşağıda concat
```

Multi-line format respect: prepend block her zaman 2 satır (`import os, sys\nsys.path.insert(0, os.getcwd())`), semicolon-tek-satır prepend YASAK.

## Section 4 — Cross-References

- W3-W1 governance refactor 4 skill paterni reuse: `skills/governance/{drift-check, schema-validate, glossary-audit, load-context}/SKILL.md` ilk block standardı.
- Phase 14 W3-W2-B+ enforce default: 13 production skill body Python block tek concat helper exec ile uyumlu olmalı.
- Lesson 38 v2 enforce kümülatif (5'inci ardışık production-ready): brief authority claim infrastructure convention dynamic state cross-check, partial inspect YASAK frozen assumption YASAK.
- Lesson 21 paterni reuse: worker proaktif scope expansion underlying helper module fix positive drift (validate_invariants.py + run_skill_python.py auto-prepend).
- Schema-first cross-ref → rules/schema-first.md (skill metadata events.schema authority).
- Naming cross-ref → rules/naming.md (skill folder hierarchy + flat tests/skills/test_*.py convention F-14W3W2Ca-1 catch).

## Section 5 — pytest Local-Only Fixture Convention (Q-CI-W3-04)

Workspace-staging path veya lokalde mevcut ama CI runner'da YOK olan fixture'a bağlı testler `@pytest.mark.skipif` marker ZORUNLU.

```python
from pathlib import Path
WORKSPACE_STAGING = Path.home() / "Documents/platinum-seo-workspace/projects/dentnotion/_state/cache"

@pytest.mark.skipif(not WORKSPACE_STAGING.exists(), reason="workspace-staging only available locally")
def test_happy_path_gsc_live():
    ...
```

- CI ubuntu-latest runner'da workspace-staging path YOKTUR → marker olmayan test 4 fail = CI kırılır.
- F-14W3W3β-4 cascade fix (Süleyman K3 Seçenek B): test_quick_wins.py + test_sf_import.py 4 test @pytest.mark.skipif marker eklendi.
- Konftest.py `local_only` marker register + `-m "not local_only"` CI flag (cleaner pattern) Phase 16+ scope.
- Mevcut `skipif(not PATH.exists())` pattern production-ready, migration ertelenebilir.

## Section 6 — Schema Enum jq Path (Q-PHASE15-EVENTENUM-BRIEF-01)

`events.schema.json` gibi JSON Schema dosyalarında enum değer path'i `.properties.<field>.enum` — `.definitions.<field>.enum` DEĞİL.

```bash
# DOĞRU
jq '.properties.event_type.enum' schemas/events.schema.json
jq '.properties.event_kind.enum' schemas/events.schema.json

# YANLIŞ (Phase 15 W1 schema-first override #16 doğum belgesi)
jq '.definitions.event_type.enum' schemas/events.schema.json  # null döner
```

Brief template schema enum cross-check adımlarında `.properties.<field>.enum` path kullanılmalı. Worker her seferinde Python fallback yapmak ZORUNDA KALMAZ.

## Section 7 — Archive Convention (Q-PHASE15-ARCHIVE-INTEG-01)

Output üreten skill'ler (monthly-report, competitive-analysis, audit reports, vb.) son adımda workspace `.claude/commands/archive` konvansiyonuna referans verir.

- SKILL.md son Step: "Output'ları `outputs/` altına kaydet + archive command'ı ile workspace backup'a al."
- Sadece output üreten skill'ler için (discovery/analysis sonuç → markdown/JSON → archive).
- Prompt-only skill'ler (quick-wins, whats-next) için archive adımı gerekmez.
- Phase 16+ enforce: audit AMBER gate (Q-PHASE15-ARCHIVE-INTEG-01).

## Enforcement

- CI: `tests/ci/test_run_skill_python.py` — substring-key detection multi-line format respect doğrular.
- Helper exec: `python3 scripts/ci/run_skill_python.py {skill}/SKILL.md` exit=0 ZORUNLU.
- W3-W3-α strict mode: `.github/workflows/ci.yml` 3 governance step `continue-on-error: false` (drift-check + schema-validate + glossary-audit).
- Manuel review: PR review checklist "Skill body 1. Python block sys.path marker var mı veya helper auto-prepend kapsamında mı?" maddesi.
