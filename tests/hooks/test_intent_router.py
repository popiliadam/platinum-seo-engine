"""tests/hooks/test_intent_router.py — AMO batch 1c intent router (L1).

The UserPromptSubmit "intent router" is the first half of AMO's intent guarantee:
when an operator states a KNOWN intent ("alpha'da aylık bakım yap"), the right
workflow is GUARANTEED to engage. The router classifies each prompt:

  * Tier-1 — the prompt canonically names a known workflow → inject a one-line
    "invoke /pseo-run <workflow> <slug>" instruction (stdout → model context) AND
    write an ``intent_declared`` marker so the batch-2c Stop denetçi can detect a
    turn that ended WITHOUT the workflow actually running.
  * Tier-2 — no match (or >=2 workflows collide) → fall back to the existing
    whats-next advisory only, and SUPERSEDE any prior declared intent so a stale
    cross-turn intent never blocks the denetçi.

It is the SINGLE voice per prompt (it subsumes the old static-bash command that
printed the "PSEO context:" line + the Drift-router advisory), and it must NEVER
crash the hook chain (any internal error → advisory + exit 0).

Confirmed facts under test (batch 0a/0b): the only proven payload binding key is
``session_id``; there is NO per-turn id, so the router ASSIGNS turn_id/intent_id
itself and delivers "current-turn only" structurally — ONE marker per session,
REWRITTEN every prompt. Every filesystem test uses tmp_path + a monkeypatched /
overridden HOME, never the real ~/.config or workspace.

Authority: schemas/intent-marker.schema.json (marker shape),
  scripts/state/session_binding.py (resolver/atomic-write reuse), batch 0a probe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

import scripts.hooks.intent_router as router
from scripts.state import session_binding as sb

_REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = _REPO_ROOT / "schemas" / "intent-marker.schema.json"
ROUTER_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "intent_router.py"
HOOK_JSON = _REPO_ROOT / "hooks" / "user-prompt-submit.json"

# The advisory the router MUST preserve byte-for-byte from the old static bash.
_EXPECTED_ADVISORY = (
    "Drift router: when uncertain about next step invoke the meta:whats-next "
    "skill (Phase 5+) — until then consult docs/PHASE_STATUS.md."
)

# DECISION 2 operator-remediation hint the degraded path must print BEFORE the
# advisory — repo-canonical unbound wording (matches the old static-bash unbound
# branch + session-start.json; /pseo-init is the real scaffolder per P1-05).
_EXPECTED_HINT = (
    "PSEO context: no active project bound — run /pseo-init or set PSEO_WORKSPACE_ROOT"
)


def _validator() -> Draft7Validator:
    return Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "shared").mkdir(parents=True)
    return ws


# ---------------------------------------------------------------------------
# 1. classify — pure Tier-1 / Tier-2 decision
# ---------------------------------------------------------------------------

def test_classify_canonical_monthly() -> None:
    wf, matched = router.classify("alpha'da aylık bakım yap")
    assert wf == "monthly"
    assert matched == ["monthly"]


def test_classify_unrelated_is_tier2() -> None:
    assert router.classify("merhaba") == (None, [])


def test_classify_blank_is_tier2() -> None:
    assert router.classify("") == (None, [])
    assert router.classify("   ") == (None, [])


def test_classify_ascii_caps_typo_variant() -> None:
    # "AYLIK BAKIM".lower() == "aylik bakim" (ASCII fold) → the typo variant matches.
    wf, matched = router.classify("AYLIK BAKIM yapalim")
    assert wf == "monthly"
    assert matched == ["monthly"]


def test_classify_does_not_overmatch_single_word() -> None:
    # specificity: a partial word must NOT trigger a false Tier-1.
    assert router.classify("show me the monthly report") == (None, [])
    assert router.classify("bakım lazım") == (None, [])


# ---------------------------------------------------------------------------
# 2. route Tier-1 (bound) — declared marker + actionable voice
# ---------------------------------------------------------------------------

def test_route_tier1_bound(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-1", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "aylık bakım yap",
        session_id="sess-1",
        workspace_root=ws,
        turn_id="t1",
        intent_id="i1",
        declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 1
    assert result["slug"] == "demo-furniture"
    m = result["marker"]
    assert m["status"] == "declared"
    assert m["workflow"] == "monthly"
    assert m["slug"] == "demo-furniture"
    assert m["command"] == "/pseo-run monthly demo-furniture"
    assert "/pseo-run monthly demo-furniture" in result["voice"]
    _validator().validate(m)  # raises on schema mismatch


# ---------------------------------------------------------------------------
# 3. route Tier-1 (unbound) — declared, NO slug, /pseo-bind voice
# ---------------------------------------------------------------------------

def test_route_tier1_unbound(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)  # no binding marker, no active.json → unbound
    result = router.route(
        "aylık bakım yap",
        session_id="sess-unbound",
        workspace_root=ws,
        turn_id="t1",
        intent_id="i1",
        declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 1
    assert result["slug"] is None
    m = result["marker"]
    assert m["status"] == "declared"
    assert "slug" not in m  # never fabricate a slug
    assert m["workflow"] == "monthly"
    assert m["command"] == "/pseo-run monthly <slug>"
    assert "/pseo-bind" in result["voice"]
    _validator().validate(m)  # still valid: declared keeps workflow + command


# ---------------------------------------------------------------------------
# 4. route Tier-2 — supersedes prior intent + verbatim advisory
# ---------------------------------------------------------------------------

def test_route_tier2_supersedes(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-1", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "merhaba",
        session_id="sess-1",
        workspace_root=ws,
        turn_id="t1",
        intent_id="i1",
        declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 2
    m = result["marker"]
    assert m["status"] == "superseded"
    assert "workflow" not in m
    assert "command" not in m
    assert result["voice"] == _EXPECTED_ADVISORY
    _validator().validate(m)


def test_advisory_is_verbatim() -> None:
    assert router._ADVISORY == _EXPECTED_ADVISORY


# ---------------------------------------------------------------------------
# 5. schema: declared / superseded validate; declared missing wf/cmd FAILS
# ---------------------------------------------------------------------------

def test_build_marker_declared_validates() -> None:
    m = router.build_marker(
        "S", turn_id="t", intent_id="i", status="declared",
        declared_at="2026-06-05T00:00:00", workflow="monthly",
        slug="demo-furniture", command="/pseo-run monthly demo-furniture",
    )
    _validator().validate(m)


def test_build_marker_superseded_validates() -> None:
    m = router.build_marker(
        "S", turn_id="t", intent_id="i", status="superseded",
        declared_at="2026-06-05T00:00:00",
    )
    _validator().validate(m)


def test_declared_marker_missing_workflow_command_fails_schema() -> None:
    bad = {
        "schema_version": "1.0",
        "session_id": "S",
        "turn_id": "t",
        "intent_id": "i",
        "status": "declared",
        "declared_at": "2026-06-05T00:00:00",
    }
    errors = list(_validator().iter_errors(bad))
    assert errors, "declared marker without workflow+command must fail the allOf"


def test_build_marker_rejects_bad_status() -> None:
    with pytest.raises(ValueError):
        router.build_marker("S", turn_id="t", intent_id="i", status="bogus",
                            declared_at="t")


def test_build_marker_omits_absent_optionals() -> None:
    m = router.build_marker("S", turn_id="t", intent_id="i", status="superseded",
                            declared_at="t")
    # additionalProperties:false — only declared keys present
    assert set(m) == {"schema_version", "session_id", "turn_id", "intent_id",
                      "status", "declared_at"}


def test_intent_marker_path(tmp_path: Path) -> None:
    p = router.intent_marker_path(tmp_path, "abc")
    assert p == tmp_path / "shared" / "sessions" / "abc.intent.json"


# ---------------------------------------------------------------------------
# 6. main() via subprocess — Tier-1 writes a valid marker + prints one voice
# ---------------------------------------------------------------------------

def _run_router(payload_text: str, *, home: Path, workspace) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)  # ~/.config/pseo never the real one
    env.pop("CLAUDE_CODE_SESSION_ID", None)  # session_id comes from the payload
    if workspace is None:
        env.pop("PSEO_WORKSPACE_ROOT", None)
    else:
        env["PSEO_WORKSPACE_ROOT"] = str(workspace)
    return subprocess.run(
        [sys.executable, str(ROUTER_SCRIPT)],
        input=payload_text,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(_REPO_ROOT),
    )


def test_main_tier1_writes_marker_and_prints_one_voice(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    sb.write_session_binding("sid-123", "demo-furniture", ws, "2026-06-05T00:00:00")
    payload = json.dumps({"session_id": "sid-123", "prompt": "aylık bakım yap"})
    res = _run_router(payload, home=home, workspace=ws)
    assert res.returncode == 0, res.stderr
    marker_path = ws / "shared" / "sessions" / "sid-123.intent.json"
    assert marker_path.exists()
    data = json.loads(marker_path.read_text(encoding="utf-8"))
    _validator().validate(data)
    assert data["status"] == "declared"
    assert data["command"] == "/pseo-run monthly demo-furniture"
    # one voice: context line THEN the actionable instruction, no traceback
    assert "PSEO context: workspace=" in res.stdout
    assert "project=demo-furniture" in res.stdout
    assert "/pseo-run monthly demo-furniture" in res.stdout
    assert "Traceback" not in res.stderr


def test_main_tier2_supersedes_and_prints_advisory(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    sb.write_session_binding("sid-9", "demo-furniture", ws, "2026-06-05T00:00:00")
    payload = json.dumps({"session_id": "sid-9", "prompt": "merhaba"})
    res = _run_router(payload, home=home, workspace=ws)
    assert res.returncode == 0, res.stderr
    marker = ws / "shared" / "sessions" / "sid-9.intent.json"
    assert marker.exists()
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "superseded"
    assert "PSEO context: workspace=" in res.stdout
    assert "Drift router:" in res.stdout


def test_marker_is_rewritten_each_prompt(tmp_path: Path) -> None:
    """current-turn-only: a Tier-1 declared marker is OVERWRITTEN by a later
    Tier-2 prompt → status flips to superseded (no payload turn_id needed)."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    sb.write_session_binding("sid-rw", "demo-furniture", ws, "2026-06-05T00:00:00")
    marker = ws / "shared" / "sessions" / "sid-rw.intent.json"

    _run_router(json.dumps({"session_id": "sid-rw", "prompt": "aylık bakım yap"}),
                home=home, workspace=ws)
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "declared"

    _run_router(json.dumps({"session_id": "sid-rw", "prompt": "merhaba"}),
                home=home, workspace=ws)
    assert json.loads(marker.read_text(encoding="utf-8"))["status"] == "superseded"


