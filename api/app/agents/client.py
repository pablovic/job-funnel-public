"""Thin Anthropic wrapper: JSON-schema-constrained output, cost accounting and a
daily budget guard. Every agent goes through here so that spend, latency and
model version are recorded on the same row as the output they produced."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from app.config import settings

PROMPTS = Path(__file__).parent / "prompts"

# USD per million tokens. Update when pricing changes; the eval harness reports
# cost per posting and a silent price change would make that number a lie.
PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (15.00, 75.00),
}

_spent_today = 0.0


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class AgentResult:
    data: dict[str, Any]
    model_version: str
    cost_usd: float
    latency_ms: int


def load_prompt(slug: str) -> str:
    return (PROMPTS / f"{slug}.md").read_text(encoding="utf-8")


def _cost(model: str, usage) -> float:
    inp, out = PRICES.get(model, (3.0, 15.0))
    return (usage.input_tokens * inp + usage.output_tokens * out) / 1_000_000


def run_json(*, model: str, system: str, user: str, schema: dict,
             tool_name: str = "emit", max_tokens: int = 2000) -> AgentResult:
    """One call, one JSON object, validated against `schema` by the API itself.

    Structured output is a tool call rather than a "reply in JSON" instruction:
    the instruction version fails on long postings by wrapping the object in
    prose, and every such failure costs a retry.
    """
    global _spent_today
    cfg = settings()
    if _spent_today >= cfg.daily_llm_budget_usd:
        raise BudgetExceeded(f"daily budget ${cfg.daily_llm_budget_usd} reached")

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    started = time.perf_counter()
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"name": tool_name, "description": "Return the structured result.",
                "input_schema": schema}],
        tool_choice={"type": "tool", "name": tool_name},
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    cost = _cost(model, resp.usage)
    _spent_today += cost

    block = next(b for b in resp.content if b.type == "tool_use")
    data = block.input if isinstance(block.input, dict) else json.loads(block.input)
    return AgentResult(data=data, model_version=model, cost_usd=cost, latency_ms=latency_ms)


def quoted_in_source(quote: str, source: str) -> bool:
    """Groundedness primitive. A quote the agent attributes to the posting must
    actually appear in it. Whitespace-insensitive, case-insensitive; anything
    looser would pass paraphrase as citation."""
    norm = lambda s: " ".join(s.lower().split())
    return norm(quote) in norm(source)
