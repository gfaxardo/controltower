# LG-EXP-GRAIN-1A — Driver Explorer Grain / Duplication Audit

**Date:** 2026-06-13
**Commit base:** d6099657449c7358c4a415fed020c3a9fa1402ed
**Motor:** Growth Machine / Control Foundation
**Phase:** Driver Explorer Grain / Duplication Audit
**Mode:** AUDIT ONLY — NO IMPLEMENTATION

---

## 1. Pre-Check

| # | Question | Answer |
|---|----------|--------|
| 1 | Motor | Growth Machine / Control Foundation |
| 2 | Fase | Driver Explorer Grain / Duplication Audit |
| 3 | Contrato | Serving fact grain, Explorer consistency, assigned program visibility |
| 4 | Tablas (read-only) | explorer_fact, eligibility, state_snapshot |
| 5 | Writer | Ninguno |
| 6 | Freshness | Ninguna (validated: data current) |
| 7 | Endpoint/UI | GET /yego-lima-growth/driver-explorer, Programs tab |
| 8 | Legacy | Ninguno relevante |
| 9 | Riesgos | False diagnosis, premature fix |
| 10 | Rollback | Revertir doc |
| 11 | ACTIVE_SCOPE_CONTRACT | In-scope: Data consistency, Explorer validation |
| 12 | Scope Escalation | AUDIT ONLY |

## 2. Active Scope Contract Result

**IN SCOPE. AUDIT ONLY.** Section 4 includes "Data consistency between Explorer, Programs, Segments, Movement, RNA, Effectiveness."

## 3. Baseline Counts — Duplication Confirmed

### Overall

| Metric | Value |
|--------|-------|
| Total rows | 37,090 |
| Total distinct drivers | 18,545 |
| Duplicate rows | 18,545 (exactly 2x) |

### By Program

| Program | Rows | Distinct Drivers | Duplicates | Ratio |
|---------|------|-----------------|------------|-------|
| PROGRAM_ACTIVE_GROWTH | 30,108 | 15,054 | 15,054 | exactly 2x |
| PROGRAM_14_90 | 5,338 | 2,669 | 2,669 | exactly 2x |
| None | 1,008 | 504 | 504 | exactly 2x |
| PROGRAM_CHURN_PREVENTION | 634 | 317 | 317 | exactly 2x |
| NEW_DRIVER_ONBOARDING | 2 | 1 | 1 | exactly 2x |

**Observation:** Every row count is exactly 2x the distinct driver count. This is not a coincidence.

### Per-Date Analysis

| target_date | Rows | Distinct Drivers | Duplication |
|-------------|------|-----------------|-------------|
| 2026-06-12 | 18,545 | 18,545 | 0% — clean within date |
| 2026-06-11 | 18,545 | 18,545 | 0% — clean within date |

**Key finding:** Each individual date has zero internal duplication. The duplication comes from having TWO dates in the table with the same set of drivers. Every driver appears once on 06-11 and once on 06-12.

### All 18,545 drivers appear in BOTH dates

Total drivers with >1 row: **18,545** (every single driver has exactly 2 rows, one per date). All duplicates are exactly 2 rows, 1 program each (no driver has multiple programs in the table).

### Comparison: Explorer vs Eligibility (06-13)

| Program | Explorer Distinct Drivers (both dates) | Eligible Today | Gap |
|---------|--------------------------------------|----------------|-----|
| ACTIVE_GROWTH | 15,054 | 17,685 | Explorer has fewer (stale labels + cumulative) |
| 14_90 | 2,669 | 2,669 | Exact match (coincidental — Explorer is cumulative) |
| CHURN_PREVENTION | 317 | 7,774 | Explorer has 4% of eligible (stale labels) |

## 4. Explorer Fact Grain

| Dimension | Value |
|-----------|-------|
| Table | `growth.yego_lima_driver_explorer_fact` |
| Primary Key | `(target_date, driver_profile_id)` |
| Grain | One row per driver per target_date |
| Max target_date | 2026-06-12 |
| Min target_date | 2026-06-11 |
| Date count | 2 (both populated with same driver set) |
| Created by migration | `220_lg_exp_1d_driver_explorer_fact.py` |

