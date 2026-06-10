"""tests/ci/test_github_governance.py — .github governance invariants (FIX-R items 3-4).

CODEOWNERS: review routing — a default owner plus EXPLICIT lines for the two
security-critical surfaces (scripts/security/, .github/workflows/) so changes
to the secret-scanner or the CI pipeline itself always carry visible ownership.

dependabot.yml: weekly pip + weekly github-actions update streams, with
minor/patch updates grouped into one PR per ecosystem. The github-actions
stream is what keeps the ci.yml commit-SHA pins (FIX-R item 1) from rotting.
"""
import pathlib

import yaml


GITHUB_DIR = pathlib.Path(__file__).resolve().parents[2] / ".github"
CODEOWNERS = GITHUB_DIR / "CODEOWNERS"
DEPENDABOT = GITHUB_DIR / "dependabot.yml"


def _codeowners_rules():
    """Parse CODEOWNERS into {pattern: [owners]} (comments/blank lines skipped)."""
    rules = {}
    for raw in CODEOWNERS.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *owners = line.split()
        rules[pattern] = owners
    return rules


def test_codeowners_exists():
    assert CODEOWNERS.exists(), ".github/CODEOWNERS missing (FIX-R item 3)"


def test_codeowners_default_owner():
    rules = _codeowners_rules()
    assert rules.get("*") == ["@popiliadam"], (
        f"CODEOWNERS catch-all must be `* @popiliadam`, got {rules.get('*')}"
    )


def test_codeowners_explicit_security_critical_paths():
    """Explicit lines (not just the catch-all) for the paths where a silent
    ownership change would be a supply-chain event: the secret scanner and
    the CI workflow definitions."""
    rules = _codeowners_rules()
    assert "@popiliadam" in rules.get("/scripts/security/", []), (
        "CODEOWNERS must explicitly own /scripts/security/"
    )
    assert "@popiliadam" in rules.get("/.github/workflows/", []), (
        "CODEOWNERS must explicitly own /.github/workflows/"
    )


def test_dependabot_exists_and_is_valid_yaml():
    assert DEPENDABOT.exists(), ".github/dependabot.yml missing (FIX-R item 4)"
    cfg = yaml.safe_load(DEPENDABOT.read_text())
    assert cfg["version"] == 2


def test_dependabot_weekly_pip_and_github_actions():
    cfg = yaml.safe_load(DEPENDABOT.read_text())
    ecosystems = {u["package-ecosystem"]: u for u in cfg["updates"]}
    assert set(ecosystems) == {"pip", "github-actions"}, (
        f"expected exactly pip + github-actions streams, got {set(ecosystems)}"
    )
    for eco, update in ecosystems.items():
        assert update["schedule"]["interval"] == "weekly", f"{eco}: must be weekly"
        assert update["directory"] == "/", f"{eco}: manifests live at repo root"


def test_dependabot_groups_minor_and_patch():
    """Minor+patch updates arrive grouped (one PR per ecosystem per week);
    majors stay individual PRs so breaking bumps get individual review."""
    cfg = yaml.safe_load(DEPENDABOT.read_text())
    for update in cfg["updates"]:
        eco = update["package-ecosystem"]
        groups = update.get("groups") or {}
        assert groups, f"{eco}: minor/patch grouping required (FIX-R item 4)"
        update_type_sets = [
            set(g.get("update-types", [])) for g in groups.values()
        ]
        assert {"minor", "patch"} in update_type_sets, (
            f"{eco}: expected a group with update-types [minor, patch], "
            f"got {update_type_sets}"
        )
