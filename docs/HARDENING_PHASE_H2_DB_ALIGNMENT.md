# H2 — Consistencia de BD y migraciones

**Fecha:** 2026-04-08

## Estado de heads

- **Head único:** `129_ensure_v_real_data_coverage` (sin ramas múltiples detectadas en `alembic heads`).

## Decisión para `ops.v_real_data_coverage`

| Pregunta | Respuesta |
|----------|-----------|
| ¿Debe existir según diseño? | **Sí** — cobertura por país para calendario drill y freshness. |
| ¿Fue reemplazada conceptualmente? | **No** — la fuente de filas puede ser `mv_real_rollup_day` (101) o directamente `real_rollup_day_fact` (129); la **vista** sigue siendo el contrato estable. |
| ¿Faltaba en despliegue? | **Sí** (observado en logs) — migraciones incompletas o entorno sin `alembic upgrade` hasta 101/129. |

## Migración añadida

- **`129_ensure_v_real_data_coverage`:** `CREATE OR REPLACE VIEW ops.v_real_data_coverage AS … FROM ops.real_rollup_day_fact WHERE country IN ('pe','co') GROUP BY country`.  
- **No destructiva** en el sentido de que no borra datos; sustituye definición de vista.  
- **Requisito:** existe `ops.real_rollup_day_fact` (cadena hourly-first). Si no existe, la migración falla de forma explícita (acción: aplicar cadena 099–101 primero).

## Vistas/tablas canónicas — cadena resumida

```
ops.mv_real_lob_day_v2 → ops.v_real_rollup_day_from_day_v2 → ops.real_rollup_day_fact
                                                              → ops.v_real_data_coverage (129)
```

## Qué quedó canónico vs temporal

| Pieza | Estado |
|-------|--------|
| Vista `ops.v_real_data_coverage` | **Canónica** (129 la garantiza al aplicar migraciones). |
| Subconsulta en `real_data_coverage_sql` | **Temporal** solo si `to_regclass` es NULL — log + aplicar 129. |
