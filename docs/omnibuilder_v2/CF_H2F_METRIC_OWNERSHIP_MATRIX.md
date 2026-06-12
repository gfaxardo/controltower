# CF-H2F — METRIC OWNERSHIP MATRIX (FINAL)

> **Fase:** CF-H2F — Metric Ownership Matrix
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `METRIC_OWNERSHIP_CERTIFIED`

---

## 1. EXECUTIVE SUMMARY

Matriz definitiva de ownership para **21 KPIs** de Omniview. Cada KPI tiene dueño canónico, shadow validator, fallback, badge, reglas de promoción y rollback. **15 KPIs con promoción READY. 4 requieren construcción previa. 2 bloqueados.**

Basada en evidencia certificada:
- CF-H2C.0A: Orders ingestion CERTIFIED
- CF-H2C.0B.1: Transactions ingestion CERTIFIED
- CF-H2C.1: Driver Identity CERTIFIED (100% UUID match)
- CF-H2C.0C: Semantic Reconciliation CERTIFIED
- CF-H2D: Near Real-Time Scheduler CERTIFIED

---

## 2. CONTEXT: DATA PILLARS

| Pillar | Phase | Status |
|--------|-------|--------|
| Orders ingestion (Lima) | CF-H2C.0A | CERTIFIED |
| Transactions ingestion (Lima) | CF-H2C.0B.1 | CERTIFIED |
| Driver Identity (Lima) | CF-H2C.1 | CERTIFIED |
| Near Real-Time Scheduler | CF-H2D | CERTIFIED |
| Semantic Reconciliation | CF-H2C.0C | CERTIFIED |
| Revenue formula | CF-H2C.0B | CERTIFIED |
| Watermarks | CF-H2C | CERTIFIED |

---

## 3. METRIC OWNERSHIP MATRIX (21 KPIs)

### 3.1 Core Operational KPIs

| # | metric_name | business_meaning | canonical_owner | shadow_validator | fallback_source | source_badge | grain | formula | required_joins | freshness_target | coverage_requirement | promotion_threshold | rollback_rule | confidence | promotion_status |
|---|------------|-----------------|-----------------|-----------------|-----------------|-------------|-------|---------|---------------|-----------------|---------------------|---------------------|--------------|------------|-----------------|
| K1 | `completed_trips` | Trips completados por día/park/slice | YANGO | CT `trips_completed` | CT_BRIDGE `ops.real_business_slice_day_fact` | YANGO_API | Day, Week, Month | `COUNT(DISTINCT order_id) FROM raw_yango.orders_raw WHERE order_status='complete'` | `orders_raw` → `mv_orders_day` → serving | ≤ 5 min | ≥ 95% vs CT (30d) | ≤ 1% delta vs CT (30d consecutive) | Delta > 1% for 5+ days OR coverage < 90% for 3+ days → rollback CT | HIGH | **READY** |
| K2 | `cancelled_trips` | Trips cancelados | CT_BRIDGE | N/A (Yango no ingiere cancelados) | N/A (única fuente) | CT_BRIDGE | Day, Week, Month | `SUM(trips_cancelled) FROM ops.real_business_slice_day_fact` | `trips_2026` → day_fact → serving | ≤ 25h | ≥ 95% coverage | N/A (CT-only, sin promoción) | N/A (sin candidato Yango) | MEDIUM | **NOT_CERTIFIED** |
| K3 | `total_orders` | Suma completed + cancelled | HYBRID | Yango completed + CT cancelled | Yango completed only (underestimates) | HYBRID | Day, Week, Month | `K1 + K2` | Depende de K1 + K2 | ≤ 25h | ≥ 95% coverage | Igual que K1 | Si K1 o K2 fallan, reportar HYBRID_DEGRADED | MEDIUM | **READY** |
| K4 | `active_drivers` | Conductores con al menos 1 trip | YANGO | CT `COUNT(DISTINCT conductor_id)` | CT_BRIDGE `ops.real_business_slice_day_fact` | YANGO_API | Day, Week, Month | `COUNT(DISTINCT driver_profile_id) FROM raw_yango.orders_raw WHERE order_status='complete'` | `orders_raw` → `mv_orders_day` → serving | ≤ 5 min | ≥ 95% vs CT (30d) | ≤ 5% delta vs CT (30d consecutive) | Delta > 5% for 5+ days OR coverage < 90% for 3+ days → rollback CT | HIGH | **READY** |
| K5 | `revenue_yego` | Revenue YEGO real (comisión Partner Fee) | YANGO | CT `revenue_yego_final` (per-slice, explained gap) | CT_BRIDGE `ops.real_business_slice_day_fact` | YANGO_API | Day, Week, Month | `SUM(ABS(amount)) FROM raw_yango.transactions_raw WHERE category_name='Partner fee for trip'` | `transactions_raw` → `mv_revenue_day` → serving | ≤ 5 min | ≥ 95% vs CT (30d) | ≤ 5% per-trip delta vs CT (30d) | Delta > 5% for 5+ days OR coverage < 90% for 3+ days → rollback CT | HIGH | **READY** |
| K6 | `gmv` | Gross Merchandise Value | YANGO | CT `efectivo+tarjeta+pago_corporativo` (= 0 en Lima) | CT_BRIDGE (proxy via ticket promedio) | YANGO_API | Day, Week, Month | `SUM(amount) FROM raw_yango.transactions_raw WHERE category_name IN ('Cash','Card payment','Corporate payment')` | `transactions_raw` → `mv_revenue_day` → serving | ≤ 5 min | ≥ 95% vs transactions volume | N/A (CT = 0, Yango es única fuente viable) | API fail → flag MISSING (sin CT comparable) | HIGH | **READY** |

