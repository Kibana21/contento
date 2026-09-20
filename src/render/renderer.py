"""D6 — DesignDoc -> HTML -> Chromium -> PNG/JPEG/PDF + measured DOM geometry.

HTML/CSS is the layout engine, not the deliverable: agents never see it. Chromium is
used because it shapes Tamil/Chinese correctly, reflows across presets instead of
cropping, and lets us measure every text box exactly for overflow checks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..contracts.design import DesignDoc
from .context import RenderContext

TEMPLATES = Path(__file__).parent / "templates"
REFERENCE_WIDTH = 1080  # poster_scale sizes in tokens/typography.json are quoted at this width

#: Geometry + computed styles pulled back out of the rendered page for validators.
_MEASURE_JS = """
() => {
  const poster = document.querySelector('.poster');
  const pr = poster.getBoundingClientRect();
  const nodes = [...poster.querySelectorAll('[id]')].map(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      id: el.id, tag: el.tagName.toLowerCase(), class: el.className,
      x: r.x - pr.x, y: r.y - pr.y, width: r.width, height: r.height,
      scrollWidth: el.scrollWidth, scrollHeight: el.scrollHeight,
      // tolerance: display faces report descender overshoot as scrollHeight
      overflows: el.scrollHeight > Math.ceil(r.height) + Math.max(2, parseFloat(cs.fontSize) * 0.18) ||
                 el.scrollWidth > Math.ceil(r.width) + 2,
      outsideCanvas: r.x - pr.x < -1 || r.y - pr.y < -1 ||
                     (r.x - pr.x) + r.width > pr.width + 1 || (r.y - pr.y) + r.height > pr.height + 1,
      fontSize: parseFloat(cs.fontSize), fontFamily: cs.fontFamily, fontWeight: cs.fontWeight,
      color: cs.color, backgroundColor: cs.backgroundColor, opacity: cs.opacity,
      text: (el.innerText || '').trim().slice(0, 160),
      qrTarget: el.dataset.qrTarget || null,
    };
  });
  return {canvas: {width: pr.width, height: pr.height},
          background: getComputedStyle(poster).backgroundColor, elements: nodes};
}
"""


@dataclass
class RenderResult:
    html_path: Path
    image_path: Path
    geometry: dict[str, Any]
    format: str

    @property
    def elements(self) -> list[dict[str, Any]]:
        return self.geometry["elements"]

    def element(self, element_id: str) -> dict[str, Any] | None:
        return next((e for e in self.elements if e["id"] == element_id), None)


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "xml", "j2"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["min"] = min
    return env


def available_families() -> list[str]:
    """Layout families the design builder may use (skeletons, not raw templates)."""
    from .layouts import FAMILIES

    return sorted(FAMILIES)


def build_html(ctx: RenderContext) -> str:
    """Render the design to HTML. Raises if a referenced fact or copy slot is missing."""
    design = ctx.design
    family = design.layout_family
    if family not in available_families():
        raise KeyError(f"unknown layout family {family!r}; have {available_families()}")

    payloads = [ctx.element_payload(e) for e in design.elements if e.visible]
    by_slot: dict[str, list[dict[str, Any]]] = {}
    for p in payloads:
        by_slot.setdefault(p["slot"], []).append(p)

    scale_factor = design.canvas.short_edge / REFERENCE_WIDTH
    spacing = ctx.brand.spacing.get("poster", {})
    unit = int(ctx.brand.spacing.get("base_unit", {}).get("value", 4))
    fonts = [
        {"family": "AIAEverest", "weight": 400, "uri": ctx.brand.font_path("display_regular")},
        {"family": "AIAEverest", "weight": 700, "uri": ctx.brand.font_path("display_medium")},
        {"family": "Open Sans", "weight": 400, "uri": ctx.brand.font_path("body_regular")},
        {"family": "Noto Sans SC", "weight": 400, "uri": ctx.brand.font_path("zh_hans")},
        {"family": "Noto Sans Tamil", "weight": 400, "uri": ctx.brand.font_path("ta")},
    ]
    from .layouts import FAMILIES

    skeleton = FAMILIES.get(family)
    template_name = skeleton.template if skeleton else family
    template = _env().get_template(f"{template_name}.html.j2")
    return template.render(
        design=design,
        composition=design.composition,
        theme=str(getattr(design.theme, "value", design.theme)),
        headline_size=ctx.brand.type_scale()["headline"]["size"] * scale_factor,
        brand=ctx.brand,
        background=ctx.background_payload(),
        elements_by_slot=by_slot,
        scale_factor=scale_factor,
        margin=round(spacing.get("outer_margin", 64) * scale_factor),
        gutter=round(spacing.get("gutter", 24) * scale_factor),
        unit=unit,
        logo_height=round(design.canvas.short_edge * 0.07),
        photo_width=round(design.canvas.width * 0.46),
        photo_height=round(design.canvas.height * 0.58),
        qr_size=round(design.canvas.short_edge * 0.12),
        fonts=[{**f, "uri": Path(f["uri"]).resolve().as_uri()} for f in fonts if f["uri"]],
    )


async def render_async(
    ctx: RenderContext,
    out_dir: Path,
    *,
    fmt: Literal["png", "jpeg", "pdf"] = "png",
    quality: int = 92,
    name: str | None = None,
) -> RenderResult:
    from playwright.async_api import async_playwright

    design: DesignDoc = ctx.design
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = name or f"{design.design_id}-v{design.version}"
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(build_html(ctx))
    image_path = out_dir / f"{stem}.{fmt}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none"])
        page = await browser.new_page(
            viewport={"width": design.canvas.width, "height": design.canvas.height},
            device_scale_factor=1,
        )
        await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        geometry = await page.evaluate(_MEASURE_JS)
        if fmt == "pdf":
            await page.pdf(path=str(image_path), width=f"{design.canvas.width}px",
                           height=f"{design.canvas.height}px", print_background=True, margin={"top": "0", "bottom": "0"})
        else:
            await page.locator(".poster").screenshot(
                path=str(image_path), type=fmt, **({"quality": quality} if fmt == "jpeg" else {})
            )
        await browser.close()

    (out_dir / f"{stem}.geometry.json").write_text(json.dumps(geometry, indent=2))
    return RenderResult(html_path=html_path, image_path=image_path, geometry=geometry, format=fmt)


def render(ctx: RenderContext, out_dir: Path, **kw: Any) -> RenderResult:
    """Synchronous wrapper used by the CLI and tests."""
    import asyncio

    return asyncio.run(render_async(ctx, out_dir, **kw))
