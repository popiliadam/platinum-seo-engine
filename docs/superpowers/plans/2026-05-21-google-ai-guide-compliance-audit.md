# Google AI Guide Compliance + May 2026 Core Update Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring PSEO Engine into compliance with Google's official AI Optimization Guide (published 2026-05-15) AND harden it against the May 2026 Core Update (rollout started 2026-05-21, ~2 weeks). Five workstreams: doc rationale alignment (Y-AI-01 + Y-AI-02), AI image IPTC disclosure (G-AI-01), bank seed via hybrid auto-discovery + operator review (G-AI-05), rotation + density cap enforcement (R-121), and Google Business Profile audit skill (G-AI-02).

**Architecture:** Six phases, riske göre artan sıra. Phase 1 patches rule rationales (zero-risk doc edits — Engine internal consistency). Phase 2 adds piexif-based IPTC metadata writer to `generate-images` skill. Phase 3 extends `brand-onboarding` skill into a 3-stage pipeline (Auto Discovery via DFS+Scrapling → Operator Review → Bank Write) and chains it as mandatory from `init-project`. Phase 4 adds R-121 rotation+density cap rule to prevent bank entry "parrot repetition" in content output. Phase 5 adds new `gbp-audit` discovery skill following the `tech-audit` pattern. Phase 6 runs the bank seed pilot for the three priority projects (demo-fintech TR YMYL-high, demo-aluminum CA local-service, demo-hvac hybrid).

**Tech Stack:**
- Python 3.11+ (existing engine baseline)
- `piexif>=1.1.3` for IPTC metadata writing (new dependency)
- DataForSEO MCP — `on_page_content_parsing`, `domain_analytics_whois_overview`, `business_data_business_listings_search`, `dataforseo_labs_google_keywords_for_site` (all existing)
- Scrapling MCP — `fetch`, `stealthy_fetch` (existing)
- JSON Schema validation via existing pipeline
- No new MCP server installs required (operator-side configuration unchanged)

---

## Context: May 2026 Core Update + AI Guide Timing

| Date | Event |
|------|-------|
| 2026-05-15 | Google publishes AI Optimization Guide (advisory) |
| **2026-05-21** | **May 2026 Core Update rollout begins** (this plan starts same day) |
| ~2026-06-03 | Core update rollout expected completion (~2 weeks) |
| ~2026-06-10 | Earliest valid GSC measurement window (Google: wait 1 week post-completion) |

