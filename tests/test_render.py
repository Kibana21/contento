"""Renderer: references resolve to real data, HTML is the engine, PNG/PDF come out."""

import datetime as dt

import pytest

from src.contracts.design import Canvas, ElementType
from src.contracts.edits import ChangePreset, apply_ops
from src.render import fixtures as fx
from src.render.context import RenderContext, UnresolvedReference
from src.render.mountains import SHAPE_SETS, mountains_svg, resolve_layers
from src.render.qr import qr_data_uri
from src.render.renderer import available_families, build_html, render


class TestReferenceResolution:
    def test_facts_come_from_brief_and_profile(self, seminar_ctx):
        assert seminar_ctx.resolve("facts.event.venue") == "Marina Bay Sands, Expo Hall 3"
        assert seminar_ctx.resolve("facts.event.date") == "18 October 2026"
        assert seminar_ctx.resolve("facts.agent.mobile") == "+65 9123 4567"

    def test_copy_slots_resolve(self, festive_ctx):
        assert "Deepavali" in festive_ctx.resolve("copy.headline")

    def test_missing_reference_fails_loudly(self, festive_ctx):
        """A blank on a poster is worse than an error in the pipeline."""
        with pytest.raises(UnresolvedReference):
            festive_ctx.resolve("facts.event.date")
        with pytest.raises(UnresolvedReference):
            festive_ctx.resolve("copy.cta")

    def test_profile_contact_wins_over_model_supplied_facts(self, seminar_ctx):
        assert seminar_ctx.facts()["agent.email"] == "jane.tan@example.com"


class TestMountains:
    def test_tint_tables_come_from_tokens(self, brand):
        layers = resolve_layers("core_3", brand.mountains, brand.colour_hex)
        assert [l.fill for l in layers] == ["#D31145", "#E4708F", "#F6CFD9"]
        assert [l.opacity for l in layers] == [1.0, 0.9, 1.0]  # front/back solid, middle 90%

    def test_inverted_uses_white_back_peak(self, brand):
        layers = resolve_layers("inverted_4", brand.mountains, brand.colour_hex)
        assert layers[0].fill == "#E4708F" and layers[-1].fill == "#FFFFFF"

    def test_transparent_uses_multiply(self, brand):
        assert any(l.blend == "multiply" for l in resolve_layers("transparent_3", brand.mountains, brand.colour_hex))

    def test_shape_sets_have_three_or_four_peaks(self):
        assert all(3 <= len(v) <= 4 for v in SHAPE_SETS.values())

    def test_svg_has_rounded_apex_not_triangle(self, brand):
        svg = mountains_svg("core_3", brand.mountains, brand.colour_hex, width=1080, height=600)
        assert svg.count("<path") == 3
        assert " Q " in svg  # quadratic curve at the apex: no pointed triangles (p69)

    def test_unknown_variant_rejected(self, brand):
        with pytest.raises(KeyError):
            resolve_layers("sparkly_7", brand.mountains, brand.colour_hex)


def test_qr_encodes_a_url():
    uri = qr_data_uri("https://example.com/jane-tan")
    assert uri.startswith("data:image/png;base64,") and len(uri) > 500


class TestHtml:
    def test_families_available(self):
        assert {"festive-portrait", "event-information"} <= set(available_families())

    def test_html_embeds_brand_tokens_and_fonts(self, festive_ctx):
        html = build_html(festive_ctx)
        assert "#D31145" in html                      # AIA Red from tokens
        assert "AIAEverest" in html and "@font-face" in html
        assert "Jane Tan" in html                     # contact block from the profile
        assert "data:image/png;base64" in html        # QR embedded

    def test_unknown_family_rejected(self, festive_ctx):
        festive_ctx.design.layout_family = "canva-freestyle"
        with pytest.raises(KeyError, match="unknown layout family"):
            build_html(festive_ctx)


class TestRendering:
    def test_png_and_geometry_produced(self, rendered):
        design, res = rendered["festive"]
        assert res.image_path.exists() and res.image_path.stat().st_size > 20_000
        assert res.geometry["canvas"] == {"width": 1080, "height": 1350}
        assert {e["id"] for e in res.elements} >= {e.id for e in design.elements}

    def test_no_overflow_or_out_of_canvas_in_fixtures(self, rendered):
        for name, (_, res) in rendered.items():
            bad = [e["id"] for e in res.elements if e["overflows"] or e["outsideCanvas"]]
            assert not bad, f"{name}: {bad}"

    def test_real_fonts_applied(self, rendered):
        _, res = rendered["seminar"]
        assert "AIAEverest" in res.element("headline")["fontFamily"]

    def test_qr_target_is_the_verified_url(self, rendered):
        _, res = rendered["seminar"]
        assert res.element("qr")["qrTarget"] == "https://example.com/jane-tan/events"

    def test_preset_change_reflows_not_crops(self, tmp_path, brand, profile):
        story = fx.seminar_design()
        tall = apply_ops(story, [ChangePreset(preset="instagram_story")])
        ctx = RenderContext(design=tall, brief=fx.seminar_brief(), copy=fx.seminar_copy(),
                            profile=profile, brand=brand)
        res = render(ctx, tmp_path, name="story")
        assert res.geometry["canvas"] == {"width": 1080, "height": 1920}
        assert not [e["id"] for e in res.elements if e["overflows"] or e["outsideCanvas"]]
        # same content, taller canvas: the details panel keeps its position from the top
        assert res.element("event-venue")["text"] == "Marina Bay Sands, Expo Hall 3"

    def test_pdf_export(self, tmp_path, festive_ctx):
        res = render(festive_ctx, tmp_path, fmt="pdf", name="print")
        assert res.image_path.suffix == ".pdf" and res.image_path.stat().st_size > 5_000
