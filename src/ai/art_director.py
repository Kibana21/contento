"""The Art Director: four design systems, authored as real CSS.

This is the agent that replaces picking one of four hand-built skeletons. It writes the
stylesheet — palette application, type, rhythm, motif — against a closed class vocabulary that
the Page Composer also codes against, so the two independent calls produce a page that is
actually styled.

All four systems come back from **one** call, deliberately. Asked separately, four generations
converge on the same safe idea; asked together, the model differentiates them against each
other. The contract then checks that structurally, because asking nicely is not a guarantee.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, ValidationError

from ..contracts.brand import BrandPack
from ..contracts.brief import CampaignBrief
from ..contracts.common import Strict
from ..contracts.content import ContentSet
from ..contracts.copy import Copy
from ..contracts.profile import AgentProfile
from ..freeform.contracts import DesignSystem, DesignSystemSet
from ..freeform.css import ALLOWED_PROPERTIES, REFUSED, CssError, CssRule, check_declaration
from ..freeform.vocabulary import CORE_CLASSES, MAX_CUSTOM_CLASSES
from .model_gateway import ModelGateway

#: The policy documents that describe how AIA design looks, rather than what it says.
DESIGN_POLICIES = ("design-principles", "colour", "typography", "layout", "logo-rules",
                   "imagery", "moving-mountains")

#: Archetypes, drawn from the reference brochures. Pre-assigning one per variation is the
#: mechanism that actually prevents convergence: the model varies *within* a given idea
#: rather than choosing the same idea four times.
ARCHETYPES = ("speaker-roster", "benefit-grid", "editorial-feature", "chip-index",
              "fullbleed-hero")

INSTRUCTIONS = """
You are the art director for AIA Singapore's Agent Marketing Studio. You design the visual
system for a set of poster variations, and you express it as CSS.

You do NOT write any words. Every piece of text on the page is placed automatically from
verified data; your job is entirely how the page looks.

How your CSS is used:
- You style a fixed vocabulary of semantic classes. `.module` is one row of a repeating group
  — a speaker, a benefit, a step — and what it looks like is your choice entirely: a card, an
  icon badge beside a label, a numbered row, a bordered panel.
- You may declare up to 8 extra class names for your own motif, and style those too.
- Another step writes the markup using exactly this vocabulary. If you style a class nobody
  uses, or forget one that is used, the page will be wrong. Style the whole vocabulary.

Hard rules:
- Colour values are ONLY token references: var(--red), var(--red-80), var(--red-60),
  var(--red-40), var(--red-20), var(--charcoal), var(--charcoal-80), var(--charcoal-60),
  var(--charcoal-20), var(--white), var(--ground), var(--ink), transparent, currentColor.
  A raw hex value is rejected.
- Do not set font-family: the typeface is assigned from the brand pack.
- No `content`, no counters, no list markers: those would put text on the page.
- Nothing that hides content: no display:none, no visibility, no opacity below 0.15, no
  clip-path, no text-indent.
- AIA Red must lead. On a light ground use it with confidence as the accent and the headline
  colour; on a bold ground it is the page.
- Text needs 4.5:1 contrast against what is behind it. charcoal-60 on white is only 3.49:1 —
  use charcoal or charcoal-80 for anything small, especially the legal line.
- The Moving Mountains are never rotated or flipped.

