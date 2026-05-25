# OMNIVIEW MOMENTUM SIGNAL AUDIT

**Date**: 2026-05-25

---

## exists_ready — Already in matrix data pipeline

| Signal | How | Where |
|--------|-----|-------|
| DoD same-weekday | `comparison_mode: "daily_same_weekday"` | Backend `_attach_daily_same_weekday_context()`, consumed in `computeDeltas()` |
| WoW (full week) | Default sequential delta for weekly grain | `computeDeltas()` — previous period in sequence IS previous week |
| WoW (partial week) | `comparison_mode: "weekly_partial_equivalent"` | Backend `_attach_weekly_partial_equivalent_context()` |
| MoM (full month) | Default sequential delta for monthly grain | `computeDeltas()` — previous period in sequence |
| MoM (partial month) | `comparison_mode: "monthly_partial_equivalent"` | Backend `_attach_monthly_partial_equivalent_context()` |
| D-1 (calendar) | Default sequential delta for daily grain (when no comparison_context) | `computeDeltas()` — previous period |

## exists_but_hidden — Data present but not visually differentiated

| Signal | Issue |
|--------|-------|
| `comparison_mode` metadata | Exists on every delta object (`delta.comparison_mode`) but NEVER read in cell renderer |
| `is_partial_equivalent` | Exists but only used for `opacity: 0.7` + `~` suffix — no momentum emphasis |
| `baseline_period_key` | Exists in delta metadata — unused visually |

## missing_serving_fact — Don't exist, don't need

| Signal | Note |
|--------|------|
| same_weekday_avg_4w | Exists in RealLOB API but NOT in Matrix serving facts. Not needed for this phase. |
| momentum_score | Doesn't exist. Not needed. |

---

## What changes today

**Nothing in the data pipeline.** All comparison data is already flowing to the frontend via `computeDeltas()`.

The gap is purely in the **visual rendering** of deltas in `BusinessSliceOmniviewMatrixCell.jsx`, which treats all deltas identically regardless of `comparison_mode`.
