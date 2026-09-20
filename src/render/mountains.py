"""Moving Mountains SVG generator (Brand Standards pp. 58-71).

The signature AIA graphic is *never* AI-generated: pointed triangles are an explicit
don't (p69). Shapes are built on the official 560x400 grid with 8px rounded corners,
and coloured strictly from the tint/opacity tables in tokens/moving-mountains.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

GRID_W, GRID_H = 560, 400
CORNER_RADIUS = 8

#: Hand-built peak sets on the official grid, front (index 0) to back.
#: Each peak is (x_left, x_apex, x_right, apex_y): a four-sided shape on the baseline.
SHAPE_SETS: dict[str, list[tuple[int, int, int, int]]] = {
    # Front (index 0) to back. Apexes are deliberately off-centre and bases overlap, so the
    # set reads as one range rather than separate symmetrical triangles.
    "classic_3": [(60, 330, 520, 120), (-80, 110, 300, 185), (300, 380, 640, 150)],
    "classic_4": [(80, 350, 540, 105), (-90, 95, 280, 195), (230, 300, 520, 150), (430, 560, 650, 175)],
    "wide_3": [(-40, 220, 420, 150), (180, 420, 620, 115), (350, 470, 660, 195)],
    "tall_4": [(120, 360, 560, 75), (-60, 130, 330, 160), (-120, 40, 200, 225), (420, 520, 660, 185)],
}


@dataclass(frozen=True)
class Layer:
    """One mountain: resolved colour, opacity and optional blend mode or stroke."""

    fill: str
    opacity: float = 1.0
    blend: str | None = None
    image_mask: bool = False
    stroke: str | None = None
    stroke_width: float = 3.0


def _peak_path(peak: tuple[int, int, int, int], sx: float, sy: float, radius: float) -> str:
    """Rounded-apex quadrilateral standing on the baseline, in output pixel space.

    Coordinates are scaled from the official grid before the corner radius is applied, so
    the apex stays rounded instead of stretching into a sharp triangle (p69 don't).
    """
    x_left, x_apex, x_right, apex_y = peak
    xl, xa, xr = x_left * sx, x_apex * sx, x_right * sx
    ya, base = apex_y * sy, GRID_H * sy
    dx_l, dy_l = xa - xl, base - ya
    dx_r, dy_r = xr - xa, base - ya
    ll = max((dx_l**2 + dy_l**2) ** 0.5, 1e-6)
    lr = max((dx_r**2 + dy_r**2) ** 0.5, 1e-6)
    r = min(radius, ll * 0.45, lr * 0.45)
    ax1, ay1 = xa - dx_l * r / ll, ya + dy_l * r / ll
    ax2, ay2 = xa + dx_r * r / lr, ya + dy_r * r / lr
    return (
        f"M {xl:.1f} {base:.1f} L {ax1:.1f} {ay1:.1f} "
        f"Q {xa:.1f} {ya:.1f} {ax2:.1f} {ay2:.1f} "
        f"L {xr:.1f} {base:.1f} Z"
    )


#: Variants the tokens describe as a rule rather than a layer table (Brand Standards p62).
OUTLINE_TINTS = (100, 60, 20)


def resolve_layers(variant: str, tokens: dict[str, Any], colour_of, *, on_red: bool = False) -> list[Layer]:
    """Turn a variant name into concrete fills using tokens/moving-mountains.json."""
    spec = tokens["variants"].get(variant)
    if spec is None:
        raise KeyError(f"unknown mountains variant {variant!r}; have {sorted(tokens['variants'])}")
    if variant == "outline":
        # "stroke red 100% or white only; inverted outline is white" (p62)
        stroke = "#FFFFFF" if on_red else colour_of("core.red")
        return [Layer(fill="none", stroke=stroke, stroke_width=3.0) for _ in OUTLINE_TINTS]
    mountains = spec["mountains"] if isinstance(spec, dict) and "mountains" in spec else spec
    if not isinstance(mountains, list):
        raise ValueError(f"variant {variant!r} is a rule description, not a layer table")
    layers: list[Layer] = []
    for m in mountains:
        if m.get("fill") == "image":
            layers.append(Layer(fill="none", image_mask=True))
            continue
        colour, tint = m["colour"], int(m["tint"])
        hex_value = colour_of(f"core.{colour}" if tint == 100 else f"core.{colour}.{tint}")
        layers.append(Layer(fill=hex_value, opacity=float(m.get("opacity", 1.0)), blend=m.get("blend")))
    return layers


def mountains_svg(
    variant: str,
    tokens: dict[str, Any],
    colour_of,
    *,
    on_red: bool = False,
    shape_set: str = "classic_3",
    width: int = GRID_W,
    height: int = GRID_H,
    image_href: str | None = None,
) -> str:
    """Render one Moving Mountains graphic as inline SVG.

    Constraints enforced here (p69): 3-4 peaks, no rotation, one graphic per design
    (the renderer places it once), rounded corners, front peak always first.
    """
    layers = resolve_layers(variant, tokens, colour_of, on_red=on_red)
    peaks = SHAPE_SETS[shape_set]
    if not 3 <= len(peaks) <= 4:
        raise ValueError("Moving Mountains use a minimum of 3 and a maximum of 4 peaks")
    if len(layers) != len(peaks):
        peaks = SHAPE_SETS["classic_4" if len(layers) == 4 else "classic_3"]
    if len(layers) != len(peaks):
        raise ValueError(f"variant {variant!r} needs {len(layers)} peaks; shape set has {len(peaks)}")

    sx, sy = width / GRID_W, height / GRID_H
    radius = CORNER_RADIUS * sx  # keep the 8px grid radius proportional after scaling
    body: list[str] = []
    defs: list[str] = []
    # draw back-to-front so the first (front) peak sits on top
    for idx in reversed(range(len(peaks))):
        layer, peak = layers[idx], peaks[idx]
        path = _peak_path(peak, sx, sy, radius)
        if layer.image_mask:
            if not image_href:
                raise ValueError("container variant requires image_href")
            defs.append(f'<clipPath id="mm-clip-{idx}"><path d="{path}"/></clipPath>')
            body.append(
                f'<image href="{image_href}" x="0" y="0" width="{width}" height="{height}" '
                f'preserveAspectRatio="xMidYMid slice" clip-path="url(#mm-clip-{idx})"/>'
            )
            continue
        style = f' style="mix-blend-mode:{layer.blend}"' if layer.blend else ""
        if layer.stroke:
            body.append(f'<path d="{path}" fill="none" stroke="{layer.stroke}" '
                        f'stroke-width="{layer.stroke_width * sx:g}" stroke-linejoin="round"{style}/>')
        else:
            body.append(f'<path d="{path}" fill="{layer.fill}" fill-opacity="{layer.opacity:g}"{style}/>')

    defs_block = f"<defs>{''.join(defs)}</defs>" if defs else ""
    return (
        f'<svg class="mountains" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'aria-hidden="true">{defs_block}{"".join(body)}</svg>'
    )
