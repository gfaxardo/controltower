# OPERATIONAL INFORMATION DENSITY AUDIT

**Date**: 2026-05-25
**Phase**: UX Hardening Stage 3 — Information Density

---

## CLASSIFICATION

### HIGH WASTE (>40% of space is structural, not operational data)

| # | File | Waste Type | Lines Wasted | Fix |
|---|------|-----------|-------------|-----|
| 1 | `KPICards.jsx` non-compact | Card padding `p-6`, `gap-6`, `mb-6` | ~40-60px per KPI card | Reduce to `p-4`, `gap-3`, `mb-4` |
| 2 | `RealLOBDrillView.jsx` | 7+ nested banners with `p-4` inside `p-6` card | ~300px | Consolidate into 1-2 compact rows |
| 3 | `RealVsProjectionView.jsx` | 7 independent cards in `space-y-6` with minimal content | ~250px | Merge into 1 unified card with divider lines |
| 4 | `BusinessSliceView.jsx` | 5 separate cards with `space-y-6` | ~200px | Unify into fewer panels |
| 5 | `15+ files` | `space-y-6` (24px gaps) | ~80px cumulative | Reduce to `space-y-4` |

### MEDIUM WASTE (20-40% structural)

| # | File | Waste Type | Lines Wasted |
|---|------|-----------|-------------|
| 6 | `MonthlySplitView.jsx` | `mt-8`, `mb-8`, `p-6` wrapper | ~80px |
| 7 | `ExecutiveSnapshotView.jsx` | Redundant header + badges before KPIs | ~40px |
| 8 | `Phase2*View.jsx` | `mt-8` dead space | ~32px each |
| 9 | `BusinessSliceView.jsx` | "Lectura ejecutiva" card for 2 sentences | ~60px |
| 10 | `App.jsx` | 2-3 layers of data trust badges | ~40px |

### ACCEPTABLE

| File | Assessment |
|------|-----------|
| `BusinessSliceOmniviewKpis.jsx` | Gold standard: 72px per KPI, efficient layout |
| `ActionContext.jsx` | Excellent density. No waste. |
| `GlobalFreshnessBanner.jsx` | Compact and efficient. |
| `FactStatusPanel.jsx` | Dense content, appropriate padding. |
| `Omniview Matrix` family | Density by design, no waste. |
| `YangoLoyaltyView.jsx` | Already hardened in Stage 2. |
| `WeeklyPlanVsRealView.jsx` | Already hardened in Stage 2. |

---

## KPI CARD DENSITY COMPARISON

| Component | Mode | Height per KPI | Padding % |
|-----------|------|---------------|-----------|
| `BusinessSliceOmniviewKpis` | Standard | ~72px | ~25% |
| `KPICards` compact | Before Stage 3 | ~96px | ~33% |
| `KPICards` compact | After Stage 3 | ~72px | ~22% |
| `KPICards` non-compact | Before Stage 3 | ~132px | ~36% |
| `KPICards` non-compact | After Stage 3 | ~88px | ~27% |
| `RealLOBDrillView` KPI bar | Standard | ~80px each | ~30% |

---

## SPACING WASTE Registry

| Spacing | Before | After | Saved |
|---------|--------|-------|-------|
| `p-6` → `p-4` (KPICards) | 24px | 16px | 8px/card |
| `gap-6` → `gap-3` (KPICards grid) | 24px | 12px | 12px/gap |
| `mb-6` → `mb-4` (KPICards) | 24px | 16px | 8px |
| `mb-4` → `mb-2` (revenue header) | 16px | 8px | 8px |
| `space-y-4` → `space-y-2` (revenue items) | 16px | 8px | 8px/item |
| `mt-8` → `mt-2` (Phase2 views) | 32px | 8px | 24px each |
| ALL disclaimer `mb-6 p-3` → `mb-3 p-2` | 48px | 24px | 24px |

---

## CHANGES APPLIED (Stage 3)

| File | Changes |
|------|---------|
| `ct-design-tokens.css` | +200 lines: density scale, KPI compression, table density, filter compression, alert compression, visual scan, information layers |
| `KPICards.jsx` | Card padding `p-6`→`p-4`, grid gap `gap-6`→`gap-3`, value font `text-3xl`→`text-2xl`, revenue card `p-6`→`p-4`, disclaimer slimmed |
