-- Registro de ejecuciones de los jobs nocturnos (orquestación).
-- Se ejecuta una vez en el SQL Editor de Supabase.
--
-- No es reporting.pipeline_runs: job_runs registra el script nocturno
-- (export CSV, disparo del pipeline, lock e idempotencia por día);
-- pipeline_runs registra las fases internas del ETL que ese script lanza.

create table if not exists public.job_runs (
    id            uuid        primary key default gen_random_uuid(),
    job_name      text        not null,
    -- Día que procesa la ejecución (UTC). Clave de la idempotencia por día.
    target_date   date        not null,
    status        text        not null default 'pending'
                  check (status in ('pending', 'processing', 'completed', 'failed')),
    -- Ejecución que terminó sin trabajar: 'duplicate' (el día ya estaba completado)
    -- o 'locked' (otra instancia estaba en processing). Solo con status completed.
    skip_reason   text        check (skip_reason in ('duplicate', 'locked')),
    started_at    timestamptz,
    finished_at   timestamptz,
    error_message text,
    -- CSV exportado, filas, run_id del pipeline, código de salida...
    details       jsonb       not null default '{}'::jsonb,
    created_at    timestamptz not null default now(),
    constraint ck_job_runs_skip_only_completed
        check (skip_reason is null or status = 'completed')
);

-- Consultas de idempotencia: ¿existe ya un completed para (job_name, target_date)?
create index if not exists ix_job_runs_job_name_target_date
    on public.job_runs (job_name, target_date);

-- El lock ES el estado processing. Este índice no es un segundo mecanismo:
-- hace atómica la transición a processing, de modo que si dos instancias
-- arrancan a la vez solo una puede tener su fila en processing.
create unique index if not exists ux_job_runs_one_processing
    on public.job_runs (job_name) where status = 'processing';

-- Solo el backend (conexión directa) accede a la tabla; la API pública de Supabase no.
alter table public.job_runs enable row level security;
