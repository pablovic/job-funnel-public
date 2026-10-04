"""Ingest -> rules -> normalize -> score. One function, called by the paste
endpoint, the scheduled sources and the backfill CLI alike, so all three paths
produce identical rows."""
from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.config import settings
from app.free import extractor as free_extractor
from app.free import scorer as free_scorer
from app.models import Company, JobDetail, Opportunity, Score
from app.rules.filters import Candidate, Decision, evaluate


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


_PROFILE_CACHE: str | None = None


def build_profile(db: Session | None = None) -> str:
    """The candidate profile the scorer judges fit against. A static file, not a
    table: it changes rarely, and the same text is the knowledge the Claude prep
    Skill uses to write. One source, two readers."""
    global _PROFILE_CACHE
    if _PROFILE_CACHE is None:
        from pathlib import Path
        _PROFILE_CACHE = (Path(__file__).parent / "profile.md").read_text(encoding="utf-8")
    return _PROFILE_CACHE


def ingest(db: Session, *, title: str, raw_text: str, url: str | None = None,
           source_id=None, vertical: str = "job", company_hint: str = "",
           salary_hint: str = "", location_hint: str = "") -> tuple[Opportunity, str]:
    h = content_hash(raw_text)
    existing = db.query(Opportunity).filter_by(content_hash=h).one_or_none()
    if existing:
        return existing, "duplicate"

    opp = Opportunity(vertical=vertical, title=title, raw_text=raw_text, url=url,
                      source_id=source_id, content_hash=h, status="new")
    db.add(opp)
    db.flush()

    # 1. Extraction. Free path is regex + source metadata; paid paths call a
    #    model. Either way the output shape is identical, so nothing downstream
    #    knows or cares which ran.
    provider = settings().llm_provider
    extraction_cost = 0.0
    if provider == "free":
        d = free_extractor.extract(raw_text, title=title, company_hint=company_hint,
                                   salary_hint=salary_hint, location_hint=location_hint)
    else:
        from app.agents import normalizer
        ex = normalizer.normalize(raw_text, title)
        d = ex.data
        extraction_cost = ex.cost_usd

    # Elegibilidad geografica. Se calcula SIEMPRE aca y no dentro del extractor,
    # porque es una regla determinista y gratuita que el camino pago tambien
    # necesita: un modelo caro no deberia tener que acordarse de mirar esto.
    geo, geo_quote = free_extractor.geo_scope(raw_text, title=title,
                                              location_hint=location_hint)

    company = None
    if d.get("company"):
        company = db.query(Company).filter(Company.name.ilike(d["company"])).one_or_none()
        if not company:
            company = Company(name=d["company"])
            db.add(company)
            db.flush()

    detail = JobDetail(
        opportunity_id=opp.id,
        company_id=company.id if company else None,
        role_family=d.get("role_family"),
        seniority=d.get("seniority", "unknown"),
        remote=d.get("remote", "unknown"),
        country=d.get("country"),
        comp_min=d.get("comp_min"), comp_max=d.get("comp_max"),
        comp_currency=d.get("comp_currency"), comp_period=d.get("comp_period"),
        comp_published=bool(d.get("comp_published")),
        comp_usd_year_min=d.get("comp_usd_year_min")
            or free_extractor.to_usd_year(d.get("comp_min"), d.get("comp_currency"), d.get("comp_period")),
        comp_usd_year_max=d.get("comp_usd_year_max")
            or free_extractor.to_usd_year(d.get("comp_max"), d.get("comp_currency"), d.get("comp_period")),
        tech_tags=d.get("tech_tags", []), domain_tags=d.get("domain_tags", []),
        asks_instrumentation=bool(d.get("asks_instrumentation")),
        asks_dbt=bool(d.get("asks_dbt")),
        extraction={"evidence": d.get("evidence", []), "cost_usd": extraction_cost,
                    "provider": provider, "geo_scope": geo, "geo_quote": geo_quote},
    )
    opp.lang = d.get("lang")
    db.add(detail)

    # 2. Deterministic gate. Rejections never reach the scorer or the deck.
    rule = evaluate(
        Candidate(title=title, text=raw_text, company=d.get("company", ""),
                  remote=detail.remote, comp_published=detail.comp_published,
                  comp_usd_year_min=detail.comp_usd_year_min,
                  comp_usd_year_max=detail.comp_usd_year_max,
                  lang=opp.lang or "en",
                  geo_scope=geo, geo_quote=geo_quote),
        comp_floor_usd=settings().comp_floor_usd_year,
        require_remote=settings().require_remote,
        languages=tuple(settings().languages.split(",")),
        eligible_regions=tuple(r.strip() for r in settings().eligible_regions.split(",")),
    )
    detail.extraction["rule_flags"] = rule.flags
    detail.extraction["rule_reasons"] = rule.reasons

    if rule.decision is Decision.REJECT:
        opp.status = "rejected_by_rules"
        db.flush()
        return opp, "rejected"

    # 3. Scoring. Free path is a weighted keyword score whose every quote is a
    #    real sentence sliced from the posting — grounded by construction. Paid
    #    paths call a model and verify each citation against the source.
    if provider == "free":
        sc = free_scorer.score(d, raw_text,
                               comp_floor_usd=settings().comp_floor_usd_year,
                               company_kind=(company.kind if company else "unknown"))
        db.add(Score(opportunity_id=opp.id, model_version="free-keyword@v1",
                     fit=sc["fit"], dimensions=sc["dimensions"], gaps=sc["gaps"],
                     evidence=[], rationale=sc["rationale"],
                     cost_usd=0, latency_ms=0))
        detail.extraction["recommended_cv"] = sc["recommended_cv"]
    else:
        from app.agents import scorer
        res, ungrounded = scorer.score(raw_text, title, build_profile(db))
        if ungrounded:
            detail.extraction["ungrounded_quotes"] = ungrounded
            db.flush()
            return opp, "score_failed_groundedness"
        db.add(Score(opportunity_id=opp.id, model_version=res.model_version,
                     fit=res.data["fit"], dimensions=res.data["dimensions"],
                     gaps=res.data.get("gaps", []), evidence=res.data.get("evidence", []),
                     rationale=res.data.get("rationale"),
                     cost_usd=res.cost_usd + extraction_cost, latency_ms=res.latency_ms))
        detail.extraction["recommended_cv"] = res.data.get("recommended_cv")
    opp.status = "scored"
    db.flush()
    return opp, "scored"
