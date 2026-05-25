# OMNIVIEW MOMENTUM INTERACTION AUDIT

**Date**: 2026-05-25

---

## READY

| Feature | Status |
|---------|--------|
| Daily weekday labels in column headers | ✅ `periodDayLabels` Map available |
| Fullscreen drill (Inspector) | ✅ Already implemented |
| Fullscreen drill (ProjectionDrill) | ✅ Already implemented |
| Escape to close fullscreen | ✅ Already implemented |

## HIDDEN (data exists, not surfaced)

| Feature | Data exists | What's missing |
|---------|-----------|----------------|
| Weekday column filtering | `periodDayLabels` + `DAYS_ES` | No `weekdayFocus` state or filter mechanism |
| Momentum color authority | `comparison_mode` on every delta | Cell renderer doesn't prioritize momentum colors |
| Momentum drill chart mode | Period deltas in selection data | No momentum vs plan toggle in drill |

## MISSING (needs backend work — deferred)

| Feature | Gap |
|---------|-----|
| Momentum-specific endpoint for drill | Drill uses plan-vs-real endpoint. Momentum would need same-weekday historical series |
| DoD same-weekday historical series beyond current selection | Not in serving facts |

## UNSAFE (do not touch)

| Feature | Reason |
|---------|--------|
| Sticky header mechanics | Complex z-index layering |
| Scroll container sizing | `calc(100vh - 240px)` hardcoded |
| Cell rendering logic | Core matrix function |
| Projection calculation | Serving facts dependent |
