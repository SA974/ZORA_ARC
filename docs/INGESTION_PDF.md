# Ingestion PDF unifiée (ARC-MEM Bridge → zora)

Pipeline unique : **PDF → texte assaini → chunks page-aware → embeddings → `rag_arc.zora`**.
Remplace l'ancienne chaîne en deux temps (`F:\RAG_PIPELINE\run_pipeline.py` → `public.*` → migration → `zora.*`).
Une seule base (`rag_arc`), un seul schéma (`zora`), aucun saut de base à base.

## Garanties de robustesse

- **Atomique** : une transaction PostgreSQL par PDF. En cas d'échec → rollback total →
  aucune ligne orpheline, fichier reprenable au prochain passage.
- **Idempotent** : déduplication par `content_hash = SHA256(octets du fichier)` (colonne unique
  `zora.documents.content_hash`). Un document déjà ingéré est *skipped* ; un échec ne laisse rien.
- **Texte assaini** : suppression des `NUL (\x00)`, recollage des césures, normalisation des espaces.
- **Embeddings** : batchés (`EMBEDDING_BATCH_SIZE=64`), dimension vérifiée (1024), relance
  exponentielle (3 tentatives) sur erreur réseau/API.
- **Métadonnées** : par document (`filename, source_path, domain, page_count, file_size_bytes,
  ingested_at, embedding_model`) et par chunk (`page_start, page_end, char_start, char_end,
  token_count, embedding_model`).
- **Garde-fous** : taille fichier (`--max-file-mb`, défaut 100) et pages (`--max-pages`, défaut 1500),
  exclusion des dossiers techniques (`ACROBAT, Talend, _files, ARCHIVES, _ERREURS, VRAC…`).

## Commandes

Python du bridge : `C:\Users\Stephane_Arnoux\arc-mem-bridge\.venv\Scripts\python.exe`.

```powershell
$py = 'C:\Users\Stephane_Arnoux\arc-mem-bridge\.venv\Scripts\python.exe'
cd C:\Users\Stephane_Arnoux\arc-mem-bridge

# Un PDF (dry-run : compte pages/chunks sans écrire)
& $py -m app.cli.arc_mem ingest-pdf "F:\...\fichier.pdf" --domain bibliotheque --dry-run
& $py -m app.cli.arc_mem ingest-pdf "F:\...\fichier.pdf" --domain bibliotheque

# Un dossier (récursif, domaine déduit du chemin), avec rapport JSON
& $py scripts\ingest_folder.py "F:\...\HOMO_SAPIENS_SAPIENS" --report ingestion_zora.json
& $py -m app.cli.arc_mem ingest-folder "F:\...\HOMO_SAPIENS_SAPIENS\ECOLOGIE" --limit 20
```

### Via HTTP (nécessite un redémarrage du bridge pour charger la route)

```powershell
& "$env:USERPROFILE\.hermes\scripts\start_arc_mem_bridge.ps1"   # redémarre uvicorn
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8791/ingest/pdf -ContentType application/json `
  -Body '{"path":"F:\\...\\fichier.pdf","domain":"bibliotheque","dry_run":true}'
```

## Reprise après échec

Aucune action spéciale : relancer la même commande. Les documents complets sont *skipped*
(dédup par hash) ; les fichiers échoués (qui n'ont rien laissé en base) sont retentés.

## Vérification

```powershell
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
& $psql -h localhost -U postgres -d rag_arc -c "select count(*) docs, (select count(*) from zora.chunks) chunks, (select count(*) from zora.chunks where embedding is null) sans_emb from zora.documents;"
& $psql -h localhost -U postgres -d rag_arc -c "select metadata->>'domain' dom, count(*) from zora.documents where metadata->>'source'='bridge-pdf' group by 1 order by 2 desc;"
```
`sans_emb` doit rester `0`. Test unitaire : `& $py -m pytest app/tests/test_pdf_service.py -q`.

## Legacy (gelé, non supprimé)

`F:\RAG_PIPELINE\run_pipeline.py` et `rag_arc.public.*` (8 801 docs) restent en l'état.
Reprise des 869 docs `public.pending` et éventuel `DROP SCHEMA public` = étapes ultérieures à valider.
Comme l'ancienne migration mappait `public.file_hash → zora.content_hash`, ré-ingérer les PDF
source via ce pipeline ne crée pas de doublon des documents déjà présents dans `zora`.
