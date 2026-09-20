"""Revision flow and CLI: change only what was asked, and say what could not be done."""

import asyncio
import datetime as dt
import json

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.ai.model_gateway import ModelGateway
from src.contracts.edits import IMPLEMENTED_OPS, NOT_YET_IMPLEMENTED, to_edit_ops
from src.main import _variation_id, build_parser
from src.revise import revise_campaign
from tests.test_workflow import scripted_model  # reuse the scripted campaign model


def edit_model(ops: list[dict], interpretation: str = "change it", unsupported=None) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {
            "ops": ops, "interpretation": interpretation, "unsupported": unsupported or []})])
    return FunctionModel(respond)


@pytest.fixture
def campaign(monkeypatch, tmp_path):
    """A finished campaign on disk, produced with a scripted model."""
    import src.ai.model_gateway as mg
    from src.workflow import create_campaign

    monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: scripted_model())
    result = asyncio.run(create_campaign(
        "profiles/demo-agent", "campaigns/deepavali-2026", out_root=tmp_path,
        interactive=False, images_enabled=False, visual_review=False, today=dt.date(2026, 9, 20)))
    return result


def revise(campaign, monkeypatch, ops, variation="a", instruction="change it", **kw):
    import src.ai.model_gateway as mg

    monkeypatch.setattr(mg.ModelGateway, "resolve", lambda self, tier: edit_model(ops, **kw))
    return asyncio.run(revise_campaign(campaign.out_dir, variation, instruction))


class TestDesignScopedEdits:
    def test_resize_is_relative_and_only_touches_one_variation(self, campaign, monkeypatch):
        before = {c.direction.id: c.image_path.stat().st_mtime_ns for c in campaign.concepts}
        result = revise(campaign, monkeypatch, [{"op": "resize", "element_id": "portrait", "scale": 0.8}])
        assert result.design.version == 2
        assert result.design.element("portrait").overrides["scale"] == pytest.approx(0.8)
        assert result.also_rerendered == []
        assert result.poster_path.stat().st_mtime_ns > before["a"]

    def test_preset_change_reflows(self, campaign, monkeypatch):
        result = revise(campaign, monkeypatch, [{"op": "change_preset", "preset": "instagram_story"}])
        assert (result.design.canvas.width, result.design.canvas.height) == (1080, 1920)
        assert result.report.passed

    def test_no_image_model_for_a_layout_change(self, campaign, monkeypatch):
        result = revise(campaign, monkeypatch, [{"op": "resize", "element_id": "portrait", "scale": 0.9}])
        assert not result.used_image_model

    def test_version_history_is_kept(self, campaign, monkeypatch):
        revise(campaign, monkeypatch, [{"op": "resize", "element_id": "portrait", "scale": 0.9}])
        designs = sorted((campaign.out_dir / "designs").glob("variation-a.v*.json"))
        assert len(designs) >= 2  # v1 and v2 both on disk


class TestCampaignScopedEdits:
    def test_copy_change_rerenders_every_variation(self, campaign, monkeypatch):
        result = revise(campaign, monkeypatch,
                        [{"op": "set_copy", "field": "headline", "text": "A brighter Deepavali"}])
        assert result.copy_changed
        assert sorted(result.also_rerendered) == ["b", "c"]
        saved = json.loads((campaign.out_dir / "copy.json").read_text())
        assert saved["headline"] == "A brighter Deepavali"

    def test_copy_that_breaks_the_rules_is_rejected(self, campaign, monkeypatch):
        """'Guaranteed returns' must not reach a poster, even via a revision."""
        result = revise(campaign, monkeypatch,
                        [{"op": "set_copy", "field": "headline", "text": "Guaranteed returns of 8% p.a."}])
        assert not result.copy_changed
        assert any("rejected" in u for u in result.plan.unsupported)
        assert json.loads((campaign.out_dir / "copy.json").read_text())["headline"] != "Guaranteed returns of 8% p.a."

    def test_fact_correction_updates_the_brief(self, campaign, monkeypatch):
        result = revise(campaign, monkeypatch,
                        [{"op": "set_fact", "field": "event.venue", "value": "Suntec City"}])
        assert result.facts_changed == ["event.venue"]
        brief = json.loads((campaign.out_dir / "brief.json").read_text())
        assert any(f["field"] == "event.venue" and f["value"] == "Suntec City" for f in brief["facts"])


class TestHonesty:
    def test_unimplemented_operations_are_reported(self, campaign, monkeypatch):
        """Saying 'added Chinese' when nothing happened would be worse than saying no."""
        result = revise(campaign, monkeypatch,
                        [{"op": "add_translation", "language": "zh-Hans", "placement": "below"}])
        assert result.plan.ops == []
        assert NOT_YET_IMPLEMENTED["add_translation"] in result.plan.unsupported
        assert "nothing was changed" in result.summary()

    def test_flat_draft_conversion_rejects_bad_operations(self):
        ops, rejected = to_edit_ops([
            {"op": "resize", "element_id": "portrait", "scale": 0.8},
            {"op": "make_it_pop"},
            {"op": "resize", "element_id": None, "scale": None},
        ])
        assert [o.op for o in ops] == ["resize"]
        assert len(rejected) == 2

    def test_every_implemented_op_is_applied_by_code(self):
        from src.contracts.edits import OP_FIELDS
        assert IMPLEMENTED_OPS <= set(OP_FIELDS)
        assert IMPLEMENTED_OPS.isdisjoint(NOT_YET_IMPLEMENTED)


class TestCli:
    def test_variation_accepts_numbers_and_letters(self):
        assert _variation_id("2") == "b" and _variation_id("B") == "b"

    def test_create_arguments(self):
        args = build_parser().parse_args(
            ["create", "--agent", "profiles/demo-agent", "--campaign", "campaigns/x", "--no-images"])
        assert args.command == "create" and args.no_images and args.preset == "instagram_portrait"

    def test_revise_requires_a_campaign(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["revise", "--variation", "1"])

    def test_unknown_preset_rejected(self):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["create", "--agent", "a", "--campaign", "c", "--preset", "billboard"])
