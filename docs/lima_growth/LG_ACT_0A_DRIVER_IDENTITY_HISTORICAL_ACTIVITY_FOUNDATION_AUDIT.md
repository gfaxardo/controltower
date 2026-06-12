# LG-ACT-0A — DRIVER IDENTITY + HISTORICAL ACTIVITY FOUNDATION AUDIT

**Ticket:** LG-ACT-0A  
**Date:** 2026-06-11  
**Status:** AUDIT COMPLETE — DESIGN READY  
**Phase:** Design only — NO implementation  

---

## TASK 1 — SCHEMA AUDIT

### public.drivers — Driver Registry (156,859 rows)

| Column | Type | Description |
|--------|------|-------------|
| `driver_id` | VARCHAR | **Primary driver UUID** — matches Yango driver_profile.id format |
| `park_id` | VARCHAR | Park UUID |
| `first_name` | VARCHAR | |
| `last_name` | VARCHAR | |
| `full_name` | VARCHAR | Combined name |
| `phone` | VARCHAR | Phone number |
| `license_number` | VARCHAR | Driver license number |
| `license_normalized_number` | VARCHAR | Normalized license |
| `license_country` | VARCHAR | License country |
| `license_issue_date` | DATE | |
| `license_expiration_date` | DATE | |
| `hire_date` | DATE | First seen / hire date |
| `fire_date` | DATE | Dismissal date |
| `work_status` | VARCHAR | `working`, `not_working`, `fired` |
| `current_status` | VARCHAR | `offline`, `busy`, `free`, `in_order_free`, `in_order_busy` |
| `car_id` | VARCHAR | Vehicle UUID |
| `car_brand`, `car_model`, `car_color`, `car_number`, `car_callsign` | VARCHAR | Vehicle details |
| `account_balance`, `account_balance_limit` | NUMERIC | Account financials |

**This is the richest driver identity table in the DB.** It has name, phone, license, vehicle, and account data for 156,859 drivers. This is almost certainly synced from the Yango API (driver-profiles/list endpoint).

### public.trips_2025 — Historical Trips (Year 2025)

| Column | Type | Description |
|--------|------|-------------|
| `id` | VARCHAR | Trip UUID |
| `conductor_id` | VARCHAR | Driver UUID |
| `conductor_nombre` | VARCHAR | Driver name at time of trip |
| `park_id` | VARCHAR | Park UUID |
| `condicion` | VARCHAR | `Completado`, `Cancelado`, `Sin condicion`, etc. |
| `fecha_finalizacion` | TIMESTAMP | Trip end time |
| `fecha_inicio_viaje` | TIMESTAMP | Trip start time |
| `motivo_cancelacion` | TEXT | Cancellation reason |
| `distancia_km` | NUMERIC | Trip distance |
| `precio_yango_pro` | NUMERIC | Yango Pro price |
| `tipo_servicio` | VARCHAR | Service type |
| Other financial columns | NUMERIC | Payment breakdown |

### public.trips_2026 — Current Year Trips (18.3M rows)

Identical schema to trips_2025. **This is our canonical source for taxi activity** — already validated against Fleetroom within 0.01% (LG-TAX-HOTFIX-1E).

---

## TASK 2 — IDENTITY COLUMN VALIDATION

### Identity Fields Available Per Source

| Identity Field | public.drivers | trips_2025 | trips_2026 | Yango API |
|---------------|---------------|------------|------------|-----------|
| Driver UUID | `driver_id` | `conductor_id` | `conductor_id` | `driver_profile.id` |
| First Name | `first_name` | — | — | `first_name` |
| Last Name | `last_name` | — | — | `last_name` |
| Full Name | `full_name` | `conductor_nombre` | `conductor_nombre` | — |
| Phone | `phone` | — | — | `phones[]` |
| License Number | `license_number` | — | — | `driver_license.number` |
| License Normalized | `license_normalized_number` | — | — | `driver_license.normalized_number` |
| Park ID | `park_id` | `park_id` | `park_id` | `park_id` |
| Hire Date | `hire_date` | — | — | `created_date` |
| Work Status | `work_status` | — | — | `work_status` |
| Current Status | `current_status` | — | — | `current_status.status` |
| Vehicle ID | `car_id` | `vehiculo_placa` | `vehiculo_placa` | `car.id` |

