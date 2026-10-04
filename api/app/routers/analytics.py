from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

VIEWS = {
    "funnel": "select * from v_funnel",
    "effort": "select * from v_effort_leak limit 12",
    "variants": "select * from v_response_by_variant",
    "power": "select * from v_power_check",
    "bias": "select * from v_bias_comp_published",
    "agreement": "select * from v_scorer_agreement",
    "followups": "select * from v_needs_followup",
}


@router.get("/{name}")
def read(name: str, db: Session = Depends(get_db)):
    sql = VIEWS.get(name)
    if not sql:
        return {"error": "unknown metric", "available": sorted(VIEWS)}
    return [dict(r) for r in db.execute(text(sql)).mappings().all()]
