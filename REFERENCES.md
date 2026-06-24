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

> Note : cette implémentation diverge des papiers sur certains points (routage index-based
> H-MEM, PPR conforme, types de conflits, gating de schéma) — voir la feuille de route
> interne de mise à niveau. Les choix d'ingénierie (ex. formule de décroissance temporelle)
> sont documentés dans les migrations correspondantes.
