# HOTFIX MOMENTUM DOMINANCE — PRECHECK GO/NO-GO

**Date**: 2025-05-25
**Foco**: Vs Proyección (viewMode='proyeccion')

---

## ROOT CAUSE

`hasMomentum` check in `ProjectionCellRender` required ALL THREE conditions:
```
periodPopComparable && periodPopLabel && periodPop != null
```

If `periodPopLabel` is null (backend doesn't set it), or `periodPopComparable` is false/null, momentum was completely hidden even when `periodPop` had a valid numeric value.

Additionally, when momentum was absent, the attainment/fulfillment display showed "47.3% (E)" in the dominant position, making Plan vs Real appear dominant.

## FIX

1. **`projectionCellDisplayModel.js`** — Canonical display helper: if `periodPop` has a valid number, momentum dominates regardless of backend flags. Label derived from grain.
2. **Cell render** — Uses display model. Momentum gets colored bold line. Plan fallback gets muted small line.
3. **Drill default** — Opens momentum tab if selection has momentum data.

## WIRING

| Check | Status |
|---|---|
| viewMode='proyeccion' | ✅ |
| ProjectionCellRender vivo | ✅ |
| Evolution not touched | ✅ |
| Deprecated components not used | ✅ |

## VERDICT: GO
