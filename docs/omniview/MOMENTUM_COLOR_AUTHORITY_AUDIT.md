# MOMENTUM COLOR AUTHORITY AUDIT

**Date**: 2025-05-25
**Mode**: Vs Proyección (viewMode='proyeccion')

---

## 1. CURRENT MOMENTUM PIPELINE

```
backend period_over_period
    ↓
projectionMatrixUtils.js → computeProjectionDeltas()
    ↓
delta.periodPop          ← percentage change (number)
delta.periodPopLabel     ← "DoD" | "WoW" | "MoM"
delta.periodPopComparable ← boolean (is comparison valid?)
delta.periodPopKind      ← kind from backend
    ↓
ProjectionCellRender → hasMomentum check
    ↓
Visual: colored delta with DoD/WoW/MoM label
```

## 2. COLOR AUTHORITY STATUS

| Aspect | Status | Details |
|---|---|---|
| Momentum row visible | ✅ | When `periodPopComparable && periodPopLabel && periodPop != null` |
| Color mapping | ✅ | Up=green `#22c55e`, Down=red `#ef4444`, Neutral=gray |
| Severity threshold | ✅ | Bold (>5%), semibold (≤5%) |
| Momentum DOMINATES attainment | ✅ | Attainment row gets `font-normal opacity-60` when momentum present |
| Gap row secondary | ✅ | Gap row gets `text-gray-300` when momentum present |
| Proy row secondary | ⚠️ | Proy row always visible at `szProy` size, competes for attention |

## 3. FALLBACK BEHAVIOR

When momentum is NOT available (periodPop == null):
- Momentum row hidden
- Attainment row shown at full weight (`font-semibold`)
- Gap row shown at normal opacity

This is correct: attainment takes the primary visual slot when momentum is unavailable.

## 4. ISSUES FOUND

| Issue | Severity | Fix |
|---|---|---|
| Proy row always visible | MEDIUM | Move to ultra-small line below Real, combo with Avance |
| Momentum label font too small | LOW | `text-[0.7em]` on label — increase slightly |
| Gap row duplicates momentum info | LOW | When momentum present, gap is redundant; hide or collapse further |

## 5. VERDICT

Momentum color authority is **working correctly**. The main improvement needed is to reduce the visual weight of the "Proy" (plan target) and "Gap" rows so they don't compete with the Real + Momentum dominant rows.
