#!/usr/bin/env bash
# Phase 14 W2 wrapper script — lesson 11 üçüncü surface mop-up
# Deployment config kategori-spesifik convention (Phase 14 W1 placeholder
# convention paralel evolution: dokümantasyon → placeholder, deployment
# config + literal-required → wrapper script self-exclude).
# Self-exclude path: scripts/ci/check_secrets.sh wrapper-only kategori.
# Lesson 28 manager mop-up matrisi 7'inci uygulama cumulative invariant.
#
# codex-hostile-audit #2 (2026-06-09): the wrapper now ALSO runs the CANONICAL
# runtime scanner (scripts/security/check_secrets.sh) so CI's secret-class
# inventory can NEVER be narrower than the runtime PreToolUse / event-redaction
# inventory — a single source of truth (16 PATTERN_NAMES classes: Google AIza,
# OpenAI/Anthropic sk-, Slack xox, GCP service-account, PEM/RSA/OPENSSH headers,
# GitHub ghp/gho/ghs/ghu + fine-grained, AWS, DataForSEO). On a clean CI
# checkout the working tree == committed state, so full-mode IS the committed
# scan. The original 4-literal committed-history git-grep stays as an ADDITIONAL
# specific-leak guard (info@demo-agency / the 3bf7… sample hash / the
# DATAFORSEO_PASSWORD literal / ghp_) — patterns the shape-based canonical
# scanner does not encode. Either gate failing fails the step (set -e).
set -euo pipefail

# Resolve the repo root from this script's own location (scripts/ci/ → repo),
# so the canonical scan covers the whole tree regardless of the caller's cwd.
_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_HERE/../.." && pwd)"

# 1) CANONICAL shape-class inventory (single source of truth, 16 classes).
#    A FAIL here aborts via set -e — the SAME gate the runtime hook enforces.
bash "$_REPO_ROOT/scripts/security/check_secrets.sh" "$_REPO_ROOT"

# 2) Committed-history specific-literal guard (git grep HEAD) — unchanged.
! git grep -nE "DATAFORSEO_PASSWORD=[a-zA-Z0-9]{8,}|info@demo-agency|3bf73e0893f69b42|ghp_[a-zA-Z0-9]{36}" \
    HEAD -- ':!.env.example' \
             ':!docs/superpowers/specs/' \
             ':!docs/CONTEXT_LEDGER.md' \
             ':!docs/OPEN_QUESTIONS.md' \
             ':!docs/DECISIONS.md' \
             ':!docs/DECISIONS_ARCHIVE.md' \
             ':!scripts/ci/check_secrets.sh' \
             ':!tests/scripts/test_events_writer.py' \
             ':!tests/ci/test_ci_yaml.py' \
             ':!tests/ci/test_check_secrets_sh.py'
