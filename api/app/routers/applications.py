from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Application, ApplicationEvent, Opportunity
from app.schemas import ApplicationIn, EventIn

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("", status_code=201)
def create(body: ApplicationIn, db: Session = Depends(get_db)):
    opp = db.get(Opportunity, body.opportunity_id)
    if not opp:
        raise HTTPException(404, "opportunity not found")
    app_row = Application(**body.model_dump())
    db.add(app_row)
    db.flush()
    # An application always opens with an event, so the funnel view never has to
    # special-case the first stage.
    db.add(ApplicationEvent(application_id=app_row.id, stage="applied"))
    opp.status = "applied"
    db.flush()
    return {"id": app_row.id, "applied_at": app_row.applied_at}


@router.post("/{app_id}/events", status_code=201)
def add_event(app_id: uuid.UUID, body: EventIn, db: Session = Depends(get_db)):
    if not db.get(Application, app_id):
        raise HTTPException(404)
    ev = ApplicationEvent(application_id=app_id, stage=body.stage, note=body.note,
                          **({"occurred_at": body.occurred_at} if body.occurred_at else {}))
    db.add(ev)
    db.flush()
    return {"id": ev.id, "stage": ev.stage}


# La vista sola no alcanza para una pantalla: trae ids, no nombres. Sin el
# puesto y la empresa, la tabla de postulaciones es una lista de fechas sin
# forma de saber de que vacante habla cada fila.
_LIST_SQL = text("""
select
  a.application_id, a.opportunity_id, a.applied_at, a.cv_variant,
  a.comp_asked_usd, a.channel, a.current_stage, a.first_response_at,
  o.title, o.url,
  c.name                                                as company,
  j.comp_usd_year_max                                   as pay_usd_year,
  (a.first_response_at::date - a.applied_at::date)      as days_to_response
from v_application_state a
join opportunities o      on o.id = a.opportunity_id
left join job_details j   on j.opportunity_id = o.id
left join companies c     on c.id = j.company_id
order by a.applied_at desc
""")


@router.get("")
def list_applications(db: Session = Depends(get_db)):
    return [dict(r) for r in db.execute(_LIST_SQL).mappings().all()]
