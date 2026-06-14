# OMNIVIEW UI — RENDERING / CHARTING / ZOOM CONTRACT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** ACTIVE GOVERNANCE RULE
**Applies to:** Any visual or charting change in Omniview V2

---

## 0. Executive Decision

**GO: RENDERING AND CHARTING CONTRACT ADDED TO OMNIVIEW UI GOVERNANCE**

All visual work must follow these rules. No charts without purpose. No zoom without contract. No data without certification. No runtime-heavy UI.

---

## 1. Data Governance

1. Every chart uses certified V2 endpoints only.
2. No V1 endpoints for new visual work.
3. No runtime-heavy aggregation in browser.
4. No invented metrics.
5. Plan and Real never mixed incorrectly.
6. Null/no data = N/A, never zero.
7. Freshness/stale/unknown always visible, never hidden.
8. Every chart declares: source endpoint, metric, grain, freshness status, aggregation method, fallback behavior.

---

## 2. Charting Rules

| Rule | Detail |
|------|--------|
| Library | Use ECharts (already in bundle). No new library without justification of weight, compatibility, performance, maintenance. |
| Purpose | Every chart must have explicit purpose: trend, comparison, composition, attainment, ranking. |
| Type selection | Line/bar for trends. Bullet/attainment bars for PvR. Horizontal bars for ranking. Cards + sparkline for KPIs. No pie charts except simple composition with few segments. |
| States | Every chart must handle: loading, empty, error, partial data. |
| Overload | No more than 3-4 charts per view. Progressive disclosure. |

---

## 3. Zoom / Focus Contract

1. Zoom increases legibility without creating double scroll.
2. Zoom preserves focus on active section.
3. Prefer: internal section zoom, density controls, focus mode, fullscreen section, fit-to-width.
4. Matrix scroll horizontal must be contained within matrix viewport, not page.
5. Focus modes for: Trend chart, Plan vs Real, Breakdown, Matrix detail.
6. Focus mode easily closable (Escape, close button).
7. Export/detail always accessible.

---

## 4. Responsive / Layout

1. Desktop wide first-class. Laptop 1366px usable.
2. Tolerate browser zoom 90%-110%.
3. No double scroll. Use CSS grid/flex with clear breakpoints.
4. KPI row legible. Charts reflow without deformation.
5. Matrix detail has internal scroll only.
6. Header and controls not too tall. Freshness always visible, never invasive.

---

## 5. Cognitive Load

1. Summary first, then trend, then comparison, then detail.
2. Progressive disclosure — not everything at once.
3. Matrix secondary, not landing.
4. Each section answers one operational question.
5. Technical language in debug panel only.
6. Debug closed by default.
7. States: Fresh, Stale, Partial, No data, Backend unavailable — all with clear labels.

---

## 6. Visual Semantics

1. Green = better. Red = worse/blocking. Amber = warning/partial. Gray = neutral/legacy.
2. Lower-is-better metrics (cancel_rate_pct) invert polarity.
3. Never color-only: always text + badge + tooltip.
4. Chart colors respect `omniviewV2ColorSemantics.js`.

---

## 7. Performance

1. No O(n²) aggregation on large matrices.
2. Memoize derived series. Avoid re-render on hover.
3. AbortController for all requests. No duplicate fetch.
4. Loading states compact. No blocking UI with heavy fallbacks.

---

## 8. Acceptance Criteria

Every visual phase must pass: browser smoke, build, no console errors, no double scroll, zoom 90-110% usable, freshness visible, matrix detail accessible, export functional, no Diagnostic/Forecast opened.

---

## 9. Temporal Delta Contract (OV2-VC)

Omniview V2 Visual Cockpit must show temporal evolution explicitly per selected grain.

### 9.1 Grain-aware comparison

| Grain | Delta Contract | Label |
|-------|---------------|-------|
| day | current day vs previous comparable day | DoD |
| week | current ISO week vs previous ISO week | WoW |
| month | current month vs previous month | MoM |

