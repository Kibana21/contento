"""Adversarial tests for the authored-markup recogniser and the CSS allowlist.

Every case here is a way a model could put text on a poster, or hide text it was required to
show, without writing a text node. These are the tests that make ADR-001 structural for the
free-form engine rather than a prompt instruction.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.freeform.css import CssError, CssRule, check_declaration, serialise as css_serialise
from src.freeform.html_parse import AuthoredHtmlError, parse_authored, serialise

GOOD = """
<section class="benefit">
  <span class="badge" data-asset="icon.shield"></span>
  <div class="copy">
    <h3 data-ref="content.benefits.0.label"></h3>
    <p data-ref="content.benefits.0.text"></p>
  </div>
</section>
<hr class="rule">
"""


class TestAccepts:
    def test_a_well_formed_benefit_module(self):
        root = parse_authored(GOOD)
        bound = [n for n in root.walk() if n.is_bound]
        assert {n.ref or n.asset for n in bound} == {
            "icon.shield", "content.benefits.0.label", "content.benefits.0.text"}

    def test_whitespace_between_tags_is_fine(self):
        assert parse_authored("<div>\n\t  <span></span>\n</div>").children

    def test_void_elements_need_no_close(self):
        assert len(parse_authored('<img data-asset="icon.x"><br><hr>').children) == 3

    def test_serialise_round_trips_structure(self):
        out = serialise(parse_authored(GOOD))
        assert 'data-ref="content.benefits.0.label"' in out and "<hr" in out
        assert ">" in out and "script" not in out


class TestRejectsText:
    """The core rule: the author may not write a character of visible text."""

    def test_plain_text_node(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<p>Guaranteed 0.35% p.a.</p>")
        assert e.value.rule_id == "authored.text"

    def test_numeric_character_references(self):
        # &#48;&#46;&#51;&#53;&#37; renders as "0.35%" and never reaches handle_data
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<p>&#48;&#46;&#51;&#53;&#37;</p>")
        assert e.value.rule_id == "authored.text"

    def test_named_entity_reference(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored("<p>&copy; AIA</p>")

    def test_nbsp_flood_is_not_whitespace(self):
        # str.isspace() returns True for U+00A0; a naive check would pass this
        assert "\xa0".isspace(), "precondition: Python thinks nbsp is whitespace"
        with pytest.raises(AuthoredHtmlError):
            parse_authored("<p>&nbsp;&nbsp;&nbsp;</p>")

    def test_literal_nbsp_character(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored("<p>\xa0\xa0</p>")

    def test_text_in_a_comment_is_still_rejected(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<!-- 0.35% p.a. --><div></div>")
        assert e.value.rule_id == "authored.comment"


class TestRejectsStructure:
    def test_script(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<script></script>")
        assert e.value.rule_id == "authored.tag"

    def test_svg_cannot_be_used_to_draw_text(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<svg><text>0.35%</text></svg>")
        assert e.value.rule_id == "authored.tag"

    def test_details_supplies_its_own_visible_label(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored("<details><summary></summary></details>")

    def test_lists_are_banned_because_markers_are_text(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored("<ul><li></li></ul>")

    def test_alt_text_renders_when_an_image_fails(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored('<img data-asset="icon.x" alt="Guaranteed 0.35% p.a.">')
        assert e.value.rule_id == "authored.attribute"

    def test_author_may_not_assign_ids(self):
        # the binder owns ids; authored ids would break the leaf-only measured set
        with pytest.raises(AuthoredHtmlError):
            parse_authored('<div id="headline"></div>')

    def test_author_may_not_write_style(self):
        # the repair layer owns the style attribute
        with pytest.raises(AuthoredHtmlError):
            parse_authored('<div style="display:none"></div>')

    def test_author_may_not_write_src(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored('<img src="https://example.com/x.png">')

    def test_event_handlers(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored('<div onclick="x()"></div>')

    def test_unbalanced_tags(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<div><span></div></span>")
        assert e.value.rule_id == "authored.unbalanced"

    def test_unclosed_tag(self):
        with pytest.raises(AuthoredHtmlError) as e:
            parse_authored("<div><span></span>")
        assert e.value.rule_id == "authored.unbalanced"

    def test_class_may_not_break_out_of_a_selector(self):
        with pytest.raises(AuthoredHtmlError):
            parse_authored('<div class="a { } .evil"></div>')


class TestCssInjectionVectors:
    """Every CSS route that puts text on a page or hides text that must appear."""

    @pytest.mark.parametrize("value", [
        '"0.35% p.a."',            # a literal string
        "attr(data-ref)",          # pulled from an attribute the model wrote
        "counter(n)",              # built out of digits
        "open-quote",              # injects the quote strings
        'url("data:image/svg+xml,<svg><text>x</text></svg>")',  # text as an image
    ])
    def test_content_is_never_allowed(self, value):
        with pytest.raises(CssError) as e:
            check_declaration("content", value)
        assert e.value.rule_id == "css.forbidden"

    @pytest.mark.parametrize("prop", ["counter-reset", "counter-increment", "quotes",
                                      "list-style-type", "list-style"])
    def test_text_building_properties(self, prop):
        with pytest.raises(CssError):
            check_declaration(prop, "n 35")

    @pytest.mark.parametrize("prop,value", [
        ("display", "none"),
        ("visibility", "hidden"),
        ("opacity", "0"),
        ("clip-path", "inset(100%)"),
        ("text-indent", "-9999px"),
        ("background-clip", "text"),
        ("-webkit-text-fill-color", "transparent"),
        ("position", "fixed"),
    ])
    def test_hiding_bound_content(self, prop, value):
        """The likeliest misbehaviour is not inventing a fact but hiding the legal line."""
        with pytest.raises(CssError):
            check_declaration(prop, value)

    def test_important_cannot_be_smuggled_through_a_value(self):
        with pytest.raises(CssError):
            check_declaration("font-size", "90px !important")

    def test_important_is_unrepresentable_in_the_output(self):
        css = css_serialise([CssRule(selector=".headline", declarations={"font-size": "90px"})])
        assert "!important" not in css and "font-size: 90px;" in css

    def test_font_family_is_assigned_not_authored(self):
        with pytest.raises(CssError):
            check_declaration("font-family", "Comic Sans MS")

    def test_hyphenation_stays_banned(self):
        # CLAUDE.md: hyphenation once split a headline mid-letter
        for prop in ("hyphens", "word-break", "overflow-wrap"):
            with pytest.raises(CssError):
                check_declaration(prop, "break-all")

    @pytest.mark.parametrize("value", ["rotate(15deg)", "scaleX(-1)", "matrix(1,0,0,1,0,0)",
                                       "skew(10deg)", "scale(0)"])
    def test_mountains_may_not_be_rotated_or_flipped(self, value):
        # Brand Standards p69
        with pytest.raises(CssError):
            check_declaration("transform", value)

    def test_translate_and_positive_scale_are_fine(self):
        check_declaration("transform", "translateY(-12px)")
        check_declaration("transform", "scale(0.9)")


class TestPalette:
    def test_raw_hex_is_rejected(self):
        with pytest.raises(CssError) as e:
            check_declaration("color", "#00FF00")
        assert e.value.rule_id == "css.palette"

    def test_token_references_are_accepted(self):
        check_declaration("color", "var(--red)")
        check_declaration("background-color", "transparent")

    def test_a_rule_validates_on_construction(self):
        with pytest.raises(ValidationError):
            CssRule(selector=".x", declarations={"content": '"0.35%"'})

    @pytest.mark.parametrize("selector", ["#id", "*", ".a::before", ".a:not(.b)", "div"])
    def test_selector_grammar(self, selector):
        with pytest.raises(ValidationError):
            CssRule(selector=selector, declarations={"color": "var(--red)"})

    @pytest.mark.parametrize("selector", [".benefit", ".benefit > .badge", ".m + .m",
                                          '[data-group="card"]', ".benefit:first-child"])
    def test_accepted_selectors(self, selector):
        assert CssRule(selector=selector, declarations={"color": "var(--red)"}).selector