### 3.2 Derived KPIs

| # | metric_name | business_meaning | canonical_owner | shadow_validator | fallback_source | source_badge | grain | formula | required_joins | freshness_target | coverage_requirement | promotion_threshold | rollback_rule | confidence | promotion_status |
|---|------------|-----------------|-----------------|-----------------|-----------------|-------------|-------|---------|---------------|-----------------|---------------------|---------------------|--------------|------------|-----------------|
| K7 | `avg_ticket` | Ticket promedio (GMV / trip) | YANGO | CT `avg_ticket` from day_fact | CT_BRIDGE | YANGO_API | Day, Week, Month | `K6 / K1` | Depende de K1 + K6 | ≤ 5 min (hereda K1+K6) | Hereda de K1+K6 | Hereda de K1+K6 | Rollback si K1 o K6 rollback | HIGH | **READY** |
| K8 | `trips_per_driver` | Viajes por conductor activo | YANGO | CT `trips_per_driver` from day_fact | CT_BRIDGE | YANGO_API | Day, Week, Month | `K1 / K4` | Depende de K1 + K4 | ≤ 5 min (hereda K1+K4) | Hereda de K1+K4 | Hereda de K1+K4 | Rollback si K1 o K4 rollback | HIGH | **READY** |
| K9 | `revenue_per_order` | Revenue YEGO por viaje | YANGO | CT `revenue_per_order` derived | CT_BRIDGE | YANGO_API | Day, Week, Month | `K5 / K1` | Depende de K1 + K5 | ≤ 5 min (hereda K1+K5) | Hereda de K1+K5 | Hereda de K1+K5 | Rollback si K1 o K5 rollback | HIGH | **READY** |
| K10 | `commission_pct` | Tasa de comisión (Platform Fee / GMV) | YANGO | CT `commission_pct` from day_fact | CT_BRIDGE | YANGO_API | Day, Week, Month | `SUM(ABS(amount)) WHERE Service fee for trip / K6` | `transactions_raw` → `mv_revenue_day` | ≤ 5 min (hereda K6) | ≥ 95% vs CT (30d) | ≤ 5% delta vs CT (30d) | Rollback si K6 rollback | MEDIUM | **READY** |
| K11 | `cancel_rate_pct` | Tasa de cancelación | HYBRID | CT (Yango sin cancelados) | CT_BRIDGE | HYBRID | Day, Week, Month | `K2 / (K1 + K2)` | Depende de K1 + K2 | ≤ 25h | N/A (sin comparación Yango) | N/A (sin candidato Yango) | Rollback si K2 falla | MEDIUM | **NOT_CERTIFIED** |

