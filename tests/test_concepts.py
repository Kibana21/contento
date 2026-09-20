"""Creative director, design builder and concept assembly."""

import asyncio
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.ai.creative_director import choose_directions, fallback_directions
from src.ai.model_gateway import ModelGateway
from src.assets.background import NEGATIVE, build_prompt
from src.concepts import _auto_fix, build_concept
from src.contracts.common import Family, Severity, ValidationReport, Finding
from src.contracts.creative import (BackgroundKind, CreativeDirection, MountainsVariant,
                                    PhotoMode, RedApplication)
from src.contracts.design import ElementType
from src.policy.rules import decide
from src.render import fixtures as fx
from src.render.design_builder import build_design
from src.render.layouts import FAMILIES, catalogue, families_for
from src.render.renderer import available_families


def direction(**kw) -> CreativeDirection:
    base = dict(id="a", name="Human", layout_family="festive-portrait",
                red_application=RedApplication.HIGHLIGHT, photo_mode=PhotoMode.CUTOUT_FRONT,
                mountains_variant=MountainsVariant.CORE_3, background=BackgroundKind.SOLID,
                rationale="warmth")
    return CreativeDirection(**(base | kw))


class TestLayoutRegistry:
    def test_every_family_has_a_template(self):
        assert set(FAMILIES) == set(available_families())

    def test_families_are_suggested_by_campaign_type(self):
        assert families_for("seminar")[0].name == "event-information"
        assert families_for("festive")[0].name == "festive-portrait"

    def test_catalogue_is_serialisable_for_the_model(self):
        entry = catalogue()[0]
        assert {"layout_family", "description", "photo_modes", "mountains_variants"} <= set(entry)


class TestCreativeDirector:
    @staticmethod
    def scripted(payload: dict) -> FunctionModel:
        def respond(messages, info: AgentInfo) -> ModelResponse:
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, payload)])
        return FunctionModel(respond)

    def test_fallback_set_is_always_valid(self):
        for family in Family:
            brief = fx.seminar_brief() if family.value in {"seminar", "event", "recruitment"} else fx.festive_brief()
            brief.family = family
            ds = fallback_directions(brief, 4)
            assert 3 <= len(ds.directions) <= 4
            assert len({d.signature for d in ds.directions}) == len(ds.directions)

    def test_identical_directions_fall_back(self, profile):
        """A model that returns four recolours of one idea must not reach the renderer."""
        same = [direction(id=i).model_dump(mode="json") for i in "abc"]
        gw = ModelGateway(test_model=self.scripted({"directions": same, "rationale": "x"}))
        ds, source = asyncio.run(choose_directions(gw, fx.festive_brief(), fx.festive_copy(), profile))
        assert source == "fallback"
        assert len({d.signature for d in ds.directions}) == len(ds.directions)

    def test_valid_set_is_accepted(self, profile):
        good = [direction(id="a").model_dump(mode="json"),
                direction(id="b", layout_family="editorial-minimal", photo_mode=PhotoMode.CONTAINER,
                          mountains_variant=MountainsVariant.OUTLINE).model_dump(mode="json"),
                direction(id="c", layout_family="social-bold", red_application=RedApplication.BOLD,
                          mountains_variant=MountainsVariant.INVERTED_4).model_dump(mode="json")]
        gw = ModelGateway(test_model=self.scripted({"directions": good, "rationale": "spread"}))
        ds, source = asyncio.run(choose_directions(gw, fx.festive_brief(), fx.festive_copy(), profile))
        assert source == "model" and len(ds.directions) == 3


