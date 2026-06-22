# WORKER PROMPT — B6: Recon Hardening + Kapı İnce-Ayar (CCE kabul-öncesi)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Sıfır context varsay. Bu batch B1-B5'in ÜSTÜNE biner (hepsi commit'li). B5 **canlı kanıt testi 8/8 kapı PASS verdi** ama 3 gerçek-dünya bulgusu çıkardı — bunları kapatıyorsun (bu, `new-blog` `status: active`'e flip'in ön koşulu). Bitince handoff raporu döndür — **PUSH ETME.**
>
> Önce oku: `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` (§4a recon, §6 kapılar), B5 kanıt raporu `outputs/cce-proof/2026-06-22-maine-coon/proof.md` (§"Engine bulguları"), ve B5'in geçici workaround'u `outputs/cce-proof/2026-06-22-maine-coon/strip_chrome.py` (Görev 1'de kalıcılaştıracağın mantık).

## Kritik mimari kural
Saf Python (stdlib `html.parser`, ⚠️ bs4 YOK). Pure-transform disiplini: import side-effect yok, idempotent, CLI ayrı. MCP çağrısı YOK. B1-B5 **fonksiyon imzalarını DEĞİŞTİRME** (yalnız davranış düzeltmesi + yeni modül). Plugin-agnostik: proje slug literal YASAK.

---

## Görev 1 — 🔴 Recon content-scoping (KRİTİK, active flip ön koşulu)

**Sorun (B5 canlı bulgusu):** `competitor_recon_transform` ham fetch'teki HER `<ul>/<table>/<h2>/<strong>`'u sayıyor. Gerçek TR sitelerinde menü/footer/ilgili-yazı "chrome"u → `structure_ceiling.lists=87`, `gap.must_cover_headings=148` saf gürültüyle şişti (spec §4a: rakip kapsamı = MAKALENİN kapsamı, navigasyonu değil).

**Çözüm (B5'in `strip_chrome.py`'sini kalıcılaştır):**
- Create: `scripts/production/content_scope.py` — `strip(html: str) -> str` (içerik-koruyan chrome ayıklayıcı). `strip_chrome.py`'deki `_ChromeStripper` mantığını birebir taşı + dökümante et:
  - **Kural 1:** `nav/header/footer/aside` alt-ağaçlarını tümüyle at (nested-depth sayımlı).
  - **Kural 2:** bir `<ul>/<ol>`'u SADECE **link-only** ise at: `li_count >= 1 AND her <li> bir <a> içeriyor AND prose_chars <= max(8, anchor_chars // 10)` (navigasyon/footer menüsü). Prose taşıyan içerik listeleri (bazı `<li>` link'lese bile) KORUNUR.
  - Geri kalan her şey verbatim korunur (başlık, paragraf, içerik tablosu, içerik listesi, `<strong>`). Açık kalan listeleri içerik olarak flush et.
  - stdlib `html.parser`, idempotent (`strip(strip(x)) == strip(x)`), import side-effect yok.
- Modify: `competitor_recon_transform.py` — `transform(serp_json, scraped_pages, *, market)` İÇİNDE, her `scraped_page`'in HTML'ini parse etmeden ÖNCE `content_scope.strip(page["html"])` uygula. İmza ve çıktı şeması (COMPETITOR_COLUMNS) DEĞİŞMEZ — yalnız artık chrome-temiz DOM ölçülür.
- Test: `tests/scripts/test_content_scope.py` — fixture'larla kanıtla:
  - nav/footer/aside alt-ağacı atılır; içindeki liste/başlık sayılmaz.
  - link-only `<ul>` (her li bir `<a>`) atılır; prose-taşıyan içerik listesi KORUNUR.
  - içerik tablosu/başlık/paragraf bozulmadan geçer (içerik kelime sayısı düşmez).
  - idempotent: `strip(strip(x)) == strip(x)`.
- Test (entegrasyon): `competitor_recon` artık chrome-şişmesi YOK — menü-dolu bir fixture sayfası → tables/lists yalnız içerik yapılarını sayar.

