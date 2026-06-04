"""Guard: Pillow must be declared in the dependency manifests.

Root-cause regression guard for the 2026-06-04 Codex P0-02 finding. PIL is
imported unconditionally by scripts/util/iptc_metadata.py (R-78 AI-image
disclosure) and skills/production/generate-images (R-76 format cascade), but
piexif — though declared — does NOT pull Pillow transitively, so a clean
`pip install -r requirements-lock.txt` previously crashed pytest collection
with ModuleNotFoundError: No module named 'PIL'.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pillow_in_requirements() -> None:
    reqs = (ROOT / "requirements.txt").read_text().lower()
    assert "pillow" in reqs, (
        "Pillow must be declared in requirements.txt — PIL is a hard runtime "
        "dependency (iptc_metadata.py / generate-images) not pulled by piexif"
    )


def test_pillow_pinned_in_lock() -> None:
    lock = (ROOT / "requirements-lock.txt").read_text().lower()
    assert "pillow" in lock, (
        "Pillow must be pinned in requirements-lock.txt (CI installs the lock)"
    )