class TestDesignBuilder:
    def build(self, brief, copy, d, profile, brand):
        return build_design(brief, copy, d, profile, decide(brief), brand)

    def test_factual_elements_are_references(self, profile, brand):
        design = self.build(fx.seminar_brief(), fx.seminar_copy(),
                            direction(layout_family="event-information", photo_mode=PhotoMode.CONTAINER,
                                      mountains_variant=MountainsVariant.CORE_4), profile, brand)
        facts = design.by_type(ElementType.FACT)
        assert facts and all(f.content_ref.startswith("facts.") and f.text is None for f in facts)

    def test_disclaimer_is_referenced_not_inlined(self, profile, brand):
        design = self.build(fx.seminar_brief(), fx.seminar_copy(),
                            direction(layout_family="event-information", photo_mode=PhotoMode.CONTAINER,
                                      mountains_variant=MountainsVariant.CORE_4), profile, brand)
        disclaimer = design.by_type(ElementType.DISCLAIMER)[0]
        assert disclaimer.content_ref == "policy.disclaimer" and disclaimer.text is None

    def test_green_campaigns_carry_no_disclaimer(self, profile, brand):
        design = self.build(fx.festive_brief(), fx.festive_copy(), direction(), profile, brand)
        assert not design.by_type(ElementType.DISCLAIMER)

    def test_bold_theme_uses_the_white_logo(self, profile, brand):
        design = self.build(fx.festive_brief(), fx.festive_copy(),
                            direction(layout_family="social-bold", red_application=RedApplication.BOLD,
                                      mountains_variant=MountainsVariant.INVERTED_4), profile, brand)
        assert design.by_type(ElementType.LOGO)[0].overrides["colour"] == "white"
        assert design.background.colour_token == "core.red"

    def test_photo_mode_none_omits_the_portrait(self, profile, brand):
        design = self.build(fx.festive_brief(), fx.festive_copy(),
                            direction(photo_mode=PhotoMode.NONE, mountains_variant=MountainsVariant.CORE_4),
                            profile, brand)
        assert not design.by_type(ElementType.AGENT_PHOTO)

    def test_missing_copy_slots_are_skipped(self, profile, brand):
        """A design must never reference copy the writer did not produce."""
        from src.contracts.copy import Copy
        design = self.build(fx.festive_brief(), Copy(headline="Only a headline"), direction(), profile, brand)
        assert not design.by_type(ElementType.BODY) and not design.by_type(ElementType.SUBHEADLINE)

    def test_qr_uses_the_briefs_verified_url(self, profile, brand):
        design = self.build(fx.seminar_brief(), fx.seminar_copy(),
                            direction(layout_family="event-information", photo_mode=PhotoMode.CONTAINER,
                                      mountains_variant=MountainsVariant.CORE_4), profile, brand)
        assert design.by_type(ElementType.QR)[0].overrides["url"] == "https://example.com/jane-tan/events"


class TestAutoFix:
    def report(self, rule: str, element: str) -> ValidationReport:
        return ValidationReport(checks_run=1, findings=[
            Finding(rule_id=rule, severity=Severity.ERROR, message="x", element_id=element)])

    def test_overflow_shrinks_the_element(self):
        design = fx.festive_design()
        fixed, applied = _auto_fix(design, self.report("layout.overflow", "headline"))
        assert applied and fixed.element("headline").overrides["scale"] == pytest.approx(0.85)

    def test_overflow_uses_the_measured_shortfall(self):
        """A headline 30% too wide is scaled by the measured ratio, not a fixed step."""
        geometry = {"elements": [{"id": "headline", "width": 700, "height": 300,
                                  "scrollWidth": 1000, "scrollHeight": 300}]}
        fixed, applied = _auto_fix(fx.festive_design(), self.report("layout.overflow", "headline"), geometry)
        assert fixed.element("headline").overrides["scale"] == pytest.approx(0.686, abs=0.01)

    def test_tiny_type_grows(self):
        fixed, applied = _auto_fix(fx.festive_design(), self.report("type.min_size", "contact"))
        assert fixed.element("contact").overrides["scale"] == pytest.approx(1.3)

    def test_unfixable_contrast_is_not_looped(self):
        """If the colour comes from the layout family, code cannot fix it: report, don't spin."""
        _, applied = _auto_fix(fx.festive_design(), self.report("contrast.text", "headline"))
        assert applied == []


