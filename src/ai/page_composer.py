"""The Page Composer: authors one page's markup.

This is the agent that replaces filling a template's slots. It writes real HTML — structure,
nesting, grouping — against the design system's class vocabulary, and it may not write a
single character of text. Every string is a `data-ref` the binder fills from locked data, and
every image is a `data-asset` the binder resolves to an approved file.

It is also the cost driver: one call per page, and a page of markup is long. Everything else
in this pipeline is a single call for the whole run.
"""

from __future__ import annotations

import json

from pydantic import Field

from ..contracts.common import Strict
from ..contracts.content import ContentSet
from ..freeform.contracts import DesignSystem, FreeformPage, PagePlan
from ..freeform.css import CssRule
from ..freeform.html_parse import ALLOWED_TAGS, VOID_TAGS
from ..render.context import RenderContext, UnresolvedReference
from .art_director import CssRuleDraft, to_design_systems  # noqa: F401  (shared draft shape)
from .model_gateway import ModelGateway

INSTRUCTIONS = """
You write the markup for one poster page.

You may not write any text. Not a word, not a number, not a punctuation mark of content.
Every piece of text on the page is placed automatically from verified data. Your markup is
structure only, and every text-bearing element is an EMPTY element carrying a data-ref:

  <h1 class="headline" data-ref="copy.headline"></h1>
  <p class="module-body" data-ref="content.speakers.2.body"></p>

Images work the same way — you never write a src, and you never draw an SVG:

  <img class="logo" data-asset="brand.logo.red">
  <img class="portrait" data-asset="profile.photo.formal">

Rules:
- Use ONLY the classes listed for you. The design system styles exactly those; a class it
  does not style renders unstyled and the page is rejected.
- Use every reference the plan lists, each exactly once. Do not use any other reference.
- Wrap repeating items in a group: <section class="module" data-group="speaker-2">. Groups
  get no id and carry no text themselves.
- Allowed elements only. No script, no svg, no lists, no forms, no style attribute, no id
  attribute, no alt attribute — the binder assigns those.
- Nest properly and close every element.
- Think about the page as a designer would: a clear focal point, a readable order, room to
  breathe, and the legal line legible at the bottom.

Return the markup, plus any page-specific CSS rules you need beyond the design system's.
"""


class FreeformPageDraft(Strict):
    """Flat: markup as a string, CSS as a list. A recursive node model is exactly the shape
    that made Gemini refuse the EditOp union for having too many states."""

    html: str = Field(max_length=40_000)
    rules: list[CssRuleDraft] = Field(default_factory=list, max_length=40)
    notes: str = Field(default="", max_length=200)


def reference_brief(plan: PagePlan, ctx: RenderContext, content: ContentSet) -> str:
    """What each reference will actually contain, so the composer can size its boxes.

    A composer that cannot see that a bio is 140 characters will lay out a box for 40, and
    the repair loop then spends a render shrinking it. Showing the lengths up front is
    cheaper than fixing it afterwards.
    """
    rows = []
    for ref in plan.must_include:
        if ref.startswith(("brand.", "generated.", "profile.photo", "mountains.")):
            rows.append({"ref": ref, "kind": "asset"})
            continue
        try:
            text = ctx.resolve(ref)
        except UnresolvedReference:
            rows.append({"ref": ref, "kind": "text", "chars": 0, "note": "unavailable"})
            continue
        rows.append({"ref": ref, "kind": "text", "chars": len(text),
                     "preview": text[:48] + ("…" if len(text) > 48 else "")})
    return json.dumps(rows, separators=(",", ":"), ensure_ascii=False)


def _prompt(plan: PagePlan, system: DesignSystem, ctx: RenderContext,
            content: ContentSet, canvas_note: str) -> str:
    return "\n".join([
        f"Design system: {system.name} — {system.archetype}, {system.ground} ground, "
        f"{system.type_pairing} type, {system.primary_motif} motif.",
        f"Its rationale: {system.rationale or '(none given)'}",
        "",
        f"Classes you may use: {', '.join(sorted(system.vocabulary))}",
        f"Elements you may use: {', '.join(sorted(ALLOWED_TAGS))} "
        f"(void: {', '.join(sorted(VOID_TAGS))})",
        "",
        f"Page {plan.index}, purpose {plan.purpose}. {canvas_note}",
        "References to place, with the length of what they will contain:",
        reference_brief(plan, ctx, content),
        "",
        "The design system's stylesheet already covers the vocabulary; add a rule only if "
        "this page genuinely needs something the system does not provide.",
    ])


def to_page(draft: FreeformPageDraft, plan: PagePlan) -> tuple[FreeformPage, list[str]]:
    """Build the page contract, dropping any page CSS that is out of bounds."""
    from ..freeform.css import CssError, check_declaration

    rules: list[CssRule] = []
    rejected: list[str] = []
    for rule in draft.rules:
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
        except Exception as exc:  # noqa: BLE001 — reported, never silently kept
            rejected.append(f"{rule.selector}: {type(exc).__name__}")
    return FreeformPage(plan=plan, html=draft.html, rules=rules, notes=draft.notes), rejected


async def compose_page(gateway: ModelGateway, plan: PagePlan, system: DesignSystem,
                       ctx: RenderContext, content: ContentSet, *,
                       canvas_note: str = "") -> tuple[FreeformPage, list[str]]:
    tier = "authoring" if "authoring" in gateway.models else "quality"

    def make(t):
        return gateway.agent("page_composer", tier=t, output_type=FreeformPageDraft,
                             instructions=INSTRUCTIONS)

    result = await gateway.run(make(tier), _prompt(plan, system, ctx, content, canvas_note),
                               node="page_composer", tier=tier, rebuild=make)
    return to_page(result.output, plan)


async def repair_page(gateway: ModelGateway, page: FreeformPage, system: DesignSystem,
                      ctx: RenderContext, content: ContentSet, findings: list,
                      image_path=None) -> tuple[FreeformPage, list[str]]:
    """Hand the composer its own page back, with what went wrong and how it looked.

    Only reached once deterministic repair is exhausted, and only for errors — a warning is
    advice, and spending a model call on advice is how budgets disappear.
    """
    from pydantic_ai import BinaryContent

    tier = "authoring" if "authoring" in gateway.models else "quality"
    agent = gateway.agent("page_composer", tier=tier, output_type=FreeformPageDraft,
                          instructions=INSTRUCTIONS)
    problems = "\n".join(f"  [{f.rule_id}] {f.message}"
                         + (f" ({f.evidence})" if f.evidence else "")
                         + (f" -> {f.suggestion}" if f.suggestion else "")
                         for f in findings)
    text = (f"{_prompt(page.plan, system, ctx, content, '')}\n\n"
            f"You wrote this page:\n{page.html}\n\n"
            f"It was rejected:\n{problems}\n\n"
            "Return a corrected page. Change only what the findings require.")
    prompt = [text]
    if image_path is not None:
        prompt.append(BinaryContent(data=image_path.read_bytes(), media_type="image/png"))
    result = await gateway.run(agent, prompt, node="page_composer", tier=tier)
    return to_page(result.output, page.plan)