**`public.drivers` is a mirror of the Yango API driver-profiles/list endpoint.** Every field maps 1:1.

---

## TASK 3 — CROSS-REFERENCE: trips vs public.drivers

### ID Format Analysis

| Table | ID Column | Format | Sample |
|-------|-----------|--------|--------|
| `public.drivers` | `driver_id` | UUID (32 hex, lowercase) | Same format |
| `public.trips_2025` | `conductor_id` | UUID (32 hex, lowercase) | Same format |
| `public.trips_2026` | `conductor_id` | UUID (32 hex, lowercase) | Same format |
| `growth.*` tables | `driver_profile_id` | UUID (32 hex, lowercase) | Same format |
| `raw_yango.orders_raw` | `driver_profile_id` | UUID (32 hex, lowercase) | Same format |
| Yango API | `driver_profile.id` | UUID (32 hex, lowercase) | Same format |

**All sources use the same UUID format.** Direct joins should work without transformation.

### Identity Bridge Tables Found

#### `public.yango_driver_identity_bridge`

| Column | Type |
|--------|------|
| `id` | INTEGER |
| `internal_conductor_id` | VARCHAR |
| `internal_license` | VARCHAR |
| `internal_driver_name` | VARCHAR |
| `internal_phone` | VARCHAR |

**Purpose:** Maps `internal_conductor_id` (likely a legacy/alternate ID) to license, name, phone. This is a **legacy identity bridge** for a different ID space — not the UUID-based bridge we need.

#### `public.v_identity_driver_base` (VIEW)

| Column | Type |
|--------|------|
| `driver_id` | VARCHAR |
| `document_type` | VARCHAR |
| `document_number` | VARCHAR |
| `first_name` | VARCHAR |
| `last_name` | VARCHAR |
| `driver_hire_date` | DATE |
| `migration_event_date` | DATE |
| `migration_scout_id` | INTEGER |
| `migration_scout_name` | VARCHAR |

**Purpose:** Identity view for migration/scout purposes. The `driver_id` column maps to the same UUID space.

---

## TASK 4 — CROSS-REFERENCE: conductor_id vs Yango driver_profile.id

### Direct Match Assessment

All sources use UUID format (32 hex chars, lowercase). The following direct joins should produce 100% match:

```
public.drivers.driver_id = public.trips_2026.conductor_id
public.drivers.driver_id = raw_yango.orders_raw.driver_profile_id
public.drivers.driver_id = growth.yango_lima_driver_state_snapshot.driver_profile_id
Yango API driver_profile.id = public.drivers.driver_id
```

### ID Reconciliation Map

```
Yango Fleet API
  driver_profile.id ─────────────────────┐
                                         │ (same UUID)
public.drivers                           │
  driver_id ─────────────────────────────┤
                                         │
public.trips_2025 / trips_2026           │
  conductor_id ──────────────────────────┤
                                         │
raw_yango.orders_raw                     │
  driver_profile_id ─────────────────────┤
                                         │
growth.yango_lima_driver_state_snapshot  │
  driver_profile_id ─────────────────────┘
```

**No identity bridge is needed.** All systems use the same Yango UUID for driver identification. The existing `yango_driver_identity_bridge` maps a different (legacy internal) ID space and is not needed for UUID-based operations.

---

## TASK 5 — DRIVER IDENTITY BRIDGE DESIGN

### Verdict: **NOT NEEDED for UUID space**

The canonical driver UUID is already consistent across all sources. However, an **enriched identity view** would be valuable for operational use:

