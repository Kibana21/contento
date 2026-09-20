"""Contract guarantees: facts stay locked, variations stay distinct, edits stay bounded."""

import datetime as dt

import pytest
from pydantic import ValidationError

from src.contracts.brief import AgentRef, CampaignBrief, EventDetails, Story
from src.contracts.common import Family, RunBudget, UsageRecord
from src.contracts.creative import (BackgroundKind, CreativeDirection, DirectionSet,
                                    MountainsVariant, PhotoMode, RedApplication)
from src.contracts.design import Canvas, DesignDoc, Element, ElementType
from src.contracts.edits import ChangePreset, EditPlan, Resize, SetFact, apply_ops
from src.contracts.profile import AgentProfile, Photo, PhotoKind


def brief(**kw) -> CampaignBrief:
    base = dict(campaign_id="CAM-1", family=Family.FESTIVE, objective="relationship",
                agent=AgentRef(profile_id="demo-agent"),
                story=Story(core_message="Warm wishes", emotional_tone="warm"))
    return CampaignBrief(**(base | kw))


def design(**kw) -> DesignDoc:
    base = dict(design_id="d1", campaign_id="CAM-1", direction_id="a",
                canvas=Canvas.from_preset("instagram_portrait"), layout_family="festive-portrait",
                elements=[Element(id="photo", type=ElementType.AGENT_PHOTO, slot="hero",
                                  asset_ref="profile.photos.formal"),
                          Element(id="headline", type=ElementType.HEADLINE, slot="top",
                                  content_ref="copy.headline")])
    return DesignDoc(**(base | kw))


class TestBrief:
    def test_event_family_requires_event(self):
        with pytest.raises(ValidationError, match="requires event details"):
            brief(family=Family.SEMINAR)

    def test_event_family_accepts_event(self):
        b = brief(family=Family.SEMINAR, event=EventDetails(date=dt.date(2026, 10, 18), venue="MBS"))
        assert b.event.date.isoformat() == "2026-10-18"

    def test_missing_fields_block_readiness(self):
        assert brief().is_ready()
        assert not brief(missing_fields=["cta.url"]).is_ready()

    def test_unknown_keys_rejected(self):
        with pytest.raises(ValidationError):
            brief(headline="models must not invent slots")


class TestFactsAreLocked:
    """ADR-001: factual elements reference data; they can never carry literal text."""

    @pytest.mark.parametrize("etype", [ElementType.FACT, ElementType.QR, ElementType.DISCLAIMER,
                                       ElementType.CONTACT_BLOCK])
    def test_factual_elements_reject_inline_text(self, etype):
        with pytest.raises(ValidationError, match="ADR-001"):
            Element(id="x", type=etype, slot="s", text="18 October 2026", asset_ref="a", content_ref="c")

    def test_fact_element_requires_reference(self):
        with pytest.raises(ValidationError, match="content_ref"):
            Element(id="x", type=ElementType.FACT, slot="s")

    def test_headline_may_hold_text(self):
        assert Element(id="h", type=ElementType.HEADLINE, slot="top", text="Happy Deepavali").text


