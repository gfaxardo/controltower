# TEMPORAL RENDER AUDIT — OMNIVIEW MATRIX

**Date**: 2026-05-25
**Purpose**: Auditar cómo se renderizan columnas, cómo se identifica el periodo actual, y cómo funciona el scroll horizontal.

---

## 1. COLUMN RENDERING PATH

```
BusinessSliceOmniviewMatrix.jsx
├── buildMatrix(rows, grain) → { allPeriods: string[], cities: Map, totals: Map, ... }
├── currentPeriodKey = getCurrentPeriodKey(grain) → "YYYY-MM-DD" / "YYYY-MM-DD" (ISO Mon) / "YYYY-MM-01"
├── computePeriodStates(allPeriods) → Map<periodKey, PERIOD_STATE>
└── passes to BusinessSliceOmniviewMatrixTable:
    ├── currentPeriodKey (prop)
    ├── allPeriods (from matrix)
    └── scrollContainerRef (ref)

BusinessSliceOmniviewMatrixTable.jsx
├── scrollContainerRef → <div ref={scrollContainerRef}>
├── <colgroup> → one <col> per period
├── BusinessSliceOmniviewMatrixHeader
│   └── isCurrentPeriod(pk, grain) → blue background + ring + badge
├── TotalsRow (sticky)
└── CityBlock → LineRow → BusinessSliceOmniviewMatrixCell
    └── isCurrentPeriod = currentPeriodKey === pk → blue background cell
```

---

## 2. CURRENT PERIOD IDENTIFICATION

### Source: `omniviewMatrixUtils.js`

```
getCurrentPeriodKey(grain)
  daily   → new Date() → "2026-05-25"
  weekly  → getMondayOfISOWeek(now) → "2026-05-25" (ISO Monday)
  monthly → "2026-05-01"

isCurrentPeriod(pk, grain)
  → pk === getCurrentPeriodKey(grain)

findCurrentPeriodIndex(allPeriods, grain)
  → indexOf(currentKey) || fallback: last period <= currentKey

getCurrentPeriodBadge(pk, grain)
  daily → "HOY"
  weekly → "SEMANA ACTUAL"
  monthly → "MES ACTUAL"
```

### Usage points:

| Location | How `isCurrentPeriod` is checked |
|----------|-------------------------------|
| `BusinessSliceOmniviewMatrixHeader.jsx:53` | `isCurrentPeriod(pk, grain)` → blue bg + ring + badge |
| `BusinessSliceOmniviewMatrixTable.jsx:621` | `currentPeriodKey === pk` → prop to cell |
| `BusinessSliceOmniviewMatrixCell.jsx:40` | `isCurrentPeriod` prop → `bg-blue-50/20` background |

---

## 3. "HOY" (TODAY) LOCATIONS

| Location | How "HOY" appears |
|----------|-------------------|
| Header badge | `<span className="text-[8px] bg-blue-500">HOY</span>` |
| Cell background | `className="bg-blue-50/20"` (very subtle light blue) |
| Button | "Ir a hoy" button triggers `scrollToCurrentPeriod()` |
| Period state label | `CURRENT_DAY` → "Hoy" (state badge, not the same as current period highlight) |

---

## 4. VIRTUALIZATION

**Type**: Soft virtualization (all columns rendered, visibility tracked only)

```
BusinessSliceOmniviewMatrixTable.jsx:183-197
  useEffect → adds 'scroll' passive listener
  update() → computes visibleColRange from scrollLeft + clientWidth + colW
  Only used in: footer indicator "Mostrando columnas X–Y de Z"
```

No actual DOM virtualization. All columns are always rendered.

---

## 5. HORIZONTAL SCROLL

### Scroll container:

```
BusinessSliceOmniviewMatrixTable.jsx:262
  <div ref={scrollContainerRef} className="overflow-x-auto overflow-y-auto" />
```

### Auto-scroll to current period:

```
BusinessSliceOmniviewMatrix.jsx:1049-1061
  scrollToCurrentPeriod()
    → colW = compact ? 58 : 66
    → idx = findCurrentPeriodIndex(allPeriods, grain)
    → targetLeft = COL1_W + COL2_W + (idx * colW)
    → scrollTo = targetLeft - viewportWidth/2 + colW/2
    → container.scrollTo({ left: scrollTo, behavior: 'smooth' })

BusinessSliceOmniviewMatrix.jsx:1063-1072
  useEffect → on first load (loading=false, data present)
    → setTimeout(300ms) → scrollToCurrentPeriod()
    → autoScrollAppliedRef = true

BusinessSliceOmniviewMatrix.jsx:1074-1076
  → autoScrollAppliedRef resets on: grain, year, viewMode, country, city, businessSlice, focusedKpi
```

