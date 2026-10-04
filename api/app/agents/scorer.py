"""Fit scorer. Produces a dimensioned score, the gaps, and a citation per claim.

Deliberately not a single number: the earlier hand-built scorer reached
Spearman 0.67 against my own labels, separating the clear "no" but not "yes"
from "maybe" — which is exactly where the decision to spend an hour applying
lives. Dimensions make the disagreement inspectable instead of mysterious."""
from __future__ import annotations

from app.agents.client import AgentResult, load_prompt, quoted_in_source, run_json
from app.config import settings

DIMENSIONS = ["domain", "craft", "comp", "level_fit", "channel", "language"]

SCHEMA = {
    "type": "object",
    "required": ["fit", "dimensions", "gaps", "evidence", "rationale", "recommended_cv"],
    "properties": {
        "fit": {"type": "number", "minimum": 0, "maximum": 100},
        "dimensions": {
            "type": "object",
            "required": DIMENSIONS,
            "properties": {d: {"type": "number", "minimum": 0, "maximum": 10} for d in DIMENSIONS},
        },
        "gaps": {
            "type": "array",
            "description": "Requirements the candidate does not meet. Honesty here is the point.",
            "items": {"type": "object", "required": ["requirement", "quote"],
                      "properties": {"requirement": {"type": "string"}, "quote": {"type": "string"},
                                     "severity": {"type": "string", "enum": ["blocking", "teachable", "cosmetic"]}}},
        },
        "evidence": {
            "type": "array",
            "items": {"type": "object", "required": ["claim", "quote"],
                      "properties": {"claim": {"type": "string"}, "quote": {"type": "string"}}},
        },
        "rationale": {"type": "string", "maxLength": 600},
        "recommended_cv": {"type": "string", "enum": ["ic", "lead"]},
    },
}


def score(raw_text: str, title: str, profile: str) -> tuple[AgentResult, list[str]]:
    """Returns the result plus any ungrounded quotes found. Callers must treat a
    non-empty second element as a failed generation, not a warning."""
    res = run_json(
        model=settings().model_scorer,
        system=load_prompt("score"),
        user=f"<profile>\n{profile}\n</profile>\n\n<posting title={title!r}>\n{raw_text[:24000]}\n</posting>",
        schema=SCHEMA,
        tool_name="emit_fit",
        max_tokens=2000,
    )
    quotes = [e["quote"] for e in res.data.get("evidence", [])] + \
             [g["quote"] for g in res.data.get("gaps", [])]
    ungrounded = [q for q in quotes if not quoted_in_source(q, raw_text)]
    return res, ungrounded
