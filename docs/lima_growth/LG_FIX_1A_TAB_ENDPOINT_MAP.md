# LG_FIX_1A_TAB_ENDPOINT_MAP — Tab to Endpoint Map

**Generated:** 2026-06-12T19:36  
**Scope:** Cada tab de UI1A mapeado a endpoint(s), función api.js, hook, y params.

---

## Tab 1: FreshnessBanner

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/components/FreshnessBanner.jsx` |
| **Hook** | `useGrowthIntelligence` (auto-fetch on mount) |
| **Endpoints llamados** | 3 |
| **Timeout** | 30000ms cada uno |

| # | Función api.js | Endpoint | Params | Expected Payload Shape |
|---|---------------|----------|--------|----------------------|
| 1 | `getGrowthHealth()` | `GET /growth/health` | none | `{ system_status, components_healthy, components_degraded, components_critical, stale_assets, broken_assets, scheduler_status, remediation }` |
| 2 | `getGrowthFreshness()` | `GET /growth/freshness` | none | `{ overall_status, summary[], assets[], checked_at }` |
| 3 | `getGrowthOperability()` | `GET /growth/operability` | none | `{ system_status, summary, components[], stale_assets, broken_assets, dependency_issues, governance_operability }` |

**Reads from props:** `health`, `freshness`, `operability`, `loading`  
**Consumed keys:** `health.system_status`, `health.stale_assets`, `health.components_healthy/degraded/critical`, `health.scheduler_status`, `health.remediation`

---

## Tab 2: Overview

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/OverviewTab.jsx` |
| **Hook** | `useGrowthIntelligence` (triggered when `date` is set) |
| **Endpoints llamados** | 7 (via hook) |
| **Timeout** | mixed (15s-30s) |

| # | Función api.js | Endpoint | Params | Timeout |
|---|---------------|----------|--------|---------|
| 1 | `getLimaGrowthOperationalSummary(date)` | `GET /yego-lima-growth/operational-summary` | `{ date }` | 30000 |
| 2 | `getLimaGrowthDriverStateSummary(date)` | `GET /yego-lima-growth/driver-state/summary` | `{ date }` | 30000 |
| 3 | `getLimaGrowthOperationalTruth(date)` | `GET /yego-lima-growth/operational-truth` | `{ date }` | 15000 |
| 4 | `getLimaGrowthMovementSummary({date})` | `GET /yego-lima-growth/movement/summary` | `{ date }` | 15000 |
| 5 | `getYangoLoyaltySummary({})` | `GET /yango-loyalty/summary` | `{}` | 60000 |

**Consumed data keys (from props):**
- `data.overview` → operational-summary response
- `data.driverState` → driver-state/summary response
- `data.operationalTruth` → operational-truth response
- `data.movementSummary` → movement/summary response
- `data.loyaltySummary` → loyalty/summary response

**Expected payload shape per source:**
- `overview.universe_total`, `overview.drivers_with_program`, `overview.drivers_without_program`, `overview.active_programs`, `overview.queue_ready`, `overview.queue_held`, `overview.program_distribution`, `overview.channel_utilization`
- `driverState.total_drivers`, `driverState.dominant_lifecycle`
- `truth.drivers_with_program`, `truth.active_programs`
- `movementSummary.entries`, `movementSummary.exits`
- `loyaltySummary.total_rna`

---

## Tab 3: Programs

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/ProgramsTab.jsx` |
| **Hook** | `useGrowthIntelligence` |
| **Endpoints** | 2 + 1 direct |

| # | Función | Endpoint | Params | Timeout |
|---|---------|----------|--------|---------|
| 1 | `getLimaGrowthProgramsSummary(date)` | `GET /yego-lima-growth/programs/summary` | `{ date }` | 60000 |
| 2 | `getLimaGrowthProgramStatus(date)` | `GET /yego-lima-growth/programs/status` | `{ date }` | 15000 |
| 3 | `createExport({source, filters})` | `POST /yego-lima-growth/export` | body: `{ source, export_reason }` | — |

**Consumed keys per program:** `program.program_code`, `program.eligible_drivers ?? program.drivers ?? program.count`, `program.prioritized ?? program.prioritized_count`, `program.queue_count ?? program.queued`, `program.priority ?? program.effective_priority`

---

## Tab 4: Segments

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/SegmentsTab.jsx` |
| **Hook** | `useGrowthIntelligence` |
| **Endpoint** | 1 |

| # | Función | Endpoint | Params | Timeout |
|---|---------|----------|--------|---------|
| 1 | `getLimaGrowthTaxonomySummary(date)` | `GET /yego-lima-growth/taxonomy/summary` | `{ date }` | 30000 |

**Consumed keys:** `taxonomy.lifecycle_distribution || taxonomy.distribution`, `taxonomy.segments`, `taxonomy.value_tiers`, `taxonomy.momentum || taxonomy.trends`  
**Per item:** `item.count || item.drivers`, `item.lifecycle || item.status`

