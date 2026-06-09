#!/usr/bin/env python3
"""scripts/hooks/intent_router.py — AMO L1 UserPromptSubmit intent router.

AMO's intent guarantee: when an operator states a KNOWN intent ("alpha'da aylık
bakım yap"), the right workflow is GUARANTEED to engage. This is the L1 half — a
UserPromptSubmit hook that classifies the prompt and, for a canonical match,
both NUDGES the model (its stdout is injected into the model context) and records
an ``intent_declared`` marker the batch-2c Stop denetçi can audit.

Two tiers (see ``classify`` / ``route``):
  * Tier-1 — the prompt canonically names ONE known workflow → inject a one-line
    "invoke /pseo-run <workflow> <slug>" instruction AND write the intent marker
    with status='declared'. (If the session is unbound the intent is still
    declared, but the voice tells the user to /pseo-bind first and the marker
    omits slug — we never fabricate one.)
  * Tier-2 — no match, or >=2 workflows collide → fall back to the existing
    whats-next advisory only, and write the marker with status='superseded' so a
    stale cross-turn intent never blocks the denetçi.

This is the SINGLE voice per prompt: it REPLACES the old static-bash command that
echoed the "PSEO context:" line + the Drift-router advisory, so it re-emits the
context line itself (do not lose it). The env_probe.py command entry (batch 0a)
stays alongside it untouched.

Confirmed facts (manager-verified, batch 0a/0b — not re-derived here):
  * The only proven payload binding key is ``session_id``. There is NO per-turn
    id, so the router ASSIGNS turn_id + intent_id itself (generated in main(),
    passed PURE into route()). "Current-turn only" is delivered structurally —
    ONE marker per session, REWRITTEN every prompt, so it always reflects the
    current turn without a payload turn_id.
  * Resolution + atomic write are REUSED from scripts/state/session_binding.py
    (resolve_session_project / resolve_workspace_root / current_session_id /
    sessions_dir / _atomic_write_json); this module adds no new IO primitive.

Non-blocking contract (mirrors scripts/hooks/audit_post_tool_use.py): main() is
wrapped so ANY internal error degrades to the advisory + exit 0. The router must
NEVER crash the hook chain and NEVER block a prompt.

The denetçi (batch 2c) and /pseo-run (batch 1d) are SEPARATE later batches; this
module builds the router + the marker contract + the one-voice wiring ONLY.

Wired as a runtime hook in hooks/user-prompt-submit.json; classified RUNTIME in
tests/hooks/test_hook_scripts_runtime_vs_ci.py + scripts/hooks/README.md.
Authority: schemas/intent-marker.schema.json, batch 0a probe, batch 0b binding.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Make ``scripts.*`` importable when run as a bare hook subprocess
# (mirrors scripts/hooks/audit_post_tool_use.py).
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(
    Path(__file__).resolve().parents[2]
)
if _PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT)

from scripts.state.session_binding import (  # noqa: E402
    _atomic_write_json,
    _is_safe_session_id,
    current_session_id,
    resolve_session_project,
    resolve_workspace_root,
    sessions_dir,
)

# ---------------------------------------------------------------------------
# Canonical workflow table — data-driven so Phase 3 adds workflows with NO code
# change. A 2nd entry whose patterns also match a prompt makes ``classify``
# return None (collision → Tier-2, advisory-only) automatically. Patterns are
# lowercased phrases; matching is substring on the lowercased prompt, so each
# pattern must be SPECIFIC enough not to false-Tier-1 on an unrelated prompt.
# ---------------------------------------------------------------------------
CANONICAL_WORKFLOWS: dict[str, dict] = {
    "monthly": {
        "label": "aylık bakım",  # operator-facing name for the injected voice
        "patterns": [
            "aylık bakım",
            "aylik bakim",
            "aylık bakim",
            "aylik bakım",
            "monthly maintenance",
        ],
        "command": "/pseo-run monthly {slug}",
    },
}

_STATUSES = ("declared", "superseded", "consumed")
_SLUG_PLACEHOLDER = "<slug>"
_EXCERPT_CAP = 160

# ---------------------------------------------------------------------------
# mention ≠ request (batch pb0) — a canonical phrase only ARMS the denetçi when
# the prompt is an actionable REQUEST, not a mention/question. Two data-driven,
# trivially-extendable token sets feed is_actionable_request. The cost is
# ASYMMETRIC (a false-positive nags a workflow nobody asked for; a false-negative
# just makes the operator type the command), so the two sets are matched with
# DELIBERATELY different strictness:
#   * actionable verbs → STRICT whole-word match (re word-boundary). Short tokens
#     like "yap" must NOT fire on "yapay" (AI / yapay zeka) and "run" must NOT
#     fire on "running"; whole-word matching is what keeps the false-positive
#     rate near zero. Turkish is agglutinative, so an inflected verb ("çalıştır"
#     in "çalıştırın") will MISS — that is the cheap, intended false-negative.
#   * question/discussion markers → LENIENT substring match. Over-catching a
#     discussion only routes to the safe (non-arming) soft tier, so breadth here
#     is free. These are NOT a grammar — just enough Turkish+English surface
#     markers to recognise "this is a question/mention" (spec §6: no NL grammar).
# Lists are heuristic and Turkish-morphology-imperfect BY DESIGN; extend by
# adding tokens, never by trying to parse.
# ---------------------------------------------------------------------------
_ACTIONABLE_TOKENS: frozenset[str] = frozenset({
    "/pseo-run",  # the explicit command token
    # imperative / request verbs (TR + EN); ASCII folds listed alongside accents
    "yap", "yapar mısın", "yapar misin", "çalıştır", "calistir",
    "başlat", "baslat", "koş", "kos", "çek", "cek", "üret", "uret",
    "oluştur", "olustur", "güncelle", "guncelle", "hazırla", "hazirla",
    "devam et", "resume", "run", "başlatalım", "baslatalim",
    "çalıştıralım", "calistiralim",
})

_QUESTION_MARKERS: frozenset[str] = frozenset({
    "nedir", "ne demek", "ne işe", "ne ise", "nasıl", "nasil", "neden",
    "niçin", "nicin", "hakkında", "hakkinda", "açıkla", "acikla", "anlat",
    "araştır", "arastir", "incele", "mı?", "mi?", "mu?", "mü?",
    "mı ?", "mi ?", "mu ?", "mü ?", "fark ne", "ne zaman",
    "mıdır", "midir", "mudur", "müdür",
})

# The advisory preserved BYTE-FOR-BYTE from the old static-bash command #1.
_ADVISORY = (
    "Drift router: when uncertain about next step invoke the meta:whats-next "
    "skill (Phase 5+) — until then consult docs/PHASE_STATUS.md."
)

_CONTEXT_PREFIX = "PSEO context:"

# Operator-remediation hint emitted on the degraded path (cannot bind: no
# session_id / no workspace / unsafe id). A non-coder operator must always get a
# next action. Repo-canonical wording — identical to the old static-bash unbound
# branch + session-start.json (/pseo-init is the real scaffolder per P1-05).
_UNBOUND_HINT = (
    f"{_CONTEXT_PREFIX} no active project bound — run /pseo-init or set PSEO_WORKSPACE_ROOT"
)


# ---------------------------------------------------------------------------
# Pure classification + marker building (no IO)
# ---------------------------------------------------------------------------

def classify(prompt: str) -> tuple[str | None, list[str]]:
    """Return (workflow_key_or_None, matched_keys) for ``prompt``.

    Exactly ONE matching workflow → Tier-1 (that key). ZERO matches → Tier-2
    (None, []). >=2 distinct workflows match → Tier-2 (None, [...]) — a collision
    is advisory-only per spec; the matched list is returned so the caller can log
    it. Pure; matches on the lowercased prompt.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return (None, [])
    normalized = prompt.lower()
    matched = [
        key
        for key, spec in CANONICAL_WORKFLOWS.items()
        if any(pattern in normalized for pattern in spec["patterns"])
    ]
    if len(matched) == 1:
        return (matched[0], matched)
    return (None, matched)


