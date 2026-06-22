# WORKER PROMPT — B5: Gerçek Konu Kanıt Testi (CCE)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Bu batch B1+B2+B3+B4'ün ÜSTÜNE biner (hepsi commit'li olmalı — manager doğrular). Bu batch **canlı MCP kullanır** (Scrapling/DFS/GSC) — maliyet sınırı YOK (operatör kararı: "her içerik kıymetli"). Bitince handoff + kanıt raporu döndür — **PUSH ETME.**
>
> Önce oku: tasarım `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` (§2 başarı kriteri, §8 kalite ölçümü); master plan; `skills/production/new-blog/SKILL.md` (B4'ün güncellediği CCE akışı).

## Görev

CCE motorunu **gerçek bir Türkçe konuda uçtan uca çalıştır** ve §2 başarı kriterini (rakipten ölçülebilir biçimde kaliteli) **kanıtla**. Bu, motorun "her zaman rakipten kaliteli" iddiasının canlı doğrulamasıdır (tasarım F5).

## Konu

Operatör/manager bir `primary_keyword` + `market`/`locale` + `content_type` verir (örn. aktif proje `demo-petcare-tr`'den düşük-riskli bir bilgilendirici konu). **Konu verilmeden başlama** — manager'dan iste. (Plugin-agnostik: çıktıda proje slug literal yok.)

## Akış (SKILL.md CCE döngüsünü canlı sür)

1. **Silahlan (MCP):** DFS `serp_organic_live_advanced` depth=10 (served `location_code` doğrula — Method-C disiplini, TR ise 2792) → top-10 organik. Her biri için Scrapling `stealthy_fetch` (×10, zorunlu) → ham HTML. DFS keyword (`keyword_suggestions` substring + `keyword_overview` + `search_intent`) + AIO (`serp` `ai_overview` öğesi). GSC `search_analytics` (varsa). Ham JSON'ları kaydet.
2. **Brief:** `new_blog.assemble_brief(...)` → Brief Paketi (gap + structure_ceiling + aio + keyword_set). Brief'i kaydet/raporla.
3. **Yaz:** craft rehberi (R-149..R-153) uygulayarak içeriği yaz — pain-mirror intro + somut örnek + marka sesi + rakip-üstü özgün değer (`data-original="true"`) + derin H2'ler. **Uydurma YASAK** (P0): gap maddesi için kaynağın yoksa `<!-- gap-skipped: kaynak yok -->` ile dürüstçe atla.
4. **Kapı:** `new_blog.evaluate(content_html, brief, round_num, max_rounds=3)` → action PASS/REWRITE/AMBER_TERMINAL. REWRITE ise feedback'le tekrar yaz (≤3 tur).
5. **Kanıt:** PASS'e ulaş (ya da AMBER_TERMINAL'de eksik raporu).

## Kanıt raporu (zorunlu çıktı — bu batch'in asıl teslimatı)

Üret: `outputs/cce-proof/{date}-{slug}/` altında — (a) `brief.json`, (b) `article.html`, (c) `gate_report.json` (`run_all` çıktısı), (d) `proof.md`:

**`proof.md` şu metrikleri KANITLA (tasarım §8):**
- **Kapsam:** `gap.must_cover_*` toplam madde sayısı vs kapsanan (gap=0 veya dürüst-atlandı listesi).
- **Yapı:** üretilen anlamlı tablo+liste sayısı vs `structure_ceiling` (≥ tavan+1 mi?).
- **Özgünlük:** `data-original` öğe(ler)i + neden rakiplerde yok.
- **AEO:** intro cevap-önce mi + `aio.answer_points` kapsama %.
- **8 kapı tablosu:** her kapı PASS/RED + kaç turda PASS'e ulaşıldı.
- **Rakip karşılaştırması:** en iyi rakip vs bizim (kapsam/yapı/özgünlük) — "geçtik mi?" net cevap.

## Kabul kriterleri

- [ ] Gerçek konuda CCE uçtan uca koştu (canlı MCP); ham JSON + brief + article + gate_report kaydedildi.
- [ ] 8 kapı **PASS** (veya AMBER_TERMINAL ise net eksik raporu + neden).
- [ ] `proof.md` §8 metriklerini sayıyla kanıtlıyor; "rakibi geçtik mi" sorusuna kanıtlı cevap.
- [ ] P0 Doğruluk: hiçbir uydurma claim yok (kaynaksız gap dürüstçe atlanmış).
- [ ] Çıktıda proje slug literal yok; üretilen HTML `pse-` prefix.
- [ ] Handoff raporu manager'a: kanıt özeti + motorun gerçekten rakibi geçip geçmediği + kapı eşik/craft kuralı için ayar önerileri (varsa). PUSH YOK.

## Not (manager'a)

Bu batch motorun **kabul geçididir**. PASS + güçlü kanıt → manager production skill'lerini (`new-blog`) `status: active`'e flip edebilir + push. Zayıf kanıt → kapı eşikleri / craft kuralları ayarlanır (B2/B3 revize turu).
