"""Authored CSS as structured declarations, serialised by us — never parsed from text.

Accepting `list[CssRule]` instead of a stylesheet string removes a whole class of problem:

  * `!important` is *unrepresentable* — the serialiser never writes it. That closes the
    CLAUDE.md gotcha structurally rather than by inspection, and it is what lets the repair
    layer win.
  * At-rules cannot exist in the representation, so `@import`, `@font-face`, `@media` and
    `@keyframes` are impossible by construction.
  * Colours are token references only, so the palette is structural and countable before a
    page is ever rendered.
  * No CSS parser is needed, so no new dependency.

The `content` property is absent from the allowlist: it is the main way text reaches a page
without being a text node. The render-time audit re-checks that independently.
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator

from ..contracts.common import Strict

#: Properties the author may set, grouped as they are reasoned about.
BOX = {"display", "position", "top", "right", "bottom", "left", "inset", "width", "height",
       "min-width", "min-height", "max-width", "max-height", "margin", "margin-top",
       "margin-right", "margin-bottom", "margin-left", "padding", "padding-top",
       "padding-right", "padding-bottom", "padding-left", "box-sizing", "overflow"}
LAYOUT = {"flex", "flex-direction", "flex-wrap", "flex-grow", "flex-shrink", "flex-basis",
          "gap", "row-gap", "column-gap", "align-items", "align-self", "align-content",
          "justify-content", "justify-items", "justify-self", "order", "place-items",
          "grid-template-columns", "grid-template-rows", "grid-template-areas", "grid-area",
          "grid-column", "grid-row", "grid-auto-flow", "grid-auto-rows", "grid-auto-columns"}
TYPE = {"font-size", "font-weight", "line-height", "letter-spacing", "text-align",
        "text-transform", "white-space", "text-decoration", "font-style"}
COLOUR = {"color", "background-color", "background", "border-color", "border-top-color",
          "border-bottom-color", "border-left-color", "border-right-color", "fill", "stroke",
          "opacity"}
SHAPE = {"border", "border-top", "border-right", "border-bottom", "border-left", "border-width",
         "border-style", "border-radius", "box-shadow", "outline", "outline-offset"}
MEDIA = {"object-fit", "object-position", "aspect-ratio", "z-index", "filter", "transform"}

ALLOWED_PROPERTIES = BOX | LAYOUT | TYPE | COLOUR | SHAPE | MEDIA

#: Properties that are refused with a specific reason, so the model gets a useful finding
#: rather than a bare "unknown property".
REFUSED: dict[str, str] = {
    "content": "text may only reach the page through data-ref",
    "counter-reset": "counters can build text out of digits",
    "counter-increment": "counters can build text out of digits",
    "counter-set": "counters can build text out of digits",
    "quotes": "quote strings are text",
    "list-style": "list markers are text",
    "list-style-type": "list markers are text",
    "font-family": "the typeface is assigned from the brand pack, not authored",
    "visibility": "bound content may not be hidden",
    "clip": "bound content may not be hidden",
    "clip-path": "bound content may not be hidden",
    "text-indent": "bound content may not be pushed off the page",
    "background-clip": "background-clip:text can erase bound text",
    "-webkit-text-fill-color": "can erase bound text",
    "-webkit-text-security": "can disguise bound text",
    "hyphens": "hyphenation splits words mid-letter (CLAUDE.md)",
    "word-break": "breaking splits words mid-letter (CLAUDE.md)",
    "overflow-wrap": "breaking splits words mid-letter (CLAUDE.md)",
    "mix-blend-mode": "can erase bound text against its background",
    "animation": "a poster is a still image",
    "transition": "a poster is a still image",
    "zoom": "use transform: scale()",
    "all": "resets escape the allowlist",
}

#: `display:none` and `position:fixed` are refused at the value level: the properties
#: themselves are legitimate.
REFUSED_VALUES: dict[str, set[str]] = {
    "display": {"none"},
    "position": {"fixed", "sticky"},
    "overflow": {"scroll", "auto"},
}

#: Only these transform functions, and only with non-negative scale factors: `rotate`,
#: `scaleX(-1)`, `matrix` and `skew` would defeat the Moving Mountains rotation rule (p69).
_TRANSFORM_OK = re.compile(
    r"^(?:(?:translate|translateX|translateY)\(-?[\d.]+(?:px|%|em|rem)?\)"
    r"|scale\((?:0?\.[1-9]\d*|1(?:\.\d+)?)\)|\s)+$"
)

#: A colour-valued property may only reference a brand token, or these two keywords.
_COLOUR_OK = re.compile(r"^(?:var\(--[a-z0-9-]+\)|transparent|currentColor|inherit)$")

#: Selectors: classes, groups, descendant/child/adjacent combinators and simple positional
#: pseudo-classes. No `::` at all, no `#id`, no `*`, no `:has()`/`:not()`.
_SELECTOR_OK = re.compile(
    r"^(?:\.[a-z][a-z0-9-]*|\[data-group=\"[a-z0-9-]+\"\]|:first-child|:last-child"
    r"|:nth-child\(\d+n?(?:[+-]\d+)?\)|[ >+]|\s)+$"
)

#: Anything that could smuggle a value past the per-property checks.
_VALUE_FORBIDDEN = re.compile(r"!\s*important|url\s*\(|expression\s*\(|attr\s*\(|[;{}<>\\]|/\*",
                              re.IGNORECASE)


class CssError(ValueError):
    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


class CssRule(Strict):
    """One authored rule. Validation happens here, so an invalid rule cannot be constructed."""

    selector: str = Field(max_length=200)
    declarations: dict[str, str] = Field(default_factory=dict)

    @field_validator("selector")
    @classmethod
    def _selector_grammar(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not _SELECTOR_OK.match(cleaned):
            raise ValueError(
                f"selector {value!r} is outside the accepted grammar: classes, "
                f'[data-group="..."], combinators and simple positional pseudo-classes only'
            )
        return cleaned

    @field_validator("declarations")
    @classmethod
    def _declarations_allowed(cls, decls: dict[str, str]) -> dict[str, str]:
        for prop, value in decls.items():
            check_declaration(prop.strip().lower(), str(value).strip())
        return decls


def check_declaration(prop: str, value: str) -> None:
    """Raise `CssError` unless this property/value pair is inside the accepted subset."""
    if prop in REFUSED:
        raise CssError("css.forbidden", f"{prop!r} is not allowed: {REFUSED[prop]}")
    if prop not in ALLOWED_PROPERTIES:
        raise CssError("css.forbidden", f"{prop!r} is not an allowed property")
    if _VALUE_FORBIDDEN.search(value):
        raise CssError("css.forbidden", f"{prop}: {value!r} contains a forbidden construct")
    if value.lower() in REFUSED_VALUES.get(prop, set()):
        reason = {"display": "bound content may not be hidden",
                  "position": "fixed/sticky escape the canvas",
                  "overflow": "a poster does not scroll"}[prop]
        raise CssError("css.forbidden", f"{prop}: {value} is not allowed: {reason}")
    if prop in COLOUR and prop != "opacity" and not _COLOUR_OK.match(value):
        raise CssError("css.palette",
                       f"{prop}: {value!r} must reference a brand token, e.g. var(--red)")
    if prop == "opacity" and not _opacity_ok(value):
        raise CssError("css.forbidden", f"opacity {value!r}: bound content may not be faded out")
    if prop == "transform" and not _TRANSFORM_OK.match(value):
        raise CssError("css.forbidden",
                       f"transform {value!r}: only translate and positive scale are allowed "
                       f"(the Moving Mountains may never be rotated or flipped)")


def _opacity_ok(value: str) -> bool:
    try:
        return 0.15 <= float(value) <= 1.0
    except ValueError:
        return False


def serialise(rules: list[CssRule]) -> str:
    """Emit the stylesheet. `!important` cannot appear because nothing here writes it."""
    out: list[str] = []
    for rule in rules:
        body = " ".join(f"{p.strip().lower()}: {str(v).strip()};"
                        for p, v in rule.declarations.items())
        if body:
            out.append(f"{rule.selector} {{ {body} }}")
    return "\n".join(out)
