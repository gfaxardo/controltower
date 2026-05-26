# CONTROL TOWER RELEASE SCOPE

**Date**: 2025-05-25
**Release**: Production controlada
**Motor**: Control Foundation

---

## INCLUDED IN THIS RELEASE

### Omniview Proyección + Momentum Radar
- Proyección como modo principal (viewMode='proyeccion')
- Momentum severity color scale (5 levels negative, 5 positive)
- Cell cognitive hierarchy: Real Value + Momentum Delta dominante
- Current period authority (emerald spotlight)
- Default expanded cities with user governance
- Single scroll owner (overflow: clip)
- Auto-scroll to current period
- "Ir a hoy" button
- NaN elimination (all formatters guarded)
- Historical degradation (past periods fade)
- Weekday focus with cognitive labels
- Top deterioration strip (OmniviewMomentumPriorityStrip)
- Mode simplification (Operational primary)

### Momentum Drill
- Toggle between Plan vs Real and Momentum views
- Hand-rolled SVG chart
- Fullscreen drill mode (Esc to exit)

### Behavioral MVP
- Diagnostics panel (standalone)
- Gap visibility
- Deterministic detection (no AI)

### Evolution Mode
- Still accessible as secondary legacy via toggle "Evolución"
- No new features or changes
- Future deprecation candidate

---

## EXPLICITLY EXCLUDED

| Feature | Reason |
|---|---|
| Evolution improvements | Secondary legacy mode |
| Cohort Intelligence | Future engine |
| Forecast Engine | Not yet activated |
| Suggestion Engine | Not yet activated |
| Decision Engine | Not yet activated |
| Action Engine | Not yet activated |
| AI Copilot | Not yet activated |
| New recommendation logic | Out of scope |
| Insight Engine port to Proyección | Pending sub-phase |
| Large cleanup of deprecated components | FASE 4/6 |
| Bundle splitting / chunk optimization | Separate optimization project |
| Usage analytics | Future observability phase |

---

## FILE FREEZE

Do NOT modify these before release:

| File | Reason |
|---|---|
| `BusinessSliceOmniviewProjectionTable.jsx` | Deprecated, not imported |
| `BusinessSliceOmniviewProjectionCell.jsx` | Deprecated, not imported |
| `RealVsProjectionView.jsx` | Legacy, not in App.jsx |
| Evolution cell logic paths | Secondary legacy |
| Backend serving fact tables | Stable |
| Sticky/scroll/fullscreen logic | Stable |
| `operationalMomentumEmphasis.js` core functions | Pre-existing, used by Evolution |

---

## RELEASE BOUNDARY

This release ships:
- Omniview Proyección as the primary operational brain
- Momentum Radar with severity color language
- Cell hierarchy: Value + Delta dominant
- Behavioral MVP as diagnostic companion
- Evolution as accessible legacy

This release does NOT ship:
- Any new engine (Forecast, Suggestion, Decision, Action, AI Copilot)
- Any AI-driven recommendations
- Any runtime heavy calculations for public UI
