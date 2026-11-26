-- Dead Letter Queue de las tareas de Celery (ticket DEV-55).
-- Se ejecuta una vez en el SQL Editor de Supabase.
--
-- Una tarea llega aquí cuando agota sus reintentos (intento inicial + 3
-- reintentos con backoff exponencial) o falla con un error no reintentable.
-- Guarda solo referencias: los kwargs del mensaje (ids y fechas), nunca datos.

create table if not exists public.task_dead_letters (
    id            uuid        primary key default gen_random_uuid(),
    task_id       text        not null,
    task_name     text        not null,
    -- Número del intento que falló por última vez (1 = intento inicial).
    attempt       integer     not null check (attempt >= 1),
    error_message text        not null,
    traceback     text,
    task_kwargs   jsonb       not null default '{}'::jsonb,
    failed_at     timestamptz not null default now(),
    -- Una redelivery del mismo mensaje no duplica la entrada.
    constraint ux_task_dead_letters_task_id unique (task_id)
);

create index if not exists ix_task_dead_letters_failed_at
    on public.task_dead_letters (failed_at desc);

-- Solo el backend (conexión directa) accede a la tabla; la API pública de Supabase no.
alter table public.task_dead_letters enable row level security;
