# OMNIVIEW MOMENTUM WIRING — REPORT

**Date**: 2026-05-25
**Status**: **GO**
**Build**: PASS (10.02s)

---

## WIRES FIXED

### 1. Weekday Focus Column Filtering
| Issue | Fix |
|-------|-----|
| `displayProjMatrix` not filtered by weekday | Added `filterWeekdayFocus` to `displayProjMatrix` memo |
| No column count indicator | Added `"{N} cols de {M}"` to the "Día" label when focus active |

**Now works**: Click DOM → `filterWeekdayFocus` filters `allPeriods` → table renders only Sundays. Column count shown.

### 2. Priority Strip Data Extraction
| Issue | Fix |
|-------|-----|
| `extractMomentumPriorityFromMatrix` used wrong row structure (`row.periods`) | Rewrote to iterate `row.lines[n].periods` and extract deltas per-line from `period.deltas[kpi]` |
| Strip returned null always | Now returns entities when deteriorations found, or "No deteriorations" when clear |

### 3. Cell Color Authority
| Issue | Fix |
|-------|-----|
| Colors came from `signalColorForKpi(delta.signal)` (projection-based) | Now: momentum → full color, projection → subdued (hex + '99'), simple sequential → very subtle (hex + '66') |
| Unused `getMomentumStyle` import | Removed — simplified to `isMomentum` + direct opacity |
| Duplicate `isMomentumComparison` call | Hoisted to line 133, reused in color + delta rendering |

**Now works**: DoD/WoW/MoM cells have bold color. Plan/projection cells have subdued color. Simple sequential cells are very faint.

### 4. Import Fix (carryover from previous hotfix)
| Issue | Fix |
|-------|-----|
| `CLASSIFY_COMPARISON` import not found in `operationalMomentumEmphasis.js` | Removed broken import from `operationalMomentumPriority.js` |

---

## VISUAL RESULT

```
Before (broken):
  Matrix: all deltas same color, same weight
  Strip: never rendered (null)
  Weekday: chips visible, no filtering

After (fixed):
  Matrix: momentum cells BOLD + full color, plan cells subdued, sequential faint
  Strip: shows deteriorations with severity chips
  Weekday: chips filter columns, count shows "4 cols de 30"
```

---

## FILES MODIFIED

| File | Changes |
|------|---------|
| `BusinessSliceOmniviewMatrix.jsx` | displayProjMatrix weekday filter + column count indicator |
| `BusinessSliceOmniviewMatrixCell.jsx` | Color authority from momentum + simplified styling |
| `operationalMomentumPriority.js` | Fixed data extraction to match matrix structure + removed broken import |
