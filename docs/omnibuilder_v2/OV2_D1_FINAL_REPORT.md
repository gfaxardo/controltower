# OV2-D.1 — FINAL REPORT: SLICE GOVERNANCE CERTIFICATION

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Slice Governance
> **Status:** **SLICE_GOVERNANCE_CERTIFIED**

---

## 1. SLICE INVENTORY

**8 business slices found across all 3 grains (day/week/month):**

| Slice | Trips (day) | Revenue (day) | Day | Week | Month | Status |
|-------|-------------|---------------|-----|------|-------|--------|
| Auto regular | 11,035,051 | 2,003,853,675 | X | X | X | CERTIFIED |
| Taxi Moto | 1,486,901 | 238,883,418 | X | X | X | CERTIFIED |
| Tuk Tuk | 250,354 | **NaN** | X | X | X | PARTIAL (no revenue) |
| PRO | 284,875 | 87,766 | X | X | X | CERTIFIED |
| YMA | 188,263 | 80,444 | X | X | X | CERTIFIED |
| Delivery | 95,045 | 28,985 | X | X | X | CERTIFIED |
| Carga | 56,838 | 107,560,884 | X | X | X | CERTIFIED |
| Delivery moto | 36,449 | 7,070,851 | X | X | X | CERTIFIED |

---

## 2. INCONSISTENCIES

| # | Issue | Severity |
|---|-------|----------|
| 1 | **Tuk Tuk has NaN revenue** across all grains | HIGH — revenue field is NULL in source data |
| 2 | Week data last refreshed 2026-04-20 (day has data through 2026-06-05) | MEDIUM — refresh gap |
| 3 | 2 slices were not in initial OV2 assumption (Delivery moto, Taxi Moto) | LOW — documentation gap |

---

## 3. SLICE DEFINITIONS

Slices are defined in `ops.real_business_slice_day_fact` via a mapping from fleet/subfleet to business_slice_name. The mapping logic is in the `v_real_trips_enriched_base` view (migration 116). Each trip's `tipo_servicio` or fleet classification is mapped to a `business_slice_name` at ingestion time.

---

## 4. MATRIX INTEGRATION

The `/matrix` endpoint extracts row labels from `business_slice_name` in the CT day_fact table. All 8 slices appear as rows in the matrix. YANGO_API_RAW shows a single "Lima Fleet" row (not a certified slice).

---

## 5. CERTIFICATION

| Classification | Slices | Reason |
|---------------|--------|--------|
| CERTIFIED | 7 | All have trips + revenue + drivers across all grains |
| PARTIAL | 1 | Tuk Tuk — no revenue data (NaN in source) |
| BLOCKED | 0 | — |
| UNCLEAR | 0 | — |

**Global: SLICE_GOVERNANCE_CERTIFIED** — 7 of 8 slices are fully certified. Tuk Tuk revenue gap is documented.

---

## 6. RECOMMENDED NEXT PHASE

OV2-D.2 — Plan vs Real V2 Integration. Slices are governed and stable.

---

## 7. BUILD

| Check | Result |
|-------|--------|
| Audit script | All 8 slices inventoried, anomalies documented |
| V1 intact | No changes to V1 |
| UI not touched | No changes to UI |
