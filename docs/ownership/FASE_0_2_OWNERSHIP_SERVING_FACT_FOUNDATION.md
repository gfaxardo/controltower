# Fase 0.2 — Ownership Serving Fact Foundation

**Fecha:** 2026-05-26
**Estado:** Implementado
**Fase anterior:** Fase 0.1 — Ownership Persistence Governance
**Siguiente fase recomendada:** Fase 1 — Omniview Perspective Engine

======================================================================
RESUMEN EJECUTIVO
======================================================================

Se construyó la capa serving ownership-aware (`ops.mv_ownership_serving_fact`)
que conecta plan canónico, real facts y ownership governance en un solo grain
materializado, sin afectar Omniview ni la arquitectura actual.

Esta capa es la base futura para la "Ownership Perspective" dentro de Omniview:
permitirá cambiar entre vista Operational y vista Ownership sin recálculo runtime,
sin joins frontend, y sin lógica duplicada.

======================================================================
ARQUITECTURA
======================================================================

```
RAW CSV → STAGING → CANONICAL PLAN → OWNERSHIP GOVERNANCE → SERVING FACTS → OMNIVIEW
                                         ↑                           ↑
                                    Fase 0.1                    Fase 0.2 ← YOU ARE HERE
```

### Flujo de datos del MV

```
ops.plan_trips_monthly ─────────────┐
(canonical plan: projected metrics) │
                                    ├── LEFT JOIN ──► ops.mv_ownership_serving_fact
ops.projection_ownership ──────────┤                    (plan + real + owner)
(jefe_producto, estado)             │
                                    │
ops.control_loop_plan_line_to_      │
business_slice ─────────────────────┤
(bridge: plan LOB → business_slice) │
                                    │
ops.real_business_slice_month_fact ─┘
(real metrics: trips, revenue, drivers)
```

### Grain canónico

```
(plan_version, period/month, country, city, lob_base, jefe_producto)
```

Este grain es CONSISTENTE con el grain de Omniview (business_slice), pero
agrega la dimensión `jefe_producto` desde la capa de ownership governance.

======================================================================
QUÉ SE IMPLEMENTÓ
======================================================================

1. **Materialized View `ops.mv_ownership_serving_fact`** (migración 156)
   - Grain: plan_version, period, country, city, lob_base, jefe_producto
   - Métricas plan: projected_trips, projected_drivers, projected_ticket, projected_revenue
   - Métricas real: real_trips, real_trips_cancelled, real_active_drivers, real_revenue
   - Métricas derivadas: execution_pct_trips, execution_pct_revenue, gap_trips, gap_revenue
   - Momentum: mom_pct_real_trips, mom_pct_real_revenue, momentum_status
   - Ownership: jefe_producto, ownership_assignment, ownership_quality, conflict_detected
   - MoM pre-computado via LAG window function (evita cálculo runtime)

2. **Refresh function `ops.refresh_ownership_serving_fact(boolean)`**
   - `p_concurrent=true` → refresco sin bloqueo (CONCURRENTLY)
   - `p_concurrent=false` → refresco bloqueante (más rápido, para loads iniciales)
   - Ejecutar tras: upload de plan → ownership sync → refresh de real facts → refresh MV

3. **Endpoint técnico `GET /ops/ownership-serving/monthly`**
   - Solo lectura, acceso técnico
   - Filtros: plan_version, country, city, jefe_producto, lob, period, ownership_assignment
   - Devuelve: rows (datos), aggregates (totales), by_owner (breakdown por jefe)
   - NO expone UI. Base para Ownership Perspective futura.

4. **Registro en `ops.serving_registry`**
   - serving_key: `ownership_serving_monthly`
   - grain: monthly
   - source_dependencies: [plan_trips_monthly, real_business_slice_month_fact, projection_ownership]

5. **QA Script `validate_ownership_serving_fact_foundation.py`**
   - 15 checks de validación
   - PASS/FAIL detallado

======================================================================
JOIN STRATEGY
======================================================================

### Plan → Ownership

```
ops.plan_trips_monthly.lob_base
    ↔ ops.projection_ownership.linea_negocio_canonica
```

Join normalizado: TRIM(LOWER(...)) en ambos lados.
Si no hay match → ownership_assignment = 'missing'.

### Plan LOB → Business Slice (para real data)

```
ops.plan_trips_monthly.lob_base (canonical key, e.g. "auto_taxi")
    → ops.control_loop_plan_line_to_business_slice.plan_line_key
    → business_slice_name (e.g. "Auto regular")
```

### Business Slice → Real Data

```
resolved_business_slice
    ↔ ops.real_business_slice_month_fact.business_slice_name
    + month, country, city
    + is_subfleet = false
```

### Fallback Strategy

| Escenario | Comportamiento |
|-----------|---------------|
| Ownership no existe para el slice | ownership_assignment = 'missing', datos del plan/real se incluyen |
| Ownership existe pero sin jefe | ownership_assignment = 'missing', ownership_quality = 'no_owner_named' |
| Ownership con conflicto | ownership_assignment = 'conflicting', conflict_detected = true |
| Plan LOB sin bridge a business_slice | real metrics = NULL, plan metrics se incluyen |
| Real fact no existe para el periodo | real metrics = 0, execution_pct = NULL |

### Riesgos de Mismatch

1. **LOB name mismatch**: Si `plan_trips_monthly.lob_base` tiene formato distinto a
   `projection_ownership.linea_negocio_canonica` (ej: "Auto regular" vs "auto_taxi"),
   el join falla. Se mitiga con TRIM(LOWER(...)) pero no cubre diferencias semánticas.

2. **Bridge coverage**: El bridge `control_loop_plan_line_to_business_slice` solo tiene
   4 mapeos semilla. LOBs no cubiertos no tendrán real data asociada.

