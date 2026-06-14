# OMNIVIEW V2 — PROFESSIONAL UI REBUILD PLAN

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** READ-ONLY AUDIT — No implementation yet
**Phase:** OV2-UI-R1 Architecture Audit

---

## 0. Executive Decision

**GO: REBUILD SHELL, REUSE LOGIC**

The current Omniview V2 UI renders without crashes and has all P0 features functional. However, it does not reflect a professional operational cockpit. The visual shell (ShadowPage, CommandHeader, MatrixShell layout) should be replaced with a cleaner, executive-oriented design. All certified business logic (6 helpers, 4 hooks, base components) is preserved and reused.

---

## 1. Current State

Omniview V2 renders at `/operacion/omniview-v2-shadow`. Has 30 files organized into pages, hooks, components (matrix/layout/base), design tokens, and CSS.

**Strengths:**
- Runtime stable (crash fixed)
- All 7 P0 features functional
- Backend/data governance certified
- Clean code separation (hooks isolate data, components are renderers)
- Unified design tokens (CSS + JS)
- All 6 helpers are well-tested and reusable

**Weaknesses:**
- Large skeleton takes up screen before data loads
- Technical banners ("OV2 Shadow", "MVP", "Yango API Safety") add noise
- Empty space between header and matrix
- CommandHeader is cluttered with too many controls
- No visual hierarchy — everything competes
- Status bar is hidden by default (collapsed)
- Not "executive" — doesn't feel like a cockpit

---

## 2. Component Inventory

### 2.1 Keep (Logic — Reuse As-Is)

| Component | Purpose | Reason |
|-----------|---------|--------|
| `useOmniviewV2Shell` | Shell data hook | Certified, working, no visual concern |
| `useOmniviewV2Matrix` | Matrix data hook | Certified, working |
| `useOmniviewV2PlanReal` | Plan vs Real hook | Certified, working |
| `useOmniviewV2DrillCell` | Drill data hook | Certified, working |
| `omniviewV2Metrics.js` | 7 metric definitions | Certified, complete |
| `omniviewV2ColorSemantics.js` | Tone engine | Certified, complete |
| `omniviewV2Export.js` | CSV engine | Certified, complete |
| `omniviewV2Sort.js` | Sort engine | Certified, complete |
| `omniviewV2PeriodPresets.js` | Presets | Certified, complete |
| `omniviewV2PlanReal.js` | PvR display | Certified, complete |
| `omniviewV2Tokens.js` | Design tokens | Foundation for new shell |
| `MatrixVisualSystem.css` | CSS custom properties | Foundation, extend |

### 2.2 Replace (Visual Shell)

| Component | Current Issue | New Direction |
|-----------|--------------|---------------|
| `OmniviewV2ShadowPage.jsx` | 480-line orchestrator with skeleton, banners, empty space | New professional page wrapper |
| `OmniviewV2CommandHeader.jsx` | Too many controls inline, no grouping | Split into ControlToolbar + StatusRail |
| `MatrixShell.jsx` | Functional but bare | Enhanced with professional density, spacing |
| `MatrixCell.jsx` | Works but could be more readable | Minor polish |
| `OmniviewV2GlobalEmptyState.jsx` | Good foundation | Keep, minor polish |

### 2.3 Deprecate (Remove Visual Noise)

| Item | Reason |
|------|--------|
| "OV2 Shadow" label | Remove from visible UI |
| "MVP shadow mode" banner | Only in debug/development mode |
| "Yango API Safety" banner | Move to source health section |
| `shellToMatrixResponse.js` adapter | Matrix endpoint works, adapter not needed |

---

## 3. Visual Diagnosis (Current State Score)

| Area | Score (1-5) | Issue |
|------|------------|-------|
| Opens without crash | 5 | Fixed |
| Looks professional | 2 | Too much skeleton, empty space, banners |
| Operator scan-ability | 2 | No clear focal point |
| Freshness clarity | 3 | Badge exists, status bar hidden |
| Matrix readability | 3 | Cells work but layout improvable |
| Control grouping | 2 | All controls in one strip, no grouping |
| Banner excess | 2 | 3+ banners visible |
| Empty space excess | 2 | Large gaps between sections |
| Loading professionalism | 2 | Large shimmer skeleton |
| Error actionability | 3 | Error boundary works, could be better |
| Plan vs Real clarity | 3 | Attainment works, but too subtle |
| Wide screen usage | 2 | Doesn't adapt well |

**Overall: 2.4/5 — Not yet professional.**

---

## 4. Proposed Professional UI Architecture

