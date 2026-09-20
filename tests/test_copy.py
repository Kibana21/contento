"""Copywriter, copy rules and the tone reviewer.

The deterministic checks are the safety net: the LLM reviewer only advises (ADR-006).
"""

import asyncio
import datetime as dt

import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from src.ai.copywriter import CopyDraft, voice_examples, write_copy
from src.ai.model_gateway import ModelGateway
from src.ai.reviewers import review_tone
from src.contracts.common import Family
from src.contracts.copy import Claim, Copy
from src.policy.rules import decide
from src.render import fixtures as fx
from src.validate.copy import disclaimer_text, validate_copy


def scripted(payload: dict) -> FunctionModel:
    def respond(messages, info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, payload)])
    return FunctionModel(respond)


def rules(report) -> set[str]:
    return {f.rule_id for f in report.findings}


@pytest.fixture
def seminar():
    brief = fx.seminar_brief()
    return brief, decide(brief)


class TestInventedFacts:
    """The text-side counterpart of ADR-001: copy may not state facts the brief lacks."""

    @pytest.mark.parametrize("text", [
        "Call me on +65 9000 1111",
        "Returns of 8% await",
        "Only S$2,000 to start",
        "Visit https://not-in-brief.example",
        "Doors open 6.30pm",
        "See you on 3 December",
    ])
    def test_unknown_facts_are_rejected(self, seminar, text):
        brief, dec = seminar
        report = validate_copy(Copy(headline="A retirement that is yours", body=text), brief, dec)
        assert "facts.invented" in rules(report)

    def test_facts_present_in_the_brief_are_allowed(self, seminar):
        brief, dec = seminar
        copy = Copy(headline="Join me", body="We meet on 18 October 2026 at Marina Bay Sands.")
        assert "facts.invented" not in rules(validate_copy(copy, brief, dec))

    def test_profile_phone_is_allowed(self, seminar):
        brief, dec = seminar
        copy = Copy(headline="Talk to me", body="Reach me any time on +65 9123 4567.")
        assert "facts.invented" not in rules(validate_copy(copy, brief, dec))


class TestProhibitedAndClaims:
    def test_prohibited_phrase(self, seminar):
        brief, dec = seminar
        assert "copy.prohibited" in rules(validate_copy(
            Copy(headline="A risk-free plan for you"), brief, dec))

    def test_unsourced_claim(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="Protection that pays",
                                    claims=[Claim(text="Covers 100 conditions")]), brief, dec)
        assert "claims.unsourced" in rules(report)

    def test_sourced_claim_passes(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="Protection that pays",
                                    claims=[Claim(text="Covers 100 conditions",
                                                  source_ref="brochure:aia-protect-3#p4")]), brief, dec)
        assert "claims.unsourced" not in rules(report)


class TestToneMechanics:
    def test_jargon_and_fear_are_flagged(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="Act now before it's too late",
                                    body="We utilise a robust solution to leverage your savings."),
                               brief, dec)
        assert {"tone.jargon", "tone.fear"} <= rules(report)

    def test_capitals_in_headline_are_not_read_as_acronyms(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="A RETIREMENT THAT IS TRULY YOURS"), brief, dec)
        assert "tone.acronym" not in rules(report)

    def test_real_acronym_is_flagged(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="Plan ahead", body="Ask me about your ILP and SRS today."),
                               brief, dec)
        assert "tone.acronym" in rules(report)

    def test_brand_capitalisation(self, seminar):
        brief, dec = seminar
        report = validate_copy(Copy(headline="Live well", body="We help you live healthier, longer, better lives."),
                               brief, dec)
        assert "brand.hlbl_caps" in rules(report)

    def test_long_headline_warned(self, seminar):
        brief, dec = seminar
        long_head = "A retirement that is truly yours, planned carefully together with me"
        assert "copy.headline_length" in rules(validate_copy(Copy(headline=long_head), brief, dec))


class TestRequiredContent:
    def test_seminar_needs_a_cta(self, seminar):
        brief, dec = seminar
        assert "copy.cta_required" in rules(validate_copy(Copy(headline="Join me"), brief, dec))

    def test_festive_does_not(self):
        brief = fx.festive_brief()
        report = validate_copy(Copy(headline="Happy Deepavali"), brief, decide(brief))
        assert "copy.cta_required" not in rules(report)

    def test_disclaimer_text_is_selected_by_risk(self, seminar):
        _, dec = seminar
        assert "Monetary Authority" in disclaimer_text(dec)
        assert disclaimer_text(decide(fx.festive_brief())) is None


class TestVoiceExamples:
    def test_examples_are_real_headlines(self):
        examples = voice_examples(Family.FESTIVE, limit=6)
        assert examples and all(4 <= len(e.split()) and len(e) <= 62 for e in examples)

    def test_navigation_noise_is_excluded(self):
        joined = " ".join(e for f in Family for e in voice_examples(f, limit=10)).lower()
        assert "submit" not in joined and "step 1" not in joined and "faq" not in joined

    def test_deterministic(self):
        assert voice_examples(Family.SEMINAR) == voice_examples(Family.SEMINAR)


class TestCopywriter:
    def test_draft_is_assembled_with_profile_signature(self, profile, seminar):
        brief, dec = seminar
        gw = ModelGateway(test_model=scripted({
            "headline": "A retirement that is yours",
            "subheadline": "Planning made approachable",
            "body": "Join me for an evening about the retirement you want.",
            "cta": "Register now", "claims": []}))
        copy = asyncio.run(write_copy(gw, brief, profile, dec))
        assert copy.signature == "Jane Tan"          # filled from the verified profile
        assert copy.cta == "Register now"
        assert gw.summary()["tokens_by_node"]["copywriter"] > 0

    def test_cta_falls_back_to_the_brief(self, profile, seminar):
        brief, dec = seminar
        gw = ModelGateway(test_model=scripted({"headline": "A retirement that is yours", "claims": []}))
        assert asyncio.run(write_copy(gw, brief, profile, dec)).cta == "Register now"

    def test_generated_copy_passes_the_rules(self, profile, seminar):
        """A well-behaved draft must not trip the deterministic checks."""
        brief, dec = seminar
        gw = ModelGateway(test_model=scripted({
            "headline": "A retirement that is truly yours",
            "subheadline": "An approachable guide to planning with confidence",
            "body": "It is never too late to feel sure about the years ahead. Join me and let us plan them.",
            "cta": "Register now", "claims": []}))
        copy = asyncio.run(write_copy(gw, brief, profile, dec))
        assert validate_copy(copy, brief, dec).passed


def test_tone_reviewer_is_advisory_only(profile, seminar):
    """Reviewer findings are warnings: they never block, and never approve."""
    brief, _ = seminar
    gw = ModelGateway(test_model=scripted({
        "findings": [{"issue": "The closing line feels a little salesy", "severity": "error"}],
        "overall": "Warm and clear"}))
    report = asyncio.run(review_tone(gw, fx.seminar_copy(), brief))
    assert len(report.findings) == 1
    assert report.findings[0].severity.value == "warn" and report.passed
