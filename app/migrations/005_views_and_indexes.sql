create index if not exists idx_zora_documents_title_trgm on zora.documents using gin (title gin_trgm_ops);
create index if not exists idx_zora_chunks_content_trgm on zora.chunks using gin (content gin_trgm_ops);
create index if not exists idx_zora_chunks_document_id on zora.chunks(document_id);

create index if not exists idx_mem_entities_name_trgm on memgraph.mem_entities using gin (name gin_trgm_ops);
create index if not exists idx_mem_facts_subject on memgraph.mem_facts(subject);
create index if not exists idx_mem_facts_predicate on memgraph.mem_facts(predicate);
create index if not exists idx_mem_facts_source_document on memgraph.mem_facts(source_document_id);
create index if not exists idx_mem_passages_source_chunk on memgraph.mem_passages(source_chunk_id);
create index if not exists idx_mem_bridges_left on memgraph.mem_bridges(left_type, left_id);
create index if not exists idx_mem_bridges_right on memgraph.mem_bridges(right_type, right_id);

create index if not exists idx_hmem_nodes_label_trgm on hmem.memory_nodes using gin (label gin_trgm_ops);
create index if not exists idx_hmem_edges_source on hmem.memory_edges(source_node_id);
create index if not exists idx_hmem_edges_target on hmem.memory_edges(target_node_id);
create index if not exists idx_hmem_position_path on hmem.positional_indexes(position_path);

do $$
begin
  if exists (select 1 from pg_extension where extname = 'vector') then
    begin
      create index if not exists idx_zora_chunks_embedding_hnsw
      on zora.chunks using hnsw (embedding vector_cosine_ops);
    exception when others then
      create index if not exists idx_zora_chunks_embedding_ivfflat
      on zora.chunks using ivfflat (embedding vector_cosine_ops);
    end;
  end if;
end $$;

create or replace view memgraph.v_graphe_ppr as
select
  left_id::text as source_id,
  right_id::text as target_id,
  weight::float8 as weight,
  relation_type
from memgraph.mem_bridges
union all
select
  source_node_id::text as source_id,
  target_node_id::text as target_id,
  weight::float8 as weight,
  edge_type as relation_type
from hmem.memory_edges;
