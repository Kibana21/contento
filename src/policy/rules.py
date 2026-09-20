"""D2 — deterministic policy and risk engine (ADR-006/007).

Rules live in knowledge/campaign-rules/*.yaml so Compliance can change them without code.
An agent may *propose* a risk class; only this module decides, and it may only raise.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from ..contracts.brief import CampaignBrief
from ..contracts.common import Family, Risk, Strict

RULES_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "campaign-rules"
CLAUSES = Path(__file__).resolve().parent.parent.parent / "knowledge" / "disclaimers" / "aia-sg-web-clauses.json"


class PolicyDecision(Strict):
    """What the pipeline is allowed to do for this brief."""

    risk: Risk
    risk_reasons: list[str] = Field(default_factory=list)
    mandatory_fields: list[str] = Field(default_factory=list)
    blocking_fields: list[str] = Field(default_factory=list)
    missing_blocking: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    disclaimer_texts: dict[str, str] = Field(default_factory=dict)
    prohibited_terms: list[str] = Field(default_factory=list)
    export_presets: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    ai_forbidden_elements: list[str] = Field(
        default_factory=lambda: ["logo", "agent_photo", "fact", "qr", "disclaimer", "contact_block"]
    )
    rules_version: str = "0.1"

    @property
    def can_generate(self) -> bool:
        return not self.missing_blocking


@functools.lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    return yaml.safe_load((RULES_DIR / "families.yaml").read_text())


@functools.lru_cache(maxsize=1)
def load_festivals() -> dict[str, Any]:
    return yaml.safe_load((RULES_DIR / "festivals.yaml").read_text())["festivals"]


@functools.lru_cache(maxsize=1)
def _clause_library() -> dict[str, str]:
    """Shortest observed wording per disclaimer category, from the aia.com.sg corpus."""
    if not CLAUSES.exists():
        return {}
    data = json.loads(CLAUSES.read_text())
    out: dict[str, str] = {}
    for category, items in data.get("categories", {}).items():
        best = min(items, key=lambda c: (-c["page_count"], len(c["text"])))
        out[category] = best["text"]
    out.setdefault("info_general", "This information is for general information only.")
    return out


def _family_rules(family: Family) -> dict[str, Any]:
    rules = load_rules()
    fam = rules["families"].get(family.value, {})
    defaults = rules["defaults"]
    return {
        "risk": Risk(fam.get("risk", "amber")),
        "mandatory": [*defaults.get("mandatory", []), *fam.get("mandatory", [])],
        "blocking": [*defaults.get("blocking", []), *fam.get("blocking", [])],
        "disclaimers": fam.get("disclaimers", []),
        "export_presets": fam.get("export_presets", defaults.get("export_presets", [])),
        "requires_human_approval": bool(fam.get("requires_human_approval", False)),
    }


def scan_risk_triggers(text: str) -> tuple[Risk, list[str]]:
    """Look for wording that forces a higher risk class, regardless of the stated family."""
    rules = load_rules()
    lowered = f" {text.lower()} "
    hits_red = [t for t in rules["risk_triggers"]["red"] if t in lowered]
    hits_amber = [t for t in rules["risk_triggers"]["amber"] if t in lowered]
    if hits_red:
        return Risk.RED, [f"phrase {t!r} implies a product or financial claim" for t in hits_red]
    if hits_amber:
        return Risk.AMBER, [f"phrase {t!r} implies financial subject matter" for t in hits_amber]
    return Risk.GREEN, []


def find_prohibited(text: str) -> list[str]:
    lowered = text.lower()
    return [t for t in load_rules()["prohibited_terms"] if t in lowered]


def present_fields(brief: CampaignBrief) -> set[str]:
    """Dotted field names the brief can actually supply."""
    present = {f.field for f in brief.facts if f.value not in (None, "", [])}
    if brief.event:
        present |= {f"event.{k}" for k, v in brief.event.model_dump().items() if v not in (None, "", [])}
    if brief.cta:
        present.add("cta.text")
        if brief.cta.url:
            present.add("cta.url")
    if brief.festival:
        present.add("festival")
    present |= {"agent.name", "agent.title"}  # always available from the verified profile
    return present


def decide(brief: CampaignBrief, *, request_text: str = "", copy_text: str = "") -> PolicyDecision:
    """Combine family rules, trigger words and the agent's proposal into one decision."""
    fam = _family_rules(brief.family)
    reasons = [f"family {brief.family.value} starts at {fam['risk'].value}"]
    risk = fam["risk"]

    trigger_risk, trigger_reasons = scan_risk_triggers(" ".join([request_text, copy_text]))
    if trigger_risk.rank > risk.rank:
        risk = trigger_risk
        reasons.extend(dict.fromkeys(trigger_reasons))

    if brief.product_promotion and risk.rank < Risk.RED.rank:
        risk = Risk.RED
        reasons.append("brief marks this as product promotion")

    # the Brief Agent may raise the class, never lower it (ADR-005)
    if brief.risk_proposed.rank > risk.rank:
        risk = brief.risk_proposed
        reasons.append(f"brief agent raised risk to {brief.risk_proposed.value}")

    have = present_fields(brief)
    missing_blocking = sorted(f for f in fam["blocking"] if f not in have)

    disclaimers = list(fam["disclaimers"])
    if risk == Risk.RED:
        for extra in ("mas_not_reviewed", "underwritten_by", "not_contract", "read_contract",
                      "ppf_scheme", "sdic_short"):
            if extra not in disclaimers:
                disclaimers.append(extra)
    elif risk == Risk.AMBER and "mas_not_reviewed" not in disclaimers:
        disclaimers.append("mas_not_reviewed")

    library = _clause_library()
    return PolicyDecision(
        risk=risk,
        risk_reasons=reasons,
        mandatory_fields=fam["mandatory"],
        blocking_fields=fam["blocking"],
        missing_blocking=missing_blocking,
        required_disclaimers=disclaimers,
        disclaimer_texts={d: library[d] for d in disclaimers if d in library},
        prohibited_terms=load_rules()["prohibited_terms"],
        export_presets=fam["export_presets"],
        requires_human_approval=fam["requires_human_approval"] or risk == Risk.RED,
        rules_version=str(load_rules().get("version", "0.1")),
    )


# --------------------------------------------------------------------------- festivals
def resolve_festival(name: str, *, today: dt.date | None = None) -> dict[str, Any] | None:
    """Map 'diwali', 'CNY' or '农历新年' to the canonical festival and its next date."""
    today = today or dt.date.today()
    needle = re.sub(r"[^a-z一-鿿 ]", " ", name.lower()).strip()
    for key, spec in load_festivals().items():
        names = {key.replace("_", " "), *[a.lower() for a in spec.get("aliases", [])]}
        if needle and (needle in names or any(n in needle for n in names)):
            dates = {int(y): d for y, d in spec["dates"].items()}
            upcoming = sorted(d for d in dates.values() if d >= today) or sorted(dates.values())
            return {
                "festival": key,
                "date": upcoming[0],
                "confirm_with_user": bool(spec.get("confirm", False)),
                "greeting_window_days": int(spec.get("greeting_window_days", 7)),
            }
    return None
