"""The free-form pipeline end to end, with scripted models and no network.

The graph and the plain sequence run the same nodes, so both are exercised here: if the
sequence works and the graph does not, the graph is the problem, which is exactly the
distinction worth being able to make.
"""

from __future__ import annotations

import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.ai.model_gateway import FREEFORM_MODELS, ModelGateway
from src.contracts.common import RunBudget
from src.freeform import fixtures as ff
from src.freeform.graph import run_sequential
from src.policy.rules import decide
from src.render import fixtures as fx

def rules_for(ground: str) -> list[dict]:
    """A real art director writes different colour roles per ground; so does the fixture."""
    return [{"selector": r.selector, "declarations": r.declarations}
            for r in ff.speaker_roster_system(ground).rules]

CONTENT = {
    "headline": "Retirement, on your terms",
    "subheadline": "A practical evening on planning the years you have worked for",
    "body": None, "cta": "Register now", "signature": "Jane Tan",
    "social_caption": None, "alt_text": "Seminar poster", "claims": [],
    "order": [f"speaker-{i}" for i in range(5)], "intro": None,
}

STORYBOARD = {
    "shape": "long_form", "page_count": 1, "purposes": ["invite"],
    "page_refs": ["copy.headline, brand.logo.red, copy.subheadline, "
                  "facts.event.date, facts.event.venue, generated.qr, policy.disclaimer"],
    "rationale": "one page; the roster sets its length",
}


def systems_payload(count: int = 3) -> dict:
    plan = [("a", "speaker-roster", "light", "ring", "cutout"),
            ("b", "benefit-grid", "bold", "pill", "none"),
            ("c", "editorial-feature", "light", "column-rule", "panel"),
            ("d", "chip-index", "light", "hairline-rule", "none")][:count]
    return {"systems": [
        {"variation_id": vid, "name": f"System {vid}", "archetype": arch, "ground": ground,
         "type_pairing": "display-led", "primary_motif": motif, "image_treatment": treat,
         "grid_columns": 12, "custom_classes": ["speaker-ring"],
         "rules": rules_for(ground), "rationale": "distinct"}
        for vid, arch, ground, motif, treat in plan]}


def page_payload(count: int = 5) -> dict:
    return {"html": ff.seminar_page(count).html, "rules": [], "notes": ""}


def scripted_model(page_html: str | None = None, speakers: int = 5) -> FunctionModel:
    """Answers whichever agent is calling, identified by its output schema."""
    def respond(messages, info: AgentInfo) -> ModelResponse:
        schema = json.dumps(info.output_tools[0].parameters_json_schema)
        prompt = " ".join(str(getattr(part, "content", "")) for m in messages
                          for part in getattr(m, "parts", []))
        if "order" in schema and "headline" in schema:
            payload = CONTENT
        elif "page_refs" in schema:
            payload = STORYBOARD
        elif "systems" in schema:
            payload = systems_payload()
        elif "html" in schema:
            ground = "bold" if "bold ground" in prompt else "light"
            payload = {"html": page_html or ff.seminar_page(speakers, ground=ground).html,
                       "rules": [], "notes": ""}
        else:
            payload = {"findings": [], "overall": "fine"}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, payload)])
    return FunctionModel(respond)


@pytest.fixture
def state(brand, profile, tmp_path):
    brief = fx.seminar_brief()
    brief.content = ff.seminar_content()
    return {
        "brief": brief,
        "decision": decide(brief, request_text="career seminar with five speakers"),
        "profile": profile, "brand": brand, "out_dir": tmp_path,
        "variations": [], "notes": [],
    }


def gateway(model) -> ModelGateway:
    return ModelGateway(budget=RunBudget(max_tokens=400_000, max_model_calls=80),
                        models=dict(FREEFORM_MODELS), campaign_id="CAM-TEST", test_model=model)


class TestPipeline:
    @pytest.mark.asyncio
    async def test_the_pipeline_produces_validated_variations(self, state):
        gw = gateway(scripted_model())
        final = await run_sequential(state, gw, variations=3)

        assert len(final["variations"]) == 3, final["notes"]
        for result in final["variations"]:
            assert result.renders, f"{result.variation_id} rendered nothing"
            assert result.ok, [f"{f.rule_id}:{f.element_id}" for f in result.report.errors]
            assert result.poster_path.exists()

    @pytest.mark.asyncio
    async def test_copy_rules_still_run(self, state):
        final = await run_sequential(state, gateway(scripted_model()), variations=3)
        assert final["copy_report"].checks_run > 0

    @pytest.mark.asyncio
    async def test_the_page_length_follows_the_roster(self, state):
        """Three speakers and five speakers cannot produce the same page."""
        short = await run_sequential(state, gateway(scripted_model(speakers=3)), variations=3)
        tall = await run_sequential({**state, "variations": [], "notes": []},
                                    gateway(scripted_model(speakers=5)), variations=3)
        assert (tall["variations"][0].renders[0].canvas.height >
                short["variations"][0].renders[0].canvas.height)

    @pytest.mark.asyncio
    async def test_every_model_call_went_through_the_gateway(self, state):
        gw = gateway(scripted_model())
        await run_sequential(state, gw, variations=3)
        nodes = {record.node for record in gw.usage_log}
        assert {"content_architect", "narrative_planner", "art_director",
                "page_composer"} <= nodes
        assert gw.summary()["calls"] == len(gw.usage_log)

    @pytest.mark.asyncio
    async def test_a_variation_that_fails_does_not_lose_the_others(self, state):
        """One broken page must cost one variation, not the run."""
        broken = '<div class="page"><h1 class="headline">Guaranteed 0.35%</h1></div>'
        gw = gateway(scripted_model(broken))
        final = await run_sequential(state, gw, variations=3)
        assert final["variations"] == [] or all(not v.ok for v in final["variations"])
        assert final["notes"]


class TestGraph:
    """The LangGraph wiring, exercised only if langgraph is installed."""

    @pytest.mark.asyncio
    async def test_the_graph_runs_the_same_nodes(self, state):
        pytest.importorskip("langgraph")
        from src.freeform.graph import run_graph

        final = await run_graph(state, gateway(scripted_model()), variations=3)
        assert len(final["variations"]) == 3
        assert all(v.renders for v in final["variations"])

    def test_the_graph_compiles_with_a_fan_out_per_variation(self):
        pytest.importorskip("langgraph")
        from src.freeform.graph import build_graph

        compiled = build_graph(gateway(scripted_model()), variations=4)
        nodes = compiled.get_graph().nodes
        assert {"content", "narrative", "art_direction", "variation"} <= set(nodes)
