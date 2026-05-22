"""Smoke test: piexif importable + JPEG EXIF round-trip works.

Verifies the dependency is installed and functional before the IPTC
metadata writer utility (Task 2.2) and ``generate-images`` integration
(Task 2.3) consume it. This is intentionally minimal — full coverage
lives in ``tests/util/test_iptc_metadata.py``.
"""

from __future__ import annotations

import io

import piexif
from PIL import Image


def test_piexif_round_trip_jpeg() -> None:
    """Write EXIF dataset, read back, assert equal."""
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    exif_dict = {"0th": {piexif.ImageIFD.Software: b"PSEO-test"}}
    exif_bytes = piexif.dump(exif_dict)

    out_buf = io.BytesIO()
    img.save(out_buf, format="JPEG", exif=exif_bytes)
    out_buf.seek(0)

    read_dict = piexif.load(out_buf.getvalue())
    assert read_dict["0th"][piexif.ImageIFD.Software] == b"PSEO-test"
