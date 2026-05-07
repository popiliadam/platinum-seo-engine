#!/usr/bin/env bash
# ============================================================================
# check_append_only.sh — Pre-commit hook: jsonl non-append diff guard
# ============================================================================
# Per rules/append-only-state.md: events.jsonl + workflows/{run_id}.json
# files MUST NOT be rewritten or have lines mutated/deleted; only new lines
# may be appended. This hook scans staged .jsonl diffs and rejects any commit
# that contains line deletions or in-place line edits.
#
# Usage:
#   ./scripts/hooks/check_append_only.sh                    # default: --staged
#   ./scripts/hooks/check_append_only.sh --staged           # check `git diff --cached`
#   ./scripts/hooks/check_append_only.sh --working-tree     # check `git diff` (unstaged)
#   ./scripts/hooks/check_append_only.sh --rev-range A..B   # check commit range
#
# Exit codes:
#   0  GREEN — no non-append diff in any .jsonl file
#   1  RED   — non-append diff detected (rejection); BLOCK commit
#   2        usage error
#
# Closes: Q-V1.5-HOOK-SCRIPTS-MISSING-01 (option b — unqualified gap closure).
# ============================================================================
set -euo pipefail

MODE="--cached"
RANGE=""

if [[ $# -gt 0 ]]; then
    case "$1" in
        --staged)
            MODE="--cached"
            ;;
        --working-tree)
            MODE=""
            ;;
        --rev-range)
            shift
            if [[ $# -lt 1 ]]; then
                echo "usage: check_append_only.sh --rev-range <A..B>" >&2
                exit 2
            fi
            RANGE="$1"
            MODE=""
            ;;
        --help|-h)
            grep -E "^# " "$0" | sed 's/^# //' >&2
            exit 0
            ;;
        *)
            echo "usage: check_append_only.sh [--staged|--working-tree|--rev-range A..B]" >&2
            exit 2
            ;;
    esac
fi

# Find changed .jsonl files in scope. Portable across bash 3.2 (macOS) — no
# `mapfile` builtin (added in bash 4.0); use explicit read-loop.
jsonl_files=()
if [[ -n "$RANGE" ]]; then
    while IFS= read -r line; do
        [[ -n "$line" ]] && jsonl_files+=("$line")
    done < <(git diff --name-only --diff-filter=AMR "$RANGE" 2>/dev/null \
                | grep -E '\.jsonl$' || true)
else
    while IFS= read -r line; do
        [[ -n "$line" ]] && jsonl_files+=("$line")
    done < <(git diff $MODE --name-only --diff-filter=AMR 2>/dev/null \
                | grep -E '\.jsonl$' || true)
fi

if [[ ${#jsonl_files[@]} -eq 0 ]]; then
    exit 0
fi

violations=0
for f in "${jsonl_files[@]}"; do
    # Detect non-append: any line beginning with `-` (other than diff header
    # lines `--- a/...`) means a deletion or in-place modification.
    if [[ -n "$RANGE" ]]; then
        diff_text=$(git diff --unified=0 "$RANGE" -- "$f" 2>/dev/null || true)
    else
        diff_text=$(git diff $MODE --unified=0 -- "$f" 2>/dev/null || true)
    fi
    if [[ -z "$diff_text" ]]; then
        continue
    fi
    if echo "$diff_text" | grep -E '^-[^-]' >/dev/null 2>&1; then
        echo "ERROR: $f has non-append diff (rules/append-only-state.md violation)" >&2
        echo "  Per append-only discipline, .jsonl files MUST be append-only;" >&2
        echo "  use a corrective new event entry instead of modifying past lines." >&2
        violations=$((violations + 1))
    fi
done

if [[ $violations -gt 0 ]]; then
    echo "" >&2
    echo "Total append-only violations: $violations" >&2
    exit 1
fi
exit 0