**PROBLEM IDENTIFIED**: `autoScrollAppliedRef` resets on ALL filter changes including `city`, `businessSlice`, `focusedKpi`. This means changing city or focused KPI re-triggers auto-scroll — fighting with user navigation.

---

## 6. STICKY ELEMENTS

| Element | Sticky behavior | CSS |
|---------|----------------|-----|
| Header (thead) | `sticky top-0 z-20` | CSS |
| City label (left) | `sticky left-0 z-10` | CSS |
| Line label (left) | `sticky z-10` with `left: COL1_W` | CSS |
| TotalsRow | `position: sticky, top: headerH, z-index: 18` | Inline style |
| Inspector panel | `self-start sticky top-2` | CSS |

---

## 7. WEEKDAY FOCUS

```
BusinessSliceOmniviewMatrix.jsx
  filterWeekdayFocus(matrix, grain, weekdayFocus)
    → Filters allPeriods to only days matching the selected weekday (0-6)
    → Applied to both displayMatrix and displayProjMatrix

Weekday focus does NOT interact with current-period logic.
If today is DOM and weekdayFocus = DOM → columns are already filtered to DOM days.
```

---

## 8. REF CONTAINER AUDIT

| Ref | Owner | Purpose |
|-----|-------|---------|
| `scrollContainerRef` | `BusinessSliceOmniviewMatrix.jsx:1040` | Created via `useRef(null)`, passed to `BusinessSliceOmniviewMatrixTable` which attaches it to the scrollable `<div>` |
| `autoScrollAppliedRef` | `BusinessSliceOmniviewMatrix.jsx:1047` | Boolean guard — prevents repeated auto-scroll |
| `execNavPendingRef` | `BusinessSliceOmniviewMatrix.jsx:1039` | Guards executive navigation |

---

## 9. TIMING AUDIT

```
1. Data fetched (getBusinessSliceDaily/Weekly/Monthly)
2. rows state updated
3. matrix = buildMatrix(rows, grain) — useMemo
4. currentPeriodKey = getCurrentPeriodKey(grain) — useMemo
5. displayMatrix depends on matrix, weekFocusOnly, weekdayFocus — useMemo
6. Matrix renders (table mounts)
7. useEffect fires: loading=false, rows.length>0
8. setTimeout(300ms) → scrollToCurrentPeriod()
9. autoScrollAppliedRef = true
```

Issue: The 300ms timeout is a hack. Better to use `requestAnimationFrame` or `useLayoutEffect`. However, 300ms is acceptable for this purpose and avoids DOM-not-ready timing issues.

---

## 10. FINDINGS

1. **Auto-scroll reset is too broad**: `autoScrollAppliedRef` resets on ALL filter changes, including city/businessSlice/focusedKpi which are user navigation actions. Should only reset on grain/viewMode changes.

2. **Visual authority is too subtle**:
   - Cell: `bg-blue-50/20` is barely visible
   - Header badge: `text-[8px]` is the smallest text in the header
   - Main value font size has no increase for current period cells

3. **No "last operational day" fallback**: If today's data hasn't been loaded (e.g., daily grain with no data for today), `findCurrentPeriodIndex` falls back to the last period <= currentKey. This is correct behavior but the code in `getCurrentPeriodKey` always returns today's date, which may not exist in the data.

4. **Scroll target calculation is correct**: `targetLeft = COL1_W + COL2_W + (idx * colW)` accounts for fixed left columns. `scrollTo = targetLeft - viewportWidth/2 + colW/2` centers the column.

5. **Projection mode has wider columns** (colW = 78-100 vs 58-78) but `scrollToCurrentPeriod` always uses the evolution column width (58-66). This means auto-scroll targeting may be slightly off in projection mode. However, auto-scroll only runs in evolution mode currently (scrollToCurrentPeriod button hidden in projection mode per line 1537).

---

## VERDICT

Render path is clear. Scroll/ref/timing are understood. Ready to harden.