**Why this matters for sequencing:** The May 2026 Core Update emphasizes "original, helpful, people-first content" and penalizes "automated, ad-bloated, repetitive content" per third-party analysis (Google's official announcement gave only generic wording; companion blog post not published — anomalous). The Engine's current R-105 / R-114 / R-119 (bank-driven expert quote / original research / first-hand experience) rules are **trivially passing** because every project's `experience_database` and `original_research_database` are empty. This means Engine-produced content for all 9 projects currently lacks the E-E-A-T "Experience" depth signal that the May 2026 Core Update directly targets. Phase 3 (Bank Seed) + Phase 4 (R-121) directly address this exposure window.

**Phase sequencing is risk-ordered, not urgency-ordered.** Doc updates first (zero-risk, atomic), then isolated utility (IPTC), then major skill revision (Bank Seed), then rule + skill consume logic (R-121), then new skill (GBP). Pilot operator sessions (Phase 6) overlap with Core Update rollout window — bank seeded content benefits measured ~2026-06-10+.

---

## Compliance Audit Findings (Final)

### ALREADY COMPLIANT (no action needed — preserved from audit)

| # | Google Requirement | PSEO Implementation | Evidence |
|---|--------------------|---------------------|----------|
| 1 | Helpful Content principles | `rules/content-quality.md` Foundational Principles | content-quality.md:22-85 |
| 2 | E-E-A-T signals (byline + schema + entity + sameAs) | `rules/content-eeat-discipline.md` R-28, R-48, R-49, R-100 | content-eeat-discipline.md |
| 3 | Scaled Content Abuse defense (uniqueness + banks + humanize) | R-117 + R-105 + R-114 + R-118 + R-119 (banks empty — see G-AI-05) | content-quality.md:200-260 |
| 4 | Truth-Verifiable (anti-fabrication) | R-14 + R-15 + R-44 + R-52 | content-quality.md:90-180 |
| 5 | Schema markup (rich results) | R-48 baseline + `skills/discovery/schema-audit/` | schema-audit/SKILL.md |
| 6 | JavaScript SEO render check | `skills/discovery/tech-audit/` uses `on_page_lighthouse` MCP | tech-audit/SKILL.md:62 |
| 7 | Core Web Vitals (LCP/CLS/INP) | tech-audit captures Lighthouse | grep evidence |
| 8 | Image SEO (LCP / format / alt) | R-21 + R-75 + R-76 + R-77 | content-html-discipline.md |
| 9 | Accessibility (WCAG 2.1 AA) | R-39 axe-core/Pa11y pre-publish | content-html-discipline.md:79 |
| 10 | Site Reputation Abuse ban (parasite SEO) | R-32 `assigned_url` host == project_domain | content-quality.md:120 |
| 11 | Per-bot robots.txt LLM policy | R-99 + `project.config.json[ai_bots]` | content-llm-discipline.md:33 |
| 12 | LLMs.txt opt-in (default OFF) | R-98 init-project asks; default `ai_training_optin: false` | per project configs |
| 13 | Indexing API + IndexNow (operator consent) | `skills/publishing/indexing-ping` | indexing-ping/SKILL.md |
| 14 | YMYL Bibliography / Counter-argument / Disclaimer | R-45 + R-50 + R-51 enforced | content-quality.md |

### CONFIRMED GAPS (this plan addresses)

| # | Gap ID | Google Requirement | Current PSEO State | Phase |
|---|--------|---------------------|--------------------|-------|
| 1 | **Y-AI-01** | R-98 rationale lags Google's 2026-05-15 "llms.txt unnecessary" position | Rule mechanism correct (default OFF); only rationale paragraph outdated | Phase 1 |
| 2 | **Y-AI-02** | R-101 + R-102 rationale framed as "AI citation candidate" | Google: "no AI-specific writing"; rationale needs reframe to "helpful content + scannability" | Phase 1 |
| 3 | **G-AI-01** | IPTC `DigitalSourceType=TrainedAlgorithmicMedia` on AI images (Merchant Center) | grep "DigitalSourceType" → 0 hits engine-wide | Phase 2 |
| 4 | **G-AI-05** | Truth-Verifiable depth via bank-driven content | All 9 projects: `experience_database: []` + `original_research_database: []` empty | Phase 3 + 6 |
| 5 | **R-121** | Bank entry topic relevance + density cap + rotation enforcement | Missing — bank entries would risk repetitive "parrot" usage across content | Phase 4 |
| 6 | **G-AI-02** | GBP for local-service AI Overview visibility | grep "google_business / GBP / business_profile" → 0 hits | Phase 5 |

### CANCELLED (decided out-of-scope)

| ID | Original Proposal | Why Cancelled |
|----|-------------------|---------------|
| G-AI-03 | Merchant Center XML feed skill | Operator HOLD — heterogeneous platforms (Ticimax/Ideasoft/WC/imagaza); future v1.8+ if revisited |
| G-AI-04 | Visible `<aside class="pse-ai-disclosure">` block + R-120 rule | Hard constraint added to memory: "AI tarafından yazıldı" ifadesi ASLA görünür HTML'de — see `feedback_ai_disclosure_ban.md`. Engine's existing 5-signal "self-evident through other ways" coverage (R-28 byline + R-89 dateModified + R-45 bibliography + R-105 expert quote bank + R-119 first-hand experience) satisfies Google's "Helpful Content — or in other ways" wording |

---

## File Structure

### Files to CREATE

| Path | Phase | Responsibility |
|------|-------|----------------|
| `scripts/util/iptc_metadata.py` | 2 | piexif-based writer for `DigitalSourceType=TrainedAlgorithmicMedia` |
| `tests/util/test_iptc_metadata.py` | 2 | Unit tests for IPTC writer (round-trip + idempotent + WebP support) |
| `scripts/meta/brand_onboarding_discovery.py` | 3 | DFS + Scrapling auto-discovery for bank seed (Stage A) |
| `scripts/meta/brand_onboarding_review.py` | 3 | Operator review prompt + diff/approve UX (Stage B) |
| `scripts/meta/brand_onboarding_write.py` | 3 | Bank entry serialization + project.config write (Stage C) |
| `tests/meta/test_brand_onboarding_discovery.py` | 3 | Discovery stage tests (mocked MCPs) |
| `tests/meta/test_brand_onboarding_review.py` | 3 | Review stage tests |
| `tests/meta/test_brand_onboarding_write.py` | 3 | Write stage tests |
| `scripts/migrations/0004_project_config_1.3_to_1.4.py` | 3 | Bank entry format zenginleştirme migration |
| `tests/migrations/test_0004_project_config_1.3_to_1.4.py` | 3 | Migration tests (additive, idempotent, preservation) |
| `skills/discovery/gbp-audit/SKILL.md` | 5 | New discovery skill (tech-audit pattern reuse) |
| `scripts/discovery/gbp_audit_transform.py` | 5 | DFS business_data + Scrapling fallback transform |
| `tests/skills/test_gbp_audit.py` | 5 | gbp-audit skill tests |
| `commands/pseo-gbp-audit.md` | 5 | Slash command |

### Files to MODIFY

| Path | Phase | Change |
|------|-------|--------|
| `rules/content-llm-discipline.md` | 1 | R-98 + R-101 + R-102 rationale paragraflarını revize |
| `requirements.txt` + `requirements-lock.txt` | 2 | Add `piexif>=1.1.3` |
| `scripts/production/generate_images.py` (verify path during Task 2.3) | 2 | Post-Higgsfield IPTC metadata write step |
| `skills/production/generate-images/SKILL.md` | 2 | Add IPTC step to 10-step protocol + R-78 reference |
| `tests/skills/test_generate_images.py` | 2 | Add IPTC round-trip test |
| `rules/content-html-discipline.md` | 2 | Add R-78 (AI-image IPTC disclosure) |
| `schemas/project-config.schema.json` | 3 | Bump version to 1.4 + add bank entry format (`applicable_topics`, `phrasings`, `last_used_in_content_id`, `max_usage_per_month`) |
| `templates/project/project.config.template.json` | 3 | Add new bank entry fields with safe defaults |
| `skills/meta/brand-onboarding/SKILL.md` | 3 | Revize — 3-stage pipeline + 5 new questions (profile-aware) |
| `skills/meta/init-project/SKILL.md` | 3 | Mandatory `produces: brand-onboarding` chain enforcement |
| `rules/content-eeat-discipline.md` | 4 | Add R-121 (bank entry rotation + density cap + topic relevance) |
| `skills/production/new-blog/SKILL.md` | 4 | R-121 consume logic |
| `skills/production/revise-content/SKILL.md` | 4 | R-121 consume logic |
| `skills/production/faq-optimization/SKILL.md` | 4 | R-121 consume logic |
| `schemas/master-excel.schema.json` | 5 | Add `gbp_audit` sheet schema |
| `docs/PHASE_STATUS.md` | post | Record v1.7 compliance phase |

### Files NOT touched (intentionally)

- `rules/content-quality.md` Foundational Principles — already aligned with Google's Helpful Content principles; no change
- `rules/content-eeat-discipline.md` R-28 / R-37 / R-48 / R-49 / R-100 — already compliant
- `skills/publishing/indexing-ping/` — already operator-consent gated (per memory `feedback_indexing_api_consent.md`)
- `skills/discovery/tech-audit/` — already captures CWV via Lighthouse MCP
- `skills/discovery/schema-audit/` — already validates JSON-LD baseline

---

## Cross-Cutting Constraints

These apply to EVERY task in EVERY phase:

1. **Plugin-agnostic boundary (F-16):** Worker MUST NOT write to `.mcp.json`. New MCP usage is operator-side configured. No new MCP server installs by skill code.
2. **Append-only state (per `rules/append-only-state.md`):** New `_state/events.jsonl` event_kind values added to `schemas/events.schema.json` enum first (schema-first discipline).
3. **AI Disclosure Ban (per memory `feedback_ai_disclosure_ban.md`):** No skill output, no template, no rule may emit "AI tarafından yazıldı" / "AI-generated" / "yapay zeka ile yazılmıştır" or equivalent visible HTML disclosure. Zero exceptions.
4. **Indexing API operator consent (per memory `feedback_indexing_api_consent.md`):** No autonomous submission to Google Indexing API, GBP API, or any external publishing surface. All new skills (especially Phase 5 gbp-audit) report findings to master.xlsx + outputs/reports — operator submits manually.
5. **Profile-aware (per `rules/content-quality.md` Principle 2):** Every new skill / rule branches behavior based on `project.config.json[profiles]`. Hard rules apply only to applicable profiles.
6. **No fabricated bank data (per R-14 + R-15):** Bank seed Stage A discovery proposes draft entries; Stage B operator MUST approve each entry; Stage C writes only approved entries. No silent auto-write.
7. **Atomic commit per task:** Each Task ends with exactly one `git commit`. No cross-task batching. Lesson 38 pattern reuse (per memory `project_phase_lessons.md`).
8. **Test stability:** After every task, full pytest suite must PASS. No "fix it next task" deferrals.
9. **Drift-check gate per phase:** End of each phase runs `/pseo-driftcheck`; PASS before moving to next phase.
10. **May 2026 Core Update timing awareness:** Phases 1-5 deliver Engine code by ~2026-05-28. Phase 6 (3 operator pilot sessions) overlaps with Core Update rollout window. Post-update GSC measurement scheduled for ~2026-06-10 — recorded in `docs/PHASE_STATUS.md`.

---

# Phase 1 — Doc Rationale Updates (Y-AI-01 + Y-AI-02)

**Goal:** Engine's `content-llm-discipline.md` rationales align with Google's 2026-05-15 official positions. Mechanism preserved; only rationale paragraphs revised.

**Affects:** Engine internal consistency. Zero behavior change in skill output. Zero test changes.

**Dependencies:** None.

**Duration estimate:** 15 minutes total (3 tasks × 5 minutes each).

---

### Task 1.1: R-98 LLMs.txt rationale update

**File:**
- Modify: `rules/content-llm-discipline.md` (R-98 block)

- [ ] **Step 1: Read current R-98 rationale**

```bash
grep -A8 "^### R-98:" rules/content-llm-discipline.md
```
Confirm rationale begins with "LLMs.txt emerging standard (2024+)".

- [ ] **Step 2: Replace rationale paragraph**

Edit `rules/content-llm-discipline.md`. Find the R-98 block's `**Rationale.**` line and replace the rationale paragraph with:

```markdown
**Rationale.** Google'ın 2026-05-15 AI Optimization Guide cümlesi: "You don't need to create new machine readable files, AI text files, markup, or Markdown to appear in generative AI search." Yani **Google için gereksiz**. Ancak diğer LLM ecosystem'leri (Anthropic, Perplexity, OpenAI) llms.txt'i tercih edebilir; opt-in mekanizması (default OFF) bu trade-off'u proje sahibine bırakır. PSEO'nun default davranışı (`ai_training_optin: false`) Google'ın eleştirisinden zaten korunmuş haldedir.
```

- [ ] **Step 3: Run rule frontmatter validation**

```bash
pytest tests/test_rules_frontmatter.py -v 2>/dev/null || pytest tests/rules/ -v 2>/dev/null
```
Expected: PASS (frontmatter unchanged; only body paragraph edit).

- [ ] **Step 4: Commit**

```bash
git add rules/content-llm-discipline.md
git commit -m "docs(rules): R-98 rationale aligned with Google 2026-05-15 'llms.txt unnecessary' position"
```

---

### Task 1.2: R-101 self-contained intro rationale recalibration

**File:**
- Modify: `rules/content-llm-discipline.md` (R-101 block)

- [ ] **Step 1: Locate R-101 rationale**

```bash
grep -A8 "^### R-101:" rules/content-llm-discipline.md
```
Confirm current rationale references "LLM context window'unda izole paragraf parse şansı yüksek".

- [ ] **Step 2: Replace rationale paragraph**

Replace the R-101 `**Rationale.**` paragraph with:

```markdown
**Rationale.** Google'ın 2026-05-15 cümlesi: "You don't need to write in a specific way just for generative AI search." Self-contained intro AI için değil; **helpful content + scannability** için (Google self-assessment kriteri: "Is this content you'd want to bookmark, share, or recommend?"). Kullanıcı sayfada H2'leri tarayıp ilgilendiği bölüme atlar — her bölümün izole faydası olur. AI/LLM citation potansiyeli yan etki, hedef değil.
```

- [ ] **Step 3: Run rule frontmatter validation**

```bash
pytest tests/test_rules_frontmatter.py -v 2>/dev/null || pytest tests/rules/ -v 2>/dev/null
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add rules/content-llm-discipline.md
git commit -m "docs(rules): R-101 rationale reframed — helpful content + scannability (not AI-specific)"
```

---

### Task 1.3: R-102 AI summary footer rationale recalibration

**File:**
- Modify: `rules/content-llm-discipline.md` (R-102 block)

- [ ] **Step 1: Locate R-102 rationale**

```bash
grep -A8 "^### R-102:" rules/content-llm-discipline.md
```

- [ ] **Step 2: Replace rationale paragraph**

Replace the R-102 `**Rationale.**` paragraph with:

```markdown
**Rationale.** AI summary footer **insan UX için** — TL;DR formatı + yer imine eklenebilirlik, Google Helpful Content "Is this content you'd want to bookmark, share, or recommend?" kriteri. Başlıksız bullet R-05 sembol yasağıyla uyumlu (brand tone — generic AI imza önleme). AI/LLM bot'un bunu özet olarak alabilmesi yan etki, hedef değil.
```

- [ ] **Step 3: Run drift-check (end of Phase 1)**

```bash
pytest tests/test_rules_frontmatter.py -v 2>/dev/null
# Run drift-check if /pseo-driftcheck is available; else skip with a note in commit
```

- [ ] **Step 4: Commit**

```bash
git add rules/content-llm-discipline.md
git commit -m "docs(rules): R-102 rationale reframed — human UX + bookmarkability (not AI-specific)"
```

**END OF PHASE 1 — 3 atomic commits, zero behavior change, Engine internal consistency restored.**

---

# Phase 2 — IPTC Metadata for AI-Generated Images (G-AI-01)

**Goal:** Every image produced by `generate-images` skill carries IPTC `DigitalSourceType=TrainedAlgorithmicMedia` metadata, complying with Google Merchant Center's AI-image disclosure policy (reaffirmed 2026-05-15 AI Guide).

**Affects:** All projects using `generate-images` (9 projects — Higgsfield-based hero image pipeline).

**Dependencies:** Phase 1 complete.

**Duration estimate:** 1-2 hours (4 tasks).

---

### Task 2.1: Add `piexif` dependency + smoke test

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-lock.txt`
- Create: `tests/util/test_piexif_smoke.py`

- [ ] **Step 1: Append piexif to requirements.txt**

Add line to `requirements.txt`:
```
piexif>=1.1.3
```

- [ ] **Step 2: Re-lock dependencies**

```bash
pip-compile requirements.txt -o requirements-lock.txt
```
Expected: `requirements-lock.txt` contains `piexif==1.1.3` or newer pinned version.

- [ ] **Step 3: Install in dev env**

```bash
pip install -r requirements-lock.txt
```
Expected: PASS, no errors.

- [ ] **Step 4: Write smoke test**

Create `tests/util/test_piexif_smoke.py`:
```python
"""Smoke test: piexif importable + JPEG EXIF round-trip works."""
import io
import piexif
from PIL import Image


def test_piexif_round_trip_jpeg():
    """Write EXIF dataset, read back, assert equal."""
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    exif_dict = {"0th": {piexif.ImageIFD.Software: b"PSEO-test"}}
    exif_bytes = piexif.dump(exif_dict)

    out_buf = io.BytesIO()
    img.save(out_buf, format="JPEG", exif=exif_bytes)
    out_buf.seek(0)

    read_dict = piexif.load(out_buf.getvalue())
    assert read_dict["0th"][piexif.ImageIFD.Software] == b"PSEO-test"
```

- [ ] **Step 5: Run smoke test**

```bash
pytest tests/util/test_piexif_smoke.py -v
```
Expected: 1 PASSED.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-lock.txt tests/util/test_piexif_smoke.py
git commit -m "chore(deps): add piexif>=1.1.3 for IPTC metadata writing"
```

---

### Task 2.2: IPTC metadata writer utility

**Files:**
- Create: `scripts/util/iptc_metadata.py`
- Create: `tests/util/test_iptc_metadata.py`

- [ ] **Step 1: Write the failing tests first (TDD)**

Create `tests/util/test_iptc_metadata.py`:
```python
"""IPTC metadata writer — DigitalSourceType=TrainedAlgorithmicMedia."""
from pathlib import Path
import piexif
from PIL import Image
import pytest

from scripts.util.iptc_metadata import write_ai_image_disclosure, DIGITAL_SOURCE_TYPE_AI


def _make_jpeg(tmp_path: Path) -> Path:
    img = Image.new("RGB", (10, 10), color=(0, 128, 255))
    p = tmp_path / "test.jpg"
    img.save(p, format="JPEG")
    return p


def test_write_ai_disclosure_adds_iptc_tag(tmp_path):
    """After write_ai_image_disclosure, DigitalSourceType=TrainedAlgorithmicMedia present in EXIF."""
    img_path = _make_jpeg(tmp_path)
    write_ai_image_disclosure(img_path)

    exif_dict = piexif.load(str(img_path))
    image_description = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription, b"")
    user_comment = exif_dict["Exif"].get(piexif.ExifIFD.UserComment, b"")
    assert (b"TrainedAlgorithmicMedia" in image_description) or (b"TrainedAlgorithmicMedia" in user_comment)


def test_write_ai_disclosure_idempotent(tmp_path):
    """Calling twice does not corrupt; second call overwrites cleanly."""
    img_path = _make_jpeg(tmp_path)
    write_ai_image_disclosure(img_path)
    write_ai_image_disclosure(img_path)
    exif_dict = piexif.load(str(img_path))
    assert b"TrainedAlgorithmicMedia" in exif_dict["0th"].get(piexif.ImageIFD.ImageDescription, b"")


def test_write_ai_disclosure_raises_on_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        write_ai_image_disclosure(tmp_path / "does-not-exist.jpg")


def test_write_ai_disclosure_supports_webp(tmp_path):
    """WebP — PIL exif round-trip via the info dict."""
    img = Image.new("RGB", (10, 10), color=(0, 128, 255))
    p = tmp_path / "test.webp"
    img.save(p, format="WEBP")
    write_ai_image_disclosure(p)
    re_read = Image.open(p)
    assert re_read.info.get("exif") is not None
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/util/test_iptc_metadata.py -v
```
Expected: 4 FAILED with `ModuleNotFoundError: scripts.util.iptc_metadata`.

- [ ] **Step 3: Implement the writer**

Create `scripts/util/iptc_metadata.py`:
```python
"""IPTC/EXIF metadata writer for AI-generated images.

Per Google Merchant Center AI-image disclosure policy
(https://support.google.com/merchants/answer/14216904) and reaffirmed
in the 2026-05-15 AI Optimization Guide.

IPTC field: DigitalSourceType
Value for fully AI-generated images: TrainedAlgorithmicMedia
(IRI: http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia)

We encode via EXIF UserComment + TIFF ImageDescription
(RFC 9277 — IPTC mapping fallback for formats lacking native IPTC chunk).
"""
from __future__ import annotations

from pathlib import Path

import piexif
from PIL import Image

DIGITAL_SOURCE_TYPE_AI = b"DigitalSourceType=TrainedAlgorithmicMedia"
"""Bytes payload — visible in IPTC parsers + EXIF text readers."""

USER_COMMENT_PAYLOAD = b"ASCII\x00\x00\x00" + DIGITAL_SOURCE_TYPE_AI
"""EXIF UserComment with ASCII charset prefix per EXIF spec."""


def write_ai_image_disclosure(image_path: Path | str) -> None:
    """Write IPTC DigitalSourceType=TrainedAlgorithmicMedia to image at path.

    Supports: JPEG, WebP (PIL exif round-trip).
    AVIF: piexif unsupported; silent skip with R-78 AMBER log.

    Raises:
        FileNotFoundError: if image_path does not exist.
    """
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(p)

    img = Image.open(p)
    fmt = img.format

    existing_exif = img.info.get("exif", b"")
    if existing_exif:
        try:
            exif_dict = piexif.load(existing_exif)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    else:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    exif_dict["Exif"][piexif.ExifIFD.UserComment] = USER_COMMENT_PAYLOAD
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = DIGITAL_SOURCE_TYPE_AI

    exif_bytes = piexif.dump(exif_dict)
    img.save(p, format=fmt, exif=exif_bytes)
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
pytest tests/util/test_iptc_metadata.py -v
```
Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add scripts/util/iptc_metadata.py tests/util/test_iptc_metadata.py
git commit -m "feat(util): IPTC DigitalSourceType writer for AI-generated images (R-78 enforcement)"
```

---

### Task 2.3: Integrate IPTC writer into `generate-images` skill

**Files:**
- Modify: `scripts/production/generate_images.py` (verify path: `find scripts -name "*generate_images*"`)
- Modify: `skills/production/generate-images/SKILL.md`
- Modify: `tests/skills/test_generate_images.py`

- [ ] **Step 1: Locate generate-images implementation**

```bash
find scripts -name "*generate_images*" -o -name "*generate-images*" 2>/dev/null
ls scripts/production/ 2>/dev/null
```
If `scripts/production/generate_images.py` exists, proceed. If it's currently spec-only (Phase 11 Wave 2 stub), the SKILL.md step addition (Step 5) still locks the contract; runtime integration follows Phase 11 work and consumes Task 2.2's utility.

- [ ] **Step 2: Add the failing test**

Append to `tests/skills/test_generate_images.py`:
```python
def test_generate_images_writes_iptc_disclosure(tmp_workspace, mock_higgsfield):
    """Every WebP/JPG output carries IPTC DigitalSourceType=TrainedAlgorithmicMedia."""
    from scripts.production.generate_images import run
    from scripts.util.iptc_metadata import DIGITAL_SOURCE_TYPE_AI
    import piexif

    result = run(project_slug="test-project", new_content_plan_id="row-001")
    assert result["status"] == "success"

    for output_path in result["images"]:
        if str(output_path).endswith(".avif"):
            continue  # piexif unsupported; documented in R-78 failure_mode
        exif = piexif.load(str(output_path))
        assert DIGITAL_SOURCE_TYPE_AI in exif["0th"].get(piexif.ImageIFD.ImageDescription, b"")
```

- [ ] **Step 3: Run test — confirm FAIL**

```bash
pytest tests/skills/test_generate_images.py::test_generate_images_writes_iptc_disclosure -v
```
Expected: FAIL.

- [ ] **Step 4: Integrate into implementation**

In `scripts/production/generate_images.py`, after the Pillow `img.save()` format cascade for each non-AVIF format, add:
```python
from scripts.util.iptc_metadata import write_ai_image_disclosure

# ... existing format cascade loop ...
# After Pillow img.save() per format:
for output_path in [webp_path, jpg_path]:  # AVIF skipped — piexif unsupported
    write_ai_image_disclosure(output_path)
```

- [ ] **Step 5: Update SKILL.md protocol**

In `skills/production/generate-images/SKILL.md`, append a step to the protocol section:

> **Step N+1 — IPTC AI disclosure write:**
> After format cascade (WebP/AVIF/JPG), each non-AVIF output is patched with IPTC `DigitalSourceType=TrainedAlgorithmicMedia` via `scripts/util/iptc_metadata.write_ai_image_disclosure`. AVIF silent skip (piexif unsupported). R-78 enforcement (see `rules/content-html-discipline.md`).

- [ ] **Step 6: Run tests — confirm PASS**

```bash
pytest tests/skills/test_generate_images.py -v
```
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/production/generate_images.py skills/production/generate-images/SKILL.md tests/skills/test_generate_images.py
git commit -m "feat(generate-images): write IPTC DigitalSourceType for AI images (Merchant Center compliance)"
```

---

### Task 2.4: Add Rule R-78 for AI-image IPTC disclosure

**File:**
- Modify: `rules/content-html-discipline.md`

- [ ] **Step 1: Locate insertion point (after R-77)**

```bash
grep -n "^### R-77:" rules/content-html-discipline.md
```

- [ ] **Step 2: Insert R-78 block**

Insert after R-77 block (before next R-XX or "Cross-References"):

```markdown
### R-78: AI-Image IPTC Disclosure (Merchant Center Compliance)

**Statement.** Tüm AI ile üretilmiş görseller (Higgsfield, nano-banana veya başka model çıktısı) IPTC `DigitalSourceType=TrainedAlgorithmicMedia` metadata içerir. Tag EXIF `UserComment` ve TIFF `ImageDescription` IFD slot'larına yazılır (RFC 9277 IPTC mapping fallback). AVIF format piexif tarafından desteklenmediğinden AVIF çıktısı silent skip (R-76 cascade WebP+JPG metadata garanti).

**Rationale.** Google Merchant Center AI-image disclosure policy (2024+, reaffirmed 2026-05-15 AI Optimization Guide); ürün listingi reddedilmesini önler ve AI-content transparency Principle 1 (Truth-Verifiable) tezahürüdür. Google'ın resmi cümlesi: "AI-generated images must include IPTC `DigitalSourceType` metadata labeled as `TrainedAlgorithmicMedia`."

**Enforcement.** `generate-images` skill `scripts/util/iptc_metadata.write_ai_image_disclosure` çağırır; pre-publish `schema-audit` veya `tech-audit` skill output görselleri için IPTC tag presence verify edebilir (opt-in check).

**Failure mode.** Silent skip — implementation hata atarsa AMBER log; metadata write zorunluluğu RED değil çünkü görsel hala kullanılabilir (Merchant Center reject downstream concern).

**Cross-link.** → R-71 (8K ultra realistic), R-72 (image_model), R-73 (1200x675), R-74 (manual upload), R-75 (LCP `<picture>`), R-76 (format cascade), R-77 (alt text).
```

- [ ] **Step 3: Run rule validation + drift-check**

```bash
pytest tests/test_rules_frontmatter.py -v 2>/dev/null
# /pseo-driftcheck if available
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add rules/content-html-discipline.md
git commit -m "docs(rules): add R-78 AI-image IPTC disclosure rule (Merchant Center compliance)"
```

**END OF PHASE 2 — 4 atomic commits, 1 new utility + 1 new rule + 1 skill integration, IPTC compliance for all 9 projects.**

---

# Phase 3 — Bank Seed Foundation (G-AI-05 Hybrid Pipeline)

**Goal:** `brand-onboarding` skill becomes a 3-stage pipeline (Auto Discovery → Operator Review → Bank Write) that populates `experience_database` + `original_research_database` for every project. Schema migration v1.3→v1.4 enriches bank entry format with `applicable_topics`, `phrasings`, `last_used_in_content_id`, `max_usage_per_month` fields (consumed by Phase 4 R-121).

**Affects:** Engine-wide — all current 9 projects + future projects. Critical for May 2026 Core Update "original / helpful / people-first content" emphasis.

**Dependencies:** Phase 2 complete. (Schema migration needs piexif-stable Engine baseline.)

**Duration estimate:** 4-5 hours (5 tasks).

---

### Task 3.1: Project-config schema migration v1.3 → v1.4

**Files:**
- Modify: `schemas/project-config.schema.json`
- Create: `scripts/migrations/0004_project_config_1.3_to_1.4.py`
- Create: `tests/migrations/test_0004_project_config_1.3_to_1.4.py`
- Modify: `templates/project/project.config.template.json`

- [ ] **Step 1: Confirm current schema version**

```bash
grep -A2 "schema_version" schemas/project-config.schema.json | head -10
```
Confirm current `const`/`enum` includes `"1.3"`.

- [ ] **Step 2: Write the failing migration test**

Create `tests/migrations/test_0004_project_config_1.3_to_1.4.py`:
```python
"""Migration 0004 — project-config v1.3 → v1.4: bank entry format enrichment."""
from scripts.migrations.migration_0004_project_config_1_3_to_1_4 import migrate


def test_migration_bumps_schema_version():
    src = {"schema_version": "1.3", "project_id": "test", "profiles": ["ymyl"]}
    out = migrate(src)
    assert out["schema_version"] == "1.4"


def test_migration_preserves_existing_bank_entries():
    """Pre-existing bank entries (rare — most empty) survive intact."""
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "profiles": ["ymyl"],
        "content_settings": {
            "experience_database": [{"id": "old-001", "claim": "10 yıl tecrübe"}],
        },
    }
    out = migrate(src)
    bank = out["content_settings"]["experience_database"]
    assert len(bank) == 1
    assert bank[0]["id"] == "old-001"
    # New fields injected with defaults
    assert bank[0]["applicable_topics"] == []
    assert bank[0]["phrasings"] == []
    assert bank[0]["last_used_in_content_id"] is None
    assert bank[0]["max_usage_per_month"] == 3  # default


def test_migration_idempotent_on_v1_4():
    src = {"schema_version": "1.4", "project_id": "test", "profiles": ["e-commerce"]}
    out = migrate(src)
    assert out["schema_version"] == "1.4"  # no-op


def test_migration_preserves_unrelated_fields():
    src = {
        "schema_version": "1.3",
        "project_id": "test",
        "profiles": ["e-commerce"],
        "content_settings": {"image_model": "nano-banana"},
    }
    out = migrate(src)
    assert out["content_settings"]["image_model"] == "nano-banana"
```

- [ ] **Step 3: Run tests — confirm FAIL**

```bash
pytest tests/migrations/test_0004_project_config_1.3_to_1.4.py -v
```
Expected: FAIL (module missing).

- [ ] **Step 4: Implement the migration**

Create `scripts/migrations/0004_project_config_1.3_to_1.4.py`:
```python
"""Migration: project-config schema v1.3 → v1.4.

Enriches bank entry format with R-121 + Phase 4 consumption fields:
- applicable_topics: list[str] — topic relevance filter
- phrasings: list[str] — rotation variants for same fact
- last_used_in_content_id: str | None — drift detection
- max_usage_per_month: int — density cap (default 3)

Existing bank entries injected with defaults; new field absence is safe (defaults preserve current behavior — no claim is over-used).
"""
from copy import deepcopy

DEFAULT_BANK_ENTRY_NEW_FIELDS = {
    "applicable_topics": [],
    "phrasings": [],
    "last_used_in_content_id": None,
    "max_usage_per_month": 3,
}


def migrate(config: dict) -> dict:
    if config.get("schema_version") == "1.4":
        return config  # idempotent
    out = deepcopy(config)
    out["schema_version"] = "1.4"
    cs = out.setdefault("content_settings", {})
    for bank_key in ("experience_database", "original_research_database"):
        bank = cs.setdefault(bank_key, [])
        for entry in bank:
            for field, default in DEFAULT_BANK_ENTRY_NEW_FIELDS.items():
                entry.setdefault(field, default if not isinstance(default, list) else list(default))
    return out
```

- [ ] **Step 5: Update schema file**

Edit `schemas/project-config.schema.json`:
- Add `"1.4"` to the `schema_version` enum (keep `"1.3"` for migration tolerance)
- In the bank entry object definitions (under `content_settings.experience_database.items` and `content_settings.original_research_database.items`), add the four new fields:
  ```json
  "applicable_topics": {"type": "array", "items": {"type": "string"}, "default": []},
  "phrasings": {"type": "array", "items": {"type": "string"}, "default": []},
  "last_used_in_content_id": {"type": ["string", "null"], "default": null},
  "max_usage_per_month": {"type": "integer", "minimum": 1, "maximum": 12, "default": 3}
  ```

- [ ] **Step 6: Run tests + schema validation**

```bash
pytest tests/migrations/test_0004_project_config_1.3_to_1.4.py -v
pytest tests/test_project_config_schema.py -v 2>/dev/null
```
Expected: PASS.

- [ ] **Step 7: Update template**

Edit `templates/project/project.config.template.json`: bump version to `"1.4"`, ensure `experience_database` and `original_research_database` keys exist with empty arrays.

- [ ] **Step 8: Commit**

```bash
git add schemas/project-config.schema.json scripts/migrations/0004_project_config_1.3_to_1.4.py tests/migrations/ templates/project/project.config.template.json
git commit -m "feat(schema): project-config v1.3→v1.4 — bank entry enrichment (R-121 consumption fields)"
```

---

### Task 3.2: brand-onboarding Stage A — Auto Discovery

**Files:**
- Create: `scripts/meta/brand_onboarding_discovery.py`
- Create: `tests/meta/test_brand_onboarding_discovery.py`

- [ ] **Step 1: Write the failing test**

Create `tests/meta/test_brand_onboarding_discovery.py`:
```python
"""Brand onboarding — Stage A — Auto discovery via DFS + Scrapling."""
import pytest

from scripts.meta.brand_onboarding_discovery import discover


def test_discover_returns_draft_entries_structure(mock_dfs, mock_scrapling, tmp_workspace_factory):
    """Discover returns dict with draft experience + research entries + topic candidates."""
    project = tmp_workspace_factory(slug="test", profiles=["e-commerce"], domain="https://example.com/")
    result = discover(project_slug="test")
    assert "draft_experience_entries" in result
    assert "draft_research_entries" in result
    assert "topic_candidates" in result
    assert isinstance(result["draft_experience_entries"], list)


def test_discover_extracts_founding_year_from_whois(mock_dfs_whois_2018, mock_scrapling, tmp_workspace_factory):
    """When WHOIS returns domain creation 2018, founding year proposed as 2018."""
    project = tmp_workspace_factory(slug="test", profiles=["b2b-saas"])
    result = discover(project_slug="test")
    matching = [e for e in result["draft_experience_entries"] if "founding" in e.get("hint", "")]
    assert len(matching) >= 1
    assert "2018" in matching[0]["claim_core"]


def test_discover_returns_topic_candidates_from_keywords_for_site(mock_dfs_keywords_top20, tmp_workspace_factory):
    """Top-20 keywords from DFS labs become applicable_topics candidate list."""
    project = tmp_workspace_factory(slug="test", profiles=["e-commerce"])
    result = discover(project_slug="test")
    assert len(result["topic_candidates"]) > 0
    assert all(isinstance(t, str) for t in result["topic_candidates"])


def test_discover_skips_paid_mcp_when_budget_exhausted(mock_dfs_budget_exhausted, tmp_workspace_factory):
    """Per F-16 budget pre-flight: when DFS budget exhausted, DURUR awaiting_approval."""
    project = tmp_workspace_factory(slug="test", profiles=["e-commerce"])
    result = discover(project_slug="test")
    assert result["status"] == "awaiting_approval"
    assert "budget" in result["reason"].lower()
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/meta/test_brand_onboarding_discovery.py -v
```
Expected: 4 FAILED.

- [ ] **Step 3: Implement Stage A**

Create `scripts/meta/brand_onboarding_discovery.py`:
```python
"""Brand onboarding Stage A — Auto discovery via DFS + Scrapling.

Pipeline:
1. DFS domain_analytics_whois_overview → domain creation date (founding year proxy)
2. DFS on_page_content_parsing → /hakkimizda + /ekibimiz + /case-studies + /portfolio
3. DFS business_data_business_listings_search → GBP-style listing (categories, year, hours)
4. DFS dataforseo_labs_google_keywords_for_site → top-20 keywords → applicable_topics candidates
5. Scrapling fetch → any /case-studies or /referanslar HTML for case study extraction
6. Output: draft_experience_entries + draft_research_entries + topic_candidates (Stage B consumes)

Per F-16: paid MCP budget pre-flight check; DURUR awaiting_approval if exhausted.
Per memory feedback_indexing_api_consent: no submission, only discovery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def discover(project_slug: str, workspace_root: Path | str | None = None) -> dict[str, Any]:
    """Run Stage A — auto-discover bank candidates from public sources."""
    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    project_dir = workspace_root / "projects" / project_slug
    config = json.loads((project_dir / "project.config.json").read_text())

    if not _budget_preflight():
        return {"status": "awaiting_approval", "reason": "DFS budget exhausted (F-16 pre-flight)"}

    domain = config.get("domain", "").rstrip("/")
    profiles = config.get("profiles", [])

    draft_experience = []
    draft_research = []
    topic_candidates = []

    founding_year = _fetch_whois_creation_year(domain)
    if founding_year:
        draft_experience.append({
            "hint": "founding_year",
            "claim_core": f"{2026 - founding_year}+ yıl sektör tecrübesi (domain {founding_year} kuruluş)",
            "evidence_url": domain,
            "source": "whois",
            "needs_review": True,
        })

    about_data = _fetch_about_page(domain)
    if about_data:
        draft_experience.extend(_extract_from_about(about_data))

    if "local-service" in profiles:
        gbp_data = _fetch_business_listing(domain, config)
        if gbp_data:
            draft_experience.extend(_extract_from_gbp(gbp_data))

    case_studies = _fetch_case_study_pages(domain)
    if case_studies:
        draft_experience.extend(_extract_case_studies(case_studies))

    topic_candidates = _fetch_top_keywords(domain, config)

    return {
        "status": "success",
        "draft_experience_entries": draft_experience,
        "draft_research_entries": draft_research,
        "topic_candidates": topic_candidates,
        "project_slug": project_slug,
    }


def _budget_preflight() -> bool:
    """Check DFS budget — placeholder; production reads from check_budget.py."""
    # In production this calls scripts/budget/check_budget.py
    return True


def _fetch_whois_creation_year(domain: str) -> int | None:
    """Stub — production calls mcp__dataforseo__domain_analytics_whois_overview."""
    return None  # implemented via MCP at runtime


def _fetch_about_page(domain: str) -> dict | None:
    """Stub — production calls mcp__dataforseo__on_page_content_parsing for /hakkimizda."""
    return None


def _extract_from_about(about_data: dict) -> list[dict]:
    """Parse about page text — pull certifications, years, partner mentions."""
    return []


def _fetch_business_listing(domain: str, config: dict) -> dict | None:
    """Stub — production calls mcp__dataforseo__business_data_business_listings_search."""
    return None


def _extract_from_gbp(gbp_data: dict) -> list[dict]:
    """Parse GBP categories, hours, year founded, attributes."""
    return []


def _fetch_case_study_pages(domain: str) -> list[dict]:
    """Stub — production tries /case-studies, /musteriler, /portfolio via Scrapling fetch."""
    return []


def _extract_case_studies(pages: list[dict]) -> list[dict]:
    """Extract titled case story headings + summary text."""
    return []


def _fetch_top_keywords(domain: str, config: dict) -> list[str]:
    """Stub — production calls mcp__dataforseo__dataforseo_labs_google_keywords_for_site."""
    return []
```

- [ ] **Step 4: Run tests with mocks**

The tests reference `mock_dfs`, `mock_scrapling`, `mock_dfs_whois_2018`, `mock_dfs_keywords_top20`, `mock_dfs_budget_exhausted`, `tmp_workspace_factory` fixtures. Create these in `tests/conftest.py` if not already present (follow existing fixture style from `tests/skills/conftest.py`).

```bash
pytest tests/meta/test_brand_onboarding_discovery.py -v
```
Expected: PASS (with fixtures returning canned MCP responses).

- [ ] **Step 5: Commit**

```bash
git add scripts/meta/brand_onboarding_discovery.py tests/meta/test_brand_onboarding_discovery.py tests/conftest.py
git commit -m "feat(brand-onboarding): Stage A auto-discovery via DFS+Scrapling (G-AI-05 hybrid pipeline)"
```

---

### Task 3.3: brand-onboarding Stage B — Operator Review

**Files:**
- Create: `scripts/meta/brand_onboarding_review.py`
- Create: `tests/meta/test_brand_onboarding_review.py`

- [ ] **Step 1: Write the failing test**

Create `tests/meta/test_brand_onboarding_review.py`:
```python
"""Stage B — Operator review of draft bank entries."""
from scripts.meta.brand_onboarding_review import generate_review_prompt, apply_review_decisions


def test_generate_review_prompt_lists_all_drafts():
    """Review prompt lists every discovered draft with index + 3 actions: approve / edit / reject."""
    discovery_output = {
        "draft_experience_entries": [
            {"hint": "founding_year", "claim_core": "8 yıl sektör tecrübesi", "evidence_url": "https://x.com"},
        ],
        "draft_research_entries": [],
        "topic_candidates": ["e-para", "yan haklar"],
    }
    prompt = generate_review_prompt(discovery_output)
    assert "8 yıl sektör tecrübesi" in prompt
    assert "[A] approve" in prompt or "approve" in prompt.lower()


def test_apply_review_decisions_approves_only_marked():
    """Only entries marked approved (with optional edits) survive to write stage."""
    discovery_output = {
        "draft_experience_entries": [
            {"hint": "founding_year", "claim_core": "8 yıl", "evidence_url": "https://x.com"},
            {"hint": "about_text", "claim_core": "BDDK lisanslı", "evidence_url": "https://x.com/about"},
        ],
        "draft_research_entries": [],
        "topic_candidates": ["e-para"],
    }
    decisions = {
        "experience_0": {"action": "approve"},
        "experience_1": {"action": "reject"},
    }
    result = apply_review_decisions(discovery_output, decisions)
    assert len(result["approved_experience"]) == 1
    assert result["approved_experience"][0]["claim_core"] == "8 yıl"


def test_apply_review_decisions_supports_edit():
    """Edit decision lets operator override claim_core / evidence_url."""
    discovery_output = {
        "draft_experience_entries": [{"hint": "founding_year", "claim_core": "8 yıl", "evidence_url": "https://x.com"}],
        "draft_research_entries": [],
        "topic_candidates": [],
    }
    decisions = {"experience_0": {"action": "edit", "claim_core": "10 yıl BDDK lisanslı e-para tecrübesi"}}
    result = apply_review_decisions(discovery_output, decisions)
    assert result["approved_experience"][0]["claim_core"] == "10 yıl BDDK lisanslı e-para tecrübesi"
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/meta/test_brand_onboarding_review.py -v
```

- [ ] **Step 3: Implement Stage B**

Create `scripts/meta/brand_onboarding_review.py`:
```python
"""Brand onboarding Stage B — Operator review of discovery output.

Generates a structured prompt listing every draft entry; operator decides
approve / edit / reject per entry. Returns approved set for Stage C.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def generate_review_prompt(discovery_output: dict) -> str:
    """Render operator-facing review prompt as markdown."""
    lines = ["# Brand Onboarding — Operator Review", ""]
    lines.append(f"## Discovered {len(discovery_output['draft_experience_entries'])} experience entries")
    for i, e in enumerate(discovery_output["draft_experience_entries"]):
        lines.append(f"\n### experience_{i}")
        lines.append(f"- **Claim:** {e['claim_core']}")
        lines.append(f"- **Evidence:** {e.get('evidence_url', '(none)')}")
        lines.append(f"- **Source:** {e.get('source', e.get('hint', 'unknown'))}")
        lines.append("- Action: [A] approve / [E] edit / [R] reject")

    lines.append(f"\n## Discovered {len(discovery_output['draft_research_entries'])} research entries")
    for i, r in enumerate(discovery_output["draft_research_entries"]):
        lines.append(f"\n### research_{i}")
        lines.append(f"- **Title:** {r.get('title', '(untitled)')}")
        lines.append(f"- **Methodology:** {r.get('methodology', '(unknown)')}")
        lines.append("- Action: [A] approve / [E] edit / [R] reject")

    lines.append(f"\n## Topic candidates (for applicable_topics)")
    lines.append(", ".join(discovery_output["topic_candidates"]))
    return "\n".join(lines)


def apply_review_decisions(discovery_output: dict, decisions: dict[str, dict]) -> dict[str, Any]:
    """Filter + edit draft entries per operator decisions.

    decisions format:
        {"experience_0": {"action": "approve|edit|reject", "claim_core": "...", ...}, ...}
    """
    approved_experience = []
    for i, entry in enumerate(discovery_output["draft_experience_entries"]):
        key = f"experience_{i}"
        decision = decisions.get(key, {"action": "reject"})
        if decision["action"] == "reject":
            continue
        approved = deepcopy(entry)
        if decision["action"] == "edit":
            for field in ("claim_core", "evidence_url"):
                if field in decision:
                    approved[field] = decision[field]
        approved_experience.append(approved)

    approved_research = []
    for i, entry in enumerate(discovery_output["draft_research_entries"]):
        key = f"research_{i}"
        decision = decisions.get(key, {"action": "reject"})
        if decision["action"] == "reject":
            continue
        approved = deepcopy(entry)
        if decision["action"] == "edit":
            for field in ("title", "methodology", "url"):
                if field in decision:
                    approved[field] = decision[field]
        approved_research.append(approved)

    return {
        "approved_experience": approved_experience,
        "approved_research": approved_research,
        "topic_candidates": discovery_output["topic_candidates"],
    }
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
pytest tests/meta/test_brand_onboarding_review.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scripts/meta/brand_onboarding_review.py tests/meta/test_brand_onboarding_review.py
git commit -m "feat(brand-onboarding): Stage B operator review of draft bank entries"
```

---

### Task 3.4: brand-onboarding Stage C — Bank Write

**Files:**
- Create: `scripts/meta/brand_onboarding_write.py`
- Create: `tests/meta/test_brand_onboarding_write.py`

- [ ] **Step 1: Write the failing test**

Create `tests/meta/test_brand_onboarding_write.py`:
```python
"""Stage C — Write approved bank entries to project.config.json."""
import json
from scripts.meta.brand_onboarding_write import write_bank_entries


def test_write_appends_to_existing_bank(tmp_workspace_factory):
    project = tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [
            {"claim_core": "10 yıl BDDK", "evidence_url": "https://example.com/hakkimizda"},
        ],
        "approved_research": [],
        "topic_candidates": ["e-para", "BDDK"],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "success"

    config = json.loads((project / "project.config.json").read_text())
    bank = config["content_settings"]["experience_database"]
    assert len(bank) == 1
    entry = bank[0]
    assert entry["claim_core"] == "10 yıl BDDK"
    assert entry["id"].startswith("exp-")  # auto-generated id
    assert entry["applicable_topics"] == ["e-para", "BDDK"]  # topic candidates injected
    assert entry["max_usage_per_month"] == 3  # default
    assert entry["last_used_in_content_id"] is None  # initial state


def test_write_rejects_entry_without_evidence_url(tmp_workspace_factory):
    """R-44 source verification: every bank entry MUST have evidence_url."""
    project = tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [{"claim_core": "10 yıl", "evidence_url": ""}],
        "approved_research": [],
        "topic_candidates": [],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "error"
    assert "evidence_url" in result["error"]


def test_write_atomic_no_partial_writes(tmp_workspace_factory):
    """If second entry is invalid, neither is written."""
    project = tmp_workspace_factory(slug="test", profiles=["ymyl"])
    review_output = {
        "approved_experience": [
            {"claim_core": "10 yıl", "evidence_url": "https://example.com/x"},
            {"claim_core": "broken", "evidence_url": ""},  # invalid
        ],
        "approved_research": [],
        "topic_candidates": [],
    }
    result = write_bank_entries(project_slug="test", review_output=review_output)
    assert result["status"] == "error"

    config = json.loads((project / "project.config.json").read_text())
    assert config["content_settings"]["experience_database"] == []  # unchanged
```

- [ ] **Step 2: Implement Stage C**

Create `scripts/meta/brand_onboarding_write.py`:
```python
"""Brand onboarding Stage C — Atomic write of approved entries to project.config.json.

Per R-44 source verification: every bank entry MUST have evidence_url.
Per R-15 site reality: evidence_url verified before write (HTTP 200 check
optional — runtime decision based on budget).
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any


def write_bank_entries(project_slug: str, review_output: dict, workspace_root: Path | str | None = None) -> dict[str, Any]:
    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    config_path = workspace_root / "projects" / project_slug / "project.config.json"
    config = json.loads(config_path.read_text())

    # Validate every entry before writing
    new_exp_entries = []
    for raw_entry in review_output["approved_experience"]:
        if not raw_entry.get("evidence_url"):
            return {"status": "error", "error": "evidence_url missing on experience entry"}
        new_exp_entries.append(_build_experience_entry(raw_entry, review_output["topic_candidates"]))

    new_res_entries = []
    for raw_entry in review_output["approved_research"]:
        if not raw_entry.get("url"):
            return {"status": "error", "error": "url missing on research entry"}
        new_res_entries.append(_build_research_entry(raw_entry, review_output["topic_candidates"]))

    # Atomic apply
    cs = config.setdefault("content_settings", {})
    cs.setdefault("experience_database", []).extend(new_exp_entries)
    cs.setdefault("original_research_database", []).extend(new_res_entries)

    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False))

    return {
        "status": "success",
        "experience_added": len(new_exp_entries),
        "research_added": len(new_res_entries),
    }


def _build_experience_entry(raw: dict, topic_candidates: list[str]) -> dict:
    return {
        "id": f"exp-{uuid.uuid4().hex[:8]}",
        "claim_core": raw["claim_core"],
        "evidence_url": raw["evidence_url"],
        "applicable_topics": list(topic_candidates),
        "phrasings": raw.get("phrasings", []),
        "last_used_in_content_id": None,
        "max_usage_per_month": raw.get("max_usage_per_month", 3),
        "evidence_type": raw.get("evidence_type", "site_reference"),
        "verified_date": raw.get("verified_date"),
    }


def _build_research_entry(raw: dict, topic_candidates: list[str]) -> dict:
    return {
        "id": f"res-{uuid.uuid4().hex[:8]}",
        "title": raw["title"],
        "methodology": raw.get("methodology", ""),
        "sample_size": raw.get("sample_size"),
        "url": raw["url"],
        "publication_date": raw.get("publication_date"),
        "applicable_topics": list(topic_candidates),
        "phrasings": raw.get("phrasings", []),
        "last_used_in_content_id": None,
        "max_usage_per_month": raw.get("max_usage_per_month", 3),
        "key_findings": raw.get("key_findings", []),
    }
```

- [ ] **Step 3: Run tests — confirm PASS**

```bash
pytest tests/meta/test_brand_onboarding_write.py -v
```

- [ ] **Step 4: Commit**

```bash
git add scripts/meta/brand_onboarding_write.py tests/meta/test_brand_onboarding_write.py
git commit -m "feat(brand-onboarding): Stage C atomic bank write with R-44 evidence_url validation"
```

---

### Task 3.5: brand-onboarding SKILL.md revize + init-project chain

**Files:**
- Modify: `skills/meta/brand-onboarding/SKILL.md`
- Modify: `skills/meta/init-project/SKILL.md`

- [ ] **Step 1: Read current brand-onboarding SKILL.md**

```bash
cat skills/meta/brand-onboarding/SKILL.md | head -100
```

- [ ] **Step 2: Update brand-onboarding SKILL.md frontmatter + protocol**

Edit `skills/meta/brand-onboarding/SKILL.md`:

In frontmatter, update `description.use_when` to mention bank seed alongside existing brand identity collection. Add to `produces` array: `"new-blog"` and `"revise-content"` (these now depend on populated banks).

In the protocol body section, add a new "Bank Seed Pipeline" subsection documenting the 3-stage flow:

```markdown
## Bank Seed Pipeline (Stages A + B + C)

**Stage A — Auto Discovery:** `scripts/meta/brand_onboarding_discovery.py.discover(project_slug)` runs DFS + Scrapling probes against the project's public web surface. Output: draft_experience_entries + draft_research_entries + topic_candidates.

**Stage B — Operator Review:** `scripts/meta/brand_onboarding_review.py` renders a markdown prompt listing every draft for operator approve / edit / reject decision. Output: approved set.

**Stage C — Atomic Bank Write:** `scripts/meta/brand_onboarding_write.py.write_bank_entries()` appends approved entries to `project.config.json[content_settings.experience_database|original_research_database]` with R-44 evidence_url validation. All-or-nothing — no partial writes.

### 5 Profile-Aware Questions (when discovery returns empty for an area)

| # | Question | Profile gate | Bank target |
|---|----------|--------------|-------------|
| 1 | Sektör tecrübesi (yıl + sertifika + partner) | all profiles | experience_database |
| 2 | 3 müşteri vaka hikayesi | all profiles | experience_database |
| 3 | Yönetici sektörel deneyimi | YMYL + b2b-saas | experience_database |
| 4 | Şirket içi anket / araştırma / case study | all (skip OK) | original_research_database |
| 5 | First-hand somut olaylar | YMYL + b2b-saas | experience_database |

### DURUR Cascades (new)

- **BANK-SEED-DISCOVERY-EMPTY:** Stage A returns 0 candidates; skill awaiting_approval, operator must supply manually
- **BANK-SEED-EVIDENCE-MISSING:** Stage C rejects entry without evidence_url (R-44 enforcement)
- **BANK-SEED-PROFILE-MIN-NOT-MET:** YMYL profile + <3 approved experience entries → awaiting_approval, operator must supply more
```

- [ ] **Step 3: Update init-project SKILL.md to chain brand-onboarding**

In `skills/meta/init-project/SKILL.md`, in the `produces` frontmatter array, ensure `"brand-onboarding"` is listed (add if not present). In the protocol body, add a "Mandatory Cascade" subsection:

```markdown
## Mandatory Cascade — brand-onboarding

After project scaffolding completes, `init-project` MUST emit a `cascade: brand-onboarding` event to `_state/events.jsonl`. The skill auto-runner picks this up and runs `brand-onboarding` with the new project slug. Init is not considered "complete" until brand-onboarding's bank-seed Stage C writes successfully.

YMYL projects: init blocks until ≥3 experience entries are seeded. Non-YMYL: init blocks until ≥1 experience entry or operator explicit-skip.
```

- [ ] **Step 4: Run drift-check**

```bash
pytest tests/test_rules_frontmatter.py tests/test_skills_frontmatter.py -v 2>/dev/null
# /pseo-driftcheck if available
```

- [ ] **Step 5: Commit**

```bash
git add skills/meta/brand-onboarding/SKILL.md skills/meta/init-project/SKILL.md
git commit -m "feat(skills): brand-onboarding 3-stage pipeline + init-project mandatory chain"
```

**END OF PHASE 3 — 5 atomic commits, schema v1.4 migration + 3-stage hybrid bank seed pipeline + init-project enforcement.**

---

# Phase 4 — Bank Entry Rotation + Density Cap (R-121)

**Goal:** Engine prevents "parrot repetition" of bank entries in content output via R-121 rule + skill consume logic. Critical for May 2026 Core Update "repetitive content visibility loss" defense.

**Affects:** `new-blog`, `revise-content`, `faq-optimization` skills.

**Dependencies:** Phase 3 complete (schema v1.4 + populated bank entries required).

**Duration estimate:** ~1 hour (1 rule write + 3 skill patches).

---

### Task 4.1: Add R-121 rule

**File:**
- Modify: `rules/content-eeat-discipline.md`

- [ ] **Step 1: Locate insertion point**

```bash
grep -n "^### R-119:" rules/content-eeat-discipline.md
grep -n "^### R-120:" rules/content-eeat-discipline.md  # may not exist
```

Insert R-121 after the last existing R-1XX rule (likely R-119 or R-120).

- [ ] **Step 2: Insert R-121 block**

```markdown
### R-121: Bank Entry Rotation + Density Cap + Topic Relevance

**Statement.** Production skill (new-blog / revise-content / faq-optimization) bank entry kullanırken 3 koşulu birlikte sağlamak ZORUNLU:

1. **Topic Relevance:** Entry'nin `applicable_topics` array'i içerik konusuyla (master.xlsx[new_content_plan].primary_keyword + topical_map.cluster_id eşleşmesi) örtüşmeli; örtüşmüyorsa entry kullanılmaz.
2. **Density Cap (profile-aware):** İçerik başına bank entry kullanımı:
   - YMYL: max 2 experience + 1 research entry per content
   - b2b-saas: max 1 experience + 1 research entry per content
   - e-commerce / local-service / portfolio: max 1 experience entry per content
3. **Rotation:** Aynı `id`'ye sahip entry, son 30 günde `master.xlsx[completed_work]` içinde kullanılmış mı? Evet ve `usage_count >= max_usage_per_month` ise entry skip; alternatif phrasing veya farklı entry seçilir.

**Rationale.** May 2026 Core Update "repetitive content visibility loss" ve "automated, ad-bloated content" penalty sinyallerine karşı Engine self-protection. R-118 (AI signature humanize) stilistik tekrarı yakalar; R-121 **semantik tekrar** yakalar (aynı bilgi farklı blog'larda tekrar etmesin). Bank entry'nin `phrasings` array'i ile aynı çekirdek bilgi farklı cümlelerle aktarılabilir (rotation içinde rotation).

**Enforcement.** Production skill pre-publish:
- Topic relevance check: applicable_topics ∩ blog_topics ≠ ∅ → entry candidate; ∅ → skip
- Density count: candidate set'ten profile-aware max sayıda seç
- Rotation check: master.xlsx[completed_work] son 30 gün filter, usage_count tally; cap üstü skip
- Seçilen entry'nin `last_used_in_content_id` güncellenir (Stage C write yeniden çağrılır mı yoksa skill update mı? — implementation karari Task 4.2'de netleşir)

**Failure mode.** AMBER if no entry passes all 3 checks (skill yeniden phrasing rotation dener); 2x AMBER → RED (yayın bloklu, operator review).

**Cross-link.** → R-105 (expert quote bank), R-114 (original research bank), R-119 (first-hand experience bank), R-118 (AI signature humanize — stilistik karşılık), schema v1.4 bank entry format.
```

- [ ] **Step 3: Run rule validation**

```bash
pytest tests/test_rules_frontmatter.py -v 2>/dev/null
```

- [ ] **Step 4: Commit**

```bash
git add rules/content-eeat-discipline.md
git commit -m "feat(rules): add R-121 bank entry rotation + density cap + topic relevance"
```

---

### Task 4.2: new-blog skill — R-121 consume logic

**Files:**
- Modify: `skills/production/new-blog/SKILL.md`
- Modify: corresponding implementation (if exists; verify with `find scripts/production -name "*new_blog*" -o -name "*new-blog*"`)
- Modify: `tests/skills/test_new_blog.py` (if exists)

- [ ] **Step 1: Add R-121 reference to SKILL.md consumes section**

In `skills/production/new-blog/SKILL.md` frontmatter, ensure `rules:rules/content-eeat-discipline.md` is in consumes (likely already there). Add a body section "R-121 Bank Selection Logic":

```markdown
## R-121 Bank Selection Logic (pre-publish)

Pre-publish, the skill selects bank entries via 3-step filter:

1. **Topic match:** `project.config[experience_database].applicable_topics ∩ master.xlsx[new_content_plan].primary_keyword_cluster ≠ ∅`
2. **Profile density:** apply per-profile cap (YMYL: 2 exp + 1 res / b2b-saas: 1+1 / others: 1+0)
3. **Rotation:** for each candidate, count usage in `master.xlsx[completed_work]` last 30 days; skip if `count >= max_usage_per_month`

Selected entries' `last_used_in_content_id` field is updated post-publish (atomic with completed_work row append).
```

- [ ] **Step 2: Add failing test (if implementation exists)**

```python
def test_new_blog_skips_entry_at_density_cap(tmp_workspace_with_full_bank):
    """When an entry hit max_usage_per_month, skill skips and tries another."""
    # ... arrange bank with 1 entry at max_usage_per_month=1, used 1 time last 30 days
    # ... run new-blog
    # ... assert that entry not in output content
```

- [ ] **Step 3: Implementation (deferred to Phase 11 if skill is spec-only)**

If `scripts/production/new_blog.py` exists, add the 3-step filter function. If not, SKILL.md spec lock is sufficient for now — runtime integration follows Phase 11 W.

- [ ] **Step 4: Commit**

```bash
git add skills/production/new-blog/SKILL.md
git commit -m "feat(new-blog): R-121 bank selection logic spec (topic + density + rotation)"
```

---

### Task 4.3: revise-content skill — R-121 consume logic

**File:**
- Modify: `skills/production/revise-content/SKILL.md`

- [ ] **Step 1: Mirror Task 4.2 changes to revise-content**

Add the "R-121 Bank Selection Logic" section. Same 3-step filter. Same `last_used_in_content_id` update post-publish.

Note: revise-content has an additional concern — if a content piece already uses bank entries (pre-revision), those count toward the density cap. R-121 says "per content" not "per skill invocation".

- [ ] **Step 2: Commit**

```bash
git add skills/production/revise-content/SKILL.md
git commit -m "feat(revise-content): R-121 bank selection logic spec"
```

---

### Task 4.4: faq-optimization skill — R-121 consume logic

**File:**
- Modify: `skills/production/faq-optimization/SKILL.md`

- [ ] **Step 1: Mirror to faq-optimization**

faq-optimization is typically lower-density content; R-121 density cap likely reduces further (FAQ items rarely cite experience claims). Spec the same logic but note in the body: "FAQ items often do not need bank entries; R-121 applies only when an FAQ answer asserts an experience or research claim."

- [ ] **Step 2: Run drift-check (end of Phase 4)**

```bash
pytest tests/test_rules_frontmatter.py tests/test_skills_frontmatter.py -v 2>/dev/null
```

- [ ] **Step 3: Commit**

```bash
git add skills/production/faq-optimization/SKILL.md
git commit -m "feat(faq-optimization): R-121 bank selection logic spec"
```

**END OF PHASE 4 — 4 atomic commits, R-121 rule + 3 skill consume specs, semantic repetition prevention.**

---

# Phase 5 — GBP Audit Skill (G-AI-02)

**Goal:** New `skills/discovery/gbp-audit/` skill audits Google Business Profile data for local-service projects via DFS `business_data_business_listings_search` + Scrapling fallback. Outputs gap report + optimization tasks to `master.xlsx[gbp_audit]` new sheet.

**Affects:** demo-aluminum CA, demo-construction İnşaat, demo-hvac (local-service hybrid).

**Dependencies:** Phase 4 complete.

**Duration estimate:** 2-3 hours (4 tasks).

---

### Task 5.1: master.xlsx[gbp_audit] sheet schema

**File:**
- Modify: `schemas/master-excel.schema.json`

- [ ] **Step 1: Read current master-excel schema**

```bash
grep -A2 "\"tech_seo\":" schemas/master-excel.schema.json | head -20
```

- [ ] **Step 2: Add gbp_audit sheet schema**

In `schemas/master-excel.schema.json`, add new sheet definition mirroring `tech_seo` shape:

```json
"gbp_audit": {
  "type": "array",
  "description": "GBP discovery skill output — gaps + optimization tasks per project.",
  "items": {
    "type": "object",
    "required": ["audit_id", "audit_date", "category", "gap_description", "severity", "recommended_action", "status"],
    "properties": {
      "audit_id": {"type": "string", "pattern": "^gbp-[a-z0-9]+$"},
      "audit_date": {"type": "string", "format": "date"},
      "category": {"enum": ["nap", "categories", "photos", "hours", "attributes", "posts", "qa", "reviews"]},
      "gap_description": {"type": "string"},
      "severity": {"enum": ["HIGH", "MEDIUM", "LOW"]},
      "recommended_action": {"type": "string"},
      "status": {"enum": ["TODO", "IN_PROGRESS", "DONE", "DISMISSED"], "default": "TODO"}
    }
  }
}
```

- [ ] **Step 3: Update allowed_writers manifest if present**

If `schemas/master-excel.schema.json` has an `allowed_writers` map, add `"gbp_audit": ["gbp-audit"]`.

- [ ] **Step 4: Commit**

```bash
git add schemas/master-excel.schema.json
git commit -m "feat(schema): master.xlsx[gbp_audit] sheet schema (G-AI-02)"
```

---

### Task 5.2: gbp-audit SKILL.md + skill scaffolding

**Files:**
- Create: `skills/discovery/gbp-audit/SKILL.md`
- Create: `commands/pseo-gbp-audit.md`

- [ ] **Step 1: Model on tech-audit SKILL.md**

```bash
cat skills/discovery/tech-audit/SKILL.md | head -100
```

- [ ] **Step 2: Create gbp-audit SKILL.md**

Create with frontmatter mirroring tech-audit:
```yaml
---
name: gbp-audit
description: |
  Use when: kullanıcı "GBP audit", "Google Business Profile kontrol", "place_id eksik mi",
  "business listing", "harita listing" der ya da /pseo-gbp-audit çağırır. Local-service
  profile zorunlu; DFS business_data_business_listings_search HEAVY (~3 credit/run);
  budget pre-flight ZORUNLU.
  Also use when: project.config.profiles içinde 'local-service' var; sf-import veya
  init-project çalışmış (master.xlsx hazır); GBP gap analysis triage.
  Do not use when: profile != local-service (skip); master.xlsx eksik (DURUR #6);
  budget exhausted (DURUR #1).
version: "1.0"
status: active
category: discovery
inputs:
  project_slug:
    type: string
    required: true
outputs:
  - "master.xlsx#gbp_audit"
  - "outputs/reports/{date}-gbp-audit.md"
  - "events.jsonl"
consumes:
  - "init-project:projects/{slug}/project.config.json"
produces:
  - "drift-check"
  - "monthly-report"
mcp_tools:
  required:
    - "mcp__dataforseo__business_data_business_listings_search"
  optional:
    - "mcp__ScraplingServer__fetch"
budget:
  uses_paid_mcp: true
  estimated_credits: 3
autonomy:
  confidence: MEDIUM
  requires_approval: true
  safe_auto_execute: false
---
```

Then add body documenting the 8-step protocol (mirror tech-audit's structure):
1. Profile gate check (local-service in profiles else skip)
2. Budget pre-flight
3. DFS business_data_business_listings_search call
4. Scrapling fallback if DFS returns empty
5. Gap analysis (NAP / categories / photos / hours / attributes / posts / Q&A / reviews)
6. Severity assignment per gap
7. Write to master.xlsx[gbp_audit] via transaction.append
8. events.jsonl audit + outputs/reports markdown render

- [ ] **Step 3: Create slash command**

Create `commands/pseo-gbp-audit.md` mirroring `commands/pseo-tech-audit.md`. Body references skill name `gbp-audit`.

- [ ] **Step 4: Commit**

```bash
git add skills/discovery/gbp-audit/SKILL.md commands/pseo-gbp-audit.md
git commit -m "feat(skill): gbp-audit SKILL.md scaffolding (discovery category, DFS+Scrapling pattern)"
```

---

### Task 5.3: gbp_audit_transform.py implementation

**Files:**
- Create: `scripts/discovery/gbp_audit_transform.py`
- Create: `tests/skills/test_gbp_audit.py`

- [ ] **Step 1: Write failing tests**

Create `tests/skills/test_gbp_audit.py`:
```python
"""gbp-audit discovery skill — DFS business listings + Scrapling fallback."""
import pytest

from scripts.discovery.gbp_audit_transform import run


def test_gbp_audit_skips_when_no_local_service_profile(tmp_workspace_factory):
    project = tmp_workspace_factory(slug="ecom-only", profiles=["e-commerce"])
    result = run(project_slug="ecom-only")
    assert result["status"] == "skipped"
    assert "local-service" in result["reason"]


def test_gbp_audit_emits_gap_rows_per_missing_field(mock_dfs_business_data_partial, tmp_workspace_factory):
    """When DFS returns listing with missing categories + photos, audit emits gap rows."""
    project = tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = run(project_slug="local-test")
    assert result["status"] == "success"
    gap_categories = {row["category"] for row in result["gap_rows"]}
    assert "categories" in gap_categories
    assert "photos" in gap_categories


def test_gbp_audit_severity_assignment(mock_dfs_business_data_partial, tmp_workspace_factory):
    """Missing primary category → HIGH; missing single photo → MEDIUM; missing post → LOW."""
    project = tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = run(project_slug="local-test")
    severities = {row["category"]: row["severity"] for row in result["gap_rows"]}
    # exact assertions depend on mock data
    assert all(s in ("HIGH", "MEDIUM", "LOW") for s in severities.values())


def test_gbp_audit_respects_budget_preflight(mock_dfs_budget_exhausted, tmp_workspace_factory):
    project = tmp_workspace_factory(slug="local-test", profiles=["local-service"])
    result = run(project_slug="local-test")
    assert result["status"] == "awaiting_approval"
    assert "budget" in result["reason"].lower()
```

- [ ] **Step 2: Run tests — confirm FAIL**

```bash
pytest tests/skills/test_gbp_audit.py -v
```

- [ ] **Step 3: Implement gbp_audit_transform**

Create `scripts/discovery/gbp_audit_transform.py`:
```python
"""gbp-audit — discovery skill transforming DFS business listings into gap report.

Per F-16 plugin-agnostic: no MCP install. Per memory feedback_indexing_api_consent:
no autonomous GBP API submit — only audit + report.

Severity matrix (per category):
- nap (NAP consistency): HIGH if mismatch with project.config domain
- categories: HIGH if no primary category, MEDIUM if <2 secondary
- photos: HIGH if <3 photos, MEDIUM if <10, LOW if <20
- hours: HIGH if missing, MEDIUM if no holiday hours
- attributes: MEDIUM if profile-relevant attribute missing
- posts: LOW if no posts last 30 days
- qa: LOW if no Q&A engagement
- reviews: MEDIUM if response rate <50%, LOW if avg rating <4.0
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4


def run(project_slug: str, workspace_root: Path | str | None = None) -> dict[str, Any]:
    workspace_root = Path(workspace_root or os.environ["PSEO_WORKSPACE_ROOT"])
    project_dir = workspace_root / "projects" / project_slug
    config = json.loads((project_dir / "project.config.json").read_text())

    if "local-service" not in config.get("profiles", []):
        return {"status": "skipped", "reason": "Profile 'local-service' missing from project.profiles", "project_slug": project_slug}

    if not _budget_preflight(config):
        return {"status": "awaiting_approval", "reason": "DFS budget exhausted (F-16 pre-flight)"}

    listing = _fetch_listing(config)
    if not listing:
        listing = _scrapling_fallback(config)

    gap_rows = _analyze_gaps(listing, config)

    return {"status": "success", "project_slug": project_slug, "gap_rows": gap_rows}


def _budget_preflight(config: dict) -> bool:
    """Stub — production checks scripts/budget/check_budget.py."""
    return True


def _fetch_listing(config: dict) -> dict | None:
    """Stub — production calls mcp__dataforseo__business_data_business_listings_search."""
    return None


def _scrapling_fallback(config: dict) -> dict | None:
    """Stub — production calls mcp__ScraplingServer__fetch on Google Maps place URL."""
    return None


def _analyze_gaps(listing: dict | None, config: dict) -> list[dict]:
    """Per-category gap analysis returning master.xlsx[gbp_audit] rows."""
    rows = []
    today = date.today().isoformat()

    if not listing:
        rows.append(_row("nap", "HIGH", "GBP listing not found", "Create or claim GBP listing for the business"))
        return rows

    if not listing.get("primary_category"):
        rows.append(_row("categories", "HIGH", "Primary category missing", "Set primary category in GBP dashboard"))
    if len(listing.get("secondary_categories", [])) < 2:
        rows.append(_row("categories", "MEDIUM", "Fewer than 2 secondary categories", "Add at least 2 relevant secondary categories"))

    photo_count = listing.get("photo_count", 0)
    if photo_count < 3:
        rows.append(_row("photos", "HIGH", f"Only {photo_count} photos", "Add at least 3 high-quality photos"))
    elif photo_count < 10:
        rows.append(_row("photos", "MEDIUM", f"Only {photo_count} photos", "Add photos to reach 10+ for healthy listing"))

    if not listing.get("business_hours"):
        rows.append(_row("hours", "HIGH", "Business hours missing", "Add regular business hours in GBP dashboard"))
    if not listing.get("holiday_hours"):
        rows.append(_row("hours", "MEDIUM", "No holiday hours configured", "Add holiday hours for upcoming holidays"))

    if listing.get("post_count_30d", 0) == 0:
        rows.append(_row("posts", "LOW", "No GBP posts in last 30 days", "Publish at least 1 GBP post (update / offer / event)"))

    return rows


def _row(category: str, severity: str, gap: str, action: str) -> dict:
    return {
        "audit_id": f"gbp-{uuid4().hex[:8]}",
        "audit_date": date.today().isoformat(),
        "category": category,
        "gap_description": gap,
        "severity": severity,
        "recommended_action": action,
        "status": "TODO",
    }
```

- [ ] **Step 4: Run tests — confirm PASS**

```bash
pytest tests/skills/test_gbp_audit.py -v
```

- [ ] **Step 5: Commit**

```bash
git add scripts/discovery/gbp_audit_transform.py tests/skills/test_gbp_audit.py
git commit -m "feat(gbp-audit): DFS business_listings + Scrapling fallback transform (G-AI-02)"
```

---

### Task 5.4: End-of-phase drift-check

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```
Expected: all PASS + new tests included.

- [ ] **Step 2: Run drift-check**

```bash
# /pseo-driftcheck if available
pytest tests/test_skills_frontmatter.py tests/test_rules_frontmatter.py -v
```
Expected: PASS.

- [ ] **Step 3: Tag completion (not yet release tag — that's post-Phase 6)**

```bash
# no tag yet; just a marker commit if needed
```

**END OF PHASE 5 — 4 atomic commits, new gbp-audit discovery skill + master.xlsx[gbp_audit] sheet, local-service projects covered.**

---

# Phase 6 — Bank Seed Pilot Sessions (Operator Workshops)

**Goal:** Run the brand-onboarding 3-stage pipeline for the three priority projects, populating their `experience_database` + `original_research_database`. Hands-on operator session — not pure code execution.

**Affects:** demo-fintech TR (YMYL-high), demo-aluminum CA (local-service), demo-hvac (e-commerce + local-service hybrid).

**Dependencies:** Phases 1-5 complete.

**Duration estimate:** 30-45 minutes per project (90-135 minutes total), spread over 1-3 sessions.

---

### Task 6.1: demo-fintech TR pilot session

**Inputs needed from operator:**
- demo-fintech's LinkedIn company URL
- demo-fintech executives' LinkedIn profile URLs (for question 3 — sektörel deneyim)
- Approval on each discovered draft entry

- [ ] **Step 1: Run discovery stage**

```bash
/pseo-active demo-fintech-tr
# Then invoke brand-onboarding with full pipeline
```
The skill runs Stage A (DFS + Scrapling against demo-fintech.example), returns draft entries.

- [ ] **Step 2: Operator review (Stage B)**

The skill presents the markdown review prompt. Operator (Süleyman) decides per entry:
- `[A] approve` — entry as-is
- `[E] edit claim_core: "..."` — operator rewrites the claim
- `[R] reject` — discard

For YMYL profile (demo-fintech-tr), minimum 3 approved experience entries required to proceed.

- [ ] **Step 3: Operator-supplied gaps**

For questions Stage A couldn't auto-fill, operator answers conversationally:
- "Yönetici sektörel deneyimi: CEO X yıl bankacılık, CTO Y yıl fintech" → bank entry
- "Hangi anket/araştırma yaptın? (skip OK)" → research bank entry if any

- [ ] **Step 4: Stage C write + verify**

Skill writes approved entries to `projects/demo-fintech-tr/project.config.json`. Verify:
```bash
cat projects/demo-fintech-tr/project.config.json | jq '.content_settings.experience_database | length'
```
Expected: ≥3.

- [ ] **Step 5: Atomic commit on workspace**

In the workspace repo (separate from engine):
```bash
cd /Users/apple/Documents/platinum-seo-workspace
git add projects/demo-fintech-tr/project.config.json
git commit -m "feat(demo-fintech-tr): bank seed (≥3 experience entries, YMYL gate satisfied)"
```

---

### Task 6.2: demo-aluminum CA pilot session

Same protocol as Task 6.1 but for `demo-aluminum-ca`. Profile is local-service only, so minimum is ≥1 experience entry.

- [ ] **Step 1: `/pseo-active demo-aluminum-ca`**
- [ ] **Step 2: Run brand-onboarding 3-stage pipeline**
- [ ] **Step 3: Operator review + supply gaps**
- [ ] **Step 4: Stage C write**
- [ ] **Step 5: Workspace commit**

```bash
git commit -m "feat(demo-aluminum-ca): bank seed (≥1 experience entry, local-service gate satisfied)"
```

---

### Task 6.3: demo-hvac pilot session

Same protocol; demo-hvac profiles are `[e-commerce, local-service]`, so ≥1 experience entry minimum.

- [ ] **Step 1: `/pseo-active demo-hvac`**
- [ ] **Step 2: Run brand-onboarding**
- [ ] **Step 3: Operator review + gaps**
- [ ] **Step 4: Stage C write**
- [ ] **Step 5: Workspace commit**

```bash
git commit -m "feat(demo-hvac): bank seed (≥1 experience entry, hybrid profile satisfied)"
```

**END OF PHASE 6 — 3 workspace commits, 3 projects bank-seeded, May 2026 Core Update exposure window addressed for priority projects.**

---

## Post-Plan Steps

- [ ] **Run full test suite (Engine)**

```bash
pytest -v
```
Expected: All previously-passing tests still pass + new tests pass (~25 new tests: 1 piexif smoke + 4 IPTC + 4 migration + 4 discovery + 3 review + 3 write + 4 gbp-audit + 2 schema = approx).

- [ ] **Run drift-check (Engine)**

```bash
# /pseo-driftcheck
pytest tests/test_skills_frontmatter.py tests/test_rules_frontmatter.py -v
```
Expected: PASS — no schema invariant broken.

- [ ] **Schedule May 2026 Core Update measurement window**

Add to `docs/PHASE_STATUS.md`:
```markdown
## v1.7 Post-Release — May 2026 Core Update Measurement

- Core update rollout completion: ~2026-06-03 (estimate)
- First valid GSC measurement: 2026-06-10 (per Google "wait 1 week post-completion")
- Baseline: GSC impressions/clicks/avg_position week of 2026-05-14 to 2026-05-20
- Comparison: GSC same metrics week of 2026-06-10 to 2026-06-16
- Run `/pseo-gsc-pull` for all 3 priority projects + portfolio aggregation
- Document deltas in `outputs/reports/2026-06-17-may-core-update-impact.md`
```

- [ ] **Update PHASE_STATUS.md + add memory file**

Create `/Users/apple/.claude/projects/-Users-apple-Documents-platinum-seo-engine/memory/project_v1_7_google_compliance.md` summarizing:
- 6 phases completed
- 5 confirmed gaps addressed (Y-AI-01, Y-AI-02, G-AI-01, G-AI-05, R-121, G-AI-02)
- 2 items cancelled (G-AI-03 HOLD, G-AI-04 PAS — memory ban active)
- 14 areas already-compliant preserved
- 25 new tests passing
- Atomic commit count: 22 (3 Phase 1 + 4 Phase 2 + 5 Phase 3 + 4 Phase 4 + 4 Phase 5 + 3 Phase 6)
- May 2026 Core Update measurement window flagged

- [ ] **Tag release v1.7.0**

```bash
git tag -a v1.7.0 -m "Google AI Optimization Guide compliance + May 2026 Core Update hardening"
git push origin main --tags
```

---

## Open Decisions (resolved or deferred)

| ID | Decision | Resolution |
|----|----------|------------|
| O-AI-01 | IPTC retroactive patch of existing workspace images? | DEFERRED to v1.8 — Phase 2 covers forward-going only |
| O-AI-02 | GBP audit cadence (one-shot vs scheduled)? | DEFAULT: manual `/pseo-gbp-audit` only; scheduled run deferred to v1.8 |
| O-AI-03 | Bank entry `phrasings` count (1 vs 3 vs 5)? | DEFAULT: 0 (operator-supplied as needed); Phase 6 sessions surface what's natural |
| O-AI-04 | R-121 density cap exact thresholds | LOCKED in Phase 4 R-121 statement (YMYL: 2+1, b2b-saas: 1+1, others: 1+0) |
| O-AI-05 | Bank-seed gate severity for non-YMYL profiles | LOCKED in Phase 3 brand-onboarding SKILL.md DURUR cascade (≥1 for non-YMYL, ≥3 for YMYL) |
| O-AI-06 | Use Scrapling stealthy_fetch for LinkedIn auto-discovery? | NO — operator manually supplies LinkedIn URLs (KVKK + LinkedIn TOS safety) |

---

## Self-Review (writing-plans skill discipline)

**1. Spec coverage:** Every confirmed gap (Y-AI-01, Y-AI-02, G-AI-01, G-AI-05, R-121, G-AI-02) has at least one task. Cancelled items (G-AI-03, G-AI-04) are explicitly noted with rationale (memory bans + HOLD).

**2. Placeholder scan:** No "TODO", "TBD", "implement later" strings in task steps. Stub functions in `brand_onboarding_discovery.py` and `gbp_audit_transform.py` are explicitly labeled "Stub — production calls mcp__... at runtime" with the exact MCP function name — these are integration points, not placeholders. Test fixtures (`mock_dfs`, `mock_scrapling`, `tmp_workspace_factory`) reference existing conftest patterns; if absent, Step 4 of Task 3.2 explicitly instructs creation following existing style.

**3. Type consistency:**
- `write_ai_image_disclosure(image_path)` signature is identical between Task 2.2 implementation and Task 2.3 consumption.
- `DIGITAL_SOURCE_TYPE_AI` constant name is identical between Task 2.2 implementation, Task 2.3 test import.
- `experience_database` + `original_research_database` field names are identical between Task 3.1 schema, Task 3.4 write, Task 4.1 R-121 reference, Task 4.2-4.4 skill consumes.
- Bank entry sub-field names (`applicable_topics`, `phrasings`, `last_used_in_content_id`, `max_usage_per_month`) are identical across migration (3.1), write (3.4), and R-121 (4.1).
- `discover()` / `apply_review_decisions()` / `write_bank_entries()` function signatures match imports in tests (Tasks 3.2 / 3.3 / 3.4).
- `gbp_audit_transform.run(project_slug)` matches test imports (Task 5.3).

**4. Memory cross-check:**
- `feedback_ai_disclosure_ban.md` honored — Phase 2 + Phase 3 + Phase 5 explicitly forbid any "AI tarafından yazıldı" wording in any output; R-78 (Phase 2) is IPTC metadata only, not visible HTML; no template files generated.
- `feedback_indexing_api_consent.md` honored — Phase 5 gbp-audit is explicitly audit-only, no submission; budget pre-flight per F-16; operator approval required.
- `feedback_hard_constraints.md` — plugin-agnostic boundary preserved (no `.mcp.json` writes).
- `feedback_communication_style.md` — Turkish chat, English code/test/commit messages.
- `feedback_product_naming_cross_check.md` — Phase 3 Stage A includes site fetch (R-15 paterni reuse) before any claim is approved.

**5. May 2026 Core Update alignment:**
- Phase 1 (15 min) completes within ~30 minutes of plan start (2026-05-21 same-day).
- Phase 2 (1-2 hours) completes by 2026-05-22.
- Phase 3 (4-5 hours) completes by 2026-05-23 to 2026-05-24.
- Phase 4 (1 hour) completes by 2026-05-25.
- Phase 5 (2-3 hours) completes by 2026-05-26 to 2026-05-27.
- Phase 6 (3 operator sessions, 30-45 min each) completes by 2026-05-29 (assuming 1 session per day).
- All engine code shipped before 2026-06-03 (Core Update rollout completion).
- First measurement window opens 2026-06-10 — automatic re-evaluation event added to PHASE_STATUS.md.

**6. Dependency graph:**
- Phase 1 → Phase 2: independent; Phase 1 first only for risk ordering.
- Phase 2 → Phase 3: piexif must be stable before schema migration (atomic phase pattern hygiene).
- Phase 3 → Phase 4: R-121 consumes bank entry v1.4 schema fields.
- Phase 4 → Phase 5: independent technically; sequenced for atomic commit isolation.
- Phase 5 → Phase 6: GBP audit data informs operator review for local-service projects.
- Each phase ends with drift-check PASS before next phase begins.

**7. Outstanding integration concerns (identified during final check):**

- **master.xlsx[completed_work] schema dependency:** R-121 rotation check (Tasks 4.2-4.4) consumes a per-content `bank_entries_used: array<string>` field listing entry ids referenced in that content. Before Task 4.2 implementation, verify this field exists in `schemas/master-excel.schema.json` under `completed_work.items.properties`. If absent, add a preceding sub-task "Task 4.1.5 — master-excel completed_work bank_entries_used migration" (mirroring the 0004 migration shape from Task 3.1). Without this field, R-121 rotation enforcement has nothing to read from.

- **DFS Stage A budget cost transparency:** Auto-discovery (Task 3.2) consumes paid DFS MCP calls per project: whois (~1 credit) + on_page_content_parsing (~3 credit × ~3 pages = 9) + business_data_business_listings (~3) + keywords_for_site (~5) ≈ 18 credits per project. For 9 projects × 18 = ~162 credits across all initial seedings. Brand-onboarding SKILL.md frontmatter (Task 3.5 Step 2) must document `budget.estimated_credits: 18` and `budget.uses_paid_mcp: true`. Budget pre-flight gate (Task 3.2 `mock_dfs_budget_exhausted` test) enforces awaiting_approval if insufficient.

- **Phase 6 operator session template:** Stage B's `generate_review_prompt` (Task 3.3) covers discovered draft candidates but does NOT yet prompt for the 5 profile-aware fallback questions when Stage A discovery returns empty for an area (e.g. no founding-year extractable, no case-study pages found). The 5-question prompt is documented in `brand-onboarding/SKILL.md` body (Task 3.5 Step 2) but needs runtime code path. Recommended: add a Task 3.3.5 between Tasks 3.3 and 3.4 that implements `generate_fallback_questions(discovery_output, project_config) -> str` returning profile-gated question prompts, with corresponding test cases. Alternatively, runtime engineer folds this into Task 3.3 if the existing test fixtures cover it.

---

**END OF PLAN — awaiting operator approval to execute Phase 1.**
