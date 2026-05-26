# HOTFIX MOMENTUM DOMINANCE AUDIT

**Date**: 2025-05-25

---

## ROOT CAUSE #1: Too-strict momentum detection

**Location**: `BusinessSliceOmniviewMatrixCell.jsx:319`

```js
const hasMomentum = delta.periodPopComparable && delta.periodPopLabel && delta.periodPop != null
```

This required `periodPopComparable` AND `periodPopLabel` to be truthy. If the backend didn't set `comparable` or `label` in the `period_over_period` object, momentum was hidden even when `periodPop` had valid data.

**Fix**: `projectionCellDisplayModel.js` checks only `periodPop != null && Number.isFinite()`. Label derived from grain.

## ROOT CAUSE #2: Attainment occupying dominant slot

When momentum was hidden, attainment/fulfillment (e.g., "47.3% (E)") appeared in Row 3 — the same row meant for the momentum delta. This made Plan vs Real appear as the dominant metric.

**Fix**: When no momentum, attainment shows in small muted text (9px gray-500), clearly marked as fallback.

## ROOT CAUSE #3: Plan value visible in cell

Row 4 showed "Plan 59,596" — even in gray 9px, the large number competed visually.

**Fix**: When momentum exists, context line only shows "avance 47.3%" (tiny). When momentum absent, context shows "Plan 59.6K · 47.3%" clearly as fallback. Remove standalone big plan number.

## ROOT CAUSE #4: Drill defaults to Plan vs Real

`OmniviewProjectionDrill.jsx` always started on Plan vs Real tab.

**Fix**: `useState(() => selectionHasMomentum(selection) ? 'momentum' : 'plan_vs_real')`

## AFFECTED FILES

| File | Change |
|---|---|
| `projectionCellDisplayModel.js` | NEW — canonical display helper |
| `BusinessSliceOmniviewMatrixCell.jsx` | Uses display model, simplified render |
| `OmniviewProjectionDrill.jsx` | Defaults to momentum tab when available |
