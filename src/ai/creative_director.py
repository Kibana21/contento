"""A4 — the Creative Director (BRD §20, FR-013, Risk 7).

Chooses 3-4 genuinely different creative directions. "Different" is defined structurally:
the tuple (layout family, red application, photo mode, mountains variant) must differ, and
the set must contain at least one bold and one highlight treatment. That rule is enforced
by the DirectionSet contract, not by asking the model nicely.

If the model returns a set that fails the rule, it is asked once more with the reason; if it
fails again we fall back to a hand-built set, so the pipeline always produces variations.
"""

from __future__ import annotations

import json

from pydantic import Field, ValidationError

from ..contracts.brief import CampaignBrief
from ..contracts.common import Strict
from ..contracts.creative import (BackgroundKind, CreativeDirection, DirectionSet,
                                  MountainsVariant, PhotoMode, RedApplication)
from ..contracts.copy import Copy
from ..contracts.profile import AgentProfile
from ..render.layouts import FAMILIES, catalogue, families_for
from .model_gateway import ModelGateway

INSTRUCTIONS = """
You are the creative director for AIA Singapore's Agent Marketing Studio. You choose
3 or 4 creative directions for one campaign. You do NOT write copy and you do not design
the page: you pick a layout family and its treatment, and explain why.

The four classic directions (adapt them to the campaign):
  Human              - the representative front and centre, warm, simple headline
  Premium editorial  - refined, spacious, restrained, red used only as an accent
  Information first  - facts and hierarchy lead, immediately readable
  Contemporary social- solid red ground, dynamic, social-first, higher energy

Hard requirements:
- Every direction must use a DIFFERENT layout_family. Two variations in the same layout
  look like the same poster.
- Directions must also differ in red_application, photo_mode or mountains_variant.
- Include at least one `bold` (red ground) and at least one `highlight` (light ground).
- Only use a layout_family, photo_mode and mountains_variant offered in the catalogue.
- `inverted` mountains only ever sit on a red ground, so pair them with `bold`.
- Set `composition` to shape the page. Use it to make the spread feel varied: change where
  the headline sits and how large it is, which side the portrait takes and its shape
  (cutout, circle, panel, arch), where the Moving Mountains sit, the accent device and the
  density. A wide, airy editorial layout and a tight, dense information layout should not
  look like the same poster with different words. Omit `composition` to accept the family's
  own defaults.
- Choose `generated` background only when a photographic or illustrative scene genuinely
  helps (festive mood, venue atmosphere). Then write `background_brief` describing the scene:
  people-focused or abstract, warm natural light, no text, no logos, no faces of the
  representative, no single-use plastics. Otherwise choose `solid` or `brand_graphic`.
"""


class DirectionSetDraft(Strict):
    directions: list[CreativeDirection] = Field(min_length=3, max_length=4)
    rationale: str = Field(default="", max_length=300, description="Why this spread of ideas")


def fallback_directions(brief: CampaignBrief, count: int = 4) -> DirectionSet:
    """Deterministic, always-valid spread used when the model cannot produce a distinct set."""
    suited = [f.name for f in families_for(brief.family.value)]
    plan = [
        ("a", "Human", "festive-portrait", RedApplication.HIGHLIGHT, PhotoMode.CUTOUT_FRONT,
         MountainsVariant.CORE_3),
        ("b", "Premium editorial", "editorial-minimal", RedApplication.HIGHLIGHT, PhotoMode.CONTAINER,
         MountainsVariant.OUTLINE),
        ("c", "Information first", "event-information", RedApplication.HIGHLIGHT, PhotoMode.NONE,
         MountainsVariant.CORE_4),
        ("d", "Contemporary social", "social-bold", RedApplication.BOLD, PhotoMode.CUTOUT_FRONT,
         MountainsVariant.INVERTED_4),
    ]
    # lead with the families that suit this campaign, but never repeat one
    plan.sort(key=lambda row: suited.index(row[2]) if row[2] in suited else len(suited))
    plan = [(chr(ord("a") + i), *row[1:]) for i, row in enumerate(plan[:count])]
    seen: set[tuple] = set()
    directions: list[CreativeDirection] = []
    for did, name, family, red, photo, mountains in plan:
        if family not in FAMILIES or family in {f for f, *_ in seen}:
            continue
        seen.add((family, red, photo, mountains))
        directions.append(CreativeDirection(
            id=did, name=name, layout_family=family, red_application=red, photo_mode=photo,
            mountains_variant=mountains, background=BackgroundKind.SOLID,
            rationale=f"{name}: standard AIA treatment for a {brief.family.value} campaign."))
    return DirectionSet(directions=directions)


def _prompt(brief: CampaignBrief, copy: Copy, profile: AgentProfile) -> str:
    suited = {f.name for f in families_for(brief.family.value)}
    # compact catalogue: the director needs the options, not prose (cost control, §7.3)
    cat = [{"layout_family": c["layout_family"], "look": c["description"].split(":")[0],
            "theme": c["default_theme"], "photo_modes": c["photo_modes"],
            "mountains": c["mountains_variants"]}
           for c in catalogue() if c["layout_family"] in suited] or catalogue()
    return "\n".join([
        f"Campaign: {brief.family.value}, objective {brief.objective}",
        f"Story: {brief.story.core_message} (tone: {', '.join(brief.tone) or brief.story.emotional_tone})",
        f"Audience: {brief.audience.primary or 'clients'}",
        f"Headline: {copy.headline}",
        f"Has event: {bool(brief.event)} | has portrait: {bool(brief.agent.photo_id)}",
        f"Representative prefers: {', '.join(profile.preferences.style) or 'no stated preference'}",
        f"Representative dislikes: {', '.join(profile.preferences.avoid) or 'nothing stated'}",
        f"Produce {brief.variation_count} directions.",
        "For each, set a composition that suits the idea: vary headline anchor and scale, "
        "photo placement and shape, mountains placement, accent and density.",
        "",
        "Layout catalogue:",
        json.dumps(cat, separators=(",", ":")),
    ])


async def choose_directions(gateway: ModelGateway, brief: CampaignBrief, copy: Copy,
                            profile: AgentProfile) -> tuple[DirectionSet, str]:
    """Returns the direction set and how it was produced ('model', 'model-retry' or 'fallback')."""
    def make(tier):
        return gateway.agent("creative_director", tier=tier, output_type=DirectionSetDraft,
                             instructions=INSTRUCTIONS)

    agent = make("quality")
    prompt = _prompt(brief, copy, profile)

    for attempt, source in ((1, "model"), (2, "model-retry")):
        try:
            result = await gateway.run(agent, prompt, node="creative_director", tier="quality",
                                       rebuild=make)
        except Exception:  # budget or model failure: fall back rather than fail the campaign
            break
        try:
            return DirectionSet(directions=result.output.directions), source
        except ValidationError as exc:
            if attempt == 2:
                break
            reason = "; ".join(e["msg"] for e in exc.errors())
            prompt = (f"{prompt}\n\nYour previous set was rejected: {reason}\n"
                      "Return a set where every direction has a different combination of "
                      "layout_family, red_application, photo_mode and mountains_variant, "
                      "including at least one bold and one highlight.")
    return fallback_directions(brief, brief.variation_count), "fallback"
