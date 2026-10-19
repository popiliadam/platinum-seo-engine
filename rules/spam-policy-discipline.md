---
name: Spam Policy Discipline
status: enforced
applies_to: [plugin]
applied_to_skills: [new-blog, revise-content, programmatic pages]
source: docs/superpowers/plans (revision map S-02, S-03 — 2026-10-13 audit)
spec_section: "Google spam policies (2026-08-28) + gen-AI content guidance (2026-10-01)"
---

# Spam Policy Discipline

Motor toplu içerik üretebildiği için Google'ın spam politikasının iki maddesine doğrudan maruzdur: **ölçekli içerik kötüye kullanımı** (scaled content abuse — çok sayıda düşük değerli sayfayı, nasıl üretildiğinden bağımsız olarak, sıralama için üretmek) ve 2026-08-28 metnindeki **üretken AI cevaplarını manipüle etme girişimi**. Ayrıca Google'ın üretken AI içerik kılavuzu (2026-10-01), AI ile üretilmiş içeriğin — title, meta description, structured data ve alt text dahil — yayından önce bir kişi tarafından kontrol edilmesini ister. Bu dosyadaki kurallar kodla zorlanır (`scripts/production/publication_guard.py`).

## Rules

### R-154: Ölçekli İçerik Koruması (Scaled Content Guard)

**Statement.** Yeni sayfa üretiminden önce üç kontrol: (1) son 7 gündeki yeni sayfa sayısı haftalık tavanın altında (varsayılan 5; proje ayarı R-61 sonrası), (2) taslak mevcut sayfalardan hiçbiriyle 5-kelimelik parça örtüşmesi %50'nin üstünde değil, (3) `user_value` — bu sayfanın kullanıcıya mevcut sayfalardan farklı olarak ne kattığı — dolu. Biri sağlanmazsa üretim durur.

**Rationale.** Aynı şablondan çıkan, birbirine benzeyen sayfalar arama talebini değil sayfa sayısını büyütür; spam politikası bunu kapsar. Tavan ve benzerlik kontrolü "daha az, daha iyi sayfa" yönünde varsayılan baskı yaratır; `user_value` alanı her sayfanın var olma nedenini yazılı hâle getirir.

**Enforcement.** `publication_guard.check_new_content` — new-blog Step 1b + Step 8 (DURUR #10). Programatik sayfa üreten her yeni akış aynı fonksiyonu çağırır.

**Failure mode.** RED — üretim durur, neden yazılır.

### R-155: Yayın Öncesi İnsan Doğrulaması

**Statement.** Her içerik paketi `verification.json` taşır: `verified_by` (kim), `verified_at` (ne zaman, UTC) ve `checked` listesi en az `text`, `title`, `meta_description`, `structured_data`, `alt_text`. Kayıt eksikse paket hazır değildir ve yayın/deploy adımı başlamaz. Kayıt motorda kalır; sayfaya görünür bir "AI" ya da "kontrol edildi" ibaresi eklenmez (görünür AI ibaresi yasağı geçerli).

**Rationale.** Google üretken AI içerik kılavuzu (2026-10-01): AI üretimi içerik ve meta veriler yayından önce bir insan tarafından doğrulanmalı. YMYL için R-124 uzman imzası bunun üstüne ek bir şarttır.

**Enforcement.** `publication_guard.verification_status` / `python3 scripts/production/publication_guard.py verify <verification.json>` (exit 0 = hazır) — new-blog Step 11 (DURUR #11).

**Failure mode.** RED — yayın bloklu.

## Cross-References

- → [content-quality](content-quality.md) — R-32 site itibarı politikası, Principle 3 (anti-cheap-content)
- → [content-craft-discipline](content-craft-discipline.md) — yapı ilkesi (her sayfa kendi sorusuna göre)
- → [content-eeat-discipline](content-eeat-discipline.md) — R-124 YMYL uzman imzası
