"""Policy engine: rules decide risk, not the model (ADR-005/006/007)."""

import datetime as dt

import pytest

from src.contracts.brief import AgentRef, CampaignBrief, EventDetails, Story
from src.contracts.common import Family, Risk
from src.policy.rules import (decide, find_prohibited, load_rules, present_fields,
                              resolve_festival, scan_risk_triggers)
from src.render import fixtures as fx


def brief(**kw) -> CampaignBrief:
    base = dict(campaign_id="CAM-1", family=Family.FESTIVE, objective="relationship",
                agent=AgentRef(profile_id="demo-agent"),
                story=Story(core_message="m", emotional_tone="warm"), festival="deepavali")
    return CampaignBrief(**(base | kw))


class TestRiskClassification:
    def test_festive_is_green(self):
        assert decide(brief()).risk is Risk.GREEN

    def test_seminar_is_amber(self):
        assert decide(fx.seminar_brief()).risk is Risk.AMBER

    def test_product_wording_forces_red(self):
        d = decide(brief(), request_text="Our plan gives guaranteed returns of 4% p.a.")
        assert d.risk is Risk.RED and d.requires_human_approval
        assert any("guaranteed return" in r for r in d.risk_reasons)

    def test_financial_wording_raises_green_to_amber(self):
        assert decide(brief(), request_text="a short note about retirement planning").risk is Risk.AMBER

    def test_agent_may_raise_risk(self):
        assert decide(brief(risk_proposed=Risk.RED)).risk is Risk.RED

    def test_agent_cannot_lower_risk(self):
        """A model claiming 'green' on a seminar must not win."""
        b = fx.seminar_brief()
        b.risk_proposed = Risk.GREEN
        assert decide(b).risk is Risk.AMBER

    def test_product_promotion_flag_forces_red(self):
        assert decide(brief(product_promotion=True)).risk is Risk.RED


class TestMandatoryFields:
    def test_seminar_without_venue_is_blocked(self):
        b = fx.seminar_brief()
        b.event = EventDetails(title="Seminar", date=dt.date(2026, 10, 18))
        b.facts = [f for f in b.facts if f.field != "event.venue"]
        d = decide(b)
        assert "event.venue" in d.missing_blocking and not d.can_generate

    def test_complete_seminar_can_generate(self):
        assert decide(fx.seminar_brief()).can_generate

    def test_festive_needs_a_festival(self):
        b = brief(festival=None)
        assert "festival" in decide(b).missing_blocking

    def test_profile_fields_always_count_as_present(self):
        assert {"agent.name", "agent.title"} <= present_fields(brief())


class TestDisclaimers:
    def test_green_needs_none(self):
        assert decide(brief()).required_disclaimers == []

    def test_amber_requires_mas_line(self):
        d = decide(fx.seminar_brief())
        assert "mas_not_reviewed" in d.required_disclaimers
        assert "Monetary Authority of Singapore" in d.disclaimer_texts["mas_not_reviewed"]

    def test_red_requires_the_full_set(self):
        d = decide(brief(product_promotion=True))
        assert {"mas_not_reviewed", "underwritten_by", "not_contract", "ppf_scheme"} <= set(d.required_disclaimers)

    def test_texts_come_from_the_observed_corpus(self):
        d = decide(brief(product_promotion=True))
        assert "AIA Singapore Private Limited" in d.disclaimer_texts["underwritten_by"]


class TestProhibitedAndTriggers:
    def test_prohibited_terms_found(self):
        assert set(find_prohibited("A risk-free way to double your money")) == {"risk-free", "double your money"}

    @pytest.mark.parametrize("text,expected", [
        ("sum assured of $500,000", Risk.RED),
        ("join my CPF workshop", Risk.AMBER),
        ("wishing you a happy new year", Risk.GREEN),
    ])
    def test_trigger_scan(self, text, expected):
        assert scan_risk_triggers(text)[0] is expected


class TestFestivals:
    def test_alias_resolution(self):
        assert resolve_festival("diwali", today=dt.date(2026, 9, 20))["festival"] == "deepavali"
        assert resolve_festival("CNY", today=dt.date(2026, 9, 20))["festival"] == "chinese_new_year"

    def test_next_occurrence_is_chosen(self):
        assert resolve_festival("christmas", today=dt.date(2026, 9, 20))["date"] == dt.date(2026, 12, 25)
        assert resolve_festival("christmas", today=dt.date(2026, 12, 26))["date"] == dt.date(2027, 12, 25)

    def test_moon_dependent_festivals_need_confirmation(self):
        """Deepavali and Hari Raya dates are officially confirmed, so we must ask."""
        assert resolve_festival("deepavali", today=dt.date(2026, 1, 1))["confirm_with_user"]
        assert resolve_festival("hari raya puasa", today=dt.date(2026, 1, 1))["confirm_with_user"]
        assert not resolve_festival("national day", today=dt.date(2026, 1, 1))["confirm_with_user"]

    def test_unknown_festival(self):
        assert resolve_festival("pancake day") is None


def test_rules_are_data_not_code():
    rules = load_rules()
    assert set(rules["families"]) >= {f.value for f in Family}
    assert rules["status"].startswith("draft")
