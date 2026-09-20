"""Hand-built design documents used by tests and the renderer spike."""

from __future__ import annotations

import datetime as dt

from ..contracts.brief import (AgentRef, CallToAction, CampaignBrief, EventDetails, Story)
from ..contracts.common import Family, Fact, Risk
from ..contracts.copy import Copy
from ..contracts.creative import MountainsVariant, RedApplication
from ..contracts.design import Background, Canvas, DesignDoc, Element, ElementType


def _profile_facts() -> list[Fact]:
    """The verified contact facts the Brief Agent copies from the profile."""
    return [Fact(field="agent.name", value="Jane Tan", source="profile"),
            Fact(field="agent.title", value="Financial Services Consultant", source="profile"),
            Fact(field="agent.agency", value="Horizon Wealth Advisory", source="profile"),
            Fact(field="agent.mobile", value="+65 9123 4567", source="profile"),
            Fact(field="agent.email", value="jane.tan@example.com", source="profile"),
            Fact(field="agent.url", value="https://example.com/jane-tan", source="profile")]


def festive_brief() -> CampaignBrief:
    return CampaignBrief(
        campaign_id="CAM-2026-000001",
        family=Family.FESTIVE,
        objective="relationship",
        tone=["warm", "elegant", "premium"],
        festival="deepavali",
        agent=AgentRef(profile_id="demo-agent", photo_id="formal"),
        story=Story(core_message="Warm Deepavali wishes to my clients",
                    emotional_tone="warm, celebratory, unhurried",
                    audience_insight="Clients value a personal note, not a sales message",
                    agent_angle="A trusted guide who remembers the people behind the policies",
                    must_avoid=["product claims", "urgency"]),
        facts=[*_profile_facts()],
        risk_proposed=Risk.GREEN,
    )


def seminar_brief() -> CampaignBrief:
    return CampaignBrief(
        campaign_id="CAM-2026-000002",
        family=Family.SEMINAR,
        objective="lead_generation",
        tone=["premium", "confident", "approachable"],
        agent=AgentRef(profile_id="demo-agent", photo_id="formal"),
        story=Story(core_message="Retirement you define yourself, planned with confidence",
                    emotional_tone="reassuring, optimistic",
                    audience_insight="Mid-career professionals who feel behind on planning",
                    agent_angle="An approachable guide, not a salesperson",
                    must_avoid=["return figures", "product names", "fear-based urgency"]),
        event=EventDetails(title="Retirement Planning Seminar", date=dt.date(2026, 10, 18),
                           time_start=dt.time(19, 0), time_end=dt.time(21, 0),
                           venue="Marina Bay Sands, Expo Hall 3"),
        cta=CallToAction(text="Register now", url="https://example.com/jane-tan/events", url_verified=True),
        facts=[*_profile_facts(),
               Fact(field="event.date", value=dt.date(2026, 10, 18), source="user"),
               Fact(field="event.time_start", value=dt.time(19, 0), source="artifact:agenda"),
               Fact(field="event.venue", value="Marina Bay Sands, Expo Hall 3", source="artifact:agenda"),
               Fact(field="cta.url", value="https://example.com/jane-tan/events", source="user")],
        risk_proposed=Risk.AMBER,
    )


def festive_copy() -> Copy:
    return Copy(
        headline="Wishing you a\njoyous Deepavali",
        subheadline="May the festival of lights bring warmth to your home",
        body="It is a privilege to walk alongside you and your family, this year and the next.",
        signature="Jane Tan",
    )


def seminar_copy() -> Copy:
    return Copy(
        headline="Retirement,\non your terms",
        subheadline="A practical evening on planning the years you have worked for",
        cta="Register now",
    )


def festive_design(preset: str = "instagram_portrait") -> DesignDoc:
    return DesignDoc(
        design_id="festive-a", campaign_id="CAM-2026-000001", direction_id="a",
        canvas=Canvas.from_preset(preset), layout_family="festive-portrait",
        theme=RedApplication.HIGHLIGHT, mountains=MountainsVariant.CORE_3,
        background=Background(kind="solid", colour_token="core.white"),
        elements=[
            Element(id="logo", type=ElementType.LOGO, slot="logo", asset_ref="brand.logo.red"),
            Element(id="mountains", type=ElementType.MOUNTAINS, slot="background-graphic",
                    overrides={"shape_set": "classic_3", "height": 660, "width": 1080,
                               "position": "inset:auto 0 0 0;"}),
            Element(id="headline", type=ElementType.HEADLINE, slot="headline",
                    content_ref="copy.headline", style_token="headline"),
            Element(id="subheadline", type=ElementType.SUBHEADLINE, slot="message",
                    content_ref="copy.subheadline", style_token="subheading"),
            Element(id="body", type=ElementType.BODY, slot="message",
                    content_ref="copy.body", style_token="body", overrides={"width": 560}),
            Element(id="portrait", type=ElementType.AGENT_PHOTO, slot="portrait",
                    asset_ref="profile.photos.formal", overrides={"width": 470, "height": 760}),
            Element(id="contact", type=ElementType.CONTACT_BLOCK, slot="contact", style_token="detail"),
            Element(id="qr", type=ElementType.QR, slot="qr", asset_ref="generated.qr"),
        ],
    )


def seminar_design(preset: str = "instagram_portrait") -> DesignDoc:
    return DesignDoc(
        design_id="seminar-c", campaign_id="CAM-2026-000002", direction_id="c",
        canvas=Canvas.from_preset(preset), layout_family="event-information",
        theme=RedApplication.HIGHLIGHT, mountains=MountainsVariant.CORE_4,
        background=Background(kind="solid", colour_token="core.charcoal.20"),
        elements=[
            Element(id="logo", type=ElementType.LOGO, slot="logo", asset_ref="brand.logo.red"),
            Element(id="mountains", type=ElementType.MOUNTAINS, slot="background-graphic",
                    overrides={"shape_set": "classic_4", "height": 560, "position": "inset:auto 0 0 0;"}),
            Element(id="headline", type=ElementType.HEADLINE, slot="headline",
                    content_ref="copy.headline", style_token="headline"),
            Element(id="subheadline", type=ElementType.SUBHEADLINE, slot="subheadline",
                    content_ref="copy.subheadline", style_token="subheading"),
            Element(id="event-date", type=ElementType.FACT, slot="details",
                    content_ref="facts.event.date", style_token="detail"),
            Element(id="event-time", type=ElementType.FACT, slot="details",
                    content_ref="facts.event.time_start", style_token="detail"),
            Element(id="event-venue", type=ElementType.FACT, slot="details",
                    content_ref="facts.event.venue", style_token="detail"),
            Element(id="portrait", type=ElementType.AGENT_PHOTO, slot="portrait",
                    asset_ref="profile.photos.formal", overrides={"width": 240, "height": 240}),
            Element(id="contact", type=ElementType.CONTACT_BLOCK, slot="contact", style_token="detail"),
            Element(id="cta", type=ElementType.CTA, slot="cta", content_ref="copy.cta", style_token="detail"),
            Element(id="qr", type=ElementType.QR, slot="qr", asset_ref="generated.qr"),
        ],
    )