Make the four systems genuinely different. Each has a different archetype, and they must
differ in ground, type pairing, motif or image treatment as well. At least one bold (red
ground) and one light. Aim for four ideas a designer would recognise as separate, not one
idea in four colourways.
"""


class CssRuleDraft(Strict):
    """Loose on the way in, so one bad declaration does not fail the whole call."""

    selector: str = Field(max_length=200)
    declarations: dict[str, str] = Field(default_factory=dict)


class DesignSystemDraft(Strict):
    variation_id: str
    name: str = Field(max_length=60)
    archetype: str
    ground: str
    type_pairing: str
    primary_motif: str
    image_treatment: str
    grid_columns: int = Field(default=12, ge=4, le=12)
    custom_classes: list[str] = Field(default_factory=list, max_length=MAX_CUSTOM_CLASSES)
    rules: list[CssRuleDraft] = Field(default_factory=list, max_length=120)
    rationale: str = Field(default="", max_length=300)


class DesignSystemSetDraft(Strict):
    systems: list[DesignSystemDraft] = Field(min_length=3, max_length=4)


def to_design_systems(draft: DesignSystemSetDraft) -> tuple[list[DesignSystem], list[str]]:
    """Convert drafts into contracts, dropping declarations that are out of bounds.

    Same pattern as `to_edit_ops`: the model's output is a proposal, and code decides what
    survives. A refused declaration is reported rather than silently kept.
    """
    systems: list[DesignSystem] = []
    rejected: list[str] = []
    for item in draft.systems:
        rules: list[CssRule] = []
        for rule in item.rules:
            kept: dict[str, str] = {}
            for prop, value in rule.declarations.items():
                try:
                    check_declaration(prop.strip().lower(), str(value).strip())
                except CssError as exc:
                    rejected.append(f"{rule.selector}: {exc.message}")
                    continue
                kept[prop.strip().lower()] = str(value).strip()
            if not kept:
                continue
            try:
                rules.append(CssRule(selector=rule.selector, declarations=kept))
            except ValidationError as exc:
                rejected.append(f"{rule.selector}: {exc.errors()[0]['msg']}")
        try:
            systems.append(DesignSystem(**(item.model_dump() | {"rules": rules})))
        except ValidationError as exc:
            rejected.append(f"system {item.variation_id}: {exc.errors()[0]['msg']}")
    return systems, rejected


@lru_cache(maxsize=1)
def _design_brief(brand_root: str) -> str:
    """The stable prefix: how AIA design looks, in AIA's own words.

    Identical on every call in a run, which is what makes it the context-caching candidate.
    """
    from ..loaders import load_brand_pack

    brand = load_brand_pack(brand_root)
    parts: list[str] = []
    for name in DESIGN_POLICIES:
        path = brand.policies.get(name)
        if path:
            parts.append(f"--- {name} ---\n{path.read_text().strip()}")
    return "\n\n".join(parts)


def _vocabulary_brief(brand: BrandPack) -> str:
    scale = brand.type_scale()
    return json.dumps({
        "classes": sorted(CORE_CLASSES),
        "type_scale_at_1080": {k: v.get("size") for k, v in scale.items()},
        "hierarchy": {"subheading_is": "headline / 3", "body_is": "subheading / 2",
                      "min_text_px": brand.hierarchy()["min_body_size"]["digital_px"]},
        "allowed_properties": sorted(ALLOWED_PROPERTIES),
        "refused_properties": sorted(REFUSED),
    }, separators=(",", ":"))


def _prompt(brief: CampaignBrief, copy: Copy, content: ContentSet, profile: AgentProfile,
            brand: BrandPack, count: int) -> str:
    counts = content.counts()
    archetypes = list(ARCHETYPES[:count])
    return "\n".join([
        _design_brief(str(brand.root)),
        "",
        "--- the vocabulary and the scale you design against ---",
        _vocabulary_brief(brand),
        "",
        "--- this campaign ---",
        f"Family: {brief.family.value}. Objective: {brief.objective}.",
        f"Story: {brief.story.core_message} (tone: {', '.join(brief.tone) or brief.story.emotional_tone})",
        f"Headline as it will be set: {copy.headline!r}",
        f"Repeating content on the page: {counts or 'none'}",
        f"Portrait available: {bool(brief.agent.photo_id)}",
        f"Representative prefers: {', '.join(profile.preferences.style) or 'no stated preference'}",
        f"Representative dislikes: {', '.join(profile.preferences.avoid) or 'nothing stated'}",
        "",
        f"Produce {count} systems, with ids {', '.join(chr(97 + i) for i in range(count))} "
        f"and archetypes in this order: {', '.join(archetypes)}.",
        "Style every class in the vocabulary. Give each system a full stylesheet — this is "
        "the only description of how its pages look.",
    ])


def fallback_design_systems(count: int = 4) -> DesignSystemSet:
    """A valid, plain set used when the model cannot produce a distinct one.

    Deliberately modest: its job is to keep a run producing something, not to look good.
    """
    from ..freeform.fixtures import speaker_roster_system

    base = speaker_roster_system()
    plan = [
        ("a", "Speaker roster", "speaker-roster", "light", "display-led", "ring", "cutout"),
        ("b", "Benefit grid", "benefit-grid", "bold", "compact", "hairline-rule", "none"),
        ("c", "Editorial feature", "editorial-feature", "light", "editorial", "column-rule", "panel"),
        ("d", "Chip index", "chip-index", "light", "monumental", "pill", "none"),
    ][:count]
    return DesignSystemSet(systems=[
        DesignSystem(variation_id=vid, name=name, archetype=arch, ground=ground,
                     type_pairing=pairing, primary_motif=motif, image_treatment=treatment,
                     custom_classes=base.custom_classes, rules=base.rules,
                     rationale="standard treatment")
        for vid, name, arch, ground, pairing, motif, treatment in plan
    ])


async def choose_design_systems(gateway: ModelGateway, brief: CampaignBrief, copy: Copy,
                                content: ContentSet, profile: AgentProfile, brand: BrandPack,
                                *, count: int = 4) -> tuple[DesignSystemSet, str, list[str]]:
    """Returns the set, how it was produced, and any declarations that were refused."""
    def make(tier):
        return gateway.agent("art_director", tier=tier, output_type=DesignSystemSetDraft,
                             instructions=INSTRUCTIONS)

    prompt = _prompt(brief, copy, content, profile, brand, count)
    tier = "authoring" if "authoring" in gateway.models else "quality"

    for attempt, source in ((1, "model"), (2, "model-retry")):
        try:
            result = await gateway.run(make(tier), prompt, node="art_director", tier=tier,
                                       rebuild=make)
        except Exception:      # budget or provider failure: a plain set beats no campaign
            break
        systems, rejected = to_design_systems(result.output)
        try:
            return DesignSystemSet(systems=systems), source, rejected
        except ValidationError as exc:
            if attempt == 2:
                break
            reason = "; ".join(e["msg"] for e in exc.errors())
            prompt = (f"{prompt}\n\nYour previous set was rejected: {reason}\n"
                      "Return systems that differ in archetype, ground, type pairing, motif "
                      "and image treatment, with at least one bold and one light ground.")
    return fallback_design_systems(count), "fallback", []
