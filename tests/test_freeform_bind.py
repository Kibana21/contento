"""The binder and the render-time audit, end to end with no model involved.

This is the milestone the whole governance layer rests on: if a hand-authored page binds real
copy, renders, audits and validates, then the agents that come later are a cost and quality
problem rather than a correctness one.
"""

from __future__ import annotations

import pytest

from src.contracts.design import Canvas, ElementType
from src.freeform import fixtures as ff
from src.freeform.binder import bind_page
from src.freeform.contracts import FreeformPage, PagePlan
from src.freeform.css import CssRule
from src.freeform.renderer import render_bound
from src.policy.rules import decide
from src.render import fixtures as fx
from src.render.context import RenderContext
from src.validate import validate_rendered


@pytest.fixture
def ctx(brand, profile):
    brief = fx.seminar_brief()
    return RenderContext(brief=brief, copy=fx.seminar_copy(), profile=profile, brand=brand,
                         decision=decide(brief, request_text="career seminar"),
                         content=ff.seminar_content())


@pytest.fixture
def canvas():
    return Canvas.from_preset("instagram_portrait")


def bind(ctx, canvas, page=None, system=None):
    return bind_page(page or ff.seminar_page(5), system or ff.speaker_roster_system(),
                     ctx, canvas=canvas)


class TestBinding:
    def test_the_roster_page_binds_cleanly(self, ctx, canvas):
        bound = bind(ctx, canvas)
        assert bound.ok, [f"{f.rule_id}: {f.message}" for f in bound.findings]

    def test_every_bound_leaf_is_tagged(self, ctx, canvas):
        bound = bind(ctx, canvas)
        assert len(bound.spec.types) == 22
        assert 'id="headline-1"' in bound.html and 'data-el-type="headline"' in bound.html

    def test_wrappers_do_not_get_ids(self, ctx, canvas):
        """Only bound leaves are measured, so collision checks see no nested pairs."""
        bound = bind(ctx, canvas)
        assert 'class="module" id=' not in bound.html
        assert 'class="stack" id=' not in bound.html

    def test_text_comes_from_locked_data(self, ctx, canvas):
        bound = bind(ctx, canvas)
        assert bound.bound_text["headline-1"] == fx.seminar_copy().headline
        assert "Wong Sze Keed" in bound.html and "Rachel Lim" in bound.html

    def test_only_copy_carries_a_hierarchy_role(self, ctx, canvas):
        """Five speaker labels are sub-headings; they must not compete with the headline."""
        bound = bind(ctx, canvas)
        subheads = [i for i, t in bound.spec.types.items() if t is ElementType.SUBHEADLINE]
        assert len(subheads) == 6                      # one real + five speaker labels
        assert bound.spec.first[ElementType.SUBHEADLINE] == "subheadline-1"

    def test_the_page_grows_with_the_content(self, ctx, canvas):
        """The capability the structured engine cannot express at all."""
        assert len(bind(ctx, canvas, ff.seminar_page(5)).spec.types) > \
               len(bind(ctx, canvas, ff.seminar_page(3)).spec.types)

    def test_the_logo_is_a_sourced_asset(self, ctx, canvas):
        bound = bind(ctx, canvas)
        assert "corporate-logo-red.svg" in bound.html


