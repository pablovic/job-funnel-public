"""ORM mapping over db/schema.sql. The SQL file is the source of truth for DDL;
these classes exist so application code has types, not so Alembic can guess."""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import (
    ARRAY, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _now() -> Mapped[dt.datetime]:
    return mapped_column(DateTime(timezone=True), server_default=text("now()"))


# --- Tipos ENUM de Postgres -------------------------------------------------
# schema.sql define estas columnas como tipos ENUM propios de Postgres, no como
# texto. Si aca se declaran como String, psycopg manda texto plano y Postgres
# rechaza el INSERT ("column is of type X but expression is of type text").
# create_type=False significa: el tipo ya existe en la base, no lo crees.
def _enum(name: str, *values: str) -> ENUM:
    return ENUM(*values, name=name, create_type=False)


VERTICAL = _enum("vertical", "job", "flight")
OPP_STATUS = _enum("opp_status", "new", "rejected_by_rules", "scored", "labeled",
                   "applied", "archived")
VERDICT = _enum("verdict", "yes", "maybe", "no")
SENIORITY = _enum("seniority", "junior", "mid", "senior", "staff", "lead",
                  "manager", "head", "unknown")
REMOTE_POLICY = _enum("remote_policy", "remote_global", "remote_country",
                      "hybrid", "onsite", "unknown")
COMPANY_KIND = _enum("company_kind", "product", "agency", "staffing",
                     "consultancy", "unknown")
CV_VARIANT = _enum("cv_variant", "ic", "lead")
STAGE = _enum("stage", "applied", "ack", "screening", "technical", "onsite",
              "offer", "rejected", "withdrawn", "ghosted")


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String, unique=True)
    adapter: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(COMPANY_KIND, default="unknown")
    pays_usd: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hq_country: Mapped[str | None] = mapped_column(String, nullable=True)
    blocklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[uuid.UUID] = _pk()
    vertical: Mapped[str] = mapped_column(VERTICAL, default="job")
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(Text)
    lang: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(OPP_STATUS, default="new")
    captured_at: Mapped[dt.datetime] = _now()
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    detail: Mapped["JobDetail"] = relationship(back_populates="opportunity", uselist=False)
    scores: Mapped[list["Score"]] = relationship(back_populates="opportunity")
    label: Mapped["Label | None"] = relationship(back_populates="opportunity", uselist=False)


class JobDetail(Base):
    __tablename__ = "job_details"
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"), primary_key=True)
    company_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    role_family: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority: Mapped[str] = mapped_column(SENIORITY, default="unknown")
    remote: Mapped[str] = mapped_column(REMOTE_POLICY, default="unknown")
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    comp_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    comp_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    comp_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    comp_period: Mapped[str | None] = mapped_column(String, nullable=True)
    comp_published: Mapped[bool] = mapped_column(Boolean, default=False)
    comp_usd_year_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    comp_usd_year_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    tech_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    domain_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    asks_instrumentation: Mapped[bool] = mapped_column(Boolean, default=False)
    asks_dbt: Mapped[bool] = mapped_column(Boolean, default=False)
    extraction: Mapped[dict] = mapped_column(JSONB, default=dict)

    opportunity: Mapped[Opportunity] = relationship(back_populates="detail")
    company: Mapped[Company | None] = relationship()


class Score(Base):
    __tablename__ = "scores"
    id: Mapped[uuid.UUID] = _pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"))
    model_version: Mapped[str] = mapped_column(String)
    fit: Mapped[float] = mapped_column(Numeric)
    dimensions: Mapped[dict] = mapped_column(JSONB)
    gaps: Mapped[list] = mapped_column(JSONB, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = _now()

    opportunity: Mapped[Opportunity] = relationship(back_populates="scores")


class Label(Base):
    __tablename__ = "labels"
    id: Mapped[uuid.UUID] = _pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"), unique=True)
    verdict: Mapped[str] = mapped_column(VERDICT)
    reason_code: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    labeled_at: Mapped[dt.datetime] = _now()

    opportunity: Mapped[Opportunity] = relationship(back_populates="label")


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[uuid.UUID] = _pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"), unique=True)
    applied_at: Mapped[dt.datetime] = _now()
    cv_variant: Mapped[str] = mapped_column(CV_VARIANT)
    cv_version: Mapped[str | None] = mapped_column(String, nullable=True)
    comp_asked_usd: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    referral: Mapped[bool] = mapped_column(Boolean, default=False)

    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application")


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    id: Mapped[uuid.UUID] = _pk()
    application_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("applications.id"))
    stage: Mapped[str] = mapped_column(STAGE)
    occurred_at: Mapped[dt.datetime] = _now()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    application: Mapped[Application] = relationship(back_populates="events")






class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[uuid.UUID] = _pk()
    model_version: Mapped[str] = mapped_column(String)
    golden_set: Mapped[str] = mapped_column(String)
    metrics: Mapped[dict] = mapped_column(JSONB)
    passed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[dt.datetime] = _now()
