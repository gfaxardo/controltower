# FASE 2B — Runbook: Postgres, Alembic y ejecución semanal

Estado y pasos reproducibles en **Windows PowerShell**. No ejecutar desde el asistente: copiar/pegar en tu consola.

---

## FASE 0 — Diagnóstico del repo (evidencia)

### 0.1 Estructura confirmada

| Elemento | Ruta | Estado |
|----------|------|--------|
| Config Alembic | `backend/alembic.ini` | Existe |
| Migraciones | `backend/alembic/versions/` | Existe (50 archivos .py) |
| Migración 010 | `backend/alembic/versions/010_fix_real_revenue_gmv_take_rate.py` | Existe |
| Migración 013 | `backend/alembic/versions/013_create_mv_real_trips_monthly_v2_no_proxy.py` | Existe |
| Migración 014 | `backend/alembic/versions/014_create_phase2b_weekly_views.py` | Existe |

### 0.2 Encabezados de migraciones relevantes (010, 013, 014)

**010_fix_real_revenue_gmv_take_rate.py**
- `revision` = `'010_fix_real_rev_gmv'`
- `down_revision` = `'009_fix_revenue_plan_input'`
- `branch_labels` = None
- `depends_on` = None

**013_create_mv_real_trips_monthly_v2_no_proxy.py**
- `revision` = `'013_create_mv_real_trips_monthly_v2_no_proxy'`
- `down_revision` = `'010_fix_real_rev_gmv'`
- `branch_labels` = None
- `depends_on` = None

**014_create_phase2b_weekly_views.py**
- `revision` = `'014_create_phase2b_weekly_views'`
- `down_revision` = `'013_create_mv_real_trips_monthly_v2_no_proxy'`
- `branch_labels` = None
- `depends_on` = None

Cadena verificada: 009 → 010 → 013 → 014 → 015 → … → 053 (un solo head).

---

## FASE 1 — Topología Alembic

### 1.1 Comandos para ejecutar (en `backend`)

Ejecuta desde la raíz del proyecto (o ajusta rutas):

```powershell
cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\backend"

alembic heads
alembic current
alembic history --verbose
alembic branches
```

- **`alembic heads`**: debe mostrar **un solo head** (`053_real_lob_drill_pro`). Si hay más de uno, hay ramas no unidas.
- **`alembic current`**: requiere conexión a la BD; muestra la revisión actual aplicada (ej. `014_create_phase2b_weekly_views` o `053_real_lob_drill_pro`).
- **`alembic history --verbose`**: lista toda la cadena desde el head hasta la base; sirve para ver padres y detectar huecos.
- **`alembic branches`**: si hay múltiples heads, aquí aparecen; si está vacío y `heads` es uno, la línea es lineal.

### 1.2 Cómo interpretar

- **1 head**: Cadena lineal; `alembic upgrade head` aplica todas las migraciones pendientes en orden.
- **Múltiples heads**: Hay ramas. Hay que crear una “merge” migration (`alembic merge -m "merge" <rev1> <rev2>`) y luego `upgrade head`.
- **down_revision missing**: Si una revisión referencia un `down_revision` que no existe como `revision` en ningún archivo, Alembic falla al cargar. Fix: corregir `down_revision` en ese archivo para que coincida con el `revision` real del padre.
- **Ciclos / referencias inexistentes**: `alembic history` o `alembic heads` pueden fallar; hay que corregir el `down_revision` del archivo que apunta mal.

### 1.3 Estado actual (sin fix de topología)

- **013** apunta a `010_fix_real_rev_gmv`; en **010** el `revision` es `'010_fix_real_rev_gmv'` → correcto.
- **009** apunta a `008_consolidate_real_phase2a`; en **008** el `revision` es `'008_consolidate_real_phase2a'` → correcto.
- No se detectó mismatch; no se aplicó ningún cambio en archivos de migración.

---

## FASE 2 — Conexión (DATABASE_URL) sin errores de encoding

