"""tests/ci/test_ci_yaml.py — ci.yml structure invariant test."""
import pathlib

import yaml


CI_YAML = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"


def test_ci_yaml_exists():
    assert CI_YAML.exists()


def test_ci_yaml_valid_syntax():
    yaml.safe_load(CI_YAML.read_text())


def test_on_push_pull_request_main():
    cfg = yaml.safe_load(CI_YAML.read_text())
    # YAML 'on' keyword is parsed as boolean True by PyYAML safe_load
    on_key = cfg.get(True, cfg.get("on"))
    assert "push" in on_key and "pull_request" in on_key
    assert on_key["push"]["branches"] == ["main"]
    assert on_key["pull_request"]["branches"] == ["main"]


def test_seven_steps_present():
    cfg = yaml.safe_load(CI_YAML.read_text())
    steps = cfg["jobs"]["ci"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert "1. drift-check" in step_names
    assert "2. schema-validate" in step_names
    assert "3. glossary-audit" in step_names
    assert "4. pytest" in step_names
    assert "5. plugin-agnostik-grep" in step_names
    assert "6. secret-grep" in step_names
    assert "7. frontmatter-compile" in step_names


def test_python_version_matrix():
    cfg = yaml.safe_load(CI_YAML.read_text())
    assert "3.10" in cfg["jobs"]["ci"]["strategy"]["matrix"]["python-version"]


def test_pip_cache_enabled():
    cfg = yaml.safe_load(CI_YAML.read_text())
    setup_step = next(s for s in cfg["jobs"]["ci"]["steps"] if "Set up Python" in s.get("name", ""))
    assert setup_step["with"]["cache"] == "pip"


def test_continue_on_error_initial_report_only_mode():
    cfg = yaml.safe_load(CI_YAML.read_text())
    check_steps = [
        s for s in cfg["jobs"]["ci"]["steps"]
        if s.get("name", "").startswith(tuple("1234567"))
    ]
    for step in check_steps:
        assert step.get("continue-on-error") is True, (
            f"Step {step['name']} report-only mode initial expected"
        )


def test_secret_grep_via_wrapper_script():
    """Lesson 11 üçüncü+dördüncü+beşinci surface mop-up: ci.yml Step 6 regex
    literal wrapper script'e taşındı (deployment config kategori) + test
    infrastructure substring fragment convention (2 alternation literal
    kaldırıldı — alternation pattern exact match self-match riski, prefix
    substring fragment yeterli; lesson 11 v3 1-dosyada-multi-katman
    consistent application: assert + docstring + comment hep aynı kategori).
    """
    cfg = yaml.safe_load(CI_YAML.read_text())
    step6 = next(
        s for s in cfg["jobs"]["ci"]["steps"]
        if s.get("name", "") == "6. secret-grep"
    )
    # Step 6 wrapper script'i çağırır (regex literal direct YOK)
    assert "scripts/ci/check_secrets.sh" in step6["run"]
    # ci.yml'de regex literal YOK (lesson 11 v3 enforce dosya-seviyesi):
    # SADECE DATAFORSEO_PASSWORD= substring assertion (regex pattern 8+
    # alphanum gerektirir, substring fragment self-match etmez). 2
    # alternation literal'ler KALDIRILDI çünkü alternation pattern exact
    # match riski (Gate 6 self-match catch — lesson 11 v3 production-ready
    # convention test-infrastructure 1-dosyada-multi-katman consistent
    # application: assert + docstring + comment hep aynı substring fragment).
    body = CI_YAML.read_text()
    assert "DATAFORSEO_PASSWORD=" not in body, "Regex literal ci.yml'den wrapper'a taşındı"


def test_no_regex_literal_in_yaml_doc_comments():
    """Lesson 11 ikinci surface (Phase 14 W1) — placeholder convention codify.

    Comment'lerde regex literal YASAK (self-match onleme), step 6 secret-grep
    komutunda regex literal ZORUNLU (CI search target).
    """
    body = CI_YAML.read_text()
    comment_lines = [l for l in body.split("\n") if l.strip().startswith("#")]
    for line in comment_lines:
        assert "DATAFORSEO_PASSWORD=" not in line, f"Comment regex literal: {line[:80]}"


def test_fetch_depth_full_history_for_secret_grep():
    cfg = yaml.safe_load(CI_YAML.read_text())
    checkout_step = next(
        s for s in cfg["jobs"]["ci"]["steps"]
        if s.get("uses", "").startswith("actions/checkout")
    )
    assert checkout_step["with"]["fetch-depth"] == 0


def test_plugin_agnostik_grep_word_boundary_and_disclaimer_exclude():
    """Lesson 28 6'inci uygulama: \\b word-boundary substring eliminate
    (inventory -> vento match yok) + F-16 disclaimer exclude intentional
    policy preserve (Q-CI-W2-02 mop-up Phase 14 W2 manager <5dk fix).
    """
    body = CI_YAML.read_text()
    step5 = next(
        s for s in yaml.safe_load(body)["jobs"]["ci"]["steps"]
        if s.get("name", "") == "5. plugin-agnostik-grep"
    )
    assert "\\b(dentnotion|" in step5["run"]
    assert "No project slug hardcoded" in step5["run"]
    assert "F-16 disclaimer" in step5["run"]
