"""Router de oportunidades.

Sobre la velocidad (problema "N+1"):
la version anterior hacia ~5 consultas POR aviso (score, empresa, postulacion,
label, detalle). Con la base en Docker cada consulta tarda ~1 ms y no se nota.
Con la base en Neon, cada consulta viaja por internet (~100 ms ida y vuelta):
200 avisos x 5 consultas = ~45 segundos para abrir /apply.

La solucion es pedir todo junto: `selectinload` le dice a SQLAlchemy "traeme
los detalles, scores, labels y empresas de TODOS estos avisos en una consulta
cada uno". Pasa de ~1000 consultas a ~6, sin importar cuantos avisos haya.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Application, JobDetail, Label, Opportunity
from app.pipeline import ingest
from app.schemas import LabelIn, OpportunityIn, OpportunityOut, ScreenIn

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _serialize(db: Session, o: Opportunity, *, include_text: bool = False,
               applied: bool | None = None) -> OpportunityOut:
    # Todo sale de las relaciones del modelo (o.detail, o.scores, o.label).
    # Si vinieron precargadas con selectinload, no hay consulta nueva; si no
    # (un solo aviso, como en get_one), SQLAlchemy las busca solo.
    d: JobDetail | None = o.detail
    s = max(o.scores, key=lambda sc: sc.created_at, default=None)
    company = d.company.name if d and d.company else None
    ex = (d.extraction or {}) if d else {}
    if applied is None:
        applied = db.query(Application.id).filter_by(opportunity_id=o.id).first() is not None
    return OpportunityOut(
        id=o.id, title=o.title, url=o.url, company=company, status=o.status, lang=o.lang,
        seniority=d.seniority if d else None, remote=d.remote if d else None,
        comp_published=d.comp_published if d else None,
        comp_usd_year_min=float(d.comp_usd_year_min) if d and d.comp_usd_year_min else None,
        comp_usd_year_max=float(d.comp_usd_year_max) if d and d.comp_usd_year_max else None,
        fit=float(s.fit) if s else None, dimensions=s.dimensions if s else None,
        gaps=s.gaps if s else None, rationale=s.rationale if s else None,
        recommended_cv=ex.get("recommended_cv"), rule_flags=ex.get("rule_flags", []),
        verdict=o.label.verdict if o.label else None, captured_at=o.captured_at,
        applied=applied,
        tech_tags=list(d.tech_tags or []) if d else [],
        domain_tags=list(d.domain_tags or []) if d else [],
        geo_scope=ex.get("geo_scope"),
        raw_text=o.raw_text if include_text else None,
    )


@router.post("", response_model=OpportunityOut, status_code=201)
def create(body: OpportunityIn, db: Session = Depends(get_db)):
    opp, outcome = ingest(db, title=body.title, raw_text=body.raw_text,
                          url=body.url, vertical=body.vertical,
                          company_hint=body.company, salary_hint=body.salary,
                          location_hint=body.location)
    if outcome == "score_failed_groundedness":
        raise HTTPException(422, "Scorer cited text absent from the posting. Saved unscored.")
    return _serialize(db, opp)


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(
    status: str | None = None,
    unlabeled: bool = Query(False, description="Triage deck: scored but not yet decided"),
    verdict: str | None = Query(None, description="Already decided: yes | maybe | no"),
    not_applied: bool = Query(False, description="Exclude anything already logged as applied"),
    include_archived: bool = Query(False, description="Also return what was dropped on close review"),
    min_fit: float = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = db.query(Opportunity)
    if status:
        q = q.filter(Opportunity.status == status)
    if unlabeled:
        q = q.filter(Opportunity.status == "scored", ~Opportunity.id.in_(db.query(Label.opportunity_id)))
    # El deck muestra lo NO decidido; esto muestra lo decidido. Son las dos
    # mitades de la misma tabla, por eso viven en el mismo endpoint.
    if verdict:
        q = q.join(Label, Label.opportunity_id == Opportunity.id).filter(Label.verdict == verdict)
    if not_applied:
        q = q.filter(~Opportunity.id.in_(db.query(Application.opportunity_id)))
    # Lo archivado esta guardado, no borrado: no aparece salvo que se pida.
    if not include_archived:
        q = q.filter(Opportunity.status != "archived")
    # Precarga en bloque: una consulta por relacion, no una por aviso.
    q = q.options(
        selectinload(Opportunity.detail).selectinload(JobDetail.company),
        selectinload(Opportunity.scores),
        selectinload(Opportunity.label),
    )
    rows = q.order_by(desc(Opportunity.captured_at)).limit(limit).all()
    # Lo mismo para "ya postule": una sola consulta para todos los ids.
    ids = [o.id for o in rows]
    applied_ids = {
        r.opportunity_id for r in
        db.query(Application.opportunity_id).filter(Application.opportunity_id.in_(ids))
    } if ids else set()
    out = [_serialize(db, o, applied=o.id in applied_ids) for o in rows]
    return [o for o in out if (o.fit or 0) >= min_fit]


@router.get("/{opp_id}", response_model=OpportunityOut)
def get_one(opp_id: uuid.UUID, db: Session = Depends(get_db)):
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(404)
    # Unico lugar que devuelve el texto del aviso: es una pantalla, un aviso.
    return _serialize(db, o, include_text=True)


@router.post("/{opp_id}/screen", response_model=OpportunityOut)
def screen(opp_id: uuid.UUID, body: ScreenIn, db: Session = Depends(get_db)):
    """El tercer filtro. Despues de leer el aviso de verdad: sigue o se cae.

    'drop' archiva (no borra, y se puede deshacer). 'keep' lo trae de vuelta.
    El "si" de este filtro no pasa por aca: es POST /applications, porque
    confirmar que vale la pena y registrar que se envio son el mismo acto.
    """
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(404)
    if o.status == "applied":
        raise HTTPException(409, "Already applied. Archiving it would hide a real application.")
    o.status = "archived" if body.decision == "drop" else "labeled"
    db.flush()
    return _serialize(db, o)


@router.post("/{opp_id}/label", response_model=OpportunityOut)
def label(opp_id: uuid.UUID, body: LabelIn, db: Session = Depends(get_db)):
    """Ground truth. Written only here, only by a person. The eval harness scores
    the model against these rows, so an agent writing them would close the loop
    on itself and the metric would stop meaning anything."""
    o = db.get(Opportunity, opp_id)
    if not o:
        raise HTTPException(404)
    existing = db.query(Label).filter_by(opportunity_id=opp_id).one_or_none()
    if existing:
        existing.verdict, existing.reason_code, existing.note = body.verdict, body.reason_code, body.note
    else:
        db.add(Label(opportunity_id=opp_id, **body.model_dump()))
    o.status = "labeled"
    db.flush()
    return _serialize(db, o)
