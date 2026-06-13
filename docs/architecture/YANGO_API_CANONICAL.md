# YANGO API — CANONICAL DOCUMENTATION

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** FIRST DRAFT — Evidence-based from live repo audit
**Engine:** Control Foundation (#1) / External integration layer

---

## 1. OVERVIEW

The Yango API domain encompasses all integrations with external Yango/YEGO services:
- Yango Fleet API (driver data ingestion)
- Yango Loyalty / Oro Tracker (loyalty KPI monitoring)
- Yego Pro Profitability (profit sharing and bonus configuration)
- Shadow reconciliation (CT vs Yango data comparison)

---

## 2. YANGO RAW INGESTION

### 2.1 Purpose
Ingest raw driver activity and trip data from the Yango Fleet API into the Growth Machine pipeline.

### 2.2 Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yango_raw_ingestion_service.py` | `backend/app/services/` | Raw data ingestion from Yango API |
| `yango_raw_tick_ingestion_service.py` | `backend/app/services/` | Tick-level ingestion |
| `yango_shadow_reconciliation_service.py` | `backend/app/services/` | Shadow data reconciliation |
| `yango_driver_identity_audit_service.py` | `backend/app/services/` | Driver identity reconciliation |

### 2.3 Endpoints

| Method | Endpoint | Router | Description |
|--------|----------|--------|-------------|
| **NEEDS VERIFICATION** | `/ingestion/*` | `ingestion.py` | Ingestion status endpoint exists but scope is limited |

**NEEDS VERIFICATION: YES** — Ingestion router appears minimal (only `/ingestion/status`). Yango raw ingestion may be triggered via CLI scripts rather than HTTP endpoints.

### 2.4 Data Flow

```
Yango Fleet API (external)
    │
    ▼
yango_raw_ingestion_service.py (fetch + transform)
    │
    ▼
Raw data landing (STATUS: UNKNOWN — verify destination table)
    │
    ▼
yego_lima_driver_360_service.py (enrich)
    │
    ▼
growth.yango_lima_driver_history_daily/weekly
    │
    ▼
growth.yango_lima_driver_360_daily
```

### 2.5 Coverage

**STATUS: UNKNOWN**
**NEEDS VERIFICATION: YES** — Ingestion coverage, pagination, error handling, and retry logic require deeper audit of `yango_raw_ingestion_service.py` and related scripts.

Referenced documents:
- `backend/exports/audits/yango_raw_landing/coverage_summary.md`
- `backend/exports/audits/yango_raw_landing/ingestion_summary.md`
- `backend/exports/audits/yango_raw_landing/reconciliation_summary.md`

---

## 3. YANGO LOYALTY / ORO TRACKER

### 3.1 Purpose
Monitor loyalty program KPIs (Oro Tracker) across cities. Track reachability, performance, and target compliance.

### 3.2 Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yango_loyalty_service.py` | `backend/app/services/` | Core loyalty operations: summary, KPIs, rules |
| `yango_loyalty_performance_service.py` | `backend/app/services/` | Historical performance, city comparison, bootstrap |
| `yango_loyalty_definition_service.py` | `backend/app/services/` | Source definitions, definition sets, validation packs |
| `yango_loyalty_reachability_service.py` | `backend/app/services/` | Reachability summary per city/KPI |

### 3.3 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yango-loyalty/summary` | Full KPI summary with category per city |
| GET | `/yango-loyalty/kpis` | Detailed KPI table |
| GET | `/yango-loyalty/reachability` | Reachability summary per city/KPI |
| GET | `/yango-loyalty/rules` | Official loyalty rules |
| POST | `/yango-loyalty/manual-kpi` | Upload manual KPI value |
| POST | `/yango-loyalty/target` | Upload single target |
| POST | `/yango-loyalty/batch-targets` | Batch upload targets per city |
| POST | `/yango-loyalty/ensure-tables` | Create loyalty tables |

### 3.4 Performance Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yango-loyalty/performance` | Loyalty performance metrics |
| GET | `/yango-loyalty/bootstrap` | Bootstrap data |
| GET | `/yango-loyalty/history` | Historical loyalty data |
| GET | `/yango-loyalty/city-comparison` | City vs city comparison |

### 3.5 Definition Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yango-loyalty/sources` | List sources |
| GET | `/yango-loyalty/definition-sets` | List definition sets |
| GET | `/yango-loyalty/definition-sets/{id}` | Get definition set |
| GET | `/yango-loyalty/preview-all-sets` | Preview all definition sets |
| GET | `/yango-loyalty/validation-pack` | Get validation pack |
| GET | `/yango-loyalty/operational-flow` | Get operational flow |

### 3.6 Reachability

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yango-loyalty/reachability/summary` | Reachability summary |

### 3.7 Tables

**NEEDS VERIFICATION: YES** — Exact table names for loyalty data. Candidate table from registry:
- `ops.mv_yango_loyalty_performance_monthly_v1` (materialized view)

---

## 4. YEGO PRO PROFITABILITY

### 4.1 Purpose
Profit sharing, bonus configuration, and simulation for Yego Pro drivers.

### 4.2 Service

| Service | File | Responsibility |
|---------|------|----------------|
| `yego_pro_profitability_service.py` | `backend/app/services/` | Profit sharing calculations |

### 4.3 Endpoints

| Method | Endpoint | Router | Description |
|--------|----------|--------|-------------|
| **NEEDS VERIFICATION** | `/yego-pro/*` | `yego_pro_profitability.py` | Profit sharing endpoints |

**NEEDS VERIFICATION: YES** — Full endpoint list for Yego Pro profitability requires reading the router file.

### 4.4 Frontend

| Component | File | Description |
|-----------|------|-------------|
| `YegoProProfitabilityPage.jsx` | `frontend/src/components/` | Profit sharing UI |

### 4.5 SQL Artifacts

| File | Description |
|------|-------------|
| `backend/sql/yego_pro_bonus_config.sql` | Bonus configuration |
| `backend/sql/yego_pro_profitability_serving_views.sql` | Serving views |
| `backend/sql/yego_pro_simulation_scenarios.sql` | Simulation scenarios |

---

## 5. SHADOW RECONCILIATION

### 5.1 Purpose
Compare Control Tower data against Yango API data to detect discrepancies and validate data integrity.

### 5.2 Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yango_shadow_reconciliation_service.py` | `backend/app/services/` | Shadow comparison |
| `yango_driver_identity_audit_service.py` | `backend/app/services/` | Identity reconciliation |

### 5.3 Shadow Sources

Omniview V2 supports `YANGO_API_RAW` as a source system (alongside `CT_TRIPS_2026`). The shadow comparison endpoint (`/ops/omniview-v2/compare`) enables side-by-side source comparison.

**canonical_ready:** YANGO_API_RAW always has `canonical_ready=false`.

---

## 6. YANGO API COVERAGE

**STATUS: UNKNOWN — NEEDS VERIFICATION**

Referenced documents:
- `docs/lima_growth/LG_YANGO_API_COVERAGE_MATRIX.md`
- `docs/lima_growth/YANGO_API_R1_LIMA_ACTIVITY_API_REEXPLORATION.md`
- `docs/omnibuilder_v2/OV2_F6_YANGO_RECONCILIATION_REPORT.md`
- `docs/omnibuilder_v2/OV2_F6B_YANGO_COVERAGE_WATERFALL.md`
- `docs/omnibuilder_v2/OV2_F6B_SOURCE_INVENTORY.md`

---

## 7. FRONTEND COMPONENTS

| Component | File | Domain |
|-----------|------|--------|
| `YegoProProfitabilityPage.jsx` | `frontend/src/components/` | Yego Pro |
| `yangoLoyalty/` (directory) | `frontend/src/components/yangoLoyalty/` | Yango Loyalty UI |

**NEEDS VERIFICATION: YES** — Exact components in `yangoLoyalty/` directory not enumerated.

---

## 8. KNOWN GAPS

| Gap | Status | Priority |
|-----|--------|----------|
| Yango API coverage matrix needs verification | NEEDS VERIFICATION | MEDIUM |
| Raw ingestion destination tables not confirmed | NEEDS VERIFICATION | MEDIUM |
| Yego Pro endpoint list not enumerated | NEEDS VERIFICATION | LOW |
| Pagination coverage for Yango API calls | MAY BE COVERED — verify | MEDIUM |
| `canonical_ready=false` handling for Yango data in Omniview V2 | KNOWN — by design | N/A |

---

## 9. CERTIFICATION STATUS

| Certification | Document | Status |
|---------------|----------|--------|
| Yango Reconciliation | `OV2_F6_YANGO_RECONCILIATION_REPORT.md` | COMPLETED |
| Yango Source Recovery | `OV2_F6A_YANGO_SOURCE_RECOVERY_AND_RECON_CERTIFICATION_REPORT.md` | COMPLETED |
| Yango Pagination Coverage | `OV2_F6C_YANGO_PAGINATION_COVERAGE_CERTIFICATION_REPORT.md` | COMPLETED |
| Loyalty Sub50 | `LOYALTY_SUB50_CERTIFICATION.md` | CERTIFIED |
| Loyalty Sub50 Inventory | `LOYALTY_SUB50_INVENTORY.md` | COMPLETED |

---

## 10. CROSS-REFERENCES

- [SYSTEM_MAP.md](SYSTEM_MAP.md) — Full system map
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Known constraints
- [GROWTH_MACHINE_CANONICAL.md](GROWTH_MACHINE_CANONICAL.md) — Growth machine domain
- [OMNIVIEW_V2_CANONICAL.md](OMNIVIEW_V2_CANONICAL.md) — Omniview domain (V2 source-agnostic)
- [OMNIVIEW_CANONICAL_REGISTRY.md](../../OMNIVIEW_CANONICAL_REGISTRY.md) — Full registry
- [LG_YANGO_API_COVERAGE_MATRIX.md](../lima_growth/LG_YANGO_API_COVERAGE_MATRIX.md) — API coverage
- [OV2_F6_YANGO_RECONCILIATION_REPORT.md](../omnibuilder_v2/OV2_F6_YANGO_RECONCILIATION_REPORT.md) — Reconciliation

---

*Generated from live repo audit. Evidence sources: `backend/app/routers/yango_loyalty.py`, `backend/app/services/yango_*.py`, `backend/app/routers/omniview_v2.py` (source-agnostic endpoints), `backend/sql/yego_pro_*.sql`, `frontend/src/components/YegoProProfitabilityPage.jsx`, `frontend/src/components/yangoLoyalty/`.*
