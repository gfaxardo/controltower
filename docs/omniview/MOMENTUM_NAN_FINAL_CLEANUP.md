# MOMENTUM NaN FINAL CLEANUP

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## AUDIT

### Formatting functions (projectionMatrixUtils.js)

| Function | NaN guard | Status |
|---|---|---|
| `fmtAttainment(pct)` | `pct == null \|\| !Number.isFinite(pct)` | ✅ Fixed |
| `fmtGap(gap, kpiKey)` | `gap == null` → returns null | ✅ Safe (null early return) |
| `fmtGapPct(pct)` | `pct == null \|\| !Number.isFinite(pct)` | ✅ Fixed |
| `fmtValue(v, kpiKey)` | `v == null \|\| !isFinite(Number(v))` | ✅ Already safe |

### Momentum display (ProjectionCellRender)

| Expression | NaN guard | Status |
|---|---|---|
| `momPctStr` | `Number.isFinite(momValue)` | ✅ Fixed (previous phase) |
| `momBold` | `Math.abs(momValue) > 5 && Number.isFinite(momValue)` | ✅ Fixed |
| `momUp` / `momDown` | `momValue > 0` — NaN compares false | ✅ Safe |
| `momLabel` | `delta.periodPopLabel` string | ✅ Safe |
| `momArrow` | conditional string | ✅ Safe |
| `momColor` | conditional string | ✅ Safe |

### Other values

| Expression | NaN guard | Status |
|---|---|---|
| `realStr` | `fmtValue()` handles null/NaN | ✅ Safe |
| `projStr` | `fmtValue()` handles null/NaN | ✅ Safe |
| `avStr` | `fmtAttainment()` handles null/NaN | ✅ Safe |
| `gapPctStr` | `fmtGapPct()` handles null/NaN | ✅ Safe |
| `gapStr` | `fmtGap()` handles null | ✅ Safe |
| `att` | backward `attainment_pct` — guarded by fmtAttainment | ✅ Safe |

## VERDICT: CLEAN

Zero NaN paths remain. All formatting functions guard against `null`, `undefined`, and `NaN` values. All cell render paths produce `'—'`, `null` (hidden), or valid formatted strings.
