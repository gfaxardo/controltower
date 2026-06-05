# LOYALTY SUB-50 INVENTORY — YEGO CONTROL TOWER

**Motor:** Control Foundation — Fase 2B Audit  
**Fecha:** 2026-06-02  
**Modo:** Auditoria exhaustiva — No implementar, no corregir  

---

## 1. LINEAGE COMPLETO

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  SOURCE LAYER                                                                │
│                                                                              │
│  [A] Yango Fleet API (external)                                              │
│      → POST /yego-lima-growth/lab/capture-orders-range                       │
│      → list_completed_orders(from_dt, to_dt, cursor)                         │
│      → Paginated cursor, park_id = settings.YANGO_LIMA_PARK_ID               │
│      → Persisted via upsert_raw_orders()                                     │
│      ↓                                                                       │
│  growth.yango_lima_orders_raw          (raw orders, upsert by order_id)       │
│      Columns: order_id, driver_profile_id, created_at, ended_at,             │
│               status, category, price, mileage, ...                          │
│                                                                              │
│  [B] ops.driver_daily_activity_fact    (Driver360 — daily driver metrics)    │
│      Columns: driver_id, activity_date, completed_trips, ...                 │
│      Populated by: driver serving facts build / refresh                      │
│      Used by: driver_serving_facts_build.sql (weekly segment, migration,      │
│               operational priority MVs)                                      │
│                                                                              │
├── FACT LAYER ───────────────────────────────────────────────────────────────┤
│                                                                              │
│  growth.yango_lima_loyalty_sub50_weekly                                      │
│      Created by: alembic/versions/162_yego_lima_loyalty_sub50_weekly.py      │
│      Populated by: yego_lima_loyalty_sub50_service.py:build_loyalty_sub50()  │
│      Columns:                                                                 │
│        week_start_date, week_end_date, driver_profile_id,                    │
│        completed_orders_week     ← SUM(completed_trips) FROM driver_daily     │
│        supply_hours_week         ← SUM(EXTRACT(EPOCH...)/3600) FROM raw     │
│        trips_per_supply_hour_week ← computed: completed/supply               │
│        productivity_band         ← LOW/MEDIUM/HIGH (settings-configurable)   │
│        driver_state              ← NULL (placeholder — never populated)      │
│        segment                   ← SUB50_40_49 ... SUB50_00_09               │
│        distance_to_50            ← max(0, 50 - completed)                    │
│        growth_priority           ← 1-5 (lower = closer to 50)                │
│        last_calculated_at, source = 'loyalty_sub50'                          │
│                                                                              │
│  Driver Segment MVs (ops schema) — for operational priority context          │
│      ops.driver_weekly_segment_fact                                          │
│      ops.driver_segment_migration_fact                                       │
│      ops.driver_operational_priority_fact                                    │
│      ops.driver_supply_overview_weekly_fact                                  │
│                                                                              │
├── SERVICE LAYER ────────────────────────────────────────────────────────────┤
│                                                                              │
│  yego_lima_loyalty_sub50_service.py                                          │
│      build_loyalty_sub50(week_start_date_str)                                │
│          → Read lima drivers from growth.yango_lima_orders_raw               │
│          → Read completed_trips from ops.driver_daily_activity_fact          │
│          → Read supply_hours from growth.yango_lima_orders_raw               │
│          → Compute segment, distance_to_50, productivity_band                │
│          → UPSERT into growth.yango_lima_loyalty_sub50_weekly                │
│      get_sub50_summary(week_start_date_str)                                  │
│          → Read from growth.yango_lima_loyalty_sub50_weekly                  │
│      get_top_opportunities(week_start_date_str, limit)                       │
│          → Read top drivers by growth_priority, mask driver_id               │
│      get_supply_opportunities(week_start_date_str, limit)                    │
│          → Read drivers with above-avg supply, below-avg orders              │
│                                                                              │
│  yego_lima_growth_capture_service.py                                         │
│      capture_orders_range(from_str, to_str, max_pages)                       │
│          → Validate range, paginate via Yango Fleet API                      │
│          → Upsert raw orders via repository                                  │
│                                                                              │
│  yego_lima_growth_repository.py                                              │
│      upsert_raw_orders(orders) → growth.yango_lima_orders_raw                │
│      get_raw_orders_summary()                                                │
│      get_recent_raw_orders(limit)                                            │
│                                                                              │
│  driver_operational_priority_service.py                                      │
│      _get_recoverability(from_seg, to_seg, movement_type)                    │
│          → Deterministic recoverability band (HIGH/MEDIUM/LOW)               │
│          → Based on segment migration, NOT sub50-specific                    │
│                                                                              │
│  recoverability_intelligence_service.py                                      │
│      → Shadow mode recoverability scoring (0-100)                            │
│      → 5 weighted components + modifiers                                     │
│      → Source: ops.driver_trip_behavior_daily_fact                           │
│      → NOT integrated with Sub50                                             │
│                                                                              │
├── ROUTER LAYER ─────────────────────────────────────────────────────────────┤
│                                                                              │
│  /yego-lima-growth/lab/*          (yego_lima_growth_lab.py)                  │
│      POST /build-loyalty-sub50                                               │
│      GET  /loyalty-sub50-summary                                             │
│      GET  /loyalty-sub50-top-opportunities                                   │
│      GET  /loyalty-sub50-supply-opportunities                                │
│      POST /capture-orders-range                                              │
│      GET  /raw-orders-summary                                                │
│      GET  /recent-raw-orders                                                 │
│                                                                              │
│  /recoverability/*                (recoverability_intelligence.py)            │
│      GET /summary, /top-recoverable, /distribution,                          │
│      GET /driver/{id}, /shadow-priority, /segments,                          │
│      GET /explainability/{id}, /risk-distribution                            │
│                                                                              │
│  /yango-loyalty/*                 (yango_loyalty.py)                          │
│      GET /summary, /kpis, /reachability, /rules                              │
│      POST /manual-kpi, /target, /batch-targets                               │
│      GET /bootstrap, /performance, /history, /city-comparison                │
│      GET /definitions/*, /operational-flow                                   │
│                                                                              │
├── FRONTEND (NONE for Sub50) ────────────────────────────────────────────────┤
│                                                                              │
│  NO frontend components exist for Loyalty Sub-50.                            │
│  NO UI routes registered in controlTowerNavigationRegistry.js.               │
│  NO api.js functions for sub50 endpoints.                                    │
│  The feature is backend-only (Fase 2B Lab).                                 │
│                                                                              │
│  Existing related frontend:                                                   │
│      YangoLoyaltyView.jsx → /yango-loyalty/* (Oro/Plata loyalty program)    │
│      RecoverabilityIntelligenceDashboard.jsx → /recoverability/* (shadow)    │
│      OperationalPriorities.jsx → /drivers/movements/actionable               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. INVENTARIO COMPLETO DE OBJETOS

### 2.1 Endpoints Involucrados

| Endpoint | Router | Service | Fase |
|----------|--------|---------|------|
| `POST /yego-lima-growth/lab/build-loyalty-sub50` | `yego_lima_growth_lab.py` | `yego_lima_loyalty_sub50_service.py:build_loyalty_sub50()` | 2B |
| `GET /yego-lima-growth/lab/loyalty-sub50-summary` | `yego_lima_growth_lab.py` | `yego_lima_loyalty_sub50_service.py:get_sub50_summary()` | 2B |
| `GET /yego-lima-growth/lab/loyalty-sub50-top-opportunities` | `yego_lima_growth_lab.py` | `yego_lima_loyalty_sub50_service.py:get_top_opportunities()` | 2B |
| `GET /yego-lima-growth/lab/loyalty-sub50-supply-opportunities` | `yego_lima_growth_lab.py` | `yego_lima_loyalty_sub50_service.py:get_supply_opportunities()` | 2B |
| `POST /yego-lima-growth/lab/capture-orders-range` | `yego_lima_growth_lab.py` | `yego_lima_growth_capture_service.py:capture_orders_range()` | 1 |
| `GET /yego-lima-growth/lab/raw-orders-summary` | `yego_lima_growth_lab.py` | `yego_lima_growth_repository.py:get_raw_orders_summary()` | 1 |
| `GET /yego-lima-growth/lab/recent-raw-orders` | `yego_lima_growth_lab.py` | `yego_lima_growth_repository.py:get_recent_raw_orders()` | 1 |

### 2.2 Routers

| Router | Archivo | Prefijo |
|--------|---------|---------|
| `yego_lima_growth_lab` | `backend/app/routers/yego_lima_growth_lab.py` | `/yego-lima-growth/lab` |
| `recoverability_intelligence` | `backend/app/routers/recoverability_intelligence.py` | `/recoverability` |
| `yango_loyalty` | `backend/app/routers/yango_loyalty.py` | `/yango-loyalty` |
| `yango_loyalty_reachability` | `backend/app/routers/yango_loyalty_reachability.py` | `/yango-loyalty` |

### 2.3 Services

| Service | Archivo | Responsabilidad |
|---------|---------|----------------|
| **Loyalty Sub50 Engine** | `backend/app/services/yego_lima_loyalty_sub50_service.py` | Build + read sub50 cohorts |
| Growth Capture | `backend/app/services/yego_lima_growth_capture_service.py` | Yango API order ingestion |
| Growth Repository | `backend/app/repositories/yego_lima_growth_repository.py` | Raw orders CRUD |
| Yango Loyalty | `backend/app/services/yango_loyalty_service.py` | Yango Loyalty Oro/Plata program |
| Loyalty Performance | `backend/app/services/yango_loyalty_performance_service.py` | Lima-only performance KPI tracking |
| Loyalty Definition | `backend/app/services/yango_loyalty_definition_service.py` | Metric definition previews |
| Recoverability Intel | `backend/app/services/recoverability_intelligence_service.py` | Shadow mode recoverability scoring |
| Driver Op Priority | `backend/app/services/driver_operational_priority_service.py` | Driver operational queue assignment |

### 2.4 Materialized Views / Serving Facts

| Object | Schema | Grain | Tipo |
|--------|--------|-------|------|
| `growth.yango_lima_loyalty_sub50_weekly` | growth | weekly | Table (target) |
| `ops.driver_daily_activity_fact` | ops | daily | Fact (source) |
| `ops.driver_weekly_segment_fact` | ops | weekly | MV |
| `ops.driver_segment_migration_fact` | ops | weekly | MV |
| `ops.driver_operational_priority_fact` | ops | weekly | MV |
| `ops.driver_supply_overview_weekly_fact` | ops | weekly | MV |
| `ops.driver_trip_behavior_daily_fact` | ops | daily | Fact (recoverability) |
| `ops.mv_yango_loyalty_performance_monthly_v1` | ops | monthly | MV (loyalty performance) |
| `ops.fct_yego_operational_flow_monthly_v2` | ops | monthly | Fact (N+R operational flow) |

### 2.5 Tablas Fuente

| Tabla | Schema | Rol |
|-------|--------|-----|
| `yango_lima_orders_raw` | growth | Raw orders from Yango Fleet API |
| `yango_lima_loyalty_sub50_weekly` | growth | Persisted sub50 classification |
| `driver_daily_activity_fact` | ops | Driver daily metrics (completed_trips) |
| `driver_trip_behavior_daily_fact` | ops | Trip behavior (recoverability source) |
| `module_ct_fleet_summary_daily` | public | Fleet daily summary (SH source for loyalty performance) |
| `trips_2026` / `trips_2025` | public | Raw trip data |
| `drivers` | public | Driver identity master |
| `dim_park` | dim | Park dimension |
| `dim_business_slice_mapping` | dim | Business slice mapping |
| `yango_loyalty_targets` | ops | Loyalty KPI targets |
| `yango_loyalty_kpi_manual` | ops | Manual KPI values |
| `yango_loyalty_monthly_goals` | ops | Monthly goals |
| `yango_loyalty_kpi_registry` | ops | KPI catalog |
| `yango_loyalty_source_registry` | ops | Data source registry |
| `yango_loyalty_metric_definition_sets` | ops | Definition sets |
| `yango_loyalty_metric_rules` | ops | Per-metric rules |
| `yango_loyalty_official_reconciliation_reference` | ops | Yango official reference values |

### 2.6 Screenshots / State

| Aspect | Status |
|--------|--------|
| Frontend UI para Sub50 | **NO EXISTE** — backend solo |
| Autenticacion | Sin auth en growth lab endpoints |
| Rate limiting | Solo Yango API client (no app-level) |
| Logging | logger.info/warning en sub50 service |
| Error handling | Basic try/except; _empty_summary() fallback |

---

## 3. NOTAS SOBRE EL INVENTARIO

1. **Loyalty Sub-50 NO tiene UI.** Los 4 endpoints estan expuestos como API Lab pero no estan registrados en `controlTowerNavigationRegistry.js` ni en `operationalMaturityRegistry.js`. No hay componente React que los consuma.

2. **No hay scheduling.** `build_loyalty_sub50()` debe ejecutarse manualmente via POST al endpoint. No hay scheduler, cron, ni refresh automatico.

3. **`driver_state` es NULL.** La columna existe en la tabla pero nunca se populiza. Es un placeholder desde la migracion original.

4. **`growth.yango_lima_driver_360_daily`** — existe como tabla en la DB (referenciada por `_audit_check_cols.py`) pero NO es utilizada por el Sub50 engine. El engine usa `ops.driver_daily_activity_fact` para `completed_trips`.

5. **`yango_lima_orders_raw`** — poblada via ingest manual (no hay cron job). El endpoint `/capture-orders-range` debe ser llamado explicitamente. Max 24h de rango por request. Sin esto, NO hay datos frescos para `supply_hours` ni driver universe.