### 2.1 Password con caracteres especiales (URL-encoding)

Si la contraseña de Postgres tiene caracteres especiales (ej. `#`, `@`, `%`, `&`), hay que codificarla en la URL. En PowerShell:

```powershell
# Reemplaza YOUR_PASSWORD por tu contraseña real (sin comillas en la variable si tiene espacios/special)
$rawPassword = "YOUR_PASSWORD"
$encodedPassword = [uri]::EscapeDataString($rawPassword)

$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_NAME = "yego_integral"
$env:DB_USER = "tu_usuario"

# Opción A: Usar DATABASE_URL (recomendado para Alembic)
$env:DATABASE_URL = "postgresql://$($env:DB_USER):$encodedPassword@$($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
```

No imprimas `$env:DATABASE_URL` en pantalla si contiene la contraseña.

### 2.2 Uso de DATABASE_URL en el proyecto

- **Alembic** usa `backend/alembic/env.py`, que lee la URL desde `app.settings` (importa `from app.settings import settings`).
- **Settings** (`backend/app/settings.py`) carga `.env` vía Pydantic (`env_file` en `model_config`) y define `DATABASE_URL: str = ""`. Si `DATABASE_URL` está definida en el entorno (por ejemplo con `$env:DATABASE_URL` en la misma sesión de PowerShell), Pydantic usa esa variable de entorno y prevalece sobre el valor del `.env`.
- Por tanto: **setear `$env:DATABASE_URL` en la sesión antes de ejecutar Alembic** es suficiente para que no se use una URL mal codificada del `.env`. No hace falta modificar código; solo usar el bloque de comandos de la sección 2.3 en la misma consola donde vas a ejecutar `alembic`.

### 2.3 Bloque único para migrar (misma sesión)

Ejecutar en **una sola ventana de PowerShell**, en este orden:

```powershell
cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\backend"

# 1) Construir DATABASE_URL con password codificado (edita usuario y contraseña)
$rawPassword = "TU_PASSWORD_AQUI"
$encodedPassword = [uri]::EscapeDataString($rawPassword)
$env:DATABASE_URL = "postgresql://tu_usuario:$encodedPassword@localhost:5432/yego_integral"

# 2) Migrar al head
alembic upgrade head

# 3) Verificar revisión actual
alembic current
```

Si ya tienes `DATABASE_URL` en `.env` y no tiene caracteres problemáticos, puedes omitir los dos primeros comandos y ejecutar solo `alembic upgrade head` y `alembic current`.

---

## FASE 3 — Reparar migraciones (solo si hace falta)

- **Estado actual**: Un solo head (`053_real_lob_drill_pro`), cadena lineal. **No se aplicó ningún parche.**
- Si en tu entorno `alembic history` o `alembic heads` fallan con “down_revision not found” o múltiples heads:
  - Abre el archivo de la revisión que reporta el error y ajusta **solo** `down_revision` para que coincida con el `revision` exacto del archivo padre (el valor que aparece en el otro .py como `revision = '...'`).
  - No renombres archivos ni uses `DROP ... CASCADE` en migraciones.
- Si en el futuro hubiera **múltiples heads**:  
  `alembic merge -m "merge_heads" <rev1> <rev2>` y luego `alembic upgrade head`.

---

## FASE 4 — Ejecución Fase 2B (upgrade + refresh + validate)

### 4.1 Scripts existentes

| Script | Ruta | Uso |
|--------|------|-----|
| Refresh MV semanal | `backend/scripts/refresh_mv_real_weekly.py` | Refresca `ops.mv_real_trips_weekly` con timeout configurable. |
| Validación Fase 2B | `backend/scripts/validate_phase2b_weekly.py` | Unicidad, reconciliación vs `trips_all`, sanity, plan semanal vs mensual. |
| SQL checks manuales | `backend/sql/phase2b_weekly_checks.sql` | Consultas para ejecutar con psql (opcional). |

