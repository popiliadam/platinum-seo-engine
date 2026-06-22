# WORKER PROMPT — B1: Silahlanma Motoru (Competitive Content Engine)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Bu projede sıfır context'in olduğunu varsay. SADECE bu dosyadaki görevleri yap. Diğer batch'lere (B2/B3/B4) ait dosyalara DOKUNMA. Bitince manager'a handoff raporu döndür — **PUSH ETME.**
>
> Tam tasarım: `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md`. Master plan + Brief Paketi şeması: `docs/superpowers/plans/2026-06-22-competitive-content-engine.md` (önce bu ikisini oku).

## Görevin

İlk-10 organik rakipten toplanan ham veriyi **Brief Paketi**'ne dönüştüren 3 saf-Python transform'u TDD ile yaz. Bu paket, içerik yazımının "ne kapsanacağı + rakip yapı tavanı + AI Overview hedefleri" girdisidir.

## Kritik mimari kural (yanlış anlama = baştan yanlış)

**Script'ler MCP ÇAĞIRMAZ.** MCP'yi Claude (skill) çağırır, ham JSON'u dosyaya yazar; senin script'in o JSON'u CLI argümanıyla `json.load` eder. Senin yazdığın her şey **saf Python** (argparse CLI + pure transform). Emsal oku: `scripts/ingestion/dfs_pull.py` (özellikle docstring + `main()` + `--raw-*` argparse). Pure-transform disiplini emsali: `scripts/planning/new_content_plan_transform.py` docstring.

## Dosyalar

- Create: `scripts/production/__init__.py` (boş)
- Create: `scripts/production/competitor_recon_transform.py`
- Create: `scripts/production/keyword_aio_intel_transform.py`
- Create: `scripts/production/build_brief.py`
- Test: `tests/scripts/test_competitor_recon_transform.py`
- Test: `tests/scripts/test_keyword_aio_intel_transform.py`
- Test: `tests/scripts/test_build_brief.py`

## Arayüz sözleşmesi (B2/B4 buna bağlı — imzalar AYNEN bunlar)

```python
# competitor_recon_transform.py
def transform(serp_json: dict, scraped_pages: list[dict], *, market: str) -> list[dict]:
    """serp_json: ham DFS serp_organic_live_advanced (top-10 organik URL kaynağı).
    scraped_pages: [{"url": str, "html": str}, ...]  (Claude'un Scrapling ile çektiği DOM).
    Döner: competitors[] — her biri {url, h2_h3:[str], questions:[str], entities:[str],
           tables:int, lists:int, word_count:int}.
    'tables' = ANLAMLI tablo (≥2 satır VE ≥2 kolon); 'lists' = ANLAMLI liste (ul/ol, ≥3 <li>).
    'questions' = '?' ile biten başlıklar + FAQ Q metinleri. 'entities' = H2/H3 + <strong>
    içindeki tekilleştirilmiş isim/terim adayları (deterministik; semantik eşleştirme B4'te)."""

# keyword_aio_intel_transform.py
def transform(raw_overview: dict, raw_suggestions: dict, raw_serp: dict, *, market: str) -> dict:
    """raw_*: ham DFS JSON'ları (D-003 dual-shape: REST envelope VEYA flat wrapper — tolere et;
    şekil normalizasyonunu scripts.ingestion.dfs_pull._normalize_dfs_response'tan IMPORT et, kopyalama).
    Döner: {"keyword_set":[{kw,volume,intent,source}], "aio":{present:bool, answer_points:[str], cited_sources:[str]}}.
    AIO: raw_serp içinde item type 'ai_overview' varsa answer_points (madde metinleri) + cited_sources (referans URL'ler);
    yoksa {present:False, answer_points:[], cited_sources:[]}."""

# build_brief.py
def build(competitors: list[dict], keyword_aio: dict, our_existing: dict | None, *, topic: dict) -> dict:
    """competitors: competitor_recon_transform.transform çıktısı.
    keyword_aio: keyword_aio_intel_transform.transform çıktısı.
    our_existing: {"headings":[str],"questions":[str],"entities":[str]} (mevcut/planlı içeriğimiz) veya None.
    topic: {primary_keyword, content_type, locale, market}.
    Döner: master plan'daki tam Brief Paketi JSON (schema_version='1.0').
    gap.* = competitor coverage birleşimi − our_existing coverage (None ise tüm coverage gap).
    structure_ceiling = competitors üzerinde max(tables), max(lists), max(h2 sayısı), max(word_count)."""
```