---

## Tab 5: Movement

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/MovementTab.jsx` |
| **Hook** | `useGrowthIntelligence` + 4 direct `api.get()` calls in own useEffect |
| **Endpoints** | 6 |

| # | Source | Endpoint | Params | Timeout |
|---|--------|----------|--------|---------|
| 1 | hook | `GET /yego-lima-growth/movement/summary` | `{ date }` | 15000 |
| 2 | hook | `GET /yego-lima-growth/movement/records` | `{ date, limit: 100 }` | 15000 |
| 3 | direct | `GET /yego-lima-growth/movement-analytics/stats` | none | 30000 |
| 4 | direct | `GET /yego-lima-growth/movement-analytics/matrix` | none | 30000 |
| 5 | direct | `GET /yego-lima-growth/movement-analytics/winners?limit=10` | `limit=10` | 30000 |
| 6 | direct | `GET /yego-lima-growth/movement-analytics/losers?limit=10` | `limit=10` | 30000 |

**Consumed keys:** `stats.positive_transitions`, `stats.negative_transitions`, `stats.total_transitions`, `stats.net_movement`, `stats.movement_classes`, `summary.entries/exits`, `analytics.segment_transitions/lifecycle_transitions`, `winners.top_winners`, `losers.top_losers`

---

## Tab 6: RNA

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/RNATab.jsx` |
| **Hook** | `useGrowthIntelligence` + 2 direct api.get() + PilotSection (1 more) |
| **Endpoints** | 7 |

| # | Source | Endpoint | Params | Timeout |
|---|--------|----------|--------|---------|
| 1 | hook | `GET /yango-loyalty/summary` | `{}` | 60000 |
| 2 | hook | `GET /yango-loyalty/kpis` | `{}` | 60000 |
| 3 | hook | `GET /yango-loyalty/city-comparison` | `{}` | 30000 |
| 4 | direct | `GET /yego-lima-growth/rna-priority/summary` | none | 30000 |
| 5 | direct | `GET /yego-lima-growth/rna-priority/drivers?band=HOT&limit=10` | `band=HOT, limit=10` | 30000 |
| 6 | PilotSection | `GET /yego-lima-growth/rna-pilot/summary` | none | 30000 |
| 7 | hook | `GET /yango-loyalty/city-comparison` | `{}` | 30000 |

**Consumed keys:** `loyalty.total_rna ?? loyalty.rna_total`, `loyalty.rna_new ?? loyalty.new_drivers`, `loyalty.rna_reactivable ?? loyalty.reactivable`, `loyalty.with_phone ?? loyalty.contactable`, `loyalty.cancelled_signals ?? loyalty.cancelled`

---

## Tab 7: Driver Explorer

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/DriverExplorerTab.jsx` |
| **Hook** | Manual fetch (no auto-load) |
| **Endpoints** | 1 + 1 export |

| # | Source | Endpoint | Params | Timeout |
|---|--------|----------|--------|---------|
| 1 | manual | `GET /drivers/activity-summary` | `{ program, lifecycle, segment, search, limit: 100, offset: 0 }` | 30000 |
| 2 | export | `POST /yego-lima-growth/export` | body: `{ source: 'driver_explorer', filters, export_reason }` | — |

**Consumed keys:** `driverData.drivers || driverData.data || driverData.records`, `driverData.total`

---

## Tab 8: Effectiveness

| Field | Value |
|-------|-------|
| **Archivo React** | `frontend/src/pages/lima-growth-ui1a/sections/EffectivenessTab.jsx` |
| **Hook** | Independent `useEffect` (not useGrowthIntelligence) |
| **Endpoints** | 1 |

| # | Función | Endpoint | Params | Timeout |
|---|---------|----------|--------|---------|
| 1 | `getEffectivenessSummary()` | `GET /yego-lima-growth/effectiveness/summary` | none | 30000 |

**Consumed keys:** `data.programs[]`, `data.total_drivers_tracked`, `data.drivers_with_outcome`, `data.coverage_pct`, `data.latest_date`, `data.message`, `data.movement_types[]`
**Per program:** `p.program_code`, `p.net_effect`, `p.assigned_drivers`, `p.positive_moves`, `p.negative_moves`, `p.improvement_rate`, `p.decline_rate`, `p.movement_score_delta`

---

## Resumen de Endpoints Únicos

26 endpoints distintos llamados por UI1A, distribuidos en:

| Dominio | Count |
|---------|-------|
| `/growth/*` | 3 |
| `/yego-lima-growth/*` | 14 |
| `/yango-loyalty/*` | 3 |
| `/yego-lima-growth/movement-analytics/*` | 4 |
| `/yego-lima-growth/rna-priority/*` | 2 |
| `/yego-lima-growth/rna-pilot/*` | 1 |
| `/drivers/*` | 1 |
| `/yego-lima-growth/export*` | 1 (via createExport) |
