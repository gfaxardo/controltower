# HOTFIX — TRUE MOMENTUM DELTA REPORT

**Date**: 2025-05-25
**Foco**: Vs Proyección

---

## 1. ROOT CAUSE

`periodPop` en el delta de proyección es un **objeto** `{ abs, pct, basis, cur_real, prev_real }`, no un número.

El display model hacía `Number(periodPop)` → NaN → `hasMomentumData = false` → momentum nunca visible.

El backend `apply_period_over_period_inplace` correctamente envía `metrics.trips_completed.pct` = -21.1, pero el frontend no extraía `.pct`.

## 2. FIX

`projectionCellDisplayModel.js`:

```js
// ANTES (bug)
const popValue = delta?.periodPop  // ← objeto, no número
// Number(obj) = NaN → momentum oculto

// DESPUÉS (fix)
const popObj   = delta?.periodPop
const popValue = (popObj && typeof popObj === 'object') ? Number(popObj.pct) : NaN
// popValue = -21.1 → momentum visible ✅
```

## 3. DATA FLOW VERIFIED

```
Backend: apply_period_over_period_inplace(rows, grain)
  → row.period_over_period = { kind:"dod", label:"DoD", comparable:true, metrics:{ trips_completed:{ abs:-1634, pct:-21.1, basis:"real" } } }

Frontend: computeProjectionDeltas(linePeriods, allPeriods)
  → delta.periodPop = popm[key]  // { abs, pct, basis, ... }

Display: buildProjectionCellDisplay(delta, grain, kpiKey)
  → popValue = delta.periodPop.pct  // -21.1
  → deltaPctStr = "-21%" ✅
```

## 4. BUILD

✅ PASS — 814 modules, 9.22s

## 5. VERDICT: GO

True momentum (DoD/WoW/MoM from backend `period_over_period.metrics.*.pct`) ahora es el delta dominante. YTD/plan nunca se usa como falso momentum.
