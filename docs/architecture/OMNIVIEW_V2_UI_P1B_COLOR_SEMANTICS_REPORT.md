# OMNIVIEW V2 — UI P1B COLOR SEMANTICS REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — Color semantics applied across all matrix cells
**Phase:** OV2-UI-P1B

---

## 0. Executive Decision

**GO: COLOR SEMANTICS COMPLETE**

Semantic tone is determined by metric polarity (higherIsBetter/lowerIsBetter) combined with delta direction. `cancel_rate_pct` correctly inverts: negative delta = favorable (green), positive delta = unfavorable (red). All 7 metrics have consistent visual classification. Legend added to CommandHeader.

---

## 1. Scope

Apply deterministic color semantics to Omniview V2 matrix cells based on metric direction and delta values. Replace hardcoded "delta-up = good, delta-down = bad" logic with polarity-aware classification.

---

## 2. Color Contract

### 2.1 Semantic Tones

| Tone | CSS Class | Border Color | Meaning |
|------|-----------|-------------|---------|
| `positive` | `ov2-cell--positive` | Green (#16a34a) | Favorable: ahead of plan, improving, fresh |
| `negative` | `ov2-cell--negative` | Red (#dc2626) | Unfavorable: behind plan, degrading, critical |
| `neutral` | `ov2-cell--neutral` | Gray (#9ca3af) | No change, zero delta, stable |
| `warning` | `ov2-cell--warning` | Yellow (#f59e0b) | Partial, at risk, non-canonical |
| `blocked` | `ov2-cell--blocked` | Red bg | Missing value, blocked status |
| `not-comparable` | `ov2-cell--not-comparable` | Muted bg | Not comparable, no reference |
| `future` | `ov2-cell--future` | Disabled bg | Future period, no data yet |
| `disabled` | `ov2-cell--disabled` | Muted bg | Metric not available |

### 2.2 Delta Classification Rule

```
delta > 0 AND higherIsBetter → positive (green)
delta > 0 AND lowerIsBetter → negative (red)
delta < 0 AND higherIsBetter → negative (red)
delta < 0 AND lowerIsBetter → positive (green)
delta ≈ 0 → neutral (gray)
delta == null → not-comparable (gray)
```

### 2.3 Helper Functions

Created: `omniviewV2ColorSemantics.js`
- `getDeltaTone(metric, deltaValue, deltaPct)` → semantic tone string
- `getCellToneClass(cell, metricId, isFuture)` → CSS class suffix
- `getToneLabel(tone)` → human-readable label
- `TONE_LEGEND` → array for rendering legend

---

## 3. Metric Direction Table

| Metric ID | Polarity | Delta +0.5 | Delta -1.0 | Delta null |
|-----------|----------|-----------|------------|------------|
| `orders` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `revenue` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `active_drivers` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `avg_ticket` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `commission_pct` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `trips_per_driver` | higherIsBetter | positive (green) | negative (red) | not-comparable |
| `cancel_rate_pct` | **lowerIsBetter** | **negative (red)** | **positive (green)** | not-comparable |

---

## 4. Components Updated

| File | Change |
|------|--------|
| `omniviewV2ColorSemantics.js` | **CREATED** — Tone classification engine |
| `MatrixCell.jsx` | **MODIFIED** — Accepts `metricId`, uses `getCellToneClass` instead of `_signalColor` + `_deltaDirection` |
| `MatrixRow.jsx` | **MODIFIED** — Passes `metricId` to MatrixCell |
| `MatrixShell.jsx` | **MODIFIED** — Accepts and passes `metricId` from parent |
| `OmniviewV2ShadowPage.jsx` | **MODIFIED** — Passes `metricId` to MatrixShell |
| `OmniviewV2CommandHeader.jsx` | **MODIFIED** — Imports and renders `TONE_LEGEND` |
| `MatrixVisualSystem.css` | **MODIFIED** — Added semantic classes (`positive`, `negative`, `neutral`, `disabled`) |

---

## 5. Cancel Rate Pct Behavior

`cancel_rate_pct` is the only `lowerIsBetter` metric. This is handled correctly:
- If cancel rate goes DOWN (negative delta) → **green** border (favorable)
- If cancel rate goes UP (positive delta) → **red** border (unfavorable)
- If value is NULL → not-comparable (gray, "N/A" text)

---

## 6. Null / N/A / Not Comparable Behavior

| Condition | Visual | CSS Class |
|-----------|--------|-----------|
| `cell.value == null` | Gray background, "N/A" text | `blocked` |
| `cell_status == 'NOT_COMPARABLE'` | Gray background, muted text | `not-comparable` |
| `delta_value == null` | No comparison badge, neutral tone | `neutral` |
| `cell_status == 'BLOCKED'` | Red-tinted background | `blocked` |
| `metric.available == false` | Gray background | `disabled` |
| `isFuture == true` | Gray background | `future` |

---

## 7. Legend

Minimal legend rendered in CommandHeader:
- Green square + "Favorable"
- Red square + "Desfavorable"
- Gray square + "Neutral"
- Gray square + "N/A"

---

## 8. Build & Validation

| Check | Result |
|-------|--------|
| `npm run build` | PASS (6.31s) |
| Backend untouched | CONFIRMED |
| No legacy endpoints | CONFIRMED |
| No Diagnostic terms | CONFIRMED |
| CSS classes applied | CONFIRMED |
| metricId propagated through chain | CONFIRMED |

---

## 9. Remaining Gaps

| Gap | Status |
|-----|--------|
| P0-3: Color semantics | **COMPLETE** |
| P0-2: CSV export | PENDING |
| P0-4: Sort controls | PENDING |
| P0-5: Plan vs Real visualization | PENDING |
| P0-6: Period presets | PENDING |

---

## 10. Next Phase

**OV2-UI-P1C: CSV Export.** Port V1 export engine (`omniviewExport.js`) to V2 data shape. Do NOT implement charts, sort, or period presets yet.

---

*Color semantics complete. 7 metrics fully classified. cancel_rate_pct correctly inverted.*