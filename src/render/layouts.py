"""Layout family registry — the controlled template families of BRD §23.

Families are designed by people; an agent may only choose one and fill its slots. This
registry tells the Design Builder which slots exist and what each family is good at.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.creative import (Accent, Anchor, Composition, Density, MountainsPlacement,
                                  MountainsVariant, PhotoMode, PhotoPlacement, PhotoShape,
                                  RedApplication)
from ..contracts.design import ElementType


@dataclass(frozen=True)
class LayoutFamily:
    name: str
    description: str
    default_theme: RedApplication
    photo_modes: tuple[PhotoMode, ...]
    mountains: tuple[MountainsVariant, ...]
    slots: dict[ElementType, str]
    portrait_size: tuple[float, float]  # fraction of canvas width/height
    mountains_height: float             # fraction of canvas height
    composition: Composition = field(default_factory=Composition)
    template: str = "composed"          # every family renders through the grammar template
    logo_colour: str = "red"
    suits: tuple[str, ...] = ()

    def slot_for(self, etype: ElementType) -> str | None:
        return self.slots.get(etype)


_COMMON = {
    ElementType.LOGO: "logo",
    ElementType.HEADLINE: "headline",
    ElementType.MOUNTAINS: "background-graphic",
    ElementType.AGENT_PHOTO: "portrait",
    ElementType.CONTACT_BLOCK: "contact",
    ElementType.CTA: "cta",
    ElementType.QR: "qr",
    ElementType.DISCLAIMER: "legal",
}

FAMILIES: dict[str, LayoutFamily] = {
    "festive-portrait": LayoutFamily(
        name="festive-portrait",
        description="Portrait-led warmth: cut-out photo in front of the Moving Mountains, "
                    "large greeting, red as highlight.",
        default_theme=RedApplication.HIGHLIGHT,
        photo_modes=(PhotoMode.CUTOUT_FRONT, PhotoMode.NONE),
        mountains=(MountainsVariant.CORE_3, MountainsVariant.CORE_4, MountainsVariant.OUTLINE),
        slots={**_COMMON, ElementType.SUBHEADLINE: "message", ElementType.BODY: "message",
               ElementType.FACT: "contact", ElementType.IMAGE: "background-graphic"},
        portrait_size=(0.44, 0.62),
        mountains_height=0.49,
        composition=Composition(headline_anchor=Anchor.TOP_LEFT, headline_span=7, headline_scale=1.12,
                                copy_span=5, photo_placement=PhotoPlacement.RIGHT,
                                photo_shape=PhotoShape.CUTOUT, photo_scale=1.0,
                                mountains_placement=MountainsPlacement.BASELINE,
                                accent=Accent.NONE, density=Density.BALANCED),
        suits=("festive", "relationship", "appreciation", "personal_branding"),
    ),
    "event-information": LayoutFamily(
        name="event-information",
        description="Information first: event facts in a high-contrast panel, speaker row, "
                    "immediate readability.",
        default_theme=RedApplication.HIGHLIGHT,
        photo_modes=(PhotoMode.CONTAINER, PhotoMode.NONE),
        mountains=(MountainsVariant.CORE_4, MountainsVariant.CORE_3),
        slots={**_COMMON, ElementType.SUBHEADLINE: "subheadline", ElementType.BODY: "subheadline",
               ElementType.FACT: "details", ElementType.IMAGE: "background-graphic"},
        portrait_size=(0.20, 0.16),
        mountains_height=0.38,
        composition=Composition(headline_anchor=Anchor.TOP_LEFT, headline_span=10, headline_scale=0.94,
                                copy_span=8, photo_placement=PhotoPlacement.INSET,
                                photo_shape=PhotoShape.CIRCLE, photo_scale=1.0,
                                mountains_placement=MountainsPlacement.CORNER_RIGHT,
                                accent=Accent.BAR, density=Density.DENSE),
        suits=("seminar", "event", "recruitment", "educational"),
    ),
    "editorial-minimal": LayoutFamily(
        name="editorial-minimal",
        description="Premium editorial: generous white space, restrained hierarchy, circular "
                    "portrait, red used sparingly as an accent rule.",
        default_theme=RedApplication.HIGHLIGHT,
        photo_modes=(PhotoMode.CONTAINER, PhotoMode.NONE),
        mountains=(MountainsVariant.OUTLINE, MountainsVariant.CORE_3, MountainsVariant.NONE),
        slots={**_COMMON, ElementType.SUBHEADLINE: "subheadline", ElementType.BODY: "message",
               ElementType.FACT: "details", ElementType.IMAGE: "background-graphic"},
        portrait_size=(0.34, 0.46),
        mountains_height=0.24,
        composition=Composition(headline_anchor=Anchor.MIDDLE_LEFT, headline_span=6, headline_scale=1.34,
                                copy_span=5, photo_placement=PhotoPlacement.RIGHT,
                                photo_shape=PhotoShape.ARCH, photo_scale=0.95,
                                mountains_placement=MountainsPlacement.CORNER_RIGHT,
                                mountains_scale=0.8, accent=Accent.RULE, density=Density.AIRY),
        suits=("personal_branding", "achievement", "festive", "seminar", "educational"),
    ),
    "social-bold": LayoutFamily(
        name="social-bold",
        description="Contemporary social: solid AIA Red ground, inverted mountains, "
                    "high-energy hierarchy, white call to action.",
        default_theme=RedApplication.BOLD,
        photo_modes=(PhotoMode.CUTOUT_FRONT, PhotoMode.NONE),
        mountains=(MountainsVariant.INVERTED_4, MountainsVariant.INVERTED_3),
        slots={**_COMMON, ElementType.SUBHEADLINE: "subheadline", ElementType.BODY: "message",
               ElementType.FACT: "details", ElementType.IMAGE: "background-graphic"},
        portrait_size=(0.46, 0.64),
        mountains_height=0.45,
        composition=Composition(headline_anchor=Anchor.BOTTOM_LEFT, headline_span=7, headline_scale=1.22,
                                copy_span=5, photo_placement=PhotoPlacement.FULL_BLEED_RIGHT,
                                photo_shape=PhotoShape.CUTOUT, photo_scale=1.1,
                                mountains_placement=MountainsPlacement.BEHIND_PHOTO,
                                accent=Accent.BLOCK, density=Density.BALANCED),
        logo_colour="white",
        suits=("festive", "event", "seminar", "recruitment", "appreciation", "achievement"),
    ),
}


def families_for(family: str) -> list[LayoutFamily]:
    """Layout families that suit a campaign family, best first."""
    suited = [f for f in FAMILIES.values() if family in f.suits]
    return suited or list(FAMILIES.values())


def catalogue() -> list[dict[str, object]]:
    """Machine-readable summary handed to the Creative Director."""
    return [{"layout_family": f.name, "description": f.description,
             "default_theme": f.default_theme.value,
             "photo_modes": [m.value for m in f.photo_modes],
             "mountains_variants": [m.value for m in f.mountains],
             "default_composition": f.composition.model_dump(mode="json"),
             "suits": list(f.suits)} for f in FAMILIES.values()]
