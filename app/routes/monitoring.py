"""Routes FastAPI pour le dashboard de monitoring."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.services.monitoring_service import MonitoringService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
monitoring_svc = MonitoringService()


@router.get("/api/dashboard", tags=["api"])
async def get_dashboard_snapshot() -> dict:
    """Snapshot complet du dashboard."""
    try:
        return monitoring_svc.get_dashboard_snapshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur dashboard: {str(e)}")


@router.get("/api/jobs", tags=["api"])
async def get_jobs() -> dict:
    """Liste des jobs."""
    try:
        jobs = monitoring_svc.get_jobs_summary()
        return {"jobs": jobs, "count": len(jobs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/events", tags=["api"])
async def get_events(limit: int = 50) -> dict:
    """Événements récents."""
    try:
        events = monitoring_svc.get_recent_events(limit=limit)
        return {"events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stats/{domain}", tags=["api"])
async def get_stats(domain: str = "global") -> dict:
    """Stats d'ingestion."""
    try:
        return monitoring_svc.get_ingestion_stats(domain)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    """Page HTML du dashboard."""
    return HTMLResponse(content=DASHBOARD_HTML)


# HTML du dashboard (intégré pour simplicité)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZORA_ARC Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            padding: 1.5rem;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            margin-bottom: 2rem;
        }
        .header h1 {
            font-size: 2rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 0.5rem;
        }
        .header p {
            color: #94a3b8;
            font-size: 0.95rem;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.5rem;
            transition: all 0.2s ease;
        }
        .stat-card:hover {
            border-color: #475569;
            background: #334155;
        }
        .stat-label {
            color: #94a3b8;
            font-size: 0.85rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-bottom: 0.5rem;
        }
        .stat-detail {
            font-size: 0.8rem;
            color: #64748b;
        }
        .progress-bar {
            width: 100%;
            height: 0.5rem;
            background: #334155;
            border-radius: 0.25rem;
            overflow: hidden;
            margin-top: 0.75rem;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #10b981, #06b6d4);
            transition: width 0.3s ease;
        }
        .section {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .section-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 1rem;
            padding-bottom: 0.75rem;
            border-bottom: 1px solid #334155;
        }
        .status-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 0.5rem;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .status-success { background: rgba(16, 185, 129, 0.2); color: #10b981; }
        .status-running { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .status-error { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .status-idle { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }
        .dot {
            display: inline-block;
            width: 0.5rem;
            height: 0.5rem;
            border-radius: 50%;
            margin-right: 0.5rem;
            vertical-align: middle;
        }
        .dot-success { background: #10b981; }
        .dot-error { background: #ef4444; }
        .dot-running { background: #3b82f6; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }
        .table th {
            background: #334155;
            padding: 0.75rem;
            text-align: left;
            font-weight: 600;
            color: #f1f5f9;
            border-bottom: 2px solid #475569;
        }
        .table td {
            padding: 0.75rem;
            border-bottom: 1px solid #334155;
            color: #cbd5e1;
        }
        .table tr:hover { background: #334155; }
        .event-type {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        .event-started { background: #3b82f6; color: white; }
        .event-completed { background: #10b981; color: white; }
        .event-error { background: #ef4444; color: white; }
        .event-info { background: #8b5cf6; color: white; }
        .event-success { background: #06b6d4; color: white; }
        .refresh-info {
            text-align: right;
            color: #64748b;
            font-size: 0.85rem;
            margin-top: 1rem;
        }
        .no-data {
            text-align: center;
            color: #64748b;
            padding: 2rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 ZORA_ARC Dashboard</h1>
            <p>Supervision en temps réel du système d'ingestion</p>
        </div>

        <!-- Synthèse globale -->
        <div class="grid">
            <div class="stat-card">
                <div class="stat-label">📊 Total à ingérer</div>
                <div class="stat-value" id="total-files">-</div>
                <div class="stat-detail">fichiers détectés</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">✅ Ingérés</div>
                <div class="stat-value" id="ingested-files">-</div>
                <div class="stat-detail">complétés avec succès</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⏳ Restants</div>
                <div class="stat-value" id="remaining-files">-</div>
                <div class="stat-detail">en attente</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">❌ Erreurs</div>
                <div class="stat-value" id="failed-files">-</div>
                <div class="stat-detail">en échec</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">⚙️ Scripts actifs</div>
                <div class="stat-value" id="running-jobs">-</div>
                <div class="stat-detail">jobs en cours</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔴 Scripts en erreur</div>
                <div class="stat-value" id="error-jobs">-</div>
                <div class="stat-detail">jobs échoués</div>
            </div>
        </div>

        <!-- Progression globale -->
        <div class="section">
            <div class="stat-label">📈 Progression globale</div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>
            <div style="margin-top: 0.75rem; color: #94a3b8; font-size: 0.9rem;">
                <span id="progress-text">0% (0 / 0)</span>
            </div>
        </div>

        <!-- Section Ingestion détaillée -->
        <div class="section">
            <div class="section-title">📥 Statistiques d'ingestion</div>
            <div class="grid">
                <div>
                    <div class="stat-label">Chunks créés</div>
                    <div style="font-size: 1.5rem; color: #f1f5f9; margin-top: 0.5rem;" id="chunks">-</div>
                </div>
                <div>
                    <div class="stat-label">Faits extraits</div>
                    <div style="font-size: 1.5rem; color: #f1f5f9; margin-top: 0.5rem;" id="facts">-</div>
                </div>
                <div>
                    <div class="stat-label">Enregistrements BD</div>
                    <div style="font-size: 1.5rem; color: #f1f5f9; margin-top: 0.5rem;" id="db-records">-</div>
                </div>
            </div>
        </div>

        <!-- Section Scripts -->
        <div class="section">
            <div class="section-title">⚙️ État des scripts</div>
            <table class="table" id="jobs-table">
                <thead>
                    <tr>
                        <th style="width: 40%;">Nom du script</th>
                        <th style="width: 15%;">Statut</th>
                        <th style="width: 15%;">Durée</th>
                        <th style="width: 15%;">Traités</th>
                        <th style="width: 15%;">Erreurs</th>
                    </tr>
                </thead>
                <tbody id="jobs-tbody">
                    <tr><td colspan="5" class="no-data">Chargement...</td></tr>
                </tbody>
            </table>
        </div>

        <!-- Journal d'événements -->
        <div class="section">
            <div class="section-title">📋 Journal des événements (dernières 24h)</div>
            <table class="table" id="events-table">
                <thead>
                    <tr>
                        <th style="width: 20%;">Timestamp</th>
                        <th style="width: 15%;">Type</th>
                        <th style="width: 30%;">Job</th>
                        <th style="width: 35%;">Message</th>
                    </tr>
                </thead>
                <tbody id="events-tbody">
                    <tr><td colspan="4" class="no-data">Chargement...</td></tr>
                </tbody>
            </table>
            <div class="refresh-info" id="refresh-info">Actualisation en cours...</div>
        </div>
    </div>

    <script>
        const API_BASE = '/monitoring/api';
        const REFRESH_INTERVAL = 5000; // 5 secondes

        async function updateDashboard() {
            try {
                const response = await fetch(`${API_BASE}/dashboard`);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();

                updateStats(data);
                updateJobs(data.jobs);
                updateEvents(data.events);
                updateRefreshTime(data.timestamp);
            } catch (error) {
                console.error('Erreur dashboard:', error);
                document.getElementById('refresh-info').textContent = `Erreur: ${error.message}`;
            }
        }

        function updateStats(data) {
            const ing = data.ingestion || {};
            document.getElementById('total-files').textContent = ing.total_files || '0';
            document.getElementById('ingested-files').textContent = ing.ingested || '0';
            document.getElementById('remaining-files').textContent = ing.remaining || '0';
            document.getElementById('failed-files').textContent = ing.failed || '0';
            document.getElementById('running-jobs').textContent = data.jobs.running || '0';
            document.getElementById('error-jobs').textContent = data.jobs.error || '0';

            const pct = ing.progress_pct || 0;
            document.getElementById('progress-fill').style.width = pct + '%';
            document.getElementById('progress-text').textContent = `${pct}% (${ing.ingested || 0} / ${ing.total_files || 0})`;

            document.getElementById('chunks').textContent = (ing.chunks_created || 0).toLocaleString();
            document.getElementById('facts').textContent = (ing.facts_extracted || 0).toLocaleString();
            document.getElementById('db-records').textContent = (ing.db_records || 0).toLocaleString();
        }

        function updateJobs(jobs) {
            const tbody = document.getElementById('jobs-tbody');
            if (!jobs || !jobs.list || jobs.list.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="no-data">Aucun job enregistré</td></tr>';
                return;
            }

            const rows = jobs.list.map(job => {
                const statusClass = `status-${job.status || 'idle'}`;
                const duration = job.last_duration_seconds ? `${job.last_duration_seconds.toFixed(1)}s` : '-';
                const errorMsg = job.last_error ? `<div style="font-size: 0.75rem; color: #ef4444; margin-top: 0.25rem;">${job.last_error.substring(0, 50)}</div>` : '';
                return `
                    <tr>
                        <td><strong>${job.name}</strong>${errorMsg}</td>
                        <td><span class="status-badge ${statusClass}">${job.status || 'idle'}</span></td>
                        <td>${duration}</td>
                        <td>${job.items_processed || 0}</td>
                        <td>${job.items_failed || 0}</td>
                    </tr>
                `;
            }).join('');
            tbody.innerHTML = rows;
        }

        function updateEvents(events) {
            const tbody = document.getElementById('events-tbody');
            if (!events || events.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="no-data">Aucun événement</td></tr>';
                return;
            }

            const rows = events.slice(0, 50).map(evt => {
                const ts = new Date(evt.timestamp).toLocaleString('fr-FR');
                const typeClass = `event-${evt.event_type}`;
                return `
                    <tr>
                        <td style="font-size: 0.85rem; color: #94a3b8;">${ts}</td>
                        <td><span class="event-type ${typeClass}">${evt.event_type}</span></td>
                        <td><strong>${evt.job_name || '-'}</strong></td>
                        <td style="font-size: 0.9rem;">${evt.message}</td>
                    </tr>
                `;
            }).join('');
            tbody.innerHTML = rows;
        }

        function updateRefreshTime(timestamp) {
            const ts = new Date(timestamp).toLocaleTimeString('fr-FR');
            document.getElementById('refresh-info').textContent = `✓ Actualisé à ${ts}`;
        }

        // Actualisation initiale et périodique
        updateDashboard();
        setInterval(updateDashboard, REFRESH_INTERVAL);
    </script>
</body>
</html>
"""
