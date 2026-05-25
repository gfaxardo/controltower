# UX WORKFLOW AUDIT — FASE 1H.3

**Date:** 2026-05-24
**Audit Scope:** All frontend routes, tabs, subviews, drilldowns, inspectors, filters, CTAs
**Principle:** Operational UX Hardening & Workflow Dominance

---

## 1. ROUTE REDUNDANCY ANALYSIS

### 1.1 Multiple Routes to Omniview
| Route | Component | Redundant? |
|---|---|---|
| `/operacion/omniview-matrix` | `BusinessSliceOmniviewMatrix` | **PRIMARY** |
| `/operacion/omniview` | `BusinessSliceOmniview` | **REDUNDANT** — same data, different layout |
| `/operacion/business-slice` | `BusinessSliceView` | **REDUNDANT** — overlapping with Omniview Matrix |

**Recommendation:** Mark `/operacion/omniview` and `/operacion/business-slice` as HIDE_FROM_NAV. Keep only Omniview Matrix as the single operational entry point. Priority: HIGH.

### 1.2 Duplicate Filter Systems
| Filter System | Location | Conflict? |
|---|---|---|
| `CollapsibleFilters` → `Filters.jsx` | App-level (all views) | YES — conflicts with Omniview internal filters |
| `OmniviewFilterPrimitives.jsx` | Omniview Matrix internal | Primary operational filters |
| Global filter props passed to views | `App.jsx` | YES — passed to many views but unused in Omniview |

**Recommendation:** Remove global Filters component from Omniview Matrix views. The Omniview has its own filter system inside the Matrix component. Having two filter levels creates confusion. Priority: HIGH.

### 1.3 Subtab Proliferation in "Operación"
Current subtabs under Operación:
1. Omniview Matrix
2. Control Loop Plan vs Real
3. Reportes
4. Oportunidades Operativas
5. Real LOB / Drill
6. Business Slice
7. Omniview

**Problems:**
- 3 of 7 subtabs point to similar Omniview data (Matrix, Business Slice, Omniview)
- User cannot distinguish which is the "real" operational view
- "Omniview" and "Omniview Matrix" are confusingly similar names

**Recommendation:** Reduce to 4 subtabs:
1. Omniview Matrix (canonical operational truth)
2. Plan vs Real (control loop)
3. Drill LOB (deep drill)
4. Oportunidades (opportunities)

Move "Reportes" to a contextual action inside Omniview Matrix. Hide Business Slice and legacy Omniview. Priority: MEDIUM.

---

## 2. NAVIGATION CONFLICTS

### 2.1 Confusing Drill Navigation
The Omniview Matrix Inspector and Projection Drill are separate components that look similar but serve different purposes. When a user clicks a cell:
- In Evolution mode → Inspector panel opens
- In Vs Proyección mode → Projection Drill opens

**Problem:** User cannot predict which panel will open. The visual transition is identical (both slide in as right-side panels).

**Recommendation:** Unify into a single Operational Inspector that adapts based on mode. Priority: LOW (existing users are accustomed).

### 2.2 Selection History Persistence
Selection history is only local to the Inspector component. If user closes the inspector, the history is lost and must rebuild context manually.

**Recommendation:** Keep selection history in the parent component's state, even when inspector is closed. Priority: LOW.

---

## 3. VISUAL OVERLOAD ZONES

### 3.1 Control Bar Overload
The Omniview Matrix control bar contains 10+ controls in a single row:
- Grain selector (3 buttons)
- Country, City, Slice, Fleet filters (4+ dropdowns)
- Year, Month selectors
- Subfleets checkbox
- Reset button
- Modo (Evolución/Vs Proyección)
- Plan Version selector + Subir button
- Vista (Data/Insight)
- Orden dropdown
- Densidad (Cómodo/Compacto)
- Zoom (+/-)
- Focus Mode toggle
- FACT tables button
- Descargar button
- "Ir a mes actual" button

**Problem:** 16+ interactive elements in a single horizontal space. Users need significant cognitive load to understand what each does.

**Recommendation:** Group into logical sections with clear visual separators. Move advanced controls (Zoom, FACT tables, Export) to a secondary row or a "More" dropdown. Priority: HIGH.

### 3.2 Banner/Context Overload
The Omniview Matrix shows simultaneously:
- Executive Banner (data trust/issues)
- Operational Context Bar
- Freshness Banner
- YTD Summary Bar (projection mode)
- YTD Alerts Block (projection mode)
- Integrity Banner (projection mode)
- Unmapped Badge

**Problem:** Up to 5-7 informational blocks between the controls and the matrix table. The actual data table is pushed far down the viewport.

