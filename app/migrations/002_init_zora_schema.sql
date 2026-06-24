create schema if not exists zora;

create table if not exists zora.taskcards (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  objective text not null,
  central_question text not null,
  expected_deliverable text not null,
  provided_data jsonb not null default '[]',
  constraints jsonb not null default '[]',
  expected_evidence_level text not null default 'standard',
  created_at timestamptz not null default now()
);

create table if not exists zora.arc_runs (
  id uuid primary key default gen_random_uuid(),
  taskcard_id uuid references zora.taskcards(id) on delete set null,
  status text not null default 'pending',
  router_score jsonb not null default '{}',
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists zora.documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_uri text,
  content_hash text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists zora.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references zora.documents(id) on delete cascade,
  ordinal integer not null,
  content text not null,
  embedding vector(1024),
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(document_id, ordinal)
);

create table if not exists zora.evidence_registry (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references zora.documents(id) on delete set null,
  chunk_id uuid references zora.chunks(id) on delete set null,
  evidence_type text not null,
  claim text not null,
  confidence numeric(4,3) not null default 0.500,
  provenance jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists zora.citations (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references zora.documents(id) on delete set null,
  chunk_id uuid references zora.chunks(id) on delete set null,
  citation_text text not null,
  locator text,
  created_at timestamptz not null default now()
);

create table if not exists zora.arc_audit_log (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references zora.arc_runs(id) on delete set null,
  event_type text not null,
  severity text not null default 'info',
  message text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
