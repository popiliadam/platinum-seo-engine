# WORKER PROMPT — B4: Orkestratör + SKILL.md + Eşik Hizalama (CCE)

> **Sen ayrı bir worker session'sın (Opus 4.8, fast, max effort).** Sıfır context varsay. Bu batch B1+B2+B3'ün ÜSTÜNE biner — onlar commit'li (`29672da`/`8387afa`/`a240877`=B1, `ef055ee`=B2, `c413068`=B3). Onların **fonksiyon imzalarını DEĞİŞTİRME** (tek istisna: aşağıdaki eşik-hizalama refactoru). Bitince handoff raporu döndür — **PUSH ETME.**
>
> Önce oku: tam tasarım `docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md` (§3 mimari, §6 kapılar, §8 döngü, §9 yapı matematiği); master plan `docs/superpowers/plans/2026-06-22-competitive-content-engine.md` (Brief Paketi şeması + global constraints).

## Kritik mimari kural (yanlış anlama = baştan yanlış)

**Orkestratör hem kod hem Claude'dur; yazım adımı Claude'dadır.** `new_blog.py` **saf Python** — Claude'u/MCP'yi ÇAĞIRAMAZ. Bu yüzden `new_blog.py` döngüyü "sürmez"; döngüye **iki saf yardımcı** verir: (1) ham MCP JSON'larından Brief Paketi montajı, (2) üretilen HTML'i kapılardan geçirme + döngü kararı. Döngünün kendisini (MCP çağrıları → Claude yazımı → kapı → re-write) **new-blog SKILL.md içinde Claude sürer.** Bu ayrımı bozma — `new_blog.py`'ye MCP/Claude çağrısı koymak mimariyi kırar.

**HTML parse:** stdlib `html.parser` (⚠️ bs4 KURULU DEĞİL — B1/B2 bunu doğruladı; emsal `scripts/validation/content_validator.py`). bs4 import etme.

## Görev 1 — Eşik hizalama (cross-batch bug fix)

B1 `_MIN_LIST_ITEMS = 3` ile rakip listelerini sayıyor; B2 `_count_meaningful_lists` ise `≥2 <li>` ile bizim listeleri sayıyor → **asimetrik** (B2 bizi haksız kayırır, "rakipten iyi" garantisini bozar). Tablo eşiği zaten tutarlı (≥2×2). Çöz:

- Create: `scripts/production/structure_metrics.py` — ortak eşik sabitleri (**tek doğruluk kaynağı**):
  ```python
  MIN_TABLE_ROWS = 2
  MIN_TABLE_COLS = 2
  MIN_LIST_ITEMS = 3   # B1 ile hizalı; B2'nin eski 2'si BUNA çekilir
  ```
- Modify: `competitor_recon_transform.py` — kendi `_MIN_*` sabitlerini `from scripts.production.structure_metrics import MIN_TABLE_ROWS, MIN_TABLE_COLS, MIN_LIST_ITEMS` ile değiştir (davranış aynı, kaynak tek).
- Modify: `quality_gates.py` — `_count_meaningful_lists` eşiğini `>= 2` → `>= MIN_LIST_ITEMS` (import). `_count_meaningful_tables` da aynı sabitleri import etsin.
- Modify (zorunlu): B2'nin `tests/scripts/fixtures/cce/good_article.html` — eğer 2-li liste içeriyorsa ≥3-li yap (yoksa structure kapısı testi kırılır). B1/B2 testlerini eşik değişimine göre güncelle ve **hepsinin yeşil kaldığını** doğrula.

## Görev 2 — Orkestratör yardımcıları (`new_blog.py`, saf Python)

- Create: `scripts/production/new_blog.py`
- Test: `tests/scripts/test_new_blog.py`

**Arayüz sözleşmesi (B5 buna bağlı — AYNEN bunlar):**
```python
def assemble_brief(*, serp_json: dict, scraped_pages: list[dict], raw_overview: dict,
                   raw_suggestions: dict, raw_serp: dict, our_existing: dict | None,
                   topic: dict, gsc: dict | None = None, generated_at: str | None = None) -> dict:
    """B1'in 3 transform'unu sırayla çağırır → tam Brief Paketi.
    1) competitor_recon_transform.transform(serp_json, scraped_pages, market=topic['market'])
    2) keyword_aio_intel_transform.transform(raw_overview, raw_suggestions, raw_serp, market=topic['market'])
    3) build_brief.build(competitors, keyword_aio, our_existing, topic=topic, generated_at=generated_at)
    gsc (skill'in MCP'den aldığı {real_queries, current_position}) varsa brief['gsc']'ye yazılır
    (build_brief default {real_queries:[],current_position:null} üretir; assemble_brief gsc ile override eder).
    Saf: MCP çağırmaz; ham JSON'lar parametre olarak gelir (SKILL.md/Claude doldurur)."""

def evaluate(content_html: str, brief: dict, *, round_num: int = 1, max_rounds: int = 3) -> dict:
    """quality_gates.run_all(content_html, brief)'i IMPORT ile çağırır (subprocess DEĞİL).
    Döner: {"gate_result": <run_all çıktısı>, "action": "PASS"|"REWRITE"|"AMBER_TERMINAL", "feedback": [str]}.
    Kural: overall=='PASS' → action 'PASS'. overall=='RED' & round_num < max_rounds → 'REWRITE'
    (feedback = run_all['rewrite_feedback']). overall=='RED' & round_num >= max_rounds → 'AMBER_TERMINAL'
    (3-tur cap, spec §8 — sonsuz döngü yok; operatöre eksik raporu)."""
```

