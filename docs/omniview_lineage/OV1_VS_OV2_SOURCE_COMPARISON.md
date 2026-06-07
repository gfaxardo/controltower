# OV1 VS OV2 SOURCE COMPARISON — Matriz Comparativa

**Generated:** 2026-06-06  
**Phase:** Control Foundation — Omniview P0 Recovery (ACTIVE)  
**Method:** Cross-referencing V1 and V2 lineage maps

---

## 1. KPI-BY-KPI SOURCE COMPARISON

| KPI | Endpoint V1 | Endpoint V2 | Source V1 | Source V2 | MV Compartida | Serving Fact Compartida | Snapshot Propio V2 | Logica Compartida | Riesgo Hereda Bug V1 | Observacion |
|-----|------------|-------------|-----------|-----------|---------------|------------------------|--------------------|--------------------|----------------------|-------------|
| **trips** | `GET /ops/business-slice/monthly` | `GET /ops/omniview-v2/matrix` (CT) | `ops.real_business_slice_month_fact.trips_completed` | `ops.real_business_slice_month_fact.trips_completed` | N/A (misma tabla) | N/A (misma tabla) | `ops.omniview_v2_serving_snapshot` (pre-built JSONB from same source) | SI — misma query, misma tabla, mismo campo | **ALTO** — Si la fact table tiene datos incorrectos, ambos sistemas los muestran | V2 lee la MISMA tabla que V1. No hay independencia de fuente. |
| **trips** | `GET /ops/business-slice/weekly` | `GET /ops/omniview-v2/matrix` (CT week) | `ops.real_business_slice_week_fact.trips_completed` | `ops.real_business_slice_week_fact.trips_completed` | N/A | N/A | Si | SI | **ALTO** | Idem — grain semanal usa misma tabla |
| **trips** | `GET /ops/business-slice/daily` | `GET /ops/omniview-v2/matrix` (CT day) | `ops.real_business_slice_day_fact.trips_completed` | `ops.real_business_slice_day_fact.trips_completed` | N/A | N/A | Si | SI | **ALTO** | Idem — grain diario usa misma tabla |
| **revenue** | `GET /ops/business-slice/monthly` | `GET /ops/omniview-v2/matrix` (CT) | `COALESCE(revenue_yego_final, revenue_yego_net)` | `revenue_yego_final` (direct) | N/A | N/A | Si | PARCIAL — misma tabla, distinta columna | **MEDIO** — V2 no usa COALESCE, si `_final` es NULL, V2 muestra NULL vs V1 que muestra `_net` | **DIFERENCIA IMPORTANTE:** V2 es mas "honesto" (NULL vs fallback silencioso) pero puede mostrar vacios donde V1 mostraba datos |
| **revenue** | `GET /ops/business-slice/omniview-projection` | `GET /ops/omniview-v2/matrix` (CT) | `serving.omniview_projection_daily_fact.revenue_yego_final` | `ops.real_business_slice_month_fact.revenue_yego_final` | N/A | **COMPARTIDA** — ambas usan `revenue_yego_final` como campo | Si | NO — V1 projection usa serving fact, V2 matrix usa fact tables directas | **BAJO** — fuentes diferentes, aunque ambas convergen en `revenue_yego_final` | V1 projection pasa por serving fact; V2 matrix va directo a fact table |
| **drivers** | `GET /ops/business-slice/monthly` | `GET /ops/omniview-v2/matrix` (CT) | `ops.real_business_slice_month_fact.active_drivers` | `ops.real_business_slice_month_fact.active_drivers` | N/A | N/A | Si | SI | **ALTO** | Misma tabla, misma columna |
| **ticket** | `GET /ops/business-slice/monthly` | `GET /ops/omniview-v2/matrix` (CT) | `ops.real_business_slice_month_fact.avg_ticket` | `ops.real_business_slice_month_fact.avg_ticket` | N/A | N/A | Si | SI | **ALTO** | Misma tabla, misma columna |
| **TPD** | Computado frontend: `trips/drivers` | Computado backend: `trips/drivers` | Fact table `trips_per_driver` o computado | `trips_per_driver` de la fact table | N/A | N/A | Si | SI — misma formula, mismo denominador | **ALTO** | Ambos derivan de trips y drivers de la misma fact table |
| **Plan vs Real** | `GET /ops/plan-vs-real/monthly` (MV) | `GET /ops/omniview-v2/shell` (readiness check) | `ops.mv_plan_vs_real_monthly_fact[_canonical]` | Shell section `plan_vs_real` — solo chequea disponibilidad, NO calcula valores | **COMPARTIDA** — MV legada | N/A | Si (vacio si no disponible) | NO — V1 calcula valores, V2 solo reporta readiness | **BAJO** — V2 no hereda bugs de calculo de Plan vs Real porque no calcula | V2 delega Plan vs Real a readiness check; no hace calculo propio |
| **Plan vs Real** | `GET /ops/control-loop/plan-vs-real` | — | `ops.real_business_slice_month_fact` + `ops.v_plan_projection_control_loop` | No existe endpoint equivalente en V2 | N/A | N/A | — | — | **N/A** — V2 no tiene este endpoint | V2 no tiene Plan vs Real operativo propio |

