# Processus d'ingestion HSS (Homo Sapiens Sapiens)

## Vue d'ensemble

Le système ZORA_ARC / arc-mem-bridge maintient une **surveillance continue** du dossier HSS pour ingérer automatiquement les PDFs scientifiques dans la base de données centrale.

### Dossier source
```
F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS
```

### Statut actuel
- **12 PDFs** ingérés et catalogués
- **5 282 chunks** extraits
- **Faits extraits** : 0 (PDFs sans texte directement extractible)
- **Nœuds H-MEM** : 0 (en attente d'extraction multi-agents sur texte OCR/enrichi)

## Composants

### 1. Script d'ingestion batch (`scripts/ingest_hss_folder.py`)

**Fonction** : Ingère tous les PDFs du dossier HSS dans arc-mem-bridge.

**Mode d'exécution** :
```bash
python scripts/ingest_hss_folder.py
```

**Fonctionnalités** :
- **Resumable** : saute les PDFs déjà traités (hash SHA256 en `metadata.pdf_sha256`)
- **Multi-agent** : applique ExtractionAgent → DetectionAgent → ResolutionAgent
- **Domaine** : tous les PDFs sont catalogués sous `domain="hss_homo_sapiens_sapiens"`
- **Logs** : 
  - `logs/hss_ingest.log` — détail complet par PDF
  - `logs/hss_ingest_status.json` — statut JSON structuré (timestamp, résumé, résultats)

**Exemple de sortie** :
```
Dossier HSS: 12 PDFs trouvés, 0 déjà ingérés
INGEST Acceptabil.pdf (sha=e6ffa807...)
  ✓ Acceptabil.pdf -> doc_id=971d3dab-f482-4a60-a0ba-8ba9ee81b403, faits=0
...
Résumé: 12 success, 0 skipped, 0 errors
```

### 2. Tâche planifiée Windows (`scripts/schedule_hss_watchdog.ps1`)

**Fonction** : Lance `ingest_hss_folder.py` automatiquement selon un calendrier.

**Installation** (doit être exécuté en tant qu'administrateur) :
```powershell
powershell -ExecutionPolicy Bypass -File scripts\schedule_hss_watchdog.ps1
```

**Déclencheurs** :
- 🔄 **Au démarrage du système** — synchronisation immédiate
- ⏰ **Toutes les 2 heures** — surveillance continue

**Vérifier la tâche** :
```powershell
schtasks /query /tn "\ARC-MEM\ARC-MEM HSS Watchdog" /v
```

**Logs** :
- Sorties : `logs/hss_ingest.log`
- Dernière exécution : `logs/hss_ingest_status.json`

### 3. Dashboard de statut (`scripts/hss_status_dashboard.py`)

**Fonction** : Affiche un tableau de bord des dernières exécutions et des statistiques DB.

**Exécution** :
```bash
python scripts/hss_status_dashboard.py
```

**Affiche** :
- Dernière exécution (timestamp)
- Résumé : succès / ignorés / erreurs
- Détails erreurs (si applicable)
- Stats DB : nombre de documents, chunks, faits, nœuds H-MEM HSS
- Calendrier prochaines exécutions

**Exemple** :
```
=== TABLEAU DE BORD INGESTION HSS ===
Dernière exécution : 2026-06-24T21:45:39.281676
Résumé : 12 PDFs
  ✓ 12 succès
  ⊘ 0 ignorés (déjà traités)
  ✗ 0 erreurs

=== STATISTIQUES DE BASE DE DONNÉES ===
Documents HSS : 12
Chunks : 5282
Faits extraits : 0
Nœuds H-MEM : 0
```

## Workflow complet

```
1. Ajouter un PDF dans F:\...\HSS\
        ↓
2. Tâche planifiée déclenche (au startup ou toutes 2h)
        ↓
3. ingest_hss_folder.py
   - Calcule SHA256 du PDF
   - Vérifie s'il est déjà traité (resumable)
   - Ingère via ingest_pdf_file()
   - Applique extraction multi-agents si possible
   ↓
4. Stockage dans arc-mem-bridge
   - zora.documents (catalogage)
   - zora.chunks (5282 chunks pour 12 PDFs)
   - memgraph.mem_facts (0 pour l'instant, faits si OCR/texte extractible)
   - hmem.memory_nodes (0 pour l'instant, indexés après extraction)
   ↓
5. Statut JSON écrit
   - logs/hss_ingest_status.json
   - Utilisable par monitoring externe
```

## Maintenance

### Ajouter un nouveau PDF
1. Copier le PDF dans `F:\Dropbox\...\HSS\`
2. La tâche planifiée le détectera au prochain cycle (max 2h)
3. Vérifier le statut : `python scripts/hss_status_dashboard.py`

### Forcer une exécution immédiate
```bash
python scripts/ingest_hss_folder.py
```

### Réinitialiser un PDF (refaire son traitement)
1. Supprimer l'enregistrement de la base :
   ```sql
   delete from zora.documents where metadata->>'source' = 'hss_folder' and title like '%nom_du_pdf%';
   delete from hmem.memory_nodes where target_id in (
       select f.id from memgraph.mem_facts f 
       where f.source_document_id in (...)
   );
   ```
2. Relancer `python scripts/ingest_hss_folder.py`

### Monitorer les logs
```bash
tail -f logs/hss_ingest.log
```

## Architecture

```
arc-mem-bridge/
├── scripts/
│   ├── ingest_hss_folder.py          ← Ingestion batch (resumable)
│   ├── schedule_hss_watchdog.ps1     ← Tâche Windows (déclenchée)
│   └── hss_status_dashboard.py       ← Dashboard statut
├── logs/
│   ├── hss_ingest.log                ← Logs détaillés
│   └── hss_ingest_status.json        ← Statut structuré (JSON)
└── HSS_PROCESS_README.md             ← Ce fichier
```

## Intégration avec Hermes

Si configuré, la tâche planifiée s'intègre avec le profil Hermes `ingest-man` ou `star-arc-mem` pour synchroniser la mémoire du système agent avec les documents HSS.

---

**État actuel** : ✅ Opérationnel  
**Dernière exécution** : 2026-06-24T21:45:39  
**Prochaine exécution** : Automatique (toutes 2h + au démarrage)
