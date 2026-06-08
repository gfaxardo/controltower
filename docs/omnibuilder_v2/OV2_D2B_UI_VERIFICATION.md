# OV2-D.2B — UI VERIFICATION

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Plan vs Real
> **Status:** UI ALREADY EXISTENT — VERIFIED

---

## 1. MODE SELECTOR

Located at `OmniviewV2ShadowPage.jsx:246-270`:

- **"Real Matrix"** button → `setViewMode('real')` — green accent
- **"Plan vs Real (Monthly)"** button → `setViewMode('plan_real')` + `setGrain('month')` — indigo accent

Both buttons exist and toggle `viewMode`.

---

## 2. KPI SELECTOR

Located at `OmniviewV2ShadowPage.jsx:260-269`:

| Button Label | metricId | 
|-------------|----------|
| Trips | `orders` → maps to `trips` in plan service |
| Revenue | `revenue` |
| Drivers | `active_drivers` |
| Ticket | `avg_ticket` |
| TPD | `trips_per_driver` |

---

## 3. DATA FLOW

```
OmniviewV2ShadowPage
  ├── viewMode === 'real'  → useOmniviewV2Matrix → GET /ops/omniview-v2/matrix
  └── viewMode === 'plan_real' → useOmniviewV2PlanReal → GET /ops/omniview-v2/plan-real/monthly
                                   └── returns MatrixResponse (same contract)
                                        └── rendered by MatrixShell (generic)
```

---

## 4. MATRIX RENDERING

`MatrixShell` component is data-structure agnostic. It renders:
- `columns` → column headers (months: "Jan 2026", "Feb 2026", ...)
- `rows` → row labels (business slices: "Auto regular", "Carga", ...)
- `cells` → metric values with delta/gap

**Plan vs Real cells automatically show:**
- `value` → real (actual)
- `delta_pct` → gap percentage
- `comparison_status` → ON_TRACK / WATCH / OFF_TRACK / NO_PLAN / NO_REAL

---

## 5. CELL INSPECTOR

`CellInspector.jsx` already renders:
- Real value (`formatted_value`)
- Gap absolute (`delta_value`)
- Gap percentage (`delta_pct`)
- Comparison status (`comparison_status`)
- Source lineage (`lineage_refs`):
  - `plan_table`: `ops.plan_trips_monthly`
  - `real_table`: `ops.real_business_slice_month_fact`
  - `plan_version`: (active version)

---

## 6. VISUAL PARITY CHECKLIST

| Requirement | Status |
|------------|--------|
| Matriz protagonista | Yes — MatrixShell renders for both modes |
| Períodos visibles (months) | Yes — column headers show "Jan 2026", "Feb 2026" |
| KPI selector fijo | Yes — selector bar above matrix |
| Slices visibles | Yes — row labels show business slice names |
| Inspector funcional | Yes — CellInspector shows plan/real/gap details |
| Real value shown | Yes — `formatted_value` in cell |
| Plan value shown | Via inspector `lineage_refs` |
| Gap % shown | Yes — `delta_pct` badge and inspector |
| Status shown | Yes — `comparison_status` colore cell |

---

## 7. NO CHANGES REQUIRED

The UI was already built for Plan vs Real. Per OV2-H.2 rules (NO UI nueva), no changes are needed. The D.2B backend fixes (slice name normalization, country code fix) make the existing UI work correctly.

---

## 8. KNOWN LIMITATIONS

| Issue | Severity | Resolution |
|-------|----------|------------|
| Revenue shows NO_REAL for all cells | P0 | `revenue_yego_final` not populated in month_fact — OMNI-P0 scope |
| LOB→slice normalization is hardcoded | P2 | Backlog: `ops.plan_lob_to_business_slice` table |
| Plan version selector not exposed in UI | P2 | Backlog: dropdown above matrix |
| Owner info not shown | P3 | Backlog: plan_ownership table integration |
