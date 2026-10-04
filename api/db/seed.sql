-- Seed: channel blocklist and ingest sources.
--
-- The blocklist below is FICTIONAL demo data. In a real instance, list the
-- staffing agencies and body shops you've learned to skip; the same names go in
-- STAFFING in app/rules/filters.py.

insert into companies (name, kind, blocklisted) values
 ('Talentbridge Staffing', 'staffing', true),
 ('Nearshore Squad', 'staffing', true),
 ('Codeforce Partners', 'consultancy', true),
 ('Staffwise', 'staffing', true),
 ('Devhire Collective', 'staffing', true)
on conflict do nothing;

insert into sources (name, adapter, config) values
 -- The paste box: roles from sites that block automation (LinkedIn and others).
 ('paste', 'paste', '{}'),

 -- WATCHLIST: known companies, whole board polled directly. Add a company with
 --   python -m app.cli boards --add <greenhouse-token>
 -- The token is the slug in boards.greenhouse.io/<token>. Empty in the demo.
 ('greenhouse_boards', 'greenhouse', '{"boards": []}'),

 -- DISCOVERY: surfaces NEW companies by keyword. One query per role family keeps
 -- each daily pull small and on target.
 ('remotive_product_analyst', 'remotive',
  '{"search": "product analyst", "limit": 30}'),
 ('remotive_growth_analyst', 'remotive',
  '{"search": "growth analyst", "limit": 30}'),
 ('remotive_data_analyst', 'remotive',
  '{"search": "analytics", "category": "data", "limit": 40}')
on conflict (name) do nothing;
