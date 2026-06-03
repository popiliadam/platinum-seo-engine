"""P1-13 (codex audit Phase 1): generate-images (status: active) requires
mcp__higgsfield__generate_image, but Higgsfield is intentionally NOT a plugin
.mcp.json server (F-24 would flag it as orphan inventory). Represent it as a
user-level external dependency in mcp-tool-registry.json
(external_user_dependencies, NOT under servers) and make the skill's preflight
say so — so a required-but-not-plugin-installed tool is documented governance,
not a silent gap.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_generate_images_higgsfield_declared_as_external():
    reg = json.loads((ROOT / "mcp-tool-registry.json").read_text(encoding="utf-8"))
    ext = reg.get("external_user_dependencies", {}).get("higgsfield", {})
    assert "generate_image" in (ext.get("tools") or []), "Higgsfield generate_image must be declared external"
    assert "higgsfield" not in reg.get("servers", {}), "Higgsfield must NOT be a plugin .mcp.json server (F-24)"


def test_generate_images_skill_preflight_mentions_external():
    txt = (ROOT / "skills/production/generate-images/SKILL.md").read_text(encoding="utf-8")
    assert re.search(r"higgsfield", txt, re.I) and re.search(r"external|user-level|preflight", txt, re.I)