**Schema (49 columns):** target_date, driver_profile_id, driver_name, phone, park_id, lifecycle, performance_state, retention_state, historical_band, segment, sub_segment, program_code, program_priority, eligibility_reason, is_in_program, rna_priority_band, rna_score, contactable, cancelled_signal, rna_value_tier, rna_momentum, movement_type, movement_from, movement_to, movement_trigger, last_contact_at, last_contact_disposition, last_contact_agent, contact_attempts, assigned_campaign_id, queue_status, opportunity_type, trips_7d, trips_30d, trips_since_anchor, first_trip_at, last_trip_at, days_since_last_trip, activity_trend, new_driver_flag, recoverable_flag, declining_flag, churn_risk_flag, impact_status, baseline_trips, post_contact_trips, trips_delta_after_contact, data_quality, refreshed_at.

## 5. Duplicate Detection Summary

| Check | Result |
|-------|--------|
| Row-level duplicates (same date + same driver)? | NO — PK prevents this |
| Date-level duplication (same driver, different dates)? | YES — all 18,545 drivers in both 06-11 and 06-12 |
| Is per-date data clean? | YES — 0% duplication within each date |
| Is duplication in the table itself? | YES — 2 rows per driver (one per date) |
| Is duplication in the writer/builder? | NO — builder produces one date at a time, clean per run |
| Is duplication in the endpoint query? | PARTIALLY — endpoint auto-resolves to MAX(target_date) but stats may aggregate across dates |

## 6. Writer / Builder Audit

| Component | Detail |
|-----------|--------|
| Builder | `build_driver_explorer_fact(target_date)` in `yego_lima_driver_explorer_fact_service.py:72` |
| Operation | UPSERT via `INSERT ... ON CONFLICT (target_date, driver_profile_id) DO UPDATE` |
| Source | `driver_state_snapshot` + `program_eligibility_daily` with `DISTINCT ON (driver_profile_id)` |
| Date filter | Builds one date at a time: `WHERE ds.snapshot_date = %(target_date)s` |
| DELETE before INSERT? | NO — no DELETE exists anywhere in the codebase for this table |
| Legacy writer? | None found |
| Duplicate risk | LOW per-run (DISTINCT ON + ON CONFLICT). Risk is in running the builder for multiple dates without pruning old dates. |
| Scheduler | Manual via CLI `build_driver_explorer_fact.py`. Not in autonomous tick cascade. |

**Assessment:** The builder is clean. It correctly produces one row per driver per date. The duplication arises because the builder was run for TWO dates (06-11 and 06-12) and old data was not cleaned up.

## 7. Endpoint Audit

| Component | Detail |
|-----------|--------|
| Router | `GET /yego-lima-growth/driver-explorer` in `yego_lima_driver_explorer.py:22` |
| Service | `search_driver_explorer()` in `yego_lima_driver_explorer_service.py:28` |
| Date resolution | `SELECT MAX(target_date)` when `target_date` param is None |
| Count method | `COUNT(*)` (equivalent to `COUNT(DISTINCT driver_profile_id)` for single-date query due to PK) |
| Stats function | `get_explorer_fact_stats()` at line 403 — aggregates by program/segment/lifecycle |
| Stats date filter | Depends on how called. If `target_date` not passed, resolves to MAX. If called without resolution, aggregates over all dates. |

**Assessment:** The endpoint correctly defaults to `MAX(target_date)` = 06-12 when no date is specified. However, if the UI or the Programs Summary serving fact calls stats without proper date filtering, it would see 2x the actual counts.

## 8. Root Cause Analysis

### Why the x2 duplication exists

1. The Explorer fact table was built for two dates: **2026-06-11** and **2026-06-12**
2. Both builds used the same source (state_snapshot + eligibility) and produced the same 18,545 drivers
3. The builder is idempotent per-date (UPSERT, no DELETE), but it does NOT prune old dates
4. The table accumulates all dates by design (PK = target_date + driver_profile_id)
5. Old data is NOT automatically cleaned up

### Why the UI shows 2x

