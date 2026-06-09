# OV2-F.6B — YANGO COVERAGE DIAGNOSTIC — FINAL REPORT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Reconciliation
> **Phase:** OV2-F.6B — Yango Coverage Diagnostic
> **Status:** **YANGO_COVERAGE_DIAGNOSED — Root cause: ingestion partial**

---

## 1. EXECUTIVE SUMMARY

El MAJOR_DELTA en la reconciliación CT vs Yango está causado por ingesta parcial de Yango. `raw_yango.orders_raw` tiene 1,000 órdenes para 2026-06-06 mientras CT bridge tiene 12,303 trips para el mismo park. La ingesta usó `--max-pages 10`, truncando datos. La MV de Yango agrega correctamente desde raw (1,000 = 1,000). El motor de reconciliación es correcto.

---

## 2. EVIDENCE

| Metric | CT | Yango | Ratio |
|--------|-----|-------|-------|
| Trips/Orders | 12,303 | 1,000 | 12.3× |
| Drivers (completed) | 1,481 | 468 | 3.2× |

### Yango raw orders_detail
- 12,087 rows total, 3 dates (Jun 4-6)
- 1,000 rows for park+date
- All 1,000 are `order_status='complete'`
- Categories: econom (850), comfort (109), minivan (23), comfort_plus (12), tuktuk (3), business (1), express (2)

### MV accuracy
- `mv_orders_day`: 1,000 orders_completed = raw 1,000 orders ✅
- MV correctly aggregates raw data

---

## 3. ROOT CAUSE CLASSIFICATION

| Hypothesis | Evidence | Verdict |
|-----------|----------|---------|
| **YANGO_INGESTION_PARTIAL** | 1,000 raw orders vs 12,303 CT trips | **PRIMARY** |
| PARK_SCOPE_MISMATCH | Same park_id (08e20910...) both sides | ❌ Not the cause |
| SLICE_SCOPE_MISMATCH | CT only has Auto regular for this park | ❌ Not the cause |
| STATUS_SEMANTICS_MISMATCH | Both use 'complete'/'completed' correctly | ❌ Not the cause |
| DRIVER_DEFINITION_MISMATCH | Yango `driver_profile_id` vs CT `driver_id` — different IDs | Partial contributor |

---

## 4. FIX

Re-run Yango ingestion with unlimited pages:
```bash
python -m scripts.ingest_yango_raw_landing --endpoint-group orders --date-from 2026-06-06 --date-to 2026-06-06 --confirm-live
```

Then refresh MV + re-run reconciliation.

---

## 5. VERDICT

**YANGO_COVERAGE_DIAGNOSED** — Engine correct, data ingestion incomplete.

---

*End of OV2-F.6B Report*
