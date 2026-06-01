---
name: Single Source of Truth
status: enforced
applies_to: [plugin, workspace]
spec_section: "§8.1"
---

# Single Source of Truth

## Kural
Bir terim, schema, template, kural veya veri TEK YERDE tanımlanmak ZORUNDADIR (MUST). Aynı bilgi ikinci bir yere kopyalanmamalı (MUST NOT); ihtiyaç halinde referans verilmelidir (REQUIRED). Plugin (motor) read-only tooling tutar; workspace (proje deposu) runtime veriyi tutar — bu ayrım korunur.

## Why
Drift, çoğunlukla iyi niyetli kopyala-yapıştırla başlar: aynı kural spec'te bir biçimde, README'de başka biçimde yazıldığında zamanla iki sürüm de "doğru" gibi görünür ve sistem hangisinin geçerli olduğunu kaybeder. Plugin agnostiklik (ADR-008) bu disiplinin pratik sonucudur: motor proje verisini taşımaz; aksi halde tek bir gerçek tanımı belirlemek imkânsızlaşır.

## How to Apply
- Bir terim/glossary girdisi yalnızca `docs/GLOSSARY.md`'de tanımlanır (→ rules/glossary-discipline.md).
- Bir schema yalnızca `schemas/{name}.schema.json` dosyasında yaşar; başka yerde alan listesi tekrarlanmaz, schema'ya `$ref` verilir.
- Plugin repo: skill, command, hook, script, schema, rule, template — read-only tooling.
- Workspace repo: project memory, `events.jsonl`, `master.xlsx`, `outputs/`, `inbox/`, `state/` — runtime veri.
- Kural metni `rules/*.md`'de; spec yalnızca özet ve gerekçe; tekrarlanan bullet listesi yasak.
- Doküman tekrarı yerine link: `→ rules/schema-first.md` formatında cross-link kullan.

## Examples (Doğru)
- Spec §8.6 naming kurallarını özetler; tam normatif metin `rules/naming.md`'dedir; başka yerde yoktur.
- `master-excel.xlsx` schema'dan üretilir (ADR-009); sheet yapısı yalnızca `master-excel.schema.json`'da tanımlıdır.
- Plugin `commands/pseo-init-project.md` proje adı içermez; proje verisi workspace'tedir.

## Anti-Patterns (Ihlal)
- Aynı kural metni hem `docs/spec.md` hem `README.md` içinde — iki yer divergea açıktır.
- Plugin içinde hard-coded proje slug'ı (gerçek bir pilot/müşteri proje adı) — §8.3 + SSOT ihlali.
- `schemas/foo.schema.json` ve `scripts/foo_writer.py` içinde alan listesinin elle tekrarlanması — schema değişince script unutulur.
- Workspace verisinin (örn: `events.jsonl` örnekleri) plugin repo'ya commit edilmesi.

## Enforcement
- CI: `scripts/checks/grep_project_names.sh` plugin repo'da proje slug'ı arar.
- CI: `tests/duplication/test_no_duplicate_glossary_terms.py`.
- Manuel review: PR review checklist "Bu bilgi başka bir yerde de var mı?" maddesi.
- Cross-link: → rules/append-only-state.md, → rules/schema-first.md.

## Reports Frontmatter Policy (H-F v1.4-deep-audit-fix Tier 3 closure)

`templates/reports/*.md` içindeki rapor template'leri iki tipe ayrılır; tip bazında frontmatter zorunluluğu farklıdır:

**Tip A — Multi-project aggregation OR schema-validated** (frontmatter ZORUNLU):
- `portfolio-{heatmap,kpi-trend,monthly-roundup,overview,task-heatmap,weekly-brief}` — read-only multi-project agregator (`schemas/portfolio-config.schema.json` const)
- `monthly-report` — `schemas/monthly-report.schema.json` v1.0 conformant
- `monitoring-weekly` + `weekly-summary` — period-rolling lifecycle aggregators
- Frontmatter: `report_kind`, `project_id`/`portfolio_id`, period boundaries, `generated_at` MUST.

**Tip B — Single-project descriptive** (frontmatter OPSIYONEL; `<!-- rules consumed -->` HTML comment block ZORUNLU):
- 17 single-project transform raporu (`cannibalization`, `cluster-map`, `competitive-analysis`, `content-decay`, `content-gaps`, `dfs-pull`, `drift`, `geo-analysis`, `gsc-pull`, `internal-links`, `new-content-plan`, `on-page-audit`, `quickwin`, `schema-audit`, `scrapling-ops`, `tech-audit`, `topical-map`).
- Comment block formatı:
  ```html
  <!--
    Reports Frontmatter Policy: single-project descriptive (rules/single-source-of-truth.md#reports-frontmatter-policy).
    Rules consumed: rules/<rule>.md, rules/events-writer.md, rules/append-only-state.md
  -->
  ```
- Bu blok skill orchestrator'un hangi rule'ları enforce ettiğini deklarasyondur; SSOT cross-link rapor kullanım context'inde explicit kalır.

**Why:** 9 multi-project rapor schema-validated → frontmatter zaten authority; 17 single-project descriptive rapor frontmatter eksikti (H-F audit finding) — HTML comment block lightweight çözüm, render output'unu etkilemez (HTML comments markdown'da invisible).

## F-XX Namespace Rules (v2.3 retro — R-7 / Q-PHASE-4-WORKER-01)

`F-XX` cross-sheet invariant labels can appear in TWO disjoint stores; both may use the same `F-XX` numerals **if** their contexts are disjoint:

1. **`schemas/cross-sheet-invariants.json` instance entries** — persistent registry. Audit history references these IDs, so ADR-038 applies: numbering is monotonic-but-gap-tolerant and **renumbering is FORBIDDEN**.
2. **`skills/governance/drift-check/SKILL.md` Engine Self-Governance subsection narrative labels** — doc-only pedagogical labels with NO audit-history references. These are **EXEMPT** from the ADR-038 renumber-forbidden policy (they are teaching labels, not registry IDs).

**v1.8 Phase 6 reconciliation:** the engine self-governance labels `F-23..F-28` (store 2) were renumbered to `F-29..F-34` to disambiguate from the `cross-sheet-invariants.json` `F-23` SF MCP entry (store 1). The registry ID `F-23` (store 1) was NOT touched — renumbering a registry ID would violate ADR-038.

→ cross-ref: ADR-038 (`docs/DECISIONS.md`), → rules/schema-first.md.