The endpoint defaults to `MAX(target_date)` = 06-12, which should return only 15,054 ACTIVE_GROWTH drivers. But the UI shows 30,108 (2x). This suggests the UI or the Programs Summary serving fact is NOT using the date-resolved endpoint, or is aggregating stats across all dates in the table.

### Possible UI query paths causing 2x

| Path | Description | Likely? |
|------|-------------|---------|
| UI bypasses endpoint date filter | UI calls `get_explorer_fact_stats()` without passing `target_date`, and the stats function doesn't auto-resolve to MAX date | HIGH |
| Programs Summary serving fact | The `programs_summary` fact_type in `yego_lima_serving_fact` might aggregate Explorer data across all dates | POSSIBLE |
| Client-side aggregation | UI receives per-date data from endpoint but sums across dates client-side | LOW |
| Legacy dashboard component | Old UI component (UI1A) uses a different query path | POSSIBLE |

## 9. Explorer vs Programs Comparison (Cross-Audit)

This audit confirms a finding from LG-PROGRAM-GOV-1A:

| Program | Explorer Rows (2 dates) | Explorer Drivers (unique) | Eligible Today | UI Expected (1 date) |
|---------|------------------------|--------------------------|----------------|---------------------|
| ACTIVE_GROWTH | 30,108 | 15,054 | 17,685 | 15,054 |
| 14_90 | 5,338 | 2,669 | 2,669 | 2,669 |
| CHURN_PREVENTION | 634 | 317 | 7,774 | 317 |

The UI counts showing 30,108 / 5,338 / 634 are the 2-date aggregates. The correct single-date counts should be 15,054 / 2,669 / 317.

## 10. UI Validation Targets

| # | Validation | Expected Correct | Current (2x) |
|---|-----------|-----------------|--------------|
| 1 | Explorer → Program ACTIVE_GROWTH count | 15,054 | 30,108 |
| 2 | Explorer → Program 14_90 count | 2,669 | 5,338 |
| 3 | Explorer → Program CHURN_PREVENTION count | 317 | 634 |
| 4 | Explorer → search driver 000150dc | 2 rows (one per date) | Verify dedup |
| 5 | Explorer → date filter = 2026-06-12 only | 15,054 / 2,669 / 317 | Should show correct |

## 11. Verdict

### **LG_EXP_GRAIN_1A_DUPLICATION_CONFIRMED**

**Classification: DATE-LEVEL DUPLICATION, NOT ROW-LEVEL.**

- The table structure is correct: PK `(target_date, driver_profile_id)`, clean per-date
- The builder is correct: one date at a time, UPSERT, `DISTINCT ON`
- The duplication is caused by:
  1. **Data**: Two dates (06-11, 06-12) exist in the table with the same driver set
  2. **Query**: UI/endpoint aggregation does not filter to latest date only
- This is **not** a writer bug, **not** a constraint bug, **not** a PK bug
- This is a data retention + query filtering issue

---

## LG-EXP-GRAIN-1B — Latest-Date Stats Fix (IMPLEMENTED)

**Date:** 2026-06-13
**Commit:** (pending)

### Root Cause Confirmed

`get_explorer_fact_stats()` in `yego_lima_driver_explorer_fact_service.py:403` did not default to `MAX(target_date)` when `target_date` was None. Instead, it aggregated stats across ALL dates in the table by using an empty `date_filter`. The Explorer search endpoint (`search_driver_explorer()`) correctly resolved to MAX(target_date), but the stats function did not.

### Fix Applied

**File:** `backend/app/services/yego_lima_driver_explorer_fact_service.py`
**Function:** `get_explorer_fact_stats()`

Added date resolution before building stats queries:
```python
if target_date is None:
    cur.execute(f"SELECT MAX(target_date) AS mx FROM {TABLE_FACT}")
    row = cur.fetchone()
    if row and row.get("mx"):
        target_date = str(row["mx"])
stats["resolved_target_date"] = target_date
```

The function now defaults to `MAX(target_date)` = 2026-06-12. Explicit `target_date` parameters are still respected.

### What was NOT done

- No DELETE of old rows (historical data preserved)
- No builder changes (builder is correct per-date)
- No writer changes
- No PK or constraint changes
- No Program Engine changes
- No eligibility/segmentation changes
- No UI changes
- No DB writes

