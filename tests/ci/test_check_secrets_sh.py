"""tests/ci/test_check_secrets_sh.py — Phase 14 W2 wrapper script invariant test.

Lesson 11 üçüncü surface mop-up: ci.yml Step 6 regex literal CI search target
self-match catch (Phase 8 ilk surface CONTEXT_LEDGER + Phase 14 W1 ikinci
PHASE_STATUS placeholder → Phase 14 W2 üçüncü ci.yml deployment config kategori).
Wrapper script convention paralel evolution: dokümantasyon → placeholder,
deployment config + literal-required → wrapper script self-exclude.
"""
import pathlib
import stat


SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts/ci/check_secrets.sh"


def test_check_secrets_sh_exists():
    assert SCRIPT.exists(), f"Wrapper script not found: {SCRIPT}"
    assert SCRIPT.is_file()


def test_check_secrets_sh_executable():
    """User-executable bit set olmalı (CI runner bash invocation için)."""
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, f"Script user-executable olmalı: {SCRIPT}"


def test_check_secrets_sh_self_exclude_path():
    """Lesson 11 üçüncü surface: wrapper script self-exclude kategori convention.

    scripts/ci/check_secrets.sh kendi kendini exclude eder (deployment config
    wrapper-only kategori, dokümantasyon placeholder convention paralel).
    """
    body = SCRIPT.read_text()
    assert ":!scripts/ci/check_secrets.sh" in body, (
        "Wrapper script kendi self-exclude path içermeli (kategori-spesifik)"
    )


def test_check_secrets_sh_three_legacy_exclude_paths():
    """CI Rule 3 invariant Phase 14+ 11 phase ardışık + 4'üncü self-exclude
    wrapper-only (kategori-spesifik genişleme, lesson 11 üçüncü surface evolution).

    3 dokümantasyon kategori exclude path stable (Phase 14 W1 codify):
      - .env.example (placeholder template)
      - docs/superpowers/specs/ (design dokümanı)
      - docs/CONTEXT_LEDGER.md (manager-only operational log)
    + 4'üncü deployment config wrapper-only (Phase 14 W2 codify):
      - scripts/ci/check_secrets.sh (literal-required search target self-reference)
    """
    body = SCRIPT.read_text()
    assert ":!.env.example" in body
    assert ":!docs/superpowers/specs/" in body
    assert ":!docs/CONTEXT_LEDGER.md" in body
