# LG_GOV_2A_DRIVER_EXPLORER_READINESS

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12  
**Veredict:** `NO-GO for deployment`

---

## READINESS CHECKLIST

### 1. Migration

| Check | Status | Detail |
|-------|--------|--------|
| Migration 219 (indexes) | **PENDING** | File exists at `219_lg_perf_1a_driver_explorer_index.py`. Not confirmed applied in production. |
| Migration 220 (explorer fact) | **NOT APPLIED** | File exists at `220_lg_exp_1d_driver_explorer_fact.py`. Table does NOT exist in production. |
| `alembic upgrade head` | **NOT RUN** | Head includes 220. Needs execution. |

**Blocker:** Table `growth.yego_lima_driver_explorer_fact` DOES NOT EXIST in production.

```sql
SELECT EXISTS(
  SELECT 1 FROM information_schema.tables
  WHERE table_schema='growth' AND table_name='yego_lima_driver_explorer_fact'
);
-- Result: FALSE
```

---

### 2. Serving Fact Writer

| Check | Status | Detail |
|-------|--------|--------|
| Writer function | **READY** | `build_driver_explorer_fact()` in `yego_lima_driver_explorer_fact_service.py:62` |
| Build script | **READY** | `backend/scripts/build_driver_explorer_fact.py --date YYYY-MM-DD` |
| Feature flag | **OFF** | `LG_DRIVER_EXPLORER_FACT_ENABLED` not set |
| autonomous_tick integration | **NOT ACTIVE** | Writer not called from cascade |

**Blocker:** Writer has never been executed against production DB. First run will be the initial population.

---

### 3. Endpoint

| Check | Status | Detail |
|-------|--------|--------|
| Service | **READY** | `yego_lima_driver_explorer_service.py` (222 lines) |
| Router | **READY** | `GET /yego-lima-growth/driver-explorer` registered in `main.py:216` |
| Graceful empty state | **READY** | `warning: "NO_SERVING_DATA"` if table empty or missing |
| Filter params | **READY** | search, lifecycle, program, segment, rna_band, limit, offset |
| Performance indices | **DESIGNED** | 6 indexes in migration 220 |

**No blocker:** Endpoint code is complete and registered. Will return `NO_SERVING_DATA` until fact is populated.

---

### 4. API Client

| Check | Status | Detail |
|-------|--------|--------|
| Function | **READY** | `getLimaGrowthDriverExplorer()` in `frontend/src/services/api.js:1732` |
| Timeout | **READY** | 15000ms |
| Coexistence | **READY** | `getDriverActivitySummary` preserved |

**No blocker.**

---

### 5. UI

| Check | Status | Detail |
|-------|--------|--------|
| DriverExplorerTab rewritten | **READY** | 258 lines, 11 real columns, 4 filters |
| Column mapping | **READY** | lifecycle, segment, program, movement, RNA → serving fact fields |
| Empty state handling | **READY** | Shows contextual "no data" vs "no results" message |
| Export button | **READY** | Uses existing `createExport()` |
| Explainability | **READY** | Uses existing `ExplainabilityPanel` component |

**No blocker.**

---

### 6. Source Table Freshness (precondition for first build)

| Source Table | Fresh? | Rows for 06-12 | Status |
|-------------|--------|---------------|--------|
| `driver_state_snapshot` | ✅ 06-12 | 18,545 | READY |
| `program_eligibility_daily` | ✅ 06-12 | 28,128 | READY |
| `rna_priority_fact` | ✅ | 888 | READY |
| `driver_lifecycle_daily` | ✅ 06-12 | 68,506 | READY |
| `v2_taxonomy_daily` | ✅ 06-12 | 68,506 | READY (orphan) |
| `v2_movement_fact` | ✅ 06-12 | 466 | READY |
| `loopcontrol_result_sync` | ⚠️ 10 rows | 10 | Near-empty |
| `assignment_queue` | ✅ | variable | READY |
| `impact_tracking` | ❌ 0 rows | 0 | Empty |

**No blocker for first build.** All primary sources have data. Secondary sources (loopcontrol, impact) will be NULL — graceful degradation.

---

### 7. Integration Readiness

| Check | Status | Detail |
|-------|--------|--------|
| autonomous_tick integration | **NOT ACTIVE** | Writer not in cascade |
| daily_refresh integration | **NOT ACTIVE** | Not in `run_daily_refresh()` steps |
| Feature flag mechanism | **DESIGNED** | `LG_DRIVER_EXPLORER_FACT_ENABLED=true` env var |
| Pruning strategy | **DESIGNED** | 90-day retention via DELETE in writer |

---

## GO / NO-GO

| Criterion | Status |
|-----------|--------|
| Migration created | ✅ READY |
| Migration applied | ❌ NOT APPLIED |
| Table exists in production | ❌ DOES NOT EXIST |
| Writer functional | ✅ READY |
| Writer executed in production | ❌ NEVER EXECUTED |
| Endpoint registered | ✅ READY |
| API client deployed | ✅ READY (in code) |
| UI rewritten | ✅ READY (in code) |
| Source tables fresh | ✅ READY |
| Integration automated | ❌ NOT AUTOMATED |

### Veredict: NO-GO

**3 of 10 criteria fail.** The serving fact table does not exist in production. Migration 220 has not been applied. The writer has never been executed. Integration into autonomous_tick is not active.

### Deployment Sequence (to achieve GO)

| Step | Action | Phase |
|------|--------|-------|
| 1 | `alembic upgrade head` (applies migrations 219 + 220) | LG-EXP-1D deploy |
| 2 | `python -m scripts.build_driver_explorer_fact --date 2026-06-12 --validate` | First build |
| 3 | Verify `GET /yego-lima-growth/driver-explorer` returns 200 with data | Validation |
| 4 | Set `LG_DRIVER_EXPLORER_FACT_ENABLED=true` | Feature flag ON |
| 5 | Verify autonomous_tick builds fact in next cascade | Integration test |
| 6 | Verify DriverExplorerTab shows real data in browser | UI validation |
| 7 | Remove `activity-summary` fallback from UI (optional) | Cleanup |

### Dependencies for GO

| Dependency | Current Status |
|-----------|---------------|
| DB access for `alembic upgrade head` | Required |
| V2 pipeline running (for source data freshness) | Manual trigger working |
| autonomous_tick running | ACTIVE (every 5 min) |

**When steps 1-6 complete, Driver Explorer is GO for production.**
