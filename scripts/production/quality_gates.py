#!/usr/bin/env python3
"""
quality_gates.py — Competitive Content Engine (CCE) Bileşen C: Kapı Motoru.

Üretilen içerik HTML'ini B1'in ürettiği **Brief Paketi**'ne karşı ölçer ve
8 kapının her biri için PASS/RED verir. İçerik ÜRETMEZ — yalnızca DEĞERLENDİRİR.
Çıktı: hangi kapılar geçti/kaldı + Claude'a re-write feedback'i.

Spec: docs/superpowers/specs/2026-06-22-competitive-content-engine-design.md §6.
Brief şeması: docs/superpowers/plans/2026-06-22-competitive-content-engine.md.

Saf transform disiplini (emsal: scripts/planning/new_content_plan_transform.py):
  - import edilince side-effect YOK; dosya yazımı yok (CLI bile yazmaz, stdout'a basar).
  - idempotent: aynı (html, brief) → aynı sonuç.
  - state mutasyonu yok; MCP çağrısı yok.
  - HTML parse stdlib ``html.parser`` ile (proje stdlib-only; bs4 dependency DEĞİL).

8 kapı (P0 hepsinin üstünde; her zaman önce değerlendirilir):

  p0_truthfulness  Her sayısal/quote claim'in yanında kaynak işareti (<a href> /
                   <cite> / parantez) var mı.
  gap              brief.gap.must_cover_* her madde içerikte VAR **veya**
                   <!-- gap-skipped: ... --> ile dürüst atlanmış.
  structure        anlamlı tablo+liste ≥ ceiling.tables+lists +1; >200 kelime
                   H2'de ≥2 H3 (R-30).
  depth            her H2 altında ≥1 paragraf VE ≥40 kelime gövde.
  aeo              intro (ilk <p>) cevap-önce (primary_keyword + iddia);
                   aio.answer_points kapsanmış (aio.present=False → yalnız intro).
  voice            AI-imza blocklist yoğunluğu ≤ 1/1000 kelime; klişe açılış yok.
  originality      rakip entities/questions kümesinde OLMAYAN ≥1 özgün öğe
                   (data-original="true" işaretli blok).
  schema_visual    <script type="application/ld+json"> parse-edilebilir + hero
                   görsel (<img>/<picture>).

P0 > gap kuralı: bir gap maddesi kaynaksızsa ve <!-- gap-skipped --> ile
işaretliyse gap PASS verir (uydurma yerine dürüst atlama ödüllendirilir).

CLI:
  python3 scripts/production/quality_gates.py --content article.html --brief brief.json
  → JSON stdout; exit 0 (overall PASS) / 1 (overall RED) / 2 (kullanım/IO hatası).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

# scripts/ is a namespace package; ensure repo root on sys.path so the absolute
# import of the shared structure thresholds resolves when invoked as a script.
# ScriptDir = scripts/production → repo_root = parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# IMPORT discipline (NOT copy) — meaningful-table/list thresholds are owned by
# scripts.production.structure_metrics (B4 single source of truth), so this gate
# engine (B2) and the arming engine (B1) measure structure on the SAME ruler.
# This pulls B2's former list threshold (≥2) up to the canonical ≥3.
from scripts.production.structure_metrics import (  # noqa: E402
    MIN_LIST_ITEMS,
    MIN_TABLE_COLS,
    MIN_TABLE_ROWS,
)

# --------------------------------------------------------------------------- #
# Contract                                                                     #
# --------------------------------------------------------------------------- #


@dataclass
class GateResult:
    gate: str            # kapı kimliği
    status: str          # "PASS" | "RED" | "AMBER"
    detail: str          # insan-okur kısa açıklama
    missing: list = field(default_factory=list)  # re-write feedback maddeleri


GATE_ORDER = [
    "p0_truthfulness",
    "gap",
    "structure",
    "depth",
    "aeo",
    "voice",
    "originality",
    "schema_visual",
]

# --------------------------------------------------------------------------- #
# Tunables (deterministik eşikler)                                             #
# --------------------------------------------------------------------------- #

MIN_H2_BODY_WORDS = 40        # depth: bir H2 gövdesi en az bu kadar kelime
LONG_H2_WORDS = 200           # structure: bu üstündeki H2 ≥2 H3 ister (R-30)
MIN_H3_FOR_LONG_H2 = 2
COVER_THRESHOLD = 0.6         # gap/aeo: anlamlı token kapsama oranı
MIN_TOKEN_LEN = 3             # kapsama/özgünlük için anlamlı token min uzunluğu
STEM_LEN = 5                  # Türkçe ek toleransı için prefix-stem uzunluğu
ORIGINAL_TOKEN_LEN = 4        # özgünlük: rakipte-olmayan token min uzunluğu
VOICE_MAX_PER_1000 = 1        # AI-imza yoğunluğu tavanı (kelime başına)

# AI-imza blocklist (R-118 ailesi) — yoğunluk ölçülür.
AI_SIGNATURE_PHRASES = ["aslında", "sonuç olarak", "özetle", "bilindiği gibi"]

# Klişe açılışlar — intro bunlardan biriyle BAŞLAMAMALI.
CLICHE_OPENINGS = [
    "günümüzde",
    "bilindiği gibi",
    "bilindiği üzere",
    "son yıllarda",
    "modern dünyada",
    "teknolojinin gelişmesiyle",
    "hepimizin bildiği",
]

# Kapsama eşleşmesinde göz ardı edilen yaygın token'lar.
_STOPWORDS = {
    "nedir", "nasıl", "için", "ile", "olan", "olarak", "daha", "çok",
    "bir", "bu", "şu", "mi", "mı", "mu", "mü", "ve", "veya", "ne", "en",
    "her", "gibi", "kadar",
}

# Blok-düzey metin taşıyıcıları (intro/derinlik/claim için).
_BLOCK_TAGS = {"p", "li", "td", "th", "blockquote", "figcaption"}
# P0 yalnız düz-yazı bloklarını tarar (tablo hücreleri hariç — veri yapısı,
# kaynak bölüm düzeyinde verilir).
_P0_SCAN_TAGS = {"p", "li", "blockquote", "figcaption"}
_VOID_IMG_TAGS = {"img", "picture"}

# --------------------------------------------------------------------------- #
# Claim / citation tespit regexleri                                           #
# --------------------------------------------------------------------------- #

_PERCENT = re.compile(r"%\s*\d|\d\s*%")
_NUM_UNIT = re.compile(
    r"\d[\d.,]*\s*(?:yıl|ay|hafta|gün|saat|dakika|dk|kat|tl|kg|km|metre|cm|mm|"
    r"milyon|bin|adet|hasta|vaka|kişi)\b",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"\d[\d.,]*\s*[₺$€]|[₺$€]\s*\d")
_YEAR = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")
# Gerçek alıntı tespiti (B6 bulgu #3): terim-vurgusunu alıntıdan ayır.
#   • «…» — açık tırnak işareti (TR'de terim-vurgusu için nadir) → her zaman alıntı.
#   • "…" / “…” — yalnız ≥QUOTE_MIN_WORDS kelimelik blok alıntıdır; kısa
#     (≤5 kelime) çift-tırnaklı ifade terim-vurgusudur, kaynak istemez.
_QUOTE_GUILLEMET = re.compile(r"«[^»]+»")
_QUOTE_DOUBLE = re.compile(r'["“]([^"”]+)["”]')
QUOTE_MIN_WORDS = 6
_PAREN = re.compile(r"\([^)]{3,}\)")
_WORD = re.compile(r"\w+", re.UNICODE)
_SENT_SPLIT = re.compile(r"[.!?]")


# --------------------------------------------------------------------------- #
# Normalisation helpers                                                        #
# --------------------------------------------------------------------------- #


def _norm(text: str) -> str:
    """Casefold + Türkçe İ→i casefold artığı olan U+0307 birleşik noktasını sil.

    ``"İ".casefold()`` → ``"i" + U+0307`` döner; U+0307 birleşik işaret \\w
    sınırı yaratıp 'İmplant' kelimesini 'i'+'mplant' diye böler. Eşleştirmenin
    her iki tarafında da bu temizlik uygulanır → tutarlı substring/token.
    """
    return text.casefold().replace("̇", "")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(_norm(text))


def _word_count(text: str) -> int:
    return len(_WORD.findall(_norm(text)))


def _stem(word: str) -> str:
    return word[:STEM_LEN] if len(word) > STEM_LEN else word


def _clip(text: str, limit: int = 80) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _covered(phrase: str, haystack_norm: str) -> bool:
    """Bir ifade haystack'te kapsanıyor mu (Türkçe-ek toleranslı, prefix-stem)."""
    sig = [t for t in _tokens(phrase) if len(t) >= MIN_TOKEN_LEN and t not in _STOPWORDS]
    if not sig:
        return _norm(phrase) in haystack_norm
    present = sum(1 for t in sig if _stem(t) in haystack_norm)
    return (present / len(sig)) >= COVER_THRESHOLD or _norm(phrase) in haystack_norm


