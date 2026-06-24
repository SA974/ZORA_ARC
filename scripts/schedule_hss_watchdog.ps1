# Crée une tâche planifiée Windows pour la surveillance continue du dossier HSS
# Exécution : chaque 2 heures, ou au démarrage + chaque 8 heures
# Logs : logs/hss_ingest.log et logs/hss_ingest_status.json

$TaskName = "ARC-MEM HSS Watchdog"
$TaskPath = "\ARC-MEM\"
$BridgeRoot = "C:\Users\Stephane_Arnoux\arc-mem-bridge"
$ScriptPath = Join-Path $BridgeRoot "scripts\ingest_hss_folder.py"
$VenvPython = Join-Path $BridgeRoot ".venv\Scripts\python.exe"
$LogDir = Join-Path $BridgeRoot "logs"

# Créer le dossier logs s'il n'existe pas
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

Write-Host "Création de la tâche planifiée: $TaskName"

# Action : lancer le script Python
$Action = New-ScheduledTaskAction `
    -Execute $VenvPython `
    -Argument "-u `"$ScriptPath`"" `
    -WorkingDirectory $BridgeRoot

# Déclencheur 1 : au démarrage du système
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup

# Déclencheur 2 : toutes les 2 heures (120 minutes)
$TriggerInterval = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Days 999)

# Principal : au démarrage
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest

# Paramètres avancés
$Settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Créer ou remplacer la tâche
if (Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Tâche existante : mise à jour..."
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskPath $TaskPath `
    -TaskName $TaskName `
    -Action $Action `
    -Principal $Principal `
    -Settings $Settings `
    -Trigger @($TriggerStartup, $TriggerInterval) `
    -Description "Surveillance HSS: ingère les PDFs du dossier F:\Dropbox\ENTREPRISES\STEPHANE_ARNOUX\SERVICE_SI_RD\RECHERCHE\HSS toutes les 2h" | Out-Null

Write-Host "✓ Tâche créée/mise à jour: $TaskName"
Write-Host "  Déclencheurs :"
Write-Host "    1. Au démarrage du système"
Write-Host "    2. Toutes les 2 heures"
Write-Host "  Logs : $LogDir\hss_ingest.log"
Write-Host "  Statut : $LogDir\hss_ingest_status.json"
