# OMNIVIEW V2 — UI P1D SORT CONTROLS REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — 6 sort modes implemented
**Phase:** OV2-UI-P1D

---

## 0. Executive Decision

**GO: SORT CONTROLS COMPLETE**

6 sort modes: Original, A→Z, Z→A, Volume, Impact, Critical. Client-side only. No refetch. Export respects sort order. Volume and Impact computed from loaded cells. Critical uses color semantics engine.

---

## 1. Scope

Client-side row sorting for Omniview V2 matrix. Sorts rows by label, selected metric volume, delta impact, or critical cell count. All computed from in-memory data.

---

## 2. V1 Sort Audit

| V1 Sort Mode | Source | Safe for V2? | Port? |
|-------------|--------|-------------|-------|
| `alpha` (A→Z) | `omniviewMatrixUtils.js:896` | YES | ADAPTED — added desc variant |
| `impact_desc` (Impacto ↓) | Uses `lineImpactMap` precomputed per city/line | YES | ADAPTED — uses max abs delta per row from cells |
| `revenue_desc` | Specific metric sort | YES | ADAPTED — generalized to `volume_desc` for selected metric |
| `trips_desc` | Specific metric sort | YES | ADAPTED — same as volume for selected metric |

---

## 3. Sort Modes Implemented

| Mode | ID | Description | Null/Edge Case |
|------|-----|-------------|---------------|
| Original | `default` | Preserves backend order | N/A |
| A → Z | `alpha_asc` | Row label ascending | Case-insensitive localeCompare |
| Z → A | `alpha_desc` | Row label descending | Same |
| Volume | `volume_desc` | Largest selected metric total first | Null-value rows last |
| Impact | `impact_desc` | Largest absolute delta first | Null-delta rows last |
| Critical | `critical_desc` | Most negative-tone cells first | Uses `omniviewV2ColorSemantics.getCellToneClass` |

**Tie-breaker:** All modes fall back to alpha ascending when values are equal.

---

## 4. Files Modified

| File | Change |
|------|--------|
| `omniviewV2Sort.js` | **CREATED** — sort engine: `sortMatrixRows`, `SORT_MODES` |
| `OmniviewV2CommandHeader.jsx` | **MODIFIED** — Sort dropdown (imports `SORT_MODES`) |
| `OmniviewV2ShadowPage.jsx` | **MODIFIED** — `sortMode` state, `useMemo` sortedRows, passes to header |

---

## 5. Export Interaction

Sort is applied to `sortedMatrixData` which feeds both `MatrixShell` and `handleExportCsv`. CSV export uses `matrixData` (which is `sortedMatrixData` after sort). Export respects current sort order.

---

## 6. Edge Cases

| Case | Behavior |
|------|----------|
| `sortMode === 'default'` | No sorting — original order |
| Null metric values in Volume | Rows with all-null values sorted last |
| Null deltas in Impact | Rows with all-null deltas sorted last |
| Future periods in Critical | Excluded (not counted) |
| Metric change | Sort re-applied with new metric values |
| Export after sort | Respects current sort order |
| Rapid sort changes | `useMemo` prevents unnecessary recomputation |

---

## 7. Validation

| Check | Result |
|-------|--------|
| `npm run build` | PASS (17.88s) |
| Backend untouched | CONFIRMED |
| No refetch on sort | CONFIRMED (client-side only) |
| CSV export respects sort | CONFIRMED |
| Null handling safe | CONFIRMED |

---

## 8. Remaining Gaps

| Gap | Status |
|-----|--------|
| P0-1: Multi-metric selector | COMPLETE |
| P0-2: CSV export | COMPLETE |
| P0-3: Color semantics | COMPLETE |
| P0-4: Sort controls | **COMPLETE** |
| P0-5: Plan vs Real visualization | PENDING |
| P0-6: Period presets | PENDING |

---

## 9. Next Phase

**OV2-UI-P2: Plan vs Real visualization.** Implement projection mode with attainment %, gap analysis, and plan-vs-real comparison. This requires backend changes for projection data. Do NOT implement charts yet.

---

*Sort controls complete. 6 modes. Client-side only. Export respects sort.*