def _has_actionable_token(normalized: str) -> bool:
    """Whole-word (re word-boundary) match of any actionable verb / command token.

    Word-boundary — NOT substring — so "yap" does not fire on "yapay" and "run"
    does not fire on "running". ``\\w`` is Unicode-aware on ``str`` patterns, so
    Turkish letters (ç ş ğ ı ü ö İ) count as word chars and bound correctly.
    """
    return any(
        re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", normalized)
        for token in _ACTIONABLE_TOKENS
    )


def _is_question(normalized: str) -> bool:
    """True if the prompt is a question / discussion (trailing '?' or any marker).

    Lenient substring match (the asymmetric-cost choice: over-catching only routes
    to the safe, non-arming soft tier). ``normalized`` is already stripped+lowered.
    """
    if normalized.endswith("?"):
        return True
    return any(marker in normalized for marker in _QUESTION_MARKERS)


def is_actionable_request(prompt: str) -> bool:
    """True iff ``prompt`` is an actionable REQUEST to run a workflow (vs a mere
    mention / question). PURE, no IO. Deterministic, data-driven, conservative,
    and biased to ``False`` on ambiguity — a false-negative just makes the operator
    type the command (cheap); a false-positive nags a workflow nobody asked for
    (expensive).

    Decision order (PRECEDENCE: a question marker WINS over an actionable verb, so
    "aylık bakımı açıkla" is a question, never a run request):
      1. normalise (strip + lower); empty / non-str → False.
      2. if it is a question/discussion (``_is_question``) → False — this overrides
         any actionable verb present.
      3. else if it carries a strong actionable signal (``_has_actionable_token``)
         → True.
      4. otherwise → False.
    """
    if not isinstance(prompt, str):
        return False
    normalized = prompt.strip().lower()
    if not normalized:
        return False
    if _is_question(normalized):  # step 2 — precedence over actionable verbs
        return False
    return _has_actionable_token(normalized)