# ---------------------------------------------------------------------------
# 7. main() robustness — never crash, never block, never write a stray marker
# ---------------------------------------------------------------------------

def _no_intent_markers(ws: Path) -> bool:
    sessions = ws / "shared" / "sessions"
    return not (sessions.exists() and list(sessions.glob("*.intent.json")))


@pytest.mark.parametrize("raw", ["", "   ", "not json {{{", "[1, 2, 3]", "null"])
def test_main_empty_or_garbage_stdin_is_advisory_no_marker(tmp_path: Path, raw: str) -> None:
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    res = _run_router(raw, home=home, workspace=ws)
    assert res.returncode == 0
    assert "Drift router:" in res.stdout  # degrades to the advisory
    assert "Traceback" not in res.stderr
    assert _no_intent_markers(ws)  # no session_id → no marker


def test_main_no_workspace_is_advisory_no_marker(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()  # empty: no ~/.config/pseo/config.json, no PSEO_WORKSPACE_ROOT
    payload = json.dumps({"session_id": "S", "prompt": "aylık bakım yap"})
    res = _run_router(payload, home=home, workspace=None)
    assert res.returncode == 0
    assert _EXPECTED_HINT in res.stdout  # DECISION 2: operator always gets a next action
    assert _EXPECTED_ADVISORY in res.stdout
    assert "Traceback" not in res.stderr


def test_main_degraded_prints_hint_then_advisory_no_marker(tmp_path: Path) -> None:
    """DECISION 2: when main() cannot bind (no session_id in the payload) it still
    gives a non-coder operator a next action — the unbound HINT line BEFORE the
    advisory — while writing NO marker and exiting 0."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    # payload carries a prompt but NO session_id → cannot bind → degraded path
    res = _run_router(json.dumps({"prompt": "aylık bakım yap"}), home=home, workspace=ws)
    assert res.returncode == 0
    assert _EXPECTED_HINT in res.stdout
    assert _EXPECTED_ADVISORY in res.stdout
    # the operator reads the next action first: hint precedes the advisory
    assert res.stdout.index(_EXPECTED_HINT) < res.stdout.index(_EXPECTED_ADVISORY)
    assert "Traceback" not in res.stderr
    assert _no_intent_markers(ws)


# ---------------------------------------------------------------------------
# 8. Coverage ported from the retired test_user_prompt_submit_context_injection.py
#    (the router subsumes the old static-bash command — these guard the parts of
#    its contract not already covered above).
# ---------------------------------------------------------------------------

def test_user_prompt_submit_matcher_is_empty_string() -> None:
    """matcher "" → every prompt triggers the router (ported hook-structure check)."""
    spec = json.loads(HOOK_JSON.read_text(encoding="utf-8"))
    assert spec["hooks"]["UserPromptSubmit"][0]["matcher"] == ""


def test_main_active_json_fallback_renders_project_in_context(tmp_path: Path) -> None:
    """Unbound session + shared/active.json present → the context line resolves the
    project via the active.json fallback (ported: 'workspace + active.json → context')."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (ws / "shared" / "active.json").write_text(
        json.dumps({"active_project": "alpha"}), encoding="utf-8"
    )  # NO session marker for sid-af → resolve falls back to active.json
    res = _run_router(json.dumps({"session_id": "sid-af", "prompt": "merhaba"}),
                      home=home, workspace=ws)
    assert res.returncode == 0, res.stderr
    assert "project=alpha" in res.stdout
    assert "Drift router:" in res.stdout  # one voice: context + advisory


