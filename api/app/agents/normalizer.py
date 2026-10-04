"""Extraction agent. Raw posting text -> normalized fields, each carrying the
quote that justified it. Cheap model, high volume."""
from __future__ import annotations

from app.agents.client import AgentResult, load_prompt, run_json
from app.config import settings

SCHEMA = {
    "type": "object",
    "required": ["company", "seniority", "remote", "comp_published", "lang"],
    "properties": {
        "company": {"type": "string"},
        "role_family": {"type": "string",
                        "enum": ["product_analytics", "growth", "marketplace", "bi",
                                 "data_engineering", "data_science", "leadership", "other"]},
        "seniority": {"type": "string",
                      "enum": ["junior", "mid", "senior", "staff", "lead", "manager", "head", "unknown"]},
        "remote": {"type": "string",
                   "enum": ["remote_global", "remote_country", "hybrid", "onsite", "unknown"]},
        "country": {"type": "string"},
        "lang": {"type": "string", "enum": ["en", "es", "pt", "other"]},
        "comp_published": {"type": "boolean"},
        "comp_min": {"type": ["number", "null"]},
        "comp_max": {"type": ["number", "null"]},
        "comp_currency": {"type": ["string", "null"], "enum": ["USD", "BRL", "ARS", "EUR", None]},
        "comp_period": {"type": ["string", "null"], "enum": ["year", "month", "hour", None]},
        "tech_tags": {"type": "array", "items": {"type": "string"}},
        "domain_tags": {"type": "array", "items": {"type": "string"}},
        "asks_instrumentation": {"type": "boolean"},
        "asks_dbt": {"type": "boolean"},
        "evidence": {
            "type": "array",
            "description": "One entry per non-obvious field, quoting the posting verbatim.",
            "items": {"type": "object",
                      "required": ["field", "quote"],
                      "properties": {"field": {"type": "string"}, "quote": {"type": "string"}}},
        },
    },
}

FX_USD = {"USD": 1.0, "BRL": 1 / 5.4, "ARS": 1 / 1400, "EUR": 1.08}


def to_usd_year(amount: float | None, currency: str | None, period: str | None) -> float | None:
    if amount is None or not currency:
        return None
    per_year = {"year": 1, "month": 12, "hour": 2080}.get(period or "year", 1)
    return round(amount * FX_USD.get(currency, 1.0) * per_year)


def normalize(raw_text: str, title: str) -> AgentResult:
    return run_json(
        model=settings().model_normalizer,
        system=load_prompt("normalize"),
        user=f"<title>{title}</title>\n<posting>\n{raw_text[:24000]}\n</posting>",
        schema=SCHEMA,
        tool_name="emit_job_fields",
        max_tokens=1500,
    )
