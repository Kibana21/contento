"""Checks against the *rendered* page: exact geometry, computed colours, real font sizes."""

from __future__ import annotations

from typing import Any

from ..contracts.brand import BrandPack
from ..contracts.common import Finding, Severity, ValidationReport
from ..contracts.design import DesignDoc, ElementType
from .colour import contrast_ratio, parse_colour

LARGE_TEXT_PX = 32  # WCAG "large text" threshold at 1x scale (24pt)


def validate_dom(design: DesignDoc, geometry: dict[str, Any], brand: BrandPack) -> ValidationReport:
    findings: list[Finding] = []
    checks = 0
    by_id = {e["id"]: e for e in geometry["elements"]}
    canvas = geometry["canvas"]
    scale = design.canvas.short_edge / 1080
    page_bg = parse_colour(geometry.get("background", "")) or (255, 255, 255)

    def fail(rule: str, msg: str, *, element: str | None = None, sev: Severity = Severity.ERROR,
             evidence: str | None = None, fix: str | None = None) -> None:
        findings.append(Finding(rule_id=rule, severity=sev, message=msg, element_id=element,
                                evidence=evidence, suggestion=fix))

    # ---- everything the design declared actually rendered -----------------
    for el in design.elements:
        if not el.visible:
            continue
        checks += 1
        node = by_id.get(el.id)
        if node is None:
            fail("render.missing", f"Element {el.id!r} did not render", element=el.id)
            continue
        if node["width"] < 1 or node["height"] < 1:
            fail("render.zero_size", f"Element {el.id!r} rendered with no size", element=el.id)

    # ---- overflow and safe margins ---------------------------------------
    margin = float(brand.spacing.get("poster", {}).get("outer_margin", 64)) * scale
    for node in geometry["elements"]:
        checks += 1
        if node["overflows"]:
            fail("layout.overflow", f"Text in {node['id']!r} is clipped by its box", element=node["id"],
                 evidence=f"content {node['scrollWidth']:.0f}x{node['scrollHeight']:.0f} vs box "
                          f"{node['width']:.0f}x{node['height']:.0f}",
                 fix="shorten the copy or reduce the type size")
        checks += 1
        if node["outsideCanvas"]:
            fail("layout.outside_canvas", f"Element {node['id']!r} falls outside the canvas", element=node["id"])
        if node["id"] in {e.id for e in design.elements if e.type in
                          {ElementType.HEADLINE, ElementType.SUBHEADLINE, ElementType.BODY, ElementType.FACT}}:
            checks += 1
            if node["x"] < margin - 1 or node["y"] < margin - 1 or \
               node["x"] + node["width"] > canvas["width"] - margin + 1:
                fail("layout.safe_margin", f"{node['id']!r} breaks the {margin:.0f}px safe margin",
                     element=node["id"], sev=Severity.WARN)

    # ---- minimum type size (Brand Standards p76) --------------------------
    min_px = float(brand.hierarchy()["min_body_size"]["digital_px"]) * scale
    text_types = {ElementType.HEADLINE, ElementType.SUBHEADLINE, ElementType.BODY,
                  ElementType.FACT, ElementType.CTA, ElementType.CONTACT_BLOCK, ElementType.DISCLAIMER}
    text_ids = {e.id for e in design.elements if e.type in text_types}
    for node in geometry["elements"]:
        if node["id"] not in text_ids or not node["text"]:
            continue
        checks += 1
        if node["fontSize"] < min_px - 0.5:
            fail("type.min_size", f"{node['id']!r} is {node['fontSize']:.0f}px; the minimum is {min_px:.0f}px",
                 element=node["id"])

    # ---- hierarchy ratios (subhead = headline/3, body = subhead/2) --------
    h = by_id.get(_first(design, ElementType.HEADLINE))
    s = by_id.get(_first(design, ElementType.SUBHEADLINE))
    b = by_id.get(_first(design, ElementType.BODY))
    ratios = brand.hierarchy()
    if h and s:
        checks += 1
        want = float(ratios["subheading_to_headline_ratio"])
        got = s["fontSize"] / h["fontSize"]
        if not want * 0.6 <= got <= want * 1.7:
            fail("type.hierarchy_sub", f"Sub-heading is {got:.2f} of the headline; the rule is {want:.2f}",
                 element=s["id"], sev=Severity.WARN)
    if s and b:
        checks += 1
        want = float(ratios["body_to_subheading_ratio"])
        got = b["fontSize"] / s["fontSize"]
        if not want * 0.6 <= got <= want * 1.7:
            fail("type.hierarchy_body", f"Body is {got:.2f} of the sub-heading; the rule is {want:.2f}",
                 element=b["id"], sev=Severity.WARN)

    # ---- approved typefaces ----------------------------------------------
    for node in geometry["elements"]:
        if node["id"] not in text_ids or not node["text"]:
            continue
        checks += 1
        family = node["fontFamily"].lower()
        if not any(f in family for f in ("aiaeverest", "open sans", "noto sans", "arial")):
            fail("type.family", f"{node['id']!r} uses an unapproved typeface", element=node["id"],
                 evidence=node["fontFamily"])

    # ---- text contrast ----------------------------------------------------
    for node in geometry["elements"]:
        if node["id"] not in text_ids or not node["text"]:
            continue
        fg = parse_colour(node["color"])
        bg = parse_colour(node["backgroundColor"])
        if fg is None:
            continue
        if bg is None or (len(node["backgroundColor"].split(",")) > 3 and node["backgroundColor"].endswith("0)")):
            bg = page_bg
        checks += 1
        ratio = contrast_ratio(fg, bg)
        threshold = 3.0 if node["fontSize"] >= LARGE_TEXT_PX * scale else brand.min_text_contrast
        if ratio < threshold:
            fail("contrast.text", f"{node['id']!r} has {ratio:.2f}:1 contrast; {threshold}:1 required",
                 element=node["id"], evidence=f"{node['color']} on {node['backgroundColor'] or 'page'}",
                 fix="use white text on red, or charcoal on light grounds")

    # ---- text must not collide with imagery -------------------------------
    obstacle_ids = {e.id for e in design.elements
                    if e.type in {ElementType.AGENT_PHOTO, ElementType.IMAGE}}
    obstacles = [n for n in geometry["elements"] if n["id"] in obstacle_ids]
    for node in geometry["elements"]:
        if node["id"] not in text_ids or not node["text"] or node["id"] in obstacle_ids:
            continue
        for obs in obstacles:
            checks += 1
            overlap = _overlap_area(node, obs)
            if overlap > 0.18 * max(node["width"] * node["height"], 1):
                fail("layout.collision",
                     f"{node['id']!r} sits on top of {obs['id']!r} ({overlap / (node['width'] * node['height']):.0%} covered)",
                     element=node["id"],
                     fix="narrow the text column or move the image")
                break

    # ---- text must not collide with other text ----------------------------
    text_nodes = [n for n in geometry["elements"]
                  if n["id"] in text_ids and n["text"] and n["width"] > 1]
    for i, node in enumerate(text_nodes):
        for other in text_nodes[i + 1:]:
            checks += 1
            overlap = _overlap_area(node, other)
            smaller = min(node["width"] * node["height"], other["width"] * other["height"])
            if overlap > 0.12 * max(smaller, 1):
                fail("layout.text_collision",
                     f"{node['id']!r} and {other['id']!r} overlap", element=node["id"],
                     evidence=f"{overlap / max(smaller, 1):.0%} of the smaller block",
                     fix="shorten the copy, reduce the type size or free up vertical space")
                break

    # ---- logo minimum size and clear space (p34) --------------------------
    logo_ids = [e.id for e in design.elements if e.type == ElementType.LOGO]
    for lid in logo_ids:
        node = by_id.get(lid)
        if not node:
            continue
        checks += 1
        if node["height"] < 24:
            fail("logo.min_size", f"Logo is {node['height']:.0f}px high; the minimum is 24px", element=lid)
        clear = node["height"] * 0.25
        checks += 1
        for other in geometry["elements"]:
            if other["id"] == lid or not other["text"]:
                continue
            if _overlaps(node, other, clear):
                fail("logo.clear_space", f"{other['id']!r} intrudes into the logo's 0.25Y clear space",
                     element=other["id"], sev=Severity.WARN,
                     fix="move the text further from the logo")
                break

    return ValidationReport(checks_run=checks, findings=findings)


def _first(design: DesignDoc, etype: ElementType) -> str:
    els = design.by_type(etype)
    return els[0].id if els else ""


def _overlap_area(a: dict[str, Any], b: dict[str, Any]) -> float:
    dx = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
    dy = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
    return max(0.0, dx) * max(0.0, dy)


def _overlaps(a: dict[str, Any], b: dict[str, Any], pad: float) -> bool:
    return not (b["x"] > a["x"] + a["width"] + pad or b["x"] + b["width"] < a["x"] - pad
                or b["y"] > a["y"] + a["height"] + pad or b["y"] + b["height"] < a["y"] - pad)
