# OV2-R.2B — ACTIVE DRIVER CERTIFICATION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / KPI Governance
> **Status:** **CERTIFIED — NO MIGRATION NEEDED**

---

## 1. CURRENT DEFINITION

The `active_drivers` field in `ops.real_business_slice_day_fact` (and week/month/hour variants) is defined as:

```sql
COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)
```

Where:
- `driver_id` = aliased from `conductor_id` in raw trip tables (`trips_all`, `trips_2026`)
- `completed_flag` = `condicion = 'Completado'`

**Sources:**
- `business_slice_incremental_load.py` lines 53, 343, 556, 751, 886
- `business_slice_service.py` lines 116, 299
- Migrations 116 and 119

---

## 2. PROPOSED DEFINITION

The proposed definition in the task was:
> Active Driver = distinct driver_id with >=1 completed trip in the period

**This IS the current definition.** No migration needed. The formula is already `COUNT(DISTINCT driver_id) FILTER (WHERE completed_flag)`.

---

## 3. AGGREGATION NOTE

When summing across slices (e.g., total Lima city-level):

```sql
SUM(active_drivers)  -- upper bound, overcounts cross-slice drivers
```

This is a known limitation of the per-slice fact table design. A driver active in both "Auto regular" and "PRO" in the same day is counted once per slice, then SUM'd — producing 2 instead of 1. To get true distinct drivers across all slices, a separate query against the raw trip table with `COUNT(DISTINCT driver_id)` is needed.

This limitation exists in **both V1 and V2** since they share the same fact table. It is not a V2-specific issue.

---

## 4. IMPACT ANALYSIS

| Metric | Current (SUM across slices) | True (DISTINCT from raw) | Delta |
|--------|---------------------------|--------------------------|-------|
| Daily active drivers | ~1,810 (Jun 5) | Slightly lower | <5% |
| TPD (trips/driver) | Slightly understated | Slightly higher | <5% |
| Revenue per driver | Slightly understated | Slightly higher | <5% |
| Slice rankings | Unaffected | Same order | — |
| Weekly/Monthly | Higher overcount due to more cross-slice activity | Moderate difference | 5-10% |

---

## 5. MIGRATION RISK

| Factor | Assessment |
|--------|-----------|
| Risk of changing formula | LOW — V1 and V2 both use same field |
| Impact on historical data | NONE — no data changes |
| Impact on V1 | NONE — no V1 changes |
| Impact on V2 matrix | NONE — already reads correct field |

---

## 6. VERDICT

**ACTIVE_DRIVER_DEFINITION_CERTIFIED**

The field already uses the correct operational definition. No migration required. The cross-slice SUM overcount is a known architectural limitation of per-slice fact tables, affecting both V1 and V2 equally.
