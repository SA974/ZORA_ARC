# ARC-MEM Bridge — Fonctionnement dans Hermes & problématique temporelle (H-MEM)

> Version : ARC-MEM Bridge v0.1 (post-implémentation embeddings + temporel + extraction MemGraphRAG, 2026-06-16)
> Répond à trois questions : (1) comment ça marche dans Hermes, (2) l'extraction est-elle automatique, (3) c'est quoi le problème temporel de H-MEM.

---

## 1. Comment ça marche dans Hermes ?

Le bridge n'est **pas** un plugin câblé dans Hermes. C'est un **service local**
(`http://127.0.0.1:8791`) + une CLI. Hermes l'utilise **par convention/instruction** :
on met un prompt durable dans Hermes du type « quand une question touche la mémoire
ARC-MEM, appelle `http://127.0.0.1:8791…` ». Donc **c'est Hermes (ou l'utilisateur) qui
appelle** les endpoints — rien ne se déclenche tout seul à chaque message.

Le bridge sépare **deux mémoires qu'il ne faut jamais confondre** :

| Couche | Rôle | Où | Endpoints |
|---|---|---|---|
| **Hindsight** | mémoire **agentique** (préférences, décisions, résumés intersessions) | base `hindsight_hermes` | `/memory/retain` (écrire), `/memory/recall` (lire) |
| **MemGraphRAG** | mémoire **documentaire probatoire** (documents → chunks → passages → faits) | base `rag_arc` | `/ingest/document`, `/facts/*`, `/retrieve` |
| **H-MEM** | **routeur** hiérarchique | — | s'exécute **automatiquement dans `/retrieve`** |
| **ZORA ARC** | gouvernance (taskcard, audit, niveau de preuve) | — | dans `/retrieve` et `/audit` |

Le point d'entrée unifié est **`/retrieve`** : il renvoie un *ContextBundle*
(souvenirs Hindsight + faits MemGraphRAG + passages + citations + route H-MEM + taskcard).
Hermes s'en sert comme **contexte pour rédiger** — `/retrieve` ne produit pas la réponse finale.

```text
Hermes ──HTTP──> ARC-MEM Bridge (8791) ──> Hindsight (mémoire agentique)
                                       ──> MemGraphRAG (preuves documentaires)
                                       ──> H-MEM (routage, auto dans /retrieve)
                                       ──> ZORA ARC (gouvernance, auto dans /retrieve, /audit)
                                       ──> PostgreSQL (rag_arc + hindsight_hermes)
```

**Règle de séparation :** Hindsight se souvient du travail ; MemGraphRAG prouve avec des
documents ; H-MEM route ; ZORA ARC gouverne ; Hermes orchestre via le bridge.

---

## 2. Extrait-il automatiquement la mémoire persistante ? → **Non.**

Piège de vocabulaire à lever :

- La **mémoire persistante agentique** de Hermes, c'est **Hindsight**. Le pipeline
  d'extraction MemGraphRAG **n'y touche pas** et ne la transforme pas en graphe.
- L'**extraction de faits MemGraphRAG** (entités/relations) ne se déclenche que si on la
  demande **explicitement** :
  - `POST /ingest/document` avec `extract: true` (par défaut **false** → on ne fait que
    stocker les chunks + embeddings) ;
  - ou `POST /facts/extract` ;
  - ou la CLI `scripts/extract_facts.py --document-id …`.
- Les 3 documents Sophia ont été extraits parce que la CLI a été **lancée manuellement**.
  Rien ne « capte » en continu les conversations Hermes pour les verser dans le graphe.

### État réel aujourd'hui

| Mécanisme | Statut |
|---|---|
| Embeddings à l'ingestion (`/ingest`) | ✅ **automatique** |
| Routage H-MEM + ZORA dans `/retrieve` | ✅ **automatique** |
| Extraction entités/faits MemGraphRAG (documents) | ✋ **manuel / opt-in** (`extract=true`, `/facts/extract`, CLI `extract_facts.py`) |
| Écriture dans Hindsight (`/memory/retain`) | ✋ **appel explicite** |
| **Sync mémoire persistante Hindsight → graphe** | ✅ **automatique** (tâche planifiée quotidienne) |

### Automatisation Hindsight → graphe (ajoutée le 2026-06-16)

La mémoire persistante agentique (table `hindsight_hermes.facts`) est désormais **synchronisée
automatiquement** dans le graphe MemGraphRAG :

- Service `app/services/hindsight_sync.py` + endpoint `POST /facts/sync-hindsight` + CLI
  `scripts/sync_hindsight.py`.
