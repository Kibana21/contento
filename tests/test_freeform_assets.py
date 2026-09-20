"""Asset resolution — the only route by which an image reaches a free-form page.

Authored markup carries no `src` and contains no `<svg>`, so everything visual comes through
`resolve_asset`. These tests cover the refusals, because those are the guarantees.
"""

from __future__ import annotations

import pytest

from src.freeform.assets import AssetError, normalise_icon, resolve_asset
from src.render import fixtures as fx
from src.render.context import RenderContext


@pytest.fixture
def ctx(brand, profile):
    return RenderContext(brief=fx.seminar_brief(), copy=fx.seminar_copy(),
                         profile=profile, brand=brand)


class TestApprovedAssets:
    def test_the_logo_comes_from_the_brand_pack(self, ctx):
        for colour in ("red", "white"):
            asset = resolve_asset(f"brand.logo.{colour}", ctx)
            assert asset.kind == "src" and colour in asset.src and asset.src.endswith(".svg")

    def test_a_logo_may_only_be_red_or_white(self, ctx):
        """Brand Standards p39 — and a model may not invent a third."""
        with pytest.raises(AssetError) as e:
            resolve_asset("brand.logo.blue", ctx)
        assert e.value.rule_id == "logo.colour"

    def test_the_qr_encodes_a_verified_url(self, ctx):
        asset = resolve_asset("generated.qr", ctx)
        assert asset.src.startswith("data:image/png;base64,")

    def test_mountains_are_generated_not_authored(self, ctx):
        asset = resolve_asset("mountains.core_3", ctx)
        assert asset.kind == "svg" and asset.svg.count("<path") >= 3

    def test_an_unknown_mountains_variant_is_refused(self, ctx):
        with pytest.raises(AssetError) as e:
            resolve_asset("mountains.nope", ctx)
        assert e.value.rule_id == "mountains.variant"

    def test_the_portrait_is_always_the_cut_out(self, ctx):
        """Shaping is CSS on this path, so no pre-baked frame is needed."""
        asset = resolve_asset("profile.photo.formal", ctx)
        assert asset.kind == "src" and "cutout" in asset.src

    @pytest.mark.parametrize("ref", ["wat.xyz", "script.evil", "file:///etc/passwd"])
    def test_unknown_references_are_refused(self, ctx, ref):
        with pytest.raises(AssetError) as e:
            resolve_asset(ref, ctx)
        assert e.value.rule_id == "asset.unknown"


class TestIcons:
    def test_a_missing_catalogue_says_so_plainly(self, ctx):
        """AIA's icon library is an outstanding item; this must not look like a bug."""
        with pytest.raises(AssetError) as e:
            resolve_asset("icon.shield", ctx)
        assert e.value.rule_id in {"asset.no_catalogue", "asset.unknown"}

    def test_an_unknown_product_icon_is_refused(self, ctx):
        with pytest.raises(AssetError) as e:
            resolve_asset("icon.product.unicorn", ctx)
        assert e.value.rule_id == "asset.unknown"

    def test_normalisation_strips_text_nodes(self):
        """A catalogue file must not be able to smuggle text onto a poster."""
        out = normalise_icon('<svg><title>t</title><text>0.35%</text>'
                             '<path d="M1 2"/></svg>')
        assert "0.35%" not in out and "<text" not in out and "<title" not in out
        assert '<path d="M1 2"/>' in out

    def test_normalisation_strips_behaviour_and_styling(self):
        out = normalise_icon('<svg><path d="M1 2" onclick="x()" style="display:none" '
                             'fill="#00FF00"/></svg>')
        assert "onclick" not in out and "style" not in out and "00FF00" not in out

    def test_normalisation_makes_icons_follow_the_css_colour(self):
        """currentColor keeps the palette token-bound with no image processing."""
        assert 'stroke="currentColor"' in normalise_icon('<svg><circle cx="5" cy="5" r="3"/></svg>')

    def test_an_icon_with_no_geometry_is_refused(self):
        with pytest.raises(AssetError) as e:
            normalise_icon("<svg><title>nothing</title></svg>")
        assert e.value.rule_id == "asset.icon_empty"
