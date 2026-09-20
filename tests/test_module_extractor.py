"""Repeating content must come from the upload, not from the model's memory.

A speaker's bio and a product's benefit are facts. These tests pin the boundary between
transcription (allowed — a PDF's typographic quotes retyped as ASCII) and invention (not,
however plausible it sounds).
"""

from __future__ import annotations

import pytest

from src.ai.module_extractor import (ProposedItem, build_items, is_sourced, merge, normalise,
                                     summarise, verify)
from src.contracts.content import ContentSet

SOURCE = """AIA Career Seminar — Speakers

MANAGEMENT SPEAKER
Wong Sze Keed, CEO of AIA Singapore
Ms Wong will be sharing on the importance of insurance, insights of this career
and what AIA offers to our Consultants.

KEYNOTE SPEAKER
Rachel Lim, Co-founder of Love, Bonito
Rachel co-founded Love, Bonito at the age of 19. She was honored by Forbes as
Asia 30under30 in 2016.
"""


def item(**kw) -> ProposedItem:
    return ProposedItem(**kw)


class TestSourcing:
    def test_a_quotation_is_accepted(self):
        assert is_sourced("Rachel co-founded Love, Bonito at the age of 19", SOURCE)

    def test_an_invention_is_refused(self):
        assert not is_sourced("Singapore's most influential entrepreneur", SOURCE)

    def test_a_changed_figure_is_refused(self):
        """The whole point: 19 is in the document, 29 is not."""
        assert is_sourced("at the age of 19", SOURCE)
        assert not is_sourced("at the age of 29", SOURCE)

    @pytest.mark.parametrize("claim", [
        "CEO OF AIA SINGAPORE",                     # case
        "  CEO of AIA Singapore  ",                 # surrounding space
        "CEO of AIA Singapore.",                    # trailing punctuation
        "CEO of  AIA   Singapore",                  # collapsed whitespace
    ])
    def test_cosmetic_tidying_is_transcription_not_invention(self, claim):
        assert is_sourced(claim, SOURCE)

    def test_reordering_words_is_invention(self):
        assert not is_sourced("AIA Singapore CEO of", SOURCE)

    def test_an_empty_claim_is_never_sourced(self):
        assert not is_sourced("", SOURCE)
        assert not is_sourced("   ", SOURCE)

    def test_normalise_folds_typography(self):
        assert normalise("Love Bonito") == normalise("Love Bonito")


class TestBuildItems:
    def test_accepted_items_are_stamped_and_locked(self):
        accepted, rejected = build_items(
            [item(label="Rachel Lim", role="Co-founder of Love, Bonito")],
            "speaker", SOURCE, "speakers")
        assert not rejected
        assert accepted[0].source == "artifact:speakers"
        assert accepted[0].verbatim and accepted[0].locked
        assert accepted[0].id == "speaker-0"

    def test_an_embellished_bio_is_rejected_with_its_reason(self):
        accepted, rejected = build_items(
            [item(label="Rachel Lim", body="Singapore's most influential entrepreneur")],
            "speaker", SOURCE, "speakers")
        assert not accepted and "not found in the document" in rejected[0]

    def test_a_wholly_invented_speaker_is_rejected(self):
        accepted, rejected = build_items(
            [item(label="Kevin Tan", role="Regional Director")],
            "speaker", SOURCE, "speakers")
        assert not accepted and rejected

    def test_one_bad_field_rejects_the_item(self):
        """Partial acceptance would put an invented line beside a real name."""
        accepted, _ = build_items(
            [item(label="Rachel Lim", role="Co-founder of Love, Bonito",
                  body="Winner of every award going")],
            "speaker", SOURCE, "speakers")
        assert not accepted

    def test_ids_continue_from_an_offset(self):
        accepted, _ = build_items([item(label="Wong Sze Keed")], "speaker", SOURCE,
                                  "speakers", start=3)
        assert accepted[0].id == "speaker-3"

    def test_an_empty_proposal_is_rejected(self):
        accepted, rejected = build_items([item()], "speaker", SOURCE, "speakers")
        assert not accepted and "no text" in rejected[0]

    def test_a_quoted_figure_survives_the_contentitem_rule(self):
        """ContentItem refuses unquoted figures; verified items are verbatim, so they pass."""
        accepted, rejected = build_items(
            [item(label="Rachel Lim", body="Asia 30under30 in 2016")],
            "speaker", SOURCE, "speakers")
        assert accepted and not rejected


class TestMergeAndReport:
    def test_merge_appends_without_duplicating(self):
        first, _ = build_items([item(label="Wong Sze Keed")], "speaker", SOURCE, "speakers")
        merged = merge(ContentSet(items=first), first)
        assert len(merged.items) == 1

    def test_the_model_is_told_what_was_rejected(self):
        """Visible rejection is what lets the agent correct itself instead of shipping it."""
        accepted, rejected = build_items(
            [item(label="Kevin Tan")], "speaker", SOURCE, "speakers")
        report = summarise("speaker", accepted, rejected)
        assert report["kind"] == "speakers" and report["rejected"]
        assert "from memory" in report["note"]

    def test_verify_names_the_offending_fields(self):
        missing = verify(item(label="Rachel Lim", body="invented text"), SOURCE)
        assert missing == ["body"]
