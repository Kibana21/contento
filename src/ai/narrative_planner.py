"""The Narrative Planner: how the story spans pages.

This replaces the Creative Director on the free-form path. The Creative Director picked a
layout family; this picks a *shape* — one poster, one long-form page, a carousel, or a
two-to-three page brochure — and decides what each page carries.

Page count is not the model's decision alone. Content volume and the campaign family
constrain it, because "how many speakers are there" is a fact about the brief rather than a
creative choice, and a model asked to be helpful will otherwise pad.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Strict
from ..contracts.content import ContentSet
from ..contracts.copy import Copy
from ..freeform.contracts import PagePlan, Storyboard
from ..policy.rules import PolicyDecision
from .model_gateway import ModelGateway

Shape = Literal["poster", "long_form", "carousel", "brochure"]

#: Roughly how much a single poster can carry before it stops being readable at a glance.
#: Above this, the shape has to change rather than the type getting smaller.
MODULES_PER_POSTER = 3
MODULES_PER_PAGE = 4

INSTRUCTIONS = """
You decide how a campaign's story is laid out across pages.

Choose one shape:
  poster     — a single fixed-size poster. The default, and right for a greeting or a simple
               invitation with a handful of facts.
  long_form  — one page whose height grows with its content. Right when there are several
               repeating items (speakers, benefits) that all deserve equal billing.
  carousel   — a sequence of square slides telling one story. Right for social, when the
               content has a natural order.
  brochure   — two or three pages. Right only when there is genuinely enough substance:
               a product story with benefits, proof and details.

