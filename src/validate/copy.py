"""D8 — deterministic copy checks (ADR-006: rules first, LLM second).

The important one is `no invented facts`: any date, time, price, percentage, phone number
or URL that appears in generated copy must already exist in the brief. This is the text-side
counterpart to keeping factual elements out of generated images (ADR-001).
"""

from __future__ import annotations

import datetime as dt
import re

from ..contracts.brief import CampaignBrief
from ..contracts.common import Family, Finding, Severity, ValidationReport
from ..contracts.copy import Copy
from ..policy.rules import PolicyDecision, find_prohibited

#: Capitalisation the Brand Standards require (pp. 5, 31).
CAPITALISATION = [
    (re.compile(r"\bhealthier,\s+longer,\s+better\s+lives\b", re.I),
     "Healthier, Longer, Better Lives", "brand.hlbl_caps"),
    (re.compile(r"\b(our|aia'?s)\s+purpose\b", re.I), "Purpose", "brand.purpose_caps"),
]

NUMERIC_PATTERNS = {
    "percentage": re.compile(r"\b\d+(?:\.\d+)?\s?%"),
    "money": re.compile(r"(?:S?\$|SGD)\s?\d[\d,]*(?:\.\d+)?", re.I),
    "phone": re.compile(r"(?:\+65\s?)?\b[689]\d{3}\s?\d{4}\b"),
    "url": re.compile(r"https?://\S+|\bwww\.\S+"),
    "time": re.compile(r"\b\d{1,2}(?:[:.]\d{2})?\s?(?:am|pm)\b", re.I),
    "date": re.compile(r"\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", re.I),
}

JARGON = ["utilise", "leverage", "synergy", "robust solution", "holistic suite", "vis-a-vis",
          "aforementioned", "pursuant to", "endeavour to", "in order to facilitate"]

FEAR_WORDS = ["don't miss out", "last chance", "act now", "hurry", "before it's too late",
              "you can't afford", "regret", "disaster"]


def _all_text(copy: Copy) -> str:
    return " ".join(v for v in copy.texts().values() if v)


def _brief_fact_text(brief: CampaignBrief) -> str:
    """Everything the copy is allowed to state, as a searchable blob."""
    parts: list[str] = []
    for fact in brief.facts:
        value = fact.value
        parts.append(str(value))
        if isinstance(value, dt.date):
            parts += [value.strftime("%-d %B %Y"), value.strftime("%-d %b"), value.strftime("%d/%m/%Y")]
        if isinstance(value, dt.time):
            parts += [value.strftime("%-I.%M%p").lower(), value.strftime("%-I%p").lower(),
                      value.strftime("%H:%M"), value.strftime("%-I:%M%p").lower()]
    if brief.cta:
        parts += [brief.cta.text, brief.cta.url or ""]
    return " ".join(parts).lower()


