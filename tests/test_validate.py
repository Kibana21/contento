"""Validators: every rule traces to a line in the brand pack, and fires on a real violation."""

import copy as copymod

import pytest

from src.contracts.creative import MountainsVariant, RedApplication
from src.contracts.design import Element, ElementType
from src.render import fixtures as fx
from src.render.context import RenderContext
from src.render.renderer import render
from src.validate import validate_all, validate_design, validate_dom, validate_pixels
from src.validate.colour import contrast_ratio, is_reddish, parse_colour


def rules(report) -> set[str]:
    return {f.rule_id for f in report.findings}


class TestColourMaths:
    def test_contrast_matches_wcag(self):
        assert contrast_ratio(parse_colour("#FFFFFF"), parse_colour("#D31145")) == pytest.approx(5.34, abs=0.02)
        assert contrast_ratio(parse_colour("#333D47"), parse_colour("#D31145")) == pytest.approx(2.07, abs=0.02)

    def test_red_detection(self):
        assert is_reddish(parse_colour("#D31145")) and is_reddish(parse_colour("#F6CFD9"))
        assert not is_reddish(parse_colour("#1F78AD")) and not is_reddish(parse_colour("#FFFFFF"))


class TestDesignValidator:
    def test_clean_design_passes(self, brand):
        assert validate_design(fx.festive_design(), brand).passed

    def test_logo_must_be_red_or_white(self, brand):
        d = fx.festive_design()
        d.element("logo").overrides["colour"] = "gold"
        assert "logo.colour" in rules(validate_design(d, brand))

    def test_missing_logo_flagged(self, brand):
        d = fx.festive_design()
        d.elements = [e for e in d.elements if e.type != ElementType.LOGO]
        assert "logo.present" in rules(validate_design(d, brand))

    def test_two_mountain_graphics_rejected(self, brand):
        d = fx.festive_design()
        d.elements.append(Element(id="mountains2", type=ElementType.MOUNTAINS, slot="background-graphic"))
        assert "mountains.single" in rules(validate_design(d, brand))

    def test_inverted_mountains_need_red_ground(self, brand):
        d = fx.festive_design()
        d.mountains = MountainsVariant.INVERTED_3
        d.theme = RedApplication.HIGHLIGHT
        assert "mountains.inverted_ground" in rules(validate_design(d, brand))

    def test_rotation_rejected(self, brand):
        d = fx.festive_design()
        d.element("mountains").overrides["rotate"] = 15
        assert "mountains.transform" in rules(validate_design(d, brand))

    def test_more_than_four_secondary_colours_rejected(self, brand):
        d = fx.festive_design()
        for i, c in enumerate(["blue", "gold", "purple", "green", "orange"]):
            d.elements.append(Element(id=f"deco{i}", type=ElementType.BODY, slot="message",
                                      text="•", overrides={"colour": f"secondary.{c}"}))
        assert "colour.max_secondary" in rules(validate_design(d, brand))

    def test_unknown_style_token_rejected(self, brand):
        d = fx.festive_design()
        d.element("headline").style_token = "mega-shout"
        assert "type.token" in rules(validate_design(d, brand))


class TestDomValidator:
    def test_fixtures_pass(self, rendered, brand):
        for name, (design, res) in rendered.items():
            report = validate_dom(design, res.geometry, brand)
            assert report.passed, f"{name}: {[f.message for f in report.errors]}"

    def test_overflowing_headline_is_caught(self, tmp_path, brand, profile):
        design = fx.festive_design()
        design.element("headline").overrides["scale"] = 2.6
        long_copy = fx.festive_copy()
        long_copy.headline = "Wishing you and your whole family a truly joyous Deepavali season"
        ctx = RenderContext(design=design, brief=fx.festive_brief(), copy=long_copy,
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="overflow")
        report = validate_dom(design, res.geometry, brand)
        assert "layout.outside_canvas" in rules(report) or "layout.overflow" in rules(report)

    def test_low_contrast_text_is_caught(self, tmp_path, brand, profile):
        design = fx.festive_design()
        design.element("subheadline").overrides["colour"] = "#F6CFD9"  # red 20% on white
        ctx = RenderContext(design=design, brief=fx.festive_brief(), copy=fx.festive_copy(),
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="contrast")
        report = validate_dom(design, res.geometry, brand)
        assert "contrast.text" in rules(report)

    def test_tiny_type_is_caught(self, tmp_path, brand, profile):
        design = fx.festive_design()
        design.element("contact").overrides["scale"] = 0.3   # ~7px: below the 15px floor
        ctx = RenderContext(design=design, brief=fx.festive_brief(), copy=fx.festive_copy(),
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="tiny")
        assert "type.min_size" in rules(validate_dom(design, res.geometry, brand))

    def test_missing_element_is_caught(self, rendered, brand):
        design, res = rendered["festive"]
        ghost = copymod.deepcopy(design)
        ghost.elements.append(Element(id="phantom", type=ElementType.BODY, slot="message", text="x"))
        assert "render.missing" in rules(validate_dom(ghost, res.geometry, brand))


class TestPixelValidator:
    def test_red_dominates_in_fixtures(self, rendered):
        for name, (design, res) in rendered.items():
            ids = {e.id for e in design.elements
                   if e.type in {ElementType.AGENT_PHOTO, ElementType.IMAGE, ElementType.QR}}
            from src.validate.pixel import photo_rects
            report = validate_pixels(res.image_path, exclude=photo_rects(res.geometry, ids))
            assert report.passed, f"{name}: {[f.message for f in report.findings]}"

    def test_competing_colour_is_caught(self, tmp_path, brand, profile):
        """A design whose coloured area is mostly blue breaks 'AIA is a red brand' (p51)."""
        design = fx.festive_design()
        design.mountains = MountainsVariant.NONE
        design.elements = [e for e in design.elements if e.type != ElementType.MOUNTAINS]
        design.background.colour_token = "secondary.blue"
        ctx = RenderContext(design=design, brief=fx.festive_brief(), copy=fx.festive_copy(),
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="blue")
        assert "colour.red_dominant" in rules(validate_pixels(res.image_path))


def test_validate_all_combines_layers(rendered, brand):
    design, res = rendered["seminar"]
    report = validate_all(design, res.geometry, res.image_path, brand)
    assert report.checks_run > 60 and report.passed


class TestCollisionRules:
    """Overlap rules: text on imagery, and text on text."""

    def test_text_over_photo_is_caught(self, tmp_path, brand, profile):
        from src.contracts.creative import Composition, PhotoPlacement
        from src.contracts.design import Canvas
        design = fx.festive_design()
        # force the headline across the whole canvas, over the portrait
        design.composition = Composition(headline_span=12, photo_placement=PhotoPlacement.CENTRE)
        design.element("headline").overrides["scale"] = 1.4
        ctx = RenderContext(design=design, brief=fx.festive_brief(), copy=fx.festive_copy(),
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="collide")
        ids = {f.rule_id for f in validate_dom(design, res.geometry, brand).findings}
        assert "layout.collision" in ids or "layout.text_collision" in ids or "layout.overflow" in ids

    def test_clean_fixture_has_no_collisions(self, rendered, brand):
        for _, (design, res) in rendered.items():
            ids = {f.rule_id for f in validate_dom(design, res.geometry, brand).findings}
            assert "layout.text_collision" not in ids and "layout.collision" not in ids
