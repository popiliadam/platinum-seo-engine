"""IPTC DigitalSourceType writer for AI-generated images (R-123, S-07).

Google's gen-AI content guidance (2026-10-01) and Merchant Center
(https://support.google.com/merchants/answer/14216904) read the IPTC
``Iptc4xmpExt:DigitalSourceType`` property. For fully AI-generated images its
value is the IPTC NewsCodes IRI

    http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia

The property lives in the image's XMP packet. Pillow writes XMP natively for
JPEG, WebP and AVIF (``save(..., xmp=...)``) and for PNG as the standard
``XML:com.adobe.xmp`` iTXt chunk — no exiftool or piexif needed. Existing EXIF is
carried over unchanged. The tag is invisible metadata: it does not add any
visible "AI-generated" text to the page (the visible-disclosure ban stays).
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Union

from PIL import Image
from PIL.PngImagePlugin import PngInfo

TRAINED_ALGORITHMIC_MEDIA = (
    "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
)
"""IPTC DigitalSourceType value for media created by a trained model."""

SUPPORTED_FORMATS = frozenset({"JPEG", "WEBP", "PNG", "AVIF"})
_PNG_XMP_KEY = "XML:com.adobe.xmp"

_XMP_PACKET = (
    '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    '  <rdf:Description rdf:about=""\n'
    '    xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/"\n'
    f'    Iptc4xmpExt:DigitalSourceType="{TRAINED_ALGORITHMIC_MEDIA}"/>\n'
    ' </rdf:RDF>\n'
    '</x:xmpmeta>\n'
    '<?xpacket end="w"?>'
)
_DST_RE = re.compile(
    r'Iptc4xmpExt:DigitalSourceType\s*=\s*"([^"]+)"'
    r"|<Iptc4xmpExt:DigitalSourceType>([^<]+)</Iptc4xmpExt:DigitalSourceType>"
)


def _xmp_text(img: Image.Image) -> str:
    raw = img.info.get("xmp") or img.info.get(_PNG_XMP_KEY) or ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def write_ai_image_disclosure(image_path: Union[Path, str]) -> None:
    """Write ``Iptc4xmpExt:DigitalSourceType = trainedAlgorithmicMedia`` into the
    XMP packet of ``image_path`` (JPEG, WebP, PNG or AVIF), keeping its format and EXIF.

    Idempotent: the packet is rewritten, not appended.

    Raises:
        FileNotFoundError: ``image_path`` does not exist.
        ValueError: the image format is not JPEG / WebP / PNG / AVIF.
    """
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(p)

    with Image.open(p) as src:
        fmt = src.format
        if fmt not in SUPPORTED_FORMATS:
            raise ValueError(
                f"unsupported image format {fmt!r} for IPTC XMP; "
                f"supported: {sorted(SUPPORTED_FORMATS)}"
            )
        save_kw: dict = {"format": fmt}
        exif = src.info.get("exif")
        if exif:
            save_kw["exif"] = exif
        icc = src.info.get("icc_profile")
        if icc:  # the JPEG / WebP savers take it only as an argument
            save_kw["icc_profile"] = icc
        if fmt == "PNG":
            info = PngInfo()
            info.add_itxt(_PNG_XMP_KEY, _XMP_PACKET)
            save_kw["pnginfo"] = info
        else:
            save_kw["xmp"] = _XMP_PACKET.encode("utf-8")
        if fmt == "JPEG":
            # "keep" reuses the original quantization tables and subsampling;
            # it only works when saving from the opened JpegImageFile itself.
            save_kw["quality"] = "keep"
        if getattr(src, "n_frames", 1) > 1:
            save_kw["save_all"] = True  # animated WebP / APNG keep every frame
        buf = io.BytesIO()
        src.save(buf, **save_kw)
    p.write_bytes(buf.getvalue())


def read_digital_source_type(image_path: Union[Path, str]) -> str | None:
    """The IPTC DigitalSourceType IRI in the image's XMP, or None."""
    with Image.open(image_path) as img:
        match = _DST_RE.search(_xmp_text(img))
    if match is None:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


__all__ = (
    "TRAINED_ALGORITHMIC_MEDIA",
    "SUPPORTED_FORMATS",
    "write_ai_image_disclosure",
    "read_digital_source_type",
)
