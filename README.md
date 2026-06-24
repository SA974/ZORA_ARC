# ZORA_ARC — ARC-MEM Bridge

Couche d'intégration locale **100 % Ollama** reliant Hermes, Hindsight, MemGraphRAG,
H-MEM et **PostgreSQL/PostGIS/pgvector** pour l'ingestion documentaire (PDF) et la
mémoire RAG / graphe de connaissances.

Architecture cible : `ZORA_ARC V9.2 ARC-MEM-H`.

> ⚠️ **Sécurité.** Aucune clé/secret n'est versionné. Le `.env` réel est gitignoré ;
> seul `.env.example` (sans valeurs sensibles) est publié. Ne committez jamais de clé.

## Principes

- **Ollama** est le provider unique (génération + embeddings). Pas de NVIDIA NIM, pas d'OpenRouter.
- **PostgreSQL/pgvector** est la base centrale ; embeddings en **768 D** (`nomic-embed-text`).
- Écritures importantes **transactionnelles** (atomicité, reprise propre).
- Hindsight = mémoire agentique ; MemGraphRAG = mémoire graphe probatoire ; H-MEM = routage hiérarchique.

## Pile technique

| Domaine | Choix |
|---|---|
| Lecture PDF | PyMuPDF (`fitz`) |
| OCR (optionnel) | PaddleOCR (lazy, `ENABLE_OCR=1`) |
| Embeddings | Ollama `nomic-embed-text` (768 D) |
| LLM | Ollama `qwen:14b` |
| Base | PostgreSQL 18 + PostGIS + pgvector + pg_trgm + pgcrypto |
| Accès DB | psycopg 3 |
| API | FastAPI + Uvicorn |
| Config | pydantic-settings |
| Tests | pytest |

## Prérequis

- Python ≥ 3.11
- PostgreSQL 16+ avec extensions `vector`, `postgis`, `pg_trgm`, `pgcrypto`
- [Ollama](https://ollama.com) installé et démarré

## Installation

```bash
# 1. Environnement virtuel
python -m venv .venv
# Windows : .venv\Scripts\Activate.ps1   |   Linux/macOS : source .venv/bin/activate

# 2. Dépendances
pip install -r requirements.txt

# 3. Configuration
cp .env.example .env      # puis éditer .env

# 4. Modèles Ollama
ollama pull nomic-embed-text     # embeddings 768 D
ollama pull qwen:14b             # génération / extraction
```

## Base de données

```bash
# Migrations versionnées (idempotentes, transactionnelles)
python scripts/apply_migrations.py --dry-run     # aperçu
python scripts/apply_migrations.py               # applique les migrations en attente
# Sur une base DÉJÀ migrée, adopter le registre sans réexécuter :
python scripts/apply_migrations.py --baseline
```

Schéma : `zora` (documents, chunks, evidence…), `memgraph` (entités, faits, passages,
conflits, couche temporelle), `hmem` (mémoire hiérarchique).

## Healthcheck

```bash
python scripts/check_postgres.py        # connexion + extensions
# /health (API) renvoie postgres + ollama + hindsight
```

## Ingestion PDF

```bash
# Dossier récursif -> zora (embeddings 768 D, transactionnel, dédup par hash)
python scripts/ingest_folder.py "/chemin/vers/pdfs" --report ingestion.json
python scripts/ingest_folder.py "/chemin/vers/pdfs" --dry-run --limit 5
```

Pipeline : scan → extraction texte → nettoyage → chunking → `content_chars` /
`content_tokens_estimated` → embeddings → stockage pgvector. Un **preflight** vérifie
qu'Ollama répond et renvoie la bonne dimension *avant* de traiter le lot.

## API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8791
# GET /health  •  POST /ingest/pdf  •  POST /ingest/folder  •  POST /retrieve  ...
```

## Tests & validation

```bash
pytest app/tests -q                       # tests unitaires/intégration
python scripts/validate_lots_0_2.py       # validation Ollama / PostgreSQL / PDF
python scripts/validate_lot3.py           # validation robustesse (preflight, health)
```

## Définition de `content_length`

Volontairement **deux champs** distincts (colonnes générées dans `zora.chunks`) :

- `content_chars` — nombre de **caractères** Unicode ;
- `content_tokens_estimated` — **tokens** estimés (≈ `caractères / 4`).

## Licence

À définir par le propriétaire du dépôt.
