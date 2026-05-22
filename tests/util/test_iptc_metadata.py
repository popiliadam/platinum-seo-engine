"""IPTC metadata writer — DigitalSourceType=TrainedAlgorithmicMedia.

Covers ``scripts/util/iptc_metadata.write_ai_image_disclosure``:
  1. Round-trip: write the tag, read it back from EXIF.
  2. Idempotent: calling twice does not corrupt the metadata.
  3. Missing input file raises FileNotFoundError.
  4. WebP support: EXIF survives the format-specific save path.

AVIF is intentionally out of scope — piexif cannot parse AVIF, so the
``generate-images`` pipeline skips AVIF outputs (documented in R-78
failure_mode).
"""

from __future__ import annotations

from pathlib import Path

import piexif
import pytest
from PIL import Image

from scripts.util.iptc_metadata import (
    DIGITAL_SOURCE_TYPE_AI,
    write_ai_image_disclosure,
)


def _make_jpeg(tmp_path: Path) -> Path:
    img = Image.new("RGB", (10, 10), color=(0, 128, 255))
    p = tmp_path / "test.jpg"
    img.save(p, format="JPEG")
    return p


def test_write_ai_disclosure_adds_iptc_tag(tmp_path: Path) -> None:
    """After write_ai_image_disclosure, DigitalSourceType=TrainedAlgorithmicMedia present in EXIF."""
    img_path = _make_jpeg(tmp_path)
    write_ai_image_disclosure(img_path)

    exif_dict = piexif.load(str(img_path))
    image_description = exif_dict["0th"].get(piexif.ImageIFD.ImageDescription, b"")
    user_comment = exif_dict["Exif"].get(piexif.ExifIFD.UserComment, b"")
    assert (
        b"TrainedAlgorithmicMedia" in image_description
        or b"TrainedAlgorithmicMedia" in user_comment
    )


def test_write_ai_disclosure_idempotent(tmp_path: Path) -> None:
    """Calling twice does not corrupt; second call overwrites cleanly."""
    img_path = _make_jpeg(tmp_path)
    write_ai_image_disclosure(img_path)
    write_ai_image_disclosure(img_path)
    exif_dict = piexif.load(str(img_path))
    assert b"TrainedAlgorithmicMedia" in exif_dict["0th"].get(
        piexif.ImageIFD.ImageDescription, b""
    )


def test_write_ai_disclosure_raises_on_missing_file(tmp_path: Path) -> None:
    """Missing input file raises FileNotFoundError (caller-visible failure)."""
    with pytest.raises(FileNotFoundError):
        write_ai_image_disclosure(tmp_path / "does-not-exist.jpg")


def test_write_ai_disclosure_supports_webp(tmp_path: Path) -> None:
    """WebP: PIL exif round-trip via the info dict."""
    img = Image.new("RGB", (10, 10), color=(0, 128, 255))
    p = tmp_path / "test.webp"
    img.save(p, format="WEBP")
    write_ai_image_disclosure(p)
    re_read = Image.open(p)
    assert re_read.info.get("exif") is not None


def test_digital_source_type_constant_format() -> None:
    """Public constant carries the expected payload (regression guard)."""
    assert DIGITAL_SOURCE_TYPE_AI == b"DigitalSourceType=TrainedAlgorithmicMedia"
