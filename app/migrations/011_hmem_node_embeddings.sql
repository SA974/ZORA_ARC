-- 011_hmem_node_embeddings.sql
-- Routage index-based H-MEM (arXiv:2507.22925) : chaque nœud de la hiérarchie porte un
-- vecteur sémantique pour calculer sim(q, nœud) couche par couche et ÉLAGUER la descente
-- (M_k^(l) = ⋃_{x∈M_k^(l-1)} TopK_{y∈Child(x)} sim(q,y)), au lieu d'une recherche plate.
--
-- Pour les nœuds-cible (entity/fact), le vecteur vit déjà dans memgraph.mem_*; pour les
-- nœuds d'index (domain/theme/subtheme) on stocke ici un embedding dédié (768D Ollama).

alter table hmem.memory_nodes add column if not exists embedding vector(768);

do $$
begin
  if exists (select 1 from pg_extension where extname = 'vector') then
    begin
      create index if not exists idx_hmem_nodes_embedding_hnsw
      on hmem.memory_nodes using hnsw (embedding vector_cosine_ops);
    exception when others then
      null;  -- index best-effort
    end;
  end if;
end $$;
