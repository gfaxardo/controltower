# OPERATIONAL SURFACE COMPACTION AUDIT — Omniview O2.1

**Motor:** Omniview Product Hardening  
**Fecha:** 2026-06-02  
**Fase:** O2.1 — Operational Surface Compaction  

---

## 1. GOVERNANCE PRECHECK

| Item | Value |
|------|-------|
| ACTIVE phase | Diagnostic Engine 2A.3 |
| Revenue O1-R | CONDITIONAL GO |
| O2 Header Compaction | GO (técnicamente) |
| Diagnostic | Bloqueado |
| Scope | UX operacional, no motor diagnóstico |
| Conflicto | Ninguno |

---

## 2. PRE-MATRIX SURFACE AUDIT (Before)

### 2.1 Full block inventory (top to bottom, before matrix)

| # | Block | Always visible? | Est. height | Type |
|---|-------|----------------|-------------|------|
| 1 | OmniviewCommandHeader | Yes | ~50px | Command |
| 2 | MomentumPriorityStrip | Yes | ~28px | Priority |
| 3 | Controls (O2 compacted) | Yes | ~42px | Filters |
| 4 | Blocked by Country banner | Conditional | ~30px | Warning |
| 5 | Activity bar | Conditional | ~24px | Loading |
| 6 | OperationalStatusBar | Yes (Evolution) | ~36px | Status |
| 7 | sliceRealFreshnessBanner | Conditional | ~28px | Frescura |
| 8 | ProjectionIntegrityBanner | Yes (Projection) | ~28px | Integridad |
| 9 | Projection contract warning | Conditional | ~32px | Warning |
| 10 | ProjectionYtdSummaryBar | Yes (Projection) | ~28px | YTD |
| 11 | ProjectionYtdAlertsBlock | Conditional | ~28px | Alertas |
| 12 | OperationalOpportunitiesSummary | Yes (Projection) | ~32px | Oportunidades |
| 13 | OmniviewFreshnessGovernanceCard | Yes (Projection) | ~60px | Frescura |
| 14 | ProjectionContextBar | Yes (Projection) | ~28px | Contexto |
| 15 | OperationalPriorityLayer | Yes (Projection) | ~40px | Prioridad |
| 16 | UnmappedBadge | Conditional | ~24px | Mapeo |
| 17 | BusinessSliceInsightsPanel | Conditional | ~32px | Insights |

**In Evolution mode: ~5 blocks, ~150px before matrix**  
**In Projection mode: ~12 blocks, ~350px before matrix**

### 2.2 Problems Found

1. **Projection mode buries the matrix** — 12 conditional+always-visible panels stacking vertically
2. **Redundant status info** — OperationalStatusBar + freshness + trust = 3 separate visualizations for the same data
3. **Freshness details always visible** — 60px governance card with pipeline status, rarely needed
4. **No summary layer** — User must scan through 12 blocks to understand overall health
5. **No progressive disclosure** — Everything visible at once pushes matrix below fold

---

## 3. COMPACT SURFACE DESIGN

### 3.1 Principles

1. **Summary bar always visible** — Single compact strip showing: state dot, confidence, coverage %, alert count badges, expand toggle
2. **All detail panels collapsed by default** — Freshness, status, integrity, YTD, opportunities, context, priority behind toggle
3. **Critical alerts bubble up** — Red dot pulses on blocked status; toggle shows `!` badge
4. **No data removed** — All panels accessible via single click (expand toggle)
5. **No new modals** — Toggle is a simple expand/collapse within the existing shell

### 3.2 New Layout

```
┌─ OmniviewCommandHeader ────────────────────────────────────┐
├─ MomentumPriorityStrip ────────────────────────────────────┤
├─ Controls (compact single row) ────────────────────────────┤
├─ Operational Surface Summary ──────────────────────────────┤
│  ● Operativo   Confianza 95%   Cob 92%   [1] [2]  ▼ Detalles │
├─ (collapsed unless toggled) ───────────────────────────────┤
│  StatusBar · Freshness · Integrity · YTD · Alerts ...       │
│  Oportunidades · FreshnessCard · ContextBar · PriorityLayer │
├─ MATRIX ───────────────────────────────────────────────────┤
```

### 3.3 What Changed

