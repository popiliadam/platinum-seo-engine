"""Per-class secret-redaction parity for events_writer (hostile-audit #3).

Finding #3: ``events_writer._SECRET_VALUE_PATTERNS`` redacted only a handful of
classes (openai/anthropic ``sk-``, ``ghp_``/``github_pat_``, ``AKIA``) and
silently PERSISTED several classes the canonical scanner
(``scripts/security/check_secrets.sh``) knows — Google ``AIza``, Slack ``xox``,
GCP service-account fields, PEM/RSA/OPENSSH private-key headers, ``gho/ghs/ghu``.
An audit/provenance event could therefore store a secret the repo claims to
detect.

Single source of truth: the canonical inventory is the 17-label ``PATTERN_NAMES``
array in ``scripts/security/check_secrets.sh``. Python redaction cannot shell out
per event, so it MIRRORS that inventory; this test is the anti-drift tripwire:

  1. ``test_enumeration_matches_canonical_pattern_names`` — the per-class
     enumeration below must equal the scanner's label set, so a 17th canonical
     pattern FAILS this test until events_writer + this enumeration grow too.
  2. ``test_event_metadata_redacts_<class>`` — every class is redacted out of a
     persisted event's free-text field.
  3. ``test_canonical_scanner_flags_<class>`` — the SAME synthetic bytes are
     flagged by the canonical scanner, tying the two surfaces together.

Every secret is built DYNAMICALLY (concat/format) so the repo's own scanners
(CI git-grep + canonical full-mode, which do NOT exclude this file) never see a
contiguous watched token in these bytes.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from scripts.state import events_writer
from scripts.state.events_writer import append_provenance

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "scripts" / "security" / "check_secrets.sh"


# ---------------------------------------------------------------------------
# Synthetic secrets — one per canonical PATTERN_NAMES label. Built at runtime
# from fragments so neither the CI wrapper nor the canonical full-scan flags
# THIS file (the bytes only become a contiguous token in memory).
# ---------------------------------------------------------------------------
_BEGIN = "-----BEGIN "
_END = " KEY-----"


def _secrets() -> dict[str, str]:
    return {
        "google_api_key_AIza": "AIza" + "B" * 35,
        "openai_or_anthropic_sk_prefix": "sk-" + "C" * 30,
        "gcp_service_account_json_private_key_field": (
            '"private_key": "' + _BEGIN + "PRIVATE" + _END + "MIIabc"
        ),
        "pem_private_key_header": _BEGIN + "PRIVATE" + _END,
        "rsa_private_key_header": _BEGIN + "RSA PRIVATE" + _END,
        "openssh_private_key_header": _BEGIN + "OPENSSH PRIVATE" + _END,
        "gcp_service_account_client_email": (
            '"client_email": "svc-bot@my-proj' + ".iam." + "gserviceaccount"
            + ".com" + '"'
        ),
        "github_pat_classic_ghp": "ghp_" + "d" * 36,
        "github_oauth_token_gho": "gho_" + "e" * 36,
        "github_server_token_ghs": "ghs_" + "f" * 36,
        "github_user_token_ghu": "ghu_" + "g" * 36,
        "aws_access_key_id_line": "aws_access_key_id=" + "A" * 20,
        "aws_secret_access_key_line": "aws_secret_access_key=" + "h" * 40,
        "aws_akia_key_literal": "AKIA" + "I" * 16,
        "slack_token_xox": "xox" + "b-" + "D" * 22,
        "dataforseo_env_hardcoded_literal": (
            "DATAFORSEO_" + "PASSWORD" + "=" + chr(34) + "p" * 10 + chr(34)
        ),
        # FIX-S S2: secret-ish key + quoted, '='-padded base64 value (>=24 b64
        # chars). Built from fragments so no contiguous token lands on disk.
        "base64_high_entropy_secret_assignment": (
            "secret = " + chr(34) + "QUJDREVGR0hJSktMTU5P" + "UFFSU1RVVldYWVo=" + chr(34)
        ),
    }


def _canonical_pattern_names() -> list[str]:
    """Extract the PATTERN_NAMES array (the canonical inventory labels)."""
    body = CANONICAL.read_text(encoding="utf-8")
    m = re.search(r"PATTERN_NAMES=\((.*?)\)", body, re.S)
    assert m, "PATTERN_NAMES array not found in canonical scanner"
    return re.findall(r'"([^"]+)"', m.group(1))


def _persist_note(tmp_path: Path, secret: str) -> str:
    """Append a provenance event carrying ``secret`` in free-text notes; return
    the persisted (post-redaction) notes value."""
    (tmp_path / "projects" / "p" / "_state").mkdir(parents=True, exist_ok=True)
    result = append_provenance(
        project_id="p",
        run_id=1,
        source={"kind": "manual"},
        operation="ingest",
        notes=f"leaked={secret} end",
        workspace_root=tmp_path,
    )
    ev = json.loads(result.path.read_text(encoding="utf-8").strip().splitlines()[-1])
    return ev["notes"]


# ---------------------------------------------------------------------------
# 1) Drift tripwire — enumeration must equal the canonical label set.
# ---------------------------------------------------------------------------

def test_enumeration_matches_canonical_pattern_names() -> None:
    enumerated = set(_secrets())
    canonical = set(_canonical_pattern_names())
    assert enumerated == canonical, (
        "events_writer redaction parity enumeration drifted from the canonical "
        f"scanner inventory.\n  only in scanner: {sorted(canonical - enumerated)}"
        f"\n  only in test:    {sorted(enumerated - canonical)}\n"
        "Add the new class to events_writer._SECRET_VALUE_PATTERNS AND this map."
    )


# ---------------------------------------------------------------------------
# 2) Redaction — every canonical class is scrubbed from event metadata.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", list(_secrets()))
def test_event_metadata_redacts_class(label: str, tmp_path: Path) -> None:
    secret = _secrets()[label]
    persisted = _persist_note(tmp_path, secret)
    assert secret not in persisted, (
        f"class {label!r} PERSISTED unredacted in event metadata: {persisted!r}"
    )
    assert events_writer._REDACTED in persisted, (
        f"class {label!r} not replaced with the redaction sentinel"
    )


# ---------------------------------------------------------------------------
# 3) Cross-surface tie — the SAME bytes are flagged by the canonical scanner,
#    so "events_writer redacts X" and "the scanner detects X" stay in lockstep.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", list(_secrets()))
def test_canonical_scanner_flags_class(label: str) -> None:
    secret = _secrets()[label]
    proc = subprocess.run(
        ["bash", str(CANONICAL), "--scan-stdin", "outputs/x.txt"],
        input=f"value={secret}\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 1, (
        f"canonical scanner did NOT flag class {label!r} (synthetic secret may be "
        f"malformed):\n{proc.stdout}\n{proc.stderr}"
    )
    assert secret not in proc.stdout, "scanner must never echo matched content"
