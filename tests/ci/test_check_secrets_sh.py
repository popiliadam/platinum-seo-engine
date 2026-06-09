"""tests/ci/test_check_secrets_sh.py — Phase 14 W2 wrapper script invariant test.

Lesson 11 üçüncü surface mop-up: ci.yml Step 6 regex literal CI search target
self-match catch (Phase 8 ilk surface CONTEXT_LEDGER + Phase 14 W1 ikinci
PHASE_STATUS placeholder → Phase 14 W2 üçüncü ci.yml deployment config kategori).
Wrapper script convention paralel evolution: dokümantasyon → placeholder,
deployment config + literal-required → wrapper script self-exclude.

Wave 2 (ADR-034) added execution-level regression tests: clean-tree EXIT 0
+ injected-secret detection round-trip (policy authority for the 7 exclude
paths and 4 detection patterns).
"""
import pathlib
import stat
import subprocess


SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts/ci/check_secrets.sh"
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


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


# Wave 2 — ADR-034 execution regression tests
# ============================================

def test_check_secrets_sh_clean_tree_exits_zero():
    """ADR-034 round-trip kanıt: çalışan repo'da check_secrets EXIT 0.
    Test fixtures (tests/scripts/test_events_writer.py + tests/ci/test_ci_yaml.py)
    + doc archive paths exclude list ile false-positive sıfır.
    """
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"check_secrets.sh expected EXIT 0 on clean tree, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_check_secrets_sh_adr034_exclude_paths():
    """ADR-034 codify: exclude path policy lock (additive değişiklik için
    ADR-034 amendment gerekir).

    Wave 2 amendment: DECISIONS.md + DECISIONS_ARCHIVE.md + this test
    file added to the list because ADR-034 body itself codifies the
    detection patterns (which would otherwise self-match), and this
    test asserts the patterns by literal (test fixture exemption).
    """
    body = SCRIPT.read_text()
    expected_excludes = [
        ":!.env.example",
        ":!docs/superpowers/specs/",
        ":!docs/CONTEXT_LEDGER.md",
        ":!docs/OPEN_QUESTIONS.md",
        ":!docs/DECISIONS.md",
        ":!docs/DECISIONS_ARCHIVE.md",
        ":!scripts/ci/check_secrets.sh",
        ":!tests/scripts/test_events_writer.py",
        ":!tests/ci/test_ci_yaml.py",
        ":!tests/ci/test_check_secrets_sh.py",
    ]
    for exc in expected_excludes:
        assert exc in body, f"ADR-034 exclude path missing: {exc}"


def test_check_secrets_sh_adr034_four_detection_patterns():
    """ADR-034 codify: 4 detection pattern lock — DATAFORSEO_PASSWORD literal,
    info@demo-agency email, hard-coded sample hash (3bf7…), GitHub PAT format
    (ghp_+36 alphanum).
    """
    body = SCRIPT.read_text()
    expected_patterns = [
        "DATAFORSEO_PASSWORD=[a-zA-Z0-9]{8,}",
        "info@demo-agency",
        "3bf73e0893f69b42",
        "ghp_[a-zA-Z0-9]{36}",
    ]
    for pat in expected_patterns:
        assert pat in body, f"ADR-034 detection pattern missing: {pat}"


# ---------------------------------------------------------------------------
# #2 — CI/runtime scanner parity (hostile-audit finding #2)
# ============================================================================
# The CI wrapper used to grep only 4 committed-history literals while the
# runtime scanner (scripts/security/check_secrets.sh) knows 16 secret CLASSES
# (PATTERN_NAMES). A class known to runtime could therefore pass GitHub Actions.
# The wrapper now ALSO invokes the canonical scanner so CI's inventory can never
# be NARROWER than runtime — a single source of truth by construction.
import re as _re

CANONICAL = pathlib.Path(__file__).resolve().parents[2] / "scripts/security/check_secrets.sh"


def _canonical_pattern_names() -> list[str]:
    """The canonical inventory labels (the runtime PATTERN_NAMES array)."""
    m = _re.search(r"PATTERN_NAMES=\((.*?)\)", CANONICAL.read_text(), _re.S)
    assert m, "PATTERN_NAMES array not found in canonical scanner"
    return _re.findall(r'"([^"]+)"', m.group(1))


def test_ci_wrapper_invokes_canonical_scanner():
    """#2 fix: the CI wrapper MUST invoke the canonical runtime scanner so its
    full 16-class inventory covers CI — not just the 4 historical literals."""
    body = SCRIPT.read_text()
    assert "scripts/security/check_secrets.sh" in body, (
        "CI wrapper must invoke scripts/security/check_secrets.sh (the canonical "
        "16-class inventory); before this fix CI ran only a 4-literal git-grep, "
        "so a committed Google/Slack/PEM/AWS secret could pass GitHub Actions"
    )


def test_ci_wrapper_coverage_superset_of_runtime_inventory():
    """Label parity: because the wrapper invokes the canonical scanner, CI's
    covered class set ⊇ the runtime PATTERN_NAMES by construction. Pin both
    halves so a future edit can't silently revert to a narrow hand-rolled set."""
    names = _canonical_pattern_names()
    assert len(names) >= 16, f"canonical inventory unexpectedly shrank: {names}"
    assert "scripts/security/check_secrets.sh" in SCRIPT.read_text(), (
        "wrapper no longer invokes the canonical scanner — CI coverage would "
        f"fall back below the {len(names)}-class runtime inventory"
    )


def test_ci_wrapper_retains_historical_literal_guard():
    """Regression: the 4 committed-history specific literals are NOT in the
    shape-based canonical inventory, so the wrapper must keep its git-grep for
    them ALONGSIDE the canonical call (assertions avoid the `=`+quote adjacency
    so they never themselves match the canonical dataforseo pattern)."""
    body = SCRIPT.read_text()
    for lit in ("info@demo-agency", "3bf73e0893f69b42", "DATAFORSEO_PASSWORD", "ghp_"):
        assert lit in body, f"historical-literal guard dropped: {lit}"


def test_ci_wrapper_canonical_call_committed_secret_roundtrip(tmp_path: pathlib.Path):
    """End-to-end: a secret CLASS the OLD 4-literal wrapper missed (Slack) is now
    caught because the wrapper runs the canonical scanner. Proven directly on the
    canonical scanner with a dynamically-built token (no literal on disk)."""
    slack = "xox" + "b-" + "Z" * 24  # synthetic Slack token shape, built at runtime
    proc = subprocess.run(
        ["bash", str(CANONICAL), "--scan-stdin", "config.yaml"],
        input=f"slack_token: {slack}\n",
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 1, (
        f"canonical scanner (now invoked by CI) must catch Slack class; "
        f"stdout={proc.stdout!r}"
    )
    assert slack not in proc.stdout, "scanner must never echo matched content"
