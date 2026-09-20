"""What the rendered-page validators need to know about a design.

The DOM checks are keyed on element *ids*, not on the DesignDoc that produced them: given an
id -> type map and the canvas size, almost every rule in `dom.py` can be evaluated from the
measured page alone. Stating that dependency explicitly lets a design built from the layout
skeletons and one authored as free-form HTML share exactly one validator.

Only `render.missing` / `render.zero_size` need more, because "an element failed to render" is
a claim about what was *declared*; the DOM cannot report something that is not there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.design import DesignDoc, ElementType

REFERENCE_WIDTH = 1080  # brand type sizes are quoted at this short edge

#: Types whose content is text: these carry the size, typeface, contrast and collision rules.
TEXT_TYPES = frozenset({ElementType.HEADLINE, ElementType.SUBHEADLINE, ElementType.BODY,
                        ElementType.FACT, ElementType.CTA, ElementType.CONTACT_BLOCK,
                        ElementType.DISCLAIMER})

#: Text that sits in the page flow and must respect the safe margin. Footer furniture
#: (CTA, contact block, legal line) is anchored to the edge band by design and is exempt.
FLOW_TEXT_TYPES = frozenset({ElementType.HEADLINE, ElementType.SUBHEADLINE,
                             ElementType.BODY, ElementType.FACT})

#: Imagery that text must not be printed on top of.
OBSTACLE_TYPES = frozenset({ElementType.AGENT_PHOTO, ElementType.IMAGE})

#: Masked out of the pixel colour analysis: photographs carry their own colours.
MASKED_TYPES = frozenset({ElementType.AGENT_PHOTO, ElementType.IMAGE, ElementType.QR})

#: The three styles whose size ratios define the hierarchy (Brand Standards p76).
HIERARCHY_TYPES = (ElementType.HEADLINE, ElementType.SUBHEADLINE, ElementType.BODY)


@dataclass(frozen=True)
class ElementSpec:
    """The design facts the DOM validators need, with no dependency on how it was built."""

    types: dict[str, ElementType]
    canvas_short_edge: int
    theme: str = "highlight"
    #: id -> visible, for the declared-versus-rendered check. Empty on the free-form path,
    #: where the authored markup *is* the declaration and there is nothing to reconcile.
    declared: dict[str, bool] = field(default_factory=dict)
    #: Which element carries each hierarchy role. The ratio rules compare exactly one
    #: headline against one sub-heading against one body.
    first: dict[ElementType, str] = field(default_factory=dict)

    @classmethod
    def from_design(cls, design: DesignDoc) -> ElementSpec:
        return cls(
            types={e.id: e.type for e in design.elements},
            canvas_short_edge=design.canvas.short_edge,
            theme=str(getattr(design.theme, "value", design.theme)),
            declared={e.id: e.visible for e in design.elements},
            first={t: els[0].id for t in HIERARCHY_TYPES if (els := design.by_type(t))},
        )

    @classmethod
    def coerce(cls, source: ElementSpec | DesignDoc) -> ElementSpec:
        """Accept either form, so both engines and the existing tests use one call signature."""
        return source if isinstance(source, cls) else cls.from_design(source)

    @property
    def scale(self) -> float:
        """Brand sizes are quoted at a 1080px short edge; every threshold scales with the canvas."""
        return self.canvas_short_edge / REFERENCE_WIDTH

    def ids_of(self, types: frozenset[ElementType] | set[ElementType]) -> set[str]:
        return {eid for eid, etype in self.types.items() if etype in types}

    @property
    def text_ids(self) -> set[str]:
        return self.ids_of(TEXT_TYPES)

    @property
    def flow_text_ids(self) -> set[str]:
        return self.ids_of(FLOW_TEXT_TYPES)

    @property
    def obstacle_ids(self) -> set[str]:
        return self.ids_of(OBSTACLE_TYPES)

    @property
    def masked_ids(self) -> set[str]:
        return self.ids_of(MASKED_TYPES)

    @property
    def logo_ids(self) -> list[str]:
        return sorted(self.ids_of(frozenset({ElementType.LOGO})))