### 4.2 Bloque de comandos PowerShell (orden recomendado)

Misma sesión donde ya configuraste `DATABASE_URL` (o donde el backend lee correctamente la BD):

```powershell
cd "c:\Users\Pc\Documents\Cursor Proyectos\YEGO CONTROL TOWER\backend"

# 1) Migrar al head (si no lo hiciste antes)
alembic upgrade head

# 2) Refresh MV semanal (timeout 7200 s = 2 h)
python scripts/refresh_mv_real_weekly.py --timeout 7200

# 3) Validaciones Fase 2B
python scripts/validate_phase2b_weekly.py
```

Solo verificar estado de la MV (sin refrescar):

```powershell
python scripts/refresh_mv_real_weekly.py --check-only
```

Ejecutar SQL de checks manualmente (opcional; requiere `psql` y variables de conexión):

```powershell
# Ejemplo si tienes psql y PGPASSWORD en env:
# $env:PGPASSWORD = "tu_password"
# psql -h localhost -p 5432 -U tu_usuario -d yego_integral -f sql/phase2b_weekly_checks.sql
```

### 4.3 Nota sobre `refreshed_at`

El script `refresh_mv_real_weekly.py` consulta `MAX(refreshed_at)` en `ops.mv_real_trips_weekly`. Esa columna **no** existe en la definición de la MV en la migración 014; la consulta puede devolver `NULL`. Es solo informativa; el refresh y el resto del script funcionan igual.

---

## FASE 5 — Checklist “Done”

Marcar cuando todo esté correcto:

- [ ] **alembic current** muestra el head esperado (ej. `053_real_lob_drill_pro`).
- [ ] **MV semanal existe**: `ops.mv_real_trips_weekly` aparece en `pg_matviews` (o el script `--check-only` no avisa “MV semanal no existe”).
- [ ] **Refresh OK**: `python scripts/refresh_mv_real_weekly.py --timeout 7200` termina sin error.
- [ ] **Validaciones OK**: `python scripts/validate_phase2b_weekly.py` pasa las comprobaciones (unicidad, reconciliación, sanity, plan sum).
- [ ] **Endpoints responden**: p. ej. GET Phase 2B semanal (según tu API) devuelve datos coherentes.

---

## Resumen de archivos tocados (este trabajo)

- **Creado**: `docs/PHASE_2B_RUNBOOK.md` (este runbook).
- **No modificados**: migraciones, `alembic.ini`, `env.py`, `settings.py`, scripts de refresh/validate (solo se documenta su uso).

---

## Diff resumido

No se aplicaron cambios de código; solo se añadió documentación en `docs/PHASE_2B_RUNBOOK.md` con diagnóstico de migraciones (010, 013, 014), comandos para topología, construcción de `DATABASE_URL` con URL-encoding en PowerShell, bloque de upgrade + refresh + validate, y checklist final.

---

## Cierre FASE 2B con evidencia (bloque único + criterio CERRADA)

Ejecutar **desde la raíz del repo** (donde está `backend/` y `docs/`). Antes de pegar: reemplaza `YOUR_DB_USER`, `YOUR_DB_PASSWORD`, y si aplica `YOUR_DB_HOST`, `YOUR_DB_PORT`, `YOUR_DB_NAME`. La carpeta `logs/` se crea si no existe.

### 1) Bloque PowerShell (copy/paste)

