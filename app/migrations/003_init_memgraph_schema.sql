create schema if not exists memgraph;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'memgraph_status') then
    create type memgraph.memgraph_status as enum ('pending', 'stable', 'inactive', 'active');
  end if;
end $$;

create table if not exists memgraph.mem_schemas (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  version text not null default 'v0.1',
  definition jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists memgraph.mem_entities (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  entity_type text not null default 'unknown',
  status memgraph.memgraph_status not null default 'active',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  unique(name, entity_type)
);

create table if not exists memgraph.mem_passages (
  id uuid primary key default gen_random_uuid(),
  source_document_id uuid references zora.documents(id) on delete set null,
  source_chunk_id uuid references zora.chunks(id) on delete set null,
  passage_text text not null,
  provenance_text text not null,
  status memgraph.memgraph_status not null default 'pending',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  constraint mem_passages_has_provenance check (
    source_document_id is not null or source_chunk_id is not null or length(provenance_text) > 0
  )
);

create table if not exists memgraph.mem_facts (
  id uuid primary key default gen_random_uuid(),
  subject text not null,
  predicate text not null,
  object_value text not null,
  source_document_id uuid references zora.documents(id) on delete set null,
  source_chunk_id uuid references zora.chunks(id) on delete set null,
  provenance_text text not null,
  confidence numeric(4,3) not null default 0.500,
  status memgraph.memgraph_status not null default 'pending',
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  constraint mem_facts_has_provenance check (
    source_document_id is not null or source_chunk_id is not null or length(provenance_text) > 0
  )
);

create table if not exists memgraph.mem_bridges (
  id uuid primary key default gen_random_uuid(),
  left_type text not null,
  left_id uuid not null,
  right_type text not null,
  right_id uuid not null,
  relation_type text not null,
  weight numeric(6,4) not null default 1.0000,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists memgraph.mem_conflicts (
  id uuid primary key default gen_random_uuid(),
  fact_id uuid references memgraph.mem_facts(id) on delete cascade,
  conflicting_fact_id uuid references memgraph.mem_facts(id) on delete cascade,
  conflict_type text not null,
  status memgraph.memgraph_status not null default 'pending',
  resolution_text text,
  created_at timestamptz not null default now()
);
