# OV2-C.2 — UX PROBLEM REVIEW: OMNIVIEW V1

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture
> **Source:** OMNI-P0 recovery validation, ai_current_phase.md, risk register OV2-A

---

## 1. PROBLEMS IDENTIFIED IN OMNIVIEW V1

### P1: Double Scroll
- **Symptom:** Matrix zone has internal scrollbar; page also scrolls. Vertical double scroll.
- **Impact:** Users lose context. Scrolling inside matrix scrolls page underneath.
- **Root cause:** No fixed container height. Matrix expands to fit content, page scrolls independently.
- **OV2 fix:** Fixed-height matrix with single, controlled inner scroll.

### P2: Header/Matrix Misalignment
- **Symptom:** Column headers desynchronize from data columns when scrolling horizontally.
- **Impact:** User cannot match column labels to cell values.
- **Root cause:** Sticky positioning breaks at certain window widths. No synchronized scroll.
- **OV2 fix:** Sticky header + sticky first column. Controlled via scroll event sync.

### P3: Cards Disconnected from Matrix
- **Symptom:** Top KPI cards show aggregate numbers but matrix shows per-slice/per-period. No visual link between the two.
- **Impact:** User sees "Revenue OK" in cards but "Revenue WARNING" in matrix. Cognitive dissonance.
- **Root cause:** Cards and matrix rendered independently, no shared state.
- **OV2 fix:** Cards and matrix share same filters/period/source. Cards update when matrix filters change.

### P4: Alerts Without Operational Focus
- **Symptom:** Alert messages appear but don't point to the specific KPI/cell/period causing them.
- **Impact:** "Revenue delta >5%" — user doesn't know which slice, which period.
- **Root cause:** Alerts generated at aggregate level, not at cell level.
- **OV2 fix:** Each alert has `target`: KPI ID, slice name, period, or cell coordinates.

### P5: Too Many Simultaneous KPIs
- **Symptom:** 12+ KPIs displayed above the matrix. Information overload.
- **Impact:** Users scan but don't comprehend. Decision paralysis.
- **Root cause:** Feature creep — each KPI added without removing others.
- **OV2 fix:** Maximum 5 KPIs in executive strip. Others in detail sections.

### P6: Cells Without Explanation
- **Symptom:** Cells show numbers without origin. User asks "where does this come from?"
- **Impact:** Low trust in data. Manual verification needed.
- **Root cause:** No cell inspector. No lineage visible in UI.
- **OV2 fix:** Click any cell → inspector panel with source_table, origin_field, aggregation, freshness, confidence.

### P7: Evolution vs Vs Proy Confusion
- **Symptom:** Two views with different data. Toggle between them. Users don't know which is canonical.
- **Impact:** Users see different revenue values depending on view. Trust destroyed.
- **Root cause:** Legacy Evolution view coexists with Vs Proy. No deprecation enforcement.
- **OV2 fix:** Single canonical view per source. No toggle between contradicting views.

### P8: Partial Data Without Badge
- **Symptom:** Periods with incomplete data look the same as complete periods.
- **Impact:** User treats partial data as final. Wrong decisions.
- **Root cause:** No period_status badge on cells. CLOSED/PARTIAL/CURRENT/FUTURE invisible.
- **OV2 fix:** Every cell has period_status badge. Color-coded. Always visible.

### P9: Revenue/Proxy Not Transparent
- **Symptom:** Revenue may be real or proxy. User cannot tell.
- **Impact:** Decisions based on proxy revenue believing it's real.
- **Root cause:** COALESCE(real, proxy) hides source. No revenue_source flag in UI.
- **OV2 fix:** revenue_source visible per cell. WARNING if proxy. BLOCKED if unavailable.

### P10: Filters Persisted Without Versioning
- **Symptom:** localStorage filters survive across sessions. Schema changes break old filters silently.
- **Impact:** User loads page with stale filter config → no data → confusion.
- **Root cause:** localStorage persistence without schema versioning.
- **OV2 fix:** No localStorage initially. When added: version key, validate on load, reset on mismatch.

### P11: Heavy Frontend Logic
- **Symptom:** WoW/MoM deltas, pacing calculations, countdowns computed in JSX.
- **Impact:** Slow render. Inconsistent calculations vs backend. Frontend is source of truth for derived metrics.
- **Root cause:** Backend returns raw values. Frontend derives everything.
- **OV2 fix:** All derivations in backend service layer. Frontend renders only.

### P12: Visual Validation Without Semantic Validation
- **Symptom:** DOM token validation passed (F1-F10) but operational failure detected.
- **Impact:** False GO declared. OMNI-P0 reopened.
- **Root cause:** Validation checked "element exists" not "element shows correct data".
- **OV2 fix:** Acceptance checklist validates semantic correctness, not DOM presence.

---

## 2. DESIGN PRINCIPLES FOR OV2

| # | Principle | Source Problem |
|---|-----------|---------------|
| 1 | Single scroll container | P1 |
| 2 | Sticky header + first column | P2 |
| 3 | Shared filter state across layout | P3 |
| 4 | Alert → target linking | P4 |
| 5 | Max 5 KPIs above fold | P5 |
| 6 | Clickable cells → inspector | P6 |
| 7 | One canonical view per source | P7 |
| 8 | Period badge on every cell | P8 |
| 9 | Revenue source transparency | P9 |
| 10 | No unversioned persistence | P10 |
| 11 | Backend computes, frontend renders | P11 |
| 12 | Semantic acceptance criteria | P12 |

---

## 3. WHAT OV2 UX MUST NEVER DO

- Double vertical scroll
- Hide source/canonical status
- Show mute alerts without target
- Exceed 5 executive KPIs
- Compute business logic in frontend
- Persist without schema version
- Mix two sources visually without label
- Show partial data without badge