```powershell
# --- Cierre FASE 2B semanal: desde raíz del repo ---
$ErrorActionPreference = 'Continue'
$RepoRoot = (Get-Location).Path
if (-not (Test-Path "backend")) { Write-Error "Ejecuta desde la raíz del repo (donde está backend/)"; exit 1 }
New-Item -ItemType Directory -Force -Path "$RepoRoot\logs" | Out-Null
$logFile = "$RepoRoot\logs\phase2b_closeout_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"
"=== Phase 2B closeout $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object -FilePath $logFile

# Credenciales (reemplaza; no se imprimen)
$env:DB_USER = 'YOUR_DB_USER'
$env:DB_PASSWORD = 'YOUR_DB_PASSWORD'
$env:DB_HOST = 'YOUR_DB_HOST'
if (-not $env:DB_HOST) { $env:DB_HOST = 'localhost' }
$env:DB_PORT = 'YOUR_DB_PORT'
if (-not $env:DB_PORT) { $env:DB_PORT = '5432' }
$env:DB_NAME = 'YOUR_DB_NAME'
if (-not $env:DB_NAME) { $env:DB_NAME = 'yego_integral' }
$encoded = [uri]::EscapeDataString($env:DB_PASSWORD)
$env:DATABASE_URL = "postgresql://$($env:DB_USER):$encoded@$($env:DB_HOST):$($env:DB_PORT)/$($env:DB_NAME)"
$env:PGPASSWORD = $env:DB_PASSWORD

Push-Location "$RepoRoot\backend"

# Alembic upgrade
"`n--- alembic upgrade head ---" | Tee-Object -FilePath $logFile -Append
alembic upgrade head 2>&1 | Tee-Object -FilePath $logFile -Append
$alembicUpgradeOk = ($LASTEXITCODE -eq 0)

# Alembic current y heads
"`n--- alembic current ---" | Tee-Object -FilePath $logFile -Append
$alembicCurrent = alembic current 2>&1
$alembicCurrent | Tee-Object -FilePath $logFile -Append
"`n--- alembic heads ---" | Tee-Object -FilePath $logFile -Append
$alembicHeads = alembic heads 2>&1
$alembicHeads | Tee-Object -FilePath $logFile -Append

# Verificar MV semanal (psql o Python)
"`n--- Verificación MV ops.mv_real_trips_weekly ---" | Tee-Object -FilePath $logFile -Append
$mvExists = $false
$psqlCmd = Get-Command psql -ErrorAction SilentlyContinue
if ($psqlCmd) {
  $mvQuery = "SELECT COALESCE(to_regclass('ops.mv_real_trips_weekly')::text, '') AS r;"
  $mvResult = (psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -t -A -c $mvQuery 2>&1) -join ' '
  $mvResult | Tee-Object -FilePath $logFile -Append | Out-Null
  if ($mvResult -match 'ops\.mv_real_trips_weekly') { $mvExists = $true }
} else {
  $pyCheck = "import sys; sys.path.insert(0,'.'); from app.db.connection import get_db, init_db_pool; init_db_pool(); g=get_db(); c=g.__enter__(); cur=c.cursor(); cur.execute(\"SELECT EXISTS (SELECT 1 FROM pg_matviews WHERE schemaname='ops' AND matviewname='mv_real_trips_weekly')\"); print('yes' if cur.fetchone()[0] else 'no'); g.__exit__(None,None,None)"
  $pyOut = python -c $pyCheck 2>&1 | Tee-Object -FilePath $logFile -Append
  if ($pyOut -match 'yes') { $mvExists = $true }
}
if ($mvExists) { "MV existe: ops.mv_real_trips_weekly" | Tee-Object -FilePath $logFile -Append } else { "MV NO encontrada" | Tee-Object -FilePath $logFile -Append }

# Refresh MV
"`n--- refresh_mv_real_weekly.py --timeout 7200 ---" | Tee-Object -FilePath $logFile -Append
python scripts/refresh_mv_real_weekly.py --timeout 7200 2>&1 | Tee-Object -FilePath $logFile -Append
$refreshOk = ($LASTEXITCODE -eq 0)

# Validaciones
"`n--- validate_phase2b_weekly.py ---" | Tee-Object -FilePath $logFile -Append
python scripts/validate_phase2b_weekly.py 2>&1 | Tee-Object -FilePath $logFile -Append
$validateOk = ($LASTEXITCODE -eq 0)

