# OPERATIONAL UI AUDIT — YEGO Control Tower

**Date**: 2026-05-25
**Scope**: Full frontend codebase
**Severity**: HIGH — Operational UX degradation affecting speed and reliability

---

## 1. EXECUTIVE SUMMARY

YEGO Control Tower has reached operational maturity but the UX has degraded through organic growth. 1197+ instances of `text-xs` or hardcoded pixel sizes (down to 6px), inconsistent spacing, oversized banners, and no container governance create:

- **Visual fatigue** — text sizes below 12px dominate critical operational views
- **Zoom dependency** — many components are illegible at 100% zoom
- **Viewport fragility** — matrix uses `calc(100vh - 240px)` hardcoded values
- **Hierarchy inversion** — banners dominate viewport over data and CTAs
- **Spacing chaos** — no tokenized spacing scale; each component chooses its own

---

## 2. DEBT HOTSPOTS (ordered by criticality)

### HOTSPOT 1: Microscopic Text — CRITICAL

| Size | Occurrences | Locations | Impact |
|------|------------|-----------|--------|
| `text-[6px]` | 1+ micro labels | Matrix cell confidence indicators | **Invisible** without zoom |
| `text-[7px]` | Several | Compact projection/status values in matrix cells | **Illegible** |
| `text-[8px]` | Many | Compact badges, tooltip detail | Barely readable |
| `text-[9px]` | Very common | Badges, tooltips, integrity banners, compact KPIs | **Below WCAG AA** |
| `text-[10px]` | Extremely common | Labels, filter titles, contextual info, chips | Widely used as "normal" size |
| `text-[11px]` | Extremely common | Secondary text, banner content, metadata | Near-acceptable but inconsistent |

**Key files**:
- `BusinessSliceOmniviewMatrix.jsx` — 7px to 14px range, worst offender
- `BusinessSliceOmniviewMatrixCell.jsx` — dynamic sizes via valSize/deltaSize props
- `BusinessSliceOmniviewMatrixHeader.jsx` — 9px/10px in compact mode
- `MatrixExecutiveBanner.jsx` — all content at 10px/11px
- `OmniviewPriorityPanel.jsx` — 8px badges, 9px subtitles
- `MaturityIndicators.jsx` — 9px badges

### HOTSPOT 2: Banners Dominating Viewport — HIGH

| Component | Height | Font Size | Issue |
|-----------|--------|-----------|-------|
| `GlobalFreshnessBanner` | `py-1.5` + expandable table | `text-2xs` (10px) | Overly compact when expanded, table at 10px |
| `MatrixExecutiveBanner` | `px-3 py-1.5` + multi-line content | `text-[10px]`/`[11px]` | Dense but long content can dominate |
| `OperationalStatusBar` | `py-1.5` collapse, expandable | `text-xs` / `text-[10px]` | Best in class but expanded chips at 10px |

**Issue**: Multiple stacked banners (freshness + margin quality + status bar) consume 80-120px before data is visible.

### HOTSPOT 3: Header Stack Height — HIGH

| Layer | Height | Conditional |
|-------|--------|-------------|
| Main nav bar | `h-11` (44px) | Always |
| Sub-tab bar | ~32px (`py-1.5`) | When subtabs exist |
| Maturity status bar | ~24px (`py-1`) | Non-stable modules |
| **Total potential** | **~100px** | Before any content |

Content area `px-3 sm:px-4 py-3` then adds more padding before scrollable regions.

### HOTSPOT 4: No Container Governance — HIGH

- No `max-width` constraints on any operational view
- Matrix uses viewport-breaking `width: 100vw` trick
- Form components have no grid system
- Scroll regions use hardcoded `calc(100vh - 240px)` values
- No consistent gutter/spacing between sections

### HOTSPOT 5: Form UX Chaos — MEDIUM

- **No shared form components** — every view builds its own
- **Filter labels at 10px** — illegible (OmniviewFilterPrimitives.jsx)
- **CollapsibleFilters at 10px** — toggle button text-2xs
- **Native selects only** — no search, no grouped options
- **KPI focus toggle buttons at 10px** — critical filter invisible
- **Projection version selector at 9px** — barely readable

### HOTSPOT 6: Z-Index Fragility — MEDIUM

```
z-5   → RecoverabilityDashboard headers
z-10  → Sticky left columns in Matrix tables
z-18  → Sticky totals row in Matrix
z-20  → Sticky table headers
z-30  → Sticky left header column
z-40  → App navigation header
z-50  → Sidebar panels
z-80  → Modal backdrops
z-100 → Fullscreen overlays
```

No `zIndex` constant registry. Values scattered across 8+ files.

