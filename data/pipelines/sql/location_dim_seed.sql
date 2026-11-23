-- Semilla de reporting.location_dim (14 locales).
-- El país de cada local se toma de los eventos ya observados en telemetry_events;
-- los locales sin eventos quedan como Colombia por defecto. CONFIRMAR con el negocio
-- (Felipe) y corregir con un update si algún local es de Florida.

with observed as (
  select tags ->> 'location_id' as location_id,
         tags ->> 'country' as country,
         count(*) as n
  from public.telemetry_events
  where tags ->> 'location_id' is not null and tags ->> 'country' is not null
  group by 1, 2
),
best as (
  select distinct on (location_id) location_id, country
  from observed
  order by location_id, n desc
)
insert into reporting.location_dim (location_id, country, currency)
select g.id::text,
       coalesce(b.country, 'CO'),
       case when coalesce(b.country, 'CO') = 'US' then 'USD' else 'COP' end
from generate_series(1, 14) as g(id)
left join best b on b.location_id = g.id::text
on conflict (location_id) do nothing;
