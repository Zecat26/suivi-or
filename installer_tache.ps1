# Crée (ou remplace) la tâche planifiée Windows "Suivi Or - collecte quotidienne".
# Déclencheurs :
#   - du lundi au vendredi à 18h00 (rattrapée au prochain démarrage si le PC était éteint)
#   - à chaque ouverture de session Windows (2 minutes après, le temps que le réseau soit prêt)
# Plusieurs collectes le même jour ne créent pas de doublon : le dernier relevé du jour remplace le précédent.
# Usage : clic droit > "Exécuter avec PowerShell", ou :  powershell -ExecutionPolicy Bypass -File installer_tache.ps1

$dossier = Split-Path -Parent $MyInvocation.MyCommand.Path
$python  = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }   # pythonw = sans fenêtre console

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$dossier\suivi_or.py`"" -WorkingDirectory $dossier

$declQuotidien = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 18:00
$declSession   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$declSession.Delay = "PT2M"

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "Suivi Or - collecte quotidienne" -Action $action `
    -Trigger @($declQuotidien, $declSession) -Settings $settings `
    -Description "Relève les cours des pièces d'or (achat-or-et-argent.fr) et de l'once d'or." -Force | Out-Null

Write-Host "Tâche planifiée créée : du lundi au vendredi à 18h00 + à chaque ouverture de session ($pythonw)."
Write-Host "Pour la supprimer : Unregister-ScheduledTask -TaskName 'Suivi Or - collecte quotidienne' -Confirm:`$false"
