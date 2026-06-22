# WORKER PROMPT — B2: Kapı Motoru (Competitive Content Engine)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Sıfır context varsay. SADECE bu dosyadaki görevleri yap. B1/B3/B4 dosyalarına DOKUNMA. Bitince handoff raporu döndür — **PUSH ETME.**
>
> Tam tasarım: `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` §6. Brief Paketi şeması: `docs/superpowers/plans/2026-06-22-competitive-content-engine.md` (önce oku).

## Görevin

Üretilen içerik HTML'ini, B1'in ürettiği Brief Paketi'ne karşı ölçen **8 kapılı kalite motorunu** TDD ile yaz. Çıktı: hangi kapılar PASS/RED + Claude'a re-write feedback'i. Bu saf bir ölçüm motoru — içerik ÜRETMEZ, sadece DEĞERLENDİRİR.

## Kritik mimari kural

Saf Python (argparse CLI + pure functions). MCP YOK. Girdiler: (a) içerik HTML'i (string/dosya), (b) Brief Paketi JSON (B1 çıktısı, fixture'la test et — B1'i beklemene gerek yok, şema master plan'da sabit). BeautifulSoup ile HTML parse (mevcut dependency).

## Dosyalar

- Create: `scripts/production/quality_gates.py`  (B1 `scripts/production/__init__.py`'yi oluşturur; yoksa sen oluştur — çakışma değil, idempotent boş dosya)
- Test: `tests/scripts/test_quality_gates.py`
- Fixture: `tests/scripts/fixtures/cce/good_article.html`, `bad_article.html`, `sample_brief.json` (sen oluştur)

## Arayüz sözleşmesi (B4 orkestratör buna bağlı — imzalar AYNEN bunlar)

```python
from dataclasses import dataclass

@dataclass
class GateResult:
    gate: str              # "p0_truthfulness" | "gap" | "structure" | "depth" | "aeo" | "voice" | "originality" | "schema_visual"
    status: str            # "PASS" | "RED" | "AMBER"
    detail: str            # insan-okur kısa açıklama
    missing: list          # eksik maddeler (re-write feedback için; PASS'te [])

def run_all(content_html: str, brief: dict) -> dict:
    """Tüm kapıları çalıştırır. Döner:
    {"gates":[GateResult-as-dict...], "overall":"PASS"|"RED", "rewrite_feedback":[str...]}.
    overall=PASS ANCAK hiçbir kapı RED değilse. P0 RED ise overall kesin RED (gap'in üstünde)."""
```

## 8 kapının kesin kuralı

| Kapı | PASS şartı | RED feedback |
|---|---|---|
| `p0_truthfulness` | Her sayısal/quote claim'in yanında citation/kaynak işareti (`<a href>`/`<cite>`/parenthetical) var | "kaynaksız claim: …" |
| `gap` | `brief.gap.must_cover_*` her madde içerikte var **VEYA** içerikte `<!-- gap-skipped: kaynak yok -->` yorumuyla dürüst atlanmış | "kapsanmamış+kaynaklı: …" |
| `structure` | anlamlı tablo+liste sayısı ≥ `brief.structure_ceiling.tables+lists` **+1**; her >200 kelime H2'de ≥2 H3 | "yapı eksik: …" |
| `depth` | Hiçbir H2 yüzeysel değil (her H2 altında ≥1 paragraf VE ≥40 kelime gövde) | "sığ bölüm: …" |
| `aeo` | İlk `<p>` (intro) sorunun direkt cevabı (ilk cümlede primary_keyword + bir iddia); `brief.aio.answer_points` her madde içerikte işlenmiş (aio.present=False ise yalnız intro şartı) | "intro cevap-önce değil / AIO noktası eksik: …" |
| `voice` | AI-imza blocklist ("Aslında", "Sonuç olarak", "Özetle", "Bilindiği gibi") yoğunluğu ≤ 1/1000 kelime; klişe açılış yok | "AI-imza: …" |
| `originality` | Rakip `entities`/`questions` kümesinde OLMAYAN ≥1 özgün öğe (kendi tablosu/aracı/vakası — `data-original="true"` işaretli blok) | "özgün değer yok" |
| `schema_visual` | İçerikte `<script type="application/ld+json">` var + parse edilebilir JSON + hero görsel ref (`<img`/`<picture`) | "JSON-LD/görsel eksik" |

**P0 > gap kuralı (testle kanıtla):** bir gap maddesi kaynaksızsa ve `<!-- gap-skipped -->` ile işaretliyse → `gap` PASS verir (uydurma yerine dürüst atlama ödüllendirilir). P0 her zaman önce değerlendirilir; P0 RED → overall RED.

## TDD adımları

- [ ] **Step 1 — Golden fixture'ları yaz.** `bad_article.html` (thin, tek tablo, AI-imza dolu, özgün yok) + `good_article.html` (derin, rakip+1 yapı, citation'lı, özgün blok, JSON-LD+hero) + `sample_brief.json` (master plan şemasında).
- [ ] **Step 2 — Failing test yaz.** Örnek:

```python
import json
from pathlib import Path
from scripts.production import quality_gates as qg

FIX = Path(__file__).parent / "fixtures" / "cce"

def _brief(): return json.loads((FIX/"sample_brief.json").read_text())

def test_bad_article_fails_overall():
    res = qg.run_all((FIX/"bad_article.html").read_text(), _brief())
    assert res["overall"] == "RED"
    assert any(g["gate"]=="depth" and g["status"]=="RED" for g in res["gates"])

def test_good_article_passes_overall():
    res = qg.run_all((FIX/"good_article.html").read_text(), _brief())
    assert res["overall"] == "PASS"

def test_p0_beats_gap_honest_skip():
    # kaynaksız gap maddesi dürüstçe atlanmış → gap PASS (uydurma değil)
    brief = _brief(); brief["gap"]["must_cover_headings"] = ["Bizde-kaynak-yok-konu"]
    html = '<article><!-- gap-skipped: kaynak yok --><h2>X</h2><p>'+("kelime "*50)+'</p></article>'
    g = next(x for x in qg.run_all(html, brief)["gates"] if x["gate"]=="gap")
    assert g["status"] == "PASS"
```

- [ ] **Step 3 — Run, FAIL gör.** `pytest tests/scripts/test_quality_gates.py -v`
- [ ] **Step 4 — quality_gates.py implement et** (8 kapı + run_all; P0 önce; argparse CLI: `--content path --brief path` → JSON stdout).
- [ ] **Step 5 — Run, PASS gör.**
- [ ] **Step 6 — Commit.** `git add scripts/production/quality_gates.py tests/scripts/test_quality_gates.py tests/scripts/fixtures/cce/ && git commit -m "feat(cce): B2 quality_gates — 8-kapı içerik kalite ölçüm motoru (TDD)"`

## Kabul kriterleri

- [ ] 8 kapı + `run_all` arayüz sözleşmesine BYTE uyumlu (B4 buna güvenecek).
- [ ] Golden test: bad→RED, good→PASS; P0>gap dürüst-atlama testi GREEN.
- [ ] Her kapı için en az 1 ayrı test (8+ test).
- [ ] Saf Python, MCP yok, idempotent, import-side-effect yok, proje slug literal yok.
- [ ] `pytest tests/scripts/test_quality_gates.py -v` temiz.
- [ ] Handoff raporu manager'a. PUSH YOK.
