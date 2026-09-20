"""D5 — build a DesignDoc from brief + copy + creative direction.

The builder is deterministic. It decides *where* things go, but never *what they say*:
every factual element carries a reference, so the renderer reads values from the brief and
profile at render time (ADR-001/004).
"""

from __future__ import annotations

from ..contracts.brand import BrandPack
from ..contracts.brief import CampaignBrief
from ..contracts.copy import Copy
from ..contracts.creative import (BackgroundKind, Composition, CreativeDirection,
                                  MountainsVariant, PhotoMode, PhotoShape)
from ..contracts.design import Background, Canvas, DesignDoc, Element, ElementType
from ..contracts.profile import AgentProfile
from ..policy.rules import PolicyDecision
from ..validate.copy import disclaimer_text
from .layouts import FAMILIES, LayoutFamily

#: Event facts shown on event-style layouts, in reading order.
EVENT_FACTS = ("event.date", "event.time_start", "event.venue")


def _style(family: LayoutFamily, etype: ElementType) -> str | None:
    return {
        ElementType.HEADLINE: "headline",
        ElementType.SUBHEADLINE: "subheading",
        ElementType.BODY: "body",
        ElementType.FACT: "detail",
        ElementType.CTA: "detail",
        ElementType.CONTACT_BLOCK: "detail",
        ElementType.DISCLAIMER: "legal",
    }.get(etype)


def build_design(
    brief: CampaignBrief,
    copy: Copy,
    direction: CreativeDirection,
    profile: AgentProfile,
    decision: PolicyDecision,
    brand: BrandPack,
    *,
    preset: str = "instagram_portrait",
    background_asset: str | None = None,
) -> DesignDoc:
    family = FAMILIES[direction.layout_family]
    canvas = Canvas.from_preset(preset)
    theme = direction.red_application
    composition = (direction.composition or family.composition).model_copy()
    if direction.photo_mode is not PhotoMode.NONE and profile.photo(brief.agent.photo_id):
        # copy and portrait may never share columns (prevents layout.collision by construction)
        composition.headline_span = min(composition.headline_span, composition.max_copy_span)
        composition.copy_span = min(composition.copy_span, composition.headline_span)
    elements: list[Element] = []

    def add(eid: str, etype: ElementType, **kw) -> None:
        slot = family.slot_for(etype)
        if slot is None:
            return
        elements.append(Element(id=eid, type=etype, slot=slot, style_token=_style(family, etype), **kw))

    # ---- logo: white on a red ground, red otherwise (Brand Standards p39) --
    logo_colour = "white" if theme.value == "bold" else family.logo_colour
    add("logo", ElementType.LOGO, asset_ref=f"brand.logo.{logo_colour}",
        overrides={"colour": logo_colour, "height": round(canvas.short_edge * 0.07)})

    # ---- brand graphic -----------------------------------------------------
    if direction.mountains_variant is not MountainsVariant.NONE:
        corner = composition.mountains_placement.value in {"corner-right", "corner-left", "behind-photo"}
        add("mountains", ElementType.MOUNTAINS,
            overrides={"shape_set": "classic_4" if "4" in direction.mountains_variant.value else "classic_3",
                       "height": round(canvas.height * family.mountains_height * composition.mountains_scale),
                       "width": round(canvas.width * ((0.58 if corner else 1.0) * composition.mountains_scale)),
                       "position": ""})  # placement comes from the composition CSS

    # ---- words: only slots the copywriter actually produced ----------------
    add("headline", ElementType.HEADLINE, content_ref="copy.headline",
        overrides={"scale": composition.headline_scale})
    if copy.subheadline:
        add("subheadline", ElementType.SUBHEADLINE, content_ref="copy.subheadline")
    if copy.body:
        add("body", ElementType.BODY, content_ref="copy.body")

    # ---- facts: referenced, never inlined ---------------------------------
    if brief.event:
        known = brief.fact_map()
        for i, field in enumerate(f for f in EVENT_FACTS if f in known):
            add(f"fact-{i}", ElementType.FACT, content_ref=f"facts.{field}")

    # ---- portrait ----------------------------------------------------------
    photo = profile.photo(brief.agent.photo_id)
    if photo and direction.photo_mode is not PhotoMode.NONE:
        w, h = family.portrait_size
        width = round(canvas.width * w * composition.photo_scale)
        height = round(canvas.height * h * composition.photo_scale)
        if composition.photo_shape is PhotoShape.CIRCLE:
            height = width  # a circle needs a square box
        overrides: dict[str, object] = {"width": width, "height": height,
                                        "shape": composition.photo_shape.value,
                                        "shadow": composition.photo_shadow}
        add("portrait", ElementType.AGENT_PHOTO, asset_ref=f"profile.photos.{photo.id}", overrides=overrides)

    # ---- contact, call to action, QR --------------------------------------
    add("contact", ElementType.CONTACT_BLOCK)
    if copy.cta or brief.cta:
        add("cta", ElementType.CTA, content_ref="copy.cta")
    qr_url = (brief.cta.url if brief.cta and brief.cta.url else profile.qr_target)
    if qr_url:
        add("qr", ElementType.QR, asset_ref="generated.qr",
            overrides={"url": qr_url, "size": round(canvas.short_edge * 0.12)})

    # ---- mandatory legal line ---------------------------------------------
    if disclaimer_text(decision):
        # referenced, not inlined: the exact wording comes from the compliance pack (ADR-001)
        add("disclaimer", ElementType.DISCLAIMER, content_ref="policy.disclaimer")

    background = Background(kind="solid", colour_token="core.red" if theme.value == "bold" else "core.white")
    if direction.background is BackgroundKind.GENERATED and background_asset:
        background = Background(kind="generated_image", asset=background_asset, colour_token=None,
                                generation={"brief": direction.background_brief or ""})
    elif direction.background is BackgroundKind.LIBRARY_IMAGE and background_asset:
        background = Background(kind="library_image", asset=background_asset, colour_token=None)

    return DesignDoc(
        design_id=f"{brief.campaign_id}-{direction.id}",
        campaign_id=brief.campaign_id,
        direction_id=direction.id,
        canvas=canvas,
        layout_family=family.name,
        theme=theme,
        mountains=direction.mountains_variant,
        composition=composition,
        background=background,
        elements=elements,
        brand_pack_version=brand.version,
        language=brief.languages.primary.value,
        notes=[direction.rationale],
    )