---

## 2. SHARED INFRASTRUCTURE MAP

### 2.1 Tables Shared (V1 + V2 both read from)

| Table | V1 Access | V2 Access | Shared Risk |
|-------|-----------|-----------|-------------|
| `ops.real_business_slice_day_fact` | Multiple endpoints | CT_TRIPS_2026 source | **ALTO** — cualquier corrupcion afecta ambos |
| `ops.real_business_slice_week_fact` | Multiple endpoints | CT_TRIPS_2026 source | **ALTO** |
| `ops.real_business_slice_month_fact` | Multiple endpoints | CT_TRIPS_2026 source | **ALTO** |
| `ops.real_business_slice_hour_fact` | Internal only | CT_TRIPS_2026 source | **MEDIO** |
| `serving.omniview_projection_daily_fact` | Projection endpoints | — | Solo V1 |
| `ops.mv_plan_vs_real_monthly_fact` | Plan vs Real monthly | Shell readiness check reference | **MEDIO** |

### 2.2 Materialized Views Shared

| MV | V1 | V2 | Shared? |
|----|----|----|---------|
| `ops.mv_plan_vs_real_monthly_fact` | Direct read | No (solo readiness) | **REFERENCIA** |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | Direct read | No | **REFERENCIA** |
| `raw_yango.mv_orders_day` | No | Si (Yango shadow) | V2 exclusivo |
| `raw_yango.mv_revenue_day` | No | Si (Yango shadow) | V2 exclusivo |

### 2.3 Refresh Orchestration Shared

| Refresh Job | Target | Affects V1 | Affects V2 |
|-------------|--------|------------|------------|
| `omniview_business_slice_real_refresh` | `day/week/month_fact` | Si | Si (mismas tablas!) |
| `serving_fact_daily_refresh` | `serving.omniview_projection_daily_fact` | Si | No |
| `refresh_raw_yango_mvs.py` | `raw_yango.mv_*` | No | Si (Yango shadow) |
| `refresh_omniview_v2_snapshots.py` | `ops.omniview_v2_serving_snapshot` | No | Si (exclusivo V2) |

---

## 3. CRITICAL SHARED DEPENDENCY ANALYSIS

### 3.1 The "Same Table" Problem

**Finding:** Omniview V2 (`CT_TRIPS_2026` source) reads from the **exact same three fact tables** as Omniview V1:
- `ops.real_business_slice_day_fact`
- `ops.real_business_slice_week_fact`
- `ops.real_business_slice_month_fact`

**Implication:** Any data quality issue in these tables (stale data, incorrect aggregation, missing periods, wrong revenue values, incorrect driver counts) will manifest in **both** V1 and V2 simultaneously.

