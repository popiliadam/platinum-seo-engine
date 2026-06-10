"""IPTC/EXIF metadata writer for AI-generated images.

Per Google Merchant Center AI-image disclosure policy
(https://support.google.com/merchants/answer/14216904) and reaffirmed
in the 2026-05-15 AI Optimization Guide.

IPTC field: DigitalSourceType
Value for fully AI-generated images: TrainedAlgorithmicMedia
(IRI: http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia)

Encoding strategy: EXIF UserComment + TIFF ImageDescription. Formats
without a native IPTC chunk (JPEG/WebP via PIL) carry the disclosure
through EXIF instead — IPTC parsers and EXIF text readers both surface
it. AVIF lacks piexif support; the ``generate-images`` skill skips it
(see ``rules/content-html-discipline.md`` R-123 failure_mode).
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import piexif
from PIL import Image

DIGITAL_SOURCE_TYPE_AI = b"DigitalSourceType=TrainedAlgorithmicMedia"
"""Bytes payload — visible in IPTC parsers and EXIF text readers."""

USER_COMMENT_PAYLOAD = b"ASCII\x00\x00\x00" + DIGITAL_SOURCE_TYPE_AI
"""EXIF UserComment with the ASCII charset prefix required by the EXIF spec."""


def write_ai_image_disclosure(image_path: Union[Path, str]) -> None:
    """Write IPTC ``DigitalSourceType=TrainedAlgorithmicMedia`` to ``image_path``.

    Supported formats: JPEG, WebP (PIL handles EXIF round-trip natively).
    AVIF is unsupported by piexif — callers must filter it before invoking.

    Behavior:
        - Reads any existing EXIF, merges the disclosure tags, re-saves.
        - Idempotent: calling twice yields the same bytes for the tag.
        - Preserves the source format on save (``img.format``).

    Raises:
        FileNotFoundError: if ``image_path`` does not exist on disk.
    """
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(p)

    img = Image.open(p)
    fmt = img.format

    existing_exif = img.info.get("exif", b"")
    if existing_exif:
        try:
            exif_dict = piexif.load(existing_exif)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
    else:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    exif_dict["Exif"][piexif.ExifIFD.UserComment] = USER_COMMENT_PAYLOAD
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = DIGITAL_SOURCE_TYPE_AI

    exif_bytes = piexif.dump(exif_dict)
    img.save(p, format=fmt, exif=exif_bytes)
