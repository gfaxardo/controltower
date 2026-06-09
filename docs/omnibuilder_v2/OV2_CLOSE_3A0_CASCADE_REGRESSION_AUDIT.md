# OV2-CLOSE.3A.0 — CASCADE REGRESSION AUDIT

> **Date:** 2026-06-09
> **Motor:** Control Foundation
> **Subproject:** Omniview V2 Closure
> **Phase:** OV2-CLOSE.3A.0 — Cascade Regression Audit
> **Status:** **REGRESSION CONFIRMED — Multiple root causes identified**
> **Rule:** NO fixes, NO rebuilds, NO cascades. Diagnostic only.

---

## 1. EXECUTIVE SUMMARY

**Se confirma una regresión de Control Foundation introducida en el commit `17d4f34` (2026-06-09).**

El nuevo `omniview_cascade_service.py` y los rebuild scripts asociados presentan múltiples bugs que causan:
- Week Fact vacío o corrupto (Matrix devuelve `None`)
- Month Fact con revenue=0
- Day Fact con divergencia vs Cell Audit
- Pérdida potencial de datos históricos por DELETE sin integridad transaccional

La causa raíz NO es un solo bug sino una combinación de 4 defectos que interactúan.

---

## 2. CONTEXT RECOVERY

### FROM `ai_operating_system.md`
- **Motor activo:** Control Foundation (REOPENED / P0)
- **Motores bloqueados:** Diagnostic, Forecast, Suggestion, Decision, Action, AI Copilot, Learning
- **Regla:** "DO NOT advance to later engines if previous engines are unstable."

### FROM `ai_current_phase.md`
- **Fase activa:** OMNI-P0 — False GO Recovery & Vs Proy Canonicalization
- **Status:** ACTIVE (reopened 2026-06-03)
- **Prioridad:** Resolver Revenue vacío, clarificar CLOSED/PARTIAL/CURRENT/FUTURE, certificación semántica V2

### Certified State (pre-regression)
| Component | Status |
|-----------|--------|
| Driver Bridge | CERTIFIED |
| Day Fact Bridge Migration | CERTIFIED |
| Week Fact Bridge Migration | CERTIFIED |
| Month Fact Bridge Migration | CERTIFIED |
| Freshness Chain | CERTIFIED |
| Scheduler Canonicalization | CERTIFIED |
| Runtime Truth Governance | CERTIFIED |
| Shared Reality Governance | CERTIFIED |
| Advancement Log | CERTIFIED |
| Inspector Foundation | CERTIFIED |
| Cell Auditability | CERTIFIED |
| Cross KPI Auditability | CERTIFIED |
| Startup Self-Heal | CERTIFIED |
| Cascade Wiring | CERTIFIED |
| Lock Recovery | CERTIFIED |

### Historical fixes (previously resolved)
1. cell_audit was stub → fixed
2. drill/cell was stub → fixed
3. scheduler cascade not connected → fixed
4. lock bug blocking cascade → fixed

**Commit introducing the regression:**
`17d4f34` (2026-06-09 08:34 -0500) — "OV2-CLOSE: Omniview V2 Closure Series (2A-3A)"
- Added: `backend/app/services/omniview_cascade_service.py` (+403 lines, NEW)
- Modified: `backend/app/repositories/omniview_v2_matrix_repository.py` (+44/-2 lines)
- Removed `SUM(active_drivers)` from fact table queries in matrix repo
- Added separate bridge query with `COUNT(DISTINCT driver_id)` for active_drivers

---

## 3. TASK 2 — GIT DIFF AUDIT

### Pending Changes (uncommitted)

