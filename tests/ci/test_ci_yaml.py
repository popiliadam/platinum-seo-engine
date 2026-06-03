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


def test_continue_on_error_all_steps_strict_mode():
    """Phase 14 W3-W3-β strict mode FINAL: tüm 7 step `continue-on-error: false`.

    W3-W3-α'da 3 governance step (drift-check + schema-validate + glossary-audit)
    strict mode'a geçti (Q-CI-W3-03 RESOLVED runtime kanıt + 4 governance helper
    exec EXIT=0 4/4 zemin). W3-W3-β v1.0.0 release closure ile kalan 4 step
    (pytest + plugin-agnostik-grep + secret-grep + frontmatter-compile) strict
    mode'a alındı (CI Run 10 mask removed actual exit code surface kanıtı +
    pytest 610 PASS + plugin-agnostik-grep 0 hit since W2 + secret-grep 0 hit
    [4 exclude path: .env.example, docs/superpowers/specs/, docs/CONTEXT_LEDGER.md,
    scripts/ci/check_secrets.sh] + frontmatter-compile 45 SKILL.md Draft7 verified).

    Lesson 21 cross-skill convention worker proaktif scope expansion 8 ardışık
    production-ready: bu test W3-W3-β closure ile ci.yml flip aynı wave'de
    update edildi (positive drift 610 PASS instead of regression).
    """
    cfg = yaml.safe_load(CI_YAML.read_text())
    check_steps = [
        s for s in cfg["jobs"]["ci"]["steps"]
        if s.get("name", "").startswith(tuple("1234567"))
    ]
    expected_strict_step_names = {
        "1. drift-check",
        "2. schema-validate",
        "3. glossary-audit",
        "4. pytest",
        "4a. events-schema-sanity",
        "5. plugin-agnostik-grep",
        "6. secret-grep",
        "7. frontmatter-compile",
    }
    seen = set()
    for step in check_steps:
        name = step.get("name", "")
        seen.add(name)
        actual = step.get("continue-on-error")
        assert actual is False, (
            f"Step {name} expected strict mode (continue-on-error: false), got {actual}"
        )
    assert seen == expected_strict_step_names, (
        f"Missing or extra steps. Expected {expected_strict_step_names}, got {seen}"
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
    (inventory -> demo-furniture match yok) + F-16 disclaimer exclude intentional
    policy preserve (Q-CI-W2-02 mop-up Phase 14 W2 manager <5dk fix).
    """
    body = CI_YAML.read_text()
    step5 = next(
        s for s in yaml.safe_load(body)["jobs"]["ci"]["steps"]
        if s.get("name", "") == "5. plugin-agnostik-grep"
    )
    assert "\\b(demo-dental|" in step5["run"]
    assert "No project slug hardcoded" in step5["run"]
    assert "F-16 disclaimer" in step5["run"]


def test_plugin_agnostik_step5_no_or_true_mask():
    """Wave 2 strict mode invariant: step 5 plugin-agnostik-grep MUST NOT
    contain `|| true` mask. Real exit code must surface so legitimate
    hardcode regressions fail the build.

    Pre-Wave-2 state used `|| true` to swallow false positives from F-16
    disclaimer multi-line slug enumerations. Wave 2 fix: expand grep -vE
    filter with adjacent-slug-pair patterns (real hardcode = 1 slug;
    disclaimer enumerates 8 slugs across 2-3 lines, so pairs are unique
    to disclaimer context).
    """
    body = CI_YAML.read_text()
    step5 = next(
        s for s in yaml.safe_load(body)["jobs"]["ci"]["steps"]
        if s.get("name", "") == "5. plugin-agnostik-grep"
    )
    assert "|| true" not in step5["run"], (
        "Wave 2 strict mode regression: step 5 must not mask exit code with `|| true`"
    )


def test_plugin_agnostik_step5_adjacent_pair_filter_present():
    """Wave 2 fix codification: adjacent-slug-pair patterns in grep -vE
    catch F-16 disclaimer multi-line continuation lines without false
    positives on real hardcodes (which would mention 1 slug only).

    7 adjacent pairs cover the 8-slug enumeration:
    demo-dental-demo-furniture, demo-furniture-demo-hvac, demo-hvac-demo-petcare, demo-petcare-demo-shop,
    demo-shop-demo-tires, demo-tires-demo-construction, demo-construction-demo-agency.
    """
    body = CI_YAML.read_text()
    step5 = next(
        s for s in yaml.safe_load(body)["jobs"]["ci"]["steps"]
        if s.get("name", "") == "5. plugin-agnostik-grep"
    )
    pairs = [
        "demo-dental.*demo-furniture",
        "demo-hvac.*demo-petcare",
        "demo-shop.*demo-tires",
        "demo-construction.*demo-agency",
    ]
    for pair in pairs:
        assert pair in step5["run"], (
            f"Wave 2 adjacent-pair filter missing: {pair} (disclaimer false positive risk)"
        )