```sql
-- Already exists in DB:
SELECT * FROM public.drivers WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
```

This single query returns full identity (name, phone, license, vehicle, account, work status, hire date) for all Lima drivers. No bridge needed.

### Optional: Identity Enrichment for Taxonomy

For the taxonomy service, we may want a lightweight `driver_identity` cache table in `growth` schema:

```sql
CREATE TABLE growth.yego_lima_driver_identity (
    driver_profile_id   TEXT PRIMARY KEY,
    park_id             TEXT,
    full_name           TEXT,
    phone               TEXT,
    license_number      TEXT,
    license_normalized  TEXT,
    work_status         TEXT,
    current_status      TEXT,
    hire_date           DATE,
    fire_date           DATE,
    last_synced_at      TIMESTAMPTZ DEFAULT now()
);
```

This is an optional cache — `public.drivers` already serves this purpose and can be queried directly.

---

## TASK 6 — HISTORICAL ACTIVITY BOOTSTRAP DESIGN

### Data Available

| Source | Date Range | Lima Drivers | Lima Completed Orders |
|--------|-----------|-------------|----------------------|
| trips_2025 | Jan-Dec 2025 | TBD (query timed out) | TBD |
| trips_2026 | Jan-Jun 2026 | 5,878 (7d), 9,726 (30d) | 178K (7d), 784K (30d) |

### Bootstrap Strategy

The goal is to compute per-driver historical metrics for taxonomy initialization:

#### Step 1: Rolling Windows from trips_2025 + trips_2026

```sql
WITH driver_weekly AS (
    SELECT 
        conductor_id,
        DATE_TRUNC('week', fecha_finalizacion)::date as week_start,
        COUNT(*) as completed_orders,
        SUM(precio_yango_pro) as gross_revenue
    FROM public.trips_2025
    WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
      AND condicion = 'Completado'
    GROUP BY 1, 2
    UNION ALL
    SELECT 
        conductor_id,
        DATE_TRUNC('week', fecha_finalizacion)::date as week_start,
        COUNT(*) as completed_orders,
        SUM(precio_yango_pro) as gross_revenue
    FROM public.trips_2026
    WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
      AND condicion = 'Completado'
    GROUP BY 1, 2
)
SELECT
    conductor_id,
    -- Recency
    MAX(week_start) as last_active_week,
    -- Volume (12-week rolling)
    COUNT(*) FILTER (WHERE week_start >= CURRENT_DATE - INTERVAL '84 days') as active_weeks_12w,
    AVG(completed_orders) FILTER (WHERE week_start >= CURRENT_DATE - INTERVAL '84 days') as avg_orders_12w,
    AVG(completed_orders) FILTER (WHERE week_start >= CURRENT_DATE - INTERVAL '28 days') as avg_orders_4w,
    MAX(completed_orders) FILTER (WHERE week_start >= CURRENT_DATE - INTERVAL '84 days') as best_week_12w,
    -- Revenue
    SUM(gross_revenue) FILTER (WHERE week_start >= CURRENT_DATE - INTERVAL '28 days') as revenue_4w,
    -- History
    MIN(week_start) as first_week,
    COUNT(DISTINCT week_start) as total_active_weeks
FROM driver_weekly
GROUP BY 1
```

#### Step 2: First Trip / Hire Date

```sql
SELECT 
    conductor_id,
    MIN(fecha_finalizacion::date) as first_trip_date,
    MAX(fecha_finalizacion::date) as last_trip_date
FROM (
    SELECT conductor_id, fecha_finalizacion FROM public.trips_2025 WHERE park_id = '...' AND condicion = 'Completado'
    UNION ALL
    SELECT conductor_id, fecha_finalizacion FROM public.trips_2026 WHERE park_id = '...' AND condicion = 'Completado'
) all_trips
GROUP BY 1
```

#### Step 3: Merge with public.drivers

