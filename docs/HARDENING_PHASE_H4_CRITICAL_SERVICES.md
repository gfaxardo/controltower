# H4 — Servicios críticos endurecidos

**Fecha:** 2026-04-08

## Tabla endpoint / dependencia / fallback

| Endpoint | Dependencia canónica | Fallback | Estado final | Riesgo residual |
|----------|----------------------|----------|--------------|-----------------|
| `GET /ops/real-lob/drill` | `ops.v_real_data_coverage` + `ops.mv_real_drill_dim_agg` + `ops.real_rollup_day_fact` | Subconsulta en `coverage_from_clause()` si vista ausente | Vista preferida; log si fallback | MV drill o fact vacíos → UI pobre; no es fallo HTTP si query OK |
| `GET /ops/real-drill/*` (coverage / summary segment) | Misma vista / MV rollup | Idem | Alineado con módulo único | Timeouts si MV enorme (infra) |
| `GET /ops/business-slice/coverage-summary` | `public.trips_unified` + vista resolved slice | Ninguno nuevo | **503** si timeout/cancel/disk (no maquillar como 500) | Escaneos pesados si falta índice en origen (DBA) |
| `GET /health` | Pool + reporte startup | N/A | **ok / degraded / blocked** explícito | — |

## Encapsulación

- **`app/db/real_data_coverage_sql.py`:** único lugar para `TEMPORARY_FALLBACK` + texto de reversión (`alembic upgrade` + migración **129**).

## Índices / vistas

- No se añadieron índices nuevos en esta pasada (el cuello de botella observado fue **espacio en disco** y **timeout** en entorno real, no un índice omitido verificado aquí). Recomendación operativa: revisar `pg_stat_user_tables` / planes en el servidor bajo carga.

## Errores HTTP

- **500:** errores no clasificados en coverage-summary.  
- **503:** timeout PostgreSQL, cancelación, disco lleno (mensaje genérico, sin filtrar datos sensibles).
