"""Deterministic repair, applied as inline styles.

The structured engine repairs by multiplying an element's `overrides["scale"]`. There is no
overrides dict here, so the same *measured* arithmetic is expressed as an inline `style`
attribute on the bound element instead.

Inline style is the right vehicle: it wins on specificity as well as order, so it survives a
high-specificity authored selector, and `style` is denied to authors, which makes this module
its sole owner.

The division of labour is deliberate: **code may shrink, only a model may cut.** If a page is
still overfull after shrinking, that is a content decision and belongs to the composer or the
planner, not to a loop that keeps reducing type until it is illegible.
"""

from __future__ import annotations

import re

from ..contracts.common import Finding, ValidationReport

#: Matches the exact ratio maths used by `concepts.py::_auto_fix`, so the two engines shrink
#: text by the same amount for the same measured shortfall.
MIN_RATIO, MAX_RATIO = 0.55, 0.96
COLLISION_RATIO = 0.88
ENLARGE_RATIO = 1.3


def shrink_ratio(node: dict | None, *, default: float = 0.85) -> float:
    """How much to shrink, taken from what the page actually measured."""
    if not node or not node.get("scrollWidth") or not node.get("width"):
        return default
    by_width = node["width"] / max(node["scrollWidth"], 1)
    by_height = node["height"] / max(node["scrollHeight"], 1)
    return max(MIN_RATIO, min(MAX_RATIO, min(by_width, by_height) * 0.98))


def repair_plan(report: ValidationReport, geometry: dict, *, min_px: float = 15.0,
                legal_px: float = 15.0) -> dict[str, dict[str, str]]:
    """element id -> CSS declarations that would fix its errors."""
    measured = {e["id"]: e for e in geometry.get("elements", [])}
    plan: dict[str, dict[str, str]] = {}

    for finding in report.errors:
        element_id = finding.element_id
        if not element_id or element_id not in measured:
            continue
        node = measured[element_id]
        size = float(node.get("fontSize") or 0)
        declarations = plan.setdefault(element_id, {})

        if finding.rule_id in {"layout.overflow", "layout.outside_canvas"} and size:
            declarations["font-size"] = f"{size * shrink_ratio(node):.1f}px"
        elif finding.rule_id == "layout.text_collision" and size:
            declarations["font-size"] = f"{size * COLLISION_RATIO:.1f}px"
        elif finding.rule_id == "type.min_size" and size:
            declarations["font-size"] = f"{max(size * ENLARGE_RATIO, min_px):.1f}px"
        elif finding.rule_id == "type.legal_prominence":
            declarations["font-size"] = f"{legal_px:.1f}px"
        elif finding.rule_id == "logo.min_size":
            declarations["height"] = "48px"
        elif finding.rule_id in {"bind.hidden", "contrast.text"}:
            # opacity is the one hiding route the allowlist permits at all, so undo it and
            # let the contrast rule judge the result on the next pass
            declarations["opacity"] = "1"
        if not declarations:
            plan.pop(element_id, None)
    return plan


def apply_repairs(html: str, plan: dict[str, dict[str, str]]) -> str:
    """Write the declarations onto the bound elements as inline styles.

    Operates on the bound document, which this package generated, so the ids are known and
    the markup shape is ours — not the model's.
    """
    for element_id, declarations in plan.items():
        body = " ".join(f"{p}: {v};" for p, v in declarations.items())
        pattern = re.compile(rf'(<[a-z0-9]+[^>]*\bid="{re.escape(element_id)}")([^>]*)>')

        def substitute(match: re.Match) -> str:
            head, rest = match.group(1), match.group(2)
            existing = re.search(r'\sstyle="([^"]*)"', rest)
            if existing:
                merged = f'{existing.group(1).rstrip().rstrip(";")}; {body}'
                rest = rest.replace(existing.group(0), f' style="{merged}"')
                return f"{head}{rest}>"
            return f'{head}{rest} style="{body}">'

        html = pattern.sub(substitute, html, count=1)
    return html


def signature_of(report: ValidationReport, extra: list[Finding] | None = None) -> set[str]:
    """What is wrong, as a comparable set. When it stops changing, repair has stopped helping."""
    return {f"{f.rule_id}:{f.element_id}" for f in [*report.errors, *(extra or [])]}
