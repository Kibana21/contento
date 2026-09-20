"""Authored markup + a stylesheet + locked facts -> a page that is safe to render.

This is where the governance lives. The model authored the form; everything with meaning is
put in by this module, from data it did not choose. Seven steps, each of which can only
reject or annotate — none of them ever invents content.

The binder is deliberately the only place that writes `id` attributes, the only place that
resolves a reference, and the only place that injects an asset. That concentration is the
point: a reviewer can read one file and see every route by which something reaches a poster.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.brand import BrandPack
from ..contracts.common import Finding, Severity
from ..contracts.design import Canvas, ElementType
from ..render.context import RenderContext, UnresolvedReference
from ..validate.spec import ElementSpec
from . import css as cssmod
from .assets import AssetError, resolve_asset
from .contracts import DesignSystem, FreeformPage
from .html_parse import AuthoredHtmlError, Node, parse_authored, serialise
from .vocabulary import (HIERARCHY_ROLE_OF_REF, VocabularyError, classes_targeted,
                         classes_used, element_type_for)

#: Element type -> the font stack it is set in. Assigned here, never authored, which is why
#: `type.family` can no longer fail on this path.
FONT_OF_TYPE: dict[ElementType, str] = {
    ElementType.HEADLINE: "var(--display)",
    ElementType.SUBHEADLINE: "var(--display)",
    ElementType.CTA: "var(--display)",
    ElementType.FACT: "var(--display)",
    ElementType.CONTACT_BLOCK: "var(--display)",
    ElementType.BODY: "var(--body)",
    ElementType.DISCLAIMER: "var(--body)",
}


@dataclass
class BoundPage:
    """A page ready to render, plus everything the validators need to judge it."""

    html: str
    spec: ElementSpec
    #: id -> the exact string injected, so the audit can prove nothing was substituted.
    bound_text: dict[str, str] = field(default_factory=dict)
    groups: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(f.severity == Severity.ERROR for f in self.findings)


def _fail(findings: list[Finding], rule: str, message: str, *, element: str | None = None,
          sev: Severity = Severity.ERROR, fix: str | None = None) -> None:
    findings.append(Finding(rule_id=rule, severity=sev, message=message,
                            element_id=element, suggestion=fix))


def bind_page(page: FreeformPage, system: DesignSystem, ctx: RenderContext, *,
              canvas: Canvas, dev_icons: bool = False) -> BoundPage:
    findings: list[Finding] = []
    empty = ElementSpec(types={}, canvas_short_edge=canvas.short_edge, theme=system.ground)

    # ---- 1. recognise -----------------------------------------------------
    try:
        root = parse_authored(page.html)
    except AuthoredHtmlError as exc:
        _fail(findings, exc.rule_id, f"line {exc.line}: {exc.message}")
        return BoundPage(html="", spec=empty, findings=findings)

    # ---- 2. the two agents must agree on class names ----------------------
    vocabulary = system.vocabulary
    for unknown in sorted(classes_used(root) - vocabulary):
        _fail(findings, "css.unknown_class",
              f"the markup uses class {unknown!r}, which this design system does not style",
              fix="use a class from the shared vocabulary, or declare it on the design system")
    for rule in [*system.rules, *page.rules]:
        for orphan in sorted(classes_targeted(rule.selector) - vocabulary):
            _fail(findings, "css.orphan_selector",
                  f"selector {rule.selector!r} targets {orphan!r}, which is not in the vocabulary")

    # ---- 3. the page carries what the storyboard promised -----------------
    refs = [n.ref for n in root.walk() if n.ref] + [n.asset for n in root.walk() if n.asset]
    for required in page.plan.must_include:
        count = refs.count(required)
        if count == 0:
            _fail(findings, "content.missing_required",
                  f"the plan requires {required!r} on this page, but it is absent")
        elif count > 1:
            _fail(findings, "content.duplicate_ref",
                  f"{required!r} appears {count} times; each reference is placed exactly once")
    for ref in refs:
        if refs.count(ref) > 1 and ref not in page.plan.must_include:
            _fail(findings, "content.duplicate_ref", f"{ref!r} appears more than once")

    # ---- 4/5/6. resolve, inject and tag ------------------------------------
    types: dict[str, ElementType] = {}
    first: dict[ElementType, str] = {}
    bound_text: dict[str, str] = {}
    counters: dict[str, int] = {}

    for node in root.walk():
        if not node.is_bound:
            continue
        ref = node.ref or node.asset or ""
        try:
            etype = element_type_for(ref)
        except VocabularyError as exc:
            _fail(findings, exc.rule_id, exc.message)
            continue

        counters[etype.value] = counters.get(etype.value, 0) + 1
        element_id = f"{etype.value}-{counters[etype.value]}"
        node.attrs["id"] = element_id
        node.attrs["data-el-type"] = etype.value
        types[element_id] = etype

        # only copy.* carries a hierarchy role, so eight module labels cannot compete with
        # the headline in the size-ratio rules
        if ref in HIERARCHY_ROLE_OF_REF and etype not in first:
            first[etype] = element_id

        if node.ref:
            try:
                text = ctx.resolve(node.ref)
            except UnresolvedReference as exc:
                _fail(findings, "ref.unresolved", f"{node.ref}: {exc}", element=element_id)
                continue
            node.children = [_TextLeaf(text)]
            bound_text[element_id] = text
        else:
            try:
                asset = resolve_asset(node.asset, ctx, canvas_width=canvas.width,
                                      on_red=system.ground == "bold", dev_icons=dev_icons)
            except AssetError as exc:
                _fail(findings, exc.rule_id, exc.message, element=element_id)
                continue
            if asset.kind == "svg":
                node.children = [_RawLeaf(asset.svg or "")]
            else:
                node.attrs["src"] = asset.src or ""
                node.attrs["alt"] = ""      # never a caption: alt text renders when src fails

    # ---- 7. assemble -------------------------------------------------------
    groups = sorted({n.attrs["data-group"] for n in root.walk() if "data-group" in n.attrs})
    html = _document(root, system, page, ctx.brand, canvas, types)
    spec = ElementSpec(types=types, canvas_short_edge=canvas.short_edge,
                       theme=system.ground, declared={}, first=first)
    return BoundPage(html=html, spec=spec, bound_text=bound_text, groups=groups,
                     findings=findings)


class _TextLeaf(Node):
    """Bound text. Escaped on the way out, and never re-parsed."""

    def __init__(self, text: str) -> None:
        super().__init__(tag="#text")
        self.text = text


class _RawLeaf(Node):
    """Markup this module generated itself — a Moving Mountains SVG or a normalised icon."""

    def __init__(self, markup: str) -> None:
        super().__init__(tag="#raw")
        self.markup = markup


def _emit(node: Node) -> str:
    if isinstance(node, _TextLeaf):
        return (node.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    if isinstance(node, _RawLeaf):
        return node.markup
    if node.tag == "root":
        return "".join(_emit(c) for c in node.children)
    attrs = "".join(f' {k}="{_escape(v)}"' for k, v in sorted(node.attrs.items()) if v != "")
    from .html_parse import VOID_TAGS

    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    return f"<{node.tag}{attrs}>{''.join(_emit(c) for c in node.children)}</{node.tag}>"


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _base_css(brand: BrandPack, canvas: Canvas, system: DesignSystem,
              types: dict[str, ElementType], long_form: bool) -> str:
    """Tokens, fonts and the canvas. Everything here outranks nothing — the authored rules
    come after, so a design system can still lay the page out however it likes."""
    scale = brand.type_scale()
    fonts = [
        ("AIAEverest", 400, brand.font_path("display_regular")),
        ("AIAEverest", 700, brand.font_path("display_medium")),
        ("Open Sans", 400, brand.font_path("body_regular")),
    ]
    faces = "\n".join(
        f'@font-face {{ font-family: "{name}"; src: url("{path.resolve().as_uri()}"); '
        f"font-weight: {weight}; font-display: block; }}"
        for name, weight, path in fonts if path
    )
    # font assignment by element type, so `type.family` cannot fail
    families = "\n".join(
        f'[data-el-type="{etype.value}"] {{ font-family: {stack}; }}'
        for etype, stack in FONT_OF_TYPE.items()
    )
    ground = brand.red if system.ground == "bold" else brand.colour_hex("core.white")
    ink = brand.colour_hex("core.white") if system.ground == "bold" else brand.charcoal
    height = "auto" if long_form else f"{canvas.height}px"
    return f"""{faces}
