#!/usr/bin/env bash
# ============================================================================
# check_secrets.sh — Zero-secrets-on-disk enforcement
# ============================================================================
# Runs at: bootstrap sign-off + every plugin install + PreToolUse hook
# Reference: docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md §8.7
#            rules/secrets-management.md
#
# Usage:
#   ./scripts/security/check_secrets.sh [root_dir]
#   (default root_dir = current working directory)
#
# Exit codes:
#   0  GREEN — no secrets detected, safe to proceed
#   1  RED   — secrets or credential artifacts detected, BLOCK
# ============================================================================
set -euo pipefail

ROOT="${1:-.}"
EXIT=0

# ----------------------------------------------------------------------------
# Secret patterns (regex)
# ----------------------------------------------------------------------------
PATTERNS=(
  # Google API key (39 chars, AIza prefix)
  "AIza[0-9A-Za-z_-]{35}"
  # OpenAI / Anthropic-style keys
  "sk-[A-Za-z0-9]{20,}"
  # Google Service Account JSON private key marker
  "\"private_key\":\\s*\"-----BEGIN"
  # Generic PEM private keys
  "-----BEGIN PRIVATE KEY-----"
  "-----BEGIN RSA PRIVATE KEY-----"
  "-----BEGIN OPENSSH PRIVATE KEY-----"
  # Google IAM service account email (client_email field)
  "\"client_email\":\\s*\".*@.*\\.iam\\.gserviceaccount\\.com\""
  # GitHub tokens
  "ghp_[A-Za-z0-9]{36}"
  "gho_[A-Za-z0-9]{36}"
  "ghs_[A-Za-z0-9]{36}"
  "ghu_[A-Za-z0-9]{36}"
  # AWS credentials
  "aws_access_key_id\\s*=\\s*[A-Z0-9]{20}"
  "aws_secret_access_key\\s*=\\s*[A-Za-z0-9/+=]{40}"
  "AKIA[0-9A-Z]{16}"
  # Slack tokens
  "xox[baprs]-[0-9a-zA-Z-]{10,}"
  # DataForSEO common leak pattern (hardcoded login+password)
  "DATAFORSEO_(LOGIN|USERNAME|PASSWORD)\\s*=\\s*[\"'][^\"']+[\"']"
)

# Parallel array: human-readable labels for each PATTERNS entry (same index).
# Used in reporting so we never echo the regex itself or the match content.
# Bash 3.2 compatible (no associative arrays — macOS default bash).
PATTERN_NAMES=(
  "google_api_key_AIza"
  "openai_or_anthropic_sk_prefix"
  "gcp_service_account_json_private_key_field"
  "pem_private_key_header"
  "rsa_private_key_header"
  "openssh_private_key_header"
  "gcp_service_account_client_email"
  "github_pat_classic_ghp"
  "github_oauth_token_gho"
  "github_server_token_ghs"
  "github_user_token_ghu"
  "aws_access_key_id_line"
  "aws_secret_access_key_line"
  "aws_akia_key_literal"
  "slack_token_xox"
  "dataforseo_env_hardcoded_literal"
)

echo "============================================================"
echo "check_secrets.sh — scanning: $ROOT"
echo "============================================================"

# ----------------------------------------------------------------------------
# 1) Regex patterns scan
#    SECURITY NOTE: We deliberately never echo the regex match content —
#    only file path + match count + pattern label. Printing the match would
#    leak the very secret we're trying to detect into stdout, shell history,
#    log files (if piped with tee), CI/CD output, and Claude transcripts.
# ----------------------------------------------------------------------------
for i in "${!PATTERNS[@]}"; do
  p="${PATTERNS[$i]}"
  name="${PATTERN_NAMES[$i]:-pattern_$i}"
  # grep -l (files-with-matches only) — never prints match content
  FILES=$(grep -rlE "$p" "$ROOT" \
    --exclude-dir=.git \
    --exclude-dir=node_modules \
    --exclude-dir=_backups \
    --exclude-dir=staging \
    --exclude-dir=__pycache__ \
    --exclude-dir=.venv \
    --exclude-dir=venv \
    --exclude="*.lock" \
    --exclude="*.log" \
    --exclude="check_secrets.sh" \
    --exclude="check-secrets.sh" \
    --exclude="secrets-management.md" \
    --exclude="2026-04-30-platinum-seo-engine-design.md" \
    --exclude="test_events_writer.py" \
    --exclude="test_ci_yaml.py" \
    --exclude="OPEN_QUESTIONS.md" 2>/dev/null || true)
  if [ -n "$FILES" ]; then
    echo ""
    echo "FAIL pattern: $name"
    while IFS= read -r f; do
      # grep -c: count only, never echoes match content
      count=$(grep -cE "$p" "$f" 2>/dev/null || echo 0)
      echo "  $f ($count match(es) — content [REDACTED])"
    done <<< "$FILES"
    EXIT=1
  fi