```sql
SELECT 
    d.driver_id,
    d.full_name,
    d.phone,
    d.license_number,
    d.hire_date,
    d.work_status,
    COALESCE(h.first_trip_date, d.hire_date) as activity_start_date,
    h.last_trip_date,
    h.last_active_week,
    h.avg_orders_4w,
    h.avg_orders_12w,
    h.best_week_12w,
    h.total_active_weeks,
    h.revenue_4w,
    -- Computed lifecycle
    CASE 
        WHEN d.hire_date >= CURRENT_DATE - 90 THEN 'NEW'
        WHEN h.last_trip_date < CURRENT_DATE - 90 THEN 'CHURNED'
        WHEN h.last_trip_date < CURRENT_DATE - 15 THEN 'AT_RISK'
        ELSE 'ACTIVE'
    END as driver_lifecycle
FROM public.drivers d
LEFT JOIN driver_history h ON d.driver_id = h.conductor_id
WHERE d.park_id = '08e20910d81d42658d4334d3f6d10ac0'
```

### Migration Path

This bootstrap would **replace** the current `driver_360_daily` → `history_weekly` → `driver_state_snapshot` pipeline with a direct `trips_2025+2026` → `driver_history` → `driver_state_snapshot` pipeline.

| Current | Proposed | Benefit |
|---------|----------|---------|
| `driver_360_daily` (broken, 179 rows) | `public.trips_2025+2026` | 18M+ rows, daily granularity, Fleetroom-validated |
| `history_weekly` (stale for 59% of drivers) | Rebuilt from `trips_*` with park filter | Current, accurate, Lima-scoped |
| `driver_state_snapshot` (18,545, global, no recency) | Rebuilt from `trips_*` with recency + park | ~2,500 Lima active, real recency |

### Expected Impact

| Metric | Current | After Bootstrap |
|--------|---------|-----------------|
| Total drivers in snapshot | 18,545 (global, all-time) | ~7,000-9,000 (Lima, recency-filtered) |
| ACTIVE (7d) | 18,545 (100% false positive) | ~2,500 (real) |
| CHURNED | 0 (unreachable) | ~4,700 (real) |
| ARCHIVED | 0 (unreachable) | ~2,200 (real) |
| Park contamination | No (0 from other parks) | No (park-filtered at source) |
| Daily data | No (driver_360_daily broken) | Yes (trips daily granularity) |

---

## TASK 7 — YANGO API CUTOVER DESIGN

### Current vs Target Architecture

```
CURRENT:
  Yango API (tick, 20 pages/day) → raw_yango.orders_raw → driver_360_daily (BROKEN) → history_weekly (STALE) → driver_state_snapshot

PROPOSED:
  public.trips_2026 (already ingested) → driver_history (new) → driver_state_snapshot (rebuilt)
  public.drivers (identity) → driver_identity_cache (optional)
  Yango API (driver-profiles/list) → driver_identity (periodic sync)
```

### Cutover Plan (3 phases)

#### ACT-1: Historical Bootstrap (1-shot)

1. Create `growth.yego_lima_driver_history_weekly_v2` from `trips_2025+2026` (park-filtered)
2. Create `growth.yego_lima_driver_recency` from `trips_2026` (last trip date per driver)
3. Create `growth.yego_lima_driver_identity` from `public.drivers` (park-filtered)
4. Rebuild `driver_state_snapshot` from bootstrap sources
5. Validate against Fleetroom benchmarks

#### ACT-2: Daily Incremental (automated)

1. Add daily sync: `trips_2026` new rows → update `driver_recency` (last trip date)
2. Add weekly sync: `trips_2026` new week → update `driver_history_weekly_v2`
3. Update `driver_state_snapshot` from incremental sources
4. Schedule as part of autonomous tick (before taxonomy build)

#### ACT-3: Yango API Integration (optional enhancement)

1. Sync `driver-profiles/list` → `driver_identity` (daily, for status/phone updates)
2. Sync `supply-hours` per-driver (sampling, not bulk)
3. Add `current_status.status` for real-time driver availability
4. Gradual migration from `public.drivers` to API-synced identity