:root {{
  --red: {brand.red}; --red-80: {brand.colour_hex('core.red.80')};
  --red-60: {brand.colour_hex('core.red.60')}; --red-40: {brand.colour_hex('core.red.40')};
  --red-20: {brand.colour_hex('core.red.20')};
  --charcoal: {brand.charcoal}; --charcoal-80: {brand.colour_hex('core.charcoal.80')};
  --charcoal-60: {brand.colour_hex('core.charcoal.60')};
  --charcoal-20: {brand.colour_hex('core.charcoal.20')};
  --white: #FFFFFF; --ground: {ground}; --ink: {ink};
  --display: "AIAEverest", "Open Sans", Arial, sans-serif;
  --body: "Open Sans", Arial, sans-serif;
  --unit: 4px;
}}
*{{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {canvas.width}px; }}
.poster {{ position: relative; width: {canvas.width}px; height: {height};
          min-height: {canvas.height}px; overflow: hidden;
          background: var(--ground); color: var(--ink);
          font-family: var(--body); -webkit-font-smoothing: antialiased; }}
img {{ display: block; max-width: 100%; }}
svg {{ display: block; }}
{families}
"""


def _document(root: Node, system: DesignSystem, page: FreeformPage, brand: BrandPack,
              canvas: Canvas, types: dict[str, ElementType]) -> str:
    long_form = page.plan.shape == "long_form"
    authored = cssmod.serialise([*system.rules, *page.rules])
    return (
        "<!doctype html>\n"
        f'<html lang="en"><head><meta charset="utf-8">'
        f"<title>{system.variation_id}-{page.plan.index}</title><style>\n"
        f"{_base_css(brand, canvas, system, types, long_form)}\n"
        f"/* authored by the design system */\n{authored}\n"
        f'</style></head><body><div class="poster">{_emit(root)}</div></body></html>'
    )
