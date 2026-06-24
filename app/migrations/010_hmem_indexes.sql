-- 010_hmem_indexes.sql
-- Index pour la mémoire hiérarchique H-MEM (peuplement + routage descendant).
-- Idempotent (create index if not exists).

-- Recherche d'un nœud par cible (déduplication select-or-insert du builder).
create index if not exists idx_hmem_nodes_target
  on hmem.memory_nodes(target_schema, target_table, target_id);

-- Recherche des nœuds par niveau (sélection de couche : domain/theme/entity/fact/passage).
create index if not exists idx_hmem_nodes_layer
  on hmem.memory_nodes(layer_id);

-- Recherche d'un nœud domaine par label (ensure_domain).
create index if not exists idx_hmem_nodes_label
  on hmem.memory_nodes(label);

-- Traversée des arêtes (routage descendant).
create index if not exists idx_hmem_edges_source on hmem.memory_edges(source_node_id);
create index if not exists idx_hmem_edges_target on hmem.memory_edges(target_node_id);
