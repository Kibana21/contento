"""Folder loaders and brand pack resolution."""

import pytest

from src.contracts.profile import PhotoKind
from src.loaders import LoaderError, load_brand_pack, load_profile, load_request


def test_demo_profile_loads_with_photos_and_contacts():
    p = load_profile("profiles/demo-agent")
    assert p.display_name == "Jane Tan"
    assert p.mobile == "+65 9123 4567"
    assert {ph.id for ph in p.photos} >= {"formal", "casual"}
    assert p.photo(None).id == "formal"  # preferred_photo honoured
    assert p.contact_facts()["agent.email"] == "jane.tan@example.com"
    assert PhotoKind.FORMAL in {ph.kind for ph in p.photos}


def test_missing_profile_raises(tmp_path):
    with pytest.raises(LoaderError, match="no profile.yaml"):
        load_profile(tmp_path)


def test_request_loads_and_lists_artifacts(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "request.md").write_text("Create a Deepavali greeting.")
    (tmp_path / "assets" / "agenda.pdf").write_bytes(b"%PDF-1.4")
    text, artifacts = load_request(tmp_path)
    assert "Deepavali" in text
    assert [a.id for a in artifacts] == ["agenda"]
    assert artifacts[0].mime == "application/pdf"


def test_empty_request_rejected(tmp_path):
    (tmp_path / "request.md").write_text("   ")
    with pytest.raises(LoaderError, match="empty"):
        load_request(tmp_path)


class TestBrandPack:
    def setup_method(self):
        self.b = load_brand_pack()

    def test_core_colours_are_brand_standards_values(self):
        assert self.b.red == "#D31145"      # AIA Red, Pantone 200C
        assert self.b.charcoal == "#333D47"  # AIA Charcoal, Pantone 432C

    def test_tint_and_secondary_resolution(self):
        assert self.b.colour_hex("core.red.20") == "#F6CFD9"
        assert self.b.colour_hex("secondary.blue") == "#1F78AD"
        assert self.b.colour_hex("secondary.gold.40") == "#EADFC9"

    def test_unknown_token_raises(self):
        with pytest.raises(KeyError):
            self.b.colour_hex("brand.turquoise")

    def test_rules_exposed_for_validators(self):
        assert self.b.max_secondary_colours == 4
        assert self.b.min_text_contrast == 4.5
        assert len(self.b.allowed_logo_positions) == 7

    def test_assets_present(self):
        assert self.b.logo_path("red").exists()
        assert self.b.logo_path("white").exists()
        assert self.b.font_path("display_medium").exists()
        with pytest.raises(KeyError):
            self.b.logo_path("blue")

    def test_typography_ratios(self):
        h = self.b.hierarchy()
        assert h["subheading_to_headline_ratio"] == pytest.approx(1 / 3, abs=1e-3)
        assert h["min_body_size"]["digital_px"] == 15
        assert "headline" in self.b.type_scale()

    def test_policies_loaded(self):
        assert {"colour", "logo-rules", "moving-mountains", "tone-of-voice"} <= set(self.b.policies)
