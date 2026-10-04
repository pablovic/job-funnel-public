from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class OpportunityIn(BaseModel):
    """Manual capture. The paste box is the highest-volume entry point: most
    good postings arrive from a saved list or a friend's message, not a scraper.

    Los tres campos de abajo son los MISMOS que Greenhouse y Remotive entregan en
    su JSON. Sin ellos, un aviso pegado a mano llegaba peor que uno automatico:
    sin empresa (canal = 7 neutro en vez de su valor real) y, peor, sin el campo
    de ubicacion, que es de donde sale la senal mas confiable del filtro
    geografico ("US Remote"). Son opcionales: si vienen vacios, el extractor
    vuelve a buscarlos en el texto como antes.
    """
    title: str
    raw_text: str
    url: str | None = None
    source: str = "paste"
    vertical: Literal["job", "flight"] = "job"
    company: str = ""
    salary: str = ""
    location: str = ""


class OpportunityOut(BaseModel):
    id: uuid.UUID
    title: str
    url: str | None
    company: str | None = None
    status: str
    lang: str | None
    seniority: str | None = None
    remote: str | None = None
    comp_published: bool | None = None
    comp_usd_year_min: float | None = None
    comp_usd_year_max: float | None = None
    fit: float | None = None
    dimensions: dict | None = None
    gaps: list | None = None
    rationale: str | None = None
    recommended_cv: str | None = None
    rule_flags: list[str] = Field(default_factory=list)
    verdict: str | None = None
    captured_at: dt.datetime

    # Si ya existe una fila en `applications` para esta oportunidad. Permite que
    # la lista de "yes" separe lo pendiente de lo ya enviado sin un segundo pedido.
    applied: bool = False

    # Las palabras que el scorer efectivamente engancho. Sin esto, la pantalla
    # solo puede mostrar el numero, y el numero no se puede discutir.
    tech_tags: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)

    # global | latam | us | canada | ... | unknown
    geo_scope: str | None = None

    # El texto del aviso. Solo lo devuelve el detalle (GET /opportunities/{id}),
    # nunca la lista: cincuenta avisos completos serian megabytes por pantalla.
    raw_text: str | None = None

    class Config:
        from_attributes = True


class LabelIn(BaseModel):
    verdict: Literal["yes", "maybe", "no"]
    reason_code: str | None = None
    note: str | None = None


class ScreenIn(BaseModel):
    """El tercer filtro: la decision despues de leer el aviso con atencion.

    Va aparte de LabelIn a proposito. `labels` guarda el juicio rapido del deck
    y es la verdad contra la que se mide el scorer; si se pisara con la decision
    posterior, la metrica dejaria de responder "acerto el scorer?" y pasaria a
    responder "cambie de opinion?", que es otra pregunta.
    """
    decision: Literal["drop", "keep"]


class ApplicationIn(BaseModel):
    opportunity_id: uuid.UUID
    cv_variant: Literal["ic", "lead"]
    cv_version: str | None = None
    comp_asked_usd: float | None = None
    channel: str | None = "ats"
    referral: bool = False


class EventIn(BaseModel):
    stage: Literal["applied", "ack", "screening", "technical", "onsite",
                   "offer", "rejected", "withdrawn", "ghosted"]
    occurred_at: dt.datetime | None = None
    note: str | None = None