| File | Classification | Rationale |
|------|---------------|-----------|
| `backend/app/routers/health.py` | SAFE | New health endpoints, unrelated to cascade |
| `backend/app/routers/ops.py` | SAFE | New ops endpoints, unrelated |
| `backend/app/services/yego_lima_movement_service.py` | SAFE | Lima Growth refactor, unrelated |
| `backend/app/services/yego_lima_scheduler_service.py` | SAFE | Lima Growth scheduler, unrelated |
| `frontend/src/pages/LimaGrowthDashboardV2.jsx` | SAFE | Lima Growth UI, unrelated |
| `frontend/src/pages/lima-growth-v2/sections/*.jsx` | SAFE | Lima Growth UI, unrelated |
| `frontend/src/services/api.js` | SAFE | API client, unrelated |
| `docs/lima_growth/*.md` | SAFE | Lima Growth docs |
| `backend/exports/audits/ov2_refresh/*` | SAFE | Audit data, symptom not cause |
| `backend/exports/audits/yango_raw_landing/*` | SAFE | Yango audit data |

**Verdict:** No pending changes affect the cascade regression. All current working tree changes are either Lima Growth-related or audit exports.

### Key Commits (last 5)

| Hash | Date | Description | Classification |
|------|------|-------------|---------------|
| `17d4f34` | Jun 9 08:34 | OV2-CLOSE: Omniview V2 Closure Series (2A-3A) | **RISKY** — Introduced cascade service + matrix repo change |
| `068eff0` | Jun 8 20:27 | Yango Pagination + Coverage Certification | SAFE |
| `eeaa928` | Jun 8 19:48 | Yango Source Governance | SAFE |
| `3a28e37` | Jun 8 19:33 | Yango coverage diagnostic | SAFE |
| `2c85c2e` | Jun 8 17:14 | Yango reconciliation recertified | SAFE |

---

## 4. TASK 3 — CASCADE AUDIT: WINDOW SIZES

### Cascade Architecture

```
RAW (public.trips_2026)
  ↓ build_driver_bridge_direct.py
DRIVER_BRIDGE (ops.driver_day_slice_fact)
  ↓ rebuild_day_from_bridge.py
DAY_FACT (ops.real_business_slice_day_fact)
  ↓ rebuild_week_from_day_and_bridge.py
WEEK_FACT (ops.real_business_slice_week_fact)
  ↓ rebuild_month_from_day_and_bridge.py
MONTH_FACT (ops.real_business_slice_month_fact)
  ↓ refresh_omniview_v2_snapshots.py
SNAPSHOT (ops.omniview_v2_serving_snapshot)
```

### Window per Layer (as configured in `omniview_cascade_service.py`)

| Layer | Script | `date_from` | `date_to` | Window |
|-------|--------|-------------|-----------|--------|
| `driver_bridge` | `build_driver_bridge_direct.py` | `today - 2d` | `today - 1d` | **1 day** |
| `day_fact` | `rebuild_day_from_bridge.py` | `today - 2d` | `today - 1d` | **1 day** |
| `week_fact` | `rebuild_week_from_day_and_bridge.py` | `2026-04-01` (hardcoded) | `today - 1d` | **Full (Apr→yesterday)** |
| `month_fact` | `rebuild_month_from_day_and_bridge.py` | `2026-06-01` (hardcoded) | `today - 1d` | **Current month only** |
| `snapshot` | `refresh_omniview_v2_snapshots.py` | — | — | N/A |

### Observations

1. **Day and bridge windows are intentionally narrow** (1 day) — designed for incremental refresh. This is correct assuming historical data in those tables survives between cascade runs.

2. **Week window is hardcoded to `2026-04-01`** — covers all operational data from April 2026 forward. This is appropriate IF day_fact has all historical data.

3. **Month window is hardcoded to `2026-06-01`** — this is a **TIME BOMB**. On July 1, 2026, the month rebuild will stop producing complete data for June. Worse, it DELETEs month >= `2026-06-01`, so after June, it would delete ALL data from June forward.

4. **The week hardcode `2026-04-01`** is also a time bomb — data before April 2026 can exist but will be deleted by the FULL DELETE in the week rebuild and never restored since the staging only covers April onward.

