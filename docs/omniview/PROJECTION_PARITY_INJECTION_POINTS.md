# PROJECTION PARITY — INJECTION POINTS AUDIT

**Date**: 2025-05-25
**Status**: CONFIRMED

---

## Injection Point 1: ProjectionCellRender (COLOR AUTHORITY + DoD/WoW/MoM)

| Attribute | Value |
|---|---|
| **File** | `BusinessSliceOmniviewMatrixCell.jsx:198-428` |
| **Type** | Inline function inside `BusinessSliceOmniviewMatrixCell` |
| **Activated by** | `mode === 'projection'` (line 68) |
| **Imports alive** | ✅ `projectionSignalColor`, `SIGNAL_DOT`, `fmtPeriodPop`, `fmtValue`, etc. |
| **Imports needed** | `getComparisonLabel`, `isMomentumComparison` from `operationalMomentumEmphasis.js` |

### Current Layout (4 rows)
```
Row 1: ↑ Projected value
Row 2: Real value (bold)
Row 3: ● Attainment % (colored by projectionSignalColor)
Row 4: Gap value (muted)
Row 5: periodPop (DoD/WoW/MoM) — EXISTS but muted (text-slate-500)
```

### Momentum Data Available
- `delta.periodPopComparable` (boolean)
- `delta.periodPopLabel` ("DoD", "WoW", "MoM")
- `delta.periodPop` (variation value, e.g., -18)
- Also available on `delta.value` and `delta.previous_value` for sequential comparison

### Target After Migration
```
Row 1: ↑ Projected value (muted, context only)
Row 2: Real value (bold)
Row 3: ▲▼ DoD +X% / -X%  ← MOMENTUM DOMINANT (bold, colored)
Row 4: ● Attainment % + Gap  ← PLAN vs REAL (subdued secondary)
```

### Color Authority Rules
- Momentum UP → green (#22c55e) + bold
- Momentum DOWN → red (#ef4444) + bold
- Momentum FLAT → gray
- Attainment → secondary opacity (0.55), smaller text
- Gap → muted gray

---

## Injection Point 2: displayProjMatrix (WEEKDAY FOCUS)

| Attribute | Value |
|---|---|
| **File** | `BusinessSliceOmniviewMatrix.jsx:919-922` |
| **Type** | useMemo |
| **Status** | **ALREADY WIRED** — `filterWeekdayFocus` applied to both `displayMatrix` AND `displayProjMatrix` |
| **Verification** | `displayProjMatrix` depends on `[projMatrix, grain, weekFocusOnly, weekdayFocus]` |

The weekday chips (DOM/LUN/MAR/...) at lines 1337-1364 are rendered OUTSIDE the `isProjectionMode` conditional, so they're visible in both modes. The filter is already applied to `displayProjMatrix`. **No code change needed for PASO 4.**

---

## Injection Point 3: OmniviewMomentumPriorityStrip (PROJECTION DATA)

| Attribute | Value |
|---|---|
| **File** | `BusinessSliceOmniviewMatrix.jsx:1305` |
| **Current input** | `baseMatrix?.cities`, `baseMatrix?.allPeriods` (evolution data only) |
| **Target** | Also receive `projMatrix?.cities`, `projMatrix?.allPeriods` when `isProjectionMode` |
| **Logic change** | Pass `projMatrix` data instead of `baseMatrix` data in projection mode |

---

## Injection Point 4: OmniviewProjectionDrill (MOMENTUM TOGGLE)

| Attribute | Value |
|---|---|
| **File** | `OmniviewProjectionDrill.jsx:22-58` |
| **Current data** | Plan vs Real: gap, attainment, root cause, control loop history |
| **Momentum API** | `getOmniviewMomentumDrill` from `services/api.js` |
| **Momentum chart** | `OmniviewMomentumDrillChart.jsx` — already imported and used in Evolution |
| **Target** | Add momentum tab/section in the drill panel |

---

## Injection Point 5: Insight/Severity Layer

| Attribute | Value |
|---|---|
| **File** | `insightEngine.js` — currently Evolution-only |
| **Target** | Compute severity from periodPop data on projection rows |
| **Approach** | Use `classifyMomentumRisk` from `operationalMomentumPriority.js` on periodPop values |

---

## SUMMARY

| Capability | Injection Point | Status |
|---|---|---|
| Momentum Color Authority | `ProjectionCellRender` | **Needs implementation** |
| Weekday Focus | `displayProjMatrix` | **Already wired** ✅ |
| Momentum Priority Strip | `OmniviewMomentumPriorityStrip` prop | **Needs prop swap** |
| Momentum Drill | `OmniviewProjectionDrill` | **Needs toggle + chart** |
| Insight Layer | `ProjectionCellRender` + `classifyMomentumRisk` | **Needs severity overlay** |
| Cognitive Priority Shift | `ProjectionCellRender` visual hierarchy | **Needs reorder** |
