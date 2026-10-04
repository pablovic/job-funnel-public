-- Job Funnel — core schema
-- Postgres 15+. Source of truth. Obsidian markdown is a rendered view of this.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- enums

create type vertical        as enum ('job', 'flight');
create type opp_status      as enum ('new', 'rejected_by_rules', 'scored', 'labeled', 'applied', 'archived');
create type verdict         as enum ('yes', 'maybe', 'no');
create type seniority       as enum ('junior', 'mid', 'senior', 'staff', 'lead', 'manager', 'head', 'unknown');
create type remote_policy   as enum ('remote_global', 'remote_country', 'hybrid', 'onsite', 'unknown');
create type company_kind    as enum ('product', 'agency', 'staffing', 'consultancy', 'unknown');
create type cv_variant      as enum ('ic', 'lead');
create type stage           as enum ('applied', 'ack', 'screening', 'technical', 'onsite', 'offer', 'rejected', 'withdrawn', 'ghosted');

-- ---------------------------------------------------------------- sources

create table sources (
  id            uuid primary key default gen_random_uuid(),
  name          text not null unique,          -- 'linkedin_saved', 'greenhouse:acme', 'wellfound_rss'
  adapter       text not null,                 -- module name in app/ingest
  config        jsonb not null default '{}',
  enabled       boolean not null default true,
  last_run_at   timestamptz,
  created_at    timestamptz not null default now()
);

create table runs (
  id            uuid primary key default gen_random_uuid(),
  source_id     uuid references sources(id) on delete set null,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  ok            boolean,
  found         int not null default 0,
  inserted      int not null default 0,
  duplicates    int not null default 0,
  error         text
);

-- ---------------------------------------------------------------- companies

create table companies (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  domain        text,
  kind          company_kind not null default 'unknown',
  pays_usd      boolean,
  hq_country    text,
  blocklisted   boolean not null default false,  -- staffing / body shops
  notes         text,
  created_at    timestamptz not null default now()
);
create unique index companies_name_key on companies (lower(name));

-- ---------------------------------------------------------------- opportunities

-- Generic across verticals so a second use case (flights) reuses the whole
-- pipeline: ingest -> rules -> score -> label -> act -> measure.
create table opportunities (
  id            uuid primary key default gen_random_uuid(),
  vertical      vertical not null default 'job',
  source_id     uuid references sources(id) on delete set null,
  external_id   text,
  url           text,
  title         text not null,
  raw_text      text not null,
  lang          text,                            -- 'es' | 'pt' | 'en'
  content_hash  text not null,                   -- sha256(normalized raw_text) — dedupe key
  status        opp_status not null default 'new',
  captured_at   timestamptz not null default now(),
  expires_at    timestamptz,
  created_at    timestamptz not null default now()
);
create unique index opportunities_hash_key on opportunities (content_hash);
create index opportunities_status_idx on opportunities (status, captured_at desc);

-- Vertical-specific normalized fields, 1:1. A flight_details table lands here later.
create table job_details (
  opportunity_id    uuid primary key references opportunities(id) on delete cascade,
  company_id        uuid references companies(id) on delete set null,
  role_family       text,                        -- 'product_analytics', 'growth', 'data_platform'
  seniority         seniority not null default 'unknown',
  remote            remote_policy not null default 'unknown',
  country           text,
  comp_min          numeric,
  comp_max          numeric,
  comp_currency     text,                        -- 'USD' | 'BRL'
  comp_period       text,                        -- 'year' | 'month'
  comp_published    boolean not null default false,
  comp_usd_year_min numeric,                     -- normalized for comparison
  comp_usd_year_max numeric,
  tech_tags         text[] not null default '{}',
  domain_tags       text[] not null default '{}',
  asks_instrumentation boolean not null default false,
  asks_dbt          boolean not null default false,
  extraction        jsonb not null default '{}'  -- every field + the quote that justified it
);

-- ---------------------------------------------------------------- scoring

create table scores (
  id             uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  model_version  text not null,                 -- 'scorer@2026-09-07+sonnet-4.6'
  fit            numeric not null,              -- 0..100
  dimensions     jsonb not null,                -- {domain, craft, comp, seniority_fit, channel}
  gaps           jsonb not null default '[]',   -- [{requirement, have:false, quote}]
  evidence       jsonb not null default '[]',   -- [{claim, quote}] — groundedness check runs on this
  rationale      text,
  cost_usd       numeric,
  latency_ms     int,
  created_at     timestamptz not null default now()
);
create index scores_opp_idx on scores (opportunity_id, created_at desc);

-- Ground truth. Never written by an agent.
create table labels (
  id             uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  verdict        verdict not null,
  reason_code    text,                          -- 'comp_low', 'channel', 'scope_too_big', 'domain'
  note           text,
  labeled_at     timestamptz not null default now()
);
create unique index labels_opp_key on labels (opportunity_id);

-- ---------------------------------------------------------------- applications

create table applications (
  id             uuid primary key default gen_random_uuid(),
  opportunity_id uuid not null references opportunities(id) on delete cascade,
  applied_at     timestamptz not null default now(),
  cv_variant     cv_variant not null,
  cv_version     text,                          -- git tag or file hash of the PDF actually sent
  comp_asked_usd numeric,
  channel        text,                          -- 'ats', 'referral', 'recruiter_inbound'
  referral       boolean not null default false
);
create unique index applications_opp_key on applications (opportunity_id);

-- Event-sourced funnel. One row per state change, never an update.
create table application_events (
  id             uuid primary key default gen_random_uuid(),
  application_id uuid not null references applications(id) on delete cascade,
  stage          stage not null,
  occurred_at    timestamptz not null default now(),
  note           text
);
create index application_events_app_idx on application_events (application_id, occurred_at);

-- ---------------------------------------------------------------- evals

create table eval_runs (
  id             uuid primary key default gen_random_uuid(),
  model_version  text not null,
  golden_set     text not null,                 -- filename + row count
  metrics        jsonb not null,                -- precision, recall, spearman, hallucination_rate, cost, p50_latency
  passed         boolean not null,
  created_at     timestamptz not null default now()
);
