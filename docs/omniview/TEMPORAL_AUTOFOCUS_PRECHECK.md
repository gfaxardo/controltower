# TEMPORAL AUTO-FOCUS & PRESENT PERIOD AUTHORITY — PRECHECK

**Date**: 2026-05-25
**Motor**: Control Foundation (GO) + Diagnostic Engine (ACTIVE 2A.3)
**Phase**: 1H.4 — Operational Maturity Governance Layer
**Fase sub**: Temporal Auto-Focus Hardening

---

## 1. ACTIVE PHASE

- **Motor**: Control Foundation
- **Phase**: 1H.4 — Operational Maturity Governance Layer
- **Status**: ACTIVE
- **Allowed changes**: UX operacional, focus mode, fullscreen drill, Omniview hardening, performance perceptual

---

## 2. READY NEXT

- **Motor**: Diagnostic Engine
- **Phase**: 2A.3 — Behavioral Pattern Diagnosis
- **Status**: READY NEXT (NOT ACTIVE)
- **Blocked until**: Serving Governance Foundation stabilized

---

## 3. GO / NO-GO ASSESSMENT

### GO ✅

| Factor | Assessment |
|--------|-----------|
| Motor alignment | Control Foundation — UX operacional hardening is fully in scope |
| Phase alignment | 1H.4 explicitly allows Omniview hardening, focus mode, operational UX |
| No new engine | No new engine activation required |
| No runtime heavy | Auto-scroll uses native `container.scrollTo()`, no polling, no loops |
| No virtualization break | Scroll container is a plain `<div>` with `overflow-x: auto`. Virtualization is "soft" (visible column tracking only, all columns rendered). Scroll does not interact with virtualization logic except updating `visibleColRange` via passive scroll listener — already exists. |
| No sticky break | Sticky positioning is pure CSS (thead `sticky top-0`, left labels `sticky left-0`). Horizontal scroll is native and does not affect sticky behavior. |
| No aggressive render | Ref-based `autoScrollAppliedRef` guard prevents repeated auto-scroll. No re-render triggered by scroll except React state updates already existing. |
| Build expected | No new dependencies, no new API calls, no structural changes. |

### NO-GO Risks: NONE

| Risk | Assessment |
|------|-----------|
| Scroll loops | Guarded by `autoScrollAppliedRef` — fires once, never repeats |
| Aggressive scroll | `behavior: 'smooth'` + single `scrollTo` call |
| Re-render severo | Scroll does not trigger React state changes (except existing `visibleColRange` update via passive listener) |
| Virtualization rota | No change to virtualization logic — all columns remain rendered |
| Sticky roto | No CSS changes to sticky positioning |
| Fuentes gigantes globales | Only current-period cells receive visual upgrades, not the entire matrix |
| Matrix inestable | No structural changes to matrix building or rendering |

---

## 4. SCROLL RISKS

| Risk | Level | Mitigation |
|------|-------|-----------|
| Auto-scroll fights user navigation | LOW | `autoScrollAppliedRef` set only on first load; reset only on grain/viewMode changes (not on city/businessSlice/focusedKpi changes) |
| Scroll position lost on re-render | LOW | Scroll is DOM-level, not React-level; re-renders don't reset scroll position of DOM element |
| Smooth scroll too slow/aggressive | LOW | `behavior: 'smooth'` is native CSS scroll-behavior; 300ms delay ensures DOM is fully rendered |
| Column width mismatch on scroll calc | LOW | Column width is deterministic: `compact ? 58 : 66` for evolution, `compact ? 78 : 100` for projection |

---

## 5. VIRTUALIZATION RISKS

| Risk | Level | Mitigation |
|------|-------|-----------|
| Visible col range incorrect after auto-scroll | NONE | `visibleColRange` updates via passive scroll listener — auto-scroll triggers the same event |
| Columns outside viewport not rendered | NONE | **All columns are rendered** — "soft virtualization" only tracks visibility for the footer indicator. No actual DOM virtualization. |
| Scroll event loop | NONE | Passive listener, no state update in scroll handler beyond `setVisibleColRange` |

---

## 6. RE-RENDER RISKS

| Risk | Level | Mitigation |
|------|-------|-----------|
| Auto-scroll triggers re-renders | NONE | `container.scrollTo()` is a DOM API call, not a state change |
| `visibleColRange` update triggers cascading re-renders | LOW | Only affects the footer indicator text (1 small element) |
| isCurrentPeriod changes trigger re-renders | LOW | `currentPeriodKey` is memoized with `useMemo([grain])` — stable reference |
| Visual authority classes trigger re-renders | NONE | Pure CSS classes, no state changes |

---

## 7. VERDICT: GO ✅

All preconditions are met:
- ✅ Motor + Phase aligned
- ✅ No new engine activation
- ✅ No runtime heavy logic
- ✅ No virtualization/sticky/scroll risks
- ✅ All changes are CSS + minor React state guard adjustments
- ✅ No structural changes to matrix

Proceed to implementation.
