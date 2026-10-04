-- Fuente Jobgether. Correr una sola vez, con la app ya levantada:
--
--   docker compose exec -T db psql -U funnel -d funnel -f /docker-entrypoint-initdb.d/sources_jobgether.sql
--
-- (guardar este archivo en api/db/ para que docker lo vea en esa ruta)
--
-- Tres consultas, una por familia de puesto, para que cada pull sea chico y
-- apuntado. `locations: anywhere` pide explicitamente los que no restringen
-- pais — que es justo el problema que tiene la mitad del mercado remoto.
--
-- Enriquecer la busqueda = editar el campo config de estas filas. Los valores
-- validos de experience y contractType los devuelve la propia API en el error
-- cuando se manda uno que no existe.

insert into sources (name, adapter, config) values
 ('jobgether_data_analyst', 'jobgether',
  '{"keyword": "data analyst", "locations": ["anywhere"], "remoteType": "full-remote",
    "experience": ["senior-5-10-years", "mid-level-2-5-years"],
    "contractType": ["full-time"], "sort": "date", "limit": 25, "max_pages": 3}'),

 ('jobgether_product_analyst', 'jobgether',
  '{"keyword": "product analyst", "locations": ["anywhere"], "remoteType": "full-remote",
    "experience": ["senior-5-10-years", "mid-level-2-5-years"],
    "contractType": ["full-time"], "sort": "date", "limit": 25, "max_pages": 3}'),

 ('jobgether_analytics_eng', 'jobgether',
  '{"keyword": "analytics engineer", "locations": ["anywhere"], "remoteType": "full-remote",
    "experience": ["senior-5-10-years", "mid-level-2-5-years"],
    "contractType": ["full-time"], "sort": "date", "limit": 25, "max_pages": 2}')
on conflict (name) do update set config = excluded.config;
