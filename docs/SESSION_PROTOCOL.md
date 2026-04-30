# Session Protocol

Spec §13'ün özeti. Fresh session'lar bunu okur. Manager session'ın nasıl çalıştığını tanımlar.

## 1. Manager Session Nedir (§13.1)
Manager session = **karar verici** session. Kod yazan ana worker DEĞİL.

Görevleri:
- Plan tutmak (`docs/PHASE_STATUS.md`)
- Worker session promptları üretmek (`docs/WORKER_PROMPTS.md` template'lerinden)
- Worker çıktılarını işlemek (Worker Output Package format)
- `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, `docs/CONTEXT_LEDGER.md` güncellemek
- Phase gateway (GO/NO-GO) kararı vermek

## 2. Fresh Session Wakeup Sequence (§13.2)
Fresh session açıldığında bu sırayla:
1. Bootstrap prompt'u oku (kullanıcı paste eder)
2. Spec doc'unun `§1`, `§13`, `§17`'sini oku — `docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md`
3. `docs/PHASE_STATUS.md` oku
4. `docs/OPEN_QUESTIONS.md` oku
5. `docs/DECISIONS.md` son 5 ADR oku
6. `docs/REFERENCE_INDEX.md` oku
7. **DUR.** Geri kalanı sadece ihtiyaç duyduğunda oku.

**Toplam ilk yükleme: <15KB** (1M context window'un <%2'si).

## 3. Subagent Dispatch Rule (§13.3)

**Worker'a delege et:**
- Çok dosya okuma gereken araştırma
- Birden fazla dosya yazma gereken implementation
- Test koşturma
- Schema validation
- Migration script yazma

**Manager'da kalsın:**
- Plan kararları
- Phase gateway kararı
- DECISIONS güncelleme
- OPEN_QUESTIONS resolve
- Worker prompt yazma

## 4. Worker Output Package Format (§13.4)

Worker session'lar manager'a dönerken **kompakt paket** dönmeli:

```markdown
## Worker Output Package

**Worker:** {worker name}
**Phase:** {phase id}
**Task:** {short task description}

### Files Created/Modified
- path/to/file.md (NEW, 142 lines)
- path/to/other.json (MODIFIED, +12/-3)

### Decisions Made
- {decision 1 — 1 line}
- {decision 2 — 1 line}

### Open Questions Surfaced
- {q1 — 1 line}

### Next Step Recommended
- {next step}

### Verification
- [x] schema-validate PASS
- [x] tests PASS
- [ ] drift-check (not run — out of scope)
```

Manager bu paketi alır, ilgili dosyaları günceller, sonraki adıma geçer.
**Manager worker transcript'ini full okumaz, sadece paketi okur.**
