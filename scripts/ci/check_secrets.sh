#!/usr/bin/env bash
# Phase 14 W2 wrapper script — lesson 11 üçüncü surface mop-up
# Deployment config kategori-spesifik convention (Phase 14 W1 placeholder
# convention paralel evolution: dokümantasyon → placeholder, deployment
# config + literal-required → wrapper script self-exclude).
# Self-exclude path: scripts/ci/check_secrets.sh wrapper-only kategori.
# Lesson 28 manager mop-up matrisi 7'inci uygulama cumulative invariant.
set -euo pipefail
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
