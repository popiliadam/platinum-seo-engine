# Contributing

Platinum SEO Engine'e katkı için kurallar. Foundation phase'lerinde (Phase 0–4) repo skeleton + manager/worker protokolü kuruluyor; skill phase'lerinde (Phase 5–13) paralel worker'lar implement ediyor.

## Otorite

- **Spec otoritedir.** `docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md` frozen authoritative input. Spec ile çelişen bir düzenleme önerisi varsa: önce `docs/OPEN_QUESTIONS.md`'ye soru olarak düşür, ADR ile karara bağla.
- **DECISIONS.md append-only.** Yeni karar = yeni ADR. Eski entry silinmez; superseded işaretlenir.
- **ARCHITECTURE.md yaşayan özettir** — spec ile çatışırsa spec wins; doc güncellenir.

## Manager/Worker Protokolü

- Manager session karar verir, plan yapar, worker dispatch eder, ADR yazar; **kod yazmaz**.
- Worker session dar scope'lu; manager'ın belirlediği görevi yapar; çıktısını **Worker Output Package** formatında verir (spec §13.4).
- Manager protokol detayı: `docs/SESSION_PROTOCOL.md`.

## Skill Yazımı

Skill kontratı `schemas/skill-frontmatter.schema.json` ile kilitli (Phase 1 deliverable). Yazım disiplini: `rules/skill-description-discipline.md` (Phase 2 deliverable; şimdilik placeholder referans). Auto-trigger kalitesi için spec §9'a bak.

## Phase Discipline

- İş **phase by phase** akar. Phase n+1'e geçmek için n'in acceptance kriteri PASS olmalı.
- Gateway phase'ler (özellikle **Phase 5**) ilerlemeyi bloklar; geçemezse foundation'a dönülür.
- Phase boyunca atomic commit'ler; phase sonu birleşik commit (ADR-002).

## Disiplinler

10 pazarlık edilemez disiplin (`rules/*.md`) drift-check ve CI tarafından otomatik denetlenir. Özet için `docs/ARCHITECTURE.md`. Single Source of Truth, Schema-First, Plugin = Proje-Agnostik öncelikli.

## Eski Repolar

`~/Documents/platinum-seo-core/` ve `~/Documents/platinum-premium-seo/` **READ-ONLY referans** (ADR-004). Migration sırasında `cp` ile kopyala; orijinal mutate etme. v1 acceptance + 1 hafta soak süresi sonrası silinir.

## Secrets

API key, token, parola asla repo'ya commit edilmez. `.env` (gitignore) veya keychain. `scripts/security/check_secrets.sh` pre-commit'te koşar.