```python
# tests/scripts/test_content_scope.py örnek
from scripts.production import content_scope as cs
def test_drops_nav_subtree():
    html = '<nav><ul><li><a href="/">Ana</a></li><li><a href="/blog">Blog</a></li></ul></nav><h2>İçerik</h2><p>metin</p>'
    out = cs.strip(html)
    assert "Ana" not in out and "İçerik" in out
def test_drops_link_only_menu_keeps_content_list():
    menu = '<ul><li><a href="/a">A</a></li><li><a href="/b">B</a></li></ul>'
    content = '<ul><li>Haftada 2-3 kez tara, keçeleşmeyi önler</li><li>Tüy dökme döneminde her gün tara bakım için</li></ul>'
    out = cs.strip(menu + content)
    assert "/a" not in out and "keçeleşmeyi" in out
def test_idempotent():
    html = '<footer><p>x</p></footer><h2>K</h2><p>içerik metni burada</p>'
    assert cs.strip(cs.strip(html)) == cs.strip(html)
```

**DİKKAT:** B1'in mevcut `test_competitor_recon_transform.py` fixture'ları temiz HTML kullanıyor (chrome yok) → `strip` no-op olmalı, testler GREEN kalmalı. Kalmıyorsa strip'in içeriği bozduğu yer vardır — düzelt (içerik korunmalı).

## Görev 2 — Gap dürüst-atlama dedup (`quality_gates.py`)

**Sorun (B5):** gap kapısı `skip_comments >= len(uncovered)` derken `uncovered`'ın **ham (dedup'suz)** uzunluğunu kullanıyor → aynı madde hem `must_cover_headings` hem `must_mention_entities`'te ise iki kez sayılıyor (B5'te 19 benzersiz → 32 ham). Yazar her benzersiz maddeyi atlasa bile sayı tutmayabilir.

**Çözüm:** gap kapısında `uncovered` set'ini **normalize + dedup** et (case-insensitive, trim) — karşılaştırmayı benzersiz uncovered maddeye göre yap. İmza/dönüş şekli (`GateResult`) değişmez. Test: aynı madde iki gap listesinde → tek sayılır; doğru sayıda skip yorumu → PASS.

## Görev 3 — P0 quote-claim regex ince-ayar (`quality_gates.py`)

**Sorun (B5):** P0 `_QUOTE` regex tırnak içi ≥12 karakteri "alıntı claim" sayıp kaynak istiyor → `"köpek karakterli kedi"` gibi **terim vurgusunu** da yakalıyor (gerçek alıntı değil).

**Çözüm:** gerçek alıntıyı terim-vurgusundan ayır — alıntı claim SADECE: `«…»` bloğu **VEYA** ≥6 kelimelik tırnaklı blok. Kısa (≤5 kelime) çift-tırnaklı terim vurgusu kaynak istemez. İmza değişmez. Test: kısa terim vurgusu → P0 tetiklemez; uzun gerçek alıntı (kaynaksız) → P0 RED.

---

## TDD + Kabul

- [ ] Her görev: failing test → implement → pass (TDD).
- [ ] `pytest tests/scripts/ -q` **tamamen yeşil** (B1-B5 + B6); özellikle `test_competitor_recon_transform.py` ve `test_quality_gates.py` GREEN kalır.
- [ ] **Kanıt (zorunlu):** B5 ham scrape'ini content-scoping'le yeniden ölç — `outputs/cce-proof/2026-06-22-maine-coon/raw/scraped_pages.json`'u `competitor_recon`'tan geçir, `structure_ceiling.lists`'in artık ~87 değil **gerçekçi (≤10)** olduğunu handoff'ta sayıyla göster (strip_chrome workaround'u olmadan, transform içinden).
- [ ] `content_scope.py` saf, idempotent, stdlib; proje slug literal yok; bs4 yok.
- [ ] B1-B5 fonksiyon imzaları korundu (yalnız davranış + yeni modül).
- [ ] FULL SUITE (`pytest -q`) yeşil — regresyon yok.
- [ ] Handoff: git diff --stat + pytest sonucu + dosya listesi + content-scoping öncesi/sonrası ceiling sayısı + açık sorular. PUSH YOK.

## Not (manager'a)
Bu batch geçince `new-blog` `status: active`'e flip + tüm CCE (B1-B6) toplu push manager'da. B5'in geçici `outputs/.../strip_chrome.py` + `build_brief_proof.py` dosyaları kanıt artefaktı — repo koduna karışmaz (outputs/ altında kalır).