class TestBinderRefusals:
    def plan(self):
        return PagePlan(index=1, purpose="invite",
                        must_include=["copy.headline", "brand.logo.red"])

    def test_a_class_the_system_does_not_style(self, ctx, canvas):
        """The failure that would otherwise render an unstyled page and pass every check."""
        page = FreeformPage(plan=self.plan(), html='<div class="page"><h1 class="headline" '
                                                   'data-ref="copy.headline"></h1>'
                                                   '<img class="logo" data-asset="brand.logo.red">'
                                                   '<p class="invented"></p></div>')
        bound = bind(ctx, canvas, page)
        assert "css.unknown_class" in {f.rule_id for f in bound.findings}

    def test_a_selector_targeting_nothing_in_the_vocabulary(self, ctx, canvas):
        system = ff.speaker_roster_system()
        system.rules.append(CssRule(selector=".nowhere", declarations={"color": "var(--red)"}))
        bound = bind(ctx, canvas, system=system)
        assert "css.orphan_selector" in {f.rule_id for f in bound.findings}

    def test_a_required_reference_that_is_missing(self, ctx, canvas):
        page = FreeformPage(plan=self.plan(),
                            html='<div class="page"><h1 class="headline" '
                                 'data-ref="copy.headline"></h1></div>')
        bound = bind(ctx, canvas, page)
        assert "content.missing_required" in {f.rule_id for f in bound.findings}

    def test_a_reference_placed_twice(self, ctx, canvas):
        page = FreeformPage(plan=self.plan(),
                            html='<div class="page">'
                                 '<h1 class="headline" data-ref="copy.headline"></h1>'
                                 '<h2 class="subheadline" data-ref="copy.headline"></h2>'
                                 '<img class="logo" data-asset="brand.logo.red"></div>')
        bound = bind(ctx, canvas, page)
        assert "content.duplicate_ref" in {f.rule_id for f in bound.findings}

    def test_a_reference_to_data_that_does_not_exist(self, ctx, canvas):
        page = FreeformPage(plan=self.plan(),
                            html='<div class="page">'
                                 '<h1 class="headline" data-ref="copy.headline"></h1>'
                                 '<img class="logo" data-asset="brand.logo.red">'
                                 '<p class="body" data-ref="content.speakers.99.label"></p></div>')
        bound = bind(ctx, canvas, page)
        assert "ref.unresolved" in {f.rule_id for f in bound.findings}

    def test_authored_text_is_refused_at_the_binder(self, ctx, canvas):
        page = FreeformPage(plan=self.plan(), html='<div class="page"><h1 class="headline">'
                                                   "Guaranteed 0.35% p.a.</h1></div>")
        bound = bind(ctx, canvas, page)
        assert "authored.text" in {f.rule_id for f in bound.findings}
        assert bound.html == ""


class TestRenderAndAudit:
    """Needs Chromium; Playwright already runs in this suite."""

    def test_the_page_renders_audits_and_validates(self, ctx, canvas, brand, tmp_path):
        bound = bind(ctx, canvas)
        result = render_bound(bound, tmp_path, canvas=canvas, name="roster", long_form=True)
        assert not result.findings, [f.evidence for f in result.findings]

        report = validate_rendered(bound.spec, result.geometry, result.image_path, brand)
        assert report.checks_run > 250
        assert report.passed, [f"{f.rule_id}:{f.element_id}" for f in report.errors]

    def test_long_form_height_is_measured_from_the_content(self, ctx, canvas, tmp_path):
        short = render_bound(bind(ctx, canvas, ff.seminar_page(3)), tmp_path, canvas=canvas,
                             name="short", long_form=True)
        tall = render_bound(bind(ctx, canvas, ff.seminar_page(5)), tmp_path, canvas=canvas,
                            name="tall", long_form=True)
        assert tall.canvas.height > short.canvas.height
        assert tall.canvas.height % 4 == 0          # the 4px brand soft grid
        assert short.canvas.height >= canvas.width

    def test_capitalised_display_type_is_styling_not_substitution(self, ctx, canvas, tmp_path):
        """The headline is set in capitals by the design; innerText reports it transformed."""
        bound = bind(ctx, canvas)
        result = render_bound(bound, tmp_path, canvas=canvas, name="caps", long_form=True)
        assert "bind.substituted" not in {f.rule_id for f in result.findings}

    def test_a_hidden_disclaimer_is_caught(self, ctx, canvas, tmp_path):
        """The likeliest misbehaviour: losing the mandatory legal line rather than inventing one."""
        system = ff.speaker_roster_system()
        system.rules.append(CssRule(selector=".legal", declarations={"opacity": "0.2"}))
        bound = bind(ctx, canvas, system=system)
        assert bound.ok
        result = render_bound(bound, tmp_path, canvas=canvas, name="faded", long_form=True)
        report = validate_rendered(bound.spec, result.geometry, result.image_path, ctx.brand)
        # 0.2 opacity passes the visibility probe but cannot pass the contrast rule
        assert not report.passed
        assert "contrast.text" in {f.rule_id for f in report.errors}
