# Fase 2B — Cierre definitivo semanal (documentación y runbook)

**Objetivo:** Cerrar Fase 2B con evidencia sólida y log reproducible, resolviendo "too many clients" y statement timeout en validaciones.

**Restricciones:** Sin inventar datos, sin asumir BD libre, sin imprimir contraseñas, sin DROP CASCADE. Cambios mínimos y seguros.

---

## FASE 1 — Hardening de conexiones (aplicado)

### 1.1 `backend/scripts/refresh_mv_real_weekly.py`

- **Engine propio:** `create_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True)`.
- **Uso:** `with engine.connect() as conn` → `raw_conn = conn.connection` para ejecutar REFRESH y verificaciones; cierre explícito de cursores.
- **Cierre:** `engine.dispose()` en `finally` para no dejar conexiones abiertas.
- **Logging:** `logging.basicConfig(..., format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")`.

### 1.2 `backend/scripts/validate_phase2b_weekly.py`

- **Engine propio:** mismo patrón `pool_size=2`, `max_overflow=0`, `pool_pre_ping=True`.
- **Timeout:** al inicio de la sesión se ejecuta `SET statement_timeout = '10min';` para todas las queries (reconciliación, PlanSum, etc.).
- **Cierre:** `engine.dispose()` en `finally`.
- **Timeout explícito:** excepciones por statement timeout (QueryCanceled / 57014 / "canceling statement") se capturan y se registran como `[FAIL]` claro en log y consola.
- **Logging:** mismo formato con timestamps.

### 1.3 Script auxiliar

- **`backend/scripts/check_connections.py`:** imprime dos líneas (conexiones activas, max_connections) para que el bloque PowerShell avise si hay riesgo de "too many clients".

---

## FASE 2 — Bloque PowerShell de cierre robusto

Ejecutar **desde la raíz del repo** (donde está `backend/`). Definir antes las variables de entorno: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`. No se imprimen contraseñas.

```powershell
# --- Cierre FASE 2B definitivo (desde raiz del repo) ---
$ErrorActionPreference = 'Continue'
$RepoRoot = (Get-Location).Path
if (-not (Test-Path "backend")) { Write-Error "Ejecuta desde la raiz del repo (donde esta backend/)"; exit 1 }
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null
$logFile = "$RepoRoot\logs\phase2b_closeout_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"
"=== Phase 2B closeout $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $logFile

if (-not $env:DATABASE_URL) {
  if (-not $env:DB_USER -or -not $env:DB_PASSWORD) { Write-Error "Define DB_USER y DB_PASSWORD (y opcionalmente DB_HOST, DB_PORT, DB_NAME)"; exit 1 }
  if (-not $env:DB_HOST) { $env:DB_HOST = 'localhost' }
  if (-not $env:DB_PORT) { $env:DB_PORT = '5432' }
  if (-not $env:DB_NAME) { $env:DB_NAME = 'yego_integral' }
  $encoded = [uri]::EscapeDataString($env:DB_PASSWORD)
  $env:DATABASE_URL = "postgresql://$($env:DB_USER):$encoded@$($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
}
$env:PGPASSWORD = $env:DB_PASSWORD

Push-Location "$RepoRoot\backend"

# 5) Conexiones activas vs max_connections
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

# 6) Alembic
"`n--- alembic upgrade head ---" | Tee-Object -FilePath $logFile -Append
alembic upgrade head 2>&1 | Tee-Object -FilePath $logFile -Append
$alembicOk = ($LASTEXITCODE -eq 0)

"`n--- alembic current ---" | Tee-Object -FilePath $logFile -Append
$alembicCurrent = alembic current 2>&1 | Out-String
$alembicCurrent | Tee-Object -FilePath $logFile -Append
"`n--- alembic heads ---" | Tee-Object -FilePath $logFile -Append
$alembicHeads = alembic heads 2>&1 | Out-String
$alembicHeads | Tee-Object -FilePath $logFile -Append