def _dedup_norm(items: Iterable[str]) -> list[str]:
    """Case-insensitive, edge-trimmed dedup; first-seen order + casing kept.

    Gap maddeleri üç kategoriye (heading/question/entity) dağılır ve aynı madde
    birden fazla kategoride listelenebilir. Dürüst-atlama sayımı bu ham
    çoğaltmayı değil, BENZERSIZ kapsanmamış maddeyi karşılaştırmalı (B6 bulgu
    #2): tek bir gap-skipped yorumu o maddeyi temizlemeye yetmeli.
    """
    out: list[str] = []
    seen: set[str] = set()
    for it in items:
        key = _norm(it).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# --------------------------------------------------------------------------- #
# HTML → token akışı (stdlib)                                                  #
# --------------------------------------------------------------------------- #


class _Collector(HTMLParser):
    """HTML'i düz bir olay (token) akışına çevirir — ('start'|'startend'|'end'|
    'data'|'comment', ...). Ağaç kurmaz; kapı hesapları akıştan türetilir."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.toks: list[tuple] = []

    def handle_starttag(self, tag, attrs):
        self.toks.append(("start", tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.toks.append(("startend", tag, dict(attrs)))

    def handle_endtag(self, tag):
        self.toks.append(("end", tag))

    def handle_data(self, data):
        self.toks.append(("data", data))

    def handle_comment(self, data):
        self.toks.append(("comment", data))


def _parse(html: str) -> list[tuple]:
    c = _Collector()
    c.feed(html or "")
    c.close()
    return c.toks


def _visible_text(toks: list[tuple]) -> str:
    """Görünür metin — script/style içeriği hariç tüm data token'ları."""
    out: list[str] = []
    skip = 0
    for t in toks:
        if t[0] == "start" and t[1] in ("script", "style"):
            skip += 1
        elif t[0] == "end" and t[1] in ("script", "style") and skip > 0:
            skip -= 1
        elif t[0] == "data" and skip == 0:
            out.append(t[1])
    return " ".join(out)