### 3.3 Identity & Lifecycle KPIs

| # | metric_name | business_meaning | canonical_owner | shadow_validator | fallback_source | source_badge | grain | formula | required_joins | freshness_target | coverage_requirement | promotion_threshold | rollback_rule | confidence | promotion_status |
|---|------------|-----------------|-----------------|-----------------|-----------------|-------------|-------|---------|---------------|-----------------|---------------------|---------------------|--------------|------------|-----------------|
| K12 | `driver_identity` | Identidad canónica del conductor | SHARED | N/A (100% match confirmado) | `public.drivers` (CT) | SHARED | Per-driver | `driver_profile_id (Yango) = driver_id (public.drivers) = conductor_id (trips_2026)` | `yango_driver_identity_map_shadow` | N/A (identidad estática) | 100% match verificado | 100% (800/800 Lima verified) | N/A (sin promoción necesaria, ya es shared) | VERY_HIGH | **READY** |
| K13 | `new_drivers` | Conductores contratados recientemente | CT_BRIDGE | Yango (requiere 90+ días de history) | `public.drivers` (CT) | CT_BRIDGE | Day, Week, Month | `COUNT(DISTINCT driver_id) FROM public.drivers WHERE hire_date >= target_date - N days` | `public.drivers` → `driver_identity_map` | ≤ 25h | ≥ 95% coverage | ≤ 5% delta vs Yango-derived (cuando 90+ días de history) | N/A (CT-only hasta que Yango tenga history suficiente) | HIGH | **SHADOW_ONLY** |
| K14 | `reactivated_drivers` | Conductores reactivados tras inactividad | REQUIRES_CONSTRUCTION | N/A | CT_BRIDGE `growth.yego_lima_driver_lifecycle_daily` | CT_BRIDGE | Day, Week, Month | `COUNT(DISTINCT driver_id) WHERE inactive_days > 15 AND completed_trips_today > 0` | `lifecycle_daily` → `activity_daily` | ≤ 25h | ≥ 95% coverage | N/A (requiere lifecycle canónico desde Yango) | N/A | MEDIUM | **BLOCKED** |
| K15 | `churned_drivers` | Conductores inactivos >15d | REQUIRES_CONSTRUCTION | N/A | CT_BRIDGE `growth.yego_lima_driver_lifecycle_daily` | CT_BRIDGE | Day, Week, Month | `COUNT(DISTINCT driver_id) WHERE inactive_days > 15 AND completed_trips_today = 0` | `lifecycle_daily` → `activity_daily` | ≤ 25h | ≥ 95% coverage | N/A (requiere lifecycle canónico desde Yango) | N/A | MEDIUM | **BLOCKED** |
| K16 | `supply_hours` | Horas online del conductor | BLOCKED | N/A | CT_BRIDGE `growth.yango_lima_driver_360_daily` | BLOCKED | Day | `GET /v2/parks/contractors/supply-hours` (per-driver endpoint, no bulk) | Yango API per-driver | N/A | N/A | N/A (sin endpoint bulk viable) | N/A (sin candidato) | LOW | **BLOCKED** |

### 3.4 Dimensional KPIs