# 7) Current == Head (FAIL inmediato si no)
$expectedHead = '053_real_lob_drill_pro'
$currentMatch = [bool]($alembicCurrent -match $expectedHead)
$headsMatch = [bool]($alembicHeads -match $expectedHead)
$currentEqHead = $currentMatch -and $headsMatch
if (-not $currentEqHead) {
  "FAIL: current no coincide con head esperado ($expectedHead)" | Tee-Object -FilePath $logFile -Append
}

# 8) Verificacion MV: to_regclass, COUNT(*), MIN/MAX week_start
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

# 9) Refresh
"`n--- refresh_mv_real_weekly.py --timeout 7200 ---" | Tee-Object -FilePath $logFile -Append
python scripts/refresh_mv_real_weekly.py --timeout 7200 2>&1 | Tee-Object -FilePath $logFile -Append
$refreshOk = ($LASTEXITCODE -eq 0)

# 10) Validate
"`n--- validate_phase2b_weekly.py ---" | Tee-Object -FilePath $logFile -Append
python scripts/validate_phase2b_weekly.py 2>&1 | Tee-Object -FilePath $logFile -Append
$validateOk = ($LASTEXITCODE -eq 0)

Pop-Location
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

# 12) Resumen
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
```

---

## FASE 3 — Optimización si la reconciliación sigue lenta

### 3.1 Query exacta de reconciliación

La validación "Reconciliacion" en `validate_phase2b_weekly.py` ejecuta esta query (parámetro `week_start` = última semana cerrada):

```sql
WITH direct_sum AS (
    SELECT
        DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE as week_start,
        COALESCE(dp.country, '') as country,
        -1 * SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego_direct
    FROM public.trips_all t
    LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
    WHERE t.condicion = 'Completado'
      AND DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE = :week_start
    GROUP BY 1,2
),
mv_sum AS (
    SELECT week_start, country, SUM(revenue_real_yego) as revenue_real_yego_mv
    FROM ops.mv_real_trips_weekly
    WHERE week_start = :week_start
    GROUP BY 1,2
)
SELECT ... FROM direct_sum d FULL OUTER JOIN mv_sum m ON ...
```

### 3.2 Diagnóstico recomendado

En la BD, con la semana concreta (ej. `'2026-02-16'::date`):

```sql
EXPLAIN (ANALYZE, BUFFERS)
WITH direct_sum AS (
    SELECT
        DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE as week_start,
        COALESCE(dp.country, '') as country,
        -1 * SUM(NULLIF(t.comision_empresa_asociada, 0)) as revenue_real_yego_direct
    FROM public.trips_all t
    LEFT JOIN dim.dim_park dp ON t.park_id = dp.park_id
    WHERE t.condicion = 'Completado'
      AND DATE_TRUNC('week', t.fecha_inicio_viaje)::DATE = '2026-02-16'::date
    GROUP BY 1,2
),
mv_sum AS (
    SELECT week_start, country, SUM(revenue_real_yego) as revenue_real_yego_mv
    FROM ops.mv_real_trips_weekly
    WHERE week_start = '2026-02-16'::date
    GROUP BY 1,2
)
SELECT COALESCE(d.week_start, m.week_start), COALESCE(d.country, m.country),
       COALESCE(d.revenue_real_yego_direct, 0), COALESCE(m.revenue_real_yego_mv, 0)