3. **Real data granularity**: Real data a nivel `business_slice_name` puede no coincidir
   exactamente con los LOBs del plan. La agregación se hace a nivel de grano más fino
   disponible (business_slice_name → agregado por LOB).

======================================================================
MATERIALIZATION STRATEGY
======================================================================

### Refresh Strategy

| Aspecto | Decisión |
|---------|----------|
| Tipo | MATERIALIZED VIEW (no tabla, no view simple) |
| Refresh | Manual o programado vía `ops.refresh_ownership_serving_fact()` |
| Concurrency | CONCURRENTLY (no bloquea lecturas durante refresh) |
| Cadencia | Tras upload de plan + refresh de real facts |
| Precondición | plan_trips_monthly y real_business_slice_month_fact deben estar actualizados |

### Indexes

```
uq_mv_ownership_serving_fact_grain     UNIQUE (plan_version, period, country, city, lob_base, jefe_producto)
ix_mv_osf_period                       (period)
ix_mv_osf_jefe                         (jefe_producto) WHERE NOT NULL
ix_mv_osf_country_city_lob             (country, city, lob_base)
ix_mv_osf_ownership_assignment         (ownership_assignment)
```

### Concurrency Safety

- UNIQUE index previene double counting
- CONCURRENTLY refresh permite lecturas sin bloqueo
- La MV es solo lectura (no se inserta/actualiza/borra directamente)
- La función de refresh es la única vía de actualización

======================================================================
VALIDACIÓN VS OMNIVIEW
======================================================================

### Totals Check

La MV debe cuadrar con las fuentes originales:

```
SUM(projected_trips) en MV ≈ SUM(projected_trips) en plan_trips_monthly
SUM(real_trips) en MV ≈ SUM(trips_completed) en real_business_slice_month_fact
```

Tolerancia: < 1% de diferencia (debido a joins LEFT que pueden excluir filas).

### Consistency Rules

- Cada fila del plan con ownership debe aparecer exactamente UNA vez en la MV
- Filas sin ownership NO se excluyen (ownership_assignment = 'missing')
- Real data se agrega a nivel (period, country, city, business_slice_name)
- No se duplica real data (is_subfleet = false filtra subfleets)

======================================================================
QUÉ HABILITA ESTA FASE
======================================================================

- Consulta de métricas plan vs real por jefe_producto
- Execution tracking por owner (sin UI)
- Momentum tracking por owner (MoM pre-computado)
- Detección de gaps de ownership
- Base de datos lista para Ownership Perspective

======================================================================
QUÉ NO HABILITA TODAVÍA
======================================================================

- Perspective selector en Omniview (Operational ↔ Ownership)
- Ownership View UI
- Rankings / leaderboards
- Gamification
- Heatmaps de accountability
- Momentum scoreboards
- Reachability ownership
- Forecast ownership
- AI ownership analysis
- Accountability cards

Eso pertenece a Fase 1 — Omniview Perspective Engine y siguientes.

======================================================================
RENDIMIENTO
======================================================================

| Métrica | Target |
|---------|--------|
| Count(*) total | < 1s |
| Query 50 rows | < 3s |
| Refresh completo | Depende del volumen de plan + real facts |
| Sin bloqueo en lecturas | CONCURRENTLY refresh |

La MV deriva de tablas ya materializadas (plan_trips_monthly, real_business_slice_month_fact)
y NO escanea raw trips. El costo principal es el JOIN entre plan y real via el bridge.

======================================================================
RIESGOS
======================================================================

1. **Bridge coverage limitado**: Solo 4 mapeos en `control_loop_plan_line_to_business_slice`.
   LOBs nuevos requieren seed manual en el bridge.

2. **LOB name mismatch**: Si los nombres de LOB en `plan_trips_monthly` no coinciden con
   `projection_ownership.linea_negocio_canonica`, el join de ownership falla silenciosamente.

3. **Dependencia de refresh**: La MV no se refresca automáticamente. Requiere orquestación
   manual o programada post-upload + post-real-refresh.

4. **MoM en bordes**: El primer mes de cada serie no tiene MoM (LAG devuelve NULL).
   Series con gaps (meses faltantes) pueden tener MoM incorrecto.

5. **Sin FK formal**: No hay foreign keys entre las tablas fuente. Si se borran datos
   de `plan_trips_monthly` o `projection_ownership`, la MV queda inconsistente hasta
   el próximo refresh.

======================================================================
ARCHIVOS CREADOS / MODIFICADOS
======================================================================

| Archivo | Acción |
|---------|--------|
| `alembic/versions/156_ownership_serving_fact_foundation.py` | Nueva migración |
| `app/adapters/projection_ownership_repo.py` | Agregado `query_ownership_serving_fact()` |
| `app/services/ownership_serving_service.py` | Nuevo servicio de consulta |
| `app/routers/ops.py` | Agregado `GET /ops/ownership-serving/monthly` |
| `scripts/validate_ownership_serving_fact_foundation.py` | Nuevo script QA |
| `docs/ownership/FASE_0_2_OWNERSHIP_SERVING_FACT_FOUNDATION.md` | Esta documentación |

======================================================================
SIGUIENTE FASE RECOMENDADA (FASE 1)
======================================================================

**Omniview Perspective Engine**

Donde aparecerá el selector:

```
Perspective:
(•) Operational
( ) Ownership
```

Habilitando:
- Cambio de perspectiva sin recálculo
- Vista por owner en Omniview
- Comparativas entre owners
- Sin joins frontend
- Sin lógica duplicada

La Fase 0.2 entrega la capa de datos lista para que la Fase 1 solo tenga que
conectar el selector de perspectiva al endpoint existente.