def _truncate_excerpt(text: str) -> str:
    """Whitespace-collapse + hard-truncate to a redaction-safe audit excerpt."""
    return " ".join(str(text).split())[:_EXCERPT_CAP]


def build_marker(
    session_id: str,
    *,
    turn_id: str,
    intent_id: str,
    status: str,
    declared_at: str,
    workflow: str | None = None,
    slug: str | None = None,
    command: str | None = None,
    prompt_excerpt: str | None = None,
) -> dict:
    """Build an intent marker dict, emitting ONLY declared keys.

    ``additionalProperties:false`` in the schema means optionals are added only
    when not None. Required keys (session_id/turn_id/intent_id/status/
    declared_at) plus schema_version are always present. Defensive enum check on
    status (the router never writes a free-form status).
    """
    if status not in _STATUSES:
        raise ValueError(f"invalid status (must be one of {_STATUSES}): {status!r}")
    marker: dict = {
        "schema_version": "1.0",
        "session_id": session_id,
        "turn_id": turn_id,
        "intent_id": intent_id,
        "status": status,
        "declared_at": declared_at,
    }
    if workflow is not None:
        marker["workflow"] = workflow
    if slug is not None:
        marker["slug"] = slug
    if command is not None:
        marker["command"] = command
    if prompt_excerpt is not None:
        marker["prompt_excerpt"] = _truncate_excerpt(prompt_excerpt)
    return marker


def intent_marker_path(workspace_root: Path, session_id: str) -> Path:
    """``{ws}/shared/sessions/{session_id}.intent.json`` (beside the binding marker)."""
    return sessions_dir(workspace_root) / f"{session_id}.intent.json"


# ---------------------------------------------------------------------------
# Voices (stdout — the hook's product)
# ---------------------------------------------------------------------------

def _tier1_voice(label: str, command: str, *, bound: bool) -> str:
    """The one-line, model-actionable Tier-1 instruction (operator-facing TR)."""
    if bound:
        return f"➤ Niyet: {label} algılandı → çalıştır: {command}"
    return (
        f"➤ Niyet: {label} algılandı, ama oturum bir projeye bağlı değil "
        f"→ önce: /pseo-bind {_SLUG_PLACEHOLDER}"
    )


def _soft_voice(label: str, command: str) -> str:
    """The Tier-1-soft hint: the workflow was MENTIONED, not requested. Surfaces
    how to run it (the helpful half) WITHOUT the imperative '➤ … çalıştır' framing
    of the declared voice — and crucially without arming the denetçi."""
    return f"ℹ️ '{label}' geçti — çalıştırmak istersen: {command}"


def _context_line(workspace_root: Path, slug: str | None) -> str:
    """Re-emit the old static-bash context line (one voice)."""
    return f"{_CONTEXT_PREFIX} workspace={workspace_root} project={slug or '<none>'}"


# ---------------------------------------------------------------------------
# Pure core — classify, resolve, decide tier, build marker + voice (NO write)
# ---------------------------------------------------------------------------

def _tier1_result(
    workflow: str,
    *,
    session_id: str,
    slug: str | None,
    turn_id: str,
    intent_id: str,
    declared_at: str,
    prompt: str,
    matched: list[str],
) -> dict:
    """Build the Tier-1 (intent declared) result: declared marker + actionable voice."""
    command = CANONICAL_WORKFLOWS[workflow]["command"].format(slug=slug or _SLUG_PLACEHOLDER)
    marker = build_marker(
        session_id,
        turn_id=turn_id,
        intent_id=intent_id,
        status="declared",
        declared_at=declared_at,
        workflow=workflow,
        slug=slug,  # None → omitted by build_marker (unbound: no fabricated slug)
        command=command,
        prompt_excerpt=prompt,
    )
    voice = _tier1_voice(CANONICAL_WORKFLOWS[workflow]["label"], command, bound=slug is not None)
    return {"marker": marker, "voice": voice, "tier": 1, "matched": matched, "slug": slug}


