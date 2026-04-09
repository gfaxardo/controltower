# H3 — Robustez de arranque y health

**Fecha:** 2026-04-08

## Clasificación de validaciones

| Nivel | Componente | Comportamiento |
|-------|------------|----------------|
| **Bloqueante** | `init_db_pool()` | Fallo → `overall=blocked` → `RuntimeError` en startup (API no arranca). |
| **Bloqueante** | `create_plan_schema`, `create_ingestion_status_schema` | Fallo → `degraded` (se registra; API arranca). *Criterio: errores de esquema local plan/ingestion no suelen impedir todo `/ops/*`.* |
| **Crítico** | `verify_schema()` | Fallo distinto de `ValueError` (dev) → `degraded` + log. En **dev**, columnas críticas faltantes → `ValueError` (comportamiento previo). |
| **No bloqueante** | `inspect_real_columns()` | Fallo → `degraded`, resultado con `_error` o dict parcial; **no tumba** startup. |

## Transacciones

- Inspecciones en `schema_verify` que ejecutan SQL fallido siguen haciendo **`conn.rollback()`** en bloques legacy/errores para evitar cascada "current transaction is aborted".

## `/health`

- **Respuesta:** `status` ∈ `ok` | `degraded` | `blocked` | `unknown` (antes del primer startup).  
- **`db_connection`:** `ok` / `down` (ping `SELECT 1`).  
- **`startup`:** copia del último reporte (`checks`, `schema_structures` omitidos en payload si muy pesados — el reporte incluye referencias; ver implementación).  
- **HTTP:** `503` si `blocked` o DB down; `200` si `ok` o `degraded`.

## Reglas resumidas: bloqueo vs degradación

- **Blocked:** sin pool PostgreSQL.  
- **Degraded:** plan/ingestion/verify_schema/inspección fallan parcialmente.  
- **OK:** checks principales pasan.

## Nota operativa

Reiniciar el proceso uvicorn tras desplegar para que `/health` refleje el nuevo formato (el entorno anterior puede seguir sirviendo el JSON legacy hasta reinicio).
