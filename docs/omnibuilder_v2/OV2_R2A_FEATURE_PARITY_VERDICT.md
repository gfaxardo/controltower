# OV2-R.2A — V1 VS V2 FEATURE PARITY VERDICT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Render Reconciliation
> **Verdict:** **FEATURE_PARITY_PASS**

---

## 1. RECONCILIATION RESULTS

| Classification | Count | % |
|---------------|-------|---|
| MATCH (≤0.5%) | 274 | 99.3% |
| MINOR_DELTA (≤2%) | 0 | 0% |
| MAJOR_DELTA (>2%) | 2 | 0.7% |
| **Total** | **276** | |

---

## 2. MAJOR DELTAS — EXPLAINED

Both MAJOR_DELTAs are **Tuk Tuk revenue = NaN** in both V1 and V2:

| Grain | Period | Slice | Metric | V1 | V2 | Cause |
|-------|--------|-------|--------|-----|-----|-------|
| week | 2026-03-23 | Tuk Tuk | revenue | NaN | NaN | Source data has NULL revenue_yego_final |
| month | 2026-03-01 | Tuk Tuk | revenue | NaN | NaN | Same |

**These are NOT V2 bugs.** Both V1 and V2 read from the same table and show the same NULL value. The revenue gap is in the source data, documented in OV2-D.1 Slice Governance.

---

## 3. WHAT COINCIDES

| KPI | Day | Week | Month |
|-----|-----|------|-------|
| trips/orders | MATCH | MATCH | MATCH |
| revenue | MATCH | MATCH | MATCH |
| active_drivers | MATCH | MATCH | MATCH |
| avg_ticket | MATCH | — | — |
| trips_per_driver | MATCH | — | — |

---

## 4. WHAT DOESN'T COINCIDE

Nothing. V1 and V2 share the same serving facts table. All divergences are NULLs propagated identically from the source.

---

## 5. BACKLOG REGISTERED

**Active Driver Definition Review** — registered in `OV2_BACKLOG_KPI_DEFINITION_GOVERNANCE.md`. The current `active_drivers` field uses `SUM()` across slices (may double-count drivers active in multiple slices). A `COUNT(DISTINCT driver_id)` definition is proposed for OV2-R.2B.

---

## 6. VERDICT

**FEATURE_PARITY_PASS**

V2 renders exactly the same values as V1 across 276 cell comparisons (day/week/month × 6 slices × 5 KPIs). The 2 NaN deltas are source data issues, not V2 rendering issues. Gonzalo sees the same numbers in both V1 and V2.

---

## 7. BUILD

| Check | Result |
|-------|--------|
| Reconciliation script | 276 comparisons, 99.3% MATCH |
| V1 intact | No V1 code modified |
| UI not touched | No UI changes |
