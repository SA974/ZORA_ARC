# 🚀 Lancer le Dashboard ZORA_ARC

## Démarrage rapide

### 1. Terminal 1 : Démarrer le serveur FastAPI
```bash
cd C:\Users\Stephane_Arnoux\arc-mem-bridge
python -m uvicorn app.main:app --host 0.0.0.0 --port 8791 --reload
```

**Sortie attendue :**
```
INFO:     Uvicorn running on http://0.0.0.0:8791
```

### 2. Terminal 2 : Ouvrir le dashboard dans le navigateur
```
http://localhost:8791/monitoring/
```

## 📊 État du dashboard

**Actuellement :**
- ✅ 12/12 PDFs du dossier HSS ingérés (100%)
- 📁 5 282 chunks créés
- 📝 0 faits extraits (PDFs bruts, sans OCR)
- 💾 6 294 enregistrements en base de données

**Vue du dashboard :**
```
┌────────────────────┬──────────────┬──────────┬────────┐
│ 📊 Total: 12       │ ✅ Ingérés:12│ ⏳ Rest:0│ ❌ Err:0│
└────────────────────┴──────────────┴──────────┴────────┘

📈 Progression
████████████████████████████████ 100% (12 / 12)

⚙️ Scripts
├─ ingest_hss_folder ✓ success     2.5s   12 traités   0 err
└─ backfill_hmem     ✗ error      30.0s   42 traités   1 err

📋 Événements
├─ Job complété: 12 traités, 0 erreurs
├─ Scan du dossier F:\Dropbox\...\HSS
└─ Ingestion batch: 12 PDFs trouvés
```

## 🔌 API endpoints

Pour accéder aux données JSON directement :

```bash
# Snapshot complet
curl http://localhost:8791/monitoring/api/dashboard

# Exemple de réponse
{
  "timestamp": "2026-06-24T21:55:51.503223",
  "jobs": {
    "running": 0,
    "error": 1,
    "success": 1,
    "total": 2,
    "list": [...]
  },
  "ingestion": {
    "total_files": 12,
    "ingested": 12,
    "remaining": 0,
    "failed": 0,
    "progress_pct": 100.0,
    "chunks_created": 5282,
    "facts_extracted": 0,
    "db_records": 6294
  },
  "events": [...]
}
```

## 📝 Logs

- **Ingestion HSS** : `logs/hss_ingest.log`
- **Dashboard** : `logs/hss_ingest_status.json`
- **Monitoring** : Tables PostgreSQL `public.monitoring_*`

## 🎯 Prochaines étapes

1. **Ajouter des PDFs** au dossier `F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS`
2. **Tâche planifiée Windows** : Lance l'ingestion automatiquement (au démarrage + toutes 2h)
3. **Extraction LLM** : Si OCR disponible, les faits seront extraits et affichés au dashboard

## 🔧 Configuration

- **Refresh** : 5 secondes (éditable dans `app/routes/monitoring.py`)
- **Port** : 8791 (configurable via la ligne de commande)
- **DB** : PostgreSQL (local, connecté via `app/db.py`)

---

**Status** : ✅ Production-ready  
**Version** : v0.1.0  
**Date** : 2026-06-24