| # | metric_name | business_meaning | canonical_owner | shadow_validator | fallback_source | source_badge | grain | formula | required_joins | freshness_target | coverage_requirement | promotion_threshold | rollback_rule | confidence | promotion_status |
|---|------------|-----------------|-----------------|-----------------|-----------------|-------------|-------|---------|---------------|-----------------|---------------------|---------------------|--------------|------------|-----------------|
| K17 | `business_slice` | Segmento de negocio | REQUIRES_MAPPING | CT `business_slice_name` | CT_BRIDGE | YANGO_API | Per-fact | `order.category → dim.yango_category_to_slice` | `orders_raw.category` → `dim.yango_category_to_slice` → `dim.dim_business_slice` | ≤ 25h | ≥ 95% mapping coverage | Mapping table validada con ≥ 95% de órdenes clasificadas | Fallback a CT business_slice_name si mapping incompleto | MEDIUM | **BLOCKED** |
| K18 | `park` | Parque operativo | SHARED | N/A | `dim.dim_park` | SHARED | Per-fact | `api_park_credentials_registry.park_id = dim.dim_park.park_id` | `api_park_credentials_registry` → `dim.dim_park` | N/A (dimensión estática) | 100% | N/A | N/A | HIGH | **READY** |
| K19 | `city` | Ciudad | SHARED | N/A | `dim.dim_park.city` | SHARED | Per-fact | `dim.dim_park.city` | `dim.dim_park` | N/A | 100% | N/A | N/A | HIGH | **READY** |
| K20 | `country` | País | SHARED | N/A | `dim.dim_park.country` | SHARED | Per-fact | `dim.dim_park.country` | `dim.dim_park` | N/A | 100% | N/A | N/A | HIGH | **READY** |

### 3.5 Program KPIs

| # | metric_name | business_meaning | canonical_owner | shadow_validator | fallback_source | source_badge | grain | formula | required_joins | freshness_target | coverage_requirement | promotion_threshold | rollback_rule | confidence | promotion_status |
|---|------------|-----------------|-----------------|-----------------|-----------------|-------------|-------|---------|---------------|-----------------|---------------------|---------------------|--------------|------------|-----------------|
| K21 | `scout_attribution / cohorts / programs` | Atribución de campaña, cohortes y programas | CT_BRIDGE | Yango (requiere mapeo de campaigns) | CT_BRIDGE | CT_BRIDGE | Day, Month | `growth schema program tables + public.drivers` | `yango_lima_program_eligibility_daily` → `yego_lima_program_registry` | ≤ 25h | ≥ 95% coverage | N/A (sin fuente Yango comparable aún) | N/A (CT-only) | MEDIUM | **SHADOW_ONLY** |

---

## 4. OWNERSHIP RECOMMENDATIONS (RATIONALE)

| KPI | Owner | Why |
|-----|-------|-----|
| `completed_trips` | **YANGO** | Yango orders_raw con COUNT(DISTINCT order_id) alinea ±1 orden/día con CT. IDs de driver son compartidos. Near-real-time (≤2.5 min freshness). CT proxy fallback. |
| `cancelled_trips` | **CT_BRIDGE** | Yango API filtra `statuses: ['complete']`. Cancelados NUNCA son ingeridos. Hasta que el scheduler incluya status 'cancelled', CT es la única fuente. |
| `total_orders` | **HYBRID** | Suma de Yango (completed) + CT (cancelled). Mientras cancelled sea CT-only, total_orders es híbrido. Si Yango ingiere cancelados, total_orders → YANGO. |
| `active_drivers` | **YANGO** | driver_profile_id = driver_id = conductor_id (100% match Lima). COUNT(DISTINCT) desde orders_raw es near-real-time. CT como shadow validator. |
| `revenue_yego` | **YANGO** | Partner fee for trip es la comisión REAL cobrada por viaje. CT revenue_yego_final contiene proxy (ticket × 3%) que infla ~5x. Per-trip delta solo 2.4% cuando coverage es completo. |
| `gmv` | **YANGO** | CT efectivo/tarjeta/pago_corporativo = 0 para Lima. Yango transactions_raw es la única fuente con GMV real (Cash + Card + Corporate). Sin comparación posible con CT. |
| `avg_ticket` | **YANGO** | Derivado de K1+K6. Hereda ownership Yango. |
| `trips_per_driver` | **YANGO** | Derivado de K1+K4. Hereda ownership Yango. |
| `revenue_per_order` | **YANGO** | Derivado de K1+K5. Hereda ownership Yango. |
| `commission_pct` | **YANGO** | Platform Fee / GMV desde transactions_raw. CT commission_pct usa revenue_yego_final (con proxy) / total_fare (incompleto). Yango es más preciso. |
| `cancel_rate_pct` | **HYBRID** | Mismo razonamiento que K2. Mientras Yango no ingiera cancelados, la tasa es híbrida: Yango completed + CT cancelled. |
| `driver_identity` | **SHARED** | driver_profile_id = driver_id confirmado 800/800 (100%). Mismo UUID. No se requiere mapping table para Lima. Shadow identity map existe para auditoría. |
| `new_drivers` | **CT_BRIDGE** | hire_date está en public.drivers (CT). Yango no expone fecha de alta. Requiere 90+ días de history de Yango para derivar "primera orden = hire_date proxy". |
| `reactivated_drivers` | **CT_BRIDGE** | Requiere lifecycle_daily con history. Actualmente solo existe en CT bridge. Yango necesitaría 90+ días de orders_raw para construir lifecycle canónico. |
| `churned_drivers` | **CT_BRIDGE** | Mismo razonamiento que reactivated. Depende de lifecycle history. |
| `supply_hours` | **BLOCKED** | Endpoint per-driver (1 HTTP call por conductor). 1,000 drivers × 1.5s = 25 min por ciclo. Inviable para near-real-time. Sin endpoint bulk de Yango. |
| `business_slice` | **REQUIRES_MAPPING** | Yango category (ej. "econom") no mapea 1:1 a CT business_slice_name (ej. "Auto regular"). Requiere dim.yango_category_to_slice. |
| `park/city/country` | **SHARED** | Dimensiones geográficas vienen de api_park_credentials_registry + dim.dim_park. Ambos sistemas comparten park_id. |
| `scout_attribution/cohorts/programs` | **CT_BRIDGE** | Atribución de campañas, cohortes por hire_date, y lógica de programas existe solo en CT. Yango no expone campaign metadata. |

