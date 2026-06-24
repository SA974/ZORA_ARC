# Dashboard de Monitoring ZORA_ARC

Dashboard moderne en temps réel pour superviser l'état global du système d'ingestion, des scripts et des tâches.

## Accès rapide

Lancer le serveur FastAPI :
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8791 --reload
```

Ouvrir le dashboard :
```
http://localhost:8791/monitoring/
```

## Architecture

### Tables PostgreSQL (`public.monitoring_*`)
- **`monitoring_jobs`** — scripts planifiés, importations batch, tâches
  - Champs : `name`, `status` (idle/running/success/error), `last_started_at`, `last_completed_at`, `last_duration_seconds`, `last_error`, `items_processed`, `items_failed`
- **`monitoring_events`** — log structuré des événements (démarrage, complétion, erreur, skipped)
- **`monitoring_ingestion_stats`** — compteurs agrégés (fichiers, chunks, faits, enregistrements BD)

### Service (`app/services/monitoring_service.py`)
API Python pour intégrer monitoring dans les scripts :
```python
from app.services.monitoring_service import MonitoringService

svc = MonitoringService()

# Enregistrer un job
job_id = svc.register_job("mon_script", "Description", "path/to/script.py")

# Marquer le démarrage
svc.job_start(job_id)

# Enregistrer des événements
svc.log_event(job_id, "info", "Traitement en cours...")

# Succès
svc.job_complete(job_id, items_processed=100, items_failed=2)

# Ou erreur
svc.job_error(job_id, "Message d'erreur")

# Mettre à jour les stats d'ingestion
svc.update_ingestion_stats(
    domain="global",
    files_detected=1000,
    files_ingested=500,
    chunks_created=50000,
    facts_extracted=500,
)

# Snapshot complet
snapshot = svc.get_dashboard_snapshot()
```

### Routes FastAPI (`app/routes/monitoring.py`)
- `GET /monitoring/` — Page HTML du dashboard
- `GET /monitoring/api/dashboard` — Snapshot complet (JSON)
- `GET /monitoring/api/jobs` — Liste des jobs
- `GET /monitoring/api/events` — Événements récents (48h)
- `GET /monitoring/api/stats/{domain}` — Stats d'ingestion par domaine

## Affichage du Dashboard

### Synthèse globale (haut)
```
┌─────────────────────┬──────────────────┬──────────────┬─────────┐
│ Total à ingérer     │ Ingérés          │ Restants     │ Erreurs │
│ 100 fichiers        │ 42               │ 58           │ 1       │
└─────────────────────┴──────────────────┴──────────────┴─────────┘
┌─────────────────────┬──────────────────┬──────────────┐
│ Scripts actifs      │ Scripts en erreur │ Chunks       │
│ 1                   │ 0                 │ 5282         │
└─────────────────────┴──────────────────┴──────────────┘
```

### Progression globale
```
📈 Progression globale
████████████████░░░░░░░░░░░░░░ 42.0% (42 / 100)
```

### État des scripts (table)
```
┌─────────────────────────┬─────────────┬──────────┬──────────┬─────────┐
│ Nom du script           │ Statut      │ Durée    │ Traités  │ Erreurs │
├─────────────────────────┼─────────────┼──────────┼──────────┼─────────┤
│ ingest_hss_folder       │ ✓ success   │ 2.5s     │ 12       │ 0       │
│ backfill_hmem           │ ✗ error     │ 30.0s    │ 42       │ 1       │
└─────────────────────────┴─────────────┴──────────┴──────────┴─────────┘
```

### Journal des événements (dernières 24h)
```
┌───────────────────────┬─────────────┬──────────────────┬─────────────────────┐
│ Timestamp             │ Type        │ Job              │ Message             │
├───────────────────────┼─────────────┼──────────────────┼─────────────────────┤
│ 2026-06-24 22:00:10   │ completed   │ ingest_hss_fold… │ Job complété: 12 tr… │
│ 2026-06-24 21:59:45   │ started     │ backfill_hmem    │ Job démarré          │
│ 2026-06-24 21:45:37   │ info        │ ingest_hss_fold… │ Scan du dossier HSS  │
└───────────────────────┴─────────────┴──────────────────┴─────────────────────┘
```

## Code couleurs

- 🟢 **Vert** (`#10b981`) — Succès, actif
- 🔴 **Rouge** (`#ef4444`) — Erreur, échoué
- 🔵 **Bleu** (`#3b82f6`) — En cours, pulsant
- ⚪ **Gris** (`#94a3b8`) — Inactif, en attente

## Intégration dans les scripts

Pour intégrer le monitoring dans `ingest_hss_folder.py` :

```python
from app.services.monitoring_service import MonitoringService

svc = MonitoringService()
job_id = svc.register_job("ingest_hss_folder", "Ingestion du dossier HSS", __file__)

try:
    svc.job_start(job_id)
    
    # ... votre logique d'ingestion
    ingested = 12
    failed = 0
    
    svc.job_complete(job_id, items_processed=ingested, items_failed=failed)
    svc.update_ingestion_stats(domain="hss_homo_sapiens_sapiens", files_ingested=ingested)
except Exception as e:
    svc.job_error(job_id, str(e))
    raise
```

## Refresh automatique

Le dashboard se refresh automatiquement tous les **5 secondes** via polling AJAX.

Éditer `REFRESH_INTERVAL` dans `app/routes/monitoring.py` pour changer la fréquence.

## Limitations et notes

- Dashboard robuste : ne plante jamais si une donnée est absente (affiche "N/A")
- État des jobs limité à 50 entrées (évite les surcharges)
- Événements limités à 24h de rétention (événement au-delà supprimé)
- Pas de persistance historique à long terme (statistiques ponctuelles uniquement)
- Conçu pour fonctionner indépendamment des scripts — s'ils crash, le dashboard continue

## Exemple : intégrer un nouveau job

1. **Enregistrer le job au démarrage du script :**
   ```python
   svc = MonitoringService()
   job_id = svc.register_job("mon_script", "Description", __file__)
   ```

2. **Enregistrer les étapes :**
   ```python
   svc.job_start(job_id)
   svc.log_event(job_id, "info", "Étape 1 en cours...")
   svc.log_event(job_id, "info", "Étape 2 en cours...")
   ```

3. **Finaliser :**
   ```python
   svc.job_complete(job_id, items_processed=N, items_failed=M)
   ```

4. **Mettre à jour les stats :**
   ```python
   svc.update_ingestion_stats(domain="...", files_ingested=N, chunks_created=M)
   ```

---

**Dernier update** : 2026-06-24  
**Version** : v0.1.0  
**Status** : Production-ready
