# Orchestrator: pre-check, run closeout block, extract evidence, decision.
# Requiere: DB_USER, DB_PASSWORD (o DATABASE_URL); opcional DB_HOST, DB_PORT, DB_NAME.
# No imprime contraseñas.

param()

# ----- FASE 0: PRE-CHECK -----
if (-not $env:DATABASE_URL) {
  if (-not $env:DB_USER -or -not $env:DB_PASSWORD) {
    Write-Host "ERROR: Missing required DB environment variables"
    exit 1
  }
  if (-not $env:DB_HOST) { $env:DB_HOST = "localhost" }
  if (-not $env:DB_PORT) { $env:DB_PORT = "5432" }
  if (-not $env:DB_NAME) { $env:DB_NAME = "yego_integral" }
}

$repoRoot = $PSScriptRoot -replace '\\scripts$',''
if (-not (Test-Path "$repoRoot\backend")) {
  Write-Host "ERROR: backend/ not found"
  exit 1
}

Push-Location $repoRoot

# ----- FASE 1: BLOQUE (documentado en docs/PHASE_2B_CLOSEOUT.md) -----
$ErrorActionPreference = 'Continue'
$RepoRoot = (Get-Location).Path
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null
$logFile = "$RepoRoot\logs\phase2b_closeout_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"
"=== Phase 2B closeout $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $logFile

if (-not $env:DATABASE_URL) {
  $encoded = [uri]::EscapeDataString($env:DB_PASSWORD)
  $env:DATABASE_URL = "postgresql://$($env:DB_USER):$encoded@$($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
}
$env:PGPASSWORD = $env:DB_PASSWORD

Push-Location "$RepoRoot\backend"

"`n--- Conexiones activas / max_connections ---" | Tee-Object -FilePath $logFile -Append
try {
  $connOut = python scripts/check_connections.py 2>&1
  $connOut | Tee-Object -FilePath $logFile -Append
  $lines = ($connOut -join "`n") -split "`n" | Where-Object { $_ -match '^\d+$' }
  if ($lines.Count -ge 2) {
    $active = [int]$lines[0]
    $max = [int]$lines[1]
    if ($active -gt ($max - 5)) {
      $warn = "ADVERTENCIA: conexiones activas=$active, max_connections=$max. Riesgo 'too many clients'. Cierra otras apps o espera."
      $warn | Tee-Object -FilePath $logFile -Append
      Write-Host $warn -ForegroundColor Yellow
    }
  }
} catch { "check_connections no disponible" | Tee-Object -FilePath $logFile -Append }

"`n--- alembic upgrade head ---" | Tee-Object -FilePath $logFile -Append
alembic upgrade head 2>&1 | Tee-Object -FilePath $logFile -Append
$alembicOk = ($LASTEXITCODE -eq 0)

"`n--- alembic current ---" | Tee-Object -FilePath $logFile -Append
$alembicCurrent = alembic current 2>&1 | Out-String
$alembicCurrent | Tee-Object -FilePath $logFile -Append
"`n--- alembic heads ---" | Tee-Object -FilePath $logFile -Append
$alembicHeads = alembic heads 2>&1 | Out-String
$alembicHeads | Tee-Object -FilePath $logFile -Append

$expectedHead = '053_real_lob_drill_pro'
$currentMatch = [bool]($alembicCurrent -match $expectedHead)
$headsMatch = [bool]($alembicHeads -match $expectedHead)
$currentEqHead = $currentMatch -and $headsMatch
if (-not $currentEqHead) {
  "FAIL: current no coincide con head esperado ($expectedHead)" | Tee-Object -FilePath $logFile -Append
}

"`n--- Verificacion MV ops.mv_real_trips_weekly ---" | Tee-Object -FilePath $logFile -Append
$mvExists = $false
$mvRows = 0
$mvWeekRange = ""
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCmd) {
  $q1 = "SELECT COALESCE(to_regclass('ops.mv_real_trips_weekly')::text, '') AS r;"
  $r1 = (psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -t -A -c $q1 2>&1) -join ' '
  $r1 | Tee-Object -FilePath $logFile -Append
  if ($r1 -match 'ops\.mv_real_trips_weekly') { $mvExists = $true }
  if ($mvExists) {
    $r2 = (psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -t -A -c "SELECT COUNT(*) FROM ops.mv_real_trips_weekly;" 2>&1) -join ' '
    if ($r2 -match '^\d+$') { $mvRows = [int]$r2 }
    $r3 = (psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -t -A -c "SELECT MIN(week_start)::text, MAX(week_start)::text FROM ops.mv_real_trips_weekly;" 2>&1) -join ' '
    $mvWeekRange = $r3.Trim()
  }
} else {
  $pyOut = python scripts/check_mv_weekly_exists.py 2>&1 | Tee-Object -FilePath $logFile -Append
  if ($pyOut -match 'yes') { $mvExists = $true }
  if ($mvExists) {
    $pyStats = python scripts/check_mv_weekly_stats.py 2>&1 | Tee-Object -FilePath $logFile -Append
    $parts = ($pyStats -split "`t")
    if ($parts.Count -ge 1 -and $parts[0] -match '^\d+$') { $mvRows = [int]$parts[0] }
    if ($parts.Count -ge 3) { $mvWeekRange = "$($parts[1]) $($parts[2])".Trim() }
  }
}
"MV exists: $mvExists | rows: $mvRows | week range: $mvWeekRange" | Tee-Object -FilePath $logFile -Append
$mvRowsGt0 = ($mvRows -gt 0)

