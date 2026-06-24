# Relance ingestion HOMO_SAPIENS_SAPIENS (avec rate-limit respect)

**Situation :** ingestion arrêtée à 307/~1500 docs bridge-pdf (quota NVIDIA free endpoint dépassé).
Quota resets généralement **24h après**, soit demain à ~19h30 UTC.

## Attendre le reset (24h)

Les quotas NVIDIA NIM free endpoint se réinitialisent toutes les 24h. Vous verrez :
```
ERROR 429 Too Many Requests
```
tant que le quota n'est pas réinitialisé. Attendez, puis relancez.

## Relance progressive (avec délai respectueux du rate limit)

**Avec `--delay 1.0`** (1 seconde entre appels API) :
```powershell
$py = 'C:\Users\Stephane_Arnoux\arc-mem-bridge\.venv\Scripts\python.exe'
cd C:\Users\Stephane_Arnoux\arc-mem-bridge
& $py scripts/ingest_folder.py `
  'F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HOMO_SAPIENS_SAPIENS' `
  --delay 1.0 `
  --report 'F:\RAG_PIPELINE\logs\ingest_zora_resume_2026-06-18.json'
```

**Estimation :**
- ~1200 docs restants × 2-4 appels API/doc = ~3000-4800 appels API
- À 1 req/sec = 1-2 heures d'exécution

**Variantes de délai :**
- `--delay 0.5` → plus agressif (risque 429 si quota étroit)
- `--delay 1.0` → équilibré (RECOMMANDÉ)
- `--delay 2.0` → très prudent (plus lent mais sûr)

## Monitoring

```powershell
# Lire le rapport en temps réel
Get-Content 'F:\RAG_PIPELINE\logs\ingest_zora_resume_2026-06-18.json' | ConvertFrom-Json
```

## Après relance

```powershell
$psql = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$env:PGCLIENTENCODING='UTF8'
& $psql -h localhost -U postgres -d rag_arc -c "select * from domain_summary order by document_count desc"
```