### Validation

| Program | Before (2x) | After Fix | Expected | Result |
|---------|------------|-----------|----------|--------|
| ACTIVE_GROWTH | 30,108 | 15,054 | 15,054 | PASS |
| 14_90 | 5,338 | 2,669 | 2,669 | PASS |
| CHURN_PREVENTION | 634 | 317 | 317 | PASS |
| None | 1,008 | 504 | 504 | PASS |

- `resolved_target_date`: 2026-06-12
- Explicit date (2026-06-11): Works correctly, returns that date's stats
- Compile check: PASS

### Risks Remaining

- `total_rows` in stats response still shows all-time total (37,090). This is informational — the per-program counts are correct.
- If new dates are added without pruning old ones, `max_date` will advance but old data accumulates. Consider adding retention policy (P1 backlog).

## 12. Remediation Plan (Updated)

| Priority | Action | Status |
|----------|--------|--------|
| P0 | Ensure `get_explorer_fact_stats()` defaults to MAX(target_date) | **DONE** (1B fix) |
| P0 | Delete old date rows | Pending (optional — fix makes this less critical) |
| P1 | Add builder cleanup for old dates | Pending |
| P2 | Document grain in GROWTH_MACHINE_CANONICAL.md | Pending |

---

## LG-EXP-GRAIN-1C — UI Checkpoint / total_rows Semantics (IMPLEMENTED)

**Date:** 2026-06-13
**Commit:** (pending)

### API Stats Evidence (Post-1B + 1C)

| Field | Value | Semantics | Safe for UI? |
|-------|-------|-----------|-------------|
| `resolved_target_date` | 2026-06-12 | Active date used for breakdowns | YES |
| `total_rows` | 37,090 | ALL-TIME metadata (all dates) | NO — informational only |
| `distinct_drivers` | 18,545 | ALL-TIME distinct drivers | NO — spans multiple dates |
| **`resolved_date_total_rows`** | **18,545** | Active date total rows | **YES — UI safe** |
| **`resolved_date_distinct_drivers`** | **18,545** | Active date unique drivers | **YES — UI safe** |
| `by_program` | 15,054 / 2,669 / 317 / 504 | Latest date counts | YES |
| `by_lifecycle` | Per-lifecycle counts | Latest date only | YES |

### API List/Pagination Evidence

| Filter | API Total | Target Date | Status |
|--------|-----------|-------------|--------|
| ACTIVE_GROWTH | 15,054 | 2026-06-12 | PASS |
| CHURN_PREVENTION | 317 | 2026-06-12 | PASS |
| PROGRAM_14_90 | 2,669 | 2026-06-12 | PASS |
| No filter | BLOCKED (NO_FILTER) | N/A | PASS |
| Explicit 06-11 + ACTIVE_GROWTH | 15,054 | 2026-06-11 | PASS |

### total_rows Conclusion

`total_rows=37,090` is all-time metadata. It is NOT used by any frontend component directly (confirmed by grep: no UI reads this field from the explorer stats endpoint). However, to prevent future misuse, the API now exposes:

- **`resolved_date_total_rows=18,545`**: The active-date row count, matching the sum of `by_program` counts. Safe for UI use.
- **`resolved_date_distinct_drivers=18,545`**: Unique drivers in the active date.

`total_rows` and `distinct_drivers` are preserved as all-time metadata (backward compatible).

### API Field Contract

Any UI component displaying a "total drivers" or "total rows" count for Driver Explorer MUST use `resolved_date_total_rows` (not `total_rows`). `total_rows` is all-time metadata only.

### Files Modified

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_driver_explorer_fact_service.py` | Added `resolved_date_total_rows` and `resolved_date_distinct_drivers` fields |

### 1C Veredict: **LG_EXP_GRAIN_1C_PASS**

- API stats correct for latest date
- API list/pagination correct
- No UI component misuses `total_rows`
- `resolved_date_total_rows` added for defensive API hardening
- No DELETE, no Program Engine, no UI changes

### 1C Decision: **GO**

---

*1C fix applied. No historical data deleted.*
