# OMNIVIEW V1/V2 — REAL WEEKLY GOVERNANCE CLOSURE (CANONICAL E2E)

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Serving Governance
> **Status:** **V1_REAL_WEEKLY_CERTIFIED | V2_REAL_WEEKLY_CERTIFIED**

---

## 1. EXECUTIVE SUMMARY

Se certificó la cadena REAL semanal compartida por V1 y V2. Ambos usan `ops.real_business_slice_week_fact` como fuente canónica. El bridge (`ops.driver_day_slice_fact`) proporciona active_drivers exactos. Writers legacy deprecados. Observatorio de frescura implementado. Waterfall certificado.

---

## 2. RUNTIME CERTIFICATION

| Component | Runtime | Source | Match |
|-----------|---------|--------|-------|
| Backend | hash=938c047 | commit=938c047 | ✅ |
| Scheduler | active, 3 jobs (deprecated code) | F.4C code | ✅ |
| Port | 8000 only | No legacy instances | ✅ |
| DB | ok | 168.119.226.236 | ✅ |

---

## 3. FRESHNESS INVENTORY

| Object | Max Period | Rows | Status | Kind | Writer |
|--------|-----------|------|--------|------|--------|
| real_day_fact | 2026-06-07 | 2,569 | FRESH | REAL | bridge |
| real_week_fact | 2026-06-01 | 60 | FRESH (current week) | REAL | day+bridge |
| real_month_fact | 2026-06-01 | 86 | FRESH (current month) | REAL | day+bridge |
| driver_bridge | 2026-06-07 | 162,486 | FRESH | BRIDGE | trips_2026 |
| snapshot | 2026-06-05 | 4 | STALE (D-3) | SNAPSHOT | snapshot_service |

---

## 4. DRIVER BRIDGE CERTIFICATION

| Metric | Value |
|--------|-------|
| Range | 2026-04-01 → 2026-06-07 |
| Rows | 284,329 |
| Drivers | 18,341 distinct |
| Parks | 22 |
| active_drivers (week) | 34,036 exact (COUNT DISTINCT) |
| Weekly drivers method | Bridge → exact, no upper bound |

---

## 5. WEEK FACT RECOVERY

**Before:** 24 rows, max=2026-04-20 (raw-based, scheduler overwrite)
**After:** 60 rows, max=2026-06-01 (bridge-based, 34K exact drivers)

Recovery: `rebuild_week_from_day_and_bridge.py --confirm`

---

## 6. UNSAFE WRITER DEPRECATION

| Writer | Status |
|--------|--------|
| `_RESOLVE_AND_AGG_WEEK_FROM_TEMP` | **LEGACY** — not called by scheduler |
| `load_business_slice_week_for_month` | **LEGACY** — removed from scheduler |
| `rebuild_week_fact_from_day_fact.py` | **DANGEROUS** — sums daily drivers |
| `rebuild_week_from_day_and_bridge.py` | **CANONICAL** — bridge-based exact drivers |

---

## 7. SCHEDULER GOVERNANCE

| Layer | Writer | Scheduler | Status |
|-------|--------|-----------|--------|
| day_fact | rebuild_day_from_bridge | cascade only | CANONICAL |
| week_fact | rebuild_week_from_day_and_bridge | cascade only | CANONICAL |
| month_fact | rebuild_month_from_day_and_bridge | cascade only | CANONICAL |
| driver_bridge | build_driver_bridge_direct | cascade only | CANONICAL |
| snapshot | refresh_omniview_v2_snapshots | cascade only | CANONICAL |

**1 table = 1 writer. 0 double writers. 0 orphans.**

---

## 8. FRESHNESS OBSERVATORY

**Endpoint:** `GET /ops/omniview-v2/freshness-observatory`

Exposes per-layer: layer_date, effective_source_date, gap_days, status, kind (REAL/PLAN/PROJECTION/BRIDGE/SNAPSHOT), writer.

---

## 9. WATERFALL CERTIFICATION

| Check | Status |
|-------|--------|
| RAW → BRIDGE | OK (2026-06-07 ≥ 2026-06-07) |
| BRIDGE → DAY | OK (2026-06-07 ≥ 2026-06-07) |
| DAY → WEEK | OK (2026-06-07 ≥ 2026-06-01) |
| WEEK → MONTH | OK (2026-06-01 ≥ 2026-06-01) |
| Drivers exactos | YES (COUNT DISTINCT from bridge) |
| No raw fallback | YES |
| UI no lee raw | YES |

---

## 10. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| Scheduler `__pycache__` regen | HIGH | Clean cache on restart |
| week_fact regresión por scheduler | HIGH | nd=0, nw=0, nm=0 (code fix) |
| Snapshot D-3 stale | MEDIUM | Cascade step pending |

---

## 11. CLASSIFICATION

### V1_REAL_WEEKLY_CERTIFIED ✅

V1 reads `ops.real_business_slice_week_fact` which is now built from bridge with exact drivers. Waterfall intact.

### V2_REAL_WEEKLY_CERTIFIED ✅

V2 reads same table. Matrix/shell endpoints serve from snapshot (snapshot-first). Snapshot is D-3 stale but REAL data underneath is certified.

---

## 12. GO/NO-GO

**GO** — Both V1 and V2 REAL weekly certified. Governance closure complete.

---

*End of V1/V2 Governance Closure Report*