FROM direct_sum d
FULL OUTER JOIN mv_sum m ON d.week_start = m.week_start AND d.country = m.country;
```

Revisar en el plan: secuencia de scans en `trips_all`, uso de índices en `week_start`/`fecha_inicio_viaje`, `country`, `park_id`, `lob_base`.

### 3.3 Índices opcionales (solo si EXPLAIN lo justifica y la tabla es grande)

- **trips_all:** filtro por `condicion` y `DATE_TRUNC('week', fecha_inicio_viaje)::DATE`; join por `park_id`. Índice sugerido (crear CONCURRENTLY en ventana de bajo uso):

  ```sql
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_all_condicion_week_start
  ON public.trips_all (condicion, (DATE_TRUNC('week', fecha_inicio_viaje)::date));
  ```

  Si ya existe índice por `(fecha_inicio_viaje)` o por `(park_id, fecha_inicio_viaje)`, puede ser suficiente; contrastar con EXPLAIN.

- **dim.dim_park:** join por `park_id`. Normalmente ya existe PK o índice en `park_id`; si no:

  ```sql
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_park_park_id ON dim.dim_park (park_id);
  ```

- **ops.mv_real_trips_weekly:** la MV ya tiene `idx_mv_real_trips_weekly_week_start` y `idx_mv_real_trips_weekly_country_city_lob_seg_week`. No es necesario crear más por esta query.

Cualquier índice nuevo creado (nombre y tabla) debe anotarse aquí:

| Índice creado | Tabla / esquema | Notas |
|---------------|-----------------|--------|
| (ej. idx_trips_all_condicion_week_start) | public.trips_all | Solo si EXPLAIN lo recomienda |

---

## Líneas exactas del log para pegar como evidencia (15)

Copiar del archivo `logs/phase2b_closeout_YYYYMMDD_HHmm.txt` generado por el bloque anterior estas líneas (o equivalentes) y pegarlas en la sección de evidencia (p. ej. `docs/PHASE_2B_STATUS.md`):

1. `=== Phase 2B closeout YYYY-MM-DD HH:mm:ss ===`
2. La línea de advertencia de conexiones (si apareció): `ADVERTENCIA: conexiones activas=...`
3. Primera línea de salida de `--- alembic upgrade head ---` (o `INFO`/error)
4. La línea de salida de `alembic current` que contiene el revision id (ej. `053_real_lob_drill_pro (head)`)
5. La línea de salida de `alembic heads` que contiene el revision id
6. `MV exists: True | rows: NNN | week range: ...` (o el equivalente)
7. `REFRESH COMPLETADO EXITOSAMENTE` (o `REFRESH FALLO`)
8. `Tiempo transcurrido: X.XX segundos` (tras el refresh)
9. `8.1 VALIDACION: Unicidad MV semanal` y la línea siguiente `[OK]` o `[ERROR]`
10. `8.2 VALIDACION: Reconciliacion semanal` y la línea con `[OK]` o `[FAIL]`/timeout
11. `8.3 VALIDACION: Sanity checks` y resumen
12. `8.4 VALIDACION: Plan semanal suma a plan mensual` y `[OK]` o `[FAIL]`
13. Bloque `RESUMEN DE VALIDACIONES` con las cuatro líneas `Unicidad: [OK]/[FAIL]`, `Reconciliacion: ...`, `Sanity: ...`, `PlanSum: ...`
14. Las líneas del `=== RESUMEN FINAL ===` (Alembic, Current==Head, MV exists, MV rows > 0, Refresh, Validate)
15. `FASE 2B CERRADA: SI` o `FASE 2B CERRADA: NO`

---

## Confirmación final

**¿FASE 2B puede considerarse estructuralmente estable?**

- **Sí**, una vez que:
  1. El bloque PowerShell termina con **FASE 2B CERRADA: SI** (Alembic OK, Current==Head, MV existe, MV rows > 0, Refresh OK, Validate OK).
  2. Las 15 líneas del log se guardan como evidencia y el resumen confirma todos OK.
  3. En entorno con muchas conexiones se ha respetado la advertencia de conexiones (cerrar otras apps o ejecutar en ventana de menor carga) y, si aplica, se han creado índices opcionales documentados tras EXPLAIN ANALYZE.

**Por qué:** La estabilidad depende de no saturar el pool de Postgres (hardening con pool pequeño y dispose en scripts), de dar tiempo suficiente a la reconciliación (statement_timeout 10min y captura explícita de timeout como FAIL) y de tener un runbook repetible que escribe un único log con resumen final y criterio SI/NO sin asumir datos ni imprimir credenciales.