class TestDirectionsAreDistinct:
    """FR-013: variations must differ materially, not just in wording."""

    @staticmethod
    def d(i, family, red, photo, mountains):
        return CreativeDirection(id=i, name=i.upper(), layout_family=family, red_application=red,
                                 photo_mode=photo, mountains_variant=mountains,
                                 background=BackgroundKind.SOLID, rationale="because")

    def test_distinct_set_accepted(self):
        s = DirectionSet(directions=[
            self.d("a", "f1", RedApplication.BOLD, PhotoMode.CUTOUT_FRONT, MountainsVariant.CORE_3),
            self.d("b", "f2", RedApplication.HIGHLIGHT, PhotoMode.CONTAINER, MountainsVariant.CORE_4),
            self.d("c", "f3", RedApplication.HIGHLIGHT, PhotoMode.NONE, MountainsVariant.OUTLINE)])
        assert len({d.signature for d in s.directions}) == 3

    def test_identical_signatures_rejected(self):
        same = [self.d(i, "f1", RedApplication.BOLD, PhotoMode.NONE, MountainsVariant.CORE_3)
                for i in "abc"]
        with pytest.raises(ValidationError, match="must differ"):
            DirectionSet(directions=same)

    def test_all_bold_rejected(self):
        with pytest.raises(ValidationError, match="bold and one highlight"):
            DirectionSet(directions=[
                self.d("a", "f1", RedApplication.BOLD, PhotoMode.NONE, MountainsVariant.CORE_3),
                self.d("b", "f2", RedApplication.BOLD, PhotoMode.CONTAINER, MountainsVariant.CORE_4),
                self.d("c", "f3", RedApplication.BOLD, PhotoMode.LAYERS, MountainsVariant.OUTLINE)])

    def test_inverted_mountains_need_red_ground(self):
        """Brand Standards p59: inverted mountains only on an AIA Red background."""
        with pytest.raises(ValidationError, match="red background"):
            self.d("a", "f1", RedApplication.HIGHLIGHT, PhotoMode.NONE, MountainsVariant.INVERTED_3)

    def test_generated_background_needs_brief(self):
        with pytest.raises(ValidationError, match="background_brief"):
            CreativeDirection(id="a", name="A", layout_family="f", red_application=RedApplication.BOLD,
                              photo_mode=PhotoMode.NONE, mountains_variant=MountainsVariant.NONE,
                              background=BackgroundKind.GENERATED, rationale="r")


class TestEditOps:
    def test_resize_is_relative_and_versioned(self):
        v2 = apply_ops(design(), [Resize(element_id="photo", scale=0.8)])
        assert v2.version == 2 and v2.parent_version == 1
        assert v2.element("photo").overrides["scale"] == pytest.approx(0.8)
        v3 = apply_ops(v2, [Resize(element_id="photo", scale=0.5)])
        assert v3.element("photo").overrides["scale"] == pytest.approx(0.4)

    def test_change_preset_reflows_canvas(self):
        v2 = apply_ops(design(), [ChangePreset(preset="instagram_story")])
        assert (v2.canvas.width, v2.canvas.height) == (1080, 1920)

    def test_unknown_element_is_rejected(self):
        with pytest.raises(KeyError, match="unknown element"):
            apply_ops(design(), [Resize(element_id="nope", scale=0.9)])

    def test_edit_plan_flags_cost_and_scope(self):
        plan = EditPlan(ops=[SetFact(field="event.date", value="2026-10-21")], interpretation="move the date")
        assert plan.is_campaign_wide and not plan.needs_image_model

    def test_edit_plan_capped(self):
        with pytest.raises(ValidationError):
            EditPlan(ops=[Resize(element_id="photo", scale=0.9)] * 11, interpretation="too many")


class TestBudget:
    def test_budget_exhausts_and_blocks(self):
        b = RunBudget(max_tokens=100)
        assert b.can_spend(tokens=50)
        b.record(UsageRecord(call_id="1", node="n", model="m", tier="fast",
                             input_tokens=60, output_tokens=50))
        assert b.exhausted and b.remaining_tokens() == 0

    def test_image_cap(self):
        b = RunBudget(max_images=1)
        b.record(UsageRecord(call_id="1", node="bg", model="m", tier="image", images=1))
        assert b.exhausted


def test_profile_photo_selection_and_credentials():
    p = AgentProfile(id="a", display_name="Jane Tan", title="FSC",
                     photos=[Photo(id="casual", kind=PhotoKind.CASUAL, path="c.jpg"),
                             Photo(id="formal", kind=PhotoKind.FORMAL, path="f.jpg")])
    assert p.photo("formal").id == "formal"
    assert p.photo(None).id == "casual"  # first photo when no primary/preference
    with pytest.raises(ValidationError, match="duplicate photo ids"):
        AgentProfile(id="a", display_name="J", title="T",
                     photos=[Photo(id="x", kind=PhotoKind.PRIMARY, path="1.jpg"),
                             Photo(id="x", kind=PhotoKind.FORMAL, path="2.jpg")])
