"""Structured content, design systems and storyboards.

The rules that matter here are the ones a model cannot talk its way past: a figure must be
quoted rather than paraphrased, and four variations must be genuinely different.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.contracts.content import ContentItem, ContentSet
from src.freeform.contracts import (DesignSystem, DesignSystemSet, FreeformDoc, FreeformPage,
                                    PagePlan, Storyboard)
from src.freeform.css import CssRule


NAMES = ["Wong Sze Keed", "Rachel Lim", "Torres Dalaine Ong", "Nur Aisyah Zainudin"]


def speaker(n: int, **kw) -> ContentItem:
    return ContentItem(id=f"speaker-{n}", kind="speaker", label=NAMES[n],
                       role="Consultant", body="A short bio.", source="artifact:speakers", **kw)


def system(vid: str, **kw) -> DesignSystem:
    base = dict(variation_id=vid, name=f"System {vid}", archetype="benefit-grid",
                ground="light", type_pairing="editorial", primary_motif="hairline-rule",
                image_treatment="cutout")
    return DesignSystem(**(base | kw))


class TestContentItem:
    def test_source_is_required(self):
        with pytest.raises(ValidationError):
            ContentItem(id="b-1", kind="benefit", label="Future retirement")

    def test_a_paraphrased_figure_is_rejected(self):
        """A paraphrased benefit is a style choice; a paraphrased number is a misstatement."""
        with pytest.raises(ValidationError) as e:
            ContentItem(id="b-1", kind="benefit", label="0.35% p.a. bonus",
                        source="artifact:brochure")
        assert "verbatim" in str(e.value)

    def test_a_quoted_figure_is_allowed(self):
        item = ContentItem(id="b-1", kind="benefit", label="0.35% p.a. bonus",
                           source="artifact:brochure", verbatim=True)
        assert item.verbatim and "0.35%" in item.text()

    def test_text_gathers_every_printable_field(self):
        item = speaker(1, value=None)
        assert "Rachel Lim" in item.text() and "Consultant" in item.text()

    def test_a_bare_numeral_is_not_a_claim(self):
        """'3 ways to plan' is a label, not a figure — same boundary as facts.invented."""
        assert ContentItem(id="b-1", kind="benefit", label="3 ways to plan",
                           source="user").label


class TestContentSet:
    def test_duplicate_ids_are_rejected(self):
        with pytest.raises(ValidationError):
            ContentSet(items=[speaker(1), speaker(1)])

    def test_group_accepts_singular_or_plural(self):
        cs = ContentSet(items=[speaker(0), speaker(1)])
        assert len(cs.group("speaker")) == len(cs.group("speakers")) == 2

    def test_counts_drive_page_sizing(self):
        cs = ContentSet(items=[speaker(0), speaker(1), speaker(2)])
        assert cs.counts() == {"speakers": 3}

    def test_resolve_addresses_an_item_field(self):
        cs = ContentSet(items=[speaker(0), speaker(1)])
        assert cs.resolve("speakers.1.label") == "Rachel Lim"
        assert cs.resolve("speakers.0.role") == "Consultant"

    @pytest.mark.parametrize("key,fragment", [
        ("speakers.9.label", "does not exist"),
        ("speakers.0.nickname", "addressable"),
        ("aliens.0.label", "unknown content kind"),
        ("speakers.x.label", "not a number"),
        ("speakers.0", "must be"),
    ])
    def test_resolve_fails_loudly(self, key, fragment):
        """A silent blank on a poster is worse than a loud failure."""
        with pytest.raises(KeyError) as e:
            ContentSet(items=[speaker(0)]).resolve(key)
        assert fragment in str(e.value)


class TestDesignSystemSet:
    def test_a_distinct_set_is_accepted(self):
        assert len(DesignSystemSet(systems=[
            system("a", archetype="benefit-grid", primary_motif="hairline-rule"),
            system("b", archetype="speaker-roster", primary_motif="ring", ground="bold"),
            system("c", archetype="editorial-feature", primary_motif="column-rule"),
            system("d", archetype="chip-index", primary_motif="pill"),
        ]).systems) == 4

    def test_two_variations_may_not_share_an_archetype(self):
        with pytest.raises(ValidationError) as e:
            DesignSystemSet(systems=[
                system("a", archetype="benefit-grid"),
                system("b", archetype="benefit-grid", ground="bold", primary_motif="ring"),
                system("c", archetype="chip-index", primary_motif="pill"),
            ])
        assert "different archetype" in str(e.value)

    def test_the_set_needs_a_bold_and_a_light_ground(self):
        with pytest.raises(ValidationError) as e:
            DesignSystemSet(systems=[
                system("a", archetype="benefit-grid"),
                system("b", archetype="speaker-roster", primary_motif="ring"),
                system("c", archetype="chip-index", primary_motif="pill"),
            ])
        assert "bold" in str(e.value)

    def test_four_variations_need_three_distinct_motifs(self):
        with pytest.raises(ValidationError) as e:
            DesignSystemSet(systems=[
                system("a", archetype="benefit-grid", primary_motif="pill"),
                system("b", archetype="speaker-roster", primary_motif="pill", ground="bold"),
                system("c", archetype="chip-index", primary_motif="ring"),
                system("d", archetype="editorial-feature", primary_motif="ring"),
            ])
        assert "distinct motifs" in str(e.value)

    def test_custom_classes_are_validated_on_the_system(self):
        with pytest.raises(ValidationError):
            system("a", custom_classes=["headline"])   # shadows a core class

    def test_by_id(self):
        s = DesignSystemSet(systems=[
            system("a"), system("b", archetype="speaker-roster", ground="bold",
                                primary_motif="ring"),
            system("c", archetype="chip-index", primary_motif="pill")])
        assert s.by_id("b").archetype == "speaker-roster"
        with pytest.raises(KeyError):
            s.by_id("z")


class TestStoryboard:
    def page(self, index=1, **kw):
        base = dict(index=index, purpose="invite",
                    must_include=["copy.headline", "brand.logo.red"])
        return PagePlan(**(base | kw))

    def test_a_single_page_storyboard(self):
        assert not Storyboard(pages=[self.page()]).is_multipage

    def test_page_one_must_carry_the_headline(self):
        with pytest.raises(ValidationError) as e:
            Storyboard(pages=[self.page(must_include=["brand.logo.red"])])
        assert "headline" in str(e.value)

    def test_page_one_must_carry_the_logo(self):
        with pytest.raises(ValidationError) as e:
            Storyboard(pages=[self.page(must_include=["copy.headline"])])
        assert "logo" in str(e.value)

    def test_pages_are_numbered_from_one(self):
        with pytest.raises(ValidationError) as e:
            Storyboard(pages=[self.page(index=2)])
        assert "numbered" in str(e.value)

    def test_a_reference_may_not_appear_on_two_pages(self):
        """One fact, one treatment — otherwise the same date could differ between pages."""
        with pytest.raises(ValidationError) as e:
            Storyboard(pages=[
                self.page(1, must_include=["copy.headline", "brand.logo.red", "facts.event.date"]),
                self.page(2, purpose="details", must_include=["facts.event.date"]),
            ])
        assert "more than one page" in str(e.value)

    def test_requires(self):
        board = Storyboard(pages=[self.page(must_include=["copy.headline", "brand.logo.red",
                                                          "policy.disclaimer"])])
        assert board.requires("policy.disclaimer") and not board.requires("generated.qr")


class TestFreeformDoc:
    def doc(self) -> FreeformDoc:
        return FreeformDoc(
            doc_id="CAM-2026-x-a", campaign_id="CAM-2026-x", variation_id="a",
            system=system("a", rules=[CssRule(selector=".headline",
                                              declarations={"font-size": "90px"})]),
            pages=[FreeformPage(plan=PagePlan(index=1, purpose="invite",
                                              must_include=["copy.headline", "brand.logo.red"]),
                                html="<div class='page'></div>")])

    def test_versioning_matches_designdoc_semantics(self):
        v2 = self.doc().next_version()
        assert v2.version == 2 and v2.parent_version == 1

    def test_it_round_trips_through_json(self):
        original = self.doc()
        restored = FreeformDoc.model_validate_json(original.model_dump_json())
        assert restored.system.rules[0].declarations["font-size"] == "90px"