**Rules:**
1. Grain selector changes the comparison contract, not just the visual filter.
2. Day shows day-over-day evolution.
3. Week shows week-over-week evolution using ISO weeks (Monday).
4. Month shows month-over-month evolution.
5. Never compare day against week, week against month, or month against day.
6. If previous comparable period does not exist, show "Not comparable", not zero.
7. If previous data is null/missing, do not compute false delta.
8. Deltas must show: absolute delta, percentage delta, direction, comparator label (DoD/WoW/MoM).
9. Lower-is-better metrics must invert visual semantics.
10. Temporal delta must remain separate from Plan vs Real delta.

### 9.2 Temporal Delta vs Plan Delta

| Concept | Meaning | Example |
|---------|---------|---------|
| Temporal Delta | Evolution vs previous period | today vs yesterday, this week vs last week |
| Plan Delta | Attainment vs plan | real vs planned target |

**Rules:**
1. Temporal Delta answers: "Are we improving or worsening?"
2. Plan Delta answers: "Are we meeting the plan?"
3. Both may coexist but must have distinct labels.
4. Do not use colors or text that suggest forecast or diagnosis.
5. Do not generate root cause or automatic suggestions.

### 9.3 Visual Requirements

Each KPI card and trend chart must indicate:
1. Active grain.
2. Current period.
3. Compared period.
4. Current value.
5. Absolute delta.
6. Percentage delta.
7. Direction.
8. Visual status per polarity.
9. Freshness.

**Example visual output:**
- `Trips: 10,997 · ▲ +8.2% DoD`
- `Revenue: S/ 45,200 · ▼ -3.1% WoW`
- `Cancel Rate: 3.2% · ▼ -0.8pp MoM` (lower-is-better: ▼=green)

### 9.4 Precheck additions

For any chart or KPI visual, add these 15 questions:
1. What grain: day, week, or month?
2. Is the delta DoD, WoW, or MoM?
3. What is the current period?
4. What is the previous comparable period?
5. What happens if the previous period doesn't exist?
6. Is the delta absolute, percentage, or both?
7. Is the metric higher-is-better or lower-is-better?
8. Does color represent "better/worse", not just "up/down"?
9. Is temporal delta separated from Plan vs Real delta?
10. Is temporal evolution presented as forecast? (must be NO)
11. Is deviation presented as diagnosis/root cause? (must be NO)
12. Is freshness valid for both current and comparison periods?
13. Does UI show "Not comparable" instead of false zero?
14. Is the chart/KPI understandable without tooltip?
15. Can the user change grain without breaking the visual contract?

---

## 10. Comparable Period / Baseline Contract (OV2-VC)

### 10.1 Comparable Period Principle

Omniview V2 must compare against operationally comparable periods, not just the immediately preceding calendar period.

| Grain | Comparable Period | Label |
|-------|------------------|-------|
| hour | same hour + same weekday of previous comparable period | HoH comparable |
| day | same weekday of previous comparable period | DoD comparable |
| week | current ISO week vs previous ISO week | WoW |
| month | current month vs previous month | MoM |

**Rules:**
1. Hour is not simply the previous hour. Compare Monday 7:00 vs previous Monday 7:00.
2. Day comparison must consider day-of-week for mobility operations.
3. Week uses ISO week (Monday).
4. Month uses calendar month.
5. If comparable period doesn't exist → `Not comparable`. Never zero.
6. Never mix temporal comparison with Plan vs Real.

### 10.2 Closed Period Rule

| Period Type | Rule |
|-------------|------|
| closed | compare against full closed comparable periods |
| open/current | mark as partial; compare against equivalent elapsed window |
| future | not comparable |

1. Open period must not be compared against full closed period without `partial` label.
2. Example: Monday 10:00 vs previous Monday up to 10:00.
3. If no equivalent window, show `Partial / not comparable`.
4. Never infer period closure without evidence.

### 10.3 Peak of Last 4 Closed Comparable Periods

Baseline: `Peak last 4`
- Best value observed in last 4 closed comparable periods.
- Grain-aware: hour → last 4 comparable hours, day → last 4 comparable days, week → last 4 closed weeks, month → last 4 closed months.
- Answers: "Are we near the best recent performance?"
- Not forecast. Not target. Not Plan.
- If < 4 periods → `limited history`.
- Closed periods only.

