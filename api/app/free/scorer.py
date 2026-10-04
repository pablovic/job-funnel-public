"""Scoring with no model. A weighted keyword score over the extracted fields.

Why this is not a downgrade: the hand-built scorer in this project's own history
reached Spearman 0.67 against my own labels — separating the clear rejections
cleanly. That was a rules scorer. The LLM's advantage is in the "yes vs maybe"
band, which is exactly where I read the posting myself anyway.

What this gives up: nuance in reading unusual postings, and prose rationales. What
it buys: zero cost, instant results, no API key, no rate limit, and a score whose
every point is traceable to a matched keyword — which is easier to defend in an
interview than "the model said 71".

Every quote returned here is a real sentence from the posting, sliced out of it,
so groundedness is true by construction rather than by verification.
"""
from __future__ import annotations

import re

# The candidate's evidence, as tag weights (see app/profile.md). Editing these is how the scorer gets tuned —
# it is the same knob the LLM prompt exposes, but inspectable and free.
STRONG_TECH = {"sql": 1.0, "python": 1.0, "ab_testing": 1.4, "statistics": 1.2,
               "bigquery": 0.8, "databricks": 0.8, "tableau": 0.6, "looker": 0.6,
               "spark": 0.4, "redshift": 0.4, "powerbi": 0.4}
STRONG_DOMAIN = {"marketplace": 1.4, "growth": 1.3, "fintech": 1.2,
                 "ecommerce": 1.1, "saas": 0.7, "logistics": 0.5}

# Declared gaps. Presence lowers craft slightly and always produces a gap entry.
GAP_TAGS = {
    "dbt": "dbt — not used; built the equivalent in SQL and Python",
    "amplitude": "product analytics tooling — has consumed, not instrumented",
    "mixpanel": "product analytics tooling — has consumed, not instrumented",
    "segment": "event instrumentation — has not defined event schemas",
    "ga4": "event instrumentation — has not defined event schemas",
}

LEVEL_FIT = {"senior": 10, "staff": 9, "mid": 7, "lead": 6,
             "unknown": 6, "manager": 3, "head": 2, "junior": 1}

WEIGHTS = {"domain": 0.28, "craft": 0.28, "comp": 0.18,
           "level_fit": 0.14, "channel": 0.07, "language": 0.05}


def _sentence_containing(text: str, needle: str) -> str:
    """The real sentence a tag was found in — used as the quote for a gap."""
    for s in re.split(r"(?<=[.!?])\s+|\n", text):
        if re.search(rf"\b{re.escape(needle)}\b", s, re.I):
            return " ".join(s.split())[:200]
    return ""


def score(extracted: dict, text: str, *, comp_floor_usd: int = 85_000,
          company_kind: str = "unknown") -> dict:
    tech = set(extracted.get("tech_tags", []))
    dom = set(extracted.get("domain_tags", []))

    # domain: weighted overlap, capped
    dom_raw = sum(STRONG_DOMAIN.get(t, 0) for t in dom)
    domain = min(10.0, dom_raw * 4.5)

    # craft: weighted tech overlap, with a floor if SQL+Python are both present
    tech_raw = sum(STRONG_TECH.get(t, 0) for t in tech)
    craft = min(10.0, tech_raw * 2.2)
    if {"sql", "python"} <= tech:
        craft = max(craft, 6.0)

    # comp: unpublished scores 5, never 0 — silence is not evidence about pay
    top = extracted.get("comp_usd_year_max")
    if not extracted.get("comp_published") or top is None:
        comp = 5.0
    elif top >= comp_floor_usd * 1.5:
        comp = 10.0
    elif top >= comp_floor_usd:
        comp = 8.0
    elif top >= comp_floor_usd * 0.8:
        comp = 4.0
    else:
        comp = 1.0

    level_fit = float(LEVEL_FIT.get(extracted.get("seniority", "unknown"), 6))
    channel = {"product": 10.0, "unknown": 7.0, "consultancy": 3.0,
               "agency": 2.0, "staffing": 0.0}.get(company_kind, 7.0)
    language = 10.0 if extracted.get("lang") in ("en", "es", "pt") else 0.0

    dims = {"domain": round(domain, 1), "craft": round(craft, 1), "comp": round(comp, 1),
            "level_fit": round(level_fit, 1), "channel": round(channel, 1),
            "language": round(language, 1)}
    fit = round(sum(dims[k] * w for k, w in WEIGHTS.items()) * 10, 1)

    # Varias etiquetas comparten el mismo texto (amplitude y mixpanel dicen lo
    # mismo; segment y ga4 tambien). Un aviso que menciona las dos generaba el
    # mismo gap repetido: ruido para leer, y claves duplicadas en la pantalla.
    gaps = []
    seen_labels: set[str] = set()
    for tag, label in GAP_TAGS.items():
        if label in seen_labels:
            continue
        if tag in tech or (tag == "segment" and extracted.get("asks_instrumentation")):
            quote = _sentence_containing(text, tag) or _sentence_containing(text, "instrument")
            if quote:
                seen_labels.add(label)
                gaps.append({"requirement": label, "quote": quote,
                             "severity": "teachable" if tag == "dbt" else "cosmetic"})

    matched = ", ".join(sorted(dom | (tech & set(STRONG_TECH)))[:6]) or "no strong tags"
    rationale = (f"Keyword match on: {matched}. "
                 f"Level reads as {extracted.get('seniority')}, remote is "
                 f"{extracted.get('remote')}, pay "
                 + (f"tops out near ${int(top):,}." if top else "not published."))

    return {
        "fit": fit, "dimensions": dims, "gaps": gaps,
        "evidence": [], "rationale": rationale,
        "recommended_cv": _cv_variant(extracted, text),
    }


# "Lead Data Analyst" is overwhelmingly an IC title; "Head of Analytics" is not.
# Sending the manager CV to an IC posting is the specific failure that gets read
# as overqualified, so the Lead CV requires evidence of actual reports, not just
# the word "lead" in a job title.
REPORTS = re.compile(
    r"\b(direct reports?|manage a team|team of \d|lead a team|people management|"
    r"hiring|coach\w* (the|your) team|liderar (uma |a )?equipe|gestão de pessoas)\b", re.I)


def _cv_variant(extracted: dict, text: str) -> str:
    seniority = extracted.get("seniority")
    if seniority in ("manager", "head"):
        return "lead"
    if seniority == "lead" and REPORTS.search(text):
        return "lead"
    return "ic"