```
OmniviewV2ProfessionalPage
├── ProfessionalHeader (clean, minimal)
│   ├── Title "Omniview V2"
│   ├── GrainSelector
│   └── FreshnessIndicator (always visible)
├── OperationalStatusRail (collapsible)
│   ├── Latest closed date
│   ├── Coverage %
│   ├── Canonical/shadow status
│   └── Source health
├── ControlToolbar (grouped controls)
│   ├── SourceSelector
│   ├── CountrySelector
│   ├── CitySelector
│   ├── SliceSelector
│   └── Separator
│   ├── MetricSelector
│   ├── ViewModeToggle (real / plan_real)
│   ├── PeriodPresets
│   ├── SortControl
│   └── ExportButton
├── ExecutiveKpiStrip (2-3 cards)
│   └── KPI cards from shell data
├── MatrixViewport
│   ├── MatrixHeader (sticky columns)
│   ├── MatrixBody (sticky rows)
│   └── MatrixEmptyState
├── CellInspectorDrawer
└── AlertStrip (warnings, if any)
```

**Data flow:** Same hooks feed same data. Only the visual shell changes.

---

## 5. Route Strategy

- Build new shell at `/operacion/omniview-v2` (new route)
- Keep current `/operacion/omniview-v2-shadow` as fallback
- Both routes use exact same hooks, helpers, endpoints
- Smoke new route, then deprecate shadow route
- Use `controlTowerNavigationRegistry.js` to control visibility

---

## 6. Implementation Phases

### OV2-UI-R2 — Professional Shell Skeleton
- Create `OmniviewV2ProfessionalPage` with clean layout
- Reuse all hooks and helpers
- No new logic — only visual restructuring
- Keep shadow page running in parallel
- **Deliverable:** New page renders with real data, no other changes

### OV2-UI-R3 — Toolbar + Controls Migration
- Migrate all controls from CommandHeader to ControlToolbar
- Group logically (source → filters → metric → sort → export)
- Period presets as buttons, not dropdown
- Freshness always visible in header
- **Deliverable:** Controls organized, fresh look

### OV2-UI-R4 — Matrix Professionalization
- Enhanced cell rendering
- Better empty/loading states (smaller skeleton)
- Density controls
- Wide screen optimization
- **Deliverable:** Matrix reads like a professional table

### OV2-UI-R5 — States Polish (Empty/Error/Freshness)
- Remove technical banners, replace with operational indicators
- Error boundary shows actionable message (not stack trace)
- Empty state explains why and suggests next action
- Debug mode toggle for stack traces
- **Deliverable:** No technical noise visible to operator

### OV2-UI-R6 — Cutover + Smoke
- Browser smoke on new route
- 7 P0 regression check
- Mark `productionReady: true` in navigation registry
- Deprecate shadow route
- **Deliverable:** Professional UI live

---

## 7. Risks

| Risk | Mitigation |
|------|-----------|
| Breaking existing hooks | Hooks untouched — only visual shell changes |
| Losing P0 features | All helpers preserved, no logic changed |
| Over-engineering | Phased approach — stop when professional look achieved |
| Scope creep into Diagnostic/Forecast | Strictly no engine features, only visual polish |
| Backend changes needed | None required — same endpoints |

---

## 8. Rollback Strategy

- Shadow route remains active until cutover
- Revert to shadow route if professional shell fails smoke
- All hooks/helpers unchanged — no data logic to roll back

---

## 9. Next Prompt

> "OV2-UI-R2: Build professional shell skeleton for Omniview V2 at new route /operacion/omniview-v2. Reuse all hooks and helpers. Clean layout with header, toolbar, matrix, empty state. Keep shadow page. No backend changes. No Diagnostic/Forecast."

---

*Read-only audit complete. Decision: rebuild shell, reuse logic. 6 phases. No code changes yet.*

---

## R3 Result

**COMPLETE.** All controls migrated. Metric selector (7 KPIs), view mode toggle, period presets (6), sort controls (6), CSV export, freshness/status bar. State owner: ProfessionalPage. Report: `OMNIVIEW_V2_UI_R3_CONTROLS_MIGRATION_REPORT.md`.

## R4 Result

**COMPLETE.** Professional matrix viewport with tone-colored borders per metric polarity, Plan vs Real attainment rendering, sticky row labels/headers, compact loading/empty states. Report: `OMNIVIEW_V2_UI_R4_MATRIX_PROFESSIONALIZATION_REPORT.md`.

## R5 Result

**COMPLETE.** Operational states polished. Status bar: green/amber/gray dots with labels (Operational / Data warning / Shadow mode / No data). Debug panel hidden behind discrete toggle. Report: `OMNIVIEW_V2_UI_R5_STATES_POLISH_REPORT.md`.

## R6 Result

**COMPLETE.** Cutover executed. `/operacion/omniview-v2-professional` is now the default Omniview V2 route. Shadow route preserved. All smoke passes. Report: `OMNIVIEW_V2_UI_R6_CUTOVER_SMOKE_REPORT.md`.

**All phases R1-R6 complete. Professional UI rebuild certified.**