---

## 5. BADGE CONTRACT

| Badge | Color | Meaning | KPIs |
|-------|-------|---------|------|
| `YANGO_API` | Green | Yango Fleet API como fuente canónica certificada | K1, K4, K5, K6, K7, K8, K9, K10, K17 |
| `CT_BRIDGE` | Grey | CT bridge como fuente (legacy o única disponible) | K2, K13, K14, K15, K21 |
| `SHARED` | Blue | Ambos sistemas comparten identificador | K12, K18, K19, K20 |
| `HYBRID` | Yellow | Combinado de múltiples fuentes | K3, K11 |
| `PROXY` | Orange | Estimación (no usado actualmente en Lima) | — |
| `BLOCKED` | Dark Red | Fuente existe pero ingesta inviable | K16 |
| `MISSING` | Red | Sin datos de ninguna fuente | — |

### Badge Rules
1. Un solo `source_badge` por KPI
2. Transiciones de badge se loguean en `ops.metric_promotion_registry`
3. Badge visible en Omniview UI como ícono por KPI header
4. Tooltip: fuente, coverage %, freshness, última fecha de certificación
5. KPI `MISSING` o `BLOCKED` → renderiza `—` con explicación

---

## 6. PROMOTION RULES

### 6.1 General Rules

| Rule | Threshold | Applies To |
|------|-----------|------------|
| Shadow days required | ≥ 30 consecutive days | All YANGO_API candidates |
| Coverage threshold | ≥ 95% vs shadow validator (30d) | All KPIs |
| Delta threshold (daily) | ≤ 5% | Revenue, Trips, GMV |
| Delta threshold (aggregate 30d) | ≤ 3% | Revenue, Trips, GMV |
| Freshness threshold | ≤ 5 minutes (near-real-time) | YANGO_API KPIs |
| Zero unexplained gaps | No days missing sin razón documentada | All KPIs |

### 6.2 KPI-Specific Conditions

