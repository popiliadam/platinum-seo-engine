"""
tests/skills/test_scrapling_ops.py — scrapling-ops generic helper tests.

Mirrors tests/skills/test_quick_wins.py patterns. MCP tools are not
Python-callable inside pytest, so all tests inject fake callables
into the helper's `mcp_clients` / `bulk_clients` parameters; this is
the same dependency-injection seam the skill orchestrator uses at
runtime, so the tests cover the production code path.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json
  - schemas/scrapling-output-mapping.schema.json (§14.5 tier sequence)
  - schemas/events.schema.json (source.kind=scrapling_mcp,
    target_excel_sheet=null)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.ingestion import scrapling_ops


# ---------------------------------------------------------------------------
# Constants — paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = REPO_ROOT / "skills" / "ingestion" / "scrapling-ops" / "SKILL.md"
SCHEMAS = REPO_ROOT / "schemas"


# ---------------------------------------------------------------------------
# Fake MCP client factory
# ---------------------------------------------------------------------------

def _make_client(
    *,
    succeed: bool,
    content: str = "<html>ok</html>",
    error: str = "blocked",
    status: int | None = None,
) -> Callable[..., Any]:
    """Build a single-URL MCP client callable that returns a dict-shape
    response matching what `_normalize_response` accepts."""
    def _fn(**kwargs: Any) -> dict[str, Any]:
        if succeed:
            return {"content": content, "status": 200}
        return {"error": error, "status": status or 403}
    return _fn


def _make_bulk_client(
    *,
    succeed: bool,
    content: str = "<html>bulk-ok</html>",
    error: str = "bulk-blocked",
) -> Callable[..., Any]:
    """Build a bulk MCP client callable; returns a dict {url: response}."""
    def _fn(**kwargs: Any) -> dict[str, Any]:
        urls = kwargs.get("urls") or []
        if succeed:
            return {u: {"content": content, "status": 200} for u in urls}
        return {u: {"error": error, "status": 403} for u in urls}
    return _fn


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads((SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8"))


@pytest.fixture(scope="module")
def scrapling_schema() -> dict:
    return json.loads(
        (SCHEMAS / "scrapling-output-mapping.schema.json").read_text("utf-8")
    )


def _parse_skill_frontmatter(skill_md_path: Path) -> dict:
    """Extract YAML frontmatter from a SKILL.md file (between --- markers)."""
    text = skill_md_path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert m is not None, f"no YAML frontmatter found in {skill_md_path}"
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------------------
# Test (a) — Frontmatter parses + validates against schema
# ---------------------------------------------------------------------------

def test_skill_frontmatter_validates(skill_frontmatter_schema: dict) -> None:
    """SKILL.md frontmatter must validate against
    schemas/skill-frontmatter.schema.json (category enum 8-value, must
    include 'ingestion' for this skill)."""
    assert SKILL_MD.exists(), f"missing {SKILL_MD}"
    fm = _parse_skill_frontmatter(SKILL_MD)

    # Spot-checks before schema-level validation.
    assert fm["name"] == "scrapling-ops"
    assert fm["category"] == "ingestion"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["inputs"]["project_slug"]["required"] is True
    assert fm["inputs"]["urls"]["required"] is True
    assert fm["inputs"]["scenario"]["default"] == "generic"
    assert fm["inputs"]["max_urls"]["default"] == 50

    required_tools = set(fm["mcp_tools"]["required"])
    assert "mcp__ScraplingServer__fetch" in required_tools
    assert "mcp__ScraplingServer__bulk_fetch" in required_tools
    assert "mcp__ScraplingServer__stealthy_fetch" in required_tools
    assert "mcp__ScraplingServer__bulk_stealthy_fetch" in required_tools

    # Schema validation — aggregates every error so the failure message is
    # actionable.
    validator = Draft7Validator(skill_frontmatter_schema)
    errors = sorted(validator.iter_errors(fm), key=lambda e: e.path)
    assert not errors, [
        (list(e.absolute_path), e.message) for e in errors
    ]


# ---------------------------------------------------------------------------
# Test (a.2) — Tier ladder constant matches §14.5 schema const
# ---------------------------------------------------------------------------

def test_tier_ladder_matches_schema(scrapling_schema: dict) -> None:
    """`TIER_LADDER` must equal the schema's `tierEscalation.const`
    (`['get', 'fetch', 'stealthy_fetch']`)."""
    const_seq = scrapling_schema["definitions"]["tierEscalation"]["const"]
    assert tuple(const_seq) == scrapling_ops.TIER_LADDER
    assert scrapling_ops.TIER_LADDER == ("get", "fetch", "stealthy_fetch")


# ---------------------------------------------------------------------------
# Test (b) — Tier escalation: success at tier 0 (no escalation)
# ---------------------------------------------------------------------------

def test_tier_escalate_succeeds_at_get() -> None:
    """When `get` returns successfully, neither `fetch` nor
    `stealthy_fetch` is invoked."""
    fetch_calls: list[str] = []
    stealthy_calls: list[str] = []

    def _fetch(**kwargs: Any) -> dict[str, Any]:
        fetch_calls.append(kwargs["url"])
        return {"content": "<html>fetch</html>"}

    def _stealthy(**kwargs: Any) -> dict[str, Any]:
        stealthy_calls.append(kwargs["url"])
        return {"content": "<html>stealthy</html>"}

    clients = {
        "get": _make_client(succeed=True, content="<html>tier0</html>"),
        "fetch": _fetch,
        "stealthy_fetch": _stealthy,
    }
    tier, content, meta = scrapling_ops.tier_escalate(
        "https://example.com/", clients,
    )
    assert tier == "get"
    assert content == "<html>tier0</html>"
    assert fetch_calls == []
    assert stealthy_calls == []
    assert meta["attempts"][0]["tier"] == "get"
    assert meta["attempts"][0]["success"] is True


# ---------------------------------------------------------------------------
# Test (c) — Tier 0 fails → tier 1 (fetch) succeeds
# ---------------------------------------------------------------------------

def test_tier_escalate_falls_through_to_fetch() -> None:
    stealthy_calls: list[str] = []

    def _stealthy(**kwargs: Any) -> dict[str, Any]:
        stealthy_calls.append(kwargs["url"])
        return {"content": "stealthy"}

    clients = {
        "get": _make_client(succeed=False, error="403 forbidden", status=403),
        "fetch": _make_client(succeed=True, content="<html>fetch-ok</html>"),
        "stealthy_fetch": _stealthy,
    }
    tier, content, meta = scrapling_ops.tier_escalate(
        "https://example.com/", clients,
    )
    assert tier == "fetch"
    assert content == "<html>fetch-ok</html>"
    assert stealthy_calls == [], "tier 2 must NOT run when tier 1 succeeds"
    # Two attempts recorded: failed get, successful fetch.
    assert [a["tier"] for a in meta["attempts"]] == ["get", "fetch"]
    assert meta["attempts"][0]["success"] is False
    assert meta["attempts"][1]["success"] is True


# ---------------------------------------------------------------------------
# Test (d) — Tier 0+1 fail → tier 2 (stealthy_fetch) succeeds
# ---------------------------------------------------------------------------

def test_tier_escalate_uses_stealthy_when_fetch_blocked() -> None:
    clients = {
        "get": _make_client(succeed=False, error="403"),
        "fetch": _make_client(succeed=False, error="cloudflare-challenge"),
        "stealthy_fetch": _make_client(
            succeed=True, content="<html>stealthy-ok</html>",
        ),
    }
    tier, content, meta = scrapling_ops.tier_escalate(
        "https://example.com/", clients,
    )
    assert tier == "stealthy_fetch"
    assert content == "<html>stealthy-ok</html>"
    assert [a["tier"] for a in meta["attempts"]] == [
        "get", "fetch", "stealthy_fetch",
    ]
    assert [a["success"] for a in meta["attempts"]] == [False, False, True]


# ---------------------------------------------------------------------------
# Test (e) — All 3 tiers fail → DURUR (raise_on_all_fail=True)
#                                   OR tier_used=None (default)
# ---------------------------------------------------------------------------

def test_tier_escalate_all_fail_raises() -> None:
    clients = {
        "get": _make_client(succeed=False, error="403"),
        "fetch": _make_client(succeed=False, error="cloudflare"),
        "stealthy_fetch": _make_client(succeed=False, error="captcha"),
    }
    with pytest.raises(scrapling_ops.TierEscalationError) as ei:
        scrapling_ops.tier_escalate(
            "https://example.com/", clients, raise_on_all_fail=True,
        )
    err = ei.value
    assert err.url == "https://example.com/"
    assert set(err.errors.keys()) == {"get", "fetch", "stealthy_fetch"}
    # Default mode: NO raise; returns None tuple with errors recorded.
    tier, content, meta = scrapling_ops.tier_escalate(
        "https://example.com/", clients,
    )
    assert tier is None
    assert content is None
    assert set(meta["errors"].keys()) == {"get", "fetch", "stealthy_fetch"}


# ---------------------------------------------------------------------------
# Test (f) — Staging JSON shape conforms to STAGING_COLUMNS
# ---------------------------------------------------------------------------

def test_staging_table_shape(tmp_path: Path) -> None:
    """build_staging_rows + staging_table_dict produce the required SQLite-
    shaped JSON: rows array of dicts with exactly STAGING_COLUMNS keys."""
    # Two URLs: one success at fetch, one all-fail.
    results = [
        ("https://ok.example.com/",
         "fetch", "<html>ok</html>",
         {"attempts": [], "tier_meta": {}}),
        ("https://bad.example.com/",
         None, None,
         {"attempts": [], "errors": {"get": "403", "fetch": "cf",
                                      "stealthy_fetch": "captcha"}}),
    ]
    rows = scrapling_ops.build_staging_rows(results, scenario="generic")
    payload = scrapling_ops.staging_table_dict(rows)

    assert payload["schema_version"] == "1.0"
    assert payload["table"] == "scrapling_staging"
    assert tuple(payload["columns"]) == scrapling_ops.STAGING_COLUMNS
    assert payload["row_count"] == 2

    # Every row carries exactly STAGING_COLUMNS as keys, no more, no less.
    for row in payload["rows"]:
        assert set(row.keys()) == set(scrapling_ops.STAGING_COLUMNS)

    ok_row = payload["rows"][0]
    assert ok_row["id"] == 1
    assert ok_row["url"] == "https://ok.example.com/"
    assert ok_row["tier_used"] == "fetch"
    assert ok_row["status"] == "ok"
    assert ok_row["content_hash"] is not None
    assert ok_row["content_hash"].startswith("sha256:")
    assert ok_row["content_bytes"] > 0
    assert ok_row["error_message"] is None
    assert ok_row["scenario"] == "generic"

    durur_row = payload["rows"][1]
    assert durur_row["id"] == 2
    assert durur_row["tier_used"] is None
    assert durur_row["status"] == "durur"
    assert durur_row["content_hash"] is None
    assert durur_row["content_bytes"] == 0
    assert durur_row["error_message"] is not None
    for tier_name in ("get", "fetch", "stealthy_fetch"):
        assert tier_name in durur_row["error_message"]

    # Persistence round-trip.
    out_path = tmp_path / "staging.json"
    scrapling_ops.write_staging_json(rows, out_path)
    reloaded = json.loads(out_path.read_text("utf-8"))
    assert reloaded == payload


# ---------------------------------------------------------------------------
# Test (g) — Bulk variant invoked when len(urls) > BULK_THRESHOLD
# ---------------------------------------------------------------------------

def test_bulk_variant_used_above_threshold() -> None:
    """When len(urls) > 10 AND bulk_clients are supplied, the bulk
    callables are invoked and the per-URL fetch is NOT (at tier 1+2)."""
    bulk_calls: dict[str, int] = {"fetch": 0, "stealthy_fetch": 0}
    single_calls: dict[str, int] = {"fetch": 0, "stealthy_fetch": 0, "get": 0}

    def _bulk_fetch(**kwargs: Any) -> dict[str, Any]:
        bulk_calls["fetch"] += 1
        return {u: {"content": f"<html>{u}</html>"} for u in kwargs["urls"]}

    def _bulk_stealthy(**kwargs: Any) -> dict[str, Any]:
        bulk_calls["stealthy_fetch"] += 1
        return {u: {"content": f"<html>stealth-{u}</html>"} for u in kwargs["urls"]}

    def _single_fetch(**kwargs: Any) -> dict[str, Any]:
        single_calls["fetch"] += 1
        return {"error": "should-not-be-called"}

    def _single_stealthy(**kwargs: Any) -> dict[str, Any]:
        single_calls["stealthy_fetch"] += 1
        return {"error": "should-not-be-called"}

    def _single_get(**kwargs: Any) -> dict[str, Any]:
        single_calls["get"] += 1
        return {"error": "403"}     # always fail at get → bulk fetch wins

    urls = [f"https://example.com/p{i}" for i in range(11)]   # 11 > BULK_THRESHOLD(10)
    clients = {
        "get": _single_get,
        "fetch": _single_fetch,
        "stealthy_fetch": _single_stealthy,
    }
    bulk_clients = {"fetch": _bulk_fetch, "stealthy_fetch": _bulk_stealthy}
    results = scrapling_ops.bulk_tier_escalate(
        urls, clients, bulk_clients=bulk_clients,
    )
    assert len(results) == 11
    # Tier 0 is per-URL by design (cheap), tier 1 (bulk_fetch) handled all.
    assert bulk_calls["fetch"] == 1, "bulk_fetch should be called exactly once"
    assert bulk_calls["stealthy_fetch"] == 0, "stealthy not needed"
    assert single_calls["fetch"] == 0, "single fetch must NOT run when bulk available"
    assert single_calls["get"] == 11, "tier 0 runs per-URL"

    # Every URL landed at tier 'fetch'.
    for url, tier, content, _meta in results:
        assert tier == "fetch", f"{url} → {tier}"
        assert content is not None and url in content


def test_bulk_fallback_per_url_client_error_does_not_crash_batch() -> None:
    """When the bulk response has an unknown shape, the per-URL fallback runs
    mcp_clients[tier](url=u). A single client raising there must NOT abort the
    whole batch (deep-audit): it should be recorded as a failed attempt and the
    URL escalates, mirroring every other guarded MCP call in the module."""
    def _single_get(**kwargs: Any) -> dict[str, Any]:
        return {"error": "403"}  # all fail at get → escalate to fetch

    def _single_fetch(**kwargs: Any) -> dict[str, Any]:
        if kwargs["url"] == "https://example.com/p0":
            raise RuntimeError("mcp hiccup")  # the unguarded crash case
        return {"content": f"<html>{kwargs['url']}</html>"}

    def _single_stealthy(**kwargs: Any) -> dict[str, Any]:
        return {"error": "still-blocked"}

    def _bulk_unknown(**kwargs: Any) -> dict[str, Any]:
        return {}  # unrecognised shape → forces the per-URL fallback

    urls = [f"https://example.com/p{i}" for i in range(11)]  # > BULK_THRESHOLD
    clients = {"get": _single_get, "fetch": _single_fetch, "stealthy_fetch": _single_stealthy}
    bulk_clients = {"fetch": _bulk_unknown, "stealthy_fetch": _bulk_unknown}

    # Must not raise — the batch completes for all 11 URLs.
    results = scrapling_ops.bulk_tier_escalate(urls, clients, bulk_clients=bulk_clients)
    assert len(results) == 11

    by_url = {u: (tier, content, meta) for (u, tier, content, meta) in results}
    # The URL whose fallback client raised is recorded as failed, not crashed.
    assert by_url["https://example.com/p0"][0] is None
    # A sibling URL still succeeded at the fetch tier.
    assert by_url["https://example.com/p1"][0] == "fetch"


def test_single_path_when_below_threshold() -> None:
    """When len(urls) <= 10 the bulk path is NOT taken even if
    bulk_clients are supplied — saves a needless bulk MCP call."""
    bulk_invoked: list[str] = []

    def _bulk_fetch(**kwargs: Any) -> dict[str, Any]:
        bulk_invoked.append("fetch")
        return {}

    clients = {
        "get": _make_client(succeed=True, content="ok"),
        "fetch": _make_client(succeed=True),
        "stealthy_fetch": _make_client(succeed=True),
    }
    urls = [f"https://example.com/p{i}" for i in range(5)]   # well below threshold
    scrapling_ops.bulk_tier_escalate(urls, clients, bulk_clients={"fetch": _bulk_fetch})
    assert bulk_invoked == [], "bulk client must not run for ≤BULK_THRESHOLD urls"


# ---------------------------------------------------------------------------
# Test (h) — URL count > max_urls triggers DURUR
# ---------------------------------------------------------------------------

def test_url_budget_exceeded_raises(tmp_path: Path) -> None:
    """run_scrapling_ops refuses to call any MCP tool when URL count is
    over the configured budget — DURUR #6."""
    mcp_called: list[str] = []

    def _client(**kwargs: Any) -> dict[str, Any]:
        mcp_called.append(kwargs["url"])
        return {"content": "should-not-run"}

    clients = {"get": _client, "fetch": _client, "stealthy_fetch": _client}
    urls = [f"https://example.com/p{i}" for i in range(51)]  # 51 > default 50
    with pytest.raises(scrapling_ops.UrlBudgetExceededError):
        scrapling_ops.run_scrapling_ops(
            urls, clients,
            output_path=tmp_path / "staging.json",
            max_urls=50,
        )
    assert mcp_called == [], "no MCP call must run after budget rejection"

    # Custom (lower) budget enforces the same way.
    with pytest.raises(scrapling_ops.UrlBudgetExceededError):
        scrapling_ops.run_scrapling_ops(
            ["a", "b", "c"], clients,
            output_path=tmp_path / "staging2.json",
            max_urls=2,
        )


