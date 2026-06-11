# ZORA_ARC
## 1. Définition générale

**ZORA ARC** est une architecture méthodologique conçue pour transformer une demande complexe, floue, sensible ou multi-projets en un **livrable structuré, sourcé, contrôlé et directement exploitable**.

Son objectif n’est pas seulement de répondre à une question. Son objectif est plus profond : **organiser les conditions de validité de la réponse**.

Autrement dit, ZORA ARC sert à éviter le passage trop rapide :

```text
Question → Réponse immédiate
```

et à le remplacer par une chaîne plus robuste :

```text
Demande → Cadrage → Qualification → Plan → Preuves → Rédaction → Audit → Correction → Livraison
```

ZORA ARC est donc à la fois :

* une méthode de cadrage ;
* un système d’analyse ;
* un routeur de complexité ;
* un dispositif d’audit ;
* un outil de production de livrables ;
* une architecture de sécurisation des tâches complexes.

---

# 2. Objectif central

L’objectif central de ZORA ARC est de transformer une tâche incertaine en un objet de travail clair.

Il permet de répondre à cinq problèmes fréquents :

| Problème              | Réponse apportée par ZORA ARC             |
| --------------------- | ----------------------------------------- |
| Demande floue         | Cadrage par TASKCARD                      |
| Tâche complexe        | Qualification par routeur                 |
| Risque d’erreur       | Gates d’audit                             |
| Manque de preuves     | Module registre de preuves                |
| Livrable inutilisable | Plan opératoire et contrôle d’opérabilité |

La formule simple serait :

> **ZORA ARC transforme le flou en structure, la structure en analyse, l’analyse en livrable, et le livrable en décision exploitable.**

---

# 3. Problème de fond que ZORA ARC cherche à résoudre

Dans les tâches complexes, le danger principal n’est pas seulement de se tromper.
Le danger est de produire une réponse qui **semble solide**, mais qui ne l’est pas.

ZORA ARC lutte donc contre :

* le faux robuste ;
* les réponses trop rapides ;
* les synthèses sans preuves ;
* les plans non opératoires ;
* les recommandations non vérifiables ;
* les erreurs de périmètre ;
* les confusions entre information, preuve, hypothèse et décision ;
* les livrables trop beaux mais inutilisables.

C’est pour cela que ZORA ARC impose une logique progressive :

```text
Cadrer avant d’analyser.
Qualifier avant d’activer.
Documenter avant d’affirmer.
Auditer avant de livrer.
Corriger avant de conclure.

┌──────────────────────────────────────────────────────────────────────────────┐
│                         ZORA_ARC V9.1 — ARC-MEM                             │
│        RAG spatial, vectoriel, probatoire et auditable sous PostgreSQL        │
└──────────────────────────────────────────────────────────────────────────────┘

        1. ENTRÉE STRUCTURÉE
        ┌────────────────────┐
        │ Question utilisateur│
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ TASKCARD + Score   │
        └─────────┬──────────┘
                  ↓
        ┌────────────────────┐
        │ Routeur ARC : SR   │
        └─────────┬──────────┘
                  ↓

        2. MODULES ARC
        ┌────────────────────────────────────────────────────┐
        │ M1 PARA │ M2 Résumé │ M3 Complexité │ M4 Preuves   │
        │ M5 Réglementaire │ M6 Scientifique │ M7 Spatial   │
        │ M8 RAG documentaire                              │
        └──────────────────────────┬─────────────────────────┘
                                   ↓

        3. BASE CENTRALE POSTGRESQL
        ┌────────────────────────────────────────────────────┐
        │ PostgreSQL                                         │
        │ ├─ PostGIS    : lieux, distances, territoires      │
        │ ├─ pgvector   : embeddings, similarité             │
        │ ├─ mem_types / mem_entities                        │
        │ ├─ mem_schemas / mem_facts                         │
        │ ├─ chunks / mem_fact_chunks                        │
        │ ├─ mem_bridges                                    │
        │ ├─ taskcards                                      │
        │ └─ arc_audit_log                                  │
        └──────────────────────────┬─────────────────────────┘
                                   ↓

        4. MÉMOIRE ARC-MEM
        ┌────────────────────────────────────────────────────┐
        │ L1 Ontologie : types, schémas, règles              │
        │ L2 Faits     : triplets, relations, validités      │
        │ L3 Passages  : textes sources, preuves             │
        │ L4 Geo-RAG   : position, échelle, temps, contexte  │
        └──────────────────────────┬─────────────────────────┘
                                   ↓

        5. RETRIEVAL + AUDIT
        ┌────────────────────────────────────────────────────┐
        │ Python externe : Personalized PageRank             │
        │ Gates : G0 Format, G1 Preuves, G2 Cohérence,       │
        │         G3 Risques, G4 Réplicabilité               │
        │ PATCH si erreur                                    │
        └──────────────────────────┬─────────────────────────┘
                                   ↓
        ┌────────────────────────────────────────────────────┐
        │ Réponse finale : sourcée, auditée, corrigée,       │
        │ exploitable par Stéphane, Zora ou Codex            │
        └──────────────────────────────────────────────────