**Recommendation:** Collapse into a single Operational Status Bar that aggregates all status info. Expandable on click. Priority: HIGH.

### 3.3 Redundant Badges
KPI cells show:
1. Signal color dot (red/amber/green)
2. Signal arrow (up/down)
3. Delta value
4. Period state badge
5. Trust overlay class
6. Insight indicator (when Insight mode is on)

**Problem:** 4-5 visual indicators on a single 3-digit number can create visual noise.

**Recommendation:** Simplify to 2 levels: primary (value + signal color) and secondary (delta on hover). Keep trust/insight as border styles only. Priority: MEDIUM.

---

## 4. MEMORY-DEPENDENT WORKFLOWS

### 4.1 Filter Reset Behavior
When user changes grain (monthly → weekly), filters are silently reset without notification. The user must remember what filters they had.

**Problem:** Loss of operational context without warning.

**Recommendation:** Show a toast or inline notification when context-affecting changes occur. Priority: LOW.

### 4.2 Week/Day Country Requirement
In weekly/daily grain, country is required but the requirement is only shown as a small amber banner. New users may not notice and get blocked.

**Recommendation:** Auto-select the most active country when switching to weekly/daily. Show a more prominent hint. Priority: MEDIUM.

---

## 5. STATES WHERE USER DOESN'T KNOW WHAT TO DO

### 5.1 Empty Matrix State
When no data is returned, the user sees:
- Blank table area
- Or a small text "Sin datos de proyección"

**Problem:** No guidance on what to do next. No suggestion to change filters, check a different grain, go to another view.

**Current handling:** Good — the `projectionEmptyKind` and `blockedByCountry` banners are clear. But the Evolution mode empty state is not handled.

**Recommendation:** Add explicit guidance for all empty states. Priority: HIGH.

### 5.2 Long Loading States
The loading skeleton is basic (pulse bars). For very long loads (30s+), there's no feedback about what's happening (which query, estimated time).

**Current handling:** The "active tasks" bar shows labels like "Matriz de datos" or "Proyección vs Real" which is good. But no time estimate or progress indication.

**Recommendation:** Add elapsed time counter for long-running queries. Priority: LOW.

---

## 6. QUICK WINS

| # | Win | Effort | Impact |
|---|---|---|---|
| 1 | Hide redundant Omniview/Business Slice subtabs | 5 min | HIGH |
| 2 | Remove global CollapsibleFilters from Omniview views | 10 min | HIGH |
| 3 | Add focus-mode dimming for secondary context | 1 hr | MEDIUM |
| 4 | Add fullscreen matrix drill (ESC to exit) | 1 hr | MEDIUM |
| 5 | Collapse status banners into single bar | 2 hr | HIGH |
| 6 | Add smart empty states with remediation guidance | 2 hr | HIGH |
| 7 | Add skeleton loading improvements | 1 hr | MEDIUM |
| 8 | Add current period visual dominance | 30 min | MEDIUM |
| 9 | Group control bar logically | 1 hr | MEDIUM |
| 10 | Add `useMemo`/`React.memo` for performance | 2 hr | HIGH |

---

## 7. PRIORITY MATRIX

| Priority | Task | Phase |
|---|---|---|
| **CRITICAL** | Remove redundant navigation entries | 2 |
| **CRITICAL** | Collapse status banners → Operational Status Bar | 2 |
| **CRITICAL** | Smart empty states | 3 |
| **HIGH** | Focus mode with context dimming | 2 |
| **HIGH** | Fullscreen matrix drill | 2 |
| **HIGH** | Performance memoization | 4 |
| **HIGH** | Current period dominance | 2 |
| **MEDIUM** | Control bar logical grouping | 2 |
| **MEDIUM** | Noise reduction (badges, text) | 2 |
| **MEDIUM** | Action context on selection | 3 |
| **LOW** | Selection history persistence | 3 |
| **LOW** | Long-load time estimates | 3 |

---

## 8. RISKS

| Risk | Mitigation |
|---|---|
| Breaking Omniview Matrix rendering | All changes behind feature checks, incremental rollout |
| Filter persistence loss | Test filter state preservation before/after each change |
| User confusion with new layout | Keep visual language consistent, preserve muscle memory |
| Performance regression | Profile before/after, use React.memo carefully |
| Breaking fullscreen/ESC behavior | Keep existing ESC handlers, add new ones non-conflicting |

---

## 9. GO / NO-GO RECOMMENDATION

**GO** for all Phase 1H.3 changes. Risks are manageable. All changes respect:
- No new engines activated
- No AI layers touched
- No runtime heavy fallback
- Serving-first architecture preserved
- Omniview Matrix remains canonical operational view

---

*End of UX Workflow Audit — Phase 1H.3*
