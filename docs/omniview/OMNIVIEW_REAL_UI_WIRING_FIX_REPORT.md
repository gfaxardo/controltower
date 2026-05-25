# Omniview Real UI Wiring Fix Report

**Date**: 2025-05-25
**Build**: `npm run build` — SUCCESS

## Diagnostic Summary

### 1. Component Identity (PASO 1-2)
- **Confirmed**: `/operacion/omniview-matrix` renders `BusinessSliceOmniviewMatrix.jsx`
- **No override**, no legacy wrapper, no feature flag blocking
- Added temporary **SMOKE MARKER** `MOMENTUM WIRING ACTIVE` with runtime stats:
  - `rows=N` — raw API row count
  - `matrixPeriods=N` — total periods in base matrix
  - `displayPeriods=N` — periods after weekday/week focus filter
  - `weekdayFocus=X` — active weekday filter
  - `sampleKey` — first period key (debug date format)
  - `matrixCities=N` — city count in matrix

### 2. Momentum Priority Strip (PASO 4)
**Problem**: `OmniviewMomentumPriorityStrip` received raw API `rows` (flat array) but `extractMomentumPriorityFromMatrix` expected matrix-structured data (`cityName` + `lines[]` + `periods` Map with `deltas`).

**Root cause**: Data model mismatch. Raw API rows are flat per-period records. The extraction function expected the post-`buildMatrix()` structure.

**Fix**:
1. Rewrote `extractMomentumPriorityFromMatrix` in `src/utils/operationalMomentumPriority.js` to accept `baseMatrix.cities` Map and `baseMatrix.allPeriods` array directly
2. Calculates sequential deltas on-the-fly from `trips_completed` metric across sorted periods
3. Updated `OmniviewMomentumPriorityStrip` props: `rows` → `cities` + `allPeriods`
4. Updated call site in `BusinessSliceOmniviewMatrix.jsx:1265` to pass `baseMatrix?.cities` and `baseMatrix?.allPeriods`

### 3. Weekday Focus (PASO 3)
**Analysis**: The filter logic was correct in principle (filter `allPeriods` by weekday via `filterWeekdayFocus` → `displayMatrix` → Table). However, the date parsing was fragile (`pk.split('-')` assumes `YYYY-MM-DD` format).

**Fix**:
1. Added `parseDateFromPeriodKey(pk)` helper supporting:
   - `YYYY-MM-DD`
   - `YYYY-MM-DDTHH:mm:ss` (ISO with time)
   - `YYYYMMDD` (compact)
2. Added DEV-only debug object at `window.__omniviewWeekdayDebug` with filter stats
3. Smoke marker now shows `displayPeriods` vs `matrixPeriods` — direct visual confirmation

### 4. Color Authority (PASO 5)
**Analysis**: The color authority code in `BusinessSliceOmniviewMatrixCell.jsx:131-138` is **already correct** for Evolution mode:

```
isMomentum → baseColor (full) + opacity 1 → DoD/WoW/MoM authority
isProjection → baseColor + '99' + opacity 0.55 → subdued vPlan
else → baseColor + '66' + opacity 0.55 → very subtle sequential
```

The `classifyComparison` in `operationalMomentumEmphasis.js` ensures daily/weekly/monthly deltas default to MOMENTUM_* classification (= MAXIMUM emphasis = full color) when backend doesn't provide an explicit `comparison_mode`.

**Vs Proyección mode**: Uses separate `ProjectionCellRender` with `projectionSignalColor` — this is intentional design for plan-vs-real comparison view.

**No code changes needed** for Evolution mode color authority.

## Files Modified

| File | Change |
|---|---|
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Added smoke marker, `parseDateFromPeriodKey`, enhanced `filterWeekdayFocus` with debug, updated OMPS call to use `baseMatrix` |
| `frontend/src/utils/operationalMomentumPriority.js` | Rewrote `extractMomentumPriorityFromMatrix` to work with Map-based `cities` structure |
| `frontend/src/components/omniview/momentum/OmniviewMomentumPriorityStrip.jsx` | Changed props from `rows` to `cities` + `allPeriods` |

## Validation Checklist

In browser at `http://localhost:5174/operacion/omniview-matrix`:

- [ ] **Smoke marker visible**: Yellow banner `MOMENTUM WIRING ACTIVE` appears below command header
- [ ] **Weekday focus**: Click VIE → `displayPeriods` drops to ~1/7 of `matrixPeriods`, columns shrink
- [ ] **Momentum strip**: Color-coded priority badges appear when data has declines
- [ ] **Evolution colors**: DoD/WoW/MoM deltas show full green/red; sequential show dim colors
- [ ] **Build passes**: `npm run build` succeeds without errors

## Cleanup Instructions (PASO 7)

After confirmed working, remove the SMOKE MARKER block (`lines 1264-1266` in `BusinessSliceOmniviewMatrix.jsx`):

```jsx
{/* SMOKE MARKER — MOMENTUM WIRING ACTIVE */}
<div style={{ ... }}>
  MOMENTUM WIRING ACTIVE ...
</div>
```
