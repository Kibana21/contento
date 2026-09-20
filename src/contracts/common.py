"""Shared primitives: facts, sources, findings, budgets, usage."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Strict(BaseModel):
    """Base for every contract: reject unknown keys so model drift fails loudly."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class Family(StrEnum):
    FESTIVE = "festive"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    SEMINAR = "seminar"
    RECRUITMENT = "recruitment"
    PERSONAL_BRANDING = "personal_branding"
    EDUCATIONAL = "educational"
    PRODUCT_PROMOTION = "product_promotion"
    ACHIEVEMENT = "achievement"
    APPRECIATION = "appreciation"


class Risk(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"

    @property
    def rank(self) -> int:
        return {"green": 0, "amber": 1, "red": 2}[self.value]


class Language(StrEnum):
    EN = "en"
    ZH_HANS = "zh-Hans"
    ZH_HANT = "zh-Hant"
    MS = "ms"
    TA = "ta"


class Severity(StrEnum):
    ERROR = "error"
    WARN = "warn"
    INFO = "info"


FactValue = str | int | float | bool | date | time | None


class Fact(Strict):
    """A campaign fact. Locked facts may never be rewritten by a model (ADR-001)."""

    field: str = Field(description="Dotted path, e.g. 'event.date' or 'agent.phone'")
    value: FactValue
    source: str = Field(description="user | profile | artifact:<id> | past_campaign:<id> | derived")
    locked: bool = True


class Assumption(Strict):
    """A default the Brief Agent chose instead of asking. Always surfaced to the user."""

    field: str
    value: FactValue
    reason: str


class Finding(Strict):
    rule_id: str
    severity: Severity
    message: str
    element_id: str | None = None
    evidence: str | None = None
    suggestion: str | None = None


class ValidationReport(Strict):
    checks_run: int = 0
    findings: list[Finding] = Field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def passed(self) -> bool:
        return not self.errors

    def merge(self, other: ValidationReport) -> ValidationReport:
        return ValidationReport(
            checks_run=self.checks_run + other.checks_run,
            findings=[*self.findings, *other.findings],
        )


class UsageRecord(Strict):
    """One model call. Written to lineage and used for budget accounting."""

    call_id: str
    node: str = Field(description="Pipeline step, e.g. 'brief_agent'")
    model: str
    tier: Literal["fast", "quality", "vision", "image", "authoring"]
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    requests: int = 1
    tool_calls: int = 0
    images: int = 0
    cost_usd: float | None = None
    campaign_id: str | None = None
    ts: datetime = Field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class RunBudget(Strict):
    """Per-run ceiling. Exhaustion degrades gracefully: return best valid output, flag partial."""

    max_tokens: int = 120_000
    max_images: int = 6
    max_model_calls: int = 40
    max_cost_usd: float | None = None
    spent_tokens: int = 0
    spent_images: int = 0
    spent_calls: int = 0
    spent_cost_usd: float = 0.0
    exhausted: bool = False

    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.spent_tokens)

    def can_spend(self, *, tokens: int = 0, images: int = 0, calls: int = 1) -> bool:
        return (
            self.spent_tokens + tokens <= self.max_tokens
            and self.spent_images + images <= self.max_images
            and self.spent_calls + calls <= self.max_model_calls
        )

    def record(self, usage: UsageRecord) -> None:
        self.spent_tokens += usage.total_tokens
        self.spent_images += usage.images
        self.spent_calls += usage.requests
        self.spent_cost_usd += usage.cost_usd or 0.0
        if (
            self.spent_tokens >= self.max_tokens
            or self.spent_images >= self.max_images
            or self.spent_calls >= self.max_model_calls
            or (self.max_cost_usd is not None and self.spent_cost_usd >= self.max_cost_usd)
        ):
            self.exhausted = True


Url = Annotated[HttpUrl, Field(description="Validated URL")]
