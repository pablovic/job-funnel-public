-- Job Funnel — metric layer.
-- One definition per metric, named, owned here and nowhere else. The API and the
-- weekly Obsidian digest both read these views; no metric is redefined in Python.

-- Current stage per application (last event wins).
create or replace view v_application_state as
select
  a.id                as application_id,
  a.opportunity_id,
  a.applied_at,
  a.cv_variant,
  a.comp_asked_usd,
  a.channel,
  -- La etapa actual es el ultimo evento. El desempate importa: cuando un acuse
  -- llega el mismo dia de la postulacion, los dos eventos comparten marca de
  -- tiempo y "el ultimo" queda librado al azar.
  --
  -- enum_range devuelve los valores del enum `stage` en el orden en que estan
  -- declarados en schema.sql, que es el del embudo: applied, ack, screening,
  -- technical, onsite, offer, rejected, withdrawn, ghosted. Ante un empate gana
  -- el que esta mas adelante, que es siempre la lectura correcta: si hay un
  -- acuse y una postulacion el mismo dia, la etapa es el acuse.
  (select e.stage from application_events e
     where e.application_id = a.id
     order by e.occurred_at desc,
              array_position(enum_range(null::stage), e.stage) desc
     limit 1)                                                           as current_stage,
  -- "Primera respuesta" es la primera vez que contesto LA EMPRESA. Tres etapas
  -- no son eso y por lo tanto no cuentan:
  --   applied    la postulacion misma
  --   ghosted    la ausencia de respuesta; registrarla como respuesta seria
  --              exactamente al reves de lo que significa
  --   withdrawn  bajarse es una accion propia, no una contestacion
  -- Si hubo contacto real antes de bajarse, ese evento existe igual y cuenta.
  (select min(e.occurred_at) from application_events e
     where e.application_id = a.id
       and e.stage not in ('applied', 'ghosted', 'withdrawn'))           as first_response_at
from applications a;

-- The funnel. Denominators are explicit on purpose: every earlier diagnosis in
-- this project went wrong by comparing against the wrong base.
--
-- NOTA SOBRE `kept` (agregada al final a proposito):
-- Postgres permite reemplazar una vista solo si las columnas existentes quedan
-- en el mismo orden; se pueden AGREGAR al final, nunca en el medio. Por eso
-- `kept` va ultima aunque conceptualmente viva entre shortlisted y applied.
--
-- Son tres filtros, no dos:
--   surfaced     lo que paso el filtro automatico (reglas)
--   shortlisted  lo que paso el filtro rapido (yes/maybe en el deck)
--   kept         lo que sobrevivio a la lectura atenta (no archivado)
--   applied      lo que efectivamente se envio
create or replace view v_funnel as
select
  count(*) filter (where o.status <> 'rejected_by_rules')                    as surfaced,
  count(*) filter (where l.verdict in ('yes', 'maybe'))                      as shortlisted,
  count(distinct a.id)                                                       as applied,
  count(*) filter (where s.first_response_at is not null)                    as responded,
  count(*) filter (where s.current_stage in ('screening','technical','onsite','offer')) as in_process,
  count(*) filter (where s.current_stage = 'offer')                          as offers,
  round(100.0 * count(distinct a.id)
        / nullif(count(*) filter (where l.verdict in ('yes','maybe')), 0), 1) as apply_rate_pct,
  round(100.0 * count(*) filter (where s.first_response_at is not null)
        / nullif(count(distinct a.id), 0), 1)                                 as response_rate_pct,
  count(*) filter (where l.verdict in ('yes','maybe') and o.status <> 'archived') as kept
from opportunities o
left join labels l                on l.opportunity_id = o.id
left join applications a          on a.opportunity_id = o.id
left join v_application_state s   on s.application_id = a.id
where o.vertical = 'job';

-- Response rate by CV variant. Read it, do not act on it: see v_power_check.
create or replace view v_response_by_variant as
select
  cv_variant,
  count(*)                                                        as applications,
  count(*) filter (where first_response_at is not null)           as responses,
  round(100.0 * count(*) filter (where first_response_at is not null)
        / nullif(count(*), 0), 1)                                 as response_rate_pct,
  round(avg(extract(epoch from first_response_at - applied_at) / 86400)::numeric, 1) as avg_days_to_response
from v_application_state
group by cv_variant;

-- Guardrail against the failure mode this project was built to avoid: declaring
-- a winner on a sample that cannot support one. Baseline 8%, MDE 30% relative,
-- 80% power, alpha 0.05 -> ~1,000 per arm. Anything below that is descriptive.
create or replace view v_power_check as
select
  (select count(*) from applications)                       as n_applications,
  1000                                                      as n_needed_per_arm,
  (select count(*) from applications) >= 2000               as can_compare_variants,
  'Below n=2000 the variant comparison is descriptive only. Do not rewrite the CV on it.'::text as guidance;

-- Where reading effort goes vs where applications come from. The 2026 diagnosis
-- was 31 saved / 3 applied; this keeps that number visible weekly.
-- `dropped_on_review` es el nuevo tercer filtro, semana a semana: cuantas de las
-- que pasaron el filtro rapido no sobrevivieron a la lectura atenta.
create or replace view v_effort_leak as
select
  date_trunc('week', o.captured_at)::date                          as week,
  count(*)                                                          as ingested,
  count(*) filter (where o.status = 'rejected_by_rules')             as auto_filtered,
  count(*) filter (where l.id is not null)                           as reviewed,
  count(*) filter (where l.verdict = 'yes')                          as shortlisted,
  count(a.id)                                                        as applied,
  count(*) filter (where o.status = 'archived')                      as dropped_on_review
from opportunities o
left join labels l       on l.opportunity_id = o.id
left join applications a on a.opportunity_id = o.id
group by 1 order by 1 desc;

-- Bias audit. In the labeled set of Sep 2026, 10/10 "no" verdicts cited
-- overqualification and none of them published a salary range — the filter was
-- firing on HR disclosure policy, not on fit. This view reruns that test.
create or replace view v_bias_comp_published as
select
  j.comp_published,
  count(*)                                             as reviewed,
  count(*) filter (where l.verdict = 'no')             as rejected,
  round(100.0 * count(*) filter (where l.verdict = 'no')
        / nullif(count(*), 0), 1)                      as reject_rate_pct
from labels l
join job_details j on j.opportunity_id = l.opportunity_id
group by 1;

-- Agreement between the scorer and my own labels, per model version.
create or replace view v_scorer_agreement as
select
  s.model_version,
  l.verdict,
  count(*)                        as n,
  round(avg(s.fit), 1)            as mean_fit,
  min(s.fit)                      as min_fit,
  max(s.fit)                      as max_fit
from scores s
join labels l on l.opportunity_id = s.opportunity_id
group by 1, 2 order by 1, 2;

-- Applications with no response and no follow-up, past the nudge window.
create or replace view v_needs_followup as
select
  a.application_id, o.title, c.name as company, a.applied_at,
  (now()::date - a.applied_at::date) as days_since
from v_application_state a
join opportunities o  on o.id = a.opportunity_id
left join job_details j on j.opportunity_id = o.id
left join companies c on c.id = j.company_id
where a.first_response_at is null
  and a.applied_at < now() - interval '7 days'
  -- Ya cerradas: no hay a quien hacerle seguimiento. Sin esto, una postulacion
  -- marcada como ghosted o withdrawn aparecia en el aviso para siempre.
  and a.current_stage not in ('ghosted', 'withdrawn', 'rejected')
order by a.applied_at;
