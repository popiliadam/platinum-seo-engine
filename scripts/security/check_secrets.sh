#!/usr/bin/env bash
# ============================================================================
# check_secrets.sh — Zero committed/tracked-secrets enforcement
# ============================================================================
# Policy: zero COMMITTED / CHANGED secrets — NOT "zero secrets on disk". A local
#   .env that is GITIGNORED is allowed: it only emits a WARN and the exit stays
#   0/GREEN (it can never be committed). A .env that is NOT gitignored, or a
#   secret-shaped pattern in a tracked file, is a FAIL (exit 1/RED). See the
#   .env handling in section 3 below + rules/secrets-management.md.
# Runs at: bootstrap sign-off + every plugin install + PreToolUse hook (full or
#   --changed-since incremental). CI uses the committed-only wrapper
#   scripts/ci/check_secrets.sh (git grep HEAD).
# Reference: docs/superpowers/specs/2026-04-30-platinum-seo-engine-design.md §8.7
#            rules/secrets-management.md
#
# Usage:
#   ./scripts/security/check_secrets.sh [root_dir]                    # full (default)
#   ./scripts/security/check_secrets.sh --changed-since [REF] [ROOT]  # incremental
#   ./scripts/security/check_secrets.sh --scan-stdin [PSEUDO_PATH]    # literal stdin
#       bytes (gitignore-UNAWARE; a gitignored local .env still only WARNs)
#   (default root_dir = current working directory)
#
# Exit codes:
#   0  GREEN — no committed/tracked secrets (a gitignored local .env only WARNs)
#   1  RED   — committed/tracked secrets or credential artifacts detected, BLOCK
# ============================================================================
set -euo pipefail

# ----------------------------------------------------------------------------
# Argument parsing
#   ./check_secrets.sh [ROOT]                         # full mode (default)
#   ./check_secrets.sh --changed-since [REF] [ROOT]   # incremental mode (B2 perf)
#   ./check_secrets.sh --scan-stdin [PSEUDO_PATH]     # literal pending bytes (stdin)
#
# Incremental mode scans ONLY files changed since REF (default HEAD~1) — useful
# for PreToolUse hook fast-path or CI per-PR scans. Structural checks (cred dirs,
# .env files, key files, chmod) are SKIPPED in incremental mode by design — those
# are full-tree checks; pattern scan dominates per-edit latency (B2 finding).
#
# --scan-stdin scans the LITERAL bytes piped on stdin (gitignore-UNAWARE), so a
# secret headed for a gitignored target — invisible to the incremental fast-path,
# which lists files via git with --exclude-standard — is still caught. The one
# carve-out: a gitignored local .env (the sanctioned local-secrets store) only
# WARNs. Optional PSEUDO_PATH is the intended write target (used for that
# carve-out only). Structural sections 2-6 are skipped (pure pattern scan).
# ----------------------------------------------------------------------------
INCREMENTAL=0
INCREMENTAL_REF=""
SCAN_STDIN=0
PSEUDO_PATH=""
if [ "${1:-}" = "--scan-stdin" ]; then
  # NEW (AMO Faz-3): parsed BEFORE --changed-since/positional so those two modes
  # stay byte-for-byte unchanged. Captures an optional intended-target path.
  SCAN_STDIN=1
  PSEUDO_PATH="${2:-}"
  ROOT="."
elif [ "${1:-}" = "--changed-since" ]; then
  INCREMENTAL=1
  INCREMENTAL_REF="${2:-HEAD~1}"
  ROOT="${3:-.}"
else
  ROOT="${1:-.}"
fi
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

