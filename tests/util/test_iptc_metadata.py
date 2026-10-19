"""IPTC DigitalSourceType written as real XMP (S-07, R-123).

Google (gen-AI content guidance, 2026-10-01) and Merchant Center read the IPTC
``Iptc4xmpExt:DigitalSourceType`` property, whose value for fully AI-generated
images is the IRI
``http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia``.
The writer used to put a plain-text note in EXIF UserComment/ImageDescription,
which no IPTC reader recognises.

Covers ``scripts/util/iptc_metadata``:
  1. JPEG / WebP / PNG / AVIF carry the property in their XMP packet.
  2. Existing EXIF survives; calling twice is idempotent.
  3. The reader returns the IRI; a plain image reads None.
  4. Missing file → FileNotFoundError; unsupported format → ValueError.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, features

from scripts.util.iptc_metadata import (
    TRAINED_ALGORITHMIC_MEDIA,
    read_digital_source_type,
    write_ai_image_disclosure,
)

IRI = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"


def _make(tmp_path: Path, fmt: str, **save_kw) -> Path:
    p = tmp_path / f"test.{fmt.lower()}"
    Image.new("RGB", (10, 10), color=(0, 128, 255)).save(p, format=fmt, **save_kw)
    return p


def test_constant_is_the_iptc_iri() -> None:
    assert TRAINED_ALGORITHMIC_MEDIA == IRI


@pytest.mark.parametrize("fmt", [
    "JPEG", "WEBP", "PNG",
    pytest.param("AVIF", marks=pytest.mark.skipif(
        not features.check("avif"), reason="this Pillow build has no AVIF codec")),
])
def test_xmp_carries_digital_source_type(tmp_path: Path, fmt: str) -> None:
    p = _make(tmp_path, fmt)
    write_ai_image_disclosure(p)
    assert read_digital_source_type(p) == IRI
    with Image.open(p) as img:
        assert img.format == fmt
        xmp = img.info.get("xmp") or img.info.get("XML:com.adobe.xmp")
    text = xmp.decode("utf-8") if isinstance(xmp, bytes) else xmp
    assert "Iptc4xmpExt:DigitalSourceType" in text


def test_existing_exif_is_preserved(tmp_path: Path) -> None:
    exif = Image.Exif()
    exif[0x0131] = "PSEO-test"  # Software
    p = _make(tmp_path, "JPEG", exif=exif.tobytes())
    write_ai_image_disclosure(p)
    with Image.open(p) as img:
        assert img.getexif().get(0x0131) == "PSEO-test"


def test_idempotent(tmp_path: Path) -> None:
    p = _make(tmp_path, "JPEG")
    write_ai_image_disclosure(p)
    write_ai_image_disclosure(p)
    assert read_digital_source_type(p) == IRI


def test_plain_image_reads_none(tmp_path: Path) -> None:
    assert read_digital_source_type(_make(tmp_path, "JPEG")) is None


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_ai_image_disclosure(tmp_path / "does-not-exist.jpg")


def test_unsupported_format_raises(tmp_path: Path) -> None:
    p = _make(tmp_path, "BMP")
    with pytest.raises(ValueError, match="BMP"):
        write_ai_image_disclosure(p)


# --- review follow-ups: tagging must not degrade the image -------------------------

def test_jpeg_keeps_quantization_and_subsampling(tmp_path: Path) -> None:
    p = _make(tmp_path, "JPEG", quality=80, subsampling=0)
    with Image.open(p) as before:
        q_before = before.quantization
    write_ai_image_disclosure(p)
    with Image.open(p) as after:
        assert after.quantization == q_before
        from PIL import JpegImagePlugin
        assert JpegImagePlugin.get_sampling(after) == 0


@pytest.mark.parametrize("fmt", ["JPEG", "WEBP", "PNG"])
def test_icc_profile_is_kept(tmp_path: Path, fmt: str) -> None:
    from PIL import ImageCms
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    p = _make(tmp_path, fmt, icc_profile=icc)
    write_ai_image_disclosure(p)
    with Image.open(p) as img:
        assert img.info.get("icc_profile") == icc


def test_animated_webp_keeps_all_frames(tmp_path: Path) -> None:
    p = tmp_path / "anim.webp"
    frames = [Image.new("RGB", (10, 10), c) for c in ((255, 0, 0), (0, 255, 0), (0, 0, 255))]
    frames[0].save(p, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    write_ai_image_disclosure(p)
    with Image.open(p) as img:
        assert getattr(img, "n_frames", 1) == 3
    assert read_digital_source_type(p) == IRI
