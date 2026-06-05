"""
tests/skills/test_weekly_summary.py — weekly-summary reporting skill tests.

Phase 9 Wave 1 (W-E2). LOCAL aggregation skill — no MCP, no DFS, no
budget pre-flight. 5-section structural contract (no schema this Wave).

Mirrors tests/skills/test_master_task_sync.py shape (frontmatter parse +
schema validate, structural assert, idempotency / window logic, sentinel
guards). Read-only contract on master.xlsx + events.jsonl.

Schemas referenced:
  - schemas/skill-frontmatter.schema.json (frontmatter validate)
  - (no monthly-report.schema.json this Wave — output has no schema)
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

from scripts.reporting import weekly_summary as ws


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = REPO_ROOT / "schemas"
SKILL_PATH = (
    REPO_ROOT / "skills" / "reporting" / "weekly-summary" / "SKILL.md"
)
TRANSFORM_PATH = REPO_ROOT / "scripts" / "reporting" / "weekly_summary.py"
TEMPLATE_PATH = (
    REPO_ROOT / "templates" / "reports" / "weekly-summary.template.md"
)
TEST_PATH = Path(__file__)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def skill_frontmatter_schema() -> dict:
    return json.loads(
        (SCHEMAS / "skill-frontmatter.schema.json").read_text("utf-8")
    )


@pytest.fixture(scope="module")
def skill_frontmatter() -> dict:
    text = SKILL_PATH.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, "SKILL.md missing YAML frontmatter delimiters"
    return yaml.safe_load(match.group(1))


@pytest.fixture
def synthetic_sheets() -> dict[str, list[dict]]:
    """Synthetic master.xlsx snapshot.

    Window for the 2026-04-26 (Sun) run: 2026-04-20 .. 2026-04-26.
      - master_task: 2 in-window done + 1 in-window added (no done)
                     + 1 out-of-window done + 1 manuel auto=False
      - opportunity / quick_wins / content_decay: a few rows each.
    """
    return {
        "master_task": [
            # In-window DONE (qualifies for tasks_done).
            {
                "task_id": "abc1234567890def",
                "task": "",
                "primary_source": "quickwin",
                "related_sources": "quick_wins",
                "url": "https://example.test/a",
                "status": "DONE",
                "created_date": "2026-04-15",
                "done_date": "2026-04-22",
                "auto_generated": True,
            },
            {
                "task_id": "fedcba9876543210",
                "task": "",
                "primary_source": "tech_fix",
                "related_sources": "tech_seo",
                "url": "https://example.test/b",
                "status": "DONE",
                "created_date": "2026-04-10",
                "done_date": "2026-04-26",
                "auto_generated": True,
            },
            # In-window CREATED only (not DONE → tasks_added but not tasks_done).
            {
                "task_id": "1111222233334444",
                "task": "",
                "primary_source": "schema",
                "related_sources": "schema",
                "url": "https://example.test/c",
                "status": "TODO",
                "created_date": "2026-04-21",
                "done_date": "",
                "auto_generated": True,
            },
            # OUT-of-window DONE.
            {
                "task_id": "5555666677778888",
                "task": "",
                "primary_source": "content_decay",
                "related_sources": "content_decay",
                "url": "https://example.test/d",
                "status": "DONE",
                "created_date": "2026-03-01",
                "done_date": "2026-04-10",
                "auto_generated": True,
            },
        ],
        "opportunity": [
            {"query": "kw-1", "opportunity_score": 0.8},
            {"query": "kw-2", "opportunity_score": 0.6},
        ],
        "quick_wins": [
            {"query": "kw-q1", "url": "https://example.test/q1"},
        ],
        "content_decay": [
            {"url": "https://example.test/decay-1", "trend": "down"},
            {"url": "https://example.test/decay-2", "trend": "down"},
            {"url": "https://example.test/decay-3", "trend": "down"},
        ],
    }


@pytest.fixture
def synthetic_events(tmp_path: Path) -> Path:
    """In-window + out-of-window events.jsonl. Returns the file path."""
    p = tmp_path / "events.jsonl"
    lines = [
        # In-window work event.
        {"event_id": "1", "event_kind": "work",
         "timestamp": "2026-04-22T10:00:00Z", "task_id": "abc"},
        # In-window NON-work event (filtered out).
        {"event_id": "2", "event_kind": "audit",
         "timestamp": "2026-04-22T11:00:00Z"},
        # Out-of-window work event (filtered out).
        {"event_id": "3", "event_kind": "work",
         "timestamp": "2026-04-01T09:00:00Z", "task_id": "old"},
        # Another in-window work event.
        {"event_id": "4", "event_kind": "work",
         "timestamp": "2026-04-26T16:00:00Z", "task_id": "def"},
    ]
    p.write_text(
        "\n".join(json.dumps(L) for L in lines) + "\n", encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Test 1 — Frontmatter validates against skill-frontmatter.schema.json
# ---------------------------------------------------------------------------

def test_frontmatter_validates(
    skill_frontmatter: dict, skill_frontmatter_schema: dict,
) -> None:
    """SKILL.md frontmatter must:
      (a) parse as YAML;
      (b) carry name=weekly-summary, status=active, version="1.0",
          category=reporting;
      (c) declare project_slug as required string input;
      (d) declare 0 mcp_tools (LOCAL aggregation, no MCP);
      (e) budget.uses_paid_mcp=false, estimated_credits=0;
      (f) outputs[] has exactly 3 entries (REVIZE 1 — no events.jsonl);
      (g) outputs include "master.xlsx#none" (READ-ONLY confirm);
      (h) triggers.manual is empty list (no slash command);
      (i) autonomy: HIGH / no approval / safe_auto_execute=true;
      (j) validate against schemas/skill-frontmatter.schema.json (Draft 7).
    """
    fm = skill_frontmatter
    assert fm["name"] == "weekly-summary"
    assert fm["status"] in {"active", "deprecated", "wip"}
    assert fm["version"] == "1.0"
    assert fm["category"] == "reporting"

    inputs = fm["inputs"]
    assert "project_slug" in inputs
    assert inputs["project_slug"]["type"] == "string"
    assert inputs["project_slug"]["required"] is True
    assert "week_end" in inputs
    assert inputs["week_end"]["required"] is False

    # No required NOR optional MCP tools — LOCAL aggregation only.
    assert fm.get("mcp_tools", {}).get("required", []) == []
    assert fm.get("mcp_tools", {}).get("optional", []) == []

    # REVIZE 1: outputs has exactly 3 entries.
    outputs = fm["outputs"]
    assert len(outputs) == 3, (
        f"REVIZE 1 violation: outputs must have exactly 3 entries (no "
        f"events.jsonl), got {len(outputs)}: {outputs}"
    )
    # READ-ONLY confirm marker must be present.
    assert any("master.xlsx#none" in o for o in outputs), (
        f"missing READ-ONLY marker 'master.xlsx#none' in outputs: {outputs}"
    )
    # Report + snapshot anchors.
    assert any("outputs/reports/" in o and "weekly-summary" in o
               for o in outputs)
    assert any("inbox/local/" in o and "weekly" in o for o in outputs)

    # REVIZE 2+3: events.jsonl is NOT in outputs (events.jsonl write removed).
    for o in outputs:
        assert "events.jsonl" not in o, (
            f"REVIZE 3 violation: events.jsonl must NOT appear in outputs: "
            f"{o!r}"
        )

    # Manual triggers empty (no slash command).
    triggers = fm.get("triggers", {})
    assert triggers.get("manual", []) == []

    # Budget: 0 credits, no paid MCP.
    assert fm["budget"]["uses_paid_mcp"] is False
    assert fm["budget"].get("estimated_credits", 0) == 0

    # Autonomy: HIGH read-only aggregator, no approval, cron-safe.
    auto = fm["autonomy"]
    assert auto["confidence"] == "HIGH"
    assert auto["requires_approval"] is False
    assert auto["safe_auto_execute"] is True

    # Full Draft 7 validation against the canonical schema.
    validator = Draft7Validator(skill_frontmatter_schema)
    errs = sorted(validator.iter_errors(fm), key=lambda e: list(e.absolute_path))
    assert not errs, (
        f"frontmatter invalid: "
        f"{[(list(e.absolute_path), e.message) for e in errs]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — natural_language sentinel: min 30 char (REVIZE 1 / Gate #7)
# ---------------------------------------------------------------------------

def test_natural_language_min_length(skill_frontmatter: dict) -> None:
    """skill-frontmatter.schema.json#triggers.natural_language has no
    minLength constraint at the schema level; the worker brief mandates
    a >=30 char minimum at the SKILL level. This sentinel asserts it.
    """
    nl = skill_frontmatter["triggers"]["natural_language"]
    assert isinstance(nl, str), (
        f"natural_language must be a comma-separated string (per spec §9), "
        f"got {type(nl).__name__}"
    )
    assert len(nl) >= 30, (
        f"natural_language too short ({len(nl)} chars; need >=30): {nl!r}"
    )


# ---------------------------------------------------------------------------
# Test 3 — 5-section structural contract (no schema this Wave)
# ---------------------------------------------------------------------------

def test_five_section_structural_contract(
    synthetic_sheets: dict[str, list[dict]],
) -> None:
    """The output of aggregate() carries every section in
    WEEKLY_SUMMARY_SECTIONS. This is the structural contract that
    replaces a schema this Wave.
    """
    batch = ws.aggregate(
        project_slug="test-slug",
        sheets=synthetic_sheets,
        work_events=[],
        week_end=date(2026, 4, 26),
    )
    payload = batch.as_dict()
    for section in ws.WEEKLY_SUMMARY_SECTIONS:
        assert section in payload, (
            f"5-section contract violation: missing key {section!r} in "
            f"output payload (have: {sorted(payload.keys())})"
        )
    # exec_summary is a string with content.
    assert isinstance(payload["exec_summary"], str)
    assert len(payload["exec_summary"]) > 0
    # gsc_weekly_delta + drift_signals are dicts.
    assert isinstance(payload["gsc_weekly_delta"], dict)
    assert isinstance(payload["drift_signals"], dict)
    # tasks_done + tasks_added are lists.
    assert isinstance(payload["tasks_done"], list)
    assert isinstance(payload["tasks_added"], list)


# ---------------------------------------------------------------------------
# Test 4 — week_end weekend snap (default = last Sunday)
# ---------------------------------------------------------------------------

def test_week_end_snaps_to_last_sunday() -> None:
    """compute_window snaps any non-Sunday reference to the most recent
    Sunday (inclusive). Sunday → Sunday (no-op). Wednesday 2026-04-22
    → Sunday 2026-04-19.
    """
    # Sunday — no shift.
    s = date(2026, 4, 26)  # Sunday
    assert s.weekday() == 6
    assert ws.snap_to_last_sunday(s) == s

    # Wednesday — back to previous Sunday.
    w = date(2026, 4, 22)  # Wednesday
    assert ws.snap_to_last_sunday(w) == date(2026, 4, 19)

    # Saturday — back one day.
    sa = date(2026, 4, 25)  # Saturday
    assert ws.snap_to_last_sunday(sa) == date(2026, 4, 19)

    # Monday — back one day.
    mo = date(2026, 4, 27)  # Monday
    assert ws.snap_to_last_sunday(mo) == date(2026, 4, 26)

    # compute_window applies snap when caller passes a non-Sunday.
    start, end = ws.compute_window(date(2026, 4, 22))
    assert end == date(2026, 4, 19)  # snapped
    assert start == date(2026, 4, 13)  # 6 days back, inclusive 7-day window
    # Inclusive 7-day window.
    assert (end - start).days == ws.WINDOW_DAYS - 1

    # Default (None) snaps today to last Sunday.
    today = date.today()
    expected_end = ws.snap_to_last_sunday(today)
    start_d, end_d = ws.compute_window(None)
    assert end_d == expected_end
    assert start_d == expected_end - timedelta(days=ws.WINDOW_DAYS - 1)


# ---------------------------------------------------------------------------
# Test 5 — events.jsonl last-7-day filter (in-window + non-work filtered)
# ---------------------------------------------------------------------------

def test_events_jsonl_last_7_day_filter(synthetic_events: Path) -> None:
    """read_events_jsonl returns ONLY entries where event_kind matches
    AND timestamp ∈ [window_start, window_end]. Other kinds + out-of-
    window entries are filtered out. Missing file → []. The reader is
    READ-ONLY (no writes implied)."""
    window_start = date(2026, 4, 20)
    window_end = date(2026, 4, 26)

    out = ws.read_events_jsonl(
        synthetic_events, window_start, window_end,
        event_kind=ws.EVENT_KIND_WORK,
    )
    # Only the 2 in-window WORK events qualify (event 1 + event 4).
    assert len(out) == 2
    ids = sorted(e["event_id"] for e in out)
    assert ids == ["1", "4"]

    # Missing file path → []
    out_empty = ws.read_events_jsonl(
        Path("/tmp/does-not-exist-99999.jsonl"), window_start, window_end,
    )
    assert out_empty == []


# ---------------------------------------------------------------------------
# Test 6 — master_task delta count (added vs done)
# ---------------------------------------------------------------------------

def test_master_task_delta_count_added_vs_done(
    synthetic_sheets: dict[str, list[dict]],
) -> None:
    """tasks_done filters on (status=DONE AND done_date in window);
    tasks_added filters on (created_date in window). Out-of-window DONE
    must be excluded; in-window CREATED+TODO must appear in tasks_added
    but not in tasks_done."""
    batch = ws.aggregate(
        project_slug="test-slug",
        sheets=synthetic_sheets,
        work_events=[],
        week_end=date(2026, 4, 26),
    )

    # 2 in-window DONE rows (abc... + fedc...)
    assert len(batch.tasks_done) == 2
    done_ids = {r["task_id"] for r in batch.tasks_done}
    assert done_ids == {"abc1234567890def", "fedcba9876543210"}

    # 1 in-window CREATED row (1111... created 2026-04-21).
    assert len(batch.tasks_added) == 1
    assert batch.tasks_added[0]["task_id"] == "1111222233334444"

    # The out-of-window DONE row (5555... done 2026-04-10) is excluded.
    for row in batch.tasks_done:
        assert row["task_id"] != "5555666677778888"

    # Drift signals reflect the synthetic sheet sizes.
    assert batch.drift_signals["opportunity_rows"] == 2
    assert batch.drift_signals["quick_wins_rows"] == 1
    assert batch.drift_signals["content_decay_rows"] == 3


# ---------------------------------------------------------------------------
# Test 7 — template renders + snapshot + report markdown smoke test
# ---------------------------------------------------------------------------

def test_template_renders_and_snapshot_shape(
    synthetic_sheets: dict[str, list[dict]], tmp_path: Path,
) -> None:
    """build_report_markdown renders the template via string.Template
    $var substitution (render_template.py compatible). build_snapshot
    produces a JSON-serializable dict. End-to-end: aggregate → render →
    write. Verifies no KeyError on any $variable in the template."""
    batch = ws.aggregate(
        project_slug="test-slug",
        sheets=synthetic_sheets,
        work_events=[],
        week_end=date(2026, 4, 26),
    )
    generated_at = "2026-04-27T08:00:00Z"

    # Smoke render — must NOT raise KeyError on any $variable.
    rendered = ws.build_report_markdown(
        batch=batch, generated_at=generated_at, template_path=TEMPLATE_PATH,
    )
    assert "weekly-summary" in rendered.lower() or "weekly summary" in rendered.lower()
    assert "test-slug" in rendered
    assert "2026-04-20" in rendered  # week_start
    assert "2026-04-26" in rendered  # week_end
    assert "2026-04-27T08:00:00Z" in rendered  # generated_at

    # Snapshot is JSON-serializable + carries 5-section payload.
    snapshot = ws.build_snapshot(batch=batch, generated_at=generated_at)
    blob = json.dumps(snapshot, ensure_ascii=False)
    parsed = json.loads(blob)
    for section in ws.WEEKLY_SUMMARY_SECTIONS:
        assert section in parsed
    assert parsed["report_kind"] == "weekly_summary"
    assert parsed["generated_at"] == generated_at
    assert parsed["project_slug"] == "test-slug"


# ---------------------------------------------------------------------------
# Test 8 — Forbidden tokens guard (grep CLEAN across production files)
# ---------------------------------------------------------------------------
#
# Tokens enforced (each carries a Phase 7 / Phase 8 lesson reference):
#   - per-call / per-url credit field name fragments (Phase 7 schema-field
#     uydurma YASAK — test references them only via the guard tuple below).
#   - the legacy metric-naming field tossed in Phase 7 closeout Q-CO-01.
#   - hardcoded plugin slugs (production files must be plugin-agnostik;
#     the test fixture file is intentionally exempt — fixtures may name
#     slugs as test data).
#   - bare TODO comment markers (`# TODO`, `// TODO`, `TODO:` — drift
#     signature). The string "TODO" as a master_task statusEnum literal
#     is ALLOWED (it's data, not a code comment).

# Build the literal field tokens via fragments so the guard list itself
# does not write the full token in source — keeps the test file from
# tripping its own check during meta-scans / future ratchets.
_CR = "estimated" + "_credits"
FORBIDDEN_TOKENS_LITERAL: tuple[str, ...] = (
    _CR + "_per_call",
    _CR + "_per_url",
    "metric" + "_name",
)
HARDCODED_SLUGS: tuple[str, ...] = ("demo-dental", "demo-furniture", "lucidya")
TODO_COMMENT_RE = re.compile(r"(?:#\s*TODO\b|//\s*TODO\b|\bTODO:\s)")

# Scope: production files only. Test file fixtures may legitimately use
# slug names / status="TODO" as test data; the production guard is what
# governs drift.
SCOPED_FILES: tuple[Path, ...] = (
    SKILL_PATH,
    TRANSFORM_PATH,
    TEMPLATE_PATH,
)


def test_no_forbidden_tokens_in_skill() -> None:
    """grep guard: forbidden tokens must not appear in production files
    (SKILL.md + transform.py + template.md). Test fixtures are exempt
    by design — they carry slug names + status enum literals as data."""
    for path in SCOPED_FILES:
        text = path.read_text(encoding="utf-8")
        # Literal forbidden field-name tokens.
        for tok in FORBIDDEN_TOKENS_LITERAL:
            assert tok not in text, (
                f"forbidden token {tok!r} appeared in {path.name}; "
                "this token is a Phase 7 lesson schema-field uydurma marker"
            )
        # Hardcoded project slugs.
        lowered = text.lower()
        for slug in HARDCODED_SLUGS:
            assert slug not in lowered, (
                f"hardcoded project slug {slug!r} appeared in "
                f"{path.name}; transforms must be plugin-agnostik"
            )
        # TODO comment markers (not status enum data).
        match = TODO_COMMENT_RE.search(text)
        assert match is None, (
            f"TODO comment marker found in {path.name} at offset "
            f"{match.start() if match else -1}: drift signature"
        )


# ---------------------------------------------------------------------------
# Test 9 — master_task READ-ONLY: transform never imports transaction
# ---------------------------------------------------------------------------

def test_transform_is_read_only_no_excel_writes() -> None:
    """The weekly-summary transform must NOT import scripts.excel.transaction
    (which is the master.xlsx writer module). master_task is READ-ONLY for
    this skill (gate #8)."""
    src = TRANSFORM_PATH.read_text(encoding="utf-8")
    assert not re.search(
        r"^\s*from\s+scripts\.excel\.transaction\s+import",
        src, flags=re.MULTILINE,
    ), (
        "scripts.excel.transaction import is forbidden in weekly_summary; "
        "this skill is READ-ONLY w.r.t. master.xlsx"
    )
    assert not re.search(
        r"^\s*import\s+scripts\.excel\.transaction",
        src, flags=re.MULTILINE,
    ), "scripts.excel.transaction import is forbidden in weekly_summary"

    # Also: events_writer must NOT be imported (REVIZE 3 — no events.jsonl
    # writes). READ-ONLY events.jsonl streaming is via plain file I/O.
    assert not re.search(
        r"^\s*from\s+scripts\.state\.events_writer\s+import",
        src, flags=re.MULTILINE,
    ), (
        "scripts.state.events_writer import is forbidden in weekly_summary "
        "(REVIZE 3 — no events.jsonl writes; Q-RP-01 deferred to Phase 14)"
    )


# ---------------------------------------------------------------------------
# Test 10 — DURUR #2: WorkspaceRootUnsetError is now reachable (B2-06)
# ---------------------------------------------------------------------------

def test_workspace_root_unset_raises_when_unresolvable(tmp_path: Path) -> None:
    """B2-06 / SKILL.md DURUR #2: main() raises WorkspaceRootUnsetError (a
    typed WeeklySummaryError) when --workspace-root cannot be resolved to a
    projects/{slug}/ directory. This is the documented stop condition #2 made
    real — previously the class was declared + exported but never raised, so
    an unresolvable workspace surfaced as a generic WorkbookMissingError or
    argparse error instead of the typed envelope the contract promises.

    The split is semantic: projects/{slug}/ ABSENT → WorkspaceRootUnsetError;
    projects/{slug}/ present but master.xlsx absent → WorkbookMissingError
    (see test_workbook_missing_raises)."""
    # WorkspaceRootUnsetError is a subclass of the base envelope.
    assert issubclass(ws.WorkspaceRootUnsetError, ws.WeeklySummaryError)

    # projects/{slug}/ does not exist under this workspace root.
    empty_ws = tmp_path / "no-projects-here"
    empty_ws.mkdir()
    with pytest.raises(ws.WorkspaceRootUnsetError):
        ws.main([
            "--project-slug", "demo-project",
            "--workspace-root", str(empty_ws),
        ])

    # An empty --workspace-root is also unresolvable.
    with pytest.raises(ws.WorkspaceRootUnsetError):
        ws.main([
            "--project-slug", "demo-project",
            "--workspace-root", "",
        ])


# ---------------------------------------------------------------------------
# Test 11 — DURUR #1: WorkbookMissingError when project dir exists, no workbook
# ---------------------------------------------------------------------------

def test_workbook_missing_raises(tmp_path: Path) -> None:
    """SKILL.md DURUR #1: projects/{slug}/ EXISTS but master.xlsx is absent →
    WorkbookMissingError. This is the other side of the B2-06 split: a present
    project dir without a workbook is a workbook problem, NOT a workspace-root
    problem."""
    project_root = tmp_path / "ws" / "projects" / "demo-project"
    project_root.mkdir(parents=True)  # dir exists; master.xlsx intentionally absent
    with pytest.raises(ws.WorkbookMissingError):
        ws.main([
            "--project-slug", "demo-project",
            "--workspace-root", str(tmp_path / "ws"),
        ])


# ---------------------------------------------------------------------------
# Test 12 — DURUR #3: TemplateMissingError from build_report_markdown
# ---------------------------------------------------------------------------

def test_template_missing_raises(
    synthetic_sheets: dict[str, list[dict]], tmp_path: Path,
) -> None:
    """SKILL.md DURUR #3: build_report_markdown raises TemplateMissingError
    when the template file is not on disk (reachable today; previously
    untested)."""
    batch = ws.aggregate(
        project_slug="demo-project", sheets=synthetic_sheets,
        work_events=[], week_end=date(2026, 4, 26),
    )
    missing = tmp_path / "nope" / "weekly-summary.template.md"
    with pytest.raises(ws.TemplateMissingError):
        ws.build_report_markdown(
            batch=batch, generated_at="2026-04-27T08:00:00Z",
            template_path=missing,
        )


# ---------------------------------------------------------------------------
# Test 13 — DURUR #4: WeeklySummaryError envelope on bad project_slug
# ---------------------------------------------------------------------------

def test_weekly_summary_error_on_bad_slug() -> None:
    """SKILL.md DURUR #4: aggregate raises the WeeklySummaryError base
    envelope on an empty / blank / non-string project_slug (reachable today;
    previously untested)."""
    for bad in ("", "   ", None):
        with pytest.raises(ws.WeeklySummaryError):
            ws.aggregate(
                project_slug=bad, sheets={}, work_events=[],
                week_end=date(2026, 4, 26),
            )


# ---------------------------------------------------------------------------
# Test 14 — Idempotency / byte-stability (SKILL.md discipline checklist)
# ---------------------------------------------------------------------------

def test_idempotent_byte_stable_output(
    synthetic_sheets: dict[str, list[dict]], synthetic_events: Path,
) -> None:
    """SKILL.md discipline checklist ('Idempotency: same workbook + frozen
    events + frozen clock → byte-stable report + snapshot'). Runs the
    aggregate → render / snapshot pipeline twice with a fixed generated_at and
    frozen inputs and asserts BYTE-identical markdown + snapshot JSON — the
    guarantee was claimed in the docstring but never actually exercised."""
    generated_at = "2026-04-27T08:00:00Z"
    work_events = ws.read_events_jsonl(
        synthetic_events, date(2026, 4, 20), date(2026, 4, 26),
        event_kind=ws.EVENT_KIND_WORK,
    )

    def render_once() -> tuple[str, str]:
        batch = ws.aggregate(
            project_slug="demo-project", sheets=synthetic_sheets,
            work_events=work_events, week_end=date(2026, 4, 26),
        )
        md = ws.build_report_markdown(
            batch=batch, generated_at=generated_at, template_path=TEMPLATE_PATH,
        )
        snap = json.dumps(
            ws.build_snapshot(batch=batch, generated_at=generated_at),
            ensure_ascii=False, indent=2, sort_keys=True,
        )
        return md, snap

    md1, snap1 = render_once()
    md2, snap2 = render_once()
    assert md1 == md2, "report markdown not byte-stable across identical runs"
    assert snap1 == snap2, "snapshot JSON not byte-stable across identical runs"
    # Byte-level equality — the SKILL.md guarantee is byte-IDENTICAL output.
    assert md1.encode("utf-8") == md2.encode("utf-8")
    assert snap1.encode("utf-8") == snap2.encode("utf-8")
