"""Campaign brief — the output of the Brief Agent (BRD §14, FR-006..FR-010)."""

from __future__ import annotations

import datetime as dt
from enum import StrEnum

from pydantic import Field, model_validator

from .common import Assumption, Family, Fact, Language, Risk, Strict


class IntendedUse(StrEnum):
    IDENTITY = "identity"
    FACT_SOURCE = "fact_source"
    DESIGN_REFERENCE = "design_reference"
    CAMPAIGN_IMAGERY = "campaign_imagery"
    INFORMATION_SOURCE = "information_source"
    CTA_SOURCE = "cta_source"
    UNKNOWN = "unknown"


class ArtifactRecord(Strict):
    """A campaign upload, classified by how it may be used (BRD §17)."""

    id: str
    uri: str
    mime: str
    intended_use: IntendedUse = IntendedUse.UNKNOWN
    extracted_facts: list[Fact] = Field(default_factory=list)
    summary: str | None = None
    notes: str | None = None


class Audience(Strict):
    primary: str | None = None
    age_range: str | None = None
    notes: str | None = None


class EventDetails(Strict):
    title: str | None = None
    date: dt.date | None = None
    time_start: dt.time | None = None
    time_end: dt.time | None = None
    venue: str | None = None
    speakers: list[str] = Field(default_factory=list)


class CallToAction(Strict):
    text: str
    url: str | None = None
    url_verified: bool = False


class Story(Strict):
    """Why this campaign exists, in the agent's voice. Feeds Copywriter and Creative Director."""

    core_message: str
    emotional_tone: str
    audience_insight: str | None = None
    agent_angle: str | None = None
    must_avoid: list[str] = Field(default_factory=list)


class AgentRef(Strict):
    profile_id: str
    photo_id: str | None = None


class Languages(Strict):
    primary: Language = Language.EN
    secondary: Language | None = None


class CampaignBrief(Strict):
    campaign_id: str
    family: Family
    objective: str
    audience: Audience = Field(default_factory=Audience)
    tone: list[str] = Field(default_factory=list)
    festival: str | None = None
    languages: Languages = Field(default_factory=Languages)
    event: EventDetails | None = None
    cta: CallToAction | None = None
    agent: AgentRef
    story: Story
    facts: list[Fact] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    risk_proposed: Risk = Field(default=Risk.GREEN, description="Agent's view; the policy engine decides")
    product_promotion: bool = False
    variation_count: int = Field(default=4, ge=1, le=6)
    brief_version: int = 1

    @model_validator(mode="after")
    def _event_family_needs_event(self) -> CampaignBrief:
        if self.family in {Family.SEMINAR, Family.EVENT, Family.RECRUITMENT} and self.event is None:
            raise ValueError(f"{self.family} brief requires event details")
        return self

    def fact(self, field: str) -> Fact | None:
        return next((f for f in self.facts if f.field == field), None)

    def fact_map(self) -> dict[str, object]:
        return {f.field: f.value for f in self.facts}

    def is_ready(self) -> bool:
        return not self.missing_fields
