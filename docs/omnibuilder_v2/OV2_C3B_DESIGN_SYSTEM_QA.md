# OV2-C.3B — DESIGN SYSTEM QA

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Visual Consistency
> **Validates:** All OV2 matrix components against OV2-C.2B and OV2-C.3A contracts

---

## 1. TYPOGRAPHY CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| T1 | All matrices use same font-family | `--ov2-font-family` | PENDING |
| T2 | Cell values use monospace | `--ov2-font-mono` | PENDING |
| T3 | Header uses same font-size | `--ov2-font-size-header` (12px) | PENDING |
| T4 | KPI values use same font-size | `--ov2-font-size-kpi` (24px) | PENDING |
| T5 | All fonts from tokens, not hardcoded | No `font-family: Arial` in components | PENDING |

---

## 2. LAYOUT CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| L1 | Row height identical across all grains | 40px (comfortable) | PENDING |
| L2 | Column width by grain | hour=70px, day=90px, week=100px, month=100px | PENDING |
| L3 | Sticky header present | `position: sticky; top: 0` | PENDING |
| L4 | Sticky first column present | `position: sticky; left: 0` | PENDING |
| L5 | MatrixShell is only wrapper | No standalone matrix divs outside MatrixShell | PENDING |

---

## 3. COLOR CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| C1 | OK cells use green | `#22c55e` border/indicator | PENDING |
| C2 | WARNING cells use amber | `#fffbeb` bg, `#f59e0b` border | PENDING |
| C3 | BLOCKED cells use red | `#fef2f2` bg, `#ef4444` border | PENDING |
| C4 | Selected cells use blue ring | `#3b82f6` inset shadow | PENDING |
| C5 | Hover uses consistent blue | `#eff6ff` background | PENDING |
| C6 | All colors via CSS variables | Zero hardcoded hex in component files | PENDING |

---

## 4. INTERACTION CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| I1 | Hover activates on all cells | Background shifts to `--ov2-bg-hover` | PENDING |
| I2 | Selected shows ring | `box-shadow: 0 0 0 2px var(--ov2-status-selected) inset` | PENDING |
| I3 | Cell click opens inspector | Inspector drawer slides from right | PENDING |
| I4 | Inspector closes on X/backdrop/Escape | Three close methods all work | PENDING |
| I5 | Muted cells not interactive | No hover, no click on null cells | PENDING |

---

## 5. BADGE CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| B1 | Same badge position | Top-right corner, 2px from edge | PENDING |
| B2 | Same badge size | `--ov2-badge-height` (18px) | PENDING |
| B3 | Same badge font | `--ov2-font-size-badge` (10px) | PENDING |
| B4 | Source badge consistent | CANONICAL green / SHADOW indigo | PENDING |
| B5 | Period badge conditional | Only shows for PARTIAL/CLOSED/FUTURE, hidden for CURRENT | PENDING |

---

## 6. CROSS-KPI CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| K1 | Orders, Revenue, Drivers look identical | Same layout, same cell size, same hover | PENDING |
| K2 | No `.revenue-cell` class in codebase | Zero matches | PENDING |
| K3 | No `.drivers-cell` class in codebase | Zero matches | PENDING |
| K4 | No `.trips-cell` class in codebase | Zero matches | PENDING |
| K5 | CellContract used uniformly | All cells receive same data shape | PENDING |

---

## 7. CROSS-GRAIN CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| G1 | Day, week, month look identical except column width | Layout structure unchanged | PENDING |
| G2 | No `.daily-cell` class in codebase | Zero matches | PENDING |
| G3 | No `.weekly-cell` class in codebase | Zero matches | PENDING |
| G4 | No `.monthly-cell` class in codebase | Zero matches | PENDING |
| G5 | Header labels change per grain | "Jun 4" for day, "W23" for week, "Jun 2026" for month | PENDING |

---

## 8. CROSS-SOURCE CONSISTENCY

| # | Check | Expected | Actual |
|---|-------|----------|--------|
| S1 | CT and Yango matrices visually identical | Same layout, only source badge differs | PENDING |
| S2 | MatrixShell receives MatrixResponse, not raw data | No per-source data parsing in MatrixShell | PENDING |
| S3 | Source badge reflects canonical_ready | CT=CANONICAL green, Yango=SHADOW indigo | PENDING |
| S4 | Yango cells show warning badges | CANONICAL_NOT_READY etc. from cell contract | PENDING |

---

## 9. CODE AUDIT CHECKS

| # | Check | Command | Expected |
|---|-------|---------|----------|
| A1 | No per-KPI CSS classes | `rg "revenue-cell\|trips-cell\|drivers-cell"` | 0 matches |
| A2 | No per-grain CSS classes | `rg "daily-cell\|weekly-cell\|monthly-cell\|hourly-cell"` | 0 matches |
| A3 | No hex colors in components | `rg "#[0-9a-fA-F]{6}" src/pages/omniview-v2-shadow/components/` | 0 matches (allowed in design tokens only) |
| A4 | No inline critical styles | `rg "style=\{\{" src/pages/omniview-v2-shadow/components/` | Minimal (layout only) |
| A5 | CSS variables used | `rg "var\(--ov2-" src/pages/omniview-v2-shadow/` | All component files |

---

## 10. BUILD CHECK

| # | Check | Command | Expected |
|---|-------|---------|----------|
| B1 | Build succeeds | `npm run build` in frontend/ | Exit 0, no errors |
| B2 | V1 components still load | Build includes existing V1 components | Pass |
| B3 | No circular imports | Build warning-free | Pass |

---

## 11. ACCEPTANCE

| Phase | Status |
|-------|--------|
| Typography | PENDING |
| Layout | PENDING |
| Color | PENDING |
| Interaction | PENDING |
| Badges | PENDING |
| Cross-KPI | PENDING |
| Cross-Grain | PENDING |
| Cross-Source | PENDING |
| Code Audit | PENDING |
| Build | PENDING |

**GO for OV2-C.3C:** All checks pass. Design system produces identical visual output regardless of KPI, grain, or source.
