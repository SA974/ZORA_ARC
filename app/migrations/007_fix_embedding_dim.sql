-- 007_fix_embedding_dim.sql
-- Corriger la dimension d'embedding de 1024 à 768 pour aligner avec nomic-embed-text.
--
-- IDEMPOTENT : l'ALTER (réécriture coûteuse de ~888k lignes) n'est exécuté QUE si la
-- colonne n'est pas déjà en vector(768). Sans ce garde-fou, rejouer ce fichier
-- réécrivait toute la table à chaque passage du runner.

do $$
begin
  if (
    select format_type(atttypid, atttypmod)
    from pg_attribute
    where attrelid = 'zora.chunks'::regclass and attname = 'embedding'
  ) <> 'vector(768)' then
    alter table zora.chunks
      alter column embedding type vector(768) using embedding::vector(768);

    drop index if exists idx_zora_chunks_embedding_hnsw;
    drop index if exists idx_zora_chunks_embedding_ivfflat;
  end if;
end $$;

create index if not exists idx_zora_chunks_embedding_hnsw
on zora.chunks using hnsw (embedding vector_cosine_ops);
