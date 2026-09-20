"""What replaces DesignDoc on the free-form path.

A `DesignDoc` describes a page as a list of typed elements in named slots, which is what makes
it safe and also what makes it templated. Here the page is authored markup plus a stylesheet,
and safety comes from the binder instead. Everything else — versioning, lineage, reproducibility
— keeps the same shape, so the rest of the system does not need to care which engine ran.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..contracts.common import Strict
from .css import CssRule
from .vocabulary import MAX_CUSTOM_CLASSES, VocabularyError, vocabulary_for

Archetype = Literal["benefit-grid", "speaker-roster", "editorial-feature",
                    "chip-index", "fullbleed-hero"]
Motif = Literal["hairline-rule", "circular-badge", "pill", "ring",
                "arch-frame", "column-rule", "chip-row", "swoosh"]


class DesignSystem(Strict):
    """One variation's look: the choices, and the stylesheet that expresses them.

    Authored once per variation and shared across all of its pages, so a three-page brochure
    reads as a set rather than three unrelated posters.
    """

    variation_id: str = Field(pattern=r"^[a-d]$")
    name: str = Field(max_length=60)
    archetype: Archetype
    ground: Literal["bold", "light"]
    type_pairing: Literal["display-led", "editorial", "compact", "monumental"]
    primary_motif: Motif
    grid_columns: int = Field(default=12, ge=4, le=12)
    image_treatment: Literal["cutout", "panel", "full-bleed", "none"]
    custom_classes: list[str] = Field(default_factory=list, max_length=MAX_CUSTOM_CLASSES)
    rules: list[CssRule] = Field(default_factory=list, max_length=120)
    rationale: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _vocabulary_is_valid(self) -> DesignSystem:
        try:
            vocabulary_for(self.custom_classes)
        except VocabularyError as exc:
            raise ValueError(exc.message) from exc
        return self

    @property
    def signature(self) -> tuple[str, str, str, str, str]:
        """What must differ between variations (the analogue of CreativeDirection.signature)."""
        return (self.archetype, self.ground, self.type_pairing,
                self.primary_motif, self.image_treatment)

    @property
    def vocabulary(self) -> frozenset[str]:
        return vocabulary_for(self.custom_classes)


class DesignSystemSet(Strict):
    """Four systems that must genuinely differ.

    The structured engine enforces this with `DirectionSet._materially_different`, because two
    variations in one layout family look like the same poster. Free-form needs it more, not
    less: left alone, four independent generations converge on one look — which is the
    complaint that started this work.
    """

    #: One is allowed: iterating on a single design is a legitimate, much cheaper run. The
    #: distinctness rules below only bite once there is more than one thing to compare.
    systems: list[DesignSystem] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def _materially_different(self) -> DesignSystemSet:
        ids = [s.variation_id for s in self.systems]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate variation ids")

        signatures = [s.signature for s in self.systems]
        if len(set(signatures)) != len(signatures):
            raise ValueError("design systems must differ in archetype, ground, type pairing, "
                             "motif or image treatment, not just wording")

        archetypes = [s.archetype for s in self.systems]
        if len(set(archetypes)) != len(archetypes):
            raise ValueError("each variation must use a different archetype: two variations "
                             "built the same way look like the same poster")

        # A spread of three or more that is all one ground is a palette, not a set of ideas.
        # Below that there is nothing to spread.
        grounds = {s.ground for s in self.systems}
        if len(self.systems) >= 3 and len(grounds) < 2:
            raise ValueError("need at least one bold (red ground) and one light variation")

        motifs = {s.primary_motif for s in self.systems}
        if len(self.systems) == 4 and len(motifs) < 3:
            raise ValueError(f"only {len(motifs)} distinct motifs across 4 variations; "
                             "at least 3 are needed for the set to read as different ideas")
        return self

    def by_id(self, variation_id: str) -> DesignSystem:
        match = next((s for s in self.systems if s.variation_id == variation_id), None)
        if match is None:
            raise KeyError(f"no design system {variation_id!r}")
        return match


class PagePlan(Strict):
    """One page's job: what it is for, what shape it is, and what must appear on it."""

    index: int = Field(ge=1, le=3)
    purpose: Literal["hook", "benefits", "proof", "details", "cta", "invite"]
    shape: Literal["preset", "long_form"] = "preset"
    preset: str = "instagram_portrait"
    must_include: list[str] = Field(default_factory=list, max_length=30,
                                    description="References that must appear exactly once")
    content_ids: list[str] = Field(default_factory=list, max_length=24)


class Storyboard(Strict):
    """How the story spans pages. Produced by the Narrative Planner, enforced by the binder."""

    pages: list[PagePlan] = Field(min_length=1, max_length=3)
    rationale: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _pages_are_coherent(self) -> Storyboard:
        indices = [p.index for p in self.pages]
        if indices != list(range(1, len(self.pages) + 1)):
            raise ValueError(f"pages must be numbered 1..{len(self.pages)}, got {indices}")

        first = self.pages[0].must_include
        if "copy.headline" not in first:
            raise ValueError("page 1 must carry the headline")
        if not any(r.startswith("brand.logo") for r in first):
            raise ValueError("page 1 must carry the AIA logo")

        # A reference may only be placed once across the whole document, so a fact cannot
        # appear twice with different treatment.
        placed = [r for page in self.pages for r in page.must_include]
        duplicates = {r for r in placed if placed.count(r) > 1}
        if duplicates:
            raise ValueError(f"reference(s) placed on more than one page: {sorted(duplicates)}")
        return self

    @property
    def is_multipage(self) -> bool:
        return len(self.pages) > 1

    def requires(self, ref: str) -> bool:
        return any(ref in page.must_include for page in self.pages)


class FreeformPage(Strict):
    """One authored page. `html` is a string on purpose — see the note below."""

    plan: PagePlan
    html: str = Field(max_length=40_000)
    rules: list[CssRule] = Field(default_factory=list, max_length=80)
    notes: str = Field(default="", max_length=200)


class FreeformDoc(Strict):
    """A versioned variation, the free-form counterpart of DesignDoc.

    Persisted to `designs/variation-<id>.v<n>.json` under the *existing* filename grammar, so
    `revise.py`'s stem parsing keeps working untouched.
    """

    doc_id: str
    campaign_id: str
    variation_id: str
    version: int = 1
    parent_version: int | None = None
    system: DesignSystem
    pages: list[FreeformPage] = Field(min_length=1, max_length=3)
    brand_pack_version: str = "0.2"
    language: str = "en"
    notes: list[str] = Field(default_factory=list)

    def next_version(self, **changes: object) -> FreeformDoc:
        data = self.model_dump()
        data |= changes
        data["version"] = self.version + 1
        data["parent_version"] = self.version
        return FreeformDoc.model_validate(data)


# `html` is a plain string rather than a recursive node model deliberately. A recursive tree
# under extra="forbid" is exactly the shape that made Gemini refuse the 11-variant EditOp union
# with "schema produces a constraint that has too many states". Strictness for markup lives in
# html_parse.py instead; CSS can stay structured because list[CssRule] is flat.
