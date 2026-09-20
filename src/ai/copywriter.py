"""A3 — the Copywriter (BRD §19, Standalone §10).

Writes the words only. It never states a fact that is not already in the brief: dates,
venues, contact details and legal lines are placed by the renderer from locked facts.

Voice comes from three places:
  * the Brand Standards tone principles and mentor persona (brand/aia-singapore/policy/),
  * the Singapore cultural cluster ("On your side"),
  * real AIA SG headlines from knowledge/approved-copy/ as few-shot examples.
"""

from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Family, Strict
from ..contracts.copy import Claim, Copy
from ..contracts.profile import AgentProfile
from ..policy.rules import PolicyDecision
from .model_gateway import ModelGateway

CORPUS = Path(__file__).resolve().parent.parent.parent / "knowledge" / "approved-copy" / "aia-sg-web-copy.jsonl"

#: Which parts of aia.com.sg sound closest to each campaign family.
VOICE_SECTIONS: dict[Family, tuple[str, ...]] = {
    Family.FESTIVE: ("health-wellness", "promotions"),
    Family.RELATIONSHIP: ("health-wellness",),
    Family.APPRECIATION: ("health-wellness",),
    Family.SEMINAR: ("health-wellness", "our-products"),
    Family.EVENT: ("health-wellness", "about-aia"),
    Family.RECRUITMENT: ("about-aia",),
    Family.PERSONAL_BRANDING: ("about-aia", "health-wellness"),
    Family.EDUCATIONAL: ("health-wellness",),
    Family.ACHIEVEMENT: ("about-aia",),
    Family.PRODUCT_PROMOTION: ("our-products",),
}

INSTRUCTIONS = """
You write short marketing copy for an AIA Singapore representative's poster.

AIA's voice is a mentor: compassionate, straightforward, positive, confident, encouraging,
motivating, guiding, on your side. Never harsh, negative, arrogant or pushy.

The five tone principles:
1. Use simple language - short sentences, simple words, no jargon, no acronyms.
2. Speak to the individual - say "you", never "customers are advised".
3. Strengthen with proof - only with facts you were given; never invent evidence.
4. Focus on the future - what this makes possible, not what has gone wrong.
5. Be positive and inclusive - never fear-based, never exclusionary.

Singapore audiences sit in AIA's "Emancipation" cluster: people want to feel achievement and
validation, and to define success on their own terms. Lead with "on your side".

Hard rules:
- Write ONLY the words. Never write a date, time, venue, phone number, email, URL, price,
  percentage or legal line: those are placed automatically from verified data.
- Never promise returns, guarantees or coverage, and never name a product unless the brief does.
- Keep the headline under 60 characters. Write it in sentence case: the design applies
  capitals itself. Do not shout in capitals.
- Always write a sub-headline: one short line that carries the promise under the headline.
- Body copy stays under 40 words, in plain English (Flesch 60+).
- Match the requested tone and the representative's story. Sound like a person, not a brochure.
"""


class CopyDraft(Strict):
    headline: str = Field(max_length=70, description="Under 60 characters; no facts, no dates")
    subheadline: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, max_length=280, description="Max ~40 words")
    cta: str | None = Field(default=None, max_length=30, description="e.g. 'Register now'")
    signature: str | None = Field(default=None, max_length=60)
    social_caption: str | None = Field(default=None, max_length=400)
    alt_text: str | None = Field(default=None, max_length=200, description="Describes the poster for screen readers")
    claims: list[str] = Field(default_factory=list, max_length=4,
                              description="Any statement of fact about a product or benefit")


@lru_cache(maxsize=1)
def _corpus() -> list[dict]:
    if not CORPUS.exists():
        return []
    return [json.loads(line) for line in CORPUS.read_text().splitlines()]


