# OV2-F.6A — YANGO SOURCE RECOVERY + RECONCILIATION RECERTIFICATION — REPORT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Reconciliation
> **Phase:** OV2-F.6A — Yango Source Freshness Recovery
> **Status:** **YANGO_RECONCILIATION_PARTIAL — Source stale, endpoint correct**

---

## 1. EXECUTIVE SUMMARY

El motor de reconciliación es correcto. El problema es que la fuente Yango (`raw_yango.mv_orders_day`) está stale (2026-06-05, 2 filas). La ingesta Yango API no está corriendo. La reconciliación correctamente reporta CT_ONLY.

---

## 2. YANGO SOURCE AUDIT

| Table | Max Date | Rows | Status |
|-------|----------|------|--------|
| `raw_yango.mv_orders_day` | 2026-06-05 | 2 | STALE |
| `raw_yango.orders_raw` | Unknown | Unknown | Source for MV |
| Yango API ingestion | Not running | — | BLOCKED |

---

## 3. MV REFRESH RESULT

```
python -m scripts.refresh_raw_yango_mvs --mv mv_orders_day
Result: OK (2 rows, 2.8s)
```

MV refresh succeeded but source data is empty. The MV reads from `raw_yango.orders_raw` which needs to be populated by the Yango Fleet API ingestion pipeline.

---

## 4. RECONCILIATION RESULT (2026-06-06, Lima main park)

| KPI | CT | Yango | Status | Reason |
|-----|-----|-------|--------|--------|
| trips | 12,303 | 0 | CT_ONLY | Yango source stale |
| drivers | 1,481 | 0 | CT_ONLY | Yango source stale |
| revenue | 5,948 | — | NOT_COMPARABLE | Yango revenue not available |

---

## 5. SOURCE DATE ALIGNMENT

| Source | Max Date | Target (D-1) | Status |
|--------|----------|-------------|--------|
| CT bridge | 2026-06-07 | 2026-06-07 | READY |
| Yango MV | 2026-06-05 | — | STALE (D-3) |
| Yango API | Not running | — | BLOCKED |

---

## 6. FRESHNESS OBSERVATORY

Current observatory (`/freshness-observatory`) does NOT include Yango layers. To add: `yango_orders_max_date`, `yango_freshness_status`, `reconciliation_readiness`.

---

## 7. REQUIRED TO UNLOCK

1. Run Yango Fleet API ingestion (orders, revenue, drivers)
2. Refresh `raw_yango.mv_orders_day` after ingestion
3. Re-run reconciliation
4. Add Yango to freshness observatory

---

## 8. CLASSIFICATION

### YANGO_RECONCILIATION_PARTIAL

- Reconciliation endpoint: READY ✅
- CT side: READY ✅
- Yango side: STALE ❌
- Source alignment: FAIL ❌

---

*End of OV2-F.6A Report*
