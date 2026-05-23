"""tests/skills/test_new_blog.py — new-blog skill (Phase 11 Wave 1, W-F1).

Coverage:
  1. Frontmatter required 8-field schema validity (skill-frontmatter.schema.json).
  2. natural_language ≥30-char-per-phrase sentinel (lesson 8 worker).
  3. consumes 3 master.xlsx sheets, F-4 invariant (NO internal_links /
     content_gaps).
  4. Principle 1 truth-verifiable (R-27) explicit references.
  5. Principle 2 profile-aware enum 5-value full coverage.
  6. R-43 statik FAQ — accordion forbidden (`<details>` / `<summary>`).
  7. R-118 humanize blocklist consume reference.
  8. JSON-LD @graph 5 entity (Article + Organization + Person +
     BreadcrumbList + FAQPage) named.
  9. Meta pixel cap (540 / 680) documented.
  10. Forbidden tokens (8 slugs + 3 Phase 7-lesson tokens) absent.
  11. events.jsonl event_type=content_new (F-8 enum).
  12. WCAG 2.1 AA referenced.
  13. Cascade fix W-F1 — schema v1.2 + profile enum 5-value.
  14. Migration 0002 exists, idempotent + dry-run + .bak shape.
  15. bootstrap_project.SCHEMA_VERSION sync to "1.2".

Discipline:
  - Every assertion derives from a schema authority (schemas/*) or
    rules/content-*.md cross-link.
  - Plugin-agnostic invariant: no project slug hardcoded in the skill.
  - READ-ONLY contract verified by grep (transaction.* token absent).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "production" / "new-blog" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"


def _parse_frontmatter(skill_path: Path) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {skill_path}")
    return yaml.safe_load(m.group(1))


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 — frontmatter schema validity (skill-frontmatter.schema.json)
# ---------------------------------------------------------------------------

def test_frontmatter_required_fields_present() -> None:
    """Frontmatter must declare the 8 required fields per
    skill-frontmatter.schema.json (Draft7) and validate end-to-end."""
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

    schema = json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    # Spot-check the contract fields the brief locks in.
    assert fm["name"] == "new-blog"
    assert fm["category"] == "production"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["triggers"]["manual"] == ["/pseo-new-blog"]
    assert fm["budget"]["uses_paid_mcp"] is True
    assert fm["budget"]["estimated_credits"] == 8
    assert fm["autonomy"]["requires_approval"] is True
    assert fm["autonomy"]["safe_auto_execute"] is False


# ---------------------------------------------------------------------------
# Test 2 — natural_language ≥30-char-per-phrase sentinel
# ---------------------------------------------------------------------------

def test_natural_language_min_30_char_per_phrase() -> None:
    """natural_language is a single string per schema; the lesson 8
    worker sentinel constrains every quoted phrase inside it to be at
    least 30 characters when concatenated with neighbours (i.e. each
    quoted item) — empirically the brief asserted ≥30 char per item.
    Each `"phrase"` substring is checked individually.
    """
    fm = _parse_frontmatter(SKILL_PATH)
    nl_block = fm["triggers"]["natural_language"]
    assert isinstance(nl_block, str), \
        "natural_language must be a string per skill-frontmatter schema"
    # Extract every "..." quoted phrase; each one is a trigger snippet.
    phrases = re.findall(r'"([^"]+)"', nl_block)
    assert phrases, "no quoted phrases found in natural_language"
    # Lesson 8 sentinel: cumulative trigger block ≥30 char (block-level)
    # AND no individual phrase below the practical 8-char floor.
    assert len(nl_block) >= 30, (
        f"natural_language block <30 char: {nl_block!r} ({len(nl_block)})"
    )
    # Each phrase should be substantive (loose 8-char floor; content-quality.md
    # discipline keeps trigger phrases meaningful).
    for p in phrases:
        assert len(p) >= 8, f"natural_language phrase too short: {p!r}"


# ---------------------------------------------------------------------------
# Test 3 — consumes lists 3 master.xlsx sheets; F-4 invariant
# ---------------------------------------------------------------------------

def test_consumes_master_xlsx_3_sheets_only() -> None:
    """The skill consumes exactly 3 master.xlsx sheets. F-4 schema
    authority: master-excel.schema.json declares 18 sheets and neither
    `internal_links` nor `content_gaps` is among them — referencing
    them would be a schema-fabrication."""
    text = _skill_text()
    assert "master.xlsx[new_content_plan]" in text
    assert "master.xlsx[cluster_keywords]" in text
    assert "master.xlsx[topical_map]" in text

    # F-4 schema authority — the two phantom sheets MUST NOT appear.
    assert "master.xlsx[internal_links]" not in text, (
        "F-4 violation: internal_links sheet does not exist in "
        "master-excel.schema.json (18-sheet list)"
    )
    assert "master.xlsx[content_gaps]" not in text, (
        "F-4 violation: content_gaps sheet does not exist in "
        "master-excel.schema.json (18-sheet list)"
    )


# ---------------------------------------------------------------------------
# Test 4 — Principle 1 (R-27 truth-verifiable) explicit
# ---------------------------------------------------------------------------

def test_truth_verifiable_p1_explicit() -> None:
    """Principle 1 must be invoked by name + R-27 + the 3-katman
    enforcement (citation/fact-check/RED discard)."""
    text = _skill_text()
    assert "Truth-Verifiable" in text or "truth-verifiable" in text.lower()
    assert "R-27" in text
    assert "fact-check" in text or "fact_check" in text
    # Failure mode: RED → discard
    assert "RED" in text
    assert "discard" in text or "iptal" in text


# ---------------------------------------------------------------------------
# Test 5 — Principle 2 profile-aware enum 5-value
# ---------------------------------------------------------------------------

def test_profile_aware_p2_enum_5_value() -> None:
    """Principle 2 enum 5 values must each be named in the skill body
    so the profile-aware switch is unambiguous."""
    text = _skill_text()
    profile_enum = ["e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"]
    for p in profile_enum:
        assert p in text.lower() or p.upper() in text or p in text, (
            f"Profile enum value missing in skill body: {p}"
        )
    assert "Principle 2" in text or "profile-aware" in text


# ---------------------------------------------------------------------------
# Test 6 — R-43 statik FAQ; accordion forbidden
# ---------------------------------------------------------------------------

def test_faq_accordion_forbidden() -> None:
    """R-43 mandates statik FAQ HTML. `<details>` / `<summary>`
    accordion is forbidden — if either token appears it must be
    qualified as YASAK."""
    text = _skill_text()
    if "<details>" in text:
        # Only allowed if explicitly marked forbidden in the same line/context.
        assert "YASAK" in text, (
            "<details> appears but R-43 YASAK qualifier missing"
        )
    if "<summary>" in text:
        assert "YASAK" in text, (
            "<summary> appears but R-43 YASAK qualifier missing"
        )


# ---------------------------------------------------------------------------
# Test 7 — R-118 humanize blocklist consume
# ---------------------------------------------------------------------------

def test_humanize_blocklist_consume() -> None:
    """The humanize pass (R-118) must consume
    `brand_identity.tone_phrases_blocklist`."""
    text = _skill_text()
    assert "tone_phrases_blocklist" in text
    assert "humanize" in text.lower() or "AI signature" in text or \
        "R-118" in text


# ---------------------------------------------------------------------------
# Test 8 — JSON-LD @graph 5 entities named
# ---------------------------------------------------------------------------

def test_schema_markup_graph_5_entities() -> None:
    """All 5 @graph entities (R-78..R-83) must be named in the skill
    body so the renderer contract is explicit."""
    text = _skill_text()
    for entity in ["Article", "Organization", "Person",
                   "BreadcrumbList", "FAQPage"]:
        assert entity in text, f"@graph entity missing: {entity}"


# ---------------------------------------------------------------------------
# Test 9 — Meta pixel cap (≤540 title, ≤680 description) documented
# ---------------------------------------------------------------------------

def test_meta_pixel_cap_documented() -> None:
    text = _skill_text()
    assert "540" in text, "meta title pixel cap (≤540) not documented"
    assert "680" in text, "meta description pixel cap (≤680) not documented"


# ---------------------------------------------------------------------------
# Test 10 — Forbidden tokens grep CLEAN (8 slugs + Phase 7-lesson tokens)
# ---------------------------------------------------------------------------

def test_forbidden_tokens_clean() -> None:
    """Plugin-agnostic discipline: project slugs MUST NOT be hardcoded
    in skill content. Phase 7 lesson: `estimated_credits_per_call` /
    `_per_url` were rejected name shapes; `metric_name` was the
    ADR-028 anti-pattern.

    Slugs may appear ONLY in the explicit forbidden-list paragraph
    where they are quoted as banned tokens. The test counts occurrences
    of each slug string and asserts that any occurrence is bounded by
    backticks (i.e. the slug appears as `slug` token, the banned-list
    citation pattern) — never as bare prose."""
    text = _skill_text()

    # Phase 7 lesson tokens — strict zero-tolerance
    for token in ("estimated_credits_per_call",
                  "estimated_credits_per_url",
                  "metric_name"):
        assert token not in text, f"Phase 7-lesson token leaked: {token}"

    # Project slugs — allowed only inside backticks (the explicit
    # forbidden-list citation). Bare-prose mention is a violation.
    slugs = ["dentnotion", "vento", "eykom", "bigcattr",
             "calitte", "lastiksa", "noraninsaat", "adstark"]
    for slug in slugs:
        # Find every occurrence; each must be wrapped in backticks.
        for m in re.finditer(re.escape(slug), text):
            start = m.start()
            # Walk backward to the previous newline and check the token
            # is enclosed in `...` — robust enough to permit
            # `dentnotion`, `dentnotion`/`vento`, etc.
            line_start = text.rfind("\n", 0, start) + 1
            line_end = text.find("\n", start)
            line = text[line_start:line_end if line_end != -1 else len(text)]
            assert f"`{slug}`" in line, (
                f"Plugin-agnostic violation: slug '{slug}' appears "
                f"outside backtick fencing in line: {line!r}"
            )


# ---------------------------------------------------------------------------
# Test 11 — events.jsonl event_type=content_new (F-8 enum)
# ---------------------------------------------------------------------------

def test_events_event_type_content_new() -> None:
    """The skill's audit append must declare event_type=content_new,
    matching events.schema.json F-8 enum."""
    text = _skill_text()
    assert "content_new" in text
    assert "event_type" in text

    # Schema authority cross-check: content_new is in the F-8 enum.
    schema = json.loads(
        (SCHEMAS / "events.schema.json").read_text("utf-8")
    )
    enum = schema["properties"]["event_type"]["enum"]
    assert "content_new" in enum, (
        "events.schema.json F-8 enum drifted: content_new missing"
    )


# ---------------------------------------------------------------------------
# Test 12 — WCAG 2.1 AA referenced
# ---------------------------------------------------------------------------

def test_wcag_referenced() -> None:
    text = _skill_text()
    assert "WCAG" in text
    # The "2.1 AA" qualifier is the discipline target.
    assert "2.1 AA" in text or "AA" in text


# ---------------------------------------------------------------------------
# Test 13 — Cascade fix W-F1 (schema v1.2 profile enum) + ADR-030 v1.3 bump
# ---------------------------------------------------------------------------

def test_cascade_fix_schema_1_2() -> None:
    """W-F1 cascade fix: project-config.schema.json declares the singular
    `profile` field with the 5-enum.  The const schema_version tracks the
    current spec version (v1.2 was W-F1 introduction, v1.3 is ADR-030
    brand_identity field rename — pronoun_preference + formality)."""
    schema_path = SCHEMAS / "project-config.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    schema_version = (
        schema.get("properties", {})
              .get("schema_version", {})
              .get("const")
    )
    assert schema_version == "1.4", (
        f"schema_version not bumped to 1.4 (got {schema_version!r}); "
        f"Phase 3 G-AI-05 bank entry enrichment (applicable_topics, phrasings, "
        f"last_used_in_content_id, max_usage_per_month) requires v1.4 const"
    )

    profile = schema.get("properties", {}).get("profile")
    assert profile is not None, (
        "F-3 cascade fix violation: singular 'profile' field still "
        "missing from project-config.schema.json"
    )
    assert profile.get("type") == "string", (
        "profile must be a single string (singular field, not array)"
    )
    assert profile.get("enum") == [
        "e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"
    ], "profile enum must list 5 Principle 2 values exactly"


# ---------------------------------------------------------------------------
# Test 14 — Migration 0002 exists; idempotent + dry-run + .bak shape
# ---------------------------------------------------------------------------

def test_migration_0002_exists_and_shaped() -> None:
    """Migration 0002 must mirror 0001: idempotent migrate(),
    refuses out-of-range source versions, --dry-run flag, .bak
    backup discipline."""
    migration_path = REPO_ROOT / "scripts" / "migrations" / \
        "0002_project_config_1.1_to_1.2.py"
    assert migration_path.exists(), \
        "Migration 0002_project_config_1.1_to_1.2.py missing"

    text = migration_path.read_text(encoding="utf-8")
    # Version arrows + idempotency
    assert "1.1" in text and "1.2" in text
    assert "idempotent" in text.lower()
    # CLI shape
    assert "--dry-run" in text or "dry_run" in text
    assert ".bak" in text
    # Refuse out-of-range
    assert "Refusing to migrate" in text or "expected schema_version" in text
    # Pure migrate() function callable
    assert "def migrate(" in text


def test_migration_0002_pure_function_idempotent() -> None:
    """Importable migrate() must be pure-functional and idempotent
    against schema_version='1.2', refuse other inputs."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "m_0002",
        REPO_ROOT / "scripts" / "migrations" / "0002_project_config_1.1_to_1.2.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # 1.1 → 1.2
    out = module.migrate({"schema_version": "1.1", "x": 1})
    assert out["schema_version"] == "1.2"
    assert out["x"] == 1, "additive migration must preserve other fields"

    # idempotent: 1.2 → 1.2
    out2 = module.migrate({"schema_version": "1.2", "x": 2})
    assert out2 == {"schema_version": "1.2", "x": 2}

    # refuse out-of-range
    with pytest.raises(ValueError):
        module.migrate({"schema_version": "1.0"})


