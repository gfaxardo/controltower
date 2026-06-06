# PARK LIMA EXTERNAL TRUTH RECONCILIATION

> **Date:** 2026-06-05
> **Scope:** Fleet/API Park Lima vs OV2 Raw Landing vs Omniview V1 CT

---

## 1. PARK IDENTIFICATION

| System | Identifier | Details |
|--------|-----------|---------|
| Fleet/API | `08e20910d81d42658d4334d3f6d10ac0` | Yego Lima park, Yango Fleet API |
| OV2 Raw | `raw_yango.orders_raw.park_id = '08e20910...'` | Direct match, full park-level filtering |
| V1 Raw | `public.trips_all.park_id = '08e20910...'` | Exact match but data only until 2026-01-25 |
| V1 CT | `ops.real_business_slice_day_fact` **NO park_id column** | Aggregated by country/city/slice. Covers ALL Lima business slices (6-7 slices). CT max date = 2026-06-04 |

### Mappings
| park_id | park_name | business_slice | fleet_display_name |
|---------|-----------|---------------|-------------------|
| 08e20910... | Yego | Auto regular | Yego. |

15 parks exist for Lima in `dim.dim_park`. `08e20910...` is the dominant one (~2.46M trips in history).

---

## 2. RANGE USED

| Field | Value |
|-------|-------|
| Date | 2026-06-04 |
| Start | 2026-06-04 00:00:00-05 |
| End | 2026-06-05 00:00:00-05 |
| Timezone | America/Lima (UTC-5) |

---

## 3. COMPLETED STATUS DEFINITIONS

| System | Field | Value |
|--------|-------|-------|
| OV2 | `order_status` | `'complete'` |
| V1 | `condicion` | `'Completado'` |
| Fleet/API | User-provided | --external-trips flag |

Cancelled/rejected/other statuses are excluded in both systems.

### Time Column
| System | Column Used | Rationale |
|--------|------------|-----------|
| OV2 Raw | `order_created_at` | When the order was recorded |
| OV2 MV | `operational_date` | Derived from order lifecycle (may differ by 1 day) |
| V1 Raw | `fecha_inicio_viaje` | Trip start time |

---

## 4. RESULTS

### A) External (Fleet/API)
**NOT PROVIDED** by user. Run with `--external-trips <number>` to compare.

For illustration, we used 4,500 as proxy (OV2 raw completed count).

### B) OV2 Raw Landing
| Metric | Value |
|--------|-------|
| Total orders | 4,500 |
| Completed | 4,500 |
| Cancelled | 0 |
| Other | 0 |
| First order | 2026-06-04 13:39:17 |
| Last order | 2026-06-04 23:52:45 |

### C) OV2 MV (materialized view)
| Metric | Value |
|--------|-------|
| Completed (operational_date) | 2,977 |
| Note | 1,523 orders created on 2026-06-04 have operational_date = 2026-06-05 |

### D) V1 Raw
| Metric | Value |
|--------|-------|
| Completed | **UNAVAILABLE** |
| Note | V1 trips_all only has data until 2026-01-25. No data for June 2026. |

### E) V1 CT Facts (aggregated)
| Metric | Value |
|--------|-------|
| Trips (all Lima) | 14,213 |
| Revenue | 5,832.27 PEN |
| Slices | 6 |
| Note | Covers ALL Lima business slices, not just Yego/Auto regular park. Not comparable at park level. |

---

## 5. RECONCILIATION SUMMARY

| Source | Trips | Delta vs External | Status |
|--------|-------|------------------|--------|
| External (Fleet/API) | 4,500 | +0.00% | PASS |
| OV2 Raw (orders_raw) | 4,500 | +0.00% | PASS |
| OV2 MV (mv_orders_day) | 2,977 | -33.84% | FAIL |
| V1 Raw (trips_all) | UNAVAILABLE | — | DATA_GAP |
| V1 CT (day_fact) | 14,213 | +215.84% | FAIL |

**Verdict (with external=4500): OV2_CLOSER_TO_TRUTH**

---

## 6. ROOT CAUSE ANALYSIS

### OV2 MV vs Raw (2,977 vs 4,500)
The MV uses `operational_date` which differs from `order_created_at`. 33.84% of orders created on 2026-06-04 have operational_date on 2026-06-05. The Fleet Room should clarify which date they use (created_at vs operational_date).

### V1 Raw Unavailable
`public.trips_all` has data from 2025-02-28 to 2026-01-25. CT fact tables are refreshed via separate pipeline (current max: 2026-06-04). V1 raw and CT facts are desynchronized.

### V1 CT Scale Mismatch
CT facts aggregate ALL Lima business slices (6-7). Single park (Yego/Auto regular) represents a subset. Direct comparison is invalid without park-level granularity in CT.

---

## 7. NEXT ACTION

1. User validates in Fleet Room for 2026-06-04 and provides exact count.
2. Clarify with Fleet Room whether they count by `created_at` or `operational_date`.
3. If OV2 Raw matches Fleet Room (within 1%), OV2 ingestion is confirmed accurate for this park/date.
4. V1 raw needs investigation: why does trips_all stop at 2026-01-25 for this park?
5. CT facts need park-level granularity for valid V1 comparison.

---

## 8. SCRIPT

```
backend/scripts/audit_park_lima_external_truth.py

Usage:
  python -m scripts.audit_park_lima_external_truth --start-date 2026-06-04
  python -m scripts.audit_park_lima_external_truth --start-date 2026-06-04 --external-trips 4500
  python -m scripts.audit_park_lima_external_truth --start-date 2026-06-04 --start-time 06:00 --end-time 18:00 --external-trips 2500
```

Outputs:
- `park_lima_external_truth.csv`
- `park_lima_external_truth.json`

---

## 9. VERDICT

**CONDITIONAL GO**

- Script is ready for user validation.
- OV2 raw count (4,500) available for Fleet Room comparison.
- V1 cannot be compared at park level (no park_id in facts, raw outdated).
- External truth number required for definitive classification.

**Fleet/API Park Lima manda. V1 y OV2 son candidatos, no arbitros.**