done

# ----------------------------------------------------------------------------
# 2) credentials/ directories (legacy leak surface) outside _backups/
# ----------------------------------------------------------------------------
CRED_DIRS=$(find "$ROOT" \
  -type d -name "credentials" \
  -not -path "*/_backups/*" \
  -not -path "*/_archive/*" \
  -not -path "*/.git/*" 2>/dev/null || true)
if [ -n "$CRED_DIRS" ]; then
  echo ""
  echo "FAIL: credentials/ directory found outside _backups/_archive/"
  echo "$CRED_DIRS"
  EXIT=1
fi

# ----------------------------------------------------------------------------
# 3) .env / .env.* files in tracked locations
# ----------------------------------------------------------------------------
ENV_FILES=$(find "$ROOT" \
  -type f \( -name ".env" -o -name ".env.*" \) \
  -not -name ".env.example" \
  -not -path "*/_backups/*" \
  -not -path "*/_archive/*" \
  -not -path "*/.git/*" \
  -not -path "*/node_modules/*" 2>/dev/null || true)
if [ -n "$ENV_FILES" ]; then
  WARN_FILES=""
  FAIL_FILES=""
  while IFS= read -r env_file; do
    [ -z "$env_file" ] && continue
    if git check-ignore -q "$env_file" 2>/dev/null; then
      WARN_FILES="$WARN_FILES $env_file"
    else
      FAIL_FILES="$FAIL_FILES $env_file"
    fi
  done <<< "$ENV_FILES"
  if [ -n "$WARN_FILES" ]; then
    echo ""
    echo "WARN: .env file(s) found but gitignored (local credentials, no leak):"
    for f in $WARN_FILES; do echo "  $f"; done
  fi
  if [ -n "$FAIL_FILES" ]; then
    echo ""
    echo "FAIL: .env file(s) NOT gitignored (leak risk!)"
    for f in $FAIL_FILES; do echo "  $f"; done
    EXIT=1
  fi
fi

# ----------------------------------------------------------------------------
# 4) Service account JSON files (gcloud pattern)
# ----------------------------------------------------------------------------
SA_FILES=$(find "$ROOT" \
  -type f \( -name "*service-account*.json" -o -name "*serviceaccount*.json" -o -name "google-indexing*.json" \) \
  -not -path "*/_backups/*" \
  -not -path "*/_archive/*" \
  -not -path "*/.git/*" 2>/dev/null || true)
if [ -n "$SA_FILES" ]; then
  echo ""
  echo "FAIL: service account JSON found (should live at ~/.config/platinum-seo-engine/secrets/ chmod 0600)"
  echo "$SA_FILES"
  EXIT=1
fi

# ----------------------------------------------------------------------------
# 5) .key / .pem files outside allowed locations
# ----------------------------------------------------------------------------
KEY_FILES=$(find "$ROOT" \
  -type f \( -name "*.key" -o -name "*.pem" \) \
  -not -path "*/_backups/*" \
  -not -path "*/_archive/*" \
  -not -path "*/.git/*" \
  -not -path "*/node_modules/*" 2>/dev/null || true)
if [ -n "$KEY_FILES" ]; then
  echo ""
  echo "FAIL: .key/.pem file(s) found (should live outside repo)"
  echo "$KEY_FILES"
  EXIT=1
fi

# ----------------------------------------------------------------------------
# 6) chmod verification for archived credentials
#    Archived credentials must be 0000 + ROTATE note required
# ----------------------------------------------------------------------------
ARCHIVED_CRED_FILES=$(find "$ROOT/_backups" "$ROOT/_archive" \
  -type f \( -name "*api-key*" -o -name "*credentials*" -o -name "*service-account*" \) \
  -not -perm 0000 2>/dev/null || true)
if [ -n "$ARCHIVED_CRED_FILES" ]; then
  echo ""
  echo "WARN: archived credential files not chmod 0000 (should be locked):"
  echo "$ARCHIVED_CRED_FILES"
  echo "  Fix: chmod 0000 <file>"
  # WARN only, not FAIL — legacy handling
fi

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
echo ""
echo "============================================================"
if [ "$EXIT" -eq 1 ]; then
  echo "SECURITY GATE FAIL"
  echo "   Fix findings above before proceeding."
  echo "   Reference: rules/secrets-management.md"
  exit 1
else
  echo "SECURITY GATE GREEN (zero secrets detected)"
  echo "   Last scan: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  exit 0
fi
