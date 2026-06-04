"""codex-audit finding 12: the README architecture diagram showed a per-project
`config.yaml` that exists nowhere — the real per-project contract file is
`project.config.json` (schemas/project-config.schema.json). Lock the diagram to
the real artifact name so it cannot mislead a reader/operator again.
"""
from pathlib import Path

README = (Path(__file__).resolve().parents[2] / "README.md").read_text("utf-8")


def test_readme_does_not_reference_config_yaml():
    assert "config.yaml" not in README, (
        "README references a fictional config.yaml; the real per-project "
        "contract is project.config.json"
    )
    assert "project.config.json" in README