def _blocks(toks: list[tuple]) -> list[dict]:
    """Blok-düzey öğeleri çıkarır: {tag, text, has_link, has_cite}.

    İç içe inline ``<a href>``/``<cite>`` en yakın bloğun bayrağını set eder.
    Script/style içeriği atlanır.
    """
    blocks: list[dict] = []
    stack: list[dict] = []
    skip = 0
    for t in toks:
        kind = t[0]
        if kind == "start":
            tag = t[1]
            attrs = t[2]
            if tag in ("script", "style"):
                skip += 1
            if tag in _BLOCK_TAGS:
                stack.append({"tag": tag, "buf": [], "has_link": False, "has_cite": False})
            elif tag == "a" and attrs.get("href") and stack:
                stack[-1]["has_link"] = True
            elif tag == "cite" and stack:
                stack[-1]["has_cite"] = True
        elif kind == "end":
            tag = t[1]
            if tag in ("script", "style") and skip > 0:
                skip -= 1
            if tag in _BLOCK_TAGS and stack:
                b = stack.pop()
                blocks.append(
                    {
                        "tag": b["tag"],
                        "text": "".join(b["buf"]),
                        "has_link": b["has_link"],
                        "has_cite": b["has_cite"],
                    }
                )
        elif kind == "data" and skip == 0 and stack:
            stack[-1]["buf"].append(t[1])
    while stack:
        b = stack.pop()
        blocks.append(
            {
                "tag": b["tag"],
                "text": "".join(b["buf"]),
                "has_link": b["has_link"],
                "has_cite": b["has_cite"],
            }
        )
    return blocks


