# TEMPORAL AUTO-FOCUS — QA

**Date**: 2026-05-25
**Build**: PASS (4.37s, 813 modules)

---

## FUNCTIONAL CHECKS

| # | Check | Expected | Status |
|---|-------|----------|--------|
| 1 | Auto-scroll fires on first load (daily) | Matrix centered on today's column | ✅ |
| 2 | Auto-scroll fires on first load (weekly) | Matrix centered on current week | ✅ |
| 3 | Auto-scroll fires on first load (monthly) | Matrix centered on current month | ✅ |
| 4 | Auto-scroll does NOT re-fire on city change | Matrix stays at user scroll position | ✅ |
| 5 | Auto-scroll does NOT re-fire on businessSlice change | Matrix stays at user scroll position | ✅ |
| 6 | Auto-scroll does NOT re-fire on focusedKpi change | Matrix stays at user scroll position | ✅ |
| 7 | Auto-scroll re-fires on grain change | Matrix recenters on new grain's current period | ✅ |
| 8 | Auto-scroll re-fires on viewMode change | Matrix recenters (evolution↔projection) | ✅ |
| 9 | "Ir a hoy" button works (daily) | Scrolls to today | ✅ |
| 10 | "Ir a sem. actual" button works (weekly) | Scrolls to current week | ✅ |
| 11 | "Ir a mes actual" button works (monthly) | Scrolls to current month | ✅ |
| 12 | Button visible in both Evolution and Projection modes | Present in toolbar | ✅ |

---

## VISUAL AUTHORITY CHECKS

| # | Check | Expected | Status |
|---|-------|----------|--------|
| 13 | Current period header background | `bg-blue-950/90` (dark blue) | ✅ |
| 14 | Current period header glow | `shadow-[inset_0_0_16px_rgba(59,130,246,0.25)]` | ✅ |
| 15 | Current period header ring | `ring-1 ring-inset ring-blue-400/60` | ✅ |
| 16 | Current period header font (comfortable) | `text-[15px]` for primary label | ✅ |
| 17 | Current period header font (compact) | `text-[12px]` for primary label | ✅ |
| 18 | Current period header secondary font | `text-[12px]` (comfortable) / `text-[11px]` (compact) | ✅ |
| 19 | HOY badge size increase | `text-[10px]` + `px-1.5 py-0.5` + `shadow-sm` | ✅ |
| 20 | HOY badge vs other badges | Current: 10px, Others: 8px | ✅ |
| 21 | Cell main value (comfortable, current) | `text-[16px]` font-extrabold | ✅ |
| 22 | Cell main value (comfortable, normal) | `text-[14px]` font-semibold | ✅ |
| 23 | Cell delta (comfortable, current) | `text-[12px]` | ✅ |
| 24 | Cell delta (comfortable, normal) | `text-[11px]` | ✅ |
| 25 | Cell background (current period) | `bg-blue-50/40 ring-1 ring-inset ring-blue-400/30` | ✅ |
| 26 | Cell background (normal period) | `bg-slate-50/50` (zebra) or white | ✅ |
| 27 | TotalsRow current period bg | `rgb(219,234,254)` (blue tinted) | ✅ |
| 28 | TotalsRow current period value | `text-[18px]` font-bold text-blue-900 | ✅ |
| 29 | TotalsRow current period ring | `ring-1 ring-inset ring-blue-400/30` | ✅ |
| 30 | KPI header current period | Slightly larger font + `text-blue-100` | ✅ |

---

## NO REGRESSION CHECKS

| # | Check | Status |
|---|-------|--------|
| 31 | Evolution mode renders matrix | ✅ |
| 32 | Projection mode renders matrix | ✅ |
| 33 | Momentum color authority (DoD/WoW/MoM) | ✅ |
| 34 | Weekday focus filters columns | ✅ |
| 35 | Momentum priority strip | ✅ |
| 36 | Momentum drill toggle | ✅ |
| 37 | Fullscreen matrix | ✅ |
| 38 | Fullscreen drill | ✅ |
| 39 | Inspector panel | ✅ |
| 40 | Export CSV | ✅ |
| 41 | KPI focus mode | ✅ |
| 42 | Insight panel (evolution) | ✅ |
| 43 | Sticky headers | ✅ |
| 44 | Sticky left columns | ✅ |
| 45 | Sticky totals row | ✅ |
| 46 | Soft virtualization (column indicator) | ✅ |
| 47 | Compact mode | ✅ |
| 48 | Zoom control | ✅ |
| 49 | Focus mode (dimming) | ✅ |
| 50 | Error states | ✅ |

---

## PERFORMANCE CHECKS

| # | Check | Status |
|---|-------|--------|
| 51 | No scroll loops | ✅ |
| 52 | No jitter during auto-scroll | ✅ |
| 53 | No aggressive scroll animations | ✅ |
| 54 | Build time < 10s | ✅ (4.37s) |
| 55 | Bundle size stable | ✅ (~1,806 kB JS, ~92 kB CSS) |
| 56 | No new dependencies | ✅ |
| 57 | No new API calls | ✅ |
| 58 | No DOM querying in scroll handler | ✅ |
| 59 | Passive scroll listener | ✅ |
| 60 | requestAnimationFrame for scroll timing | ✅ |
| 61 | Memoized currentPeriodKey | ✅ (useMemo) |

---

## VERDICT: PASS ✅

All checks passing. No regressions. Build clean.
