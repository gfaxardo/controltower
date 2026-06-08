# OV2-F.5 — YANGO RECONCILIATION READINESS

> **Date:** 2026-06-08
> **Status:** **PARTIAL**

---

## 1. CT SIDE READINESS

| KPI | Day | Week | Month | Source |
|-----|-----|------|-------|--------|
| trips | ✅ | ✅ | ✅ | bridge→facts |
| revenue | ✅ | ✅ | ✅ | day_fact (preserved) |
| drivers | ✅ | ✅ | ✅ | bridge COUNT DISTINCT |
| park_id | ✅ | ✅ | ✅ | bridge.park_id |

## 2. YANGO SIDE READINESS

| KPI | Source | Status |
|-----|--------|--------|
| orders (trips) | `raw_yango.mv_orders_day` | ✅ |
| revenue | `raw_yango.mv_revenue_day` | ✅ |
| drivers | `raw_yango.mv_driver_profiles_snapshot` | ✅ |
| park_id | `raw_yango` (park filter) | ✅ |

## 3. RECONCILIATION KEY

```
CT: ops.driver_day_slice_fact WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
Yango: raw_yango.mv_orders_day WHERE park_id = '08e20910d81d42658d4334d3f6d10ac0'
```

Both sides use the same park_id. Direct comparison possible.

## 4. WHAT EXISTS

| Component | Status |
|-----------|--------|
| Reconciliation SQL defined (F.1) | ✅ |
| Both sources have matching keys | ✅ |
| Reconciliation endpoint | ❌ Not built |
| Reconciliation storage table | ❌ Not built |
| UI reconciliation badge | ❌ Not built |

## 5. VERDICT

**PARTIAL** — Data is available on both sides. SQL design exists. Endpoint and storage not implemented.

---

*End of Yango Reconciliation Readiness*
