-- Esquema de reporting del pipeline de desempeño de negocio.
-- Se ejecuta una vez en el SQL Editor de Supabase. Nunca se escribe en telemetry_events.

create schema if not exists reporting;

-- Destino principal: tabla y constraint exactos del BRIEFING (sección 5).
create table if not exists reporting.weekly_location_performance (
  id uuid primary key default gen_random_uuid(),
  location_id text not null,
  country text not null,
  week_start date not null,
  total_purchase_cost numeric not null default 0,
  total_waste_cost numeric not null default 0,
  waste_ratio numeric not null default 0,
  stockout_events_count integer not null default 0,
  price_alert_events_count integer not null default 0,
  currency text not null,
  computed_at timestamptz not null default now(),
  unique (location_id, week_start)
);

-- Los 14 locales con su país y moneda (fuente de verdad del país de cada local).
create table if not exists reporting.location_dim (
  location_id text primary key,
  country     text not null check (country in ('CO', 'US')),
  currency    text not null check (currency in ('COP', 'USD')),
  name        text
);

-- Registro de ejecución: auditoría, punto de control y bloqueo.
create table if not exists reporting.pipeline_runs (
  run_id              uuid primary key default gen_random_uuid(),
  pipeline_name       text not null,
  trigger_type        text not null check (trigger_type in ('schedule', 'manual', 'backfill')),
  window_start        date not null,
  window_end          date not null,
  status              text not null check (status in
                        ('running', 'completed', 'completed_with_warnings', 'failed', 'skipped_locked')),
  phase               text not null default 'open'
                        check (phase in ('open', 'extract', 'transform', 'load', 'close')),
  started_at          timestamptz not null default now(),
  finished_at         timestamptz,
  rows_extracted      integer,
  rows_after_dedup    integer,
  rows_rejected       integer,
  rows_inserted       integer,
  rows_updated        integer,
  rows_unchanged      integer,
  error_message       text,
  resumed_from_run_id uuid references reporting.pipeline_runs (run_id),
  prefect_flow_run_id text,
  details             jsonb not null default '{}'::jsonb
);

-- Bloqueo: una sola corrida "running" por pipeline.
create unique index if not exists ux_pipeline_runs_one_running
  on reporting.pipeline_runs (pipeline_name) where status = 'running';

-- Solo el backend (conexión directa) accede a estas tablas.
alter table reporting.weekly_location_performance enable row level security;
alter table reporting.location_dim enable row level security;
alter table reporting.pipeline_runs enable row level security;
