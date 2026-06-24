# ARC-MEM Bridge Architecture

Version: ARC-MEM Bridge v0.1  
Architecture cible: ZORA_ARC V9.2 ARC-MEM-H

## Séparation des responsabilités

Hindsight est la mémoire agentique persistante. Il conserve les préférences utilisateur, décisions de projet, résumés intersessions et contexte Hermes. Sur Windows, le mode opérationnel retenu est `postgresql_direct`: ARC-MEM Bridge lit et écrit directement dans PostgreSQL `hindsight_hermes`, sans daemon Hindsight et sans PostgreSQL embedded.

MemGraphRAG est la mémoire documentaire probatoire. Elle conserve documents, chunks, passages, entités, faits, relations, conflits, preuves et provenance. La chaîne cible est source -> chunk -> passage -> fait -> réponse.

H-MEM est le routeur hiérarchique. Il organise les niveaux domain, theme, subtheme, entity, fact et passage. Ses noeuds peuvent pointer vers `zora`, `memgraph`, ou vers un souvenir Hindsight par référence externe.

PostgreSQL est la base centrale unique au niveau serveur. `rag_arc` porte les schémas applicatifs `zora`, `memgraph` et `hmem`; `hindsight_hermes` porte la mémoire agentique directe déjà migrée. Aucun PostgreSQL embedded n’est utilisé.

Hermes Desktop reste l’interface agent. ARC-MEM Bridge l’expose via API locale et CLI, avec diagnostic sans modification brutale.

ZORA ARC gouverne les tâches avec TASKCARD, score routeur, modules indicatifs, preuve, audit et gates qualité.