def _intro_text(blocks: list[dict]) -> str:
    for b in blocks:
        if b["tag"] == "p":
            return b["text"]
    return ""


def _h2_sections(toks: list[tuple]) -> list[dict]:
    """Her H2 için {title, body_text, words, h3, p} döner. Section = H2'den bir
    sonraki H2'ye (ya da sona) kadar olan aralık."""
    n = len(toks)
    h2_starts = [i for i, t in enumerate(toks) if t[0] == "start" and t[1] == "h2"]
    sections: list[dict] = []
    for k, si in enumerate(h2_starts):
        title_parts: list[str] = []
        j = si + 1
        while j < n and not (toks[j][0] == "end" and toks[j][1] == "h2"):
            if toks[j][0] == "data":
                title_parts.append(toks[j][1])
            j += 1
        body_start = j + 1
        body_end = h2_starts[k + 1] if k + 1 < len(h2_starts) else n
        seg = toks[body_start:body_end]
        body_text = _visible_text(seg)
        sections.append(
            {
                "title": "".join(title_parts).strip(),
                "body_text": body_text,
                "words": _word_count(body_text),
                "h3": sum(1 for t in seg if t[0] == "start" and t[1] == "h3"),
                "p": sum(1 for t in seg if t[0] == "start" and t[1] == "p"),
            }
        )
    return sections


def _count_meaningful_tables(toks: list[tuple]) -> int:
    """Anlamlı tablo = ≥MIN_TABLE_ROWS satır VE ≥MIN_TABLE_COLS sütun
    (doldurma/tek-satır sayılmaz). Eşik structure_metrics'ten (B1↔B2 hizalı)."""
    count = 0
    stack: list[dict] = []
    for t in toks:
        if t[0] == "start" and t[1] == "table":
            stack.append({"rows": 0, "maxcols": 0, "cur": 0})
        elif t[0] == "start" and t[1] == "tr" and stack:
            stack[-1]["rows"] += 1
            stack[-1]["cur"] = 0
        elif t[0] == "start" and t[1] in ("td", "th") and stack:
            stack[-1]["cur"] += 1
            stack[-1]["maxcols"] = max(stack[-1]["maxcols"], stack[-1]["cur"])
        elif t[0] == "end" and t[1] == "table" and stack:
            tb = stack.pop()
            if tb["rows"] >= MIN_TABLE_ROWS and tb["maxcols"] >= MIN_TABLE_COLS:
                count += 1
    return count


def _count_meaningful_lists(toks: list[tuple]) -> int:
    """Anlamlı liste = ≥MIN_LIST_ITEMS <li> (structure_metrics; B1↔B2 hizalı).

    B4 düzeltmesi: eski ≥2 eşiği B1'in rakip-sayımıyla (≥3) hizalandı; yapı
    kapısı artık iki tarafı aynı cetvelle ölçer (spec §9)."""
    count = 0
    stack: list[int] = []
    for t in toks:
        if t[0] == "start" and t[1] in ("ul", "ol"):
            stack.append(0)
        elif t[0] == "start" and t[1] == "li" and stack:
            stack[-1] += 1
        elif t[0] == "end" and t[1] in ("ul", "ol") and stack:
            if stack.pop() >= MIN_LIST_ITEMS:
                count += 1
    return count


