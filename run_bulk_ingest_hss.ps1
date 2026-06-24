# Ingestion de masse HSS -> zora (arc-mem-bridge). Detache, resumable (dedup par hash).
$ErrorActionPreference = "Stop"
$proj = "C:\Users\Stephane_Arnoux\arc-mem-bridge"
$py = "$proj\.venv\Scripts\python.exe"
$hss = "F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS"
$envFile = "C:\Users\Stephane_Arnoux\.hermes\profiles\star-arc-mem\.env"

# 1. Charger l'env du profil (provider=ollama, OLLAMA_*, etc.)
Get-Content $envFile | Where-Object { $_ -and !$_.StartsWith("#") } | ForEach-Object {
    $p = $_ -split "=", 2
    if ($p.Length -eq 2) { [Environment]::SetEnvironmentVariable($p[0].Trim(), $p[1].Trim(), "Process") }
}

# 2. Pre-check Ollama (embeddings) : abandon propre si indisponible
try {
    $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 8
    if (-not ($tags.models.name -match "nomic-embed-text")) { throw "modele nomic-embed-text absent" }
} catch {
    Write-Error "Ollama indisponible ou nomic-embed-text absent : $($_.Exception.Message)"
    exit 3
}

# 3. Ingestion complete : pas de limite de pages, gros fichiers admis, rapport JSON
Set-Location $proj
& $py scripts/ingest_folder.py $hss --max-pages 0 --max-file-mb 300 --delay 0 --report "$proj\hss_ingestion_report.json"
Write-Output "INGESTION TERMINEE exit=$LASTEXITCODE"
