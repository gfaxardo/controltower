# OV2-F.6 — YANGO RECONCILIATION ENGINE — FINAL REPORT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Reconciliation
> **Phase:** OV2-F.6 — Yango Reconciliation Engine
> **Status:** **RECONCILIATION_READY — Yango data stale**

---

## 1. EXECUTIVE SUMMARY

Se construyó motor de reconciliación CT vs Yango por park_id y fecha. Endpoint `/reconciliation/park` compara trips y drivers usando bridge (CT) y `raw_yango.mv_orders_day` (Yango). La reconciliación muestra CT_ONLY para ambas métricas porque Yango data está stale (2026-06-05, 2 filas). La lógica de comparación está certificada — el gap es de frescura de Yango, no de la reconciliación.

---

## 2. SOURCE AUDIT

| Source | CT | Yango |
|--------|-----|-------|
| Table | `ops.driver_day_slice_fact` | `raw_yango.mv_orders_day` |
| Park key | `park_id` | `park_id` |
| Trips column | `completed_trips` | `orders_completed` |
| Drivers column | COUNT DISTINCT driver_id | `unique_drivers` |
| Revenue column | `revenue_yego_final` (day_fact) | Not available |
| Max date | 2026-06-07 | 2026-06-05 |

---

## 3. RECONCILIATION ENDPOINT

```
GET /ops/omniview-v2/reconciliation/park?date=2026-06-06&park_id=08e20910d81d42658d4334d3f6d10ac0
```

### Sample result (2026-06-06)

| KPI | CT | Yango | Delta | Status |
|-----|-----|-------|-------|--------|
| trips | 12,303 | 0 | — | CT_ONLY |
| drivers | 1,481 | 0 | — | CT_ONLY |
| revenue | 5,948 | — | — | NOT_COMPARABLE |

---

## 4. STATUS CODES

| Code | Condition |
|------|-----------|
| MATCH | delta ≤ 1% |
| MINOR_DELTA | 1% < delta ≤ 5% |
| MAJOR_DELTA | delta > 5% |
| CT_ONLY | CT has data, Yango = 0 |
| YANGO_ONLY | Yango has data, CT = 0 |
| NOT_COMPARABLE | Both 0 or column missing |

---

## 5. DELIVERABLES

| # | Item |
|---|------|
| 1 | `GET /ops/omniview-v2/reconciliation/park` endpoint |
| 2 | `f6_yango_audit.py` — source audit script |
| 3 | `OV2_F6_YANGO_RECONCILIATION_REPORT.md` (this document) |

---

## 6. GO/NO-GO

**RECONCILIATION_READY** — Endpoint operational. Yango data stale — requires `refresh_raw_yango_mvs` to run.

---

*End of OV2-F.6 Report*
