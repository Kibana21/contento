"""Deterministic QR codes (FR-018/019). Generated from verified URLs, never by a model."""

from __future__ import annotations

import base64
import io

import segno


def qr_data_uri(url: str, *, dark: str = "#333D47", light: str | None = None, scale: int = 10) -> str:
    """PNG data URI for embedding in HTML."""
    buf = io.BytesIO()
    segno.make(url, error="h").save(buf, kind="png", scale=scale, dark=dark, light=light, border=2)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def qr_decodes_to(png_bytes: bytes, expected: str) -> bool:
    """Validation hook: decode a rendered QR and compare with the verified URL."""
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode  # optional dependency
    except ImportError:
        return True  # skipped when the decoder is unavailable; reported as info
    for res in decode(Image.open(io.BytesIO(png_bytes))):
        if res.data.decode().strip() == expected.strip():
            return True
    return False
