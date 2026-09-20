"""The free-form campaign folder: folders in, posters and lineage out.

The folder has to answer "how was this made?" the same way whichever engine produced it, so
these tests check the shape as much as the contents.
"""

from __future__ import annotations

import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.contracts.common import RunBudget
from src.freeform import fixtures as ff
from src.freeform.pipeline import create_freeform_campaign
from src.lineage.record import read_metadata
from tests.test_freeform_graph import CONTENT, STORYBOARD, rules_for, systems_payload

AGENDA = """AIA Career Seminar — Speakers

Wong Sze Keed, CEO of AIA Singapore
Sharing the importance of insurance and what this career offers our consultants.

Rachel Lim, Co-founder of Love, Bonito
On the skills and temperament needed to succeed as an entrepreneur and consultant.

Venue: Marina Bay Sands, Expo Hall 3
Date: 18 October 2026, 7pm
Registration: https://example.com/jane-tan/events
"""

BRIEF = {
    "family": "seminar", "objective": "lead_generation",
    "tone": ["confident", "approachable"], "festival": None,
    "story": {"core_message": "A career worth switching for", "emotional_tone": "aspirational",
              "audience_insight": None, "agent_angle": None, "must_avoid": []},
    "photo_id": "formal", "facts": [], "assumptions": [], "missing_fields": [],
    "risk_proposed": "amber", "product_promotion": False, "variation_count": 3,
    "audience": {"primary": "mid-career professionals", "age_range": "30-45", "notes": None},
    "languages": {"primary": "en", "secondary": None},
    "event": {"title": "AIA Career Seminar", "date": "2026-10-18", "time_start": "19:00:00",
              "time_end": None, "venue": "Marina Bay Sands, Expo Hall 3", "speakers": []},
    "cta": {"text": "Register now", "url": "https://example.com/jane-tan/events"},
}


@pytest.fixture
def campaign(tmp_path):
    folder = tmp_path / "career-seminar"
    (folder / "assets").mkdir(parents=True)
    (folder / "request.md").write_text(
        "# Campaign Request\nAIA Career Seminar on 18 October, 7pm at Marina Bay Sands.\n"
        "Speakers are in the attached agenda. Make it aspirational.\n")
    (folder / "assets" / "agenda.txt").write_text(AGENDA)
    return folder


def scripted() -> FunctionModel:
    """Answers each agent by its output schema, and runs the extract_modules tool once."""
    state = {"extracted": False}

    def respond(messages, info: AgentInfo) -> ModelResponse:
        schema = json.dumps(info.output_tools[0].parameters_json_schema)
        prompt = " ".join(str(getattr(p, "content", "")) for m in messages
                          for p in getattr(m, "parts", []))
        if "intended_use" in schema:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
                "intended_use": "information_source", "summary": "speaker agenda",
                "extracted_facts": [], "contains_instructions": False})])
        if "core_message" in schema:
            if not state["extracted"] and any(t.name == "extract_modules"
                                              for t in info.function_tools):
                state["extracted"] = True
                return ModelResponse(parts=[ToolCallPart("extract_modules", {
                    "artifact_id": "agenda", "kind": "speaker",
                    "items": [
                        {"label": "Wong Sze Keed", "role": "CEO of AIA Singapore",
                         "body": "Sharing the importance of insurance"},
                        {"label": "Rachel Lim", "role": "Co-founder of Love, Bonito",
                         "body": "On the skills and temperament needed to succeed"},
                        # not in the agenda: must be refused
                        {"label": "Kevin Tan", "role": "Regional Director"},
                    ]})])
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, BRIEF)])
        if "order" in schema and "headline" in schema:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
                                                     {**CONTENT, "order": ["speaker-0", "speaker-1"]})])
        if "page_refs" in schema:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, STORYBOARD)])
        if "systems" in schema:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
                                                     systems_payload(2))])
        if "html" in schema:
            ground = "bold" if "bold ground" in prompt else "light"
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
                "html": ff.seminar_page(2, ground=ground).html, "rules": [], "notes": ""})])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
                                                 {"findings": [], "overall": "fine"})])
    return FunctionModel(respond)


@pytest.fixture
def run(campaign, tmp_path, monkeypatch):
    async def go(**kw):
        from src.ai import model_gateway as mg

        original = mg.ModelGateway.resolve
        monkeypatch.setattr(mg.ModelGateway, "resolve",
                            lambda self, tier: self.test_model or original(self, tier))
        return await create_freeform_campaign(
            "profiles/demo-agent", campaign, out_root=tmp_path / "out",
            variations=2, interactive=False, visual_review=False,
            budget=RunBudget(max_tokens=400_000, max_model_calls=80), **kw)
    return go


class TestCampaignFolder:
    @pytest.mark.asyncio
    async def test_it_writes_a_self_contained_folder(self, run, monkeypatch):
        from src.ai import model_gateway as mg
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted())

        result = await run()
        assert result.ok, result.summary()
        out = result.out_dir
        for name in ("campaign.json", "brief.json", "copy.json", "policy.json",
                     "content.json", "usage.json"):
            assert (out / name).exists(), name
        assert (out / "validation" / "copy.json").exists()
        assert len(list(out.glob("variation-*.png"))) == 2
        assert len(list((out / "designs").glob("*.json"))) == 2

    @pytest.mark.asyncio
    async def test_lineage_records_every_page_and_its_source(self, run, monkeypatch):
        from src.ai import model_gateway as mg
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted())

        result = await run()
        record = json.loads((result.out_dir / "campaign.json").read_text())
        # the structured engine's 1:1 shape is preserved
        assert len(record["variations"]) == len(record["exports"]) == 2
        for export in record["exports"]:
            assert export["page_count"] >= 1 and export["pages"]
            assert all(len(p["sha256_16"]) == 16 for p in export["pages"])
        for variation in record["variations"]:
            assert variation["engine"] == "freeform"
            assert variation["design_system"]["rules"]

    @pytest.mark.asyncio
    async def test_an_invented_speaker_never_reaches_the_campaign(self, run, monkeypatch):
        """The agenda has two speakers; the model also proposed a third that is not in it."""
        from src.ai import model_gateway as mg
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted())

        result = await run()
        labels = {i.label for i in result.content.items}
        assert labels == {"Wong Sze Keed", "Rachel Lim"}
        assert "Kevin Tan" not in json.dumps(json.loads(
            (result.out_dir / "content.json").read_text()))
        assert all(i.source == "artifact:agenda" for i in result.content.items)

    @pytest.mark.asyncio
    async def test_provenance_is_embedded_in_the_poster(self, run, monkeypatch):
        from src.ai import model_gateway as mg
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted())

        result = await run()
        stamp = read_metadata(result.out_dir / "variation-a.png")
        assert stamp["CampaignID"] == result.campaign_id
        assert stamp["Risk"] == "amber" and stamp["LineageFile"] == "campaign.json"

    @pytest.mark.asyncio
    async def test_the_sequential_path_produces_the_same_folder(self, run, monkeypatch):
        from src.ai import model_gateway as mg
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted())

        result = await run(use_graph=False)
        assert result.ok and len(result.variations) == 2
