-- 013_monitoring_dashboard.sql
-- Tables de supervision : tâches, scripts, événements, compteurs d'ingestion

-- Tâches / jobs (scripts planifiés, imports batch, etc.)
create table if not exists public.monitoring_jobs (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  description text,
  script_path text,
  status text not null default 'idle',  -- idle, running, success, error
  last_started_at timestamptz,
  last_completed_at timestamptz,
  last_duration_seconds float,
  last_error text,
  items_processed int default 0,
  items_failed int default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Événements (log structuré pour le dashboard)
create table if not exists public.monitoring_events (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.monitoring_jobs(id) on delete set null,
  event_type text not null,  -- started, completed, error, skipped, info, success
  message text not null,
  details jsonb,
  timestamp timestamptz not null default now()
);

-- Compteurs d'ingestion (vue agrégée, mis à jour par triggers ou batch)
create table if not exists public.monitoring_ingestion_stats (
  id uuid primary key default gen_random_uuid(),
  domain text not null default 'global',
  total_files_detected int default 0,
  total_files_validated int default 0,
  total_files_ingested int default 0,
  total_files_failed int default 0,
  total_chunks_created int default 0,
  total_embeddings_generated int default 0,
  total_facts_extracted int default 0,
  total_db_records_stored int default 0,
  updated_at timestamptz not null default now(),
  unique(domain)
);

-- Index pour perf queries dashboard
create index if not exists idx_monitoring_jobs_status on public.monitoring_jobs(status);
create index if not exists idx_monitoring_jobs_updated on public.monitoring_jobs(updated_at desc);
create index if not exists idx_monitoring_events_timestamp on public.monitoring_events(timestamp desc);
create index if not exists idx_monitoring_events_job on public.monitoring_events(job_id);

-- Vue pour le dashboard : jobs actifs + récents
create or replace view public.v_monitoring_jobs_summary as
select
  j.id, j.name, j.status,
  j.last_started_at, j.last_completed_at, j.last_duration_seconds,
  j.last_error, j.items_processed, j.items_failed,
  (select count(*) from public.monitoring_events where job_id = j.id and timestamp > now() - interval '24 hours') as events_24h
from public.monitoring_jobs j
order by j.updated_at desc;

-- Vue pour le dashboard : événements récents (48h)
create or replace view public.v_monitoring_recent_events as
select
  e.id, e.job_id, j.name as job_name, e.event_type, e.message, e.timestamp
from public.monitoring_events e
left join public.monitoring_jobs j on j.id = e.job_id
where e.timestamp > now() - interval '48 hours'
order by e.timestamp desc;
