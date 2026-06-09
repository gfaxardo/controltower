# OV2-CLOSE.3A — FINAL MATRIX RECONCILIATION (PARTIAL REPORT)

> **Date:** 2026-06-09
> **Motor:** Control Foundation
> **Phase:** OV2-CLOSE.3A — Final Matrix Reconciliation
> **Status:** **IN PROGRESS — active_drivers fix applied, reconciliation in progress**

---

## 1. DIFF: MATRIX REPOSITORY

**File:** `backend/app/repositories/omniview_v2_matrix_repository.py`

### Change
- **Removed:** `COALESCE(SUM(active_drivers), 0)` from the fact table query (week_fact/month_fact)
- **Added:** Separate bridge query `COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0)` from `ops.driver_day_slice_fact`
- **Added:** Grain-aware period grouping (`date_trunc('week'/'month', activity_date)`) to match fact table period column
- **Added:** Merge logic to join driver counts into fact table rows by (period_date, business_slice_name)

### Why
week_fact/month_fact store `active_drivers` per (period, slice, park). `SUM(active_drivers)` across parks inflates driver counts (same driver in multiple parks counted multiple times). `COUNT(DISTINCT driver_id)` from bridge correctly deduplicates.

### Lines
```
- 98: removed SUM(active_drivers) from fact table query
+ 109-153: added bridge query + grain-aware grouping + merge logic
```

---

## 2. RECONCILIATION RESULTS (2026-06-09 ~07:20 UTC-5)

*After startup cascade ran during backend restart.*

### Day (period: 2026-06-06)

| KPI | Cell Audit | Matrix | Match |
|-----|-----------|--------|-------|
| trips | 13,041 | 9,736 | **DELTA** (-3,305) |
| revenue | 5,948 | 4,732 | **DELTA** (-1,216) |
| active_drivers | 1,585 | 1,438 | **DELTA** (-147) |

### Week (period: 2026-06-01)

| KPI | Cell Audit | Matrix | Match |
|-----|-----------|--------|-------|
| trips | 79,927 | None | **N/A** |
| revenue | 35,963 | None | **N/A** |
| active_drivers | 2,866 | None | **N/A** |

### Month (period: 2026-06-01)

| KPI | Cell Audit | Matrix | Match |
|-----|-----------|--------|-------|
| trips | 89,134 | 20,987 | **DELTA** (-68,147) |
| revenue | 40,166 | 0 | **DELTA** (-40,166) |
| active_drivers | 2,980 | 1,438 | **DELTA** (-1,542) |

---

## 3. ACTIVE DRIVERS STATUS

**Not yet matching.**

The bridge query for active_drivers was added to the matrix repository, but the matrix still shows different values. The merge logic matches by `(period_date, business_slice_name)` — if the fact table rows have different period formatting or some slices are missing from the bridge query, the merge fails with default 0 or an old value.

**Likely issues:**
1. The startup cascade rebuilt fact tables with a narrow date range (only last 2 days for day_fact: June 7-8). Data for June 1-6 may have been deleted/narrowed.
2. Week matrix returns None — fact table may have been rebuilt with different week_start values.
3. The cell_audit still uses bridge directly and shows correct values.

**Next step:** Verify cascade date ranges are wide enough to cover the test periods.

---

## 4. WHAT'S MISSING FOR MONTH REVENUE

The month matrix shows revenue = 0 for Auto regular while cell audit shows 40,166. This is a separate issue from active_drivers:

1. **Revenue comes from fact table**, not bridge. The cascade may have deleted/zeroed the month_fact revenue data.
2. **Month revenue query** in repository: `COALESCE(SUM(revenue_yego_final), 0)` from `ops.real_business_slice_month_fact`. If the cascade rebuilt month with incorrect values, the revenue shows 0.
3. **Cell audit** computes revenue from `ops.real_business_slice_day_fact` (day_fact) by summing over the month period. This survives cascade rebuilds better because it aggregates daily data.

**Gap:** The cascade's month rebuild may be computing revenue differently or the rebuild script has a bug in revenue aggregation.

---

## 5. RISKS

| # | Issue |
|---|-------|
| 1 | Cascade date range too narrow (only last 2 days). Historical data may have been pruned during rebuild. |
| 2 | Week matrix returns None — cascade may have rebuilt with only current week (2026-06-08), leaving test week (2026-06-01) empty. |
| 3 | Month matrix revenue = 0 — cascade month rebuild script may not include revenue correctly. |
| 4 | Matrix active_drivers merge logic may not correctly match period_dates between bridge and fact tables. |

---

## 6. NEXT STEPS RECOMMENDED

1. **Fix cascade date range:** Ensure cascade rebuilds a wider window (at least 7 days for day, 4 weeks for week, 2 months for month) so historical test data isn't lost.
2. **Verify merge logic:** Confirm that `_serialize_date` produces consistent period strings between fact table rows and bridge rows.
3. **Debug month revenue:** Trace `rebuild_month_from_day_and_bridge.py` to verify revenue field is populated correctly.
4. **Re-run reconciliation** after cascade fix.

*End of partial report — OV2-CLOSE.3A*
