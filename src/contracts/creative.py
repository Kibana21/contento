"""Creative directions — Creative Director output (BRD §20, Standalone §11)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import Strict


class RedApplication(StrEnum):
    """Brand Standards p54: AIA Red is either the bold ground or the highlight accent."""

    BOLD = "bold"
    HIGHLIGHT = "highlight"


class PhotoMode(StrEnum):
    """How the agent portrait meets the Moving Mountains (Brand Standards pp. 64-68)."""

    CUTOUT_FRONT = "cutout_front"
    CONTAINER = "container"
    FULL_BLEED = "full_bleed"
    LAYERS = "layers"
    NONE = "none"


class MountainsVariant(StrEnum):
    CORE_3 = "core_3"
    CORE_4 = "core_4"
    INVERTED_3 = "inverted_3"
    INVERTED_4 = "inverted_4"
    OUTLINE = "outline"
    TRANSPARENT_3 = "transparent_3"
    NONE = "none"


class BackgroundKind(StrEnum):
    GENERATED = "generated"
    BRAND_GRAPHIC = "brand_graphic"
    SOLID = "solid"
    LIBRARY_IMAGE = "library_image"


class CreativeDirection(Strict):
    id: str = Field(pattern=r"^[a-d]$", description="a|b|c|d")
    name: str
    layout_family: str
    red_application: RedApplication
    photo_mode: PhotoMode
    mountains_variant: MountainsVariant
    background: BackgroundKind
    background_brief: str | None = Field(
        default=None, description="Image prompt seed. Never text, never the agent's face."
    )
    headline_placement: Literal["top-left", "top-center", "top-right", "center", "bottom-left", "bottom-center", "bottom-right"] = "top-left"
    composition: "Composition | None" = Field(default=None, description="Layout grammar; skeleton defaults are used when omitted")
    rationale: str = Field(max_length=300)

    @property
    def signature(self) -> tuple[str, str, str, str]:
        """Tuple that must differ between directions (FR-013)."""
        return (self.layout_family, self.red_application, self.photo_mode, self.mountains_variant)

    @model_validator(mode="after")
    def _generated_needs_brief(self) -> CreativeDirection:
        if self.background == BackgroundKind.GENERATED and not self.background_brief:
            raise ValueError("generated background requires background_brief")
        if self.mountains_variant.startswith("inverted") and self.red_application != RedApplication.BOLD:
            raise ValueError("inverted Moving Mountains require a red background (bold application)")
        return self


class DirectionSet(Strict):
    directions: list[CreativeDirection] = Field(min_length=3, max_length=4)

    @model_validator(mode="after")
    def _materially_different(self) -> DirectionSet:
        sigs = [d.signature for d in self.directions]
        if len(set(sigs)) != len(sigs):
            raise ValueError("directions must differ in layout/red/photo/mountains, not just wording")
        reds = {d.red_application for d in self.directions}
        if len(reds) < 2:
            raise ValueError("need at least one bold and one highlight direction")
        ids = [d.id for d in self.directions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate direction ids")
        families = [d.layout_family for d in self.directions]
        if len(set(families)) != len(families):
            raise ValueError("each direction must use a different layout family: "
                             "two variations in the same layout look like the same poster")
        return self


class Anchor(StrEnum):
    TOP_LEFT = "top-left"
    TOP_RIGHT = "top-right"
    MIDDLE_LEFT = "middle-left"
    MIDDLE_RIGHT = "middle-right"
    BOTTOM_LEFT = "bottom-left"
    CENTRE = "centre"


class PhotoPlacement(StrEnum):
    RIGHT = "right"
    LEFT = "left"
    CENTRE = "centre"
    FULL_BLEED_RIGHT = "full-bleed-right"
    INSET = "inset"


class PhotoShape(StrEnum):
    CUTOUT = "cutout"          # free-standing person, no frame
    CIRCLE = "circle"
    PANEL = "panel"            # photo inside a rounded rectangle
    ARCH = "arch"              # rounded-top panel: editorial feel


class MountainsPlacement(StrEnum):
    BASELINE = "baseline"      # full-width along the bottom
    CORNER_RIGHT = "corner-right"
    CORNER_LEFT = "corner-left"
    BEHIND_PHOTO = "behind-photo"
    BAND = "band"              # horizontal band behind the copy block


class Accent(StrEnum):
    RULE = "rule"              # short red rule under the headline
    BLOCK = "block"            # red block behind a word
    BAR = "bar"                # vertical bar beside the copy
    NONE = "none"


class Density(StrEnum):
    AIRY = "airy"
    BALANCED = "balanced"
    DENSE = "dense"


class Composition(Strict):
    """The layout grammar: what a creative direction may vary inside a skeleton.

    Every field is bounded, so composition stays inside the brand's rules while giving a
    genuinely wide range of looks. The renderer reads this; no free-form CSS is possible.
    """

    headline_anchor: Anchor = Anchor.TOP_LEFT
    headline_span: int = Field(default=8, ge=4, le=12, description="columns of 12")
    headline_scale: float = Field(default=1.0, ge=0.7, le=1.7)
    copy_span: int = Field(default=6, ge=3, le=12)
    photo_placement: PhotoPlacement = PhotoPlacement.RIGHT
    photo_shape: PhotoShape = PhotoShape.CUTOUT
    photo_scale: float = Field(default=1.0, ge=0.6, le=1.45)
    photo_shadow: bool = True
    mountains_placement: MountainsPlacement = MountainsPlacement.BASELINE
    mountains_scale: float = Field(default=1.0, ge=0.5, le=1.5)
    accent: Accent = Accent.NONE
    density: Density = Density.BALANCED
    centred: bool = False

    @model_validator(mode="after")
    def _columns_fit(self) -> Composition:
        if self.centred and self.headline_anchor in {Anchor.TOP_RIGHT, Anchor.MIDDLE_RIGHT}:
            raise ValueError("centred copy cannot also be right-anchored")
        if self.photo_placement in {PhotoPlacement.FULL_BLEED_RIGHT} and self.headline_span > 8:
            raise ValueError("a full-bleed photo leaves at most 8 columns for the headline")
        return self

    @property
    def photo_columns(self) -> int:
        """Columns of 12 the portrait occupies; copy takes what is left."""
        return {"right": 5, "left": 5, "centre": 6, "full-bleed-right": 6, "inset": 3}[
            self.photo_placement.value]

    @property
    def max_copy_span(self) -> int:
        return max(4, 12 - self.photo_columns)

    @property
    def gap_scale(self) -> float:
        return {"airy": 1.45, "balanced": 1.0, "dense": 0.72}[self.density.value]

    @property
    def margin_scale(self) -> float:
        return {"airy": 1.35, "balanced": 1.0, "dense": 0.85}[self.density.value]


CreativeDirection.model_rebuild()