### Cascade Execution Order: CRITICAL BUG IN CLI SCRIPT

| Source | Order | Correct? |
|--------|-------|----------|
| `omniview_cascade_service.py` | bridge → day → week → month → snapshot | **CORRECT** |
| `run_ov2_refresh_cascade.py` (CLI) | bridge → **week → month → day** | **WRONG** |

The CLI script rebuilds week and month BEFORE day. This means week_fact and month_fact are built from **stale day_fact data** (day_fact hasn't been refreshed yet in that cascade run).

---

## 5. TASK 4 — DELETE + INSERT AUDIT

### Summary Table

| Layer | Delete Pattern | Insert Pattern | Transactional Integrity | Risk |
|-------|---------------|----------------|------------------------|------|
| `driver_bridge` | NONE (UPSERT via ON CONFLICT) | INSERT ... ON CONFLICT DO UPDATE | Single atomic UPSERT | **SAFE** |
| `day_fact` | `DELETE WHERE trip_date BETWEEN x AND y` | `INSERT FROM staging` | **SEPARATE COMMITS** (line 95, 98) | **HIGH** |
| `week_fact` | `DELETE FROM table` (NO WHERE) | `INSERT FROM staging` | **SEPARATE COMMITS** (line 118, 137) | **CRITICAL** |
| `month_fact` | `DELETE WHERE month >= x` | `INSERT FROM staging` | **SEPARATE COMMITS** (line 107, 122) | **HIGH** |
| `week_fact (legacy)` | `DELETE WHERE week_start IN (staging weeks)` | `INSERT FROM staging` | **SEPARATE COMMITS** | **MEDIUM** |

### Evidence of the Transactional Integrity Bug

**File:** `backend/scripts/rebuild_week_from_day_and_bridge.py:116-137`

```python
cur.execute(f"DELETE FROM {TARGET}")       # line 116 — DELETES ALL ROWS
deleted = cur.rowcount
conn.commit()                               # line 118 — ⚠️ COMMIT DELETE
print(f"  Deleted {deleted} rows")

cur.execute(f"""                            # line 121
    INSERT INTO {TARGET} (...)            
    SELECT ... FROM {STAGING}
""")
inserted = cur.rowcount
conn.commit()                               # line 134 — ⚠️ COMMIT INSERT
```

**Same pattern in all 3 rebuild scripts** (day, week, month). The `except` block at the end performs `conn.rollback()`, but this only rolls back the current transaction. Since DELETE was already committed, the rollback CANNOT restore deleted data.

### Impact Analysis

**If INSERT fails after DELETE succeeds:**
- `day_fact`: loses 1 day of data (limited blast radius)
- `week_fact`: **loses ALL data** (FULL DELETE with no WHERE clause)
- `month_fact`: loses all data from `date_from` forward (June onward with current hardcode)

### The Week DELETE Is Catastrophic

The week rebuild script does:
```sql
DELETE FROM ops.real_business_slice_week_fact
```
No WHERE clause. This deletes **every row** in week_fact. If the subsequent INSERT fails for any reason (timeout, constraint violation, OOM, etc.), all week data is permanently lost.

**This is the most likely explanation for "Week = None" in the Matrix.**

---

## 6. TASK 5 — HISTORICAL COVERAGE AUDIT

### Expected Coverage (what SHOULD be in tables before cascade)

| Table | Expected MIN date | Expected MAX date | Data Source |
|-------|-------------------|-------------------|-------------|
| `driver_day_slice_fact` | 2026-04-01 | 2026-06-08 | Raw trips_2026 (cumulative UPSERT) |
| `real_business_slice_day_fact` | 2026-04-01 | 2026-06-08 | Bridge + self (incremental DELETE/INSERT) |
| `real_business_slice_week_fact` | 2026-04-01 | Week of 2026-06-01 | day_fact + bridge (FULL REBUILD) |
| `real_business_slice_month_fact` | 2026-04-01 | 2026-06-01 | day_fact + bridge (partial rebuild) |

### Post-Cascade Coverage Risk

1. **Day historical data** — should survive IF the day_fact DELETE was scoped to the 1-day window. However, if a previous cascade run used a wider date range (e.g., manual run), historical data could have been deleted.

2. **Week historical data** — entirely dependent on INSERT succeeding after the FULL DELETE. If the cascade's week step failed after DELETE, ALL historical week data is gone.

3. **Month historical data** — months before `2026-06-01` are preserved (DELETE uses `WHERE month >=`). Months after June 1 are rebuilt each time.

### Actual Evidence (from OV2_CLOSE_3A reconciliation report)

| Grain | Cell Audit (bridge/day_fact) | Matrix (fact table) | Gap |
|-------|------------------------------|---------------------|-----|
| Day (Jun 6) | 13,041 trips | 9,736 trips | -25% |
| Week (Jun 1) | 79,927 trips | **None** | 100% missing |
| Month (Jun 1) | 89,134 trips, $40,166 rev | 20,987 trips, $0 rev | -76% trips, -100% rev |

**Conclusion:** Historical coverage was partially lost for day, entirely lost for week (fact table likely empty), and severely degraded for month.

---

## 7. TASK 6 — WEEK NONE RCA (Root Cause Analysis)

### Symptom
Matrix returns `None` for Week grain, while Cell Audit shows valid data (79,927 trips, $35,963 revenue, 2,866 active drivers).

### Why Cell Audit works
`cell_audit` (line 489-498 in `omniview_v2.py`) queries `ops.driver_day_slice_fact` (bridge) directly. It does NOT read from `ops.real_business_slice_week_fact`. So it shows correct data regardless of week_fact state.

### Why Matrix fails
`get_ct_matrix_data(grain="week")` queries `ops.real_business_slice_week_fact`:

```sql
SELECT week_start AS period_date, business_slice_name,
       COALESCE(SUM(trips_completed), 0)::bigint AS trips_completed,
       COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue_yego_final
FROM ops.real_business_slice_week_fact
WHERE LOWER(TRIM(country)) = %s AND LOWER(TRIM(city)) = %s
  AND week_start >= %s::date AND week_start <= %s::date
GROUP BY week_start, business_slice_name
```

If `week_fact` returns zero rows for the requested period, the status is `"NO_DATA"` and Matrix returns `None`.

### Root Cause Hypothesis Chain

1. **Cascade ran on startup** (`run_startup_self_heal()` in `main.py:370-383`)
2. **Week rebuild step executed:** `DELETE FROM ops.real_business_slice_week_fact` (FULL DELETE)
3. **INSERT step failed or produced empty results** because:
   - **3a.** Day_fact was incomplete at the time week was rebuilt (missing historical data)
   - **3b.** The CLI script (`run_ov2_refresh_cascade.py`) runs week BEFORE day, so week was built from stale day_fact
   - **3c.** Bridge data was incomplete for the query range
4. **Table was left empty or with only the current partial week**

### Most Probable Cause
**Option 3a or 3b combined with 2.** The FULL DELETE on week_fact is the enabler. Whether the INSERT fails or produces incomplete data, the DELETE has already committed and the old data is gone.

---

## 8. TASK 7 — MONTH REVENUE=0 RCA

### Symptom
Matrix Month shows `revenue_yego_final = 0` for June 2026, while Cell Audit shows $40,166.

### How revenue flows

**Cell Audit** (for month grain with period `2026-06-01`):
- Queries `ops.real_business_slice_day_fact` for the full month range (June 1-30)
- Sums `revenue_yego_final` across ALL business slices and parks
- Shows $40,166 (correct cumulative for available June data)

**Matrix** (for month grain):
- Queries `ops.real_business_slice_month_fact`
- The month_fact table is populated by `rebuild_month_from_day_and_bridge.py`
- Revenue in month_fact comes from day_fact: `SUM(COALESCE(revenue_yego_final, 0))`

### Root Cause Hypothesis Chain

1. **Month rebuild reads day_fact for June 1-8** (date_to = yesterday)
2. **Day_fact was incomplete** at cascade time (missing revenue data for many days)
3. **Revenue_yego_final was 0 or NULL** in those day_fact rows
4. **Month_fact stored revenue = 0**

### Why day_fact revenue could be missing

The day rebuild script (`rebuild_day_from_bridge.py`) **copies revenue from existing day_fact**, it does NOT recalculate revenue:
```sql
day_revenue AS (
    SELECT trip_date, business_slice_name,
           SUM(COALESCE(revenue_yego_final, 0)) AS revenue_yego_final
    FROM {TARGET}              -- ← TARGET = ops.real_business_slice_day_fact itself!
    WHERE trip_date BETWEEN x AND y
)
```

So the day rebuild preserves whatever revenue was already in day_fact. If day_fact had 0 revenue for certain days (from a previous corruption), the rebuild preserves the 0.

### But Cell Audit shows $40,166 for the month...

Cell Audit ALSO queries day_fact. So if day_fact has revenue, both should see it. The difference is:
- Cell Audit sums **ALL rows** for the full month range (June 1-30 or whatever is in day_fact)
- month_fact was rebuilt from day_fact data for **June 1-8 only** (cascade date_to)

If day_fact has $40,166 revenue accumulated across ALL available June dates, then the month rebuild should also capture it for June 1-8. Unless:
1. The month rebuild's JOIN logics drop rows
2. The revenue is spread across dates beyond June 8 (but cell audit also queries up to June 8 in practice, since that's what's in day_fact)
3. **The month rebuild ran when day_fact was in an intermediate/corrupted state**

### Most Probable Cause
**The cascade (or a previous cascade) ran when day_fact was incomplete.** The month rebuild captured revenue=0 from that incomplete state. Since month is never recalculated from scratch (unlike week which does a FULL DELETE), the 0 persisted.

---

## 9. TASK 8 — REGRESSION CLASSIFICATION

### Classification: **E) MULTIPLE REGRESSION**

The incident is not a single bug but a compound of 4 interacting defects:

| # | Defect | Severity | File(s) |
|---|--------|----------|---------|
| **D1** | Week rebuild: FULL DELETE without WHERE, separate commit from INSERT | **CRITICAL** | `rebuild_week_from_day_and_bridge.py:116-118` |
| **D2** | Day/Month rebuild: DELETE committed before INSERT (transactional split) | **HIGH** | `rebuild_day_from_bridge.py:93-98`, `rebuild_month_from_day_and_bridge.py:104-122` |
| **D3** | CLI cascade script: wrong layer order (week/month before day) | **HIGH** | `run_ov2_refresh_cascade.py:23-28` |
| **D4** | Hardcoded date boundaries (month: 2026-06-01, week: 2026-04-01) | **MEDIUM** | `omniview_cascade_service.py:115,125` |

### Which defects caused the observed symptoms?

| Symptom | Primary Cause | Contributing Factors |
|---------|--------------|---------------------|
| Week = None | **D1** — FULL DELETE committed, INSERT failed or incomplete | D3 (stale day_fact), D4 (narrow window) |
| Month revenue = 0 | **D2** — DELETE committed, INSERT may have been from incomplete day_fact | D4 (June-only window) |
| Day divergence | **D2** — DELETE committed before INSERT, narrow window | Day rebuild only processes 1 day, doesn't recover lost data |

---

## 10. TASK 9 — REMEDIATION PLAN

### Principle
**MINIMUM changes. SAFETY first. NO new logic.**

### Phase 1: Fix Transactional Integrity (P0 — CRITICAL)

**What:** Wrap DELETE + INSERT in a single transaction with rollback capability.

**Files to fix:**
1. `backend/scripts/rebuild_week_from_day_and_bridge.py` — lines 116-137
2. `backend/scripts/rebuild_day_from_bridge.py` — lines 93-98
3. `backend/scripts/rebuild_month_from_day_and_bridge.py` — lines 104-122

**Fix:** Remove the intermediate `conn.commit()` between DELETE and INSERT. Let the single commit at the end handle both. The `except` block's `conn.rollback()` will then properly undo the DELETE if the INSERT fails.

**Risk:** Low. This is a pure safety fix, does not change logic.

**Rollback:** Not needed. The fix only improves safety.

### Phase 2: Fix CLI Cascade Order (P0 — HIGH)

**What:** Reorder `LAYERS` in `run_ov2_refresh_cascade.py` to match the service order.

**File:** `backend/scripts/run_ov2_refresh_cascade.py:23-28`

**Fix:** Change order from `[driver_bridge, week_fact, month_fact, day_fact]` to `[driver_bridge, day_fact, week_fact, month_fact]`.

**Risk:** Zero. Pure reorder.

### Phase 3: Change Week DELETE to Targeted (P1)

**What:** Replace FULL DELETE with targeted DELETE matching the staging range.

**File:** `backend/scripts/rebuild_week_from_day_and_bridge.py:116`

**Fix:** 
```python
# FROM:
cur.execute(f"DELETE FROM {TARGET}")
# TO:
cur.execute(f"DELETE FROM {TARGET} WHERE week_start IN (SELECT DISTINCT week_start FROM {STAGING})")
```

**Risk:** Low. This is the same pattern already used safely in the legacy `rebuild_week_fact_from_day_fact.py:147-150`.

### Phase 4: Fix Hardcoded Dates (P1)

**What:** Replace hardcoded `2026-04-01` and `2026-06-01` with computed offsets.

**File:** `backend/app/services/omniview_cascade_service.py:115,125`

**Fix:**
- Week: `date_from = (today - timedelta(days=90)).isoformat()` (rolling 90-day window)
- Month: `date_from = today.replace(day=1).isoformat()` (first day of current month)

**Risk:** Medium. Changes behavior but removes time bomb. Requires testing.

### Phase 5: Recertification (P2)

After Phase 1-4 fixes are applied and verified:
1. Run a single cascade manually (not at startup)
2. Verify all 5 layers produce correct MAX dates and row counts
3. Run partial matrix reconciliation (Day, Week, Month) using cell_audit as ground truth
4. Certify each layer

### What NOT to do
- DO NOT add new features to rebuild scripts
- DO NOT change revenue calculation logic
- DO NOT modify the matrix repository beyond what's already committed
- DO NOT run Browser QA until serving facts are verified
- DO NOT open any blocked engine

---

## 11. GO / NO GO

### Decision: **NO GO**

**OV2-CLOSE.3A.0 cannot proceed to closure.**

Control Foundation is currently in a **REGRESSED** state:

- Week serving facts are unreliable (likely empty)
- Month serving facts have zero revenue
- Day serving facts show divergence
- The cascade mechanism that was supposed to ensure freshness is itself the source of corruption

### Conditions for GO

1. All 4 defects (D1-D4) must be fixed
2. At least one successful cascade must run without data loss
3. Week, Month, and Day Matrix must reconcile with Cell Audit (within 1% tolerance)
4. MAX dates across all fact tables must be within 1 day of today
5. No historical coverage loss confirmed

### Immediate Next Step

**Apply Phase 1 and Phase 2 fixes first** (transactional integrity + CLI order). These are the minimum safe changes required before any cascade can be trusted to run again.

---

*End of OV2-CLOSE.3A.0 Cascade Regression Audit*
*Rule enforced: NO fixes implemented. NO cascades executed. Diagnosis only.*