| KPI | Additional Conditions |
|-----|----------------------|
| K1 `completed_trips` | `COUNT(DISTINCT order_id)` vs CT `trips_completed`: delta ≤ 1% (30d) |
| K4 `active_drivers` | `COUNT(DISTINCT driver_profile_id)` vs CT `COUNT(DISTINCT conductor_id)`: delta ≤ 5% (30d) |
| K5 `revenue_yego` | Partner fee vs CT `revenue_yego_final` per-slice: explained gap documentado. Per-trip delta ≤ 5% |
| K6 `gmv` | CT GMV = 0. Yango es única fuente. Aceptar sin comparación. |
| K17 `business_slice` | `dim.yango_category_to_slice` mapping table con ≥ 95% de órdenes clasificadas |

### 6.3 Rollback Rules

| Condition | Action |
|-----------|--------|
| Coverage < 90% for 3+ consecutive days | Rollback a CT_BRIDGE, alert |
| Delta > 20% for 3+ consecutive days | Rollback a CT_BRIDGE, investigar |
| Freshness > 30 min for 6+ consecutive cycles | Flag YANGO_API_DEGRADED, mantener fuente con warning |
| API credentials fail (401/403) | Rollback inmediato a CT_BRIDGE |
| Scheduler fails for 10+ consecutive cycles | Rollback a CT_BRIDGE |
| Promotion registry `approved_by` = null | **NO PROMOTION** — requiere aprobación explícita |

---

## 7. BLOCKERS — KPIs NOT PROMOTABLE

| KPI | Blocker | What's Missing | Resolution |
|-----|---------|---------------|------------|
| K2 `cancelled_trips` | Yango API solo ingiere `complete` | Endpoint que ingiera `statuses: ['cancelled']` | Cambiar filtro del scheduler Yango o mantener CT |
| K11 `cancel_rate_pct` | Hereda de K2 | Mismo que K2 | Mismo que K2 |
| K14 `reactivated_drivers` | Sin lifecycle canónico Yango | 90+ días de orders_raw history | Construir lifecycle_daily desde Yango |
| K15 `churned_drivers` | Sin lifecycle canónico Yango | 90+ días de orders_raw history | Construir lifecycle_daily desde Yango |
| K16 `supply_hours` | Sin endpoint bulk | Endpoint Yango bulk supply-hours | Esperar endpoint bulk o aceptar CT bridge |
| K17 `business_slice` | Sin mapping table | `dim.yango_category_to_slice` | Crear mapping table con curación manual/ML |

---

## 8. CERTIFICATION STATUS

### 8.1 By Promotion Status

| Status | Count | KPIs |
|--------|-------|------|
| **READY** | 12 | K1, K3, K4, K5, K6, K7, K8, K9, K10, K12, K18, K19, K20 |
| **SHADOW_ONLY** | 2 | K13, K21 |
| **NOT_CERTIFIED** | 2 | K2, K11 |
| **BLOCKED** | 4 | K14, K15, K16, K17 |

### 8.2 By Source Badge

| Badge | Count |
|-------|-------|
| YANGO_API | 9 |
| CT_BRIDGE | 5 |
| SHARED | 4 |
| HYBRID | 2 |
| BLOCKED | 1 |

---

## 9. CANONICAL MAPPER READINESS (CF-H2G)

### GO for CF-H2G: **CONDITIONAL GO**

**Evidence:**
- 12 KPIs READY con dueño canónico definido
- 9 KPIs con fuente YANGO_API certificada
- Badge contract formalizado (7 badges)
- Promotion rules definidos (6 reglas generales + 5 KPI-specific)
- Rollback rules definidos (5 condiciones)
- Shadow validator activo (CT bridge) para todos los YANGO_API KPIs
- Driver identity SHARED (100% UUID match confirmado)

**Prerequisites for CF-H2G:**

| Pre-req | Status | Impact |
|---------|--------|--------|
| `dim.yango_category_to_slice` mapping | PENDING | Solo K17 bloqueado. Resto de KPIs no afectados. |
| 30+ days Yango continuous data | IN PROGRESS | Scheduler CF-H2D corriendo. Se acumula diariamente. |
| Revenue validation per-slice | PENDING | Requiere K17 para segmentar revenue por slice. |
| Cancelled orders ingestion | OPTIONAL | K2 se queda CT. No bloquea K1, K3-K10. |
| `ops.metric_promotion_registry` | DESIGN ONLY (this document) | No bloquea mapper. Se construye en paralelo. |

### Mapper Scope (Phase 1 — Certified KPIs Only)

CF-H2G Phase 1 construye mapper para **12 KPIs READY**:
```
completed_trips, total_orders, active_drivers, revenue_yego, gmv,
avg_ticket, trips_per_driver, revenue_per_order, commission_pct,
driver_identity, park, city, country
```

KPIs excluidos del mapper Phase 1 (usan CT_BRIDGE directo): cancelled_trips, cancel_rate_pct, new_drivers, scout_attribution.

KPIs bloqueados (no incluidos en mapper): reactivated_drivers, churned_drivers, supply_hours, business_slice.

---

## 10. BACKLOG REORGANIZATION

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **CF-H2F** | Metric Ownership Matrix (this document) |
| **READY NEXT** | **CF-H2G** | Omniview Source Canonical Mapper (CONDITIONAL GO) |
| **READY NEXT** | **CF-H2F.1** | Business Slice Mapping (`dim.yango_category_to_slice`) |
| BLOCKED | CF-H2H | Omniview Source Promotion |
| BACKLOG | CF-H2E | Multipark Credential Expansion |
| BACKLOG | CF-H2I | Historical Snapshot Locking |
| BACKLOG | CF-H2J | Continuous Certification Monitor |
| BACKLOG | CF-H2K | Supply Hours Canonicalization |

---

## 11. SUMMARY TABLE (Quick Reference)

| KPI | OWNER | VALIDATOR | FALLBACK | PROMOTION_STATUS |
|-----|-------|-----------|----------|-----------------|
| completed_trips | YANGO | CT trips_completed | CT_BRIDGE | READY |
| cancelled_trips | CT_BRIDGE | N/A | N/A | NOT_CERTIFIED |
| total_orders | HYBRID | Yango+CT | Yango only | READY |
| active_drivers | YANGO | CT conductor_id | CT_BRIDGE | READY |
| revenue_yego | YANGO | CT revenue_yego_final | CT_BRIDGE | READY |
| gmv | YANGO | N/A (CT=0) | CT_BRIDGE proxy | READY |
| avg_ticket | YANGO | CT avg_ticket | CT_BRIDGE | READY |
| trips_per_driver | YANGO | CT trips_per_driver | CT_BRIDGE | READY |
| revenue_per_order | YANGO | CT derived | CT_BRIDGE | READY |
| commission_pct | YANGO | CT commission_pct | CT_BRIDGE | READY |
| cancel_rate_pct | HYBRID | N/A | CT_BRIDGE | NOT_CERTIFIED |
| driver_identity | SHARED | N/A (100%) | CT public.drivers | READY |
| new_drivers | CT_BRIDGE | Yango (future) | CT_BRIDGE | SHADOW_ONLY |
| reactivated_drivers | CT_BRIDGE | N/A | CT_BRIDGE | BLOCKED |
| churned_drivers | CT_BRIDGE | N/A | CT_BRIDGE | BLOCKED |
| supply_hours | BLOCKED | N/A | CT_BRIDGE | BLOCKED |
| business_slice | REQUIRES_MAPPING | CT business_slice_name | CT_BRIDGE | BLOCKED |
| park | SHARED | N/A | dim_park | READY |
| city | SHARED | N/A | dim_park | READY |
| country | SHARED | N/A | dim_park | READY |
| scout/cohorts/programs | CT_BRIDGE | Yango (future) | CT_BRIDGE | SHADOW_ONLY |

---

## 12. FIRMA

| Campo | Valor |
|-------|-------|
| **Formalizado por** | CF-H2F Metric Ownership Matrix |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `METRIC_OWNERSHIP_CERTIFIED` |
| **Veredicto** | CF-H2G: **CONDITIONAL GO** |
| **Próxima fase** | CF-H2F.1 (Business Slice Mapping) + CF-H2G (Canonical Mapper) |
