"""The Art Director, offline.

Two things matter here: a model proposal is filtered rather than trusted, and the set that
comes out is genuinely four different ideas rather than one idea four times.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.ai.art_director import (ARCHETYPES, DesignSystemSetDraft, fallback_design_systems,
                                 to_design_systems)
from src.freeform.contracts import DesignSystemSet


def draft(vid: str, archetype: str, *, ground="light", motif="ring", rules=None) -> dict:
    return {"variation_id": vid, "name": f"System {vid}", "archetype": archetype,
            "ground": ground, "type_pairing": "display-led", "primary_motif": motif,
            "image_treatment": "cutout", "rules": rules or []}


class TestConversion:
    def test_a_clean_draft_becomes_a_system(self):
        systems, rejected = to_design_systems(DesignSystemSetDraft(systems=[
            draft("a", "speaker-roster", rules=[
                {"selector": ".headline", "declarations": {"font-size": "90px",
                                                           "color": "var(--red)"}}]),
            draft("b", "benefit-grid", ground="bold", motif="pill"),
            draft("c", "chip-index", motif="hairline-rule"),
        ]))
        assert not rejected and len(systems) == 3
        assert systems[0].rules[0].declarations["color"] == "var(--red)"

    def test_a_raw_hex_is_dropped_but_the_rule_survives(self):
        """One bad declaration must not cost the whole stylesheet."""
        systems, rejected = to_design_systems(DesignSystemSetDraft(systems=[
            draft("a", "speaker-roster", rules=[
                {"selector": ".headline",
                 "declarations": {"font-size": "90px", "color": "#00FF00"}}]),
            draft("b", "benefit-grid", ground="bold", motif="pill"),
            draft("c", "chip-index", motif="hairline-rule"),
        ]))
        assert systems[0].rules[0].declarations == {"font-size": "90px"}
        assert any("brand token" in r for r in rejected)

    @pytest.mark.parametrize("prop,value", [
        ("content", '"0.35% p.a."'),
        ("display", "none"),
        ("font-family", "Comic Sans MS"),
        ("clip-path", "inset(100%)"),
    ])
    def test_forbidden_declarations_never_reach_a_system(self, prop, value):
        systems, rejected = to_design_systems(DesignSystemSetDraft(systems=[
            draft("a", "speaker-roster",
                  rules=[{"selector": ".legal", "declarations": {prop: value}}]),
            draft("b", "benefit-grid", ground="bold", motif="pill"),
            draft("c", "chip-index", motif="hairline-rule"),
        ]))
        assert systems[0].rules == [] and rejected

    def test_an_invalid_selector_is_reported_not_raised(self):
        systems, rejected = to_design_systems(DesignSystemSetDraft(systems=[
            draft("a", "speaker-roster",
                  rules=[{"selector": ".a::before", "declarations": {"color": "var(--red)"}}]),
            draft("b", "benefit-grid", ground="bold", motif="pill"),
            draft("c", "chip-index", motif="hairline-rule"),
        ]))
        assert systems[0].rules == [] and rejected


class TestDistinctness:
    def test_a_converged_set_is_refused(self):
        """Four variations of one idea is the complaint that started this work."""
        systems, _ = to_design_systems(DesignSystemSetDraft(systems=[
            draft("a", "speaker-roster"), draft("b", "speaker-roster"),
            draft("c", "speaker-roster"),
        ]))
        with pytest.raises(ValidationError):
            DesignSystemSet(systems=systems)

    def test_the_fallback_is_always_valid(self):
        for count in (3, 4):
            systems = fallback_design_systems(count)
            assert len(systems.systems) == count
            assert len({s.archetype for s in systems.systems}) == count
            assert {s.ground for s in systems.systems} >= {"bold", "light"}

    def test_archetypes_are_preassigned_in_order(self):
        """Pre-assigning the idea per variation is what actually prevents convergence."""
        assert ARCHETYPES[:4] == ("speaker-roster", "benefit-grid", "editorial-feature",
                                  "chip-index")