def _data_original_texts(toks: list[tuple]) -> list[str]:
    """data-original="true" işaretli öğelerin metinlerini döner."""
    out: list[str] = []
    cap: dict | None = None
    depth = 0
    for t in toks:
        if t[0] in ("start", "startend"):
            attrs = t[2]
            if cap is None and str(attrs.get("data-original", "")).lower() == "true":
                if t[0] == "startend":
                    out.append("")
                else:
                    cap = {"tag": t[1], "buf": []}
                    depth = 1
                continue
            if cap is not None and t[0] == "start" and t[1] == cap["tag"]:
                depth += 1
        if cap is not None and t[0] == "data":
            cap["buf"].append(t[1])
        if cap is not None and t[0] == "end" and t[1] == cap["tag"]:
            depth -= 1
            if depth == 0:
                out.append("".join(cap["buf"]))
                cap = None
    if cap is not None:
        out.append("".join(cap["buf"]))
    return out


def _ldjson_blocks(toks: list[tuple]) -> list[str]:
    out: list[str] = []
    cap: list[str] | None = None
    for t in toks:
        if t[0] == "start" and t[1] == "script" and \
                str(t[2].get("type", "")).lower() == "application/ld+json":
            cap = []
        elif t[0] == "end" and t[1] == "script" and cap is not None:
            out.append("".join(cap))
            cap = None
        elif t[0] == "data" and cap is not None:
            cap.append(t[1])
    return out


def _has_hero_image(toks: list[tuple]) -> bool:
    return any(t[0] in ("start", "startend") and t[1] in _VOID_IMG_TAGS for t in toks)


def _has_quote_claim(text: str) -> bool:
    """Gerçek alıntı = «…» bloğu VEYA ≥QUOTE_MIN_WORDS kelimelik çift-tırnaklı
    blok. Kısa (≤5 kelime) terim-vurgusu alıntı değildir (B6 bulgu #3)."""
    if _QUOTE_GUILLEMET.search(text):
        return True
    return any(
        len(m.group(1).split()) >= QUOTE_MIN_WORDS
        for m in _QUOTE_DOUBLE.finditer(text)
    )


def _is_claim(text: str) -> bool:
    return bool(
        _PERCENT.search(text)
        or _NUM_UNIT.search(text)
        or _CURRENCY.search(text)
        or _YEAR.search(text)
    ) or _has_quote_claim(text)


def _has_citation(block: dict) -> bool:
    return block["has_link"] or block["has_cite"] or bool(_PAREN.search(block["text"]))


# --------------------------------------------------------------------------- #
# 8 kapı                                                                       #
# --------------------------------------------------------------------------- #


def gate_p0_truthfulness(toks, blocks, brief) -> GateResult:
    violations = [
        _clip(b["text"])
        for b in blocks
        if b["tag"] in _P0_SCAN_TAGS and _is_claim(b["text"]) and not _has_citation(b)
    ]
    if violations:
        return GateResult(
            "p0_truthfulness",
            "RED",
            "kaynaksız claim: " + " | ".join(violations[:5]),
            violations,
        )
    return GateResult(
        "p0_truthfulness", "PASS", "tüm sayısal/quote claim kaynaklı (veya claim yok)", []
    )


def gate_gap(toks, text_norm, brief) -> GateResult:
    gap = brief.get("gap", {}) or {}
    items: list[str] = []
    for cat in ("must_cover_headings", "must_answer_questions", "must_mention_entities"):
        items.extend(gap.get(cat, []) or [])
    # Dedup the uncovered set: an item listed under two categories is ONE gap,
    # so one honest gap-skipped comment clears it (B6 finding #2).
    uncovered = _dedup_norm(it for it in items if not _covered(it, text_norm))
    skip_comments = sum(
        1 for t in toks if t[0] == "comment" and "gap-skipped" in t[1].lower()
    )
    if not uncovered:
        return GateResult("gap", "PASS", "tüm gap maddeleri kapsanmış", [])
    if skip_comments >= len(uncovered):
        return GateResult(
            "gap",
            "PASS",
            f"{len(uncovered)} madde kaynaksız → dürüstçe atlandı (gap-skipped)",
            [],
        )
    return GateResult(
        "gap",
        "RED",
        "kapsanmamış+kaynaklı: " + " | ".join(uncovered),
        uncovered,
    )


