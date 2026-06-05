"""tests/hooks/test_active_project_contract.py — active.json field-name contract (ADR-032).

Both hooks that need the active project now DELEGATE its resolution to
scripts/state/session_binding (per-session marker → canonical `active_project`
fallback) instead of parsing active.json INLINE:

  * post-tool-use.json   → scripts/hooks/audit_post_tool_use.py   (AMO batch 0d)
  * user-prompt-submit.json → scripts/hooks/intent_router.py      (AMO batch 1c)

So the ADR-032 canonical-field guard ('active_project', never the legacy
'project_id') now lives at the DELEGATION boundary: each hook wires its script,
no command reads active.json inline, and session_binding reads the canonical
field. This file locks that contract for BOTH hooks.

History: the file used to parametrize a `test_hook_reads_active_project_field`
over an `ACTIVE_READERS` tuple of hooks that parsed active.json INLINE. Batch 0d
removed post-tool-use.json from it; batch 1c removed the last entry
(user-prompt-submit.json) when the intent router subsumed the static-bash reader,
so the inline-reader test became vacuous and was replaced by the per-hook
delegation tests below — the canonical-field assertion is preserved inside them.
(session-start.json only `cat`s active.json for display; it does not parse the
field, so it is not a field-reader and is intentionally not covered here.)
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "hooks"
SESSION_BINDING = REPO_ROOT / "scripts" / "state" / "session_binding.py"


def _command_strings(hook_filename: str) -> list[str]:
    """All command-type command strings declared by a hooks/*.json file."""
    spec = json.loads((HOOKS_DIR / hook_filename).read_text(encoding="utf-8"))
    return [
        h["command"]
        for handlers in spec["hooks"].values()
        for handler in handlers
        for h in handler["hooks"]
        if h.get("type") == "command"
    ]


def _assert_delegates(hook_filename: str, script_rel: str, script_token: str) -> None:
    """Lock one hook's delegation contract: it wires `script_rel`, reads NO
    active.json inline, and the script resolves the project via session_binding's
    canonical `active_project` field (never the legacy `project_id`) — ADR-032."""
    commands = _command_strings(hook_filename)
    assert any(script_token in c for c in commands), f"{hook_filename} must wire {script_rel}"
    assert not any("active.json" in c for c in commands), (
        f"{hook_filename} should delegate active.json resolution to {script_rel}, "
        f"not read it inline"
    )
    script = (REPO_ROOT / script_rel).read_text(encoding="utf-8")
    assert "resolve_session_project" in script, (
        f"{script_rel} must delegate to session_binding.resolve_session_project"
    )
    binding = SESSION_BINDING.read_text(encoding="utf-8")
    assert '"active_project"' in binding, "session_binding must read canonical active_project"
    assert '"project_id"' not in binding, (
        "session_binding must not read the legacy project_id field from active.json (ADR-032)"
    )


def test_post_tool_use_delegates_active_project_to_session_binding() -> None:
    """post-tool-use.json delegates active.json resolution to the batch-0d audit
    script + session_binding — canonical `active_project`, never legacy. ADR-032."""
    _assert_delegates(
        "post-tool-use.json",
        "scripts/hooks/audit_post_tool_use.py",
        "audit_post_tool_use.py",
    )


def test_user_prompt_submit_delegates_active_project_to_session_binding() -> None:
    """user-prompt-submit.json command #0 invokes the batch-1c intent router, which
    MOVED the active-project read out of the static-bash command and into the
    script (it delegates to session_binding). ADR-032 contract preserved at the
    new boundary; this is the same migration batch 0d did for post-tool-use.json."""
    spec = json.loads((HOOKS_DIR / "user-prompt-submit.json").read_text(encoding="utf-8"))
    cmd0 = spec["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "intent_router.py" in cmd0, (
        "UserPromptSubmit command #0 must invoke scripts/hooks/intent_router.py"
    )
    _assert_delegates(
        "user-prompt-submit.json",
        "scripts/hooks/intent_router.py",
        "intent_router.py",
    )
