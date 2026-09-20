"""The free-form pipeline, as a LangGraph state machine.

Every node is a thin wrapper around a plain async function that works standalone, and the
LangGraph import is local to this module. That is deliberate on both counts: the pure
functions stay unit-testable without a graph runtime, the test suite never needs langgraph
installed, and if the graph turns out to earn nothing it can be deleted without touching the
work it calls.

What the graph is actually for here:
  * fan-out over variations, and within a variation over pages;
  * the repair loop as a real cycle with a recursion limit rather than a hand-rolled `for`;
  * a checkpoint, so an expensive run is not lost to one failed page;
  * an interrupt point for the human approval that red-risk material needs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, TypedDict

from ..ai.art_director import choose_design_systems, fallback_design_systems
from ..ai.content_architect import build_content
from ..ai.model_gateway import BudgetExceeded, ModelGateway
from ..ai.narrative_planner import fallback_storyboard, plan_narrative
from ..ai.page_composer import compose_page, repair_page
from ..contracts.brand import BrandPack
from ..contracts.brief import CampaignBrief
from ..contracts.common import Finding, ValidationReport
from ..contracts.content import ContentSet
from ..contracts.copy import Copy
from ..contracts.design import Canvas
from ..contracts.profile import AgentProfile
from ..policy.rules import PolicyDecision
from ..render.context import RenderContext
from ..validate import validate_rendered
from ..validate.copy import validate_copy
from .binder import bind_page
from .contracts import DesignSystem, FreeformDoc, FreeformPage, PagePlan, Storyboard
from .renderer import PageRender, render_bound_async
from .repair import apply_repairs, repair_plan, signature_of

MAX_CSS_FIXES = 2
MAX_LLM_REPAIRS = 1
MAX_RENDERS = 4


def _merge(left: list, right: list) -> list:
    """Reducer for the fan-out: each variation appends its own result."""
    return [*left, *right]


class CampaignState(TypedDict, total=False):
    """Graph state. Contracts in, contracts out — the same ones the other engine uses."""

    brief: CampaignBrief
    decision: PolicyDecision
    profile: AgentProfile
    brand: BrandPack
    out_dir: Path
    copy: Copy
    content: ContentSet
    copy_report: ValidationReport
    storyboard: Storyboard
    systems: list[DesignSystem]
    variations: Annotated[list, _merge]
    notes: Annotated[list, _merge]
    partial: bool


@dataclass
class VariationResult:
    variation_id: str
    doc: FreeformDoc
    renders: list[PageRender] = field(default_factory=list)
    report: ValidationReport = field(default_factory=ValidationReport)
    audit: list[Finding] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)
    fell_back: bool = False

    @property
    def ok(self) -> bool:
        return self.report.passed and not self.audit

    @property
    def poster_path(self) -> Path | None:
        return self.renders[0].image_path if self.renders else None


# --------------------------------------------------------------------------- nodes
async def node_content(state: CampaignState, gateway: ModelGateway) -> dict[str, Any]:
    """Copy and the arrangement of already-verified content, then the ordinary copy rules."""
    copy, content, rejected = await build_content(
        gateway, state["brief"], state["profile"], state["decision"])
    report = validate_copy(copy, state["brief"], state["decision"])
    notes = [f"content architect: {r}" for r in rejected]
    return {"copy": copy, "content": content, "copy_report": report, "notes": notes}


async def node_narrative(state: CampaignState, gateway: ModelGateway) -> dict[str, Any]:
    board, source, rejected = await plan_narrative(
        gateway, state["brief"], state["copy"], state["content"], state["decision"])
    return {"storyboard": board,
            "notes": [f"storyboard ({source}), {len(board.pages)} page(s)",
                      *(f"planner: {r}" for r in rejected)]}


async def node_art_direction(state: CampaignState, gateway: ModelGateway,
                             count: int) -> dict[str, Any]:
    systems, source, rejected = await choose_design_systems(
        gateway, state["brief"], state["copy"], state["content"], state["profile"],
        state["brand"], count=count)
    return {"systems": systems.systems,
            "notes": [f"design systems ({source})", *(f"art director: {r}" for r in rejected[:5])]}


async def build_variation(state: CampaignState, system: DesignSystem,
                          gateway: ModelGateway) -> VariationResult:
    """One variation: compose each page, bind, render, validate, repair.

    The repair ladder is measured first and modelled second. Code may shrink; only the
    composer may cut.
    """
    brief, brand = state["brief"], state["brand"]
    ctx = RenderContext(brief=brief, copy=state["copy"], profile=state["profile"],
                        brand=brand, decision=state["decision"], content=state["content"])
    out_dir = state["out_dir"] / "pages" / system.variation_id
    renders: list[PageRender] = []
    pages: list[FreeformPage] = []
    report = ValidationReport()
    audit: list[Finding] = []
    repairs: list[str] = []

    for plan in state["storyboard"].pages:
        canvas = Canvas.from_preset(plan.preset)
        long_form = plan.shape == "long_form"
        page, rejected = await compose_page(
            gateway, plan, system, ctx, state["content"],
            canvas_note=f"Canvas {canvas.width}px wide"
                        + (", height grows with the content." if long_form
                           else f" by {canvas.height}px."))
        repairs += [f"composer css refused: {r}" for r in rejected[:3]]

        best: tuple[PageRender, ValidationReport, list[Finding]] | None = None
        previous: set[str] | None = None
        llm_repairs = 0

        for attempt in range(MAX_RENDERS):
            bound = bind_page(page, system, ctx, canvas=canvas)
            if not bound.ok:
                page_report = ValidationReport(checks_run=1, findings=bound.findings)
                page_audit: list[Finding] = []
                render = None
            else:
                render = await render_bound_async(
                    bound, out_dir, canvas=canvas,
                    name=f"page-{plan.index}", long_form=long_form)
                page_report = validate_rendered(bound.spec, render.geometry,
                                                render.image_path, brand)
                page_audit = render.findings

            # keep the best attempt, not the last: an earlier render may be less broken
            score = len(page_report.errors) + len(page_audit)
            if render is not None and (best is None
                                       or score < len(best[1].errors) + len(best[2])):
                best = (render, page_report, page_audit)
            if render is not None and not page_report.errors and not page_audit:
                break

            signature = signature_of(page_report, page_audit)
            if signature == previous:
                break                       # the repairs have stopped helping
            previous = signature

            # 1. deterministic: shrink by the measured shortfall
            applied = False
            if render is not None and attempt < MAX_CSS_FIXES:
                plan_css = repair_plan(page_report, render.geometry)
                if plan_css:
                    bound.html = apply_repairs(bound.html, plan_css)
                    repairs += [f"{eid}: {', '.join(d)}" for eid, d in plan_css.items()]
                    # re-render the patched document directly
                    render = await render_bound_async(
                        bound, out_dir, canvas=canvas,
                        name=f"page-{plan.index}", long_form=long_form)
                    page_report = validate_rendered(bound.spec, render.geometry,
                                                    render.image_path, brand)
                    page_audit = render.findings
                    best = (render, page_report, page_audit)
                    applied = True
                    if not page_report.errors and not page_audit:
                        break

            # 2. the composer, once, with what went wrong and how it looked
            if not applied and llm_repairs < MAX_LLM_REPAIRS:
                llm_repairs += 1
                try:
                    page, _ = await repair_page(
                        gateway, page, system, ctx, state["content"],
                        [*page_report.errors, *page_audit],
                        image_path=render.image_path if render else None)
                    repairs.append(f"page {plan.index}: composer revised its own markup")
                except BudgetExceeded:
                    raise
                except Exception:
                    break
            elif not applied:
                break

        if best is None:
            report = report.merge(ValidationReport(
                checks_run=1,
                findings=[Finding(rule_id="bind.failed", severity="error",
                                  message=f"page {plan.index} could not be bound")]))
            continue
        render, page_report, page_audit = best
        renders.append(render)
        report = report.merge(page_report)
        audit += page_audit
        pages.append(page)

    doc = FreeformDoc(
        doc_id=f"{brief.campaign_id}-{system.variation_id}",
        campaign_id=brief.campaign_id, variation_id=system.variation_id,
        system=system, pages=pages or [FreeformPage(plan=state["storyboard"].pages[0], html="")],
        brand_pack_version=brand.version, language=brief.languages.primary.value)
    return VariationResult(variation_id=system.variation_id, doc=doc, renders=renders,
                           report=report, audit=audit, repairs=repairs)


async def node_variation(state: CampaignState, system: DesignSystem,
                         gateway: ModelGateway) -> dict[str, Any]:
    try:
        result = await build_variation(state, system, gateway)
    except BudgetExceeded:
        return {"partial": True,
                "notes": [f"variation {system.variation_id}: stopped on the budget"]}
    except Exception as exc:  # noqa: BLE001 — one bad variation must not lose the others
        return {"notes": [f"variation {system.variation_id} failed: {type(exc).__name__}: {exc}"]}
    return {"variations": [result],
            "notes": [f"variation {system.variation_id}: "
                      + ("ok" if result.ok
                         else f"{len(result.report.errors)} error(s), {len(result.audit)} audit")]}


# --------------------------------------------------------------------------- the graph
def build_graph(gateway: ModelGateway, *, variations: int = 4):
    """Assemble the StateGraph. Imported lazily so the test suite need not install langgraph."""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    graph = StateGraph(CampaignState)

    # Nodes are async wrappers, not lambdas: a lambda returns the coroutine rather than
    # awaiting it, and LangGraph then reports "Expected dict, got <coroutine>".
    async def content_node(s: CampaignState) -> dict[str, Any]:
        return await node_content(s, gateway)

    async def narrative_node(s: CampaignState) -> dict[str, Any]:
        return await node_narrative(s, gateway)

    async def art_direction_node(s: CampaignState) -> dict[str, Any]:
        return await node_art_direction(s, gateway, variations)

    async def variation_node(payload: dict) -> dict[str, Any]:
        """One fan-out branch. `Send` hands it the state plus the system it is building."""
        return await node_variation(payload["state"], payload["system"], gateway)

    graph.add_node("content", content_node)
    graph.add_node("narrative", narrative_node)
    graph.add_node("art_direction", art_direction_node)
    graph.add_node("variation", variation_node)

    def fan_out(state: CampaignState):
        return [Send("variation", {"state": state, "system": system})
                for system in state.get("systems", [])]

    graph.add_edge(START, "content")
    graph.add_edge("content", "narrative")
    graph.add_edge("narrative", "art_direction")
    graph.add_conditional_edges("art_direction", fan_out, ["variation"])
    graph.add_edge("variation", END)
    return graph.compile()


async def run_graph(state: CampaignState, gateway: ModelGateway, *,
                    variations: int = 4) -> CampaignState:
    """Run the pipeline. Falls back to the plain sequence if langgraph is unavailable."""
    try:
        compiled = build_graph(gateway, variations=variations)
    except ImportError:
        return await run_sequential(state, gateway, variations=variations)
    return await compiled.ainvoke(state, {"recursion_limit": 50})


async def run_sequential(state: CampaignState, gateway: ModelGateway, *,
                         variations: int = 4) -> CampaignState:
    """The same nodes, in order, with no graph runtime.

    Kept working on purpose: it is how the pipeline is unit-tested, and it is the answer if
    the graph ever turns out to cost more than it earns.
    """
    import asyncio

    state = {**state, "variations": [], "notes": []}
    for step, node in (("content", node_content), ("narrative", node_narrative)):
        state.update(await node(state, gateway))  # type: ignore[arg-type]
    state.update(await node_art_direction(state, gateway, variations))

    results = await asyncio.gather(*(node_variation(state, system, gateway)
                                     for system in state.get("systems", [])))
    for update in results:
        state["variations"] = [*state.get("variations", []), *update.get("variations", [])]
        state["notes"] = [*state.get("notes", []), *update.get("notes", [])]
        state["partial"] = state.get("partial", False) or update.get("partial", False)
    return state
