# Real LOB — Instrucciones de migración y refresh

## Cambios aplicados (064 — modo incremental)

- **Modo incremental**: tablas fact `ops.real_drill_dim_fact` y `ops.real_rollup_day_fact` en vez de MVs gigantes
- **Ventana reciente**: solo se inserta data de los últimos N días (`REAL_LOB_RECENT_DAYS`, default 90)
- **Backfill por chunks**: `scripts/backfill_real_lob_mvs.py` para cargar histórico mes a mes
- **Coverage**: `ops.v_real_lob_coverage` expone min/max cargado; el frontend muestra "Cobertura actual: X — Y"
- **Blinda recursos**: `SET LOCAL work_mem='256MB'`, `maintenance_work_mem='512MB'`, `statement_timeout='1h'`, `lock_timeout='5min'`
- **Observabilidad**: log de `pg_stat_database.temp_files` y `temp_bytes`

## Pasos para ejecutar (manual)

**NO ejecutar automáticamente. El usuario ejecuta manualmente:**

### 1. Verificar estado actual

```bash
cd backend
alembic current
alembic heads
```

### 2. Aplicar migración 064

```bash
alembic upgrade head
```

La migración crea las tablas fact y popula solo la ventana reciente (últimos 90 días por defecto). Si falla con `DiskFull` o `temp file limit`:
- Ver `docs/MIGRACION_064_DISKFULL_TROUBLESHOOTING.md` (incluye Plan B: tablespace TEMP)

### 3. Validación

```bash
psql $env:DATABASE_URL -f scripts/sql/validate_real_lob_rescue.sql
```

En Windows PowerShell, si `DATABASE_URL` no está definido:

```powershell
$env:PGPASSWORD = "tu_password"
psql -h localhost -U tu_user -d tu_db -f scripts/sql/validate_real_lob_rescue.sql
```

Revisar que:
- `v_real_lob_coverage` muestre min/max cargado
- No haya duplicados en drill por LOB
- Exista breakdown `service_type`

### 4. Backfill histórico (opcional)

Si necesitas cargar meses anteriores:

```bash
python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2025-12-01
```

Ejemplo por meses concretos:

```bash
python -m scripts.backfill_real_lob_mvs --from 2025-06-01 --to 2025-09-01
```

### 5. Configuración opcional

| Variable | Default | Descripción |
|----------|---------|-------------|
| `REAL_LOB_RECENT_DAYS` | 90 | Días de ventana reciente que se cargan en la migración |

## Frontend: cobertura visible

La vista Real LOB muestra en el header:
- **Cobertura actual:** min_trip_date_loaded — max_trip_date_loaded
- **Último día con data:** cuando aplica
- **(ventana: N días)** si está configurado

Así se evita la impresión de "falta data" cuando el histórico aún no está backfilled.
