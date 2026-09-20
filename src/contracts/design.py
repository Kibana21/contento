"""Structured design representation — BRD §21, ADR-004.

Elements never inline factual text. They reference a fact or copy slot, so a model can
never overwrite a name, date or phone number (ADR-001).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import Strict
from .creative import Composition, MountainsVariant, RedApplication


class ElementType(StrEnum):
    LOGO = "logo"
    HEADLINE = "headline"
    SUBHEADLINE = "subheadline"
    BODY = "body"
    CTA = "cta"
    FACT = "fact"
    AGENT_PHOTO = "agent_photo"
    IMAGE = "image"
    MOUNTAINS = "mountains"
    QR = "qr"
    DISCLAIMER = "disclaimer"
    CONTACT_BLOCK = "contact_block"


#: Element types whose content is factual and therefore locked to a reference (ADR-001).
FACTUAL_TYPES = {ElementType.FACT, ElementType.QR, ElementType.DISCLAIMER,
                 ElementType.CONTACT_BLOCK, ElementType.LOGO, ElementType.AGENT_PHOTO}

PRESETS: dict[str, tuple[int, int]] = {
    "instagram_square": (1080, 1080),
    "instagram_portrait": (1080, 1350),
    "instagram_story": (1080, 1920),
    "whatsapp_portrait": (1080, 1350),
    "linkedin_post": (1200, 1200),
    "facebook_post": (1200, 630),
    "a4_print": (2480, 3508),
}


class Canvas(Strict):
    preset: str = "instagram_portrait"
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    dpi: int = 72

    @classmethod
    def from_preset(cls, preset: str) -> Canvas:
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
        w, h = PRESETS[preset]
        return cls(preset=preset, width=w, height=h, dpi=300 if preset == "a4_print" else 72)

    @property
    def short_edge(self) -> int:
        return min(self.width, self.height)


class Element(Strict):
    id: str
    type: ElementType
    slot: str = Field(description="Named region in the layout family, e.g. 'hero', 'footer-left'")
    content_ref: str | None = Field(
        default=None, description="'copy.headline' or 'facts.event.date' — resolved at render time"
    )
    asset_ref: str | None = Field(default=None, description="Path or asset id for images/logo/QR")
    text: str | None = Field(default=None, description="Literal text; forbidden for factual types")
    style_token: str | None = None
    overrides: dict[str, str | float | int | bool] = Field(default_factory=dict)
    visible: bool = True

    @model_validator(mode="after")
    def _factual_must_reference(self) -> Element:
        if self.type in FACTUAL_TYPES and self.text is not None:
            raise ValueError(f"{self.type} element must reference data, not inline text (ADR-001)")
        if self.type in {ElementType.FACT} and not self.content_ref:
            raise ValueError("fact element needs content_ref")
        if self.type in {ElementType.LOGO, ElementType.QR, ElementType.AGENT_PHOTO} and not self.asset_ref:
            raise ValueError(f"{self.type} element needs asset_ref")
        return self


class Background(Strict):
    kind: Literal["generated_image", "library_image", "solid", "brand_graphic"] = "solid"
    asset: str | None = None
    colour_token: str | None = "core.white"
    generation: dict[str, str] = Field(default_factory=dict, description="prompt, model, seed — for lineage")


class DesignDoc(Strict):
    """One rendered variation, versioned. Re-renderable and diffable."""

    design_id: str
    campaign_id: str
    direction_id: str
    version: int = 1
    parent_version: int | None = None
    canvas: Canvas
    layout_family: str
    theme: RedApplication = RedApplication.HIGHLIGHT
    mountains: MountainsVariant = MountainsVariant.NONE
    composition: Composition = Field(default_factory=Composition)
    background: Background = Field(default_factory=Background)
    elements: list[Element] = Field(default_factory=list)
    brand_pack_version: str = "0.2"
    language: str = "en"
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_element_ids(self) -> DesignDoc:
        ids = [e.id for e in self.elements]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate element ids")
        return self

    def element(self, element_id: str) -> Element | None:
        return next((e for e in self.elements if e.id == element_id), None)

    def by_type(self, etype: ElementType) -> list[Element]:
        return [e for e in self.elements if e.type == etype]

    def next_version(self, **changes: object) -> DesignDoc:
        data = self.model_dump()
        data |= changes
        data["version"] = self.version + 1
        data["parent_version"] = self.version
        return DesignDoc.model_validate(data)
