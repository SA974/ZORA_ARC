# Références scientifiques

L'architecture mémoire de ZORA_ARC / ARC-MEM Bridge s'appuie sur deux travaux de recherche.
Ce projet en est une **implémentation locale (100 % Ollama)** et s'en inspire ; tout le
crédit conceptuel revient à leurs auteurs.

## H-MEM — mémoire hiérarchique

> **Hierarchical Memory for High-Efficiency Long-Term Reasoning in LLM Agents**
> Haoran Sun, Shaoning Zeng. 2025. arXiv:2507.22925.
> https://arxiv.org/abs/2507.22925

Inspire : la mémoire hiérarchique multi-niveaux, le routage descendant par index, et la
régulation temporelle (courbe d'oubli d'Ebbinghaus + renforcement/affaiblissement par
feedback) — implémentée ici dans `app/migrations/006_temporal_and_embeddings.sql`,
`app/services/temporal_service.py`, `app/services/hmem_*.py`.

```bibtex
@article{sun2025hmem,
  title   = {Hierarchical Memory for High-Efficiency Long-Term Reasoning in LLM Agents},
  author  = {Sun, Haoran and Zeng, Shaoning},
  journal = {arXiv preprint arXiv:2507.22925},
  year    = {2025},
  url     = {https://arxiv.org/abs/2507.22925}
}
```

## MemGraphRAG — mémoire-graphe multi-agents

> **MemGraphRAG: Memory-based Multi-Agent System for Graph Retrieval-Augmented Generation**
> Chuanjie Wu, Zhishang Xiang, Yunbo Tang, Zerui Chen, Qinggang Zhang, Jinsong Su.
> KDD 2026. arXiv:2606.00610.
> Article : https://arxiv.org/abs/2606.00610
> Code : https://github.com/XMUDeepLIT/MemGraphRAG

Inspire : la structure en trois couches (ontologie / faits / passages) avec liens
bidirectionnels, la détection/résolution de conflits, et le retrieval hiérarchique combinant
similarité d'embedding et Personalized PageRank — implémentés ici dans
`app/services/memgraph_service.py`, `app/services/extraction_service.py`,
`app/services/ppr_service.py` et le schéma `app/migrations/003_init_memgraph_schema.sql`.

```bibtex
@inproceedings{wu2026memgraphrag,
  title     = {MemGraphRAG: Memory-based Multi-Agent System for Graph Retrieval-Augmented Generation},
  author    = {Wu, Chuanjie and Xiang, Zhishang and Tang, Yunbo and Chen, Zerui and Zhang, Qinggang and Su, Jinsong},
  booktitle = {Proceedings of the ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  year      = {2026},
  note      = {arXiv:2606.00610},
  url       = {https://arxiv.org/abs/2606.00610}
}
```

---

## Fondations conceptuelles — Pensée complexe, systèmes et résilience

> **De la révolution du complexe à la pensée du complexe**
> Janine Guespin-Michel. Mai 2018. Creative Commons.
> http://penseeducomplexe.free.fr

Inspire l'approche **holistique** de l'architecture ZORA_ARC : la mémoire comme système
complexe auto-organisé, où les faits/entités/passages forment des patrons interconnectés
plutôt que des structures arborescentes rigides.

> **Approche de la résilience et perturbations des systèmes complexes par une évaluation globale**
> Véronique Thomas-Vaslin, Frédéric Jacquemart.
> (Global evaluation of the resilience and perturbations of complex systems)

Cadre pour évaluer la robustesse du graphe MemGraphRAG sous conflits temporels et
perturbations d'extraction (feedback, supersession).

> **Extended Criticality, Phase Spaces and Enablement in Biology**
> Longo, G., Montévil, M. (2013). *Chaos, Soliton and Fractals*, 55, 64-79.
> DOI: 10.1016/j.chaos.2013.07.001

Notion d'**espaces de phase** appliquée au retrieval hiérarchique : la requête navigue dans un
espace latent de domaines/faits/passages, structuré par les transitions (arêtes H-MEM).

> **Man and His Environment: Biomedical Knowledge and Social Action**
> René Dubos. 1966.

Perspective écologique sur l'intégration de la connaissance humaine dans les systèmes
informatiques — ZORA_ARC comme un *environnement* où les mémoires et faits coévoluent.

> **René Dubos, Tuberculosis, and the Ecological Facets of Virulence**
> Mark Honigsbaum. *HPLS* (2017), 39:15.
> DOI: 10.1007/s40656-017-0142-51

Application historique de la pensée écologique et contextuelle à la maladie
(Dubos/Rickettsias) : modèle d'une connaissance qui reflète les **contextes** plutôt que les
*essences* — analogie avec les faits MemGraphRAG, validés par leurs passages de provenance.

---

> Note : cette implémentation diverge des papiers sur certains points (routage index-based
> H-MEM, PPR conforme, types de conflits, gating de schéma) — voir la feuille de route
> interne de mise à niveau. Les choix d'ingénierie (ex. formule de décroissance temporelle)
> sont documentés dans les migrations correspondantes.