- **Idempotent** : chaque passage est tagué `hindsight_fact_id` ; les souvenirs déjà
  synchronisés sont sautés (filtre `--min-len` pour ignorer le bruit type « session_du: … »).
- **Tâche Windows quotidienne** « ARC-MEM Hindsight Sync » (03:00, plafond `--limit 200`/run,
  `StartWhenAvailable`, log dans `logs/hindsight_sync.log`). Rattrape le backlog en quelques jours
  puis reste à jour.
- Lancement manuel : `python scripts/sync_hindsight.py --dry-run` (liste) ou sans `--dry-run`
  (exécute).

---

## 3. La « problématique temporelle » de H-MEM

**En une phrase : une mémoire qui ne connaît pas le temps répond avec des choses périmées.**

Une mémoire naïve = vecteurs + recherche par similarité. Elle n'a **aucune notion de temps** :

- un fait d'il y a 18 mois pèse autant qu'un fait d'hier ;
- si on a dit « j'adore le ski » l'an dernier puis « je déteste le ski » récemment, elle
  renvoie **les deux** avec le même poids → contradiction, sans savoir lequel est **vrai
  maintenant** ;
- les vieux faits hors-sujet noient les faits récents pertinents.

H-MEM part d'une analogie avec la mémoire humaine : elle **s'efface** avec le temps (courbe
d'oubli d'Ebbinghaus) et se **renforce ou s'affaiblit selon le feedback** (l'humain change
d'avis). Une bonne mémoire doit donc : laisser **décroître** ce qui n'est pas reconfirmé,
**renforcer** ce qui est validé, **affaiblir** ce qui est contredit, et au moment de chercher,
pondérer par « à quel point ce souvenir est encore **vivant/courant** », pas seulement par
ressemblance de texte.

### Comment notre couche temporelle le résout (exemple concret)

> Fait A : « Zora utilise **OpenRouter** » (valid_from 2025)
> Fait B : « Zora utilise **NVIDIA NIM** » (valid_from 2026)

- **Bi-temporel** : chaque fait porte `valid_from`/`valid_to` (quand c'est vrai dans le monde)
  en plus de `observed_at` (quand on l'a appris) et `created_at` (quand on l'a écrit). On peut
  demander « qu'était-il vrai en 2025 ? » *et* « qu'est-ce qui est vrai maintenant ? ».
- **Décroissance (salience)** : `salience_now = base · exp(−decay_rate · âge)`. Un fait jamais
  reconfirmé **fane** et descend dans le classement.
- **Feedback** : approbation ×1.3 (ravive + remet l'horloge à zéro), réfutation ×0.5 (affaiblit),
  neutre → laisse la courbe d'oubli agir.
- **Conflit temporel + supersession** : B contredit A (même sujet + prédicat, objet différent,
  embeddings proches) → **B supplante A** (`superseded_by`, `valid_to` de A fermé, statut
  `inactive`).
- **Récupération** : `/retrieve` (via la vue `memgraph.v_active_facts`) classe par
  **similarité × salience** et **exclut les faits supplantés/périmés**. Résultat : « quel
  provider utilise Zora ? » → **NVIDIA NIM** (courant), OpenRouter écarté mais toujours
  consultable dans l'historique.

Le « ski » donnerait pareil : « aime le ski » serait supplanté par « déteste le ski », et
l'agent ne ressortirait plus l'ancien goût comme s'il était d'actualité.

> ⚠️ **Honnêteté** : le papier H-MEM (arXiv:2507.22925) **ne donne aucune formule** de
> décroissance/feedback. L'exponentielle et les multiplicateurs (1.3 / 0.5) sont un **choix
> d'ingénierie**, ajustables (voir `app/migrations/006_temporal_and_embeddings.sql` et
> `app/services/temporal_service.py`).

---

## Tableau récapitulatif des objets temporels (table `memgraph.mem_facts`)

| Champ | Sens | Type temporel |
|---|---|---|
| `created_at` | quand la ligne a été écrite | transaction time |
| `observed_at` | quand le fait a été observé/asserté | event time |
| `valid_from` / `valid_to` | intervalle de validité réelle (`valid_to` NULL = encore vrai) | valid time |
| `salience` / `decay_rate` | poids courant + vitesse d'oubli | décroissance |
| `last_accessed_at` / `reinforced_count` | dernier renforcement, nb d'approbations | feedback |
| `superseded_by` | fait plus récent qui le remplace | supersession |

Vue `memgraph.v_active_facts` = faits non supplantés, encore valides, avec `salience_now`
calculée à la volée par `memgraph.fact_salience_now()`.
