-- 006_temporal_and_embeddings.sql
-- Paramétrage des tables pour : (1) embeddings sur la couche faits/entités MemGraphRAG,
-- (2) modèle temporel bi-temporel + décroissance + feedback inspiré de H-MEM (arXiv:2507.22925).
--
-- NOTE D'INGÉNIERIE : H-MEM décrit le mécanisme temporel de façon QUALITATIVE (approbation -> ++,
-- pas de feedback -> courbe d'oubli, réfutation -> --) sans équation. Le modèle ci-dessous
-- (décroissance exponentielle type Ebbinghaus + feedback multiplicatif) est notre choix
-- d'implémentation explicite, pas une formule verbatim du papier.
--
-- Sémantique temporelle (bi-temporelle) :
--   created_at  = transaction time  (quand la ligne a été écrite)            [déjà présent]
--   observed_at = event time        (quand le fait a été observé/asserté)
--   valid_from / valid_to = valid time (intervalle de validité réelle ; valid_to NULL = encore vrai)
-- Toutes les colonnes sont NULLABLE ou avec DEFAULT : ALTER non bloquant (mem_facts est vide).

-- 1) Embeddings (même espace que zora.chunks : Ollama nomic-embed-text, vector(768)) ----------
alter table memgraph.mem_facts    add column if not exists embedding vector(768);
alter table memgraph.mem_entities add column if not exists embedding vector(768);

-- 2) Modèle temporel + décroissance sur la couche faits ---------------------------------------
alter table memgraph.mem_facts add column if not exists observed_at     timestamptz not null default now();
alter table memgraph.mem_facts add column if not exists valid_from      timestamptz;
alter table memgraph.mem_facts add column if not exists valid_to        timestamptz;
alter table memgraph.mem_facts add column if not exists salience        numeric(6,4) not null default 1.0000;  -- poids courant [0,1]
alter table memgraph.mem_facts add column if not exists decay_rate      numeric(8,6) not null default 0.010000; -- lambda / jour (Ebbinghaus)
alter table memgraph.mem_facts add column if not exists last_accessed_at timestamptz;
alter table memgraph.mem_facts add column if not exists access_count    integer not null default 0;
alter table memgraph.mem_facts add column if not exists reinforced_count integer not null default 0;
alter table memgraph.mem_facts add column if not exists superseded_by   uuid references memgraph.mem_facts(id) on delete set null;

-- Garde-fou : un intervalle de validité cohérent
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'mem_facts_valid_interval') then
    alter table memgraph.mem_facts
      add constraint mem_facts_valid_interval check (valid_to is null or valid_from is null or valid_to >= valid_from);
  end if;
end $$;

-- 3) Enrichissement de la table de conflits (traçabilité de la détection) ----------------------
alter table memgraph.mem_conflicts add column if not exists similarity   numeric(6,4);
alter table memgraph.mem_conflicts add column if not exists detected_via text not null default 'manual';
alter table memgraph.mem_conflicts add column if not exists resolved_at  timestamptz;

-- 4) Journal de feedback (mécanisme H-MEM : approbation / neutre / réfutation) ------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'feedback_signal') then
    create type memgraph.feedback_signal as enum ('approval', 'neutral', 'rebuttal');
  end if;
end $$;

create table if not exists memgraph.mem_feedback (
  id uuid primary key default gen_random_uuid(),
  fact_id uuid not null references memgraph.mem_facts(id) on delete cascade,
  signal memgraph.feedback_signal not null,
  multiplier numeric(6,4) not null,          -- facteur appliqué à salience lors de l'événement
  salience_before numeric(6,4),
  salience_after numeric(6,4),
  source text not null default 'user',        -- user | llm | system
  note text,
  created_at timestamptz not null default now()
);

-- 5) Fonction de salience décroissante (évaluée au moment de la lecture) ------------------------
-- R(t) = base * exp(-decay_rate * âge_en_jours), borné [0,1]. STABLE car dépend de now().
create or replace function memgraph.fact_salience_now(
  base numeric,
  decay_rate numeric,
  ref timestamptz
) returns numeric
language sql stable as $$
  select greatest(0::numeric, least(1::numeric,
    coalesce(base, 1.0) * exp(
      - coalesce(decay_rate, 0.01)
      * (extract(epoch from (now() - coalesce(ref, now()))) / 86400.0)
    )
  ))
$$;

-- 6) Vue des faits actifs (non supplantés, encore valides, salience décroissante calculée) ------
create or replace view memgraph.v_active_facts as
select
  f.*,
  memgraph.fact_salience_now(f.salience, f.decay_rate, coalesce(f.last_accessed_at, f.observed_at)) as salience_now
from memgraph.mem_facts f
where f.superseded_by is null
  and (f.valid_to is null or f.valid_to > now())
  and f.status <> 'inactive';

-- 7) Index ------------------------------------------------------------------------------------
create index if not exists idx_mem_facts_observed_at on memgraph.mem_facts(observed_at);
create index if not exists idx_mem_facts_valid_from  on memgraph.mem_facts(valid_from);
create index if not exists idx_mem_facts_valid_to    on memgraph.mem_facts(valid_to);
create index if not exists idx_mem_facts_superseded   on memgraph.mem_facts(superseded_by);
create index if not exists idx_mem_feedback_fact      on memgraph.mem_feedback(fact_id);

do $$
begin
  if exists (select 1 from pg_extension where extname = 'vector') then
    begin
      create index if not exists idx_mem_facts_embedding_hnsw
      on memgraph.mem_facts using hnsw (embedding vector_cosine_ops);
    exception when others then
      create index if not exists idx_mem_facts_embedding_ivfflat
      on memgraph.mem_facts using ivfflat (embedding vector_cosine_ops);
    end;
  end if;
end $$;