### 10.4 Moving Average Baseline

Baseline: `Rolling average`
- Rolling average of last N closed comparable periods.
- Defaults: hour→4, day→4, week→4, month→3/4.
- Answers: "Are we above or below recent trend?"
- Not forecast. Not target.
- Label: `Avg last 4` or `Avg last 3`.
- If insufficient history → `limited history`.
- Never invent missing values.

### 10.5 Visual Separation Rules

The cockpit must separate:

| Concept | Meaning |
|---------|---------|
| Temporal delta | actual vs comparable period |
| Peak last 4 | actual vs best recent period |
| Rolling average | actual vs recent average |
| Plan delta | actual vs plan |

**Rules:**
1. Never mix labels.
2. Never use same color without explaining concept.
3. Never present peak or moving average as forecast.
4. Never present deviation as root cause.

### 10.6 Precheck Additions

1. Is the comparison temporal, peak, rolling average, or Plan vs Real?
2. What is the active grain?
3. What is the current period — closed or partial?
4. What is the comparable period?
5. Does the comparable respect same-day/hour when applicable?
6. Is comparison against full closed period or equivalent window?
7. What is the peak last 4 baseline?
8. What is the rolling average used?
9. Is there sufficient history?
10. What is shown if history is missing?
11. Is the metric higher-is-better or lower-is-better?
12. Does color represent better/worse?
13. Is it separated from Plan vs Real?
14. Is forecast/diagnosis avoided?
15. Is freshness validated for both current and comparable periods?
16. Does UI show `Not comparable` instead of false zero?
17. Can the user understand the comparator without tooltip?
18. Is the logic lightweight in frontend?
19. Is there a rollback?
20. Is it documented in the contract?

---

## 11. Precheck (Visual Prompts)

1. What operational question does this chart answer?
2. Which certified endpoint feeds it?
3. What grain? What metric?
4. Plan and Real separated correctly?
5. Higher-is-better or lower-is-better?
6. Null/no data behavior?
7. Stale/unknown freshness behavior?
8. Frontend aggregation? Is it lightweight?
9. Runtime-heavy risk?
10. Zoom 90/100/110% behavior?
11. Focus mode / fit-to-width?
12. Double scroll risk?
13. Understandable without tooltip?
14. State communicated with text + color?
15. Matrix still available as detail/export?
16. Export still works?
17. Browser smoke done?
18. Rollback exists?
19. Documented in North Star / contract?

---

## 12. Freshness Evidence Contract (OV2-GOV-FR1)

Every Omniview phase that touches UI, charts, matrix, KPI cards, or visual cockpit must include real freshness evidence.

**Rules:**
1. No theoretical freshness accepted. No "endpoint 200" only. No "health OK" only.
2. Every report must include a `Freshness Evidence Snapshot`.
3. If data is stale → `TECHNICAL GO` but NOT `OPERATIONAL GO`.
4. If freshness is unknown → phase cannot be marked certified.
5. If a visualization uses multiple endpoints, each endpoint needs evidence.
6. If freshness is unverifiable for a source, declare it explicitly.
7. Do NOT execute refresh/backfill to "force" PASS unless explicitly instructed.

**Freshness Evidence Snapshot (required fields):**

| Field | Required |
|-------|----------|
| endpoint | YES |
| source table / serving fact | YES if known |
| operating_date | YES |
| max_data_date / max_period | YES |
| row_count / period_count | YES if available |
| freshness_status | YES |
| stale_age | YES if calculable |
| freshness_threshold | YES if defined |
| last_refresh_at | YES if available |
| validation_timestamp | YES |
| pass_fail | YES |
| UI impact | YES |

**Decision Classification:**
- Technical GO: build + browser pass
- Browser GO: UI renders correctly
- Freshness GO: data is fresh per threshold
- Operational GO: Technical + Browser + Freshness all pass

If Freshness is WARN/FAIL → Operational GO is CONDITIONAL.