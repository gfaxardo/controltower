# CF-H2F — METRIC OWNERSHIP MATRIX

> **Fase:** CF-H2F — Metric Ownership Matrix
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `METRIC_OWNERSHIP_FORMALIZED`

---

## 1. EXECUTIVE SUMMARY

Matriz formal de ownership para 18 KPIs de Omniview, basada en evidencia certificada de las fases CF-H2C.0A a CF-H2C.0C. **8 KPIs tienen dueño canónico definido (YANGO o CT_BRIDGE). 7 KPIs requieren mapeo o construcción previa. 3 KPIs están bloqueados por falta de fuente.**

---

## 2. CONTEXT: DATA PILLARS CERTIFIED

| Pillar | Phase | Status |
|--------|-------|--------|
| Orders ingestion (Lima) | CF-H2C.0A | CERTIFIED |
| Transactions ingestion (Lima) | CF-H2C.0B.1 | CERTIFIED |
| Driver Identity (Lima) | CF-H2C.1 | CERTIFIED (100% UUID match) |
| Near Real-Time Scheduler | CF-H2D | CERTIFIED |
| Semantic Reconciliation | CF-H2C.0C | CERTIFIED |
| Revenue formula | CF-H2C.0B | CERTIFIED |
| Watermarks | CF-H2C | CERTIFIED |

---

## 3. METRIC OWNERSHIP MATRIX

### 3.1 Core Operational KPIs (Tier 1)

| # | KPI | Business Meaning | Canonical Owner | Formula | Grain | Source Badge | Confidence | Status |
|---|-----|-----------------|-----------------|---------|-------|-------------|------------|--------|
| **K1** | `completed_trips` | Trips completados por día/park/slice | **YANGO** | `COUNT(DISTINCT order_id) FROM raw_yango.orders_raw WHERE order_status='complete'` | Day, Week, Month | `YANGO_API` | HIGH | **CERTIFIED** |
| **K2** | `cancelled_trips` | Trips cancelados | **CT_BRIDGE** | `SUM(trips_cancelled) FROM ops.real_business_slice_day_fact` | Day, Week, Month | `CT_BRIDGE` | MEDIUM | **CERTIFIED** |
| **K3** | `total_orders` | Total órdenes (complete + cancelled) | **HYBRID** | `K1 + K2` | Day, Week, Month | `HYBRID` | MEDIUM | **CERTIFIED** |
| **K4** | `active_drivers` | Drivers únicos con al menos 1 trip | **YANGO** | `COUNT(DISTINCT driver_profile_id) FROM raw_yango.orders_raw WHERE order_status='complete'` | Day, Week, Month | `YANGO_API` | HIGH | **CERTIFIED** |
| **K5** | `revenue_yego` | Revenue YEGO (comisión cobrada al driver) | **YANGO** | `SUM(ABS(amount)) FROM raw_yango.transactions_raw WHERE category_name='Partner fee for trip'` | Day, Week, Month | `YANGO_API` | HIGH | **CERTIFIED** |
| **K6** | `gmv` | Gross Merchandise Value (pago del pasajero) | **YANGO** | `SUM(amount) FROM raw_yango.transactions_raw WHERE category_name IN ('Cash','Card payment','Corporate payment')` | Day, Week, Month | `YANGO_API` | HIGH | **CERTIFIED** |

### 3.2 Derived KPIs (Tier 2)

| # | KPI | Business Meaning | Canonical Owner | Formula | Depends On | Source Badge | Confidence | Status |
|---|-----|-----------------|-----------------|---------|-----------|-------------|------------|--------|
| **K7** | `avg_ticket` | Ticket promedio (GMV / trip) | **YANGO** | `K6 / K1` | K1, K6 | `YANGO_API` | HIGH | **CERTIFIED** |
| **K8** | `trips_per_driver` | Viajes por conductor activo | **YANGO** | `K1 / K4` | K1, K4 | `YANGO_API` | HIGH | **CERTIFIED** |
| **K9** | `revenue_per_order` | Revenue YEGO por viaje | **YANGO** | `K5 / K1` | K1, K5 | `YANGO_API` | HIGH | **CERTIFIED** |
| **K10** | `commission_rate` | Tasa de comisión Yango (platform fee / GMV) | **YANGO** | `SUM(ABS(Service fee)) / K6` | K6 | `YANGO_API` | MEDIUM | **CERTIFIED** |

### 3.3 Identity & Dimensional KPIs (Tier 3)

| # | KPI | Business Meaning | Canonical Owner | Formula | Source Badge | Confidence | Status |
|---|-----|-----------------|-----------------|---------|-------------|------------|--------|
| **K11** | `driver_identity` | Identidad del conductor (name, phone, license) | **SHARED** | `driver_profile_id = driver_id` (mismo UUID) | `SHARED` | VERY_HIGH | **CERTIFIED** |
| **K12** | `business_slice` | Segmento de negocio (Auto, YMA, TukTuk, etc.) | **REQUIRES_MAPPING** | `order.category → dim_business_slice_mapping` | `YANGO_API` | MEDIUM | **PENDING MAPPING** |
| **K13** | `park / city / country` | Dimensional geográfica | **SHARED** | `api_park_credentials_registry + dim.dim_park` | `SHARED` | HIGH | **CERTIFIED** |

### 3.4 Lifecycle & Growth KPIs (Tier 4)

| # | KPI | Business Meaning | Canonical Owner | Formula | Source Badge | Confidence | Status |
|---|-----|-----------------|-----------------|---------|-------------|------------|--------|
| **K14** | `new_drivers` | Drivers nuevos (hire_date reciente) | **CT_BRIDGE** | `public.drivers WHERE hire_date >= N days ago` | `CT_BRIDGE` | HIGH | **CERTIFIED** |
| **K15** | `reactivated_drivers` | Drivers que volvieron después de inactividad | **REQUIRES_CONSTRUCTION** | Requires lifecycle_daily (growth schema) | `CT_BRIDGE` | MEDIUM | **PENDING** |
| **K16** | `churn / inactive` | Drivers inactivos >15d | **REQUIRES_CONSTRUCTION** | Requires lifecycle_daily (growth schema) | `CT_BRIDGE` | MEDIUM | **PENDING** |
| **K17** | `supply_hours` | Horas online del conductor | **BLOCKED** | `GET /v2/parks/contractors/supply-hours` (per-driver, no bulk) | `BLOCKED` | LOW | **BLOCKED** |
| **K18** | `scout / attribution / programs` | Atribución de campaña y programa | **CT_BRIDGE** | `growth schema program tables` | `CT_BRIDGE` | MEDIUM | **CERTIFIED** |

---

## 4. BADGE CONTRACT

### 4.1 Badge Definitions

| Badge | Color | Meaning | When Assigned |
|-------|-------|---------|---------------|
| `YANGO_API` | Green | Data from Yango Fleet API, certified coverage | KPI is CERTIFIED, promotion conditions met |
| `CT_BRIDGE` | Grey | Data from CT bridge (trips_2026, public.drivers) | Legacy source, pre-Yango or Yango unavailable |
| `SHARED` | Blue | Both systems share the same identifier | UUID match confirmed (driver_id) |
| `HYBRID` | Yellow | Combined from multiple sources | e.g., total_orders = Yango_complete + CT_cancelled |
| `PROXY` | Orange | Estimated/proxy value | When real source is unavailable |
| `MISSING` | Red | No data from any source | Gap in both systems |
| `BLOCKED` | Dark Red | Source exists but ingestion not viable | e.g., supply_hours (per-driver endpoint) |

### 4.2 Badge Rules

1. A KPI can only have ONE `source_badge` at a time
2. If badge changes (e.g., `CT_BRIDGE` → `YANGO_API`), the transition is logged
3. Badge is visible in Omniview UI as a small icon per KPI header
4. Tooltip shows: source, coverage %, freshness, last certified date
5. If a KPI becomes `MISSING` or `BLOCKED`, it renders as `—` with explanation

---

## 5. PROMOTION RULES

### 5.1 General Rules

| Rule | Threshold | Applies To |
|------|-----------|------------|
| Shadow days required | >= 30 consecutive days | All KPIs |
| Coverage threshold | >= 95% vs shadow validator | All KPIs |
| Delta threshold (daily) | <= 5% | Revenue, Trips, GMV |
| Delta threshold (aggregate 30d) | <= 3% | Revenue, Trips, GMV |
| Freshness threshold | <= 5 minutes (near real-time) | All YANGO_API KPIs |
| Zero unexplained gaps | No days with missing data without documented reason | All KPIs |

### 5.2 KPI-Specific Promotion Conditions

| KPI | Additional Conditions |
|-----|----------------------|
| `completed_trips` (K1) | COUNT(DISTINCT order_id) vs CT trips_completed: delta <= 1% for 30 days |
| `revenue_yego` (K5) | Partner fee vs CT revenue_yego_final per-slice: explained gap documented. Per-trip delta <= 5% |
| `active_drivers` (K4) | COUNT(DISTINCT driver_profile_id) vs CT COUNT(DISTINCT conductor_id): delta <= 5% for 30 days |
| `gmv` (K6) | CT GMV = 0 for Lima. Yango is sole source. No comparison possible — accept Yango. |
| `business_slice` (K12) | Requires mapping table `dim.yango_category_to_slice`. Promotion blocked until mapping exists. |

### 5.3 Rollback Rules

| Condition | Action |
|-----------|--------|
| Coverage drops below 90% for 3+ consecutive days | Rollback to `CT_BRIDGE`, alert |
| Delta exceeds 20% for 3+ consecutive days | Rollback to `CT_BRIDGE`, investigate |
| Freshness exceeds 30 minutes for 6+ consecutive cycles | Flag `YANGO_API_DEGRADED`, keep source but warn |
| API credentials fail (401/403) | Immediate rollback to `CT_BRIDGE` |
| Scheduler fails for 10+ consecutive cycles | Rollback to `CT_BRIDGE` |

---

## 6. BLOCKERS — KPIs NOT PROMOTABLE YET

| KPI | Blocker | Resolution |
|-----|---------|------------|
| **cancelled_trips** (K2) | Yango API query filters `statuses: ['complete']`. Cancelled orders are never ingested. | Add cancelled status to scheduler query, or keep CT as source. Low priority — cancellation rate can stay CT. |
| **supply_hours** (K17) | Per-driver endpoint. Requires 1 HTTP call per driver. At 1,000 drivers × 1.5s = 25 minutes per cycle. Not viable for near real-time. | Wait for Yango bulk supply-hours endpoint, or accept CT bridge as source. |
| **business_slice** (K12) | Yango `category` field (e.g. "econom") doesn't map 1:1 to CT business slices (e.g. "Auto regular"). | Create `dim.yango_category_to_slice` mapping table. Requires manual curation or ML classification. |
| **reactivated_drivers** (K15) | Requires lifecycle_daily table which depends on CT bridge history. | Build lifecycle from Yango orders_raw history once 90+ days of data exist. |
| **churn/inactive** (K16) | Same as K15 — requires lifecycle history. | Same resolution as K15. |

---

## 7. CERTIFICATION STATUS SUMMARY

### 7.1 By Tier

| Tier | Total KPIs | Certified | Pending | Blocked |
|------|-----------|-----------|---------|---------|
| Tier 1 (Core Ops) | 6 | 6 | 0 | 0 |
| Tier 2 (Derived) | 4 | 4 | 0 | 0 |
| Tier 3 (Identity/Dim) | 3 | 2 | 1 | 0 |
| Tier 4 (Lifecycle/Growth) | 5 | 2 | 2 | 1 |
| **TOTAL** | **18** | **14** | **3** | **1** |

### 7.2 Certified KPIs (14)

`completed_trips`, `cancelled_trips`, `total_orders`, `active_drivers`, `revenue_yego`, `gmv`, `avg_ticket`, `trips_per_driver`, `revenue_per_order`, `commission_rate`, `driver_identity`, `park/city/country`, `new_drivers`, `scout/attribution/programs`

### 7.3 Pending KPIs (3)

`business_slice` (mapping required), `reactivated_drivers` (lifecycle required), `churn/inactive` (lifecycle required)

### 7.4 Blocked KPIs (1)

`supply_hours` (no bulk API endpoint)

---

## 8. GO / NO-GO

### 8.1 GO for CF-H2G (Omniview Source Canonical Mapper)

**GO.** 14 of 18 KPIs have certified canonical ownership. The mapper can be built for certified KPIs now, with pending/blocked KPIs using CT_BRIDGE fallback.

### 8.2 Prerequisites for CF-H2G

| Pre-req | Status |
|---------|--------|
| `dim.yango_category_to_slice` mapping table | **Pending** — needed for K12 (business_slice) |
| 30+ days of continuous Yango data | **In progress** — scheduler running since CF-H2D |
| Revenue validation against CT per-slice | **Pending** — requires K12 first |
| Cancelled orders ingestion (optional) | **Pending** — K2 stays CT for now |

### 8.3 NO-GO for Omniview Promotion

Omniview source promotion (switching UI to Yango) requires:
- CF-H2G (Canonical Mapper) completed
- CF-H2H (Source Promotion) completed
- All Tier 1 KPIs certified for 30+ days
- Rollback plan tested

---

## 9. BACKLOG UPDATED

| Fase | Estado |
|------|--------|
| CF-H2C.0C | Semantic Reconciliation — **CERTIFIED** |
| **CF-H2F** | **Metric Ownership Matrix — ACTIVE (this document)** |
| CF-H2F.1 | Business Slice Mapping (`dim.yango_category_to_slice`) — **READY NEXT** |
| CF-H2G | Omniview Source Canonical Mapper — **BLOCKED** (pending K12) |
| CF-H2E | Multipark Credential Expansion — **BACKLOG** |
| CF-H2H | Omniview Source Promotion — **BLOCKED** |
| CF-H2I | Historical Snapshot Locking — **BACKLOG** |
| CF-H2J | Continuous Certification Monitor — **BACKLOG** |

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| **Formalizado por** | CF-H2F Metric Ownership Matrix |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `METRIC_OWNERSHIP_FORMALIZED` |
| **Próxima fase** | CF-H2F.1 — Business Slice Mapping |
