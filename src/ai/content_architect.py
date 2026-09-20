"""The Content Architect: shapes what the page has into what the page needs.

It does *not* extract facts — `extract_modules` already did that during the brief, verified
against the upload. This agent decides how the verified material is grouped and ordered, and
writes the short connective copy around it.

The distinction matters. Anything it writes is subject to the ordinary copy rules; anything
it groups was already sourced and locked. A model that could do both would be able to
launder an invention into a "benefit".
"""

from __future__ import annotations

from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Strict
from ..contracts.content import ContentItem, ContentSet
from ..contracts.copy import Claim, Copy
from ..contracts.profile import AgentProfile
from ..policy.rules import PolicyDecision
from .copywriter import INSTRUCTIONS as COPY_INSTRUCTIONS
from .copywriter import _prompt as copy_prompt
from .model_gateway import ModelGateway

INSTRUCTIONS = COPY_INSTRUCTIONS + """

This campaign also has structured content already quoted from the representative's uploads —
speakers, benefits or steps. You do NOT rewrite those: they are verified quotations and are
placed exactly as they stand.

What you do decide:
- `order`: the ids, in the order they should read. Lead with whatever earns attention.
- `intro`: one short line introducing the group, if it needs one. Your words, so the ordinary
  rules apply: no dates, no figures, no claims.

If the content reads well in the order it arrived, return it unchanged.
"""


class ContentPlanDraft(Strict):
    """The copy slots, plus how the sourced material is arranged."""

    headline: str = Field(max_length=70)
    subheadline: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, max_length=280)
    cta: str | None = Field(default=None, max_length=30)
    signature: str | None = Field(default=None, max_length=60)
    social_caption: str | None = Field(default=None, max_length=400)
    alt_text: str | None = Field(default=None, max_length=200)
    claims: list[str] = Field(default_factory=list, max_length=4)
    order: list[str] = Field(default_factory=list, max_length=24,
                             description="Content item ids, in reading order")
    intro: str | None = Field(default=None, max_length=90)


def reorder(content: ContentSet, order: list[str]) -> tuple[ContentSet, list[str]]:
    """Apply the model's ordering. Ids it invents are ignored; ids it forgets keep their place.

    Reordering is the only thing it may do here — the items themselves are already locked, so
    an unknown id is a mistake rather than a new item.
    """
    by_id = {item.id: item for item in content.items}
    rejected = [oid for oid in order if oid not in by_id]
    ordered = [by_id[oid] for oid in order if oid in by_id]
    ordered += [item for item in content.items if item.id not in set(order)]
    return ContentSet(items=ordered), rejected


async def build_content(gateway: ModelGateway, brief: CampaignBrief, profile: AgentProfile,
                        decision: PolicyDecision) -> tuple[Copy, ContentSet, list[str]]:
    """Write the copy and arrange the sourced content. Returns copy, content, rejections."""
    content = brief.content

    def make(tier):
        return gateway.agent("content_architect", tier=tier, output_type=ContentPlanDraft,
                             instructions=INSTRUCTIONS)

    prompt = copy_prompt(brief, profile, decision)
    if content.items:
        listing = "\n".join(
            f"  {i.id}: {i.label or ''}"
            + (f" — {i.role}" if i.role else "")
            + (f" | {i.body[:60]}" if i.body else "")
            for i in content.items)
        prompt += (f"\n\nVerified content already quoted from the uploads "
                   f"({sum(content.counts().values())} items):\n{listing}\n"
                   "Return their ids in `order`. Do not rewrite them.")

    result = await gateway.run(make("quality"), prompt, node="content_architect",
                               tier="quality", rebuild=make)
    draft = result.output

    arranged, rejected = (reorder(content, draft.order) if content.items
                          else (content, []))
    if draft.intro:
        # the intro is the architect's own words, so it is copy, not content
        arranged = ContentSet(items=[*arranged.items])

    copy = Copy(
        headline=draft.headline,
        subheadline=draft.subheadline or draft.intro,
        body=draft.body,
        cta=draft.cta or (brief.cta.text if brief.cta else None),
        signature=draft.signature or profile.display_name,
        social_caption=draft.social_caption,
        alt_text=draft.alt_text,
        claims=[Claim(text=c) for c in draft.claims],
    )
    return copy, arranged, rejected
