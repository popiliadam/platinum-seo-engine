# Fresh-session prompt — Senaryo #2: 45-Skill Kontrat Denetimi (dynamic workflow)

**Kullanım:** Aşağıdaki `---` çizgisinden sonraki bloğun tamamını kopyalayıp yeni
(fresh) bir Claude Code oturumuna yapıştır. Sadece-okuma audit'tir; düzeltme ayrı
onayla yapılır.

**Seri bağlamı:** Workflow-audit serisinin 2. adımı. Menü:
1. Codebase kalite+güvenlik audit'i — ✅ bitti, main'de
2. **45-skill kontrat denetimi — BU PROMPT**
3. Release-öncesi hazırlık taraması (gelecek)
4. Doküman↔kod drift (kısmen yapıldı)
5. Test sağlığı (kısmen yapıldı — B test-net)
6. Şema↔migration↔kullanım tutarlılığı (gelecek)

---

Platinum SEO Engine — Senaryo #2: 45-SKILL KONTRAT DENETİMİ (dynamic workflow).

NEDIR: Workflow-audit serisinin 2. adımı. 1. adım (codebase kalite+güvenlik
audit'i) bitti ve main'e gitti — referans:
  - docs/audits/2026-06-04_deep_quality_security_audit.md (+ .findings.json)
  - hafıza: "Deep Audit 2026-06-04", "events.jsonl In-Place Rewrite"
Bu adımın sorusu farklı: KOD doğru mu değil — "her SKILL.md ne VAAT ediyor,
implementasyon ve paired test bu vaadi TUTUYOR mu?" (kontrat bütünlüğü).

NASIL ÇALIŞTIR — DYNAMIC WORKFLOW (Workflow tool, açık opt-in: bunu çoklu-ajan
orkestrasyon olarak çalıştırmanı istiyorum):
  1. Önce skill'leri keşfet: skills/{discovery,governance,ingestion,meta,
     planning,production,publishing,reporting}/*/SKILL.md — sayıyı doğrula
     (~45). Sayıyı log'la.
  2. FIND fazı: her skill için 1 ajan (paralel, ~45). Her ajan O skill'in
     SKILL.md'sini + implementasyon script'(ler)ini (scripts/<kategori>/...) +
     paired test'ini (tests/...) OKUR ve aşağıdaki kontrat boyutlarında somut
     ihlal arar. Her bulgu file:line + kanıt içermeli; tahmin yok.
  3. Barrier: tüm bulguları topla + benzersizleştir.
  4. VERIFY fazı: her bulguyu düşmanca doğrula (bulgu başına 2-3 bağımsız
     skeptik, gerçek SKILL.md+kodu okuyup "bu gerçek mi yoksa yanlış-pozitif/
     kasıtlı tasarım mı"). ≥2/3 onay = CONFIRMED. (1. adımda 34 ham bulgunun
     10'u böyle elendi — eleme bu işin asıl değeri.)
  5. SYNTH fazı: önem sırasına göre rapor + "neyi kaçırdık" eleştirmeni.
  Maliyet: 45+ ajan, token-yoğun — bilinçli kabul (sen istedin).

KONTRAT BOYUTLARI (her skill için ajan bunları sorgular):
  1. Trigger doğruluğu: SKILL.md description / "Use when" tetikleyici beyanı,
     skill'in GERÇEKTE yaptığıyla (body + scripts) uyuşuyor mu? Aşırı/eksik vaat?
  2. Status doğruluğu: FM status (active/wip/deprecated) ↔ body ↔ runtime
     gerçeği. (NOT: bu zaten tests/skills/test_status_declaration_parity.py ile
     guard'lı ve 8 skill 2026-06-04'te wip'e çekildi — guard'ın TUTTUĞUNU doğrula,
     sadece YENİ drift'i bulgu say. status'a kod dalı bağlı DEĞİL — declarative.)
  3. Paired test var mı + ANLAMLI mı: tests/ altında karşılığı var mı? Kontratı
     mı test ediyor yoksa "lastik damgası" mı (sadece enum üyeliği assert eden)?
     (1. audit rubber-stamp testleri buldu — bu paterni avla.)
  4. Autonomy tutarlılığı: FM autonomy (requires_approval, safe_auto_execute,
     confidence) ↔ skill'in gerçek yan etkileri + proje hard-kuralları. ÖZELLİKLE:
     dış API'ye otonom submit YASAK kalemler (Indexing API consent —
     feedback_indexing_api_consent; indexing-ping zaten düzeltildi, BAŞKA ihlal
     var mı?) ve AI-disclosure (feedback_ai_disclosure_ban).
  5. Capability vs implementasyon: skill var-olmayan bir runtime/yetenek vaat
     ediyor mu (stub) ve bunu "stub-mod kontratı" olarak belgelemiş mi?
  6. Inputs/outputs drift: SKILL.md'deki beyan edilen girdi/çıktı, script'in
     gerçek imzası/çıktı şemasıyla uyuşuyor mu?
  7. Cross-ref geçerliliği: skill'in andığı schema/rule/ADR referansları var mı
     ve eşleşiyor mu?

ZATEN ÇÖZÜLDÜ — TEKRAR BULGU SAYMA (sadece doğrula/regres kontrolü):
  - 8-skill active→wip (new-blog, revise-content, faq-optimization,
    content-remediation, generate-images, indexing-ping, verify-indexing,
    mark-done) — commit 3ddd13c.
  - indexing-ping autonomy requires_approval:true/safe_auto_execute:false +
    consent note; verify-indexing read-only GSC olduğu için auto-exec kaldı.
  - FM↔body status parity guard: test_status_declaration_parity.py.
  - İçerik R-XX validatörü (content_validator.py) ayrı SHIPPED — bu audit'in
    konusu değil.

ÇIKTI: docs/audits/<bugünün-tarihi>-skill-contract-audit.md (öncelikli rapor:
exec summary, severity'e göre bulgular file:line+kanıt+öneri, temalar) +
.findings.json (makine-okunur). Sadece-okuma: KOD/SKILL DEĞİŞTİRME. Bitince bana
özetle ve hangi bulguları düzeltelim diye SOR (1. adımdaki gibi — düzeltme ayrı
onay + TDD + Dev-QA loop).

KURALLAR: Public docs/rapor İngilizce; benimle sohbet Türkçe; ben kodlama bilmem,
basit Türkçe + tablo + öneri. Önce raporu/findings'i sun, kararı bana bırak.
