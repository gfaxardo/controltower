# Real LOB — Instrucciones de migración y refresh

## Cambios aplicados (064)

- **Blinda recursos**: `SET LOCAL work_mem='256MB'`, `maintenance_work_mem='512MB'`, `statement_timeout='1h'`, `lock_timeout='5min'`
- **Índices base**: `ix_trips_all_real_lob_refresh`, `ix_trips_all_park_fecha` (y equivalentes en trips_2026 si existe)
- **Sin REFRESH en migración**: `CREATE MATERIALIZED VIEW ... AS SELECT` ya popula las MVs
- **Observabilidad**: log de `pg_stat_database.temp_files` y `temp_bytes` antes/después de cada MV
- **Script seguro**: `scripts/safe_refresh_real_lob.py` para refrescar tras carga de datos

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

Si falla con `DiskFull` o `temp file limit`:
- Liberar espacio en disco (5–10 GB recomendados)
- Ver `docs/MIGRACION_064_DISKFULL_TROUBLESHOOTING.md`

### 3. Refresh post-migración (opcional)

La migración ya popula las MVs. Solo ejecutar si necesitas actualizar tras nueva carga de datos:

```bash
python -m scripts.safe_refresh_real_lob
```

### 4. Validación

```bash
psql $env:DATABASE_URL -f scripts/sql/validate_real_lob_temp_and_refresh.sql
```

En Windows PowerShell, si `DATABASE_URL` no está definido:

```powershell
$env:PGPASSWORD = "tu_password"
psql -h localhost -U tu_user -d tu_db -f scripts/sql/validate_real_lob_temp_and_refresh.sql
```

## Orden de refresh (safe_refresh_real_lob.py)

1. `ops.mv_real_drill_enriched` (base, más pesado)
2. `ops.mv_real_drill_dim_agg` (lee de enriched, CONCURRENTLY si hay unique index)
3. `ops.mv_real_rollup_day` (independiente, CONCURRENTLY si hay unique index)
