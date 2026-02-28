# Cierre FASE 2B - Lee credenciales de env: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
$ErrorActionPreference = 'Continue'
$RepoRoot = (Get-Location).Path
if (-not (Test-Path "backend")) { Write-Error "Ejecuta desde la raiz del repo (donde esta backend/)"; exit 1 }
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null
$logFile = "$RepoRoot\logs\phase2b_closeout_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"
"=== Phase 2B closeout $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $logFile

if (-not $env:DB_HOST) { $env:DB_HOST = 'localhost' }
if (-not $env:DB_PORT) { $env:DB_PORT = '5432' }
if (-not $env:DB_NAME) { $env:DB_NAME = 'yego_integral' }
$encoded = [uri]::EscapeDataString($env:DB_PASSWORD)
$env:DATABASE_URL = "postgresql://$($env:DB_USER):$encoded@$($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
$env:PGPASSWORD = $env:DB_PASSWORD

Push-Location "$RepoRoot\backend"

"`n--- alembic upgrade head ---" | Tee-Object -FilePath $logFile -Append
alembic upgrade head 2>&1 | Tee-Object -FilePath $logFile -Append
$alembicUpgradeOk = ($LASTEXITCODE -eq 0)

"`n--- alembic current ---" | Tee-Object -FilePath $logFile -Append
$alembicCurrent = alembic current 2>&1
$alembicCurrent | Tee-Object -FilePath $logFile -Append
"`n--- alembic heads ---" | Tee-Object -FilePath $logFile -Append
$alembicHeads = alembic heads 2>&1
$alembicHeads | Tee-Object -FilePath $logFile -Append

"`n--- Verificacion MV ops.mv_real_trips_weekly ---" | Tee-Object -FilePath $logFile -Append
$mvExists = $false
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCmd) {
  $mvQuery = "SELECT COALESCE(to_regclass('ops.mv_real_trips_weekly')::text, '') AS r;"
  $mvResult = (psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -t -A -c $mvQuery 2>&1) -join ' '
  $mvResult | Tee-Object -FilePath $logFile -Append | Out-Null
  if ($mvResult -match 'ops\.mv_real_trips_weekly') { $mvExists = $true }
} else {
  $pyOut = python scripts/check_mv_weekly_exists.py 2>&1 | Tee-Object -FilePath $logFile -Append
  if ($pyOut -match 'yes') { $mvExists = $true }
}
if ($mvExists) { "MV existe: ops.mv_real_trips_weekly" | Tee-Object -FilePath $logFile -Append } else { "MV NO encontrada" | Tee-Object -FilePath $logFile -Append }

"`n--- refresh_mv_real_weekly.py --timeout 7200 ---" | Tee-Object -FilePath $logFile -Append
python scripts/refresh_mv_real_weekly.py --timeout 7200 2>&1 | Tee-Object -FilePath $logFile -Append
$refreshOk = ($LASTEXITCODE -eq 0)

"`n--- validate_phase2b_weekly.py ---" | Tee-Object -FilePath $logFile -Append
python scripts/validate_phase2b_weekly.py 2>&1 | Tee-Object -FilePath $logFile -Append
$validateOk = ($LASTEXITCODE -eq 0)

"`n--- (Opcional) phase2b_weekly_checks.sql ---" | Tee-Object -FilePath $logFile -Append
if (Get-Command psql -ErrorAction SilentlyContinue) {
  psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -f sql/phase2b_weekly_checks.sql 2>&1 | Tee-Object -FilePath $logFile -Append
} else {
  "psql no instalado; omitiendo checks SQL opcionales" | Tee-Object -FilePath $logFile -Append
}

Pop-Location
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

$headMatch = [bool]($alembicCurrent -match '053_real_lob_drill_pro')
$closed = $alembicUpgradeOk -and $headMatch -and $mvExists -and $refreshOk -and $validateOk
"`n=== RESUMEN ===" | Tee-Object -FilePath $logFile -Append
"alembic upgrade OK: $alembicUpgradeOk" | Tee-Object -FilePath $logFile -Append
"alembic current == head (053): $headMatch" | Tee-Object -FilePath $logFile -Append
"MV semanal existe: $mvExists" | Tee-Object -FilePath $logFile -Append
"Refresh OK: $refreshOk" | Tee-Object -FilePath $logFile -Append
"Validate OK: $validateOk" | Tee-Object -FilePath $logFile -Append
"FASE 2B CERRADA: $(if ($closed) { 'SI' } else { 'NO' })" | Tee-Object -FilePath $logFile -Append
Write-Host "`nLog guardado en: $logFile"
Write-Host "alembic current == head: $headMatch | MV existe: $mvExists | Refresh: $refreshOk | Validate: $validateOk"
Write-Host "FASE 2B CERRADA: $(if ($closed) { 'SI' } else { 'NO' })"