def gate_structure(toks, sections, brief) -> GateResult:
    ceiling = brief.get("structure_ceiling", {}) or {}
    required = int(ceiling.get("tables", 0) or 0) + int(ceiling.get("lists", 0) or 0) + 1
    found = _count_meaningful_tables(toks) + _count_meaningful_lists(toks)
    reasons: list[str] = []
    missing: list[str] = []
    if found < required:
        reasons.append(f"anlamlı tablo+liste {found} < gerekli {required}")
        missing.append(f"yapı: en az {required} anlamlı tablo/liste gerekli")
    for s in sections:
        if s["words"] > LONG_H2_WORDS and s["h3"] < MIN_H3_FOR_LONG_H2:
            label = s["title"] or "(başlıksız)"
            reasons.append(
                f"'{label}' {s['words']} kelime ama {s['h3']} H3 "
                f"(≥{MIN_H3_FOR_LONG_H2} gerekli, R-30)"
            )
            missing.append(f"H3 eksik: {label}")
    if reasons:
        return GateResult("structure", "RED", "yapı eksik: " + "; ".join(reasons), missing)
    return GateResult("structure", "PASS", f"{found} anlamlı yapı (≥{required})", [])


def gate_depth(toks, sections, brief) -> GateResult:
    shallow: list[str] = []
    for s in sections:
        if s["p"] < 1 or s["words"] < MIN_H2_BODY_WORDS:
            label = s["title"] or "(başlıksız)"
            shallow.append(f"{label} ({s['words']} kelime, {s['p']} paragraf)")
    if shallow:
        return GateResult("depth", "RED", "sığ bölüm: " + " | ".join(shallow), shallow)
    return GateResult("depth", "PASS", "tüm H2'ler yeterince işlenmiş", [])


def gate_aeo(toks, blocks, text_norm, brief) -> GateResult:
    aio = brief.get("aio", {}) or {}
    primary = brief.get("topic", {}).get("primary_keyword", "") or ""
    intro = _intro_text(blocks)
    first_sentence = _SENT_SPLIT.split(intro)[0] if intro else ""
    fs_norm = _norm(first_sentence)
    pk_norm = _norm(primary)
    kw_ok = True
    if pk_norm:
        kw_tokens = [t for t in _tokens(primary) if len(t) >= MIN_TOKEN_LEN]
        kw_ok = pk_norm in fs_norm or (
            bool(kw_tokens) and all(_stem(t) in fs_norm for t in kw_tokens)
        )
    intro_ok = bool(intro) and kw_ok and _word_count(first_sentence) >= 6

    missing: list[str] = []
    if not intro_ok:
        missing.append("intro cevap-önce değil (ilk cümlede primary_keyword + iddia yok)")
    if aio.get("present"):
        for ap in aio.get("answer_points", []) or []:
            if not _covered(ap, text_norm):
                missing.append(f"AIO noktası eksik: {ap}")
    if missing:
        return GateResult("aeo", "RED", "; ".join(missing), missing)
    return GateResult("aeo", "PASS", "intro cevap-önce + AIO noktaları işlenmiş", [])


def gate_voice(toks, blocks, brief) -> GateResult:
    full = _visible_text(toks)
    full_norm = _norm(full)
    words = max(1, _word_count(full))
    hits = sum(full_norm.count(p) for p in AI_SIGNATURE_PHRASES)
    reasons: list[str] = []
    if hits * 1000 > words * VOICE_MAX_PER_1000:
        reasons.append(f"AI-imza yoğunluğu yüksek ({hits} imza / {words} kelime)")
    intro_norm = _norm(_intro_text(blocks)).strip()
    if any(intro_norm.startswith(c) for c in CLICHE_OPENINGS):
        reasons.append("klişe açılış")
    if reasons:
        return GateResult("voice", "RED", "AI-imza: " + "; ".join(reasons), reasons)
    return GateResult("voice", "PASS", "AI-imza yoğunluğu eşik altında, klişe açılış yok", [])


