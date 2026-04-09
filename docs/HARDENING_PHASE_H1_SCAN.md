# H1 — Diagnóstico y mapeo del estado (scan)

**Fecha:** 2026-04-08  
**Alcance:** backend startup, rutas críticas `/ops`, Alembic, scripts SQL, frontend consumidor.

## 1. Dependencias canónicas esperadas (Real / coverage)

| Objeto | Rol | Cadena documentada |
|--------|-----|-------------------|
| `ops.real_rollup_day_fact` | Rollup diario canónico (vista sobre `mv_real_lob_day_v2` en cadena 101) | Fuente de filas para cobertura por país |
| `ops.mv_real_rollup_day` | Vista de compatibilidad `SELECT * FROM real_rollup_day_fact` (101) | Usada en migraciones antiguas para `v_real_data_coverage` |
| `ops.v_real_data_coverage` | Agregado por `country` (`pe`/`co`): min/max fechas, min_month, min_week | Consumida por drill PRO, real_drill (calendario/coverage) |
| `ops.mv_real_drill_dim_agg` | Drill PRO por periodo/breakdown | `/ops/real-lob/drill` |
| `public.trips_unified` + vista resolved business slice | Cobertura matrix | `/ops/business-slice/coverage-summary` |

**Plan vs Real:** contratos separados; Real permanece en Postgres (`ops.*`, `public.trips_unified`, dims).

## 2. Qué existe en código (estado tras hardening)

- **Startup:** `app/main.py` delega en `run_startup_checks()` (`startup_checks.py`), guarda reporte en `startup_state.py`.
- **Inspección:** `schema_verify.verify_schema()` (columnas críticas `dim.dim_park`, `bi.real_daily_enriched`); `inspect_real_columns()` legacy + rollback en fallos.
- **Cobertura centralizada:** `app/db/real_data_coverage_sql.py` — resolución `to_regclass('ops.v_real_data_coverage')` → vista canónica o subconsulta equivalente sobre `ops.real_rollup_day_fact` con log `[TEMPORARY_FALLBACK:v_real_data_coverage]`.
- **Servicios:** `real_lob_drill_pro_service.get_drill`, `real_drill_service.get_real_drill_coverage` y rama B2B/B2C de `get_real_drill_summary` usan `coverage_from_clause()`.

## 3. Qué garantizan las migraciones (BD esperada)

- **Head actual:** `129_ensure_v_real_data_coverage` (después de `128_omniview_matrix_issue_action_log`).
- **101:** define `real_rollup_day_fact`, `mv_real_rollup_day`, `v_real_data_coverage` desde `mv_real_rollup_day`.
- **129:** `CREATE OR REPLACE VIEW ops.v_real_data_coverage` desde `ops.real_rollup_day_fact` (alineación explícita si un despliegue no aplicó 101 completo).

## 4. Fallbacks identificados

- **Temporal explícito:** si la vista no existe, misma semántica vía subconsulta en `real_data_coverage_sql.coverage_from_clause()` — revertir con `alembic upgrade head` (129) cuando la BD esté alineada.

## 5. Cinco endpoints más críticos para disponibilidad

1. `GET /health` — liveness + estado startup/DB.  
2. `GET /ops/real-lob/drill` — drill PRO (MV + coverage).  
3. `GET /ops/business-slice/coverage-summary` — consultas pesadas sobre `trips_unified` + vista resolved.  
4. `GET /ops/business-slice/filters` — carga de omniview / slice.  
5. `GET /ops/data-trust` o `GET /ops/real/monthly` (canónico) — narrativa de confianza / Real mensual.

## 6. Frontend — consumo

- `frontend/src/services/api.js`: `/ops/real-lob/drill`, `drill/children`, `drill/parks`, `/ops/business-slice/coverage-summary` (timeout largo para heavy).  
- Contratos JSON existentes no se modificaron en nombre de campos; solo comportamiento HTTP 503 en `coverage-summary` bajo timeout/recurso (ver H4).

## 7. Scripts útiles (repo)

- `backend/scripts/regenerate_views_and_verify.py` — lista de vistas incl. `ops.v_real_data_coverage`.  
- `backend/scripts/diagnose_and_fix_real_drill.py` — SQL de reparación drill.  
- `alembic upgrade head` — alineación canónica.
