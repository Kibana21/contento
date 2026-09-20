"""The design-system API that the two authoring agents both code against.

The Art Director writes the stylesheet and the Page Composer writes the markup, in two
independent model calls. Nothing makes them agree on class names by default: if the director
styles `.speaker-portrait` and the composer writes `class="speaker-photo"`, the page renders
unstyled, passes every check that looks at text and geometry, and looks broken.

So the vocabulary is closed and shared. Both agents receive it, and the binder enforces it in
both directions — markup may not use a class the system does not style, and the system may not
target a class outside the vocabulary. An invisible failure becomes a caught one.
"""

from __future__ import annotations

from ..contracts.design import ElementType

#: Classes every design system styles and every page may use. Semantic, not visual: a
#: `.module` is "one row of a repeating group", and what that looks like is the director's
#: choice — an icon badge, a speaker card or a numbered step.
CORE_CLASSES = frozenset({
    # structure
    "page", "band", "stack", "row", "grid", "spacer",
    # one item of a repeating group, and its parts
    "module", "module-media", "module-label", "module-role", "module-body",
    # type
    "headline", "headline-accent", "subheadline", "body", "eyebrow",
    # furniture
    "cta", "chip", "badge", "divider", "detail-row", "detail-icon",
    "portrait", "logo", "legal", "qr", "mountains", "backdrop",
})

#: How far a design system may extend the vocabulary for its own motif.
MAX_CUSTOM_CLASSES = 8

#: Reference namespace -> element type. Derived by the binder, never taken from the model,
#: so a model cannot relabel a disclaimer as decoration to dodge a rule.
TYPE_OF_REF: dict[str, ElementType] = {
    "copy.headline": ElementType.HEADLINE,
    "copy.subheadline": ElementType.SUBHEADLINE,
    "copy.body": ElementType.BODY,
    "copy.cta": ElementType.CTA,
    "copy.signature": ElementType.CONTACT_BLOCK,
    "policy.disclaimer": ElementType.DISCLAIMER,
}

#: Prefix -> element type, for references that carry an index or an id.
#: Order matters: most specific first, so `profile.photo.formal` resolves to a portrait
#: rather than matching the broader `profile.` prefix and being typed as a fact.
TYPE_OF_PREFIX: tuple[tuple[str, ElementType], ...] = (
    ("brand.logo", ElementType.LOGO),
    ("profile.photo", ElementType.AGENT_PHOTO),
    ("generated.qr", ElementType.QR),
    ("mountains.", ElementType.MOUNTAINS),
    ("icon.", ElementType.IMAGE),
    ("background.", ElementType.IMAGE),
    ("facts.", ElementType.FACT),
    ("profile.", ElementType.FACT),
)

#: Which field of a content item plays which typographic role. A benefits grid has many
#: labels, so they are typed as sub-headings; only `copy.*` carries a hierarchy role, which
#: is why eight module labels cannot break the headline/subhead/body ratio rules.
TYPE_OF_CONTENT_FIELD: dict[str, ElementType] = {
    "label": ElementType.SUBHEADLINE,
    "role": ElementType.FACT,
    "body": ElementType.BODY,
    "value": ElementType.FACT,
    "photo": ElementType.IMAGE,
    "icon": ElementType.IMAGE,
}

#: Only these three carry a hierarchy role, so the ratio checks compare exactly one of each.
HIERARCHY_ROLE_OF_REF = {
    "copy.headline": ElementType.HEADLINE,
    "copy.subheadline": ElementType.SUBHEADLINE,
    "copy.body": ElementType.BODY,
}

#: Fields a `content.<kind>.<index>.<field>` reference may address.
CONTENT_FIELDS = frozenset(TYPE_OF_CONTENT_FIELD)


class VocabularyError(ValueError):
    def __init__(self, rule_id: str, message: str) -> None:
        super().__init__(message)
        self.rule_id = rule_id
        self.message = message


def vocabulary_for(custom: list[str] | None = None) -> frozenset[str]:
    """The full set of classes a page may use, given a system's declared extensions."""
    extra = list(custom or [])
    if len(extra) > MAX_CUSTOM_CLASSES:
        raise VocabularyError(
            "css.custom_class_limit",
            f"{len(extra)} custom classes; at most {MAX_CUSTOM_CLASSES} are allowed",
        )
    for name in extra:
        if name in CORE_CLASSES:
            raise VocabularyError("css.custom_class_shadow",
                                  f"custom class {name!r} shadows a core class")
        if not name or not name.replace("-", "").isalnum() or not name[0].isalpha():
            raise VocabularyError("css.custom_class_name",
                                  f"custom class {name!r} must be alphanumeric with hyphens")
    return CORE_CLASSES | frozenset(extra)


def classes_used(node) -> set[str]:
    """Every class token appearing in an authored tree."""
    used: set[str] = set()
    for element in node.walk():
        used |= set(element.attrs.get("class", "").split())
    return used


def classes_targeted(selector: str) -> set[str]:
    """Class names a selector targets. The grammar in css.py guarantees the shape."""
    parts = selector.replace(">", " ").replace("+", " ").split()
    return {part.lstrip(".").split(":")[0] for part in parts if part.startswith(".")}


def element_type_for(ref: str) -> ElementType:
    """The element type a reference implies. Derived here, never authored."""
    if ref in TYPE_OF_REF:
        return TYPE_OF_REF[ref]
    if ref.startswith("content."):
        field = ref.rsplit(".", 1)[-1]
        if field not in CONTENT_FIELDS:
            raise VocabularyError("ref.unresolved",
                                  f"{ref!r}: {field!r} is not an addressable content field")
        return TYPE_OF_CONTENT_FIELD[field]
    for prefix, etype in TYPE_OF_PREFIX:
        if ref.startswith(prefix):
            return etype
    raise VocabularyError("ref.namespace", f"unknown reference {ref!r}")
