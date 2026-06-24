-- 012_memgraphrag_quality_gates.sql
-- #3 Conflits MemGraphRAG : types + résolution evidence-driven
-- #4 Gating de schéma par fréquence (candidate -> stable)

-- #4 : Gating de schéma par fréquence
alter table memgraph.mem_schemas add column if not exists frequency_count integer not null default 0;
alter table memgraph.mem_schemas add column if not exists status text not null default 'candidate';
comment on column memgraph.mem_schemas.status is 'candidate ou stable ; seuls les schémas stable acceptent des faits au graphe';

-- #3 : Résolution evidence-driven pour conflits
alter table memgraph.mem_conflicts add column if not exists conflict_type_enum text;
alter table memgraph.mem_conflicts add column if not exists evidence_comparison text;
comment on column memgraph.mem_conflicts.conflict_type_enum is 'temporal, mutually_exclusive, ou granularity';
comment on column memgraph.mem_conflicts.evidence_comparison is 'comparaison texte des passages : qui a la meilleure provenance ?';

-- Vue pour les schémas stables (prêts à être utilisés dans le graphe)
create or replace view memgraph.v_stable_schemas as
  select * from memgraph.mem_schemas where status = 'stable';
