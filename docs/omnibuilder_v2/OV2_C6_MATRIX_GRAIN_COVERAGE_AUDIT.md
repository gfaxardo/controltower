# OV2-C.6 — MATRIX GRAIN COVERAGE AUDIT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix API Certification

---

## 1. COVERAGE MATRIX

| Source | hour | day | week | month |
|--------|------|-----|------|-------|
| CT_TRIPS_2026 | SUPPORTED_BY_ROLLUP | **SUPPORTED** | SUPPORTED_BY_ROLLUP | SUPPORTED_BY_ROLLUP |
| YANGO_API_RAW | NOT_SUPPORTED | **SUPPORTED** | NOT_SUPPORTED | NOT_SUPPORTED |

---

## 2. CT_TRIPS_2026 DETAIL

| Grain | Table | Status | Notes |
|-------|-------|--------|-------|
| hour | `ops.real_business_slice_hour_fact` | SUPPORTED_BY_ROLLUP | Table exists (migration 099). Query pattern identical to day. Not yet wired in repository. |
| day | `ops.real_business_slice_day_fact` | **SUPPORTED** | Active in repository. Production data available. |
| week | `ops.real_business_slice_week_fact` | SUPPORTED_BY_ROLLUP | Table exists (migration 119). Same columns as day. Query `week_start` instead of `trip_date`. |
| month | `ops.real_business_slice_month_fact` | SUPPORTED_BY_ROLLUP | Table exists (migration 116). Query `month` instead of `trip_date`. Column names differ slightly (e.g., `completados_por_hora`). |

### Effort to support CT week/month:
- Add grain table mapping in `_grain_table()` → already done
- Wire `build_columns()` to generate week/month labels → already done
- Repository queries use same pattern → **ZERO code changes needed** — just test

---

## 3. YANGO_API_RAW DETAIL

| Grain | Status | Notes |
|-------|--------|-------|
| hour | NOT_SUPPORTED | No `raw_yango.mv_orders_hour` exists. Design exists in OV2-C.0. Requires migration. |
| day | **SUPPORTED** | Active via `mv_orders_day` + `mv_revenue_day`. |
| week | NOT_SUPPORTED | No week MV. Could be implemented as `SELECT ... GROUP BY date_trunc('week', order_date)` from `orders_raw`. |
| month | NOT_SUPPORTED | No month MV. Same approach as week. |

### Effort to support Yango week/month:
- **Option A:** Create `mv_orders_week`, `mv_revenue_week` MVs (1 migration)
- **Option B:** Query `orders_raw` directly with `GROUP BY date_trunc('week', order_date)` (no migration, slower)
- **Recommended:** Option B for week (trivial), Option A for month (pre-aggregated)

---

## 4. REPOSITORY READINESS

Current `get_matrix_data()` dispatches by source + grain. The `_grain_table()` function already maps all CT grains:

```python
CT_GRAIN_TABLES = {
    "hour": ("ops.real_business_slice_hour_fact", "hour_start"),
    "day": ("ops.real_business_slice_day_fact", "trip_date"),
    "week": ("ops.real_business_slice_week_fact", "week_start"),
    "month": ("ops.real_business_slice_month_fact", "month"),
}
```

### To activate CT week/month: **Change 0 lines of code.** Just test.
### To activate CT hour: **Change 0 lines of code.** Just test with `&grain=hour`.
### For Yango week/month: **NOT_SUPPORTED** returned by guard clause.

---

## 5. CLASSIFICATION SUMMARY

| Classification | Count | Items |
|---------------|-------|-------|
| SUPPORTED | 2 | CT day, Yango day |
| SUPPORTED_BY_ROLLUP | 3 | CT hour, CT week, CT month |
| NOT_SUPPORTED | 3 | Yango hour, Yango week, Yango month |
| BACKLOG | 0 | — |

---

## 6. NEXT STEPS

| Priority | Action | Effort |
|----------|--------|--------|
| HIGH | Test CT week/month with existing repository | 0 code changes |
| MEDIUM | Test CT hour with existing repository | 0 code changes |
| MEDIUM | Create Yango week MV or direct query | 1 migration or query change |
| LOW | Create Yango month MV | 1 migration |
| BACKLOG | Create Yango hour MV | 1 migration (design in OV2-C.0) |

---

## 7. VERDICT

CT_TRIPS_2026 has **full grain readiness** — hour, day, week, month tables all exist and share identical query patterns. YANGO_API_RAW is **day-only** with clear paths to week/month via rollup queries.
