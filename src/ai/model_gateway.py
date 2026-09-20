"""The single choke point for every model call.

Responsibilities (plan §D10):
  * map logical tiers -> concrete models, so agents never name a model (BRD §48, NFR 32.7)
  * enforce per-call caps and the per-run RunBudget
  * record a UsageRecord for every call (lineage + cost dashboards)

Tests use Pydantic AI's TestModel/FunctionModel: no network, no credentials.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage, UsageLimits

from ..contracts.common import RunBudget, UsageRecord

Tier = Literal["fast", "quality", "vision", "image"]
OutputT = TypeVar("OutputT", bound=BaseModel)

DEFAULT_MODELS: dict[Tier, str] = {
    "fast": "gemini-2.5-flash",
    "quality": "gemini-2.5-pro",
    "vision": "gemini-2.5-flash",
    "image": "gemini-3.1-flash-image",
}

#: Per-call ceilings. Deliberately tight: agents return structured data, not essays.
CALL_CAPS: dict[Tier, dict[str, int]] = {
    "fast": {"max_tokens": 2_000, "thinking_budget": 0},
    "quality": {"max_tokens": 4_000, "thinking_budget": 1_024},
    "vision": {"max_tokens": 2_000, "thinking_budget": 0},
    "image": {"max_tokens": 0, "thinking_budget": 0},
}


class BudgetExceeded(RuntimeError):
    """Raised when a run has spent its budget. Callers degrade gracefully (flag `partial`)."""


#: HTTP statuses worth retrying: rate limits and transient server errors.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 3


@dataclass
class ModelGateway:
    """Creates budget-aware Pydantic AI agents."""

    budget: RunBudget = field(default_factory=RunBudget)
    campaign_id: str | None = None
    models: dict[Tier, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    usage_log: list[UsageRecord] = field(default_factory=list)
    test_model: Model | None = None  # injected in tests
    _clients: dict[str, Model] = field(default_factory=dict, repr=False)

    # ---- model resolution -------------------------------------------------
    def resolve(self, tier: Tier) -> Model | str:
        if self.test_model is not None:
            return self.test_model
        name = self.models[tier]
        if name not in self._clients:
            self._clients[name] = _build_google_model(name)
        return self._clients[name]

    def settings(self, tier: Tier, **overrides: Any) -> ModelSettings:
        caps = CALL_CAPS[tier]
        settings: dict[str, Any] = {"max_tokens": caps["max_tokens"], "temperature": 0.4}
        if caps["thinking_budget"] == 0:
            settings["google_thinking_config"] = {"thinking_budget": 0}
        return ModelSettings(**(settings | overrides))

    def limits(self, tier: Tier, *, tool_calls: int | None = None, requests: int = 4) -> UsageLimits:
        """Per-run remainder, expressed as a per-call limit so one agent cannot drain the budget."""
        return UsageLimits(
            request_limit=requests,
            tool_calls_limit=tool_calls,
            total_tokens_limit=max(1, min(self.budget.remaining_tokens(), CALL_CAPS[tier]["max_tokens"] * 12)),
        )

    # ---- agent construction ----------------------------------------------
    def agent(
        self,
        node: str,
        *,
        tier: Tier,
        output_type: type[OutputT],
        instructions: str,
        tools: Sequence[Any] = (),
        deps_type: type | None = None,
        retries: int = 2,
        **settings: Any,
    ) -> Agent:
        """Build an agent whose output is a validated Pydantic model."""
        self._preflight(node)
        kwargs: dict[str, Any] = {
            "output_type": output_type,
            "instructions": instructions,
            "model_settings": self.settings(tier, **settings),
            "retries": retries,
            "name": node,
        }
        if tools:
            kwargs["tools"] = list(tools)
        if deps_type is not None:
            kwargs["deps_type"] = deps_type
        return Agent(self.resolve(tier), **kwargs)

    # ---- accounting -------------------------------------------------------
    def _preflight(self, node: str) -> None:
        if self.budget.exhausted or not self.budget.can_spend():
            raise BudgetExceeded(f"run budget exhausted before {node}")

    def record(self, node: str, tier: Tier, usage: RunUsage, *, images: int = 0) -> UsageRecord:
        rec = UsageRecord(
            call_id=uuid.uuid4().hex[:12],
            node=node,
            model=self.models[tier] if self.test_model is None else "test",
            tier=tier,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cache_read_tokens,
            requests=max(1, usage.requests),
            tool_calls=usage.tool_calls,
            images=images,
            cost_usd=float(usage.cost().total_price) if _has_price(usage) else None,
            campaign_id=self.campaign_id,
        )
        self.usage_log.append(rec)
        self.budget.record(rec)
        return rec

    async def run(self, agent: Agent, prompt: Any, *, node: str, tier: Tier,
                  limits: UsageLimits | None = None,
                  rebuild: Callable[[Tier], Agent] | None = None, **run_kwargs: Any):
        """Run an agent, enforce limits, retry transient failures, and account for usage.

        A mid-run limit breach becomes `BudgetExceeded` so callers degrade gracefully.
        Rate limits (429) and transient server errors are retried with backoff; if a
        `rebuild` factory is given, the last attempt drops to the fast tier rather than
        failing the campaign (NFR 32.2).
        """
        from pydantic_ai.exceptions import ModelHTTPError

        self._preflight(node)
        used_tier = tier
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                result = await agent.run(prompt, usage_limits=limits or self.limits(used_tier), **run_kwargs)
            except UsageLimitExceeded as exc:
                self.budget.exhausted = True
                raise BudgetExceeded(f"{node}: {exc}") from exc
            except ModelHTTPError as exc:
                if exc.status_code not in RETRYABLE_STATUS or attempt == MAX_ATTEMPTS:
                    raise
                if exc.status_code == 429 and rebuild is not None and used_tier == "quality":
                    used_tier = "fast"          # the quality model is busy: finish on the fast one
                    agent = rebuild(used_tier)
                await asyncio.sleep(min(8.0, 1.5 ** attempt) + random.random())
                continue
            self.record(node, used_tier, _usage_of(result))
            return result
        raise RuntimeError(f"{node}: exhausted retries")  # pragma: no cover

    # ---- reporting --------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        by_node: dict[str, int] = {}
        for rec in self.usage_log:
            by_node[rec.node] = by_node.get(rec.node, 0) + rec.total_tokens
        return {
            "calls": len(self.usage_log),
            "tokens": self.budget.spent_tokens,
            "images": self.budget.spent_images,
            "cost_usd": round(self.budget.spent_cost_usd, 4) or None,
            "budget_exhausted": self.budget.exhausted,
            "tokens_by_node": by_node,
        }

    def write_usage(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"summary": self.summary(), "calls": [r.model_dump(mode="json") for r in self.usage_log]},
                       indent=2)
        )


def _usage_of(result: Any) -> RunUsage:
    """`result.usage` is a property in pydantic-ai v2 and a method in v1."""
    usage = result.usage
    return usage() if callable(usage) else usage


def _has_price(usage: RunUsage) -> bool:
    try:
        return usage.cost().total_price is not None
    except Exception:  # pricing data unavailable for this model
        return False


def _build_google_model(name: str) -> Model:
    """Vertex AI via the service-account key, falling back to an API key if present."""
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    key_path = Path(os.environ.get("AIA_SERVICE_ACCOUNT", "api_key.json"))
    if key_path.exists():
        import json as _json

        from google import genai
        from google.oauth2 import service_account

        info = _json.loads(key_path.read_text())
        creds = service_account.Credentials.from_service_account_file(
            key_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        client = genai.Client(
            vertexai=True,
            project=info["project_id"],
            location=os.environ.get("GEMINI_LOCATION", "global"),
            credentials=creds,
        )
        return GoogleModel(name, provider=GoogleProvider(client=client))
    return GoogleModel(name, provider=GoogleProvider(api_key=os.environ["GOOGLE_API_KEY"]))
