# FASE 2.7 — DB Layer Gate Scan

## 1. Cómo se ejecutan queries hoy

El connection layer (`backend/app/db/connection.py`) provee 4 context managers:
- `get_db()` — pool ThreadedConnectionPool, devuelve `conn` raw
- `get_db_drill()` — conexión dedicada con `statement_timeout=0`
- `get_db_audit()` — conexión con timeout largo (10 min)
- `get_db_quick()` — conexión con timeout corto (12s)

Todos devuelven una conexión psycopg2 raw. Ninguno aplica enforcement de serving.

## 2. Choke-point real

`execute_serving_query()` en `serving_guardrails.py` es el único gate para queries de serving. Pero es voluntario: cualquier código puede hacer `cur.execute(...)` directo sin pasar por el wrapper.

Los 5 servicios críticos ya usan `execute_serving_query`:
- `business_slice_omniview_service.py` — 4 call sites
- `control_loop_plan_vs_real_service.py` — 1 call site
- `real_lob_service.py` — 2 call sites
- `real_lob_service_v2.py` — 2 call sites
- `real_lob_v2_data_service.py` — 1 call site

## 3. Qué se puede interceptar sin romper el sistema

- Agregar `ContextVar` que marque si hay un gate activo
- Agregar `QueryExecutionContext` para que cada ejecución lleve metadata explícita
- Crear `execute_db_gated_query()` encima de `execute_serving_query` que fije el ContextVar
- Agregar modo configurable (`DB_SERVING_GUARD_MODE`) para graduar enforcement
- Detección de ejecución sin contexto vía consulta del ContextVar

## 4. Qué falta

| Gap | Descripción |
|-----|-------------|
| No hay ContextVar | Imposible saber a nivel execution si hay gate activo |
| No hay modo configurable | El enforcement es todo-o-nada en strict_mode por policy |
| No hay QueryExecutionContext | El wrapper solo recibe policy y source_name sueltos |
| No hay DB gate log separado | El usage_log existente no distingue service-level vs DB-level |
| No hay detección de query sin contexto | Si un servicio hace `cur.execute` directo, nadie lo detecta |

## 5. Servicios críticos ya migrados a wrapper (FASE 2.6)

Todos usan `execute_serving_query` + `register_policy` + `_SERVING_POLICY`. Ninguno usa `QueryExecutionContext` ni DB-level gate aún.
