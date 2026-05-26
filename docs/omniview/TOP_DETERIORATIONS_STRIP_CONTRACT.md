# TOP DETERIORATIONS STRIP — CONTRACT

**Date**: 2025-05-25
**Component**: `OmniviewMomentumPriorityStrip`
**Status**: Already implemented and wired for both modes

---

## 1. WHAT IT IS

A compact operational strip that surfaces the entities (cities + lines) with the highest signal deterioration, computed deterministically from projection momentum data.

Positioned between the Command Header and the matrix table.

## 2. DATA SOURCE

- `extractMomentumPriorityFromMatrix(cities, allPeriods, grain, maxItems)` from `operationalMomentumPriority.js`
- Reads from `projMatrix.cities` in projection mode, `baseMatrix.cities` in evolution mode
- No new backend APIs — uses existing matrix data

## 3. RISK LEVELS

| Level | Label | Visual |
|---|---|---|
| CRITICAL_DECLINE | "!!" prefix | Red background + text |
| ACCELERATING_DOWN | "!!" prefix | Red background + text |
| CONSECUTIVE_DOWN | "!" prefix | Amber background + text |
| SINGLE_DECLINE | "↓" prefix | Light amber |
| STABLE | No prefix | Green |
| RECOVERING | No prefix | Green |
| IMPROVING | "↑" prefix | Green + emerald |

## 4. CURRENT WIRING (Matrix.jsx:1300)

```jsx
<OmniviewMomentumPriorityStrip
  cities={isProjectionMode ? projMatrix?.cities ?? null : baseMatrix?.cities ?? null}
  allPeriods={isProjectionMode ? projMatrix?.allPeriods ?? [] : baseMatrix?.allPeriods ?? []}
  grain={grain}
  maxItems={5}
/>
```

- Wired for BOTH evolution and projection
- `maxItems=5` limits display to top 5 deteriorations
- Automatically disappears when no deteriorations detected

## 5. OPERATIONAL PROPERTIES

| Property | Value |
|---|---|
| Deterministic | YES — no AI/ML |
| Real-time | Computed from matrix data on each render |
| No backend calls | Pure frontend from existing data |
| Compact | 1 line, min-height 24px |
| Color-coded | Severity expressed through background/text color |
| Accessible | `role="status"` + `aria-label` |

## 6. NO DUPLICATION

This strip does NOT duplicate the Insights Engine:
- Insights Engine: behavioral pattern detection (Evolution only)
- Momentum Priority Strip: deterministic signal ranking (both modes)

They serve different purposes and don't overlap.
