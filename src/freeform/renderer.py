"""Render a bound page, and audit what Chromium actually built.

The audit is the guarantee, not the parser. A CSS allowlist can only block vectors someone
thought of, whereas asking the rendered document whether any pseudo-element carries content
catches every text-injection route at once. And the probe for hidden or covered elements
catches the likelier misbehaviour: not a model inventing a fact, but a design quietly losing
the mandatory legal line behind a photograph.

Long-form pages are rendered twice on purpose. A page whose height depends on its content
cannot have that height known beforehand, and measuring it is better than guessing: it keeps
`outsideCanvas` meaningful, keeps the pixel analysis aligned with the geometry, and makes the
height a recorded number rather than a side effect.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.common import Finding, Severity
from ..contracts.design import Canvas
from .binder import BoundPage

#: Geometry for the shared validators. The same shape `render/renderer.py` produces, so
#: `validate_dom` consumes either without knowing which engine ran.
MEASURE_JS = """
() => {
  const poster = document.querySelector('.poster');
  const pr = poster.getBoundingClientRect();
  const nodes = [...poster.querySelectorAll('[id]')].map(el => {
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      id: el.id, tag: el.tagName.toLowerCase(),
      class: typeof el.className === 'string' ? el.className : '',
      x: r.x - pr.x, y: r.y - pr.y, width: r.width, height: r.height,
      scrollWidth: el.scrollWidth, scrollHeight: el.scrollHeight,
      overflows: el.scrollHeight > Math.ceil(r.height) + Math.max(2, parseFloat(cs.fontSize) * 0.18) ||
                 el.scrollWidth > Math.ceil(r.width) + 2,
      outsideCanvas: r.x - pr.x < -1 || r.y - pr.y < -1 ||
                     (r.x - pr.x) + r.width > pr.width + 1 || (r.y - pr.y) + r.height > pr.height + 1,
      fontSize: parseFloat(cs.fontSize), fontFamily: cs.fontFamily, fontWeight: cs.fontWeight,
      color: cs.color, backgroundColor: cs.backgroundColor, opacity: cs.opacity,
      // opacity compounds down the tree, and a faded ancestor hides its children just as well
      effectiveOpacity: (() => { let o = 1, n = el;
        while (n && n !== document.documentElement) {
          o *= parseFloat(getComputedStyle(n).opacity); n = n.parentElement; }
        return o; })(),
      text: (el.innerText || '').trim().slice(0, 400),
      qrTarget: null,
    };
  });
  return {canvas: {width: pr.width, height: pr.height},
          background: getComputedStyle(poster).backgroundColor, elements: nodes};
}
"""

#: The three assertions that make ADR-001 hold against a document Chromium actually built.
AUDIT_JS = """
() => {
  const poster = document.querySelector('.poster');
  const problems = [];
  // 1. no pseudo-element may carry content: the catch-all for CSS text injection
  for (const el of poster.querySelectorAll('*')) {
    for (const pseudo of ['::before', '::after', '::marker']) {
      const c = getComputedStyle(el, pseudo).content;
      if (c && c !== 'none' && c !== 'normal')
        problems.push({rule: 'bind.injected_text', id: el.id || null,
                       evidence: pseudo + ' ' + c.slice(0, 60)});
    }
  }
  // 2/3. every bound element must be visible, and actually reachable on screen
  for (const el of poster.querySelectorAll('[id]')) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility !== 'visible' ||
        parseFloat(cs.opacity) < 0.15 || r.width < 1 || r.height < 1) {
      problems.push({rule: 'bind.hidden', id: el.id,
                     evidence: cs.display + '/' + cs.visibility + '/' + cs.opacity});
      continue;
    }
    const pts = [[.5,.5],[.15,.15],[.85,.15],[.15,.85],[.85,.85]];
    let covered = 0;
    for (const [fx, fy] of pts) {
      const hit = document.elementFromPoint(r.x + r.width * fx, r.y + r.height * fy);
      if (!(hit && (hit === el || el.contains(hit) || hit.contains(el)))) covered++;
    }
    if (covered >= 3)
      problems.push({rule: 'bind.occluded', id: el.id, evidence: covered + '/5 probes covered'});
  }
  // `text-transform` legitimately changes what innerText reports (AIA headlines are set in
  // capitals by the design, not by the writer), so report it and let the comparison allow for it
  return {problems, text: Object.fromEntries(
    [...poster.querySelectorAll('[id]')].map(el => [el.id, {
      text: (el.innerText || '').trim(),
      transform: getComputedStyle(el).textTransform}]))};
}
"""

MIN_LONG_FORM_RATIO = 1.0   # never shorter than the nominal canvas
MAX_LONG_FORM_RATIO = 4.0   # a poster, not a web page


@dataclass
class PageRender:
    html_path: Path
    image_path: Path
    geometry: dict[str, Any]
    canvas: Canvas
    findings: list[Finding] = field(default_factory=list)

    @property
    def format(self) -> str:
        return self.image_path.suffix.lstrip(".")


def _normalise(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _audit_findings(audit: dict, bound: BoundPage) -> list[Finding]:
    findings = [
        Finding(rule_id=p["rule"], severity=Severity.ERROR, element_id=p.get("id"),
                message={
                    "bind.injected_text": "text reached the page without being bound data",
                    "bind.hidden": "a bound element is not visible",
                    "bind.occluded": "a bound element is covered by something else",
                }[p["rule"]],
                evidence=p.get("evidence"),
                suggestion="every required element must be legible on the finished poster")
        for p in audit.get("problems", [])
    ]
    rendered = audit.get("text", {})
    for element_id, expected in bound.bound_text.items():
        node = rendered.get(element_id)
        if node is None:
            continue
        actual, transform = node["text"], node.get("transform", "none")
        # A design may set copy in capitals; that is styling, not substitution. Anything
        # beyond a case change still has to match the data exactly.
        left, right = _normalise(actual), _normalise(expected)
        if transform not in ("none", ""):
            left, right = left.casefold(), right.casefold()
        if left != right:
            findings.append(Finding(
                rule_id="bind.substituted", severity=Severity.ERROR, element_id=element_id,
                message="the rendered text differs from the data that was bound",
                evidence=f"{_normalise(actual)[:60]!r} != {_normalise(expected)[:60]!r}"))
    return findings


async def render_bound_async(bound: BoundPage, out_dir: Path, *, canvas: Canvas,
                             name: str, long_form: bool = False,
                             fmt: str = "png") -> PageRender:
    """Render, measure and audit one bound page."""
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{name}.html"
    html_path.write_text(bound.html)
    image_path = out_dir / f"{name}.{fmt}"
    settled = canvas

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            args=["--force-color-profile=srgb", "--font-render-hinting=none"])
        try:
            page = await browser.new_page(
                viewport={"width": canvas.width, "height": canvas.height},
                device_scale_factor=1)
            await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            await page.evaluate("document.fonts.ready")

            if long_form:
                # pass 1: let the content decide, then settle on a measured height
                content_height = await page.evaluate(
                    "() => document.querySelector('.poster').scrollHeight")
                height = max(int(canvas.width * MIN_LONG_FORM_RATIO),
                             min(int(content_height), int(canvas.width * MAX_LONG_FORM_RATIO)))
                height += (-height) % 4          # the 4px brand soft grid
                settled = Canvas(preset=canvas.preset, width=canvas.width, height=height,
                                 dpi=canvas.dpi)
                await page.set_viewport_size({"width": settled.width, "height": settled.height})
                await page.evaluate("document.fonts.ready")

            geometry = await page.evaluate(MEASURE_JS)
            audit = await page.evaluate(AUDIT_JS)
            await page.locator(".poster").screenshot(path=str(image_path), type=fmt)
        finally:
            await browser.close()

    (out_dir / f"{name}.geometry.json").write_text(json.dumps(geometry, indent=2))
    return PageRender(html_path=html_path, image_path=image_path, geometry=geometry,
                      canvas=settled, findings=_audit_findings(audit, bound))


def render_bound(bound: BoundPage, out_dir: Path, **kw: Any) -> PageRender:
    import asyncio

    return asyncio.run(render_bound_async(bound, out_dir, **kw))
