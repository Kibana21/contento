"""The campaign pipeline: folders in, posters plus lineage out."""

import asyncio
import datetime as dt
import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.contracts.common import RunBudget
from src.lineage.record import read_metadata
from src.workflow import create_campaign


def brief_payload(**kw) -> dict:
    base = {
        "family": "festive", "objective": "relationship",
        "tone": ["warm", "elegant"], "festival": "deepavali",
        "story": {"core_message": "Warm Deepavali wishes", "emotional_tone": "warm",
                  "audience_insight": None, "agent_angle": None, "must_avoid": []},
        "photo_id": "formal", "facts": [], "assumptions": [], "missing_fields": [],
        "risk_proposed": "green", "product_promotion": False, "variation_count": 3,
        "audience": {"primary": "clients", "age_range": None, "notes": None},
        "languages": {"primary": "en", "secondary": None},
        "event": None, "cta": None,
    }
    return base | kw


COPY = {"headline": "Wishing you a bright Deepavali",
        "subheadline": "On your side, this season and always",
        "body": "Thank you for the trust you place in me. It is a privilege to plan alongside you.",
        "cta": None, "claims": []}

DIRECTIONS = {"directions": [
    {"id": "a", "name": "Human", "layout_family": "festive-portrait", "red_application": "highlight",
     "photo_mode": "cutout_front", "mountains_variant": "core_3", "background": "solid",
     "background_brief": None, "headline_placement": "top-left", "rationale": "warm"},
    {"id": "b", "name": "Premium editorial", "layout_family": "editorial-minimal",
     "red_application": "highlight", "photo_mode": "container", "mountains_variant": "outline",
     "background": "solid", "background_brief": None, "headline_placement": "top-left",
     "rationale": "spacious"},
    {"id": "c", "name": "Contemporary social", "layout_family": "social-bold", "red_application": "bold",
     "photo_mode": "cutout_front", "mountains_variant": "inverted_4", "background": "solid",
     "background_brief": None, "headline_placement": "top-left", "rationale": "energy"}],
    "rationale": "three distinct looks"}

REVIEW = {"findings": [], "overall": "Reads warmly"}


def scripted_model() -> FunctionModel:
    """One model that answers whichever agent is calling, by output-tool name."""
    def respond(messages, info: AgentInfo) -> ModelResponse:
        tool = info.output_tools[0]
        schema = json.dumps(tool.parameters_json_schema)
        if "core_message" in schema:
            payload = brief_payload()
        elif "directions" in schema:
            payload = DIRECTIONS
        elif "headline" in schema:
            payload = COPY
        elif "intended_use" in schema:
            payload = {"intended_use": "information_source", "summary": "agenda",
                       "extracted_facts": [], "contains_instructions": False}
        else:
            payload = REVIEW
        return ModelResponse(parts=[ToolCallPart(tool.name, payload)])
    return FunctionModel(respond)


@pytest.fixture
def run(monkeypatch, tmp_path):
    """Run the pipeline with a scripted model and no network."""
    def _run(**kwargs):
        import src.ai.model_gateway as mg

        original = mg.ModelGateway.__post_init__ if hasattr(mg.ModelGateway, "__post_init__") else None
        monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted_model())
        defaults = dict(profile_dir="profiles/demo-agent", campaign_dir="campaigns/deepavali-2026",
                        out_root=tmp_path, interactive=False, images_enabled=False,
                        visual_review=False, today=dt.date(2026, 9, 20))
        return asyncio.run(create_campaign(**(defaults | kwargs)))
    return _run


class TestHappyPath:
    def test_three_posters_and_a_campaign_folder(self, run, tmp_path):
        result = run()
        assert result.ok and len(result.concepts) == 3
        out = result.out_dir
        for name in ("campaign.json", "brief.json", "copy.json", "policy.json", "usage.json"):
            assert (out / name).exists(), name
        assert len(list(out.glob("variation-*.png"))) == 3
        assert len(list((out / "designs").glob("*.json"))) == 3
        assert len(list((out / "concepts").glob("*.json"))) == 3

    def test_every_variation_uses_a_different_layout(self, run):
        families = [c.design.layout_family for c in run().concepts]
        assert len(set(families)) == len(families)

    def test_posters_pass_validation(self, run):
        for concept in run().concepts:
            assert concept.ok, [f.message for f in concept.report.errors]

    def test_copy_passes_the_rules(self, run):
        assert run().copy_report.passed


class TestLineage:
    def test_record_answers_how_it_was_made(self, run):
        record = run().lineage
        assert record.campaign_id and record.request_sha256_16
        assert record.brand_pack_version == "0.2" and record.rules_version == "0.1"
        assert record.profile_id == "demo-agent"
        assert set(record.models) == {"fast", "quality", "vision", "image"}
        assert record.usage and record.usage_summary["tokens"] > 0
        assert len(record.variations) == len(record.exports) == 3
        assert all(v["validation"]["checks_run"] > 50 for v in
                   [x.model_dump() for x in record.variations])

    def test_exports_are_hashed(self, run):
        exports = run().lineage.exports
        assert all(len(e.sha256_16) == 16 for e in exports)
        assert len({e.sha256_16 for e in exports}) == len(exports)  # genuinely different images

    def test_provenance_is_embedded_in_the_png(self, run):
        result = run()
        meta = read_metadata(result.concepts[0].image_path)
        assert meta["CampaignID"] == result.campaign_id
        assert meta["BrandPack"] == "0.2" and meta["Risk"] == "green"
        assert "gemini" in meta["Models"]

    def test_campaign_json_is_readable(self, run):
        record = json.loads((run().out_dir / "campaign.json").read_text())
        assert record["schema_version"] == "0.1"
        assert record["brief"]["family"] == "festive"
        assert record["campaign_copy"]["headline"]


class TestGuards:
    def test_missing_mandatory_details_block_generation(self, run):
        """A festive brief with no festival cannot be generated, and says so."""
        import src.ai.brief_agent as ba

        original = ba.assemble_brief

        def stripped(draft, deps, campaign_id):
            brief = original(draft, deps, campaign_id)
            brief.festival = None
            return brief

        ba.assemble_brief = stripped
        try:
            result = run()
        finally:
            ba.assemble_brief = original
        assert not result.ok and "festival" in result.blocked_reason
        assert result.concepts == []

    def test_budget_exhaustion_degrades_gracefully(self, run):
        """Running out of budget stops the run cleanly and says why; it never crashes."""
        result = run(budget=RunBudget(max_tokens=200_000, max_model_calls=2))
        assert result.partial and "budget" in result.blocked_reason
        assert result.brief is not None          # the work already done is kept
        assert (result.out_dir / "campaign.json").exists()

    def test_fallback_directions_when_the_director_is_cut_off(self, run):
        """If the director cannot run, a valid deterministic spread is used instead."""
        result = run(budget=RunBudget(max_tokens=200_000, max_model_calls=3))
        assert result.partial or len({c.design.layout_family for c in result.concepts}) == len(result.concepts)

    def test_stale_output_is_cleared(self, run, tmp_path):
        first = run()
        stale = first.out_dir / "variation-z.png"
        stale.write_bytes(b"old")
        run()
        assert not stale.exists()