**Açık soru kararları (B1/B2 handoff'larından — net):** `gsc` → assemble_brief parametresi (yukarıda). `generated_at` → kabul, assemble_brief'ten build'e geçer. `run_all` → `import`le çağrılır (exit-code/subprocess değil). `AMBER` → yalnız orkestratörde (3-tur cap → AMBER_TERMINAL); kapılar PASS/RED kalır.

## Görev 3 — new-blog SKILL.md güncelle

- Modify: `skills/production/new-blog/SKILL.md`
- CCE döngüsünü mevcut 12-step'e işle: **silahlan** (MCP: DFS serp depth=10 + Scrapling×10 ZORUNLU + DFS keyword/AIO + GSC → ham JSON → `assemble_brief`) → **yaz** (Claude, craft rehberi R-149+ uygula) → **kapı** (`evaluate`) → **re-write** (action=REWRITE ise feedback ile tekrar yaz; PASS'e veya AMBER_TERMINAL'e kadar).
- `consumes`'a ekle: `rules/content-craft-discipline.md`, `scripts/production/new_blog.py`, `scripts/production/quality_gates.py`.
- Scrapling Step 4'ü "optional/top-3" → **"zorunlu/top-10"** güncelle. AIO Step 5'i gerçek `answer_points` analizine bağla.
- `status: wip` KALSIN (B5 kanıt geçene kadar; active'i manager flip eder).
- Plugin-agnostik: proje slug literal YASAK, `pse-` prefix.

## TDD adımları (Görev 1 ve 2 için; Görev 3 doküman)

- [ ] **structure_metrics:** önce test (sabitler doğru + B1/B2 import ediyor), sonra util, sonra B1/B2 refactor + fixtures güncelle, full `tests/scripts/` yeşil.
- [ ] **new_blog.py:** failing test → implement → pass. Örnek testler:
```python
from scripts.production import new_blog

def test_assemble_brief_overrides_gsc():
    brief = new_blog.assemble_brief(
        serp_json={"tasks":[{"result":[{"items":[]}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword":"x","content_type":"guide","locale":"tr-TR","market":"TR"},
        gsc={"real_queries":["q1"],"current_position":12}, generated_at="2026-06-22T00:00:00Z")
    assert brief["gsc"]["real_queries"] == ["q1"]
    assert brief["schema_version"] == "1.0"

def test_evaluate_red_under_cap_is_rewrite():
    brief = new_blog.assemble_brief(serp_json={"tasks":[{"result":[{"items":[]}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword":"x","content_type":"guide","locale":"tr-TR","market":"TR"})
    out = new_blog.evaluate("<article><p>kısa</p></article>", brief, round_num=1, max_rounds=3)
    assert out["action"] in ("REWRITE","PASS")
    assert "gate_result" in out

def test_evaluate_red_at_cap_is_amber_terminal():
    brief = new_blog.assemble_brief(serp_json={"tasks":[{"result":[{"items":[]}]}]}, scraped_pages=[],
        raw_overview={}, raw_suggestions={}, raw_serp={}, our_existing=None,
        topic={"primary_keyword":"x","content_type":"guide","locale":"tr-TR","market":"TR"})
    out = new_blog.evaluate("<article><p>kısa</p></article>", brief, round_num=3, max_rounds=3)
    # boş içerik kesin RED → cap'te AMBER_TERMINAL
    assert out["action"] == "AMBER_TERMINAL"
```
- [ ] Commit'ler (scoped, **explicit pathspec** ile — paylaşımlı worktree race'e karşı): structure_metrics+refactor ayrı commit, new_blog.py ayrı, SKILL.md ayrı.

## Kabul kriterleri

- [ ] `structure_metrics.py` tek kaynak; B1+B2 import ediyor; liste eşiği her ikisinde **≥3** (hizalı); tablo ≥2×2.
- [ ] `new_blog.py` saf Python (MCP/Claude çağrısı YOK); `assemble_brief` + `evaluate` sözleşmeye BYTE uyumlu; `run_all` import'la çağrılıyor.
- [ ] `evaluate` 3-tur cap → AMBER_TERMINAL (sonsuz döngü yok).
- [ ] SKILL.md CCE döngüsü + craft R-149+ + kapı referansı; Scrapling zorunlu/top-10; status wip.
- [ ] `pytest tests/scripts/ -q` **tamamen yeşil** (B1/B2/B4 + eşik refactor sonrası); proje slug literal yok; bs4 import yok.
- [ ] Handoff raporu manager'a (git diff --stat + pytest + dosya listesi + açık sorular + **B5 için finalize imzalar**). PUSH YOK.
