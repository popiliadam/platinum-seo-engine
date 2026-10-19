"""K-11 — the canonical secret scanner catches the formats it used to miss.

Every token below is assembled at runtime from harmless pieces, so this file
itself never contains a secret-shaped literal (the pending-write scanner would
refuse to save it, and the repo scan must stay green). Each format has a
positive case (must be RED) and the task-id / placeholder style negatives must
stay GREEN.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scripts" / "security" / "check_secrets.sh"

A = "A" * 16
X40 = "abcdEFGH" * 5
B64 = "QWxhZGRpbjpvcGVuIHNlc2FtZQ"


def _scan(text: str) -> int:
    proc = subprocess.run(["bash", str(SCANNER), "--scan-stdin", "notes.txt"],
                          input=text.encode(), capture_output=True, cwd=ROOT, timeout=60)
    return proc.returncode


POSITIVE = {
    "aws_temporary_key_asia": "ASI" + "A" + A,
    "aws_secret_access_key_env": "AWS_SECRET" + "_ACCESS_KEY=" + X40,
    "github_pat_fine_grained": "github" + "_pat_" + "11ABCDEFG0" + "x" * 20,
    "github_refresh_token_ghr": "gh" + "r_" + "a" * 36,
    "google_oauth_client_secret": "GOC" + "SPX-" + "z" * 28,
    "google_oauth_refresh_token": "token: 1/" + "/0" + "g" * 40,
    "google_oauth_access_token": "ya" + "29." + "h" * 40,
    "slack_app_token_xapp": "xa" + "pp-1-" + "A1B2C3D4E5F6",
    "slack_webhook_url": "https://hooks." + "slack.com/services/T0ABC/B0DEF/" + "q" * 24,
    "ec_private_key_header": "-----BEGIN " + "EC PRIVATE KEY-----",
    "encrypted_private_key_header": "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----",
    "pgp_private_key_header": "-----BEGIN " + "PGP PRIVATE KEY BLOCK-----",
    "jwt_token": "ey" + "J" + "a" * 12 + ".ey" + "J" + "b" * 12 + "." + "c" * 12,
    "stripe_live_key": "sk" + "_live_" + "9" * 24,
    "dataforseo_env_unquoted": "DATAFORSEO" + "_PASSWORD=" + "a1b2c3d4e5f6g7h8",
    "http_basic_auth_header": "Authorization: " + "Basic " + B64,
    "python_auth_tuple_literal": "requests.get(u, auth" + "=('me@x.test', 'hunter2hunter2'))",
}

NEGATIVE = [
    "task-1791967081556-0",                        # adstark task ids
    "DATAFORSEO_PASSWORD=your-dataforseo-password",  # .env.example placeholder
    "DATAFORSEO_PASSWORD=${DFS_PASSWORD}",
    "Authorization: Bearer <token>",
    "see 1/0 split and ya29 notes",
    "task_live_" + "a1" * 12,                      # live-key shape inside a word
]


@pytest.mark.parametrize("label", sorted(POSITIVE))
def test_format_is_caught(label: str) -> None:
    assert _scan(f"line before\n{POSITIVE[label]}\nline after\n") == 1, label


@pytest.mark.parametrize("text", NEGATIVE)
def test_benign_text_stays_green(text: str) -> None:
    assert _scan(text + "\n") == 0, text