# Opcional: checks SQL
"`n--- (Opcional) phase2b_weekly_checks.sql ---" | Tee-Object -FilePath $logFile -Append
if (Get-Command psql -ErrorAction SilentlyContinue) {
  psql -h $env:DB_HOST -p $env:DB_PORT -U $env:DB_USER -d $env:DB_NAME -f sql/phase2b_weekly_checks.sql 2>&1 | Tee-Object -FilePath $logFile -Append
} else {
  "psql no instalado; omitiendo checks SQL opcionales" | Tee-Object -FilePath $logFile -Append
}

Pop-Location
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

# Resumen
$headMatch = ($alembicCurrent -match '053_real_lob_drill_pro')
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
```

### 2) Líneas exactas que debes pegar aquí (las más importantes)

Copia del log generado **solo** estas líneas (o equivalentes) y pégalas como evidencia:

1. `=== Phase 2B closeout YYYY-MM-DD HH:mm:ss ===`
2. La línea completa de salida de `alembic current` (ej. `053_real_lob_drill_pro (head)`)
3. La línea completa de `alembic heads` (ej. `053_real_lob_drill_pro (head)`)
4. `MV existe: ops.mv_real_trips_weekly` o `MV NO encontrada`
5. `REFRESH COMPLETADO EXITOSAMENTE` o `REFRESH FALLO`
6. `Tiempo transcurrido: X.XX segundos` (si el refresh fue OK)
7. En la sección RESUMEN DE VALIDACIONES: las cuatro líneas `Unicidad: [OK]/[FAIL]`, `Reconciliacion: ...`, `Sanity: ...`, `PlanSum: ...`
8. `[OK] Validaciones criticas pasaron` o `[ERROR] Validaciones criticas fallaron`
9. Las líneas finales del bloque RESUMEN: `alembic upgrade OK: True/False`, `alembic current == head (053): True/False`, `MV semanal existe: True/False`, `Refresh OK: True/False`, `Validate OK: True/False`
10. `FASE 2B CERRADA: SI` o `FASE 2B CERRADA: NO`

### 3) Criterio de cierre y si algo falla

**FASE 2B CERRADA = SÍ** si y solo si:

- `alembic upgrade head` termina sin error (exit 0).
- `alembic current` muestra exactamente el head (ej. `053_real_lob_drill_pro (head)`).
- La verificación de la MV devuelve que `ops.mv_real_trips_weekly` existe.
- `refresh_mv_real_weekly.py --timeout 7200` termina con exit 0 y en log aparece “REFRESH COMPLETADO EXITOSAMENTE”.
- `validate_phase2b_weekly.py` termina con exit 0, “Unicidad: [OK]”, “Reconciliacion: [OK]”, “Sanity: [OK]”, “PlanSum: [OK]” y “[OK] Validaciones criticas pasaron”.

**Si algo falla — siguiente paso:**

| Fallo | Qué revisar / siguiente paso |
|-------|------------------------------|
| `alembic upgrade head` falla | Revisar mensaje de error en el log (conexión, revisión bloqueada, SQL). Comprobar `alembic current` y que no haya migraciones rotas. |
| `alembic current` ≠ head | Ejecutar de nuevo `alembic upgrade head`; si ya está en head y el texto es distinto, comprobar que el head sea `053_real_lob_drill_pro`. |
| MV no existe | La migración 014 no se aplicó o falló. Revisar errores de migraciones 013/014 en el log; corregir BD o migraciones y volver a ejecutar `alembic upgrade head`. |
| Refresh falla o timeout | Revisar tamaño de `trips_all` y tiempo del REFRESH; subir `--timeout` o optimizar la MV. Revisar el mensaje de error en el log. |
| Validate falla (Unicidad/Reconciliacion/Sanity/PlanSum) | Abrir el log en la sección “VALIDACION” correspondiente; corregir datos o definiciones (MV/vistas) según el mensaje y volver a refresh/validate. |
| `psql` no encontrado | Normal; el bloque usa Python para comprobar la MV. Los checks opcionales con `phase2b_weekly_checks.sql` se omiten. |
