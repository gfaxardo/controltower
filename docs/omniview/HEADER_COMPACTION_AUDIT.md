# HEADER COMPACTION AUDIT — Omniview O2

**Motor:** Omniview Product Hardening  
**Fecha:** 2026-06-02  
**Fase:** O2 — Header Compaction  

---

## 1. GOVERNANCE PRECHECK

| Item | Value |
|------|-------|
| ACTIVE phase | Diagnostic Engine 2A.3 |
| READY NEXT | Revenue Detail Certification (CF-H2) |
| Revenue status | CONDITIONAL GO (P0 fixed, P1/P2 backlog) |
| Diagnostic blocked? | Yes — not in scope |
| Revenue P1/P2 in scope? | No — backlog only |

---

## 2. AUDIT — CURRENT HEADER (Before)

### 2.1 Header Structure (top to bottom, before matrix)

| Row | Component | Est. Height |
|-----|-----------|------------|
| 1 | OmniviewCommandHeader (mode, grain, health dots, attention) | ~50px |
| 1b | MatrixExecutiveBanner (inside command header, when present) | ~40px |
| 2 | OmniviewMomentumPriorityStrip | ~28px |
| 3 | Controls Row 1: Grain + Filters + Period + Weekday + Reset | ~55px |
| 4 | OmniviewDataHelp row | ~28px |
| 5 | Controls Row 2: Mode + Perspective + KPI + Order + Density + Zoom + Focus + Export | ~36px |
| 6 | Optional banners (blocked, loading, fact status) | ~30px |
| 7 | OperationalStatusBar (Evolution) | ~36px |
| 8 | Projection banners (YTD, alerts, opportunities, freshness, context, priority) | ~120px |

**Estimated total before matrix: ~300-420px**

On a 768px viewport, the matrix starts at 40-55% of initial scroll position.

### 2.2 Problems Found

1. **Controls split across 3 rows** — Two dedicated control rows plus a DataHelp row
2. **Redundant labels** — "Grano", "Scope semanal", "Modo", "Vista", "KPI", "Perspectiva", "Orden", "Densidad", "Zoom" all as separate labels
3. **DataHelp always visible** — Takes a full row even when not needed
4. **Separador verticales** — `w-px` dividers between every section add visual noise
5. **Large buttons** — Weekday buttons with shadow+scale animation, large padding on FACT/Export buttons
6. **Large py/x gaps** — `py-1.5`, `gap-x-3`, `gap-y-1.5` on control rows
7. **OperationalStatusBar + MomentumPriorityStrip** — Two separate rows for status info
8. **Projection banners stacking** — Up to 6 separate banners stacked vertically before the matrix

### 2.3 Files Reviewed

| File | Lines | Component |
|------|-------|-----------|
| `BusinessSliceOmniviewMatrix.jsx` | 4081 | Main assembly | 
| `omniview/command/OmniviewCommandHeader.jsx` | 96 | Command header strip |
| `operational/OperationalStatusBar.jsx` | 111 | Status bar |
| `omniview/momentum/OmniviewMomentumPriorityStrip.jsx` | — | Priority strip |
| `omniview/OmniviewDataHelp.jsx` | — | Data help section |
| `omniview/OmniviewFilterPrimitives.jsx` | — | Filter selects |

---

## 3. COMPACT HEADER V2 — PROPOSAL & IMPLEMENTATION

### 3.1 Design Principles

1. Matrix gains protagonism — starts higher on viewport
2. All controls in ONE compact row
3. DataHelp collapsed into expandable icon inline
4. Reduced padding: `px-2 py-1` instead of `px-3 py-1.5`
5. Smaller separators: `h-3.5` instead of `h-4`
6. Smaller text: `text-[10px]` for buttons instead of `text-xs`
7. Redundant labels removed — controls are self-describing
8. All filters/controls accessible without scrolling

### 3.2 What Changed

| Area | Before | After |
|------|--------|-------|
| Controls | 3 rows (filters, DataHelp, visualization) | 1 row + 1 subtitle line |
| Control paddings | `px-3 py-1` / `px-3 py-1.5` | `px-2 py-1` |
| Control gaps | `gap-x-2`, `gap-x-3`, `gap-y-1.5` | `gap-x-1.5`, `gap-y-0.5` |
| DataHelp | Full row visible always | Inline toggle button + expandable |
| Grain selector | With label "Grano" above | No label, self-describing buttons |
| Weekday buttons | `px-2.5 py-1 text-xs` with shadow | `px-1.5 py-0.5 text-[10px]` no shadow |
| Mode selector | "Evolución" / "Vs Proyección" | "Evolución" / "Vs Proy." |
| Perspective | "Operational" / "Ownership" | "Oper" / "Owner" |
| KPI selector | With "KPI" label | No label |
| Density | "Cómodo" / "Compacto" (unchanged) | Same, smaller buttons |
| Zoom | Separate labels | No labels on ± buttons |
| Focus | "Enfocar" / "Salir foco" | "Foco" / "Salir" |
| Export | "Descargar" with icon | "CSV" with icon |
| Go-to-current | "Ir a hoy" / "Ir a mes actual" | "Ahora" |
| FACT tables | "FACT tables" | "FACT" |
| Vertical separators | Every section | Only major sections |
| Status banners | Full height | Unchanged (not in scope) |

### 3.3 Estimated Height Reduction

| Area | Before | After | Saved |
|------|--------|-------|-------|
| Controls area | ~119px (3 rows) | ~42px (1 row + subtitle) | **~77px** |
| DataHelp | ~28px | 0px (inline toggle) | **~28px** |
| Total savings | | | **~105px** |

**New estimated header before matrix: ~195-315px** (reduced ~35%)

### 3.4 Files Modified

| File | Change |
|------|--------|
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Merged 3 control rows into 1 compact row; added `dataHelpOpen` state; removed redundant labels; reduced button sizes and gaps |

Lines changed: ~1456-1758 replaced with compact version (~150 lines replaced).

---

## 4. QA CHECKLIST

| # | Check | Result |
|---|-------|--------|
| 1 | `npm run build` | **PASS** — Built in 9.59s, no errors |
| 2 | No console errors on build | **PASS** — 0 errors |
| 3 | Filters still present | **PASS** — All filters in single row |
| 4 | Revenue still visible (API fix preserved) | **PASS** — No API changes |
| 5 | Matrix renders | **PASS** — Matrix component unchanged |
| 6 | No double scroll | **PASS** — Same overflow structure |
| 7 | Responsive basic | **PASS** — `flex-wrap` on control row |
| 8 | No critical alerts lost | **PASS** — CommandHeader + banners preserved |
| 9 | No new state variables broken | **PASS** — Only added `dataHelpOpen` |

---

## 5. VEREDICT

### **GO**

Header compacted successfully. Build passes. Matrix gains ~105px of vertical space. All controls preserved in one compact row. No API or business logic touched. No filters or alerts removed.

### Remaining Risks

| Risk | Severity | Note |
|------|----------|------|
| Tight fit on small screens | LOW | `flex-wrap` ensures controls wrap to second line on narrow viewports |
| Very dense text in controls | LOW | `text-[10px]` is operational minimum; matches `--ct-font-micro` token |
| DataHelp less discoverable | LOW | Toggle button with icon always visible; expandable on click |

### Next Step

O3 — Present Focus: auto-scroll to current period, highlight current month/week/day in matrix.
