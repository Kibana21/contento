"""D3 — portrait processing (BRD §18, ADR: identity is never generated).

Permitted: crop, background removal, background replacement, lighting and colour
correction, framing, scaling, masking. Not permitted, ever: changing the face, age,
ethnicity or body shape. Nothing here is generative — it is pixel work on the
representative's own photograph.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

CUTOUT_SUFFIX = "-cutout.png"


@dataclass
class PortraitResult:
    path: Path
    cutout: bool
    note: str | None = None


def cutout_path_for(source: Path) -> Path:
    return Path(source).with_name(f"{Path(source).stem}{CUTOUT_SUFFIX}")


def remove_background(source: Path | str, *, force: bool = False) -> PortraitResult:
    """Produce a transparent PNG of the person, cached next to the original."""
    source = Path(source)
    target = cutout_path_for(source)
    if target.exists() and not force:
        return PortraitResult(target, True, "cached")
    try:
        from rembg import new_session, remove

        session = new_session("birefnet-portrait") if _has_model("birefnet-portrait") else new_session("u2net")
        with Image.open(source) as im:
            result = remove(im.convert("RGB"), session=session, post_process_mask=True)
        result = _trim_transparent(result)
        result.save(target)
        return PortraitResult(target, True)
    except Exception as exc:  # a failed cut-out must not stop a campaign
        return PortraitResult(source, False, f"cut-out unavailable: {type(exc).__name__}")


def _has_model(name: str) -> bool:
    return any(Path.home().joinpath(".u2net", f"{name}.onnx").exists() for _ in (0,))


def _trim_transparent(im: Image.Image, padding: int = 8) -> Image.Image:
    """Crop to the subject so layouts can position the person, not the empty space."""
    alpha = im.getchannel("A")
    box = alpha.getbbox()
    if not box:
        return im
    left, top, right, bottom = box
    return im.crop((max(0, left - padding), max(0, top - padding),
                    min(im.width, right + padding), min(im.height, bottom + padding)))


def enhance(source: Path | str, *, warmth: float = 1.04, contrast: float = 1.03,
            brightness: float = 1.02) -> Path:
    """Gentle lighting and colour correction only (Brand Standards: warm, natural light)."""
    source = Path(source)
    target = source.with_name(f"{source.stem}-graded{source.suffix}")
    with Image.open(source) as im:
        im = im.convert("RGBA" if source.suffix.lower() == ".png" else "RGB")
        im = ImageEnhance.Color(im).enhance(warmth)
        im = ImageEnhance.Contrast(im).enhance(contrast)
        im = ImageEnhance.Brightness(im).enhance(brightness)
        im.save(target)
    return target


def drop_shadow(cutout: Path | str, *, blur: int = 28, offset: tuple[int, int] = (0, 14),
                opacity: int = 70) -> Path:
    """Composite a soft shadow behind a cut-out so it sits on the page rather than floating."""
    cutout = Path(cutout)
    target = cutout.with_name(f"{cutout.stem}-shadow.png")
    with Image.open(cutout).convert("RGBA") as im:
        pad = blur * 3
        canvas = Image.new("RGBA", (im.width + pad * 2, im.height + pad * 2), (0, 0, 0, 0))
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        silhouette = Image.new("RGBA", im.size, (26, 30, 36, opacity))
        shadow.paste(silhouette, (pad + offset[0], pad + offset[1]), im)
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        canvas.alpha_composite(shadow)
        canvas.alpha_composite(im, (pad, pad))
        canvas.save(target)
    return target


def duotone(source: Path | str, dark: str = "#333D47", light: str = "#FFEDF1") -> Path:
    """Brand duotone treatment for supporting imagery (never for the representative's face)."""
    source = Path(source)
    target = source.with_name(f"{source.stem}-duotone.png")
    dark_rgb = tuple(int(dark[i:i + 2], 16) for i in (1, 3, 5))
    light_rgb = tuple(int(light[i:i + 2], 16) for i in (1, 3, 5))
    with Image.open(source) as im:
        grey = im.convert("L")
        ramp = []
        for i in range(256):
            ramp.append(tuple(int(dark_rgb[c] + (light_rgb[c] - dark_rgb[c]) * i / 255) for c in range(3)))
        out = Image.new("RGB", im.size)
        out.putdata([ramp[p] for p in grey.getdata()])
        out.save(target)
    return target


def signature(path: Path | str) -> str:
    """Short digest used in lineage to prove which photograph was used."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def framed(cutout: Path | str, *, tint: str = "#F6CFD9", ratio: float = 0.78,
           gradient_to: str | None = "#FFFFFF") -> Path:
    """Composite a cut-out onto a brand-tinted panel.

    A framed portrait that keeps the photographer's grey studio wall looks flat and
    off-brand. Placing the cut-out on an AIA tint makes framed treatments (panel, arch,
    circle) feel designed rather than cropped.
    """
    cutout = Path(cutout)
    target = cutout.with_name(f"{cutout.stem}-framed.png")
    tint_rgb = tuple(int(tint[i:i + 2], 16) for i in (1, 3, 5))
    end_rgb = tuple(int(gradient_to[i:i + 2], 16) for i in (1, 3, 5)) if gradient_to else tint_rgb

    with Image.open(cutout).convert("RGBA") as person:
        height = person.height
        width = max(int(height * ratio), person.width)
        panel = Image.new("RGB", (width, height))
        for y in range(height):  # soft vertical gradient, light at the top
            blend = y / max(height - 1, 1)
            row = tuple(int(end_rgb[c] + (tint_rgb[c] - end_rgb[c]) * blend) for c in range(3))
            panel.paste(row, (0, y, width, y + 1))
        panel = panel.convert("RGBA")
        panel.alpha_composite(person, ((width - person.width) // 2, 0))
        panel.save(target)
    return target