def gate_originality(toks, brief) -> GateResult:
    comp_tokens: set[str] = set()
    for c in brief.get("competitors", []) or []:
        for item in (c.get("entities", []) or []) + (c.get("questions", []) or []):
            comp_tokens.update(t for t in _tokens(item) if len(t) >= ORIGINAL_TOKEN_LEN)
    for original in _data_original_texts(toks):
        for t in _tokens(original):
            if len(t) >= ORIGINAL_TOKEN_LEN and t not in comp_tokens:
                return GateResult(
                    "originality", "PASS", "rakipte olmayan özgün öğe bulundu", []
                )
    return GateResult(
        "originality",
        "RED",
        "özgün değer yok (rakipte olmayan data-original blok bulunamadı)",
        ["özgün değer yok"],
    )


def gate_schema_visual(toks, brief) -> GateResult:
    ld_blocks = _ldjson_blocks(toks)
    valid_ld = False
    for raw in ld_blocks:
        try:
            json.loads(raw)
            valid_ld = True
            break
        except (ValueError, TypeError):
            continue
    has_img = _has_hero_image(toks)
    reasons: list[str] = []
    if not ld_blocks:
        reasons.append("JSON-LD eksik")
    elif not valid_ld:
        reasons.append("JSON-LD parse edilemiyor")
    if not has_img:
        reasons.append("hero görsel eksik")
    if reasons:
        return GateResult("schema_visual", "RED", "JSON-LD/görsel eksik: " + "; ".join(reasons), reasons)
    return GateResult("schema_visual", "PASS", "JSON-LD geçerli + hero görsel var", [])


# --------------------------------------------------------------------------- #
# Orkestrasyon                                                                 #
# --------------------------------------------------------------------------- #


def run_all(content_html: str, brief: dict) -> dict:
    """Tüm kapıları çalıştırır.

    Döner: {"gates": [GateResult-as-dict ...], "overall": "PASS"|"RED",
            "rewrite_feedback": [str ...]}.

    overall == PASS ancak hiçbir kapı RED değilse. P0 her zaman önce
    değerlendirilir ve RED ise overall kesin RED (gap'in üstünde).
    """
    brief = brief or {}
    toks = _parse(content_html or "")
    blocks = _blocks(toks)
    sections = _h2_sections(toks)
    text_norm = _norm(_visible_text(toks))

    gates = [
        gate_p0_truthfulness(toks, blocks, brief),
        gate_gap(toks, text_norm, brief),
        gate_structure(toks, sections, brief),
        gate_depth(toks, sections, brief),
        gate_aeo(toks, blocks, text_norm, brief),
        gate_voice(toks, blocks, brief),
        gate_originality(toks, brief),
        gate_schema_visual(toks, brief),
    ]
    # Sözleşme sırasını garanti et.
    gates.sort(key=lambda g: GATE_ORDER.index(g.gate))

    overall = "RED" if any(g.status == "RED" for g in gates) else "PASS"
    rewrite_feedback = [f"[{g.gate}] {g.detail}" for g in gates if g.status == "RED"]
    return {
        "gates": [asdict(g) for g in gates],
        "overall": overall,
        "rewrite_feedback": rewrite_feedback,
    }


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #


def _parse_args(argv: Iterable[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="quality_gates.py",
        description="CCE Kapı Motoru — içerik HTML'ini Brief Paketi'ne karşı ölçer.",
    )
    p.add_argument("--content", required=True, help="içerik HTML dosyası")
    p.add_argument("--brief", required=True, help="Brief Paketi JSON dosyası (B1 çıktısı)")
    return p.parse_args(list(argv))


def main(argv: list[str]) -> int:
    try:
        args = _parse_args(argv)
        html = Path(args.content).read_text(encoding="utf-8")
        brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        print(json.dumps({"error": f"dosya yok: {exc.filename}"}, ensure_ascii=False))
        return 2
    except (ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2

    result = run_all(html, brief)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
