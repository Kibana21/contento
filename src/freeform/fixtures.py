"""Hand-authored pages, standing in for the Page Composer.

These are what the whole engine is exercised with offline: real markup in the accepted
subset, real design-system CSS, real content — and no model call anywhere. If the fixtures
bind, render, audit and validate, the governance layer works, and the agents that come later
are a cost and quality problem rather than a correctness one.

The speaker roster mirrors the AIA Career Seminar reference: a page whose length is set by
how many speakers there are, which is precisely what the structured engine cannot express.
"""

from __future__ import annotations

from ..contracts.content import ContentItem, ContentSet
from .contracts import DesignSystem, FreeformPage, PagePlan
from .css import CssRule

#: Names and roles stand in for an uploaded agenda; `source` says where they came from.
SPEAKERS = [
    ("Wong Sze Keed", "CEO of AIA Singapore",
     "Sharing the importance of insurance and what this career offers our consultants."),
    ("Rachel Lim", "Co-founder of Love, Bonito",
     "On the skills and temperament needed to succeed as an entrepreneur and consultant."),
    ("Torres Dalaine Ong", "Mid-career switcher",
     "Previously from the technology industry."),
    ("Nur Aisyah Zainudin", "Mid-career switcher",
     "Previously an air stewardess."),
    ("Mohamad Aiman Haziq", "Fresh from national service",
     "On starting a financial services career early."),
]


def seminar_content() -> ContentSet:
    return ContentSet(items=[
        ContentItem(id=f"speaker-{i}", kind="speaker", label=name, role=role, body=bio,
                    source="artifact:speakers", verbatim=True)
        for i, (name, role, bio) in enumerate(SPEAKERS)
    ])


def speaker_roster_system() -> DesignSystem:
    """Reference brochure 2's language: a ring around each portrait, a red pill for the role."""
    return DesignSystem(
        variation_id="a",
        name="Speaker roster",
        archetype="speaker-roster",
        ground="light",
        type_pairing="display-led",
        primary_motif="ring",
        image_treatment="cutout",
        custom_classes=["speaker-ring"],
        rationale="Portraits lead; each speaker gets equal billing down a single column.",
        rules=[
            CssRule(selector=".page", declarations={
                "display": "flex", "flex-direction": "column", "gap": "48px",
                "padding": "64px"}),
            CssRule(selector=".band", declarations={
                "display": "flex", "align-items": "center", "justify-content": "space-between"}),
            CssRule(selector=".logo", declarations={"height": "76px"}),
            CssRule(selector=".headline", declarations={
                "font-size": "90px", "line-height": "1.02", "letter-spacing": "-0.018em",
                "text-transform": "uppercase", "color": "var(--red)", "font-weight": "700"}),
            CssRule(selector=".subheadline", declarations={
                "font-size": "30px", "line-height": "1.2", "color": "var(--charcoal)"}),
            CssRule(selector=".stack", declarations={
                "display": "flex", "flex-direction": "column", "gap": "32px"}),
            CssRule(selector=".module", declarations={
                "display": "grid", "grid-template-columns": "240px 1fr", "gap": "32px",
                "align-items": "center"}),
            CssRule(selector=".module + .module", declarations={
                "border-top": "1px solid var(--charcoal-20)", "padding-top": "32px"}),
            CssRule(selector=".speaker-ring", declarations={
                "width": "220px", "height": "220px", "border-radius": "50%",
                "border": "3px solid var(--red)", "object-fit": "cover",
                "object-position": "top center"}),
            CssRule(selector=".module-role", declarations={
                # align-self stops the flex column stretching the pill to full width
                "display": "inline-block", "align-self": "flex-start",
                "background": "var(--red)", "color": "var(--white)",
                "border-radius": "999px", "padding": "6px 20px", "font-size": "22px",
                "text-transform": "uppercase", "letter-spacing": "0.04em"}),
            CssRule(selector=".module-label", declarations={
                "font-size": "38px", "font-weight": "700", "color": "var(--charcoal)"}),
            CssRule(selector=".module-body", declarations={
                "font-size": "24px", "line-height": "1.45", "color": "var(--charcoal-80)"}),
            CssRule(selector=".detail-row", declarations={
                "display": "flex", "gap": "16px", "align-items": "center",
                "font-size": "28px", "color": "var(--charcoal)"}),
            CssRule(selector=".row", declarations={
                "display": "flex", "gap": "40px", "align-items": "flex-end",
                "justify-content": "space-between"}),
            CssRule(selector=".qr", declarations={"width": "150px"}),
            # charcoal-60 on white is 3.49:1 — the exact contrast defect recorded in
            # docs/architecture.md §18. The legal line needs charcoal-80 (6.1:1).
            CssRule(selector=".legal", declarations={
                "font-size": "15px", "line-height": "1.3", "color": "var(--charcoal-80)",
                "max-width": "620px"}),
        ],
    )


def _speaker_module(index: int) -> str:
    return (
        f'<section class="module">'
        f'<img class="speaker-ring" data-asset="content.speakers.{index}.photo">'
        f'<div class="stack">'
        f'<span class="module-role" data-ref="content.speakers.{index}.role"></span>'
        f'<h3 class="module-label" data-ref="content.speakers.{index}.label"></h3>'
        f'<p class="module-body" data-ref="content.speakers.{index}.body"></p>'
        f"</div></section>"
    )


def seminar_plan(count: int = 5) -> PagePlan:
    refs = ["copy.headline", "brand.logo.red", "copy.subheadline",
            "facts.event.date", "facts.event.venue", "generated.qr", "policy.disclaimer"]
    for i in range(count):
        refs += [f"content.speakers.{i}.role", f"content.speakers.{i}.label",
                 f"content.speakers.{i}.body"]
    return PagePlan(index=1, purpose="invite", shape="long_form",
                    preset="instagram_portrait", must_include=refs)


def seminar_page(count: int = 5, *, with_photos: bool = False) -> FreeformPage:
    """The page grows with the roster — which is the whole point of this engine."""
    modules = "".join(
        _speaker_module(i) if with_photos
        else _speaker_module(i).replace(
            f'<img class="speaker-ring" data-asset="content.speakers.{i}.photo">',
            '<div class="speaker-ring"></div>')
        for i in range(count)
    )
    html = f"""
    <div class="page">
      <div class="band"><img class="logo" data-asset="brand.logo.red"></div>
      <div class="stack">
        <h1 class="headline" data-ref="copy.headline"></h1>
        <p class="subheadline" data-ref="copy.subheadline"></p>
      </div>
      <div class="stack">{modules}</div>
      <div class="stack">
        <div class="detail-row" data-ref="facts.event.date"></div>
        <div class="detail-row" data-ref="facts.event.venue"></div>
      </div>
      <div class="row">
        <p class="legal" data-ref="policy.disclaimer"></p>
        <img class="qr" data-asset="generated.qr">
      </div>
    </div>
    """
    return FreeformPage(plan=seminar_plan(count), html=html)