def _tier1_soft_result(
    workflow: str,
    *,
    session_id: str,
    slug: str | None,
    turn_id: str,
    intent_id: str,
    declared_at: str,
    matched: list[str],
) -> dict:
    """Build the Tier-1-soft (mentioned, NOT requested) result.

    The workflow was named but the prompt is a mention/question — surface the
    command via the soft voice, but write a ``superseded`` marker (same minimal
    shape as Tier-2) so the denetçi is NOT armed for a workflow nobody asked for.
    The command is rendered into the VOICE only; it is never stored on a
    superseded marker (the denetçi reads ``status`` alone — denetci.py:145)."""
    command = CANONICAL_WORKFLOWS[workflow]["command"].format(slug=slug or _SLUG_PLACEHOLDER)
    marker = build_marker(
        session_id, turn_id=turn_id, intent_id=intent_id,
        status="superseded", declared_at=declared_at,
    )
    voice = _soft_voice(CANONICAL_WORKFLOWS[workflow]["label"], command)
    return {"marker": marker, "voice": voice, "tier": "1-soft", "matched": matched, "slug": slug}


def route(
    prompt: str,
    *,
    session_id: str,
    workspace_root: Path | None,
    turn_id: str,
    intent_id: str,
    declared_at: str,
) -> dict:
    """Decide the tier and produce the marker + voice for one prompt.

    Returns {"marker", "voice", "tier", "matched" (list), "slug"} — PURE; the
    caller writes the marker file + prints the voice. ``slug`` is the resolved
    project (may be None) for the caller's context line, independent of tier.

    Three outcomes (``tier``):
      * ``1``        — a canonical workflow is named AND the prompt is an
                       actionable REQUEST → ``declared`` marker (ARMS the denetçi)
                       + the actionable '➤ … çalıştır' voice. UNCHANGED from pre-pb0.
      * ``"1-soft"`` — a canonical workflow is named but the prompt only MENTIONS /
                       asks about it → ``superseded`` marker (denetçi NOT armed) +
                       a soft hint that still surfaces the command. THE pb0 fix.
      * ``2``        — no canonical match / collision → ``superseded`` + the
                       whats-next advisory. UNCHANGED from pre-pb0.
    """
    workflow, matched = classify(prompt)
    slug: str | None = None
    if workspace_root is not None:
        slug = resolve_session_project(workspace_root, session_id=session_id, strict=False)

    if workflow is not None and is_actionable_request(prompt):  # Tier-1: declared
        return _tier1_result(
            workflow, session_id=session_id, slug=slug, turn_id=turn_id,
            intent_id=intent_id, declared_at=declared_at, prompt=prompt, matched=matched,
        )

    if workflow is not None:  # Tier-1-soft: mentioned, not requested → do NOT arm
        return _tier1_soft_result(
            workflow, session_id=session_id, slug=slug, turn_id=turn_id,
            intent_id=intent_id, declared_at=declared_at, matched=matched,
        )

    # Tier-2: no match / collision → supersede any prior declared intent.
    marker = build_marker(
        session_id, turn_id=turn_id, intent_id=intent_id,
        status="superseded", declared_at=declared_at,
    )
    return {"marker": marker, "voice": _ADVISORY, "tier": 2, "matched": matched, "slug": slug}


# ---------------------------------------------------------------------------
# Thin, never-crashing main (generates ids/timestamps; does the IO)
# ---------------------------------------------------------------------------

def _read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:  # cannot read stdin → caller degrades to the advisory
        return ""


def _parse_payload(raw: str) -> dict:
    """Parse hook stdin → dict; empty / malformed / non-object → {} (never raises)."""
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _new_turn_id(now_iso: str) -> str:
    """Router-assigned ordering stamp: timestamp (orderable) + random suffix (unique)."""
    return f"{now_iso}-{uuid4().hex[:8]}"


def main() -> int:
    """Emit one voice for this prompt; write the intent marker on Tier-1/Tier-2.

    NEVER crashes the hook chain: any error degrades to the advisory + exit 0.
    """
    try:
        payload = _parse_payload(_read_stdin())
        session_id = current_session_id(payload)
        workspace_root = resolve_workspace_root()
        if not session_id or workspace_root is None or not _is_safe_session_id(session_id):
            # Cannot bind → still give the operator a next action, then the advisory.
            print(_UNBOUND_HINT)
            print(_ADVISORY)
            return 0
        now_iso = datetime.now().isoformat()
        result = route(
            payload.get("prompt") or "",
            session_id=session_id,
            workspace_root=workspace_root,
            turn_id=_new_turn_id(now_iso),
            intent_id=uuid4().hex,
            declared_at=now_iso,
        )
        _atomic_write_json(intent_marker_path(workspace_root, session_id), result["marker"])
        print(_context_line(workspace_root, result["slug"]))
        print(result["voice"])
        return 0
    except Exception:  # never block a prompt — the advisory is the safe fallback
        print(_ADVISORY)
        return 0


if __name__ == "__main__":
    sys.exit(main())
