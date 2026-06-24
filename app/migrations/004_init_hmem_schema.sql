create schema if not exists hmem;

create table if not exists hmem.memory_layers (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  ordinal integer not null unique,
  description text not null default '',
  created_at timestamptz not null default now()
);

insert into hmem.memory_layers(name, ordinal, description)
values
  ('domain', 1, 'Top-level ARC-MEM domain'),
  ('theme', 2, 'Major memory theme'),
  ('subtheme', 3, 'Narrower routing topic'),
  ('entity', 4, 'Entity-level memory node'),
  ('fact', 5, 'Fact-level node'),
  ('passage', 6, 'Passage-level node')
on conflict (name) do nothing;

create table if not exists hmem.memory_nodes (
  id uuid primary key default gen_random_uuid(),
  layer_id uuid not null references hmem.memory_layers(id) on delete restrict,
  label text not null,
  target_schema text,
  target_table text,
  target_id uuid,
  external_ref text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now(),
  constraint memory_nodes_target_allowed check (
    (target_schema is null and target_table is null and target_id is null)
    or (target_schema = 'zora' and target_table in ('documents', 'chunks'))
    or (target_schema = 'memgraph' and target_table in ('mem_entities', 'mem_facts', 'mem_passages'))
    or (target_schema = 'hindsight' and external_ref is not null and target_id is null)
  )
);

create table if not exists hmem.memory_edges (
  id uuid primary key default gen_random_uuid(),
  source_node_id uuid not null references hmem.memory_nodes(id) on delete cascade,
  target_node_id uuid not null references hmem.memory_nodes(id) on delete cascade,
  edge_type text not null default 'routes_to',
  weight numeric(6,4) not null default 1.0000,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists hmem.positional_indexes (
  id uuid primary key default gen_random_uuid(),
  node_id uuid not null references hmem.memory_nodes(id) on delete cascade,
  position_path text not null,
  rank_hint numeric(8,4) not null default 0,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists hmem.routing_paths (
  id uuid primary key default gen_random_uuid(),
  query_hash text not null,
  path jsonb not null,
  score numeric(6,4) not null default 0,
  created_at timestamptz not null default now()
);
