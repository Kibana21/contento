"""Model gateway: budgets enforced, usage recorded, no network in tests."""

import asyncio
import json

import pytest
from pydantic import BaseModel
from pydantic_ai.models.test import TestModel

from src.ai.model_gateway import CALL_CAPS, BudgetExceeded, ModelGateway
from src.contracts.common import RunBudget


class Out(BaseModel):
    headline: str


def gateway(**kw) -> ModelGateway:
    return ModelGateway(test_model=TestModel(), campaign_id="CAM-1", **kw)


def run(coro):
    return asyncio.run(coro)


def test_usage_is_recorded_per_node():
    gw = gateway()
    agent = gw.agent("copywriter", tier="quality", output_type=Out, instructions="write copy")
    res = run(gw.run(agent, "Deepavali", node="copywriter", tier="quality"))
    assert isinstance(res.output, Out)
    summary = gw.summary()
    assert summary["calls"] == 1
    assert summary["tokens"] > 0
    assert "copywriter" in summary["tokens_by_node"]


def test_budget_blocks_further_calls():
    """Spending the budget stops the next agent from being built."""
    gw = gateway(budget=RunBudget(max_tokens=10_000, max_model_calls=1))
    agent = gw.agent("a", tier="fast", output_type=Out, instructions="i")
    run(gw.run(agent, "hello", node="a", tier="fast"))
    assert gw.budget.exhausted
    with pytest.raises(BudgetExceeded, match="exhausted"):
        gw.agent("b", tier="fast", output_type=Out, instructions="i")


def test_mid_run_limit_breach_becomes_budget_exceeded():
    """A tiny budget trips pydantic-ai's own limit; we surface it as BudgetExceeded."""
    gw = gateway(budget=RunBudget(max_tokens=10))
    agent = gw.agent("a", tier="fast", output_type=Out, instructions="i")
    with pytest.raises(BudgetExceeded):
        run(gw.run(agent, "hello", node="a", tier="fast"))
    assert gw.budget.exhausted


def test_call_caps_applied_per_tier():
    gw = gateway()
    assert gw.settings("fast").get("max_tokens") == CALL_CAPS["fast"]["max_tokens"]
    # fast tier disables thinking tokens
    assert gw.settings("fast").get("google_thinking_config") == {"thinking_budget": 0}
    assert "google_thinking_config" not in gw.settings("quality")


def test_limits_shrink_with_remaining_budget():
    gw = gateway(budget=RunBudget(max_tokens=500))
    assert gw.limits("fast").total_tokens_limit == 500
    gw.budget.spent_tokens = 450
    assert gw.limits("fast").total_tokens_limit == 50


def test_usage_file_written(tmp_path):
    gw = gateway()
    agent = gw.agent("n", tier="fast", output_type=Out, instructions="i")
    run(gw.run(agent, "x", node="n", tier="fast"))
    out = tmp_path / "usage.json"
    gw.write_usage(out)
    data = json.loads(out.read_text())
    assert data["summary"]["calls"] == 1 and len(data["calls"]) == 1
    assert data["calls"][0]["node"] == "n"
