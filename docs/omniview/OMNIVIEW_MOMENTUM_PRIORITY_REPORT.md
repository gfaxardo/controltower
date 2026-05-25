# OMNIVIEW MOMENTUM PRIORITY ENGINE — REPORT

**Date**: 2026-05-25
**Status**: **GO**
**Build**: PASS (9.26s)

---

## 1. WHAT WAS CREATED

### Priority Engine (`operationalMomentumPriority.js`)
| Function | Purpose |
|----------|---------|
| `detectConsecutiveDecline(values)` | Counts consecutive periods declining (>3% threshold) |
| `detectMomentumAcceleration(values)` | Detects if decline is getting steeper |
| `classifyMomentumRisk(deltas, grain)` | Classifies entity into RISK level |
| `buildMomentumPriorityLabel(entity)` | Builds descriptive label ("CALI ↓ 18% · 3 consecutive") |
| `sortMomentumAttention(entities)` | Ranks by risk priority |
| `extractMomentumPriorityFromMatrix(rows, grain)` | Extracts top N entities from matrix data |

### Risk Levels (7 levels)
| Level | Trigger |
|-------|---------|
| `critical_decline` | 3+ consecutive declines AND severe (>10% daily, >8% weekly, >5% monthly) |
| `accelerating_down` | Each period drops more than the previous |
| `consecutive_down` | 2+ consecutive declines |
| `single_decline` | One period drop |
| `stable` | No significant change |
| `recovering` | Coming back from decline |
| `improving` | Positive momentum |

### Priority Strip (`OmniviewMomentumPriorityStrip.jsx`)
- Compact 1-line strip between command header and controls
- Shows top 5 deteriorations with severity-colored chips
- "!! More critical" prefix for CRITICAL/ACCELERATING
- Optional improvements section
- "No deteriorations" when all clear
- Background tints red when >2 declines detected

---

## 2. INTEGRATION

```
┌─ Command Header ─────────────────────────────────┐
│  Mode selector | Evolution · Mensual | Health dots│
├──────────────────────────────────────────────────┤
│  Momentum: !! CALI ↓ 18% · 3 declining | ! LIM ↓ 8% · 2 consec  │  ← NEW
├──────────────────────────────────────────────────┤
│  Filter Controls                                  │
├──────────────────────────────────────────────────┤
│  Matrix Table                                     │
└──────────────────────────────────────────────────┘
```

---

## 3. FILES CREATED

| File | Purpose |
|------|---------|
| `utils/operationalMomentumPriority.js` | Priority engine (pure functions, ~200 lines) |
| `components/omniview/momentum/OmniviewMomentumPriorityStrip.jsx` | Visual priority strip (~120 lines) |
| `docs/omniview/OMNIVIEW_MOMENTUM_PRIORITY_PRECHECK.md` | Precheck |
| `docs/omniview/OMNIVIEW_MOMENTUM_PRIORITY_REPORT.md` | This report |

## 4. FILES MODIFIED

| File | Change |
|------|--------|
| `BusinessSliceOmniviewMatrix.jsx` | +2 lines (import + priority strip) |

---

## 5. ENGINE PRINCIPLES

- **Deterministic**: pure functions, no randomness, no ML
- **Centralized**: all ranking logic in one file
- **No new endpoints**: uses existing matrix cell deltas
- **No IA**: purely statistical (consecutive count, acceleration detection, threshold comparison)
- **No recommendations**: only classifies and ranks, never prescribes

---

## 6. VERDICT

**GO** — Omniview now surfaces momentum deteriorations automatically. Priority engine is deterministic and lightweight. Strip is compact and non-intrusive.
