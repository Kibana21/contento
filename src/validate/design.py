"""Structural checks on the DesignDoc — run before anything is rendered."""

from __future__ import annotations

from ..contracts.brand import BrandPack
from ..contracts.common import Finding, Severity, ValidationReport
from ..contracts.design import DesignDoc, ElementType
from ..render.mountains import SHAPE_SETS, resolve_layers


def validate_design(design: DesignDoc, brand: BrandPack) -> ValidationReport:
    findings: list[Finding] = []
    checks = 0

    def fail(rule: str, msg: str, *, element: str | None = None, sev: Severity = Severity.ERROR,
             evidence: str | None = None, fix: str | None = None) -> None:
        findings.append(Finding(rule_id=rule, severity=sev, message=msg, element_id=element,
                                evidence=evidence, suggestion=fix))

    # ---- logo (Brand Standards pp. 34, 38, 39) ----------------------------
    checks += 1
    logos = design.by_type(ElementType.LOGO)
    if not logos:
        fail("logo.present", "No AIA logo on the design")
    for el in logos:
        checks += 1
        colour = str(el.overrides.get("colour", "red"))
        if colour not in {"red", "white"}:
            fail("logo.colour", f"Logo colour {colour!r}: logos are only ever AIA Red or white",
                 element=el.id, fix="use colour 'red' on light grounds, 'white' on red/dark")
        checks += 1
        if brand.allowed_logo_positions and el.slot not in {"logo", *brand.allowed_logo_positions}:
            fail("logo.position", f"Logo slot {el.slot!r} is not an approved position",
                 element=el.id, evidence=str(brand.allowed_logo_positions))
    checks += 1
    if len(logos) > 1:
        fail("logo.count", "More than one AIA logo on the design", sev=Severity.WARN)

    # ---- Moving Mountains (pp. 59-69) ------------------------------------
    graphics = design.by_type(ElementType.MOUNTAINS)
    checks += 1
    if len(graphics) > 1:
        fail("mountains.single", "Only one Moving Mountains graphic per design (p69)")
    if graphics and design.mountains.value != "none":
        checks += 1
        try:
            layers = resolve_layers(design.mountains.value, brand.mountains, brand.colour_hex,
                                    on_red=str(getattr(design.theme, 'value', design.theme)) == 'bold')
        except (KeyError, ValueError) as exc:
            layers = []
            fail("mountains.variant", str(exc), element=graphics[0].id)
        if layers and not 3 <= len(layers) <= 4:
            fail("mountains.count", f"{len(layers)} peaks: use a minimum of 3 and a maximum of 4",
                 element=graphics[0].id)
        checks += 1
        if design.mountains.value.startswith("inverted") and design.theme != "bold":
            fail("mountains.inverted_ground", "Inverted mountains may only sit on an AIA Red background",
                 element=graphics[0].id)
        for el in graphics:
            checks += 1
            shape = str(el.overrides.get("shape_set", "classic_3"))
            if shape not in SHAPE_SETS:
                fail("mountains.shape_set", f"Unknown shape set {shape!r}", element=el.id)
            checks += 1
            if any(k in el.overrides for k in ("rotate", "flip", "transform")):
                fail("mountains.transform", "Moving Mountains must not be rotated or flipped (p69)",
                     element=el.id)

    # ---- colour usage (pp. 52-56) ----------------------------------------
    used_secondary = {
        str(v) for el in design.elements for k, v in el.overrides.items()
        if k in {"colour", "fill"} and str(v).startswith("secondary.")
    }
    if design.background.colour_token and design.background.colour_token.startswith("secondary."):
        used_secondary.add(design.background.colour_token)
    checks += 1
    if len(used_secondary) > brand.max_secondary_colours:
        fail("colour.max_secondary",
             f"{len(used_secondary)} secondary colours used; the maximum is {brand.max_secondary_colours}",
             evidence=", ".join(sorted(used_secondary)))
    checks += 1
    if used_secondary and design.theme != "bold" and design.background.colour_token in (None, "core.white"):
        has_red = any("core.red" in str(v) for el in design.elements for v in el.overrides.values())
        if not has_red and design.mountains.value == "none":
            fail("colour.secondary_needs_red", "Secondary colours may not be used without AIA Red (p56)")

    # ---- references resolve ----------------------------------------------
    for el in design.elements:
        checks += 1
        if el.content_ref and el.content_ref.split(".")[0] not in {"copy", "facts", "profile", "policy"}:
            fail("ref.namespace", f"Unknown reference {el.content_ref!r}", element=el.id)

    # ---- typography tokens exist -----------------------------------------
    scale = brand.type_scale()
    for el in design.elements:
        if el.style_token:
            checks += 1
            if el.style_token not in scale:
                fail("type.token", f"Unknown style token {el.style_token!r}", element=el.id,
                     evidence=", ".join(scale))

    return ValidationReport(checks_run=checks, findings=findings)