`generated_at` ASLA `Date.now()` benzeri runtime'dan üretilmez — CLI'da `--generated-at` argümanıyla geçilir (idempotency: same input+arg → byte-identical output). Default None → alan `null`.

## TDD adımları (her transform için döngü tekrarla)

- [ ] **Step 1 — Failing test yaz.** Örnek (competitor_recon):

```python
# tests/scripts/test_competitor_recon_transform.py
from scripts.production import competitor_recon_transform as cr

def test_counts_meaningful_table_only():
    html = ('<h2>Fiyat Karşılaştırması</h2>'
            '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>'
            '<table><tr><td>tek hücre</td></tr></table>')  # 2. tablo anlamsız
    out = cr.transform({"tasks":[{"result":[{"items":[]}]}]},
                       [{"url":"https://x.example/p","html":html}], market="TR")
    assert out[0]["tables"] == 1          # sadece anlamlı tablo
    assert "Fiyat Karşılaştırması" in out[0]["h2_h3"]

def test_question_heading_detected():
    html = '<h3>İmplant ağrır mı?</h3><p>...</p>'
    out = cr.transform({"tasks":[{"result":[{"items":[]}]}]},
                       [{"url":"https://x.example/p","html":html}], market="TR")
    assert "İmplant ağrır mı?" in out[0]["questions"]
```

- [ ] **Step 2 — Testi çalıştır, FAIL gör.** `pytest tests/scripts/test_competitor_recon_transform.py -v` → FAIL (module/func yok).
- [ ] **Step 3 — Minimal implementasyon yaz** (BeautifulSoup ile parse; anlamlı tablo/liste kuralı; idempotent; import-side-effect yok).
- [ ] **Step 4 — Testi çalıştır, PASS gör.**
- [ ] **Step 5 — Commit.** `git add scripts/production/ tests/scripts/test_competitor_recon_transform.py && git commit -m "feat(cce): B1 competitor_recon transform — rakip kapsama envanteri (TDD)"`

build_brief için zorunlu ek test:
```python
def test_gap_is_competitor_minus_ours():
    comps = [{"url":"u","h2_h3":["A","B"],"questions":["Q1?"],"entities":["E1"],"tables":2,"lists":1,"word_count":900}]
    ka = {"keyword_set":[],"aio":{"present":False,"answer_points":[],"cited_sources":[]}}
    brief = build_brief.build(comps, ka, {"headings":["A"],"questions":[],"entities":[]},
                              topic={"primary_keyword":"x","content_type":"guide","locale":"tr-TR","market":"TR"})
    assert "B" in brief["gap"]["must_cover_headings"]      # rakipte var, bizde yok
    assert "A" not in brief["gap"]["must_cover_headings"]  # bizde var → gap değil
    assert brief["structure_ceiling"]["tables"] == 2
    assert brief["schema_version"] == "1.0"
```

## Kabul kriterleri

- [ ] 3 transform + `__init__.py` oluşturuldu; her biri import-side-effect'siz, idempotent, argparse CLI'lı.
- [ ] DFS dual-shape `_normalize_dfs_response` IMPORT edildi (kopyalanmadı).
- [ ] Anlamlı tablo (≥2×2) / liste (≥3 li) ayrımı testle doğrulandı.
- [ ] gap = rakip − bizim; structure_ceiling = max; Brief Paketi master plan şemasına BYTE uyumlu.
- [ ] Tüm yeni testler GREEN; `pytest tests/scripts/test_*recon*.py tests/scripts/test_*aio*.py tests/scripts/test_build_brief.py -v` temiz.
- [ ] Proje slug literal YOK (grep ile kendin doğrula). MCP çağrısı YOK (saf Python).
- [ ] Handoff raporu manager'a (git status/diff --stat + pytest sonucu + dosya listesi + açık sorular). PUSH YOK.