class TestBackgroundPrompt:
    def test_prompt_carries_the_brand_photography_rules(self, brand):
        prompt = build_prompt(direction(background=BackgroundKind.GENERATED,
                                        background_brief="oil lamps at dusk"),
                              fx.festive_brief(), brand)
        assert "oil lamps at dusk" in prompt and "deepavali" in prompt.lower()
        assert brand.red in prompt and "natural warm light" in prompt

    def test_negative_prompt_blocks_text_and_logos(self):
        for banned in ("text", "logo", "watermark", "single-use plastic"):
            assert banned in NEGATIVE


def test_concept_runs_end_to_end_without_image_generation(tmp_path, profile, brand):
    brief, copy = fx.festive_brief(), fx.festive_copy()
    gw = ModelGateway()
    concept = asyncio.run(build_concept(gw, direction(), brief, copy, profile, decide(brief), brand,
                                        tmp_path, images_enabled=False))
    assert concept.ok, [f.message for f in concept.report.errors]
    assert concept.image_path.exists()
    assert gw.budget.spent_images == 0


def test_generated_background_is_skipped_gracefully(tmp_path, profile, brand):
    """With image generation off, the concept still renders and says why."""
    brief, copy = fx.festive_brief(), fx.festive_copy()
    d = direction(background=BackgroundKind.GENERATED, background_brief="warm diyas")
    concept = asyncio.run(build_concept(ModelGateway(), d, brief, copy, profile, decide(brief), brand,
                                        tmp_path, images_enabled=False))
    assert concept.background_note == "image generation disabled"
    assert concept.design.background.kind == "solid" and concept.ok


class TestCompositionGrammar:
    """The layout grammar: wide creative range, but every combination stays legal."""

    def test_grammar_is_bounded(self):
        from pydantic import ValidationError
        from src.contracts.creative import Anchor, Composition, PhotoPlacement

        with pytest.raises(ValidationError):
            Composition(headline_scale=3.0)          # type cannot run away
        with pytest.raises(ValidationError):
            Composition(headline_span=14)            # only 12 columns exist
        with pytest.raises(ValidationError):
            Composition(centred=True, headline_anchor=Anchor.TOP_RIGHT)
        with pytest.raises(ValidationError):
            Composition(photo_placement=PhotoPlacement.FULL_BLEED_RIGHT, headline_span=11)

    def test_copy_and_portrait_never_share_columns(self, profile, brand):
        """Collision is prevented by construction, not corrected afterwards."""
        from src.contracts.creative import Composition, PhotoPlacement
        from src.policy.rules import decide

        greedy = Composition(headline_span=12, copy_span=12, photo_placement=PhotoPlacement.RIGHT)
        design = build_design(fx.festive_brief(), fx.festive_copy(),
                              direction(composition=greedy), profile, decide(fx.festive_brief()), brand)
        comp = design.composition
        assert comp.headline_span <= comp.max_copy_span
        assert comp.headline_span + comp.photo_columns <= 12

    def test_each_skeleton_has_its_own_look(self):
        from src.render.layouts import FAMILIES

        signatures = {(f.composition.photo_shape, f.composition.density, f.composition.accent,
                       f.composition.mountains_placement) for f in FAMILIES.values()}
        assert len(signatures) == len(FAMILIES)

    def test_composition_is_recorded_on_the_design(self, profile, brand):
        from src.contracts.creative import Composition, Density
        from src.policy.rules import decide

        comp = Composition(density=Density.AIRY, headline_scale=1.3)
        design = build_design(fx.festive_brief(), fx.festive_copy(), direction(composition=comp),
                              profile, decide(fx.festive_brief()), brand)
        assert design.composition.density is Density.AIRY          # reproducible
        assert design.element("headline").overrides["scale"] == pytest.approx(1.3)

    def test_every_family_renders_through_the_grammar(self):
        from src.render.layouts import FAMILIES

        assert {f.template for f in FAMILIES.values()} == {"composed"}