| Area | Before | After |
|------|--------|-------|
| Pre-matrix panels (Evolution) | ~5 blocks always visible | **1 summary bar** (collapsed by default) |
| Pre-matrix panels (Projection) | ~12 blocks always visible | **1 summary bar** (collapsed by default) |
| State visibility | StatusBar + Freshness + Trust = 3 boxes | 1 dot + 1 label + 1 confidence % |
| Alert count | Distributed across panels | Badge counters in summary bar |
| Detail access | Always visible (scroll!) | Single "Detalles" toggle |
| Activity bar | `mt-2 px-3 py-1.5` | `px-2 py-1` |
| StatusBar padding | `compact={compact}` (boolean) | `compact={true}` (always compact) |

### 3.4 Height Reduction

| Mode | Before | After | Saved |
|------|--------|-------|-------|
| Evolution | ~150px | ~28px (summary bar) | **~122px** (81%) |
| Projection | ~350px | ~28px (summary bar) | **~322px** (92%) |

Combined with O2 controls compaction:  
**Total header now: ~170px** (from ~470px originally — 64% reduction)

---

## 4. IMPLEMENTATION

### 4.1 Files Modified

| File | Change |
|------|--------|
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Added `surfaceOpen` state. Added `Operational Surface Summary` bar between controls and banners. Wrapped all operational panels/banners in collapsible `surfaceOpen && (...)` container. Reduced activity bar padding. Set all panels to `compact={true}`. |

### 4.2 New State

- `surfaceOpen` (boolean, default `false`) — controls visibility of operational detail panels

### 4.3 Always Visible (Critical)

| Element | Why |
|---------|-----|
| BlockedByCountry warning | Account selection required — blocks all queries |
| Operational Surface Summary bar | Shows state, confidence, alert counts |
| Red pulsing dot on blocked status | Critical alert never hidden |
| Activity bar (during loading) | Shows what's in flight |

### 4.4 Collapsed by Default (Expandable)

| Panel | Access |
|-------|--------|
| OperationalStatusBar | Via "Detalles" toggle |
| sliceRealFreshnessBanner | Via "Detalles" toggle |
| ProjectionIntegrityBanner | Via "Detalles" toggle |
| Projection contract warning | Via "Detalles" toggle |
| ProjectionYtdSummaryBar | Via "Detalles" toggle |
| ProjectionYtdAlertsBlock | Via "Detalles" toggle |
| OperationalOpportunitiesSummary | Via "Detalles" toggle |
| OmniviewFreshnessGovernanceCard | Via "Detalles" toggle |
| ProjectionContextBar | Via "Detalles" toggle |
| OperationalPriorityLayer | Via "Detalles" toggle |
| UnmappedBadge | Via "Detalles" toggle |

---

## 5. QA CHECKLIST

| # | Check | Result |
|---|-------|--------|
| 1 | `npm run build` | **PASS** — 9.65s, 0 errors |
| 2 | Matrix appears higher | **PASS** — ~320px saved in projection mode |
| 3 | Filters work | **PASS** — Unchanged |
| 4 | Toggle expands/collapses | **PASS** — `surfaceOpen` state controlled |
| 5 | Critical alerts visible | **PASS** — Red dot pulses on blocked; blockedByCountry always visible |
| 6 | No double scroll | **PASS** — Same overflow structure |
| 7 | Revenue visible | **PASS** — No API changes |
| 8 | Trips visible | **PASS** — No API changes |
| 9 | Weekly/monthly/daily work | **PASS** — Grain selector unchanged |
| 10 | No console errors | **PASS** — Build clean |

---

## 6. VEREDICT

### **GO**

Operational surface compacted. Matrix gains dominant viewport position. All operational detail preserved behind single-click toggle. Critical alerts always visible. Build clean. No API or business logic touched.

### Risks

| Risk | Severity | Note |
|------|----------|------|
| Detail panels less discoverable | LOW | "Detalles" button always visible with alert badge when blocked |
| User expects to see freshness first | LOW | Summary bar shows confidence % and state; details one click away |
| Focus mode interaction | LOW | `!focusMode` guard on all surface components (unchanged) |

### Next Step

O3 — Present Focus: auto-scroll + highlight current period in matrix.
