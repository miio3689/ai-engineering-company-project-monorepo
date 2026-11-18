-- Eventos de telemetría del backoffice (8 columnas, 3 índices).
-- Tabla de solo escritura: los eventos son hechos inmutables y no hay lógica
-- de UPDATE ni de DELETE en la API.

create table if not exists public.telemetry_events (
    id          uuid        primary key default gen_random_uuid(),
    "timestamp" timestamptz not null,
    service     text        not null,
    event_type  text        not null,
    level       text        default 'info' check (level in ('info', 'warn', 'error')),
    value       numeric,
    message     text,
    tags        jsonb       default '{}'::jsonb
);

create index if not exists ix_telemetry_events_timestamp
    on public.telemetry_events ("timestamp");
create index if not exists ix_telemetry_events_event_type
    on public.telemetry_events (event_type);
create index if not exists ix_telemetry_events_tags
    on public.telemetry_events using gin (tags);

-- Solo el backend (conexión directa) accede a la tabla; la API pública de Supabase no.
alter table public.telemetry_events enable row level security;