# ---------------------------------------------------------------------------
# Test (h.2) — run_scrapling_ops happy path ties everything together
# ---------------------------------------------------------------------------

def test_run_scrapling_ops_writes_staging(tmp_path: Path) -> None:
    """End-to-end: small URL list → orchestrator writes a staging file
    matching the documented shape and returns a summary."""
    clients = {
        "get": _make_client(succeed=False, error="403"),
        "fetch": _make_client(succeed=True, content="<html>ok</html>"),
        "stealthy_fetch": _make_client(succeed=False, error="should-not-run"),
    }
    urls = ["https://a.example.com/", "https://b.example.com/"]
    out_path = tmp_path / "scrapling_2026-05-01_test.json"
    summary = scrapling_ops.run_scrapling_ops(
        urls, clients, output_path=out_path, scenario="generic",
    )
    assert summary["row_count"] == 2
    assert summary["ok_count"] == 2
    assert summary["durur_count"] == 0
    assert summary["tier_counts"] == {"fetch": 2}
    assert summary["scenario"] == "generic"
    assert summary["staging_path"] == str(out_path)

    # File on disk matches the summary.
    on_disk = json.loads(out_path.read_text("utf-8"))
    assert on_disk["row_count"] == 2
    assert tuple(on_disk["columns"]) == scrapling_ops.STAGING_COLUMNS
    assert {r["url"] for r in on_disk["rows"]} == set(urls)
    assert all(r["tier_used"] == "fetch" for r in on_disk["rows"])
    assert all(r["status"] == "ok" for r in on_disk["rows"])