def validate_copy(copy: Copy, brief: CampaignBrief, decision: PolicyDecision,
                  *, min_flesch: float = 60.0) -> ValidationReport:
    findings: list[Finding] = []
    checks = 0
    text = _all_text(copy)
    known = _brief_fact_text(brief)

    def fail(rule: str, msg: str, *, sev: Severity = Severity.ERROR,
             evidence: str | None = None, fix: str | None = None) -> None:
        findings.append(Finding(rule_id=rule, severity=sev, message=msg, evidence=evidence, suggestion=fix))

    # ---- no invented facts ------------------------------------------------
    for kind, pattern in NUMERIC_PATTERNS.items():
        for match in pattern.findall(text):
            checks += 1
            needle = match.strip().lower().rstrip(".,")
            if needle.replace(" ", "") in known.replace(" ", ""):
                continue
            fail("facts.invented", f"Copy states a {kind} that is not in the brief: {match!r}",
                 evidence=match, fix="remove it, or add it to the brief as a sourced fact")

    # ---- prohibited wording and claims ------------------------------------
    for term in find_prohibited(text):
        checks += 1
        fail("copy.prohibited", f"Prohibited phrase {term!r}", evidence=term)
    for term in decision.prohibited_terms:
        if term in text.lower() and not any(f.evidence == term for f in findings):
            checks += 1
            fail("copy.prohibited", f"Prohibited phrase {term!r}", evidence=term)

    checks += 1
    ungrounded = [c.text for c in copy.claims if not c.is_grounded]
    if ungrounded:
        fail("claims.unsourced", f"{len(ungrounded)} claim(s) with no approved source",
             evidence="; ".join(ungrounded)[:200],
             fix="cite an approved product source or remove the claim")

    # ---- brand capitalisation ---------------------------------------------
    for pattern, correct, rule in CAPITALISATION:
        for match in pattern.findall(text) or []:
            checks += 1
            found = match if isinstance(match, str) else " ".join(match)
            if correct.lower().startswith(found.lower()) and found not in correct:
                fail(rule, f"{found!r} must be written as {correct!r}", sev=Severity.WARN, evidence=found)

    # ---- tone mechanics ----------------------------------------------------
    for word in JARGON:
        if word in text.lower():
            checks += 1
            fail("tone.jargon", f"Jargon: {word!r}", sev=Severity.WARN, evidence=word,
                 fix="use plain language (Brand Standards p18: simple words, short sentences)")
    for word in FEAR_WORDS:
        if word in text.lower():
            checks += 1
            fail("tone.fear", f"Fear or urgency wording: {word!r}", sev=Severity.WARN, evidence=word,
                 fix="AIA is positive and never negative (p18)")

    checks += 1
    # skip all-caps slots (headlines are set in capitals by the renderer, not the writer)
    mixed_case = " ".join(v for v in copy.texts().values() if v and v != v.upper())
    acronyms = {a for a in re.findall(r"\b[A-Z]{2,5}\b", mixed_case)
                if a not in {"AIA", "CPF", "SG", "MAS", "QR", "HLBL", "SGD"}}
    if acronyms:
        fail("tone.acronym", f"Unexplained acronym(s): {', '.join(sorted(acronyms))}",
             sev=Severity.WARN, fix="spell it out on first use (p18: avoid acronyms)")

    # ---- readability -------------------------------------------------------
    body = " ".join(t for t in [copy.subheadline, copy.body] if t)
    if len(body.split()) >= 12:
        checks += 1
        try:
            import textstat

            score = textstat.flesch_reading_ease(body)
            if score < min_flesch - 10:
                fail("copy.readability", f"Flesch score {score:.0f}; target is {min_flesch:.0f}+",
                     evidence=f"{score:.0f}", fix="shorter sentences, simpler words")
            elif score < min_flesch:
                fail("copy.readability", f"Flesch score {score:.0f}; target is {min_flesch:.0f}+",
                     sev=Severity.WARN, evidence=f"{score:.0f}")
        except ImportError:
            pass

    # ---- required content --------------------------------------------------
    checks += 1
    if brief.family in {Family.SEMINAR, Family.EVENT, Family.RECRUITMENT} and not copy.cta:
        fail("copy.cta_required", f"A {brief.family.value} campaign needs a call to action")

    checks += 1
    if len(copy.headline) > 60:
        fail("copy.headline_length", f"Headline is {len(copy.headline)} characters; keep it under 60",
             sev=Severity.WARN, fix="posters are read at a glance")

    return ValidationReport(checks_run=checks, findings=findings)


def disclaimer_text(decision: PolicyDecision) -> str | None:
    """The mandatory legal line(s) for this risk class, rendered as one block."""
    if not decision.required_disclaimers:
        return None
    order = ["underwritten_by", "not_contract", "read_contract", "ppf_scheme", "sdic_short",
             "info_general", "mas_not_reviewed"]
    parts = [decision.disclaimer_texts[k] for k in order if k in decision.disclaimer_texts]
    return " ".join(parts) or None
