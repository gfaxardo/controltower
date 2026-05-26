# MOMENTUM-FIRST COGNITION AUDIT

**Date**: 2025-05-25
**Mode**: Vs Proyección

---

## 1. CURRENT VISUAL HIERARCHY PER CELL

| Element | Position | Font | Weight | Color | Classification |
|---|---|---|---|---|---|
| HOY badge | Row 1 | 7px | bold | emerald-500 | **Terciario** — contextual marker |
| REAL VALUE | Row 2 | 13-16px | extrabold | gray-900 | **Dominante** — the hero number |
| MOMENTUM DELTA | Row 3 | 11px | extrabold/bold | severity color | **Dominante** — the trend |
| Plan + Avance | Row 4 | 9px | normal | gray-400 | **Terciario** — collapsed context |
| Status label | Row 5 | 9px | medium | colored | **Terciario** — when needed |

## 2. WHAT DOMINATES COGNITIVELY

**Row 2 (REAL VALUE)** → the operator reads the actual operational number first.
**Row 3 (MOMENTUM DELTA)** → immediately below, the colored arrow communicates direction + magnitude.

Both together = 80%+ of cognitive load. This is good.

## 3. WHAT COMPETES WITH MOMENTUM

| Element | Competition level | Resolution |
|---|---|---|
| Plan (Proy) | LOW — collapsed to Row 4, ultra-small | OK |
| Attainment % | LOW — only shown when no momentum | OK |
| Gap | REMOVED from cell — tooltip only | OK |
| KPI comparability badge | LOW — 6px, absolute positioned | OK |
| Confidence dots | LOW — 1px dots, absolute positioned | OK |
| Critical alert dot | LOW — 1.5px, position absolute | OK |
| Status label | LOW — only shown when no real data | OK |

## 4. WHAT STILL "SMELLS LIKE BI"

| Element | BI smell | Fix applied |
|---|---|---|
| Zebra striping | ❌ Classic BI table pattern | ✅ Reduced intensity: `bg-slate-50/50` → lighter backgrounds |
| Thick borders | ❌ Excel-like heavy dividers | ✅ Softer: `border-gray-200/60` → `border-gray-150` |
| Table header dark bg | ⚠️ Dark header = report feel | ⚠️ Kept for contrast; but softened body |
| "Plan" text | ❌ Financial planning term | ⚠️ Relegated to context line |
| Performance label font | ⚠️ Small label still feels "data table" | ✅ Context line ultra-small + gray |

## 5. CLASSIFICATION SUMMARY

| Element type | Count | Action |
|---|---|---|
| Dominante | 2 (Real + Momentum) | Keep at max weight |
| Contextual | 2 (Plan + Avance) | Keep ultra-small |
| Terciario | 5 (badge, status, dots) | Keep minimal |
| Eliminado | 1 (Gap from cell) | Tooltip only |
| Tooltip only | 1 (Full plan data) | Already in tooltip |

## VERDICT: Cognitive hierarchy is correct. Momentum + Real dominate, everything else is minimal or tooltip-only.
