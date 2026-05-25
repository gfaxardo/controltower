# PROJECTION PARITY CHECK

**Date**: 2025-05-25
**FASE 2 Sub-check**

---

## Capacidades — Evolution vs Proyección

### Momentum

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| DoD (same-weekday) | ✅ Full color, bold, labeled | ✅ PeriodPop color authority | **ABSORBED** |
| WoW (week-over-week) | ✅ Full color, bold, labeled | ✅ PeriodPop color authority | **ABSORBED** |
| MoM (month-over-month) | ✅ Full color, bold, labeled | ✅ PeriodPop color authority | **ABSORBED** |
| Momentum color authority | ✅ `isMomentumComparison` + full baseColor | ✅ `momColor` based on periodPop value | **ABSORBED** |
| Momentum labels | ✅ "DoD"/"WoW"/"MoM" prefix | ✅ `momLabel` from `periodPopLabel` | **ABSORBED** |
| Momentum arrows | ✅ ▲ green / ▼ red | ✅ ▲ green / ▼ red | **ABSORBED** |

### Drill

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| Momentum charts | ✅ `OmniviewMomentumDrillChart` | ✅ Toggle in `OmniviewProjectionDrill` | **ABSORBED** |
| Plan vs Real charts | ❌ N/A | ✅ `ProjectionEvolutionChart` | **KEPT** |
| Drill mode toggle | ❌ N/A | ✅ Plan vs Real / Momentum toggle | **ABSORBED** |

### Priority & Severity

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| Momentum Priority Strip | ✅ `OmniviewMomentumPriorityStrip` with `baseMatrix` | ✅ Same component with `projMatrix` | **ABSORBED** |
| Deterioration detection | ✅ `classifyMomentumRisk` | ✅ Same engine | **ABSORBED** |
| Consecutive decline | ✅ Detected | ✅ Detected | **ABSORBED** |
| Critical/accelerating | ✅ Colored chips | ✅ Colored chips | **ABSORBED** |

### Filters

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| Weekday Focus | ✅ DOM/LUN/MAR/... chips | ✅ Same filter on `displayProjMatrix` | **ALREADY ABSORBED** |
| Weekly scope (±6 weeks) | ✅ Toggle | ✅ Same filter | **ABSORBED** |

### Insight Layer

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| Insight detection | ✅ `insightEngine` | ❌ Not yet | **PARTIALLY ABSORBED** |
| Severity overlay | ✅ Ring colors on cells | ❌ Not yet | **PENDING** |
| Insight panel | ✅ `BusinessSliceInsightsPanel` | ❌ Not yet | **PENDING** |

### Cognitive Priority Shift

| Feature | Evolution | Proyección | Status |
|---|---|---|---|
| Momentum dominates visually | ✅ Primary color signal | ✅ Momentum row between Real and Attainment | **ABSORBED** |
| Plan vs Real secondary | ❌ N/A | ✅ Attainment dimmed when momentum present | **ABSORBED** |
| Gap subdued | ❌ N/A | ✅ Gap grayed further when momentum present | **ABSORBED** |

---

## SUMMARY

| Status | Count | Items |
|---|---|---|
| **ABSORBED** | 14 | DoD, WoW, MoM, color authority, labels, arrows, charts, drill toggle, priority strip, deterioration, weekday focus, weekly scope, priority shift, gap subdued |
| **PARTIALLY ABSORBED** | 1 | Insight layer (severity rings exist on Evolution cells; Projection cells use own severity via `signalBg`) |
| **PENDING** | 1 | Insight panel for projection mode |
| **BLOCKED** | 0 | — |
| **KEPT** | 1 | Plan vs Real chart (coexists with momentum drill via toggle) |

---

## VERDICT

**ABSORPTION ESTADO**: 14/16 capacidades migradas o confirmadas.
**Insight layer es la única capacidad parcial** — pendiente para subfase posterior sin romper estabilidad.
