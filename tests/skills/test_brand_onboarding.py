"""tests/skills/test_brand_onboarding.py — brand-onboarding meta skill (Phase 12 W-G2).

Coverage (15 cases):
  1.  Frontmatter required 8-field schema validity (skill-frontmatter.schema.json).
  2.  Inputs structure — exactly 3 inputs (project_slug, domain, profile_hint).
  3.  DURUR #1 — Süleyman onay yok → no events.jsonl write contract documented.
  4.  DURUR #2 — project_slug collision/reserved word REJECT documented.
  5.  DURUR #3 — brand_identity / content_settings field skip → AMBER iterate.
  6.  DURUR #4 — profile_hint 6th value REJECT (5-value enum enforce).
  7.  DURUR #5 — workspace yok → STAGING-ONLY mode warning, no project.config.json write.
  8.  DURUR #6 — domain DNS resolve fail → AMBER manual confirm.
  9.  project_slug kebab-case regex enforced (^[a-z][a-z0-9-]*$).
  10. profile enum 5-value full coverage (Principle 2 type-safe).
  11. Domain DNS validation socket.gethostbyname documented (mock-friendly).
  12. brand_identity 18-field + content_settings 14-field full enumeration.
  13. project-config.schema.json v1.5 staging conformance (Draft7Validator).
  14. Plugin agnostik (F-16): .mcp.json byte-hash unchanged after skill creation.
  15. Foundational Principles 3-layer enforce (truth-verifiable + profile-aware
      + AI suistimal yasağı) explicit references.

Discipline:
  - Schema-first override applied: events.schema.json `event_kind=workflow`
    requires workflow_action + workflow_run_id, NOT event_type. Brief's
    `event_type=brand_onboarded` re-routed to `notes` semantic marker
    (Lesson 7+23 worker override).
  - STAGING-ONLY contract: skill never references projects/{slug}/config/
    project.config.json as a write target.
  - .mcp.json byte sentinel pinned at 543 bytes / md5
    93523d41e14f90916fefb86d346bd702 (v1.8: sf MCP server added per ADR-039
    controlled F-16 break; previously 482B / 906183032322a97254579f453705c182
    pinned at v1.1 when npm packages were pinned to semver).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = REPO_ROOT / "skills" / "meta" / "brand-onboarding" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"
MCP_JSON = REPO_ROOT / ".mcp.json"

# Baseline .mcp.json bytes captured at v1.8 Phase 2 (ADR-039 controlled
# F-16 break: sf MCP server added). Pre-v1.8 baseline (W-G2 origin):
# 482B / 906183032322a97254579f453705c182. Any drift from THIS hash means
# the skill — or unrelated plugin work — touched the MCP boundary, which
# the F-16 invariant still forbids outside an ADR-documented change.
MCP_JSON_MD5_BASELINE = "93523d41e14f90916fefb86d346bd702"
MCP_JSON_BYTES_BASELINE = 543


def _parse_frontmatter(skill_path: Path) -> dict:
    text = skill_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise ValueError(f"No YAML frontmatter in {skill_path}")
    return yaml.safe_load(m.group(1))


def _skill_text() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def _md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def project_config_schema() -> dict:
    return json.loads(
        (SCHEMAS / "project-config.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def events_schema() -> dict:
    return json.loads((SCHEMAS / "events.schema.json").read_text("utf-8"))


# ---------------------------------------------------------------------------
# Test 1 — frontmatter schema validity (skill-frontmatter.schema.json)
# ---------------------------------------------------------------------------

def test_frontmatter_schema_valid(skill_frontmatter_schema: dict) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (Draft7) and lock the brief
    contract: name, category, status, triggers, mcp_tools(empty),
    budget(unpaid), autonomy(approval=true, safe_auto=false)."""
    fm = _parse_frontmatter(SKILL_PATH)
    required = ["name", "description", "version", "status", "category",
                "inputs", "outputs", "triggers"]
    for field in required:
        assert field in fm, f"Missing required field: {field}"

    validator = Draft7Validator(skill_frontmatter_schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    assert fm["name"] == "brand-onboarding"
    assert fm["category"] == "meta"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["triggers"]["manual"] == ["/pseo-brand-onboarding"]
    assert fm["mcp_tools"].get("required") in ([], None)
    assert fm["mcp_tools"].get("optional") in ([], None)
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"]["estimated_credits"] == 0
    assert fm["autonomy"]["confidence"] == "HIGH"
    assert fm["autonomy"]["requires_approval"] is True
    assert fm["autonomy"]["safe_auto_execute"] is False


# ---------------------------------------------------------------------------
# Test 2 — inputs structure: exactly 3 inputs per brief
# ---------------------------------------------------------------------------

def test_inputs_structure_three_inputs() -> None:
    """Brief locks 3 inputs: project_slug (required), domain (required),
    profile_hint (optional). Drift from this set breaks the wizard
    contract."""
    fm = _parse_frontmatter(SKILL_PATH)
    inputs = fm["inputs"]
    assert isinstance(inputs, dict), \
        "inputs must be a dict<param, {type, required, ...}> per schema"
    assert set(inputs.keys()) == {"project_slug", "domain", "profile_hint"}, \
        f"inputs drift: got {sorted(inputs.keys())}"

    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True
    assert inputs["domain"]["type"] == "string"
    assert inputs["domain"]["required"] is True
    assert inputs["profile_hint"]["type"] == "string"
    assert inputs["profile_hint"].get("required", False) is False


# ---------------------------------------------------------------------------
# Test 3 — DURUR #1: no approval → no events.jsonl write
# ---------------------------------------------------------------------------

def test_durur_1_no_approval_no_event_write() -> None:
    """DURUR #1 sentinel: when approval_received is false the skill MUST
    NOT append to _state/events.jsonl. This is the gating contract that
    keeps unattended runs idempotent and audit-clean."""
    text = _skill_text()
    assert "DURUR #1" in text and "Süleyman onayı" in text, \
        "DURUR #1 not surfaced in SKILL.md"
    # Events.jsonl gating: phrase is `events.jsonl` (backticked) +
    # "yazılmaz" — accept either the bare or backticked form.
    assert ("yazılmaz" in text and "events.jsonl" in text), \
        "DURUR #1 contract: events.jsonl gating absent"
    # The events block must explicitly note ONLY ON APPROVAL gating.
    assert "ONLY ON APPROVAL" in text, \
        "events.jsonl Step 9 missing ONLY ON APPROVAL gating clause"


# ---------------------------------------------------------------------------
# Test 4 — DURUR #2: project_slug collision / reserved word REJECT
# ---------------------------------------------------------------------------

def test_durur_2_slug_collision_or_reserved() -> None:
    """DURUR #2 sentinel: existing projects/{slug}/ dir or reserved
    word list (admin/system/root/api/www etc.) → REJECT. The skill
    documents both branches."""
    text = _skill_text()
    assert "DURUR #2" in text, "DURUR #2 missing"
    # Reserved word list must enumerate at least admin + system per brief.
    for token in ("admin", "system", "root", "api", "www"):
        assert token in text, f"reserved word `{token}` not enumerated"
    # Collision check phrase.
    assert "projects/{slug}" in text, \
        "DURUR #2 collision check on projects/{slug}/ directory absent"


# ---------------------------------------------------------------------------
# Test 5 — DURUR #3: missing field → AMBER iterate, no auto-fill
# ---------------------------------------------------------------------------

def test_durur_3_missing_field_amber_iterate() -> None:
    """DURUR #3 sentinel: when Süleyman skips a brand_identity or
    content_settings field, the skill must AMBER + prompt yeniden
    iterate. AI suistimal yasağı: the skill MUST NOT auto-fill."""
    text = _skill_text()
    assert "DURUR #3" in text, "DURUR #3 missing"
    assert "AMBER" in text, "AMBER signaling not surfaced"
    assert ("default doldurmaz" in text or "ASLA otomatik doldurmaz" in text), \
        "AI suistimal yasağı: auto-fill ban not declared"


# ---------------------------------------------------------------------------
# Test 6 — DURUR #4: profile_hint 6th value REJECT (5-value enum)
# ---------------------------------------------------------------------------

def test_durur_4_profile_enum_six_value_reject(project_config_schema: dict) -> None:
    """DURUR #4 sentinel: profile enum is type-safe 5-value (Principle 2).
    Any 6th value REJECT. Cross-checks schema authority — the 5 values
    declared in project-config.schema.json must match SKILL.md prose
    exactly."""
    text = _skill_text()
    assert "DURUR #4" in text, "DURUR #4 missing"

    # Schema authority: 5 values, no more, no less.
    profile_decl = project_config_schema["properties"]["profile"]
    assert profile_decl["enum"] == [
        "e-commerce", "ymyl", "local-service", "b2b-saas", "portfolio"
    ], "schema profile enum drifted from 5-value lock"

    # All 5 values must appear in the SKILL prose.
    for v in profile_decl["enum"]:
        assert v in text, f"profile enum value `{v}` missing from SKILL.md"

    # A negative sentinel: a fabricated 6th value MUST NOT appear.
    forbidden_sixth = ["enterprise", "marketplace", "education", "gov"]
    for f in forbidden_sixth:
        # Soft check — these tokens can appear in unrelated prose, but
        # never as a profile enum extension. Concretely, REJECT must be
        # documented for the 6th-value path.
        assert f"\"{f}\"" not in text and f"'{f}'" not in text, \
            f"6th profile candidate `{f}` leaked into SKILL.md as a quoted enum-style token"


# ---------------------------------------------------------------------------
# Test 7 — DURUR #5: workspace yok → STAGING-ONLY (no project.config.json write)
# ---------------------------------------------------------------------------

def test_durur_5_staging_only_mode() -> None:
    """DURUR #5 sentinel: pre-Phase-14 the engine repo has no projects/
    dir. Skill must run in STAGING-ONLY mode, NEVER writing
    projects/{slug}/project.config.json. Staging output goes to
    outputs/onboarding/{slug}-staging-config.json."""
    text = _skill_text()
    assert "DURUR #5" in text, "DURUR #5 missing"
    assert "STAGING-ONLY" in text, "STAGING-ONLY mode banner absent"

    # Staging artifact path is documented.
    assert "outputs/onboarding/{slug}-staging-config.json" in text, \
        "staging output path not documented"

    # Negative sentinel: skill MUST NOT advertise writing the canonical
    # project.config.json path. (The substring CAN appear in DURUR #5
    # narrative, but NOT as an output target. We check the frontmatter
    # outputs[] strictly — that is the machine-readable contract.)
    fm = _parse_frontmatter(SKILL_PATH)
    for out in fm["outputs"]:
        assert "projects/{slug}/project.config.json" not in out, \
            f"frontmatter outputs leaks canonical config path: {out!r}"
        assert "project.config.json" not in out, (
            f"frontmatter outputs writes project.config.json — STAGING-ONLY "
            f"violation: {out!r}"
        )


# ---------------------------------------------------------------------------
# Test 8 — DURUR #6: domain DNS resolve fail → AMBER manual confirm
# ---------------------------------------------------------------------------

def test_durur_6_dns_resolve_fail_amber() -> None:
    """DURUR #6 sentinel: socket.gethostbyname() exception path triggers
    AMBER manual confirm prompt. Süleyman either approves (continue)
    or declines (ABORT). Auto-skip is forbidden."""
    text = _skill_text()
    assert "DURUR #6" in text, "DURUR #6 missing"
    assert ("socket.gethostbyname" in text or "DNS" in text), \
        "DNS resolve mechanism (socket.gethostbyname / DNS) not documented"
    assert "AMBER" in text, "AMBER fallback not declared"
    assert "manual confirm" in text or "manual" in text.lower(), \
        "manual confirm prompt requirement absent"


# ---------------------------------------------------------------------------
# Test 9 — project_slug kebab-case regex (^[a-z][a-z0-9-]*$)
# ---------------------------------------------------------------------------

def test_project_slug_kebab_case_regex(project_config_schema: dict) -> None:
    """The skill's slug regex MUST match project-config.schema.json
    project_id pattern verbatim. Drift between the two breaks
    init-project handoff at Phase 14."""
    text = _skill_text()
    schema_pattern = project_config_schema["properties"]["project_id"]["pattern"]
    assert schema_pattern == "^[a-z][a-z0-9-]*$", (
        "schema project_id pattern drifted; brief lock invalidated"
    )
    assert "^[a-z][a-z0-9-]*$" in text, \
        "SKILL.md does not cite the kebab-case regex; drift risk against schema"

    # Positive cases compile + match.
    rx = re.compile(schema_pattern)
    for good in ("demo-dental", "my-project", "a", "b2b-saas-pilot"):
        assert rx.match(good), f"slug `{good}` should be valid"
    # Negative cases — the schema regex is intentionally lax on a
    # trailing dash; the SKILL's reserved-word + collision logic catches
    # those at runtime. We test only what the regex itself rejects.
    for bad in ("My-Project", "1startswith-digit", "bad slug", "snake_case"):
        assert not rx.match(bad), f"slug `{bad}` should be invalid"


# ---------------------------------------------------------------------------
# Test 10 — profile enum 5-value full coverage (Principle 2)
# ---------------------------------------------------------------------------

def test_profile_enum_principle_2_five_value(project_config_schema: dict) -> None:
    """Foundational Principle 2 (profile-aware) anchors on the 5-value
    enum. The skill must enumerate all 5 in its body for downstream
    heuristic mapping; missing any value breaks the wizard's
    suggest path."""
    text = _skill_text()
    enum_values = project_config_schema["properties"]["profile"]["enum"]
    assert len(enum_values) == 5
    for v in enum_values:
        assert v in text, f"profile enum `{v}` missing from SKILL.md prose"

    # Principle 2 by name must appear (truth-verifiable cross-reference).
    assert "Principle 2" in text or "profile-aware" in text, \
        "Principle 2 (profile-aware) not anchored in SKILL.md"


# ---------------------------------------------------------------------------
# Test 11 — domain DNS validation via socket.gethostbyname (mock-friendly)
# ---------------------------------------------------------------------------

def test_domain_dns_validation_socket_documented() -> None:
    """Step 2 DNS sanity uses Python stdlib `socket.gethostbyname` so
    the wizard runs without external deps. Tests using monkeypatch can
    swap the resolver. Verify the SKILL prose calls out the exact
    stdlib symbol (not a vendored DNS lib)."""
    text = _skill_text()
    assert "socket.gethostbyname" in text, (
        "SKILL.md must cite socket.gethostbyname (stdlib) for DNS sanity; "
        "no third-party DNS dep allowed"
    )
    # The exception path MUST flow into DURUR #6 (AMBER manual confirm).
    assert ("DNS resolve fail" in text) and ("DURUR #6" in text), \
        "DNS fail → DURUR #6 link missing"

    # Soft mock-style sanity: monkeypatch can replace gethostbyname; we
    # simulate one call here purely to assert the stdlib symbol exists.
    import socket
    assert callable(socket.gethostbyname)


# ---------------------------------------------------------------------------
# Test 12 — brand_identity 18 + content_settings 14 full enumeration
# ---------------------------------------------------------------------------

def test_brand_identity_18_and_content_settings_14_enumerated(
    project_config_schema: dict,
) -> None:
    """The wizard must surface every brand_identity property (20 after
    ADR-030 v1.3 added pronoun_preference + formality canonical) and
    every content_settings property (14) so Süleyman is prompted for
    each. Counting drift here is a direct schema invariant violation."""
    text = _skill_text()

    bi_props = project_config_schema["properties"]["brand_identity"]["properties"]
    cs_props = project_config_schema["properties"]["content_settings"]["properties"]
    assert len(bi_props) == 20, (
        f"brand_identity drifted from 20 fields (18 + ADR-030 v1.3 "
        f"pronoun_preference/formality): got {len(bi_props)}"
    )
    assert len(cs_props) == 14, (
        f"content_settings drifted from 14 fields: got {len(cs_props)}"
    )

    # Every brand_identity property must appear in the SKILL.md prose.
    for prop in bi_props:
        assert prop in text, (
            f"brand_identity field `{prop}` not enumerated in Step 4 prompt list"
        )
    # Every content_settings property must appear too.
    for prop in cs_props:
        assert prop in text, (
            f"content_settings field `{prop}` not enumerated in Step 5 prompt list"
        )


# ---------------------------------------------------------------------------
# Test 13 — staging output is project-config.schema.json v1.5 conformant
# ---------------------------------------------------------------------------

def test_staging_output_schema_conformance(
    project_config_schema: dict, tmp_path: Path,
) -> None:
    """Build a representative staging artifact in-memory, validate it
    against project-config.schema.json v1.5 (Draft7). This locks the
    contract that outputs/onboarding/{slug}-staging-config.json
    candidates the skill emits round-trip cleanly into init-project at
    Phase 14."""
    # schema v1.5 is asserted by the const constraint (v1.8 Phase 1 D-SF-12
    # sf block additive; Phase 3 G-AI-05 bank entry enrichment retained;
    # ADR-030 brand_identity rename remained).
    assert project_config_schema["properties"]["schema_version"]["const"] == "1.5"

    # Minimal-required staging artifact derived from schema.required.
    staging = {
        "schema_version": "1.5",
        "project_id": "demo-dental",
        "domain": "https://example.com/",
        "market": "TR",
        "language": {"content_locale": "tr-TR"},
        "currency": "TRY",
        "platform": "wordpress",
        "profiles": ["local-service"],
        "paths": {
            "workspace_root": "projects/demo-dental",
            "excel_filename": "master.xlsx",
            "sf_exports_dir": "sf_exports",
            "staging_dir": "staging",
            "reports_dir": "reports",
            "blog_dir": "blog",
            "backups_dir": "backups",
        },
        "gsc": {"site_url": "https://example.com/"},
        "dataforseo": {"location_code": 2792, "language_code": "tr"},
        # v1.2 additive — singular profile (Principle 2).
        "profile": "local-service",
        # brand_identity additive (subset, all optional).
        "brand_identity": {
            "primary_color": "#112233",
            "tone": "semi-pro",
            "hitap": "siz",
        },
        # content_settings additive (subset, all optional).
        "content_settings": {
            "toc_strategy": "static",
            "indexnow_enabled": True,
            "image_model": "nano-banana",
        },
    }
    validator = Draft7Validator(project_config_schema)
    errors = sorted(validator.iter_errors(staging), key=lambda e: list(e.absolute_path))
    assert not errors, "; ".join(
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in errors
    )

    # Negative — 6th profile value MUST fail.
    staging_bad = {**staging, "profile": "enterprise"}
    bad_errors = list(validator.iter_errors(staging_bad))
    assert bad_errors, (
        "schema accepted out-of-enum profile 'enterprise' — Principle 2 "
        "type-safe lock broken"
    )

    # Persist round-trip the way Step 7 would.
    out_dir = tmp_path / "outputs" / "onboarding"
    out_dir.mkdir(parents=True)
    out_path = out_dir / "demo-dental-staging-config.json"
    out_path.write_text(
        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    re_read = json.loads(out_path.read_text("utf-8"))
    assert re_read == staging


# ---------------------------------------------------------------------------
# Test 14 — Plugin agnostik (F-16): .mcp.json byte-hash unchanged
# ---------------------------------------------------------------------------

def test_plugin_agnostik_mcp_json_unchanged() -> None:
    """F-16 invariant: brand-onboarding declares NO MCP tools and MUST
    NOT have caused .mcp.json drift during creation. The hash baseline
    is captured at SKILL creation time; any later edit to .mcp.json
    must be intentional and re-baseline this constant explicitly."""
    assert MCP_JSON.exists(), ".mcp.json missing — repo state corrupted"
    actual_md5 = _md5(MCP_JSON)
    actual_size = MCP_JSON.stat().st_size
    assert actual_md5 == MCP_JSON_MD5_BASELINE, (
        f"F-16 violation: .mcp.json md5 drift "
        f"(baseline={MCP_JSON_MD5_BASELINE}, now={actual_md5})"
    )
    assert actual_size == MCP_JSON_BYTES_BASELINE, (
        f"F-16 violation: .mcp.json size drift "
        f"(baseline={MCP_JSON_BYTES_BASELINE}, now={actual_size})"
    )

    # Frontmatter contract: required + optional MCP arrays empty.
    fm = _parse_frontmatter(SKILL_PATH)
    assert fm["mcp_tools"].get("required", []) == []
    assert fm["mcp_tools"].get("optional", []) == []


# ---------------------------------------------------------------------------
# Test 15 — Foundational Principles 3-layer enforce
# ---------------------------------------------------------------------------

def test_foundational_principles_three_layer(events_schema: dict) -> None:
    """All three Foundational Principles must be invoked by name in the
    SKILL body:
      - truth-verifiable (Principle 1, R-27): Süleyman cevapları
        events.jsonl payload'una düşer (notes field; schema-first
        override over brief's event_type=brand_onboarded).
      - profile-aware (Principle 2): 5-value enum + heuristic suggest.
      - AI suistimal yasağı: skill kendi kafasından alan doldurmaz.
    Also asserts the schema-first override is documented in-band."""
    text = _skill_text()

    # Layer 1 — truth-verifiable / Principle 1 / R-27.
    assert ("Truth-verifiable" in text or "truth-verifiable" in text), \
        "Principle 1 truth-verifiable not anchored"
    assert "Principle 1" in text, "Principle 1 not named"
    assert "R-27" in text, "R-27 reference missing"

    # Layer 2 — profile-aware / Principle 2.
    assert "Principle 2" in text, "Principle 2 not named"
    assert "profile-aware" in text, "profile-aware phrase missing"

    # Layer 3 — AI suistimal yasağı.
    assert "AI suistimal" in text, "AI suistimal yasağı not declared"

    # Schema-first override (Lesson 7+23) — events.schema discipline.
    assert "Schema-first override" in text, \
        "schema-first override (Lesson 7+23) not surfaced"
    # The override target — workflow_action + workflow_run_id — must be
    # present in the prose.
    assert "workflow_action" in text, "workflow_action override target missing"
    assert "workflow_run_id" in text, "workflow_run_id override target missing"

    # And the events.schema authority MUST list workflow event_kind.
    assert "workflow" in events_schema["properties"]["event_kind"]["enum"], (
        "events.schema event_kind enum dropped 'workflow' — ADR-020 broken"
    )
    # workflow_action enum must be the closed 8-value lifecycle list (sanity).
    wa = events_schema["properties"]["workflow_action"]["enum"]
    assert set(wa) >= {"started", "done", "approved", "rejected", "failed"}, (
        f"workflow_action enum drifted from ADR-020 lifecycle: {wa}"
    )