"`n--- refresh_mv_real_weekly.py --timeout 7200 ---" | Tee-Object -FilePath $logFile -Append
python scripts/refresh_mv_real_weekly.py --timeout 7200 2>&1 | Tee-Object -FilePath $logFile -Append
$refreshOk = ($LASTEXITCODE -eq 0)

"`n--- validate_phase2b_weekly.py ---" | Tee-Object -FilePath $logFile -Append
python scripts/validate_phase2b_weekly.py 2>&1 | Tee-Object -FilePath $logFile -Append
$validateOk = ($LASTEXITCODE -eq 0)

Pop-Location
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

$allOk = $alembicOk -and $currentEqHead -and $mvExists -and $mvRowsGt0 -and $refreshOk -and $validateOk
$summary = @"
`n=== RESUMEN FINAL ===
Alembic: $(if ($alembicOk) { 'OK' } else { 'FAIL' })
Current==Head: $(if ($currentEqHead) { 'OK' } else { 'FAIL' })
MV exists: $(if ($mvExists) { 'YES' } else { 'NO' })
MV rows > 0: $(if ($mvRowsGt0) { 'YES' } else { 'NO' })
Refresh: $(if ($refreshOk) { 'OK' } else { 'FAIL' })
Validate: $(if ($validateOk) { 'OK' } else { 'FAIL' })
FASE 2B CERRADA: $(if ($allOk) { 'SI' } else { 'NO' })
"@
$summary | Tee-Object -FilePath $logFile -Append
Write-Host $summary
Write-Host "`nLog: $logFile"

Pop-Location

# ----- FASE 2: EXTRACCION EVIDENCIA -----
$logPath = $logFile
$content = Get-Content -Path $logPath -Raw
$lines = @($content -split "`r?\n")

$evidence = @(
  ($lines | Where-Object { $_ -match '^=== Phase 2B closeout ' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '^ADVERTENCIA: conexiones' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '053_real_lob_drill_pro' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '053_real_lob_drill_pro' } | Select-Object -Skip 1 -First 1),
  ($lines | Where-Object { $_ -match '^MV exists:' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '^MV exists:' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '^MV exists:' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match 'REFRESH COMPLETADO EXITOSAMENTE|REFRESH FALLO' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match 'Tiempo transcurrido:' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '8\.1 VALIDACION: Unicidad' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '8\.2 VALIDACION: Reconciliacion' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '8\.3 VALIDACION: Sanity' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '8\.4 VALIDACION: Plan' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '^=== RESUMEN FINAL ===' } | Select-Object -First 1),
  ($lines | Where-Object { $_ -match '^FASE 2B CERRADA:' } | Select-Object -First 1)
)
if (-not $evidence[3]) { $evidence[3] = $evidence[2] }
$mvLine = $evidence[4]
if ($mvLine -match 'rows: (\d+)') { $evidence[5] = "rows: $($Matches[1])" }
if ($mvLine -match 'week range: (.+)$') { $evidence[6] = "week range: $($Matches[1].Trim())" }

# ----- FASE 3: DECISION -----
$resumen = @($content -split "`r?\n" | Where-Object { $_ -match '^Alembic:|^Current==Head:|^MV exists:|^MV rows|^Refresh:|^Validate:|^FASE 2B CERRADA:' })
$alembicOkR = [bool]($resumen | Where-Object { $_ -match '^Alembic: OK' })
$currentEqHeadR = [bool]($resumen | Where-Object { $_ -match '^Current==Head: OK' })
$mvExistsR = [bool]($resumen | Where-Object { $_ -match '^MV exists: YES' })
$mvRowsR = [bool]($resumen | Where-Object { $_ -match '^MV rows > 0: YES' })
$refreshOkR = [bool]($resumen | Where-Object { $_ -match '^Refresh: OK' })
$validateOkR = [bool]($resumen | Where-Object { $_ -match '^Validate: OK' })
$closedSi = [bool]($resumen | Where-Object { $_ -match '^FASE 2B CERRADA: SI' })

$allPass = $alembicOkR -and $currentEqHeadR -and $mvExistsR -and $mvRowsR -and $refreshOkR -and $validateOkR -and $closedSi

Write-Host "`n----- EVIDENCIA (15 lineas) -----"
for ($i = 0; $i -lt 15; $i++) {
  if ($evidence -and $evidence[$i]) { Write-Host $evidence[$i] }
}

Write-Host "`n----- DECISION -----"
if ($allPass) {
  Write-Host ">>> DECISION: FASE 2B CERRADA Y ESTABLE"
} else {
  Write-Host ">>> DECISION: FASE 2B NO CERRADA"
  $razon = "Ver RESUMEN FINAL en log"
  if (-not $alembicOkR) { $razon = "Alembic upgrade/connection FAIL" }
  elseif (-not $currentEqHeadR) { $razon = "Current != Head" }
  elseif (-not $mvExistsR) { $razon = "MV no existe" }
  elseif (-not $mvRowsR) { $razon = "MV rows = 0" }
  elseif (-not $refreshOkR) { $razon = "Refresh FAIL" }
  elseif (-not $validateOkR) { $razon = "Validate FAIL (revisar Unicidad/Reconciliacion/Sanity/PlanSum)" }
  elseif (-not $closedSi) { $razon = "FASE 2B CERRADA: NO en resumen" }
  Write-Host ">>> RAZON PRINCIPAL: $razon"
  Write-Host ">>> ACCION CORRECTIVA: Revisar log $logPath y resolver la condicion indicada; re-ejecutar cierre."
}

exit 0
