"""Colour helpers shared by the validators: WCAG contrast and hue classification."""

from __future__ import annotations

import colorsys
import re

RGB = tuple[float, float, float]


def parse_colour(value: str) -> RGB | None:
    """Accept '#RGB', '#RRGGBB', 'rgb(r,g,b)' or 'rgba(r,g,b,a)'."""
    value = value.strip()
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) != 6:
            return None
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    m = re.match(r"rgba?\(([^)]+)\)", value)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
    try:
        return tuple(float(p) for p in parts[:3])  # type: ignore[return-value]
    except ValueError:
        return None


def relative_luminance(rgb: RGB) -> float:
    def channel(c: float) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def is_reddish(rgb: RGB, *, min_sat: float = 0.12) -> bool:
    """AIA Red and its tints: red/magenta hue with enough saturation to read as brand red."""
    r, g, b = (c / 255 for c in rgb)
    h, ls, s = colorsys.rgb_to_hls(r, g, b)
    hue = h * 360
    return s >= min_sat and (hue <= 25 or hue >= 320) and ls < 0.97


def is_chromatic(rgb: RGB, *, min_sat: float = 0.12) -> bool:
    r, g, b = (c / 255 for c in rgb)
    _, ls, s = colorsys.rgb_to_hls(r, g, b)
    return s >= min_sat and 0.03 < ls < 0.97