def test_main_malformed_active_json_does_not_crash(tmp_path: Path) -> None:
    """Malformed shared/active.json must not crash the router (ported graceful
    degradation): resolution yields no project, the hook still emits + exits 0."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (ws / "shared" / "active.json").write_text("{not valid json", encoding="utf-8")
    res = _run_router(json.dumps({"session_id": "sid-bad", "prompt": "merhaba"}),
                      home=home, workspace=ws)
    assert res.returncode == 0
    assert "Traceback" not in res.stdout
    assert "Traceback" not in res.stderr
    assert "project=<none>" in res.stdout  # unresolved → <none>, no crash
    assert "Drift router:" in res.stdout


# ---------------------------------------------------------------------------
# 9. batch pb0 — mention ≠ request: is_actionable_request + the Tier-1-soft tier
#
#    THE LIVE BUG: the router used to ARM the denetçi (write status='declared')
#    whenever a prompt merely CONTAINED a canonical phrase ("aylık bakım"). It
#    misfired 3× in one session — including on a Path B research prompt whose only
#    crime was discussing "aylık bakım" — nagging /pseo-run for a workflow the
#    operator never asked for. The fix: a canonical match now writes 'declared'
#    (→ denetçi armed) ONLY when the prompt is an actionable REQUEST; a
#    mention/question writes 'superseded' (→ denetçi NOT armed) while still
#    surfacing the command via a soft hint. A genuine command is byte-unchanged.
# ---------------------------------------------------------------------------

# Genuine-request voice that MUST stay byte-identical to pre-pb0 (demo-furniture, bound).
_DECLARED_VOICE_FURNITURE = "➤ Niyet: aylık bakım algılandı → çalıştır: /pseo-run monthly demo-furniture"
# Soft "mentioned, not requested" hint (demo-furniture, bound) — surfaces the command but
# does NOT arm the denetçi.
_SOFT_VOICE_FURNITURE = "ℹ️ 'aylık bakım' geçti — çalıştırmak istersen: /pseo-run monthly demo-furniture"


@pytest.mark.parametrize("prompt, expected", [
    # --- strong actionable signals (each whole-word verb ⇒ True) ---
    ("aylık bakım yap", True),
    ("bunu çalıştır", True),
    ("bunu calistir", True),
    ("şimdi başlat", True),
    ("simdi baslat", True),
    ("hemen koş", True),
    ("hemen kos", True),
    ("verileri çek", True),
    ("verileri cek", True),
    ("rapor üret", True),
    ("rapor uret", True),
    ("içerik oluştur", True),
    ("icerik olustur", True),
    ("planı güncelle", True),
    ("plani guncelle", True),
    ("brief hazırla", True),
    ("brief hazirla", True),
    ("devam et", True),
    ("please resume", True),
    ("please run it", True),
    ("hadi başlatalım", True),
    ("hadi çalıştıralım", True),
    ("yapar mısın", True),                 # polite request WITHOUT a '?'
    ("/pseo-run monthly demo-furniture", True),     # explicit command token
    # --- question / discussion signals (each ⇒ False, OVERRIDES verbs) ---
    ("aylık bakım nedir?", False),
    ("bu ne demek", False),
    ("ne işe yarar", False),
    ("nasıl çalışır", False),
    ("nasil calisir", False),
    ("neden böyle", False),
    ("niçin", False),
    ("nicin", False),
    ("bunun hakkında", False),
    ("bunun hakkinda", False),
    ("aylık bakımı açıkla", False),
    ("bunu acikla", False),
    ("bana anlat", False),
    ("şunu araştır", False),
    ("sunu arastir", False),
    ("şunu incele", False),
    ("çalıştırdın mı?", False),
    ("doğru mu?", False),
    ("bu mu?", False),
    ("öyle mü?", False),
    ("fark ne", False),
    ("ne zaman olur", False),
    ("geçerli midir", False),
    ("geçerli mıdır", False),
    # --- precedence: a question marker WINS over an actionable verb ---
    ("aylık bakımı açıkla ve çalıştır", False),  # 'açıkla' beats 'çalıştır'
    ("aylık bakımı çalıştır mı?", False),        # trailing '?' beats 'çalıştır'
    # --- word-boundary discipline: 'yap' must NOT match 'yapay' (AI), 'run'
    #     must NOT match 'running' — these are the dangerous false-positives ---
    ("yapay zeka ile aylık bakım planı", False),
    ("the script is running", False),
    # --- empty / mention / non-str ⇒ False ---
    ("", False),
    ("   ", False),
    ("merhaba", False),
    ("aylık bakım", False),                # bare MENTION: no verb, no question
    (None, False),
    (123, False),
])
def test_is_actionable_request_table(prompt, expected) -> None:
    assert router.is_actionable_request(prompt) is expected


# ---- route: a MENTION/question of a canonical workflow → soft + superseded ----

def test_route_mention_research_prompt_is_soft_superseded(tmp_path: Path) -> None:
    """The live false-positive, locked: a Path B research prompt that merely
    DISCUSSES 'aylık bakım' must write a SUPERSEDED marker (denetçi NOT armed) and
    emit the soft hint — NOT the '➤ Niyet … çalıştır' declared voice."""
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-soft", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "path b araştırması: aylık bakım router'ı nasıl çalışıyor inceleyelim",
        session_id="sess-soft",
        workspace_root=ws,
        turn_id="t1",
        intent_id="i1",
        declared_at="2026-06-05T10:00:00",
    )
    m = result["marker"]
    assert m["status"] == "superseded"            # ← the fix: nothing owed
    assert "workflow" not in m and "command" not in m
    assert result["voice"] == _SOFT_VOICE_FURNITURE   # helpful surfacing of the command
    assert "➤ Niyet" not in result["voice"]       # NOT the declared actionable voice
    _validator().validate(m)


@pytest.mark.parametrize("prompt", [
    "aylık bakım nedir?",
    "monthly maintenance workflow'unu açıkla",
    "aylık bakım ne işe yarar",
])
def test_route_question_mentions_are_soft_superseded(tmp_path: Path, prompt: str) -> None:
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-q", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        prompt, session_id="sess-q", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == "1-soft"
    assert result["marker"]["status"] == "superseded"
    assert result["voice"] == _SOFT_VOICE_FURNITURE
    _validator().validate(result["marker"])


def test_route_soft_unbound_uses_slug_placeholder(tmp_path: Path) -> None:
    """A mention in an UNBOUND session still surfaces the command, with the
    <slug> placeholder (never a fabricated slug), and stays superseded."""
    ws = _workspace(tmp_path)  # no binding → unbound
    result = router.route(
        "aylık bakım nedir?", session_id="sess-ub", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == "1-soft"
    assert result["marker"]["status"] == "superseded"
    assert result["voice"] == "ℹ️ 'aylık bakım' geçti — çalıştırmak istersen: /pseo-run monthly <slug>"
    _validator().validate(result["marker"])


# ---- route: a GENUINE request stays Tier-1 declared, byte-identical voice ----

@pytest.mark.parametrize("prompt", [
    "demo-furniture'da aylık bakım yap",
    "aylık bakımı çalıştır",
    "aylık bakım başlat",
])
def test_route_genuine_requests_stay_declared(tmp_path: Path, prompt: str) -> None:
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-req", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        prompt, session_id="sess-req", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 1
    m = result["marker"]
    assert m["status"] == "declared"
    assert m["workflow"] == "monthly"
    assert m["command"] == "/pseo-run monthly demo-furniture"


def test_route_declared_voice_is_byte_identical(tmp_path: Path) -> None:
    """The genuine-request Tier-1 voice is UNCHANGED from pre-pb0 behaviour."""
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-bi", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "demo-furniture'da aylık bakım yap", session_id="sess-bi", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 1
    assert result["voice"] == _DECLARED_VOICE_FURNITURE


def test_route_bare_slash_command_is_tier2_advisory(tmp_path: Path) -> None:
    """DISCREPANCY FLAGGED TO MANAGER: the worker-prompt lists '/pseo-run monthly
    demo-furniture' as a 'declared' regression, but classify() matches on the canonical
    PHRASE ('aylık bakım' / 'monthly maintenance'), which this string does NOT
    contain → it is Tier-2 (advisory + superseded), not Tier-1. is_actionable_
    request() correctly sees it as actionable (see the table), but route() never
    reaches the actionability gate because classify() returns None first.

    This is HARMLESS: typing the slash command runs the workflow THIS turn, so the
    denetçi sees coverage and would allow turn-end even if it were declared.
    Making it Tier-1 would require adding a '/pseo-run monthly' classify pattern
    (a CANONICAL_WORKFLOWS change), which is out of this batch's scope. Pinned so
    any future classify change to this is a DELIBERATE update."""
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-slash", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "/pseo-run monthly demo-furniture", session_id="sess-slash", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 2
    assert result["marker"]["status"] == "superseded"
    assert result["voice"] == _EXPECTED_ADVISORY
    # the predicate itself is correct — the miss is in classify, not actionability
    assert router.is_actionable_request("/pseo-run monthly demo-furniture") is True


def test_route_no_match_is_unchanged_tier2(tmp_path: Path) -> None:
    """Regression: a prompt with NO canonical phrase is still Tier-2 advisory."""
    ws = _workspace(tmp_path)
    sb.write_session_binding("sess-nm", "demo-furniture", ws, "2026-06-05T00:00:00")
    result = router.route(
        "merhaba nasılsın", session_id="sess-nm", workspace_root=ws,
        turn_id="t", intent_id="i", declared_at="2026-06-05T10:00:00",
    )
    assert result["tier"] == 2
    assert result["marker"]["status"] == "superseded"
    assert result["voice"] == _EXPECTED_ADVISORY


# ---- main() end-to-end via subprocess: mention → no declared marker on disk ----

def test_main_mention_writes_superseded_not_declared(tmp_path: Path) -> None:
    """E2E at the process boundary: a payload that only MENTIONS the workflow
    writes a SUPERSEDED marker (denetçi NOT armed) and prints the soft hint."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    sb.write_session_binding("sid-m", "demo-furniture", ws, "2026-06-05T00:00:00")
    res = _run_router(
        json.dumps({"session_id": "sid-m", "prompt": "aylık bakım nedir?"}),
        home=home, workspace=ws,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads((ws / "shared" / "sessions" / "sid-m.intent.json").read_text(encoding="utf-8"))
    assert data["status"] == "superseded"          # NOT 'declared'
    assert "istersen" in res.stdout                # the soft hint surfaced
    assert "/pseo-run monthly demo-furniture" in res.stdout  # …with the runnable command
    assert "Niyet" not in res.stdout               # NOT the declared voice
    assert "Traceback" not in res.stderr


def test_main_request_writes_declared_marker(tmp_path: Path) -> None:
    """E2E: a genuine request payload still writes a 'declared' marker (the
    denetçi-arming half is preserved for real intents)."""
    ws = _workspace(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    sb.write_session_binding("sid-r", "demo-furniture", ws, "2026-06-05T00:00:00")
    res = _run_router(
        json.dumps({"session_id": "sid-r", "prompt": "demo-furniture'da aylık bakım yap"}),
        home=home, workspace=ws,
    )
    assert res.returncode == 0, res.stderr
    data = json.loads((ws / "shared" / "sessions" / "sid-r.intent.json").read_text(encoding="utf-8"))
    assert data["status"] == "declared"
    assert data["command"] == "/pseo-run monthly demo-furniture"
    assert "/pseo-run monthly demo-furniture" in res.stdout
    assert "Traceback" not in res.stderr