Then say what each page carries, by reference name. Rules:
- Page 1 always carries copy.headline and the AIA logo.
- The legal line (policy.disclaimer) goes on the last page, once.
- A reference appears on exactly one page. Never repeat a fact across pages.
- Put every content item you were told exists somewhere. Do not invent references.
- Prefer fewer pages. A second page must earn itself; padding is worse than brevity.
"""


class StoryboardDraft(Strict):
    """Flat by design: nested page objects with per-page reference lists is about as much
    structure as Gemini takes reliably."""

    shape: Shape = "poster"
    page_count: int = Field(default=1, ge=1, le=3)
    purposes: list[str] = Field(default_factory=list, max_length=3)
    page_refs: list[str] = Field(
        default_factory=list, max_length=3,
        description="One entry per page: its references, comma separated")
    rationale: str = Field(default="", max_length=300)


def available_refs(brief: CampaignBrief, copy: Copy, content: ContentSet,
                   decision: PolicyDecision) -> list[str]:
    """Every reference this campaign can actually place. The planner may use no others."""
    refs = ["copy.headline", "brand.logo.red"]
    for slot in ("subheadline", "body", "cta"):
        if getattr(copy, slot, None):
            refs.append(f"copy.{slot}")
    if brief.event:
        refs += [f"facts.event.{k}" for k, v in brief.event.model_dump().items()
                 if v not in (None, "", []) and k != "speakers"]
    if brief.cta and brief.cta.url or brief.agent.photo_id:
        refs.append("generated.qr")
    if brief.agent.photo_id:
        refs.append("profile.photo." + brief.agent.photo_id)
    for plural, count in content.counts().items():
        for i in range(count):
            refs += [f"content.{plural}.{i}.{f}" for f in ("label", "role", "body")
                     if content.resolve(f"{plural}.{i}.{f}")]
    if decision.required_disclaimers:
        refs.append("policy.disclaimer")
    return refs


def suggest_shape(content: ContentSet, brief: CampaignBrief) -> Shape:
    """The deterministic floor: content volume decides before the model is asked."""
    modules = sum(content.counts().values())
    if modules > MODULES_PER_PAGE * 2:
        return "brochure"
    if modules > MODULES_PER_POSTER:
        return "long_form"
    return "poster"


def _preset_for(shape: Shape, decision: PolicyDecision) -> str:
    if shape == "carousel":
        return "instagram_square"
    if shape == "brochure":
        return "a4_print"
    return (decision.export_presets or ["instagram_portrait"])[0]


def to_storyboard(draft: StoryboardDraft, allowed: list[str], decision: PolicyDecision,
                  ) -> tuple[Storyboard, list[str]]:
    """Build the contract from the draft, dropping references the campaign cannot place."""
    rejected: list[str] = []
    pages: list[PagePlan] = []
    placed: set[str] = set()
    shape = draft.shape
    preset = _preset_for(shape, decision)

    for index in range(min(draft.page_count, len(draft.page_refs) or draft.page_count)):
        raw = draft.page_refs[index] if index < len(draft.page_refs) else ""
        refs: list[str] = []
        for ref in (r.strip() for r in raw.split(",")):
            if not ref:
                continue
            if ref not in allowed:
                rejected.append(f"page {index + 1}: {ref!r} is not available in this campaign")
            elif ref in placed:
                rejected.append(f"page {index + 1}: {ref!r} is already on an earlier page")
            else:
                refs.append(ref)
                placed.add(ref)
        purpose = (draft.purposes[index] if index < len(draft.purposes) else "hook")
        pages.append(PagePlan(
            index=index + 1,
            purpose=purpose if purpose in {"hook", "benefits", "proof", "details", "cta",
                                           "invite"} else "hook",
            shape="long_form" if shape == "long_form" else "preset",
            preset=preset, must_include=refs))

    # What the planner leaves off is mostly a design choice — a poster carries the venue but
    # rarely the end time. Only the legally mandatory line is forced back on; anything else
    # omitted is reported, so a dropped fact is visible without being overruled.
    if decision.required_disclaimers and "policy.disclaimer" not in placed and pages:
        pages[-1].must_include = [*pages[-1].must_include, "policy.disclaimer"]
        placed.add("policy.disclaimer")
    rejected += [f"not placed on any page: {r}" for r in allowed if r not in placed]
    return Storyboard(pages=pages, rationale=draft.rationale), rejected


def fallback_storyboard(brief: CampaignBrief, copy: Copy, content: ContentSet,
                        decision: PolicyDecision) -> Storyboard:
    """One page carrying everything, sized by content volume. Always valid."""
    shape = suggest_shape(content, brief)
    refs = available_refs(brief, copy, content, decision)
    return Storyboard(
        pages=[PagePlan(index=1, purpose="invite",
                        shape="long_form" if shape in {"long_form", "brochure"} else "preset",
                        preset=_preset_for("long_form" if shape == "brochure" else shape, decision),
                        must_include=refs)],
        rationale="single page carrying the whole campaign")


async def plan_narrative(gateway: ModelGateway, brief: CampaignBrief, copy: Copy,
                         content: ContentSet, decision: PolicyDecision,
                         ) -> tuple[Storyboard, str, list[str]]:
    """Returns the storyboard, how it was produced, and anything that was refused."""
    allowed = available_refs(brief, copy, content, decision)
    agent = gateway.agent("narrative_planner", tier="fast", output_type=StoryboardDraft,
                          instructions=INSTRUCTIONS)
    prompt = "\n".join([
        f"Campaign: {brief.family.value}, {decision.risk.value} risk.",
        f"Story: {brief.story.core_message}",
        f"Repeating content: {content.counts() or 'none'}",
        f"Suggested shape from content volume: {suggest_shape(content, brief)}",
        f"Available references (use only these):\n  " + "\n  ".join(allowed),
        "",
        "Give one entry in page_refs per page, comma separated.",
    ])
    try:
        result = await gateway.run(agent, prompt, node="narrative_planner", tier="fast")
    except Exception:
        return fallback_storyboard(brief, copy, content, decision), "fallback", []
    try:
        board, rejected = to_storyboard(result.output, allowed, decision)
        return board, "model", rejected
    except Exception:
        return fallback_storyboard(brief, copy, content, decision), "fallback", []
