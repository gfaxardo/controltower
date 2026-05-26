# SCROLL OWNERSHIP AUDIT — OMNIVIEW PROYECCIÓN

**Date**: 2025-05-25
**Foco**: Vs Proyección (NO Evolution)

---

## 1. ÁRBOL REAL DE SCROLL CONTAINERS

```
<div data-omniview-matrix-root>                                    ← root (Matrix.jsx:1268)
│   overflow-x-hidden                                               ← CLIPS horizontal overflow
│   width: 100vw, left: 50%, margin-left: -50vw                     ← full bleed
│
├── <div px-3 space-y-2>                                           ← content wrapper
│   ├── OmniviewCommandHeader
│   ├── OmniviewMomentumPriorityStrip
│   ├── <div overflow-hidden>                                      ← controls wrapper (line 1303)
│   │   │   overflow-hidden                                         ← CLIPS controls overflow
│   │   └── filters, grain, zoom, etc.
│   └── ... other components ...
│
├── {Evolution mode}
│   └── <div flex gap-3>                                           ← matrix + inspector (line 1791)
│       ├── <div flex-1 min-w-0>                                   ← zoom wrapper (line 1792)
│       │   │   transform: scale(zoom%)                             ← scale transform
│       │   └── BusinessSliceOmniviewMatrixTable
│       │       └── <div rounded-lg overflow-hidden>                ← table wrapper (Table:248)
│       │           │   overflow-hidden                              ← CLIPS overflow
│       │           └── <div ref={scrollContainerRef}               ← **HORIZONTAL + VERTICAL SCROLL OWNER** (Table:262)
│       │               │   overflow-x-auto                           ← horizontal scrollbar #1
│       │               │   overflow-y-auto                           ← vertical scrollbar #1
│       │               │   maxHeight: calc(100vh - 240px)           ← explicit max height
│       │               │
│       │               └── <table min-w-full>
│       │                   ├── colgroup (2 fixed + N period cols)
│       │                   ├── Header (sticky top)
│       │                   ├── TotalsRow (sticky top: headerH)
│       │                   ├── CityBlock (sticky left col 1-2)
│       │                   └── LineRow (sticky left col 1-2)
│       │
│       └── BusinessSliceOmniviewInspector                         ← sidebar
│           overflow-y-auto on .ct-layer-drill (CSS)

├── {Projection mode — normal}
│   └── <div flex gap-3>                                           ← matrix + drill (line 1902)
│       ├── <div flex-1 min-w-0>                                   ← zoom wrapper (line 1903)
│       │   └── BusinessSliceOmniviewMatrixTable
│       │       └── <div rounded-lg overflow-hidden>                ← **SAME TABLE WRAPPER**
│       │           └── <div ref={scrollContainerRef}               ← **SAME SCROLL OWNER**
│       │               │   **BUT: scrollContainerRef.current is null until mount**
│       │               │   **auto-scroll never fires for projection**
│       │
│       └── OmniviewProjectionDrill                                ← sidebar

├── {Evolution fullscreen}
│   └── <div fixed inset-0 z-[100] overflow-y-auto>                ← fullscreen scroll (line 1747)
│       └── BusinessSliceOmniviewMatrixTable
│           └── <div ref={scrollContainerRef}                       ← **SAME ref; NEW instance in fullscreen DOM**

├── {Projection fullscreen}
│   └── <div fixed inset-0 z-[100] overflow-y-auto>                ← fullscreen scroll (line 1858)
│       └── BusinessSliceOmniviewMatrixTable
│           └── <div ref={scrollContainerRef}                       ← **SAME ref; NEW instance in fullscreen DOM**
```

---

## 2. WHO CONTROLS WHAT

| Layer | Element | Scroll Control | Issue |
|---|---|---|---|
| **Root** | `data-omniview-matrix-root` | `overflow-x-hidden` | Clips everything. Prevents horizontal scroll at page level. |
| **Controls** | wrapper div | `overflow-hidden` | Clips filter content. Not scrollable. |
| **Table outer** | `rounded-lg overflow-hidden` | `overflow-hidden` | CLIPS the table borders. **This is the potential double-scrollbar generator.** |
| **Table inner** | `ref={scrollContainerRef}` | `overflow-x-auto overflow-y-auto` | **THE REAL SCROLL OWNER.** Attached to `scrollContainerRef`. |
| **Fullscreen** | `fixed inset-0 overflow-y-auto` | `overflow-y-auto` | Owns vertical scroll in fullscreen. Horizontal scroll still in inner table. |
| **Inspector** | `.ct-layer-drill` | `overflow-y-auto` | Sidebar vertical scroll. OK. |

---

## 3. DOUBLE SCROLLBAR ROOT CAUSE ANALYSIS

### Horizontal double scrollbar

The outer `overflow-hidden` on the table wrapper div (`Table.jsx:248`) combined with the inner `overflow-x-auto` on the scroll container (line 262) can produce a double horizontal scrollbar when:

1. The inner table's `min-w-full` + colgroup exceeds the viewport width
2. The inner div gets a horizontal scrollbar
3. The outer `overflow-hidden` wrapper clips the scrollbar, BUT if the inner div is taller than the wrapper (due to vertical content), the outer wrapper may expand or show its own scrollbar

**Root cause**: `overflow-hidden` wraps an `overflow-auto` child. The hidden overflow on the parent makes the child's scrollbars partially clipped, and the browser may compensate by showing additional scrollbars.

### Vertical double scrollbar

The inner table div has `maxHeight: calc(100vh - 240px)` with `overflow-y-auto`. If this height computation doesn't account for all content above it, the full page may also have a vertical scrollbar.

**Root cause**: `calc(100vh - 240px)` is a hardcoded value that may not match actual toolbar heights on all viewports, causing both the inner and outer containers to be scrollable.

---

## 4. REDUNDANT WRAPPERS

| Wrapper | Purpose | Needed? |
|---|---|---|
| Table `overflow-hidden` wrapper | Border radius + shadow clipping | **YES** but can use `overflow: clip` instead |
| Controls `overflow-hidden` | Border clipping | YES |
| Root `overflow-x-hidden` | Full-bleed without horizontal page scroll | YES, but needs careful management |
| Zoom `min-w-0` wrapper | Overflow containment for scale() | YES |

---

## 5. SCROLL CONTAINER IDENTITY

**The REAL scroll owner is:**

```
<div ref={scrollContainerRef}
     className="overflow-x-auto overflow-y-auto"
     style={{ maxHeight: 'calc(100vh - 240px)' }}>
```

This div:
- Owns BOTH horizontal and vertical scroll
- Contains the sticky elements (header, totals, city/label columns)
- Is the target of `scrollToCurrentPeriod()`
- Is the source of `visibleColRange` event
- Contains the entire `<table>` element

**BUT** it is wrapped in `overflow-hidden` which clips its scrollbars and causes the confusion.

---

## 6. RECOMMENDATION

1. Change outer table wrapper from `overflow-hidden` to `overflow-clip` to prevent double scrollbars while keeping border clipping
2. Ensure the root `overflow-x-hidden` doesn't conflict
3. Fix the auto-scroll to work for projection mode
4. Add a projection-specific scroll centering engine
5. Verify that the vertical `maxHeight` doesn't conflict with other content
