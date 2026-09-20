"""Pixel-level checks on the exported image: red dominance, gradients, ink coverage."""

from __future__ import annotations

from pathlib import Path

from ..contracts.common import Finding, Severity, ValidationReport
from .colour import is_chromatic, is_reddish

SAMPLE_EDGE = 220  # downsample before counting; keeps checks fast and stable


Rect = tuple[float, float, float, float]  # x, y, w, h in canvas pixels


def analyse(image_path: Path, exclude: list[Rect] | None = None) -> dict[str, float]:
    """Count colour usage, ignoring photographic regions.

    Photographs carry their own colours (skin, clothing, venue). The Brand Standards rule
    is about *design* colour, so agent photos and placed imagery are masked out first.
    """
    from PIL import Image

    im = Image.open(image_path).convert("RGB")
    full_w, full_h = im.size
    im.thumbnail((SAMPLE_EDGE, SAMPLE_EDGE))
    sx, sy = im.width / full_w, im.height / full_h
    mask = [(x * sx, y * sy, w * sx, h * sy) for x, y, w, h in (exclude or [])]

    pixels: list[tuple[int, int, int]] = []
    data = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if any(rx <= x < rx + rw and ry <= y < ry + rh for rx, ry, rw, rh in mask):
                continue
            pixels.append(data[x, y])
    total = len(pixels)
    chromatic = [p for p in pixels if is_chromatic(p)]
    red = [p for p in chromatic if is_reddish(p)]
    return {
        "total": total,
        "chromatic_share": len(chromatic) / total if total else 0.0,
        "red_share_of_canvas": len(red) / total if total else 0.0,
        "red_share_of_chromatic": len(red) / len(chromatic) if chromatic else 0.0,
        "distinct_colours": float(len({p for p in pixels})),
    }


def photo_rects(geometry: dict, photo_ids: set[str]) -> list[Rect]:
    """Bounding boxes of photographic elements, for masking."""
    return [(e["x"], e["y"], e["width"], e["height"]) for e in geometry["elements"]
            if e["id"] in photo_ids]


def validate_pixels(image_path: Path, *, theme: str = "highlight",
                    exclude: list[Rect] | None = None) -> ValidationReport:
    """AIA Red must be the dominant colour in any design (Brand Standards p51/p54).

    'Dominant' is read as: of the coloured (non-neutral) area, red and its tints lead.
    A bold-theme design must additionally be mostly red by area.
    """
    stats = analyse(image_path, exclude)
    findings: list[Finding] = []
    checks = 2

    if stats["chromatic_share"] > 0.02 and stats["red_share_of_chromatic"] < 0.5:
        findings.append(Finding(
            rule_id="colour.red_dominant", severity=Severity.ERROR,
            message=f"AIA Red is {stats['red_share_of_chromatic']:.0%} of the coloured area; "
                    "it must be the dominant colour",
            evidence=f"chromatic {stats['chromatic_share']:.1%} of canvas",
            suggestion="increase the red graphic area or remove competing colours"))

    if theme == "bold" and stats["red_share_of_canvas"] < 0.35:
        findings.append(Finding(
            rule_id="colour.bold_ground", severity=Severity.WARN,
            message=f"Bold theme but red covers only {stats['red_share_of_canvas']:.0%} of the canvas",
            suggestion="use AIA Red as the solid background"))

    return ValidationReport(checks_run=checks, findings=findings)