#: Navigation and UI text that is not campaign voice.
_NOISE = re.compile(
    r"^\d|step \d|submit|faq|important notes?|related|more articles|terms|privacy|download|"
    r"^aia [a-z]+ (cover|protect|plan|fund|series|saver|shield)|^our |^find |^contact|^learn|"
    r"click|login|sign up|read more|view all|enquiry",
    re.I,
)


#: Short "AIA Something Something" strings are product names, not voice.
_PRODUCT_NAME = re.compile(r"^AIA(\s+\S+){1,4}$")


def voice_examples(family: Family, *, limit: int = 8, seed: int = 7) -> list[str]:
    """Real AIA Singapore headlines, as a voice reference (not approved campaign wording)."""
    sections = VOICE_SECTIONS.get(family, ("health-wellness",))
    pool = [
        h.strip() for page in _corpus() if page["section"] in sections
        for h in [*(page.get("h1") or []), *(page.get("headings") or [])]
        if 18 <= len(h.strip()) <= 62
        and not _NOISE.search(h)
        and " " in h.strip()
        and len(h.split()) >= 4          # a phrase, not a label
        and not _PRODUCT_NAME.match(h.strip())
    ]
    unique = sorted(set(pool))
    return random.Random(seed).sample(unique, min(limit, len(unique)))


def _prompt(brief: CampaignBrief, profile: AgentProfile, decision: PolicyDecision) -> str:
    story = brief.story
    lines = [
        f"Campaign family: {brief.family.value} ({decision.risk.value} risk)",
        f"Objective: {brief.objective}",
        f"Audience: {brief.audience.primary or 'clients'}"
        + (f", aged {brief.audience.age_range}" if brief.audience.age_range else ""),
        f"Tone asked for: {', '.join(brief.tone) or story.emotional_tone}",
        f"Core message: {story.core_message}",
        f"Representative's angle: {story.agent_angle or 'a trusted adviser'}",
        f"Written by: {profile.display_name}, {profile.title}",
    ]
    if brief.festival:
        lines.append(f"Festival: {brief.festival.replace('_', ' ')}")
    if brief.event:
        lines.append("There is an event. Do NOT write its date, time or venue: they are placed "
                     "automatically. You may refer to it in general terms.")
    if brief.cta:
        lines.append(f"There is a call to action button reading roughly: {brief.cta.text}")
    if story.audience_insight:
        lines.append(f"Audience insight: {story.audience_insight}")
    if story.must_avoid:
        lines.append(f"Must avoid: {', '.join(story.must_avoid)}")
    if profile.preferences.avoid:
        lines.append(f"Representative dislikes: {', '.join(profile.preferences.avoid)}")
    if decision.risk.value != "green":
        lines.append("This is regulated subject matter: make no claim about products, returns or coverage.")

    examples = voice_examples(brief.family)
    if examples:
        lines += ["", "AIA Singapore voice reference (style only, do not copy):",
                  *(f"  - {e}" for e in examples)]
    lang = brief.languages
    if lang.secondary:
        lines.append(f"\nWrite in {lang.primary.value}. A {lang.secondary.value} version is added later; "
                     "keep sentences short enough to translate cleanly.")
    return "\n".join(lines)


async def write_copy(gateway: ModelGateway, brief: CampaignBrief, profile: AgentProfile,
                     decision: PolicyDecision) -> Copy:
    def make(tier):
        return gateway.agent("copywriter", tier=tier, output_type=CopyDraft, instructions=INSTRUCTIONS)

    result = await gateway.run(make("quality"), _prompt(brief, profile, decision),
                               node="copywriter", tier="quality", rebuild=make)
    draft = result.output
    return Copy(
        headline=draft.headline,
        subheadline=draft.subheadline,
        body=draft.body,
        cta=draft.cta or (brief.cta.text if brief.cta else None),
        signature=draft.signature or profile.display_name,
        social_caption=draft.social_caption,
        alt_text=draft.alt_text,
        claims=[Claim(text=c) for c in draft.claims],
    )
