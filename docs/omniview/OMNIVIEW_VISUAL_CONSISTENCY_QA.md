# OMNIVIEW VISUAL CONSISTENCY QA

**Date**: 2025-05-25
**Status**: AUDITED — PASS

---

## Color Systems

### Evolution Mode
| Element | Color Source | Color |
|---|---|---|
| Momentum delta (DoD/WoW/MoM) | `signalColorForKpi(delta.signal, kpiKey)` | #22c55e (green up), #ef4444 (red down), #9ca3af (neutral) |
| Sequential delta | Same + opacity 0.55 | Dimmed versions |
| Projection delta | Same + #99 alpha | Medium opacity |
| Cell background | Tailwind classes | bg-slate-50/50 zebra, bg-blue-50 selected |

### Projection Mode
| Element | Color Source | Color |
|---|---|---|
| Momentum (DoD/WoW/MoM) | Computed `momColor` from periodPop | #22c55e (up), #ef4444 (down), #9ca3af (neutral) |
| Attainment % | `projectionSignalColor(signal)` | #16a34a (green), #d97706 (warning), #dc2626 (danger), #9ca3af (no_data) |
| Gap | Muted gray | text-gray-400 |
| Real value | Black/gray | text-gray-800 |
| Projected value | Gray | text-gray-400 |

**Consistency**: Evolution uses `signalColorForKpi` (green #22c55e). Projection momentum uses same green (#22c55e). Projection attainment uses darker green (#16a34a). Minor variation — both in green spectrum.

---

## Typography Hierarchy

| Level | Size | Weight | Where |
|---|---|---|---|
| Real value | 13px (9px compact) | font-semibold | Cell row 2 (both modes) |
| Momentum delta | 11px (8px compact) | font-bold/font-semibold | Evolution cell, Projection momentum row |
| Attainment % | 11px (8px compact) | font-semibold / font-normal (when momentum present) | Projection cell row 3 |
| Projected value | 10px (7px compact) | normal | Projection cell row 1 |
| Gap | 10px (7px compact) | normal | Projection cell row 4 |
| Labels (DoD/WoW/MoM) | 0.7em of parent | opacity-70 | Both modes |

**Consistency**: PASS — size scale is uniform between modes.

---

## Badge / Severity Styles

| Element | Style | Where |
|---|---|---|
| Critical alert dot | w-1.5 h-1.5 rounded-full bg-red-600 | ProjectionCellRender |
| Low confidence ring | ring-1 ring-inset ring-dashed ring-red-300/70 | ProjectionCellRender |
| Anomaly dot | w-1 h-1 rounded-full bg-amber-500 | ProjectionCellRender |
| Integrity broken banner | Red background + border | Projection mode |
| YTD alert chip | Colored chip with emoji | Both modes |
| Priority strip chip | Colored chip with risk color | Both modes |

**Consistency**: PASS — all severity indicators use consistent red/amber/green palette.

---

## Opacity / Emphasis Logic

| State | Opacity | Where |
|---|---|---|
| Momentum present + attainment | 0.6 | ProjectionCellRender attainment row |
| Momentum present + gap | text-gray-300 (vs 400) | ProjectionCellRender gap row |
| Future period + no real | 0.6 | ProjectionCellRender cell |
| Partial comparison | 0.6 | Evolution cell delta |
| Focus mode dimming | 0.3 | Evolution cells without insights |

**Consistency**: PASS — momentum dominates (full opacity), plan/real secondary (0.6).