**Mitigation in V2:**
- V2 uses `revenue_yego_final` directly (not COALESCE) — this makes revenue issues **visible** rather than hidden
- V2 adds `lineage` tracking per KPI — origin table/field/aggregation explicitly documented
- V2 adds `warnings` per response — data quality issues are surfaced
- V2 snapshot serving adds a caching layer but the underlying data is the same

### 3.2 Revenue Field Difference

| System | Revenue Source | Behavior when `_final` is NULL |
|--------|---------------|-------------------------------|
| V1 | `COALESCE(revenue_yego_final, revenue_yego_net)` | Silently shows `_net` value |
| V2 | `revenue_yego_final` | Shows NULL (or 0) |

**Impact:** If `revenue_yego_final` is not populated for certain periods/slices, V2 will show gaps where V1 showed data. This is an improvement for visibility but can cause operational confusion if not communicated.

### 3.3 Plan vs Real Gap

V1 has fully operational Plan vs Real:
- MV-based pre-aggregation
- Plan vs Real monthly, alerts, control loop variants

V2 has:
- Only a `plan_vs_real` section in shell that checks if plan data exists
- No actual Plan vs Real computation
- Blocked for Yango source

**This is a feature gap, not a bug inheritance — V2 simply hasn't built Plan vs Real yet.**

---

## 4. INDEPENDENT V2 ASSETS (Not Shared with V1)

| Asset | Purpose | Exclusivo V2 |
|-------|---------|-------------|
| `ops.omniview_v2_serving_snapshot` | Pre-built matrix + shell JSONB payloads | Si |
| `raw_yango.mv_orders_day` | Yango orders from Fleet API | Si |
| `raw_yango.mv_revenue_day` | Yango revenue from Fleet API | Si |
| `raw_yango.mv_transactions_day` | Yango transactions | Si |
| `raw_yango.mv_driver_profiles_snapshot` | Yango driver profiles | Si |
| `raw_yango.mv_source_coverage_day` | Yango source coverage | Si |
| `source_registry` (Python dataclasses) | Source definitions with metrics | Si |
| Shell 10-section architecture | Single response with multiple operational views | Si |
| MatrixResponse contract | Backend-native columns/rows/cells | Si |
| Dual-source comparison | CT vs Yango side-by-side | Si |

---

## 5. RISK CLASSIFICATION SUMMARY

| Risk Category | KPIs Affected | Severity | V2 Inherits? |
|---------------|---------------|----------|-------------|
| **Fact table data corruption** | trips, revenue, drivers, ticket, TPD | CRITICAL | **SI** — comparte tablas |
| **Revenue NULL visibility** | revenue | MEDIUM | **NO** — V2 es mas explicito |
| **Plan vs Real calculation bugs** | Plan vs Real | HIGH | **NO** — V2 no calcula Plan vs Real |
| **MV staleness** | Plan vs Real (legacy) | MEDIUM | **NO** — V2 no depende de esas MVs |
| **Refresh job failure** | trips, revenue, drivers | CRITICAL | **SI** — mismo refresh job |
| **Snapshot staleness** | matrix, shell (single-day) | MEDIUM | **SOLO V2** — riesgo nuevo |
| **Yango API coverage** | Yango shadow data | LOW | **SOLO V2** — riesgo nuevo |
| **Runtime fallback bypass** | matrix, shell | LOW | **SOLO V2** — protegido por `allow_runtime` flag |

---

## 6. ARCHITECTURAL VERDICT (Preliminary)

| Pregunta | Respuesta |
|----------|-----------|
| V2 usa fuentes V1? | **SI** — las mismas fact tables (day/week/month) |
| V2 corrige bugs de V1? | **PARCIAL** — corrige el COALESCE silencioso de revenue, pero hereda cualquier error en las fact tables |
| V2 aisla problemas de V1? | **PARCIAL** — a nivel de API/contrato (snapshot, lineage, warnings) pero NO a nivel de datos |
| V2 es independiente? | **NO** — depende del mismo pipeline de refresh y las mismas fact tables |
| V2 agrega riesgos nuevos? | **SI** — snapshot staleness, dependencia de Yango MVs, shell complexity |