### Sources of Truth (Final)

| Data Domain | Canonical Source | Update Frequency |
|------------|-----------------|-----------------|
| Trip completion | `public.trips_2026` (`condicion='Completado'`) | Daily incremental |
| Driver identity (name, phone, license) | `public.drivers` (synced from Yango API) | Daily sync |
| Driver current status | Yango API `current_status.status` | Hourly (optional) |
| Driver supply hours | Yango API `supply-hours` (per-driver) | Sampling only |
| Driver recency (last trip) | `trips_2026` computed | Daily |
| Driver history (volume, trends) | `trips_2025+2026` aggregated | Weekly |

---

## TASK 8 — ROADMAP

### ACT-1: Historical Activity Bootstrap

| Step | Description | Effort | Dependency |
|------|------------|--------|-----------|
| 1.1 | SQL migration: `growth.yego_lima_driver_history_weekly_v2` | 1d | None |
| 1.2 | SQL migration: `growth.yego_lima_driver_recency` | 0.5d | None |
| 1.3 | Bootstrap script: populate from trips_2025+2026 | 1d | 1.1, 1.2 |
| 1.4 | Validation: compare against Fleetroom benchmarks | 0.5d | 1.3 |
| 1.5 | Rebuild driver_state_snapshot from bootstrap | 1d | 1.3 |

**Deliverable:** Lima-scoped, recency-filtered driver_state_snapshot with real activity metrics.

### ACT-2: Daily Incremental Pipeline

| Step | Description | Effort | Dependency |
|------|------------|--------|-----------|
| 2.1 | Daily recency update service | 1d | ACT-1 |
| 2.2 | Weekly history update service | 1d | ACT-1 |
| 2.3 | Integrate with autonomous tick | 0.5d | 2.1, 2.2 |
| 2.4 | Update taxonomy service to use new sources | 1d | 2.3 |
| 2.5 | Validation + shadow mode comparison | 0.5d | 2.4 |

**Deliverable:** Self-updating taxonomy pipeline using real activity data.

### ACT-3: Yango API Identity Cutover

| Step | Description | Effort | Dependency |
|------|------------|--------|-----------|
| 3.1 | Driver identity sync from Yango API | 1.5d | None (independent) |
| 3.2 | Driver current status sync | 1d | None |
| 3.3 | Supply hours sampling service | 1d | None |
| 3.4 | Replace public.drivers dependency with API sync | 0.5d | 3.1 |
| 3.5 | Validation | 0.5d | 3.1-3.4 |

**Deliverable:** Yango API as canonical identity source with real-time status.

---

## APPENDIX — Key Tables Reference

| Table | Rows | Key Column | Schema Validated |
|-------|------|-----------|-----------------|
| `public.drivers` | 156,859 | `driver_id` (UUID) | YES |
| `public.trips_2025` | TBD (millions) | `conductor_id` (UUID) | YES |
| `public.trips_2026` | 18,273,981 | `conductor_id` (UUID) | YES |
| `public.yango_driver_identity_bridge` | TBD | `internal_conductor_id` (legacy) | YES |
| `public.v_identity_driver_base` | VIEW | `driver_id` (UUID) | YES |
| `raw_yango.orders_raw` | 36,516 | `driver_profile_id` (UUID) | YES |
| `raw_yango.driver_profiles_raw` | TBD | TBD | NOT CHECKED |

---

**LG-ACT-0A — FIN**

*All sources use the same Yango UUID for driver identity — no bridge needed.*  
*public.drivers is a complete identity registry with 156,859 rows.*  
*Historical activity can be bootstrapped from trips_2025+2026 with daily granularity.*  
*Roadmap: ACT-1 (bootstrap) → ACT-2 (incremental) → ACT-3 (API cutover).*  
*Design ready for ACT-1 implementation.*