# ----------------------------------------------------------------------------
# --scan-stdin mode (AMO Faz-3): scan the LITERAL pending bytes from stdin.
#   The incremental fast-path sources its file list from git (with
#   --exclude-standard), so a secret headed for a GITIGNORED target is invisible
#   to it. This mode bypasses git enumeration entirely: it buffers stdin once and
#   runs the SAME PATTERNS over those literal bytes. It is gitignore-UNAWARE by
#   design — with ONE carve-out: a gitignored local .env is a sanctioned local
#   secrets store, so a hit there is WARN (exit 0), never FAIL (mirrors section
#   3). Every OTHER target (no pseudo-path, a non-gitignored target, or a
#   gitignored NON-.env target) is a FAIL (exit 1). Structural sections 2-6 are
#   skipped (pure literal-bytes pattern scan, like incremental).
#   SECURITY: only the pattern label + match count are ever printed — never the
#   matched content (same invariant as section 1).
# ----------------------------------------------------------------------------
if [ "$SCAN_STDIN" = "1" ]; then
  echo "============================================================"
  echo "check_secrets.sh — scanning (stdin pending bytes)..."
  echo "============================================================"

  # Buffer stdin once into a private temp file (binary-safe; lets us reuse the
  # per-pattern grep machinery). Always cleaned up via the EXIT trap.
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  cat > "$tmp"

  # Run the SAME pattern loop over the buffered bytes. Collect matches as
  # newline-delimited "name|count" entries — never the matched content itself.
  HIT=0
  HITS=""
  for i in "${!PATTERNS[@]}"; do
    p="${PATTERNS[$i]}"
    name="${PATTERN_NAMES[$i]:-pattern_$i}"
    if grep -qE "$p" "$tmp" 2>/dev/null; then
      HIT=1
      c=$(grep -cE "$p" "$tmp" 2>/dev/null || echo 0)
      HITS="${HITS}${name}|${c}"$'\n'
    fi
  done
  HITS="${HITS%$'\n'}"

  # Verdict 1: nothing matched → clean.
  if [ "$HIT" = "0" ]; then
    echo ""
    echo "============================================================"
    echo "SECURITY GATE GREEN (no secrets in stdin pending bytes)"
    exit 0
  fi

  # A secret pattern matched. Apply the gitignored-.env WARN carve-out: a hit is
  # WARN (exit 0) ONLY when the intended target is a gitignored local .env /
  # .env.* (but NOT .env.example). Mirrors section 3's git check-ignore logic.
  IS_ENV_CARVEOUT=0
  if [ -n "$PSEUDO_PATH" ]; then
    base="$(basename "$PSEUDO_PATH")"
    case "$base" in
      .env.example)
        : ;;  # committed template — never carve out (a secret here is a FAIL)
      .env|.env.*)
        if git check-ignore -q -- "$PSEUDO_PATH" 2>/dev/null; then
          IS_ENV_CARVEOUT=1
        fi
        ;;
    esac
  fi

  # Verdict 2: gitignored local .env → WARN, exit stays 0/GREEN.
  if [ "$IS_ENV_CARVEOUT" = "1" ]; then
    echo ""
    echo "WARN: secret pattern in gitignored local .env ($PSEUDO_PATH) — local credentials, no leak"
    echo "  (content [REDACTED])"
    echo ""
    echo "============================================================"
    echo "SECURITY GATE GREEN (gitignored local .env — WARN only)"
    exit 0
  fi

  # Verdict 3: any OTHER target (no pseudo-path, non-gitignored, or gitignored
  # NON-.env) → FAIL. Report the matching label(s) + count — never the content.
  echo ""
  while IFS= read -r entry; do
    [ -z "$entry" ] && continue
    n="${entry%%|*}"
    c="${entry##*|}"
    echo "FAIL pattern: $n"
    echo "  stdin pending bytes ($c match(es) — content [REDACTED])"
  done <<< "$HITS"
  echo ""
  echo "============================================================"
  echo "SECURITY GATE FAIL"
  echo "   Secret-shaped pattern in pending bytes for: ${PSEUDO_PATH:-<unknown target>}"
  echo "   Reference: rules/secrets-management.md"
  exit 1
fi

echo "============================================================"
if [ "$INCREMENTAL" = "1" ]; then
  echo "check_secrets.sh — scanning (incremental, since $INCREMENTAL_REF): $ROOT"
else
  echo "check_secrets.sh — scanning: $ROOT"
fi
echo "============================================================"

# Pre-compute changed file list once when in incremental mode (B2 perf).
CHANGED_FILES_LIST=""
if [ "$INCREMENTAL" = "1" ]; then
  # git diff lists tracked changes only; union in untracked-but-not-ignored
  # files so a brand-new secret-bearing file can't slip the incremental gate
  # (codex-audit f7). --exclude-standard keeps gitignored local .env WARN-only.
  CHANGED_FILES_LIST=$(cd "$ROOT" && { git diff --name-only "$INCREMENTAL_REF" 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u || true)
  if [ -z "$CHANGED_FILES_LIST" ]; then
    echo "INCREMENTAL: no files changed since $INCREMENTAL_REF (or git unavailable)"
  fi
fi

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
  if [ "$INCREMENTAL" = "1" ]; then
    # Incremental: scan only changed files (file-by-file grep -lE)
    FILES=""
    if [ -n "$CHANGED_FILES_LIST" ]; then
      while IFS= read -r cf; do
        [ -z "$cf" ] && continue
        full="$ROOT/$cf"
        [ -f "$full" ] || continue
        if grep -lE "$p" "$full" >/dev/null 2>&1; then
          FILES="${FILES}${full}"$'\n'
        fi
      done <<< "$CHANGED_FILES_LIST"
      FILES="${FILES%$'\n'}"
    fi
  else
    # Full mode: recursive grep with policy excludes (ADR-034)
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
  fi
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

# Structural section guard: skip in incremental mode (B2 perf — patterns
# dominate per-edit latency; structural checks are full-tree concerns).
if [ "$INCREMENTAL" = "0" ]; then

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

fi  # end of structural-only sections (incremental mode skips all of section 2-6)

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
  echo "SECURITY GATE GREEN (no committed/tracked secrets)"
  echo "   Last scan: $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  exit 0
fi