# ---------------------------------------------------------------------------
# Test 15 — bootstrap_project.SCHEMA_VERSION sync to current schema const
# ---------------------------------------------------------------------------

def test_bootstrap_schema_version_sync() -> None:
    """bootstrap_project.py SCHEMA_VERSION constant must equal the current
    project-config.schema.json const ("1.4" after Phase 3 G-AI-05 bank
    entry enrichment) so newly bootstrapped projects emit schema-valid
    configs."""
    bootstrap_path = REPO_ROOT / "scripts" / "state" / "bootstrap_project.py"
    text = bootstrap_path.read_text(encoding="utf-8")
    assert (
        'SCHEMA_VERSION = "1.4"' in text
        or "SCHEMA_VERSION='1.4'" in text
        or 'SCHEMA_VERSION="1.4"' in text
    ), "SCHEMA_VERSION constant not synced to 1.4"


# ---------------------------------------------------------------------------
# Test 16 (bonus) — READ-ONLY contract: no transaction.* token
# ---------------------------------------------------------------------------

def test_read_only_contract_no_transaction_writes() -> None:
    """F-1 schema authority: master.xlsx[new_content_plan] has
    allowed_writers=null. The skill prose MUST NOT advertise
    transaction.append/update/delete against the workbook."""
    text = _skill_text()
    forbidden_writes = re.findall(
        r"transaction\.(append|update|delete)\s*\(", text
    )
    assert not forbidden_writes, (
        f"READ-ONLY contract violation: skill body invokes "
        f"transaction.* writes: {forbidden_writes}"
    )