### HOTSPOT 7: Scroll Region Hardcoding — MEDIUM

| Location | Value | Issue |
|----------|-------|-------|
| `BusinessSliceOmniviewMatrixTable.jsx` | `calc(100vh - 240px)` | Brittle; header height changes |
| `BusinessSliceOmniviewProjectionTable.jsx` | `calc(100vh - 240px)` | Same brittleness |
| `BusinessSliceOmniviewInspector.jsx` | `max-h-[68vh]`, `max-h-[50vh]` | Hardcoded viewport fractions |
| `OmniviewProjectionDrill.jsx` | `calc(100vh - 200px)` | Inconsistent with other views |
| `DriverLifecycleDashboard.jsx` | `max-h-[600px]` | Hardcoded pixel value |

---

## 3. QUICK WINS (no-risk, high-impact)

| # | Action | Impact | Risk |
|---|--------|--------|------|
| 1 | Create `ct-design-tokens.css` with typography/space scale | Foundation | None |
| 2 | Raise minimum font to `text-xs` (12px) everywhere except matrix cell data | Legibility | Low |
| 3 | Add `max-w-[1400px]` content container with margin auto | Viewport governance | Very low |
| 4 | Reduce GlobalFreshnessBanner expanded table font to `text-xs` (from 2xs) | Legibility | None |
| 5 | Standardize `py-1.5` → `py-1` on banners (recover 4-8px per banner) | Viewport efficiency | None |
| 6 | Create `ct-toolbar` / `ct-panel` / `ct-section` layout CSS classes | Consistency | None |
| 7 | Raise filter labels from `text-[10px]` to `text-xs` | Form usability | None |
| 8 | Raise maturity badges from `text-[9px]` to `text-[11px]` | Metadata legibility | None |

---

## 4. RISK REGISTER

| Risk | Probability | Severity | Mitigation |
|------|------------|----------|------------|
| Matrix cell sizing breaks when raising minimum | Medium | High | Keep matrix cells at current sizes; they NEED density. Isolate as exception |
| Scroll regions break with new layout primitives | Low | High | Use `calc()` with CSS custom properties, not hardcoded values |
| Banner reduction hides critical info | Low | Medium | Expand-on-click pattern already works; keep it |
| Form select styling breaks with tokenization | Low | Low | Only change class names, not structure |

---

## 5. COMPONENT CLASSIFICATION

### TOUCH (high-impact)
- `GlobalFreshnessBanner.jsx` — font size, padding
- `MatrixExecutiveBanner.jsx` — font size  
- `OmniviewFilterPrimitives.jsx` — label fonts, select sizing
- `CollapsibleFilters.jsx` — button font
- `MaturityIndicators.jsx` — badge font size
- `OperationalStatusBar.jsx` — expanded chip font
- `SmartEmptyState.jsx` — action hint font
- `App.jsx` — header sizing, content padding, layout primitives
- `index.css` — add layout primitives
- `tailwind.config.js` — font size scale

### OBSERVE (risk of breakage)
- `BusinessSliceOmniviewMatrix.jsx` — extremely complex; only touch banners/alerts within
- `BusinessSliceOmniviewMatrixCell.jsx` — cell sizing is intentional density
- `BusinessSliceOmniviewMatrixHeader.jsx` — header sizing tied to cell widths
- `BusinessSliceOmniviewMatrixTable.jsx` — scroll calc values

### DON'T TOUCH
- `echartsTheme.js` / `echartsRegister.js` — charting config, not visual debt
- `omniviewUtils.js` / `insightEngine.js` — pure logic
- API service files
- Backend files

---

## 6. BASELINE MEASUREMENTS

### Typography inventory
| Token | Current Usage | Proposed Minimum |
|-------|--------------|-----------------|
| 6px (`text-[6px]`) | 1+ locations | Remove / 10px if matrix-internal |
| 7px (`text-[7px]`) | Several | Remove / 10px if matrix-internal |
| 8px (`text-[8px]`) | Many | 10px (matrix exceptions only) |
| 9px (`text-[9px]`) | Very common | 11px |
| 10px (`text-[10px]`, `text-2xs`) | Extremely common | 12px (`text-xs`) |
| 11px (`text-[11px]`) | Extremely common | 12px (`text-xs`) |
| 12px (`text-xs`) | Common | Keep as minimum for UI chrome |

### Spacing inventory
| Pattern | Current | Proposed |
|---------|---------|----------|
| Banner padding | `px-3 py-1.5` | `px-3 py-1` |
| Section gap | Ad-hoc `space-y-*` | `gap-2` / `gap-3` |
| Content padding | `px-3 sm:px-4 py-3` | `px-4 py-2` |
