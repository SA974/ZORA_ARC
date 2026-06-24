"""ARC-MEM System — package racine organisant le système en DEUX blocs fonctionnels :

- ``arc_mem_bridge``   : pont Hermes <-> PostgreSQL, ingestion PDF, chunks, embeddings,
                         stockage, journalisation, provider Ollama, healthcheck.
- ``memory_rag_core``  : H-MEM (mémoire hiérarchique) + MemGraphRAG (entités, faits,
                         passages, conflits), retrieval et scoring.

⚠️ Façade de compatibilité : l'implémentation vit aujourd'hui dans le package ``app`` ; ce
package ré-exporte cette logique sous une surface unique et organisée, sans casser les
imports ``app.*`` existants (utilisés par Hermes et les scripts). La migration physique du
code vers ``src/arc_mem_system`` peut se faire ensuite, module par module, derrière ces façades.
"""

__version__ = "0.2.0"
