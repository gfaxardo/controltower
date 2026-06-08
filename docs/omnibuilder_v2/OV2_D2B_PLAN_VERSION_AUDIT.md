# OV2-D.2B — PLAN VERSION AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Plan vs Real
> **Status:** AUDIT COMPLETE

---

## 1. PLAN VERSIONS

| Version | Rows | Period | Status |
|---------|------|--------|--------|
| `e2e_20260526_165110` | 684 | 2026-01 → 2026-12 | **LATEST** (current) |
| `unified_fresh_1779825863` | 684 | 2026-01 → 2026-12 | Previous |
| `ruta27_2026_04_15` through `ruta27_2026_04_21` | 360 each | 2026-01 → 2026-12 | Historical |
| `ruta27_v2026_01_17`, `ruta27_v2026_01_23` | 312 each | 2026-01 → 2026-12 | Historical |

**Total versions:** 12
**Active version:** `e2e_20260526_165110`

---

## 2. COVERAGE BY COUNTRY

| Country | Rows | Cities | Months |
|---------|------|--------|--------|
| CO (Colombia) | 3,224 | 9 | 12 |
| PE (Peru) | 1,648 | 3 | 12 |

---

## 3. COVERAGE BY CITY (Peru)

| City | Rows | Months |
|------|------|--------|
| Lima | 684 | 12 |
| Arequipa | 564 | 12 |
| Trujillo | 400 | 12 |

---

## 4. COVERAGE BY SLICE (Lima)

Plan LOB raw values (before mapping):

| LOB | Rows | Months |
|-----|------|--------|
| auto taxi | — | 12 |
| auto_taxi | — | 12 |
| carga | — | 12 |
| delivery | — | 12 |
| pro | — | 12 |
| tuk tuk | — | 12 |
| tuk_tuk | — | 12 |
| yma | — | 12 |
| ymm | — | 12 |

**LOB mapping active:** 28 rules (`ops.plan_lob_mapping`)

---

## 5. BUSINESS SLICE MATCHING (D.2B Fix)

**Problem:** Plan LOB canonical names (e.g., `auto_taxi`) don't match real table business slice names (e.g., `Auto regular`).

**Fix applied:** `_LOB_TO_SLICE` normalization map in `omniview_v2_plan_real_repository.py`:

| Plan canonical | Business slice |
|----------------|---------------|
| `auto_taxi` | `Auto regular` |
| `carga` | `Carga` |
| `delivery` | `Delivery` |
| `pro` | `PRO` |
| `tuk_tuk` | `Tuk Tuk` |
| `yma` | `YMA` |
| `ymm` | `YMA` |

**Backlog:** Replace hardcoded map with `ops.plan_lob_to_business_slice` table.

---

## 6. COUNTRY CODE FIX

**Problem:** Plan table stores country as "PE"/"CO", repository queried with "peru".

**Fix:** Added `_COUNTRY_CODE` and `_CITY_CAPS` normalization maps. Plan query uses `TRIM(country)` without LOWER, matching exact DB values.

---

## 7. PLAN VS REAL MATCH RESULTS (2026-01 to 2026-06, Lima)

| Metric | Total Cells | Matched (ON_TRACK+WATCH+OFF) | NO_PLAN | NO_REAL |
|--------|-------------|------------------------------|---------|---------|
| trips | 36 | 34 | 2 | 0 |
| active_drivers | 36 | 34 | 2 | 0 |
| avg_ticket | 36 | 34 | 2 | 0 |
| revenue | 36 | 0 | 2 | 34 |

**Revenue gap:** Plan table has `projected_revenue` for Peru but real table `revenue_yego_final` may not be populated in `ops.real_business_slice_month_fact`. This is a P0 data quality issue tracked separately from D.2B (likely resolved by OMNI-P0 revenue canonicalization).

---

## 8. DATA QUALITY FLAGS

| Issue | Severity | Resolution |
|-------|----------|------------|
| Plan/real slice name mismatch | P0 (fixed) | `_LOB_TO_SLICE` normalization |
| Country code inconsistency (PE vs peru) | P1 (fixed) | Separate normalization per table |
| LOB duplicates (auto taxi + auto_taxi) | P2 | Template normalization needed |
| Revenue real data missing | P0 | Tracked in OMNI-P0 |
| `ymm` LOB has 0 projected trips | P3 | Plan template gap |
