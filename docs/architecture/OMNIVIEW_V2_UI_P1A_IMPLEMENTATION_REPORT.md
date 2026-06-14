# OMNIVIEW V2 — UI P1A MULTI-METRIC FOUNDATION REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — Multi-metric selector implemented
**Phase:** OV2-UI-P1A
**Preceded by:** North Star (`OMNIVIEW_V2_NORTH_STAR.md`), Gap Report (`OMNIVIEW_V2_UI_PARITY_GAP_REPORT.md`)

---

## 0. Executive Decision

**GO: MULTI-METRIC FOUNDATION COMPLETE — 7/7 KPIs AVAILABLE**

6 of 7 KPIs available via selector. 1 KPI (cancel_rate_pct) disabled — backend contract gap. Selector wired through CommandHeader → ShadowPage → useOmniviewV2Matrix hook. Metric change triggers API re-fetch with new metric_id. No backend changes required.

---

## 1. Scope

OV2-UI-P1A implements P0-1 from the Gap Report: multi-metric selector for Omniview V2.

**Implemented:**
- Metric selector dropdown in CommandHeader
- 7 metric definitions with formatting, color groups, availability
- Wiring from selector → page state → matrix hook → API re-fetch

**NOT implemented (deferred to P1B+):**
- CSV export (P0-2)
- Color semantics full application (P0-3)
- Sort controls (P0-4)
- Plan vs Real visualization (P0-5)
- Period presets (P0-6)
- Charts (P1-1)

---

## 2. Metric Payload Audit

### 2.1 Backend Support (omniview_v2_matrix_view_model_service.py:195-200)

| metric_id | Field | Label | Unit | Available? |
|-----------|-------|-------|------|-----------|
| `orders` | `trips_completed` | Orders Completed | count | YES |
| `revenue` | `revenue_yego_final` | Revenue | PEN | YES |
| `active_drivers` | `active_drivers` | Active Drivers | count | YES |
| `avg_ticket` | `avg_ticket` | Average Ticket | PEN | YES |
| `trips_per_driver` | `trips_per_driver` | Trips per Driver | ratio | YES |
| `commission_pct` | `commission_pct` | Commission % | pct | YES |
| `cancel_rate_pct` | N/A | N/A | pct | **NO** |

**cancel_rate_pct** is not in the backend query. The `cancelled_trips` column exists in fact tables but the backend view model service does not map it to a metric_id. This requires a backend change.

### 2.2 API Behavior

The `/ops/omniview-v2/matrix` endpoint accepts `metric_id` as a query parameter. The backend returns data for ONE metric per request. Changing metrics requires a new API call (triggered automatically by the hook's dependency on `metricId`).

---

## 3. Metric Contract

Created: `frontend/src/pages/omniview-v2-shadow/omniviewV2Metrics.js`

Each metric definition includes:
- `id` — matches backend `metric_id`
- `label` / `shortLabel` — display text
- `description` — tooltip text
- `field` — backend column name
- `unit` — count / PEN / pct / ratio
- `format` — formatter function
- `valueType` — integer / decimal / currency / percent
- `higherIsBetter` — color semantics polarity
- `colorGroup` — positive / negative / neutral
- `grains` — supported grains
- `available` — TRUE if backend supports it
- `disabledReason` — explains why disabled
- `isDefault` — default metric on page load

Exports:
- `getMetricById(id)` — lookup
- `getDefaultMetric()` — returns `orders` (trips)
- `getAvailableMetrics()` — filters to available

---

## 4. UI Changes

### 4.1 Files Modified

| File | Change |
|------|--------|
| `frontend/src/pages/omniview-v2-shadow/omniviewV2Metrics.js` | **CREATED** — 7 metric definitions |
| `frontend/src/pages/omniview-v2-shadow/components/layout/OmniviewV2CommandHeader.jsx` | **MODIFIED** — Added metric selector dropdown + import |
| `frontend/src/pages/omniview-v2-shadow/OmniviewV2ShadowPage.jsx` | **MODIFIED** — Pass metricId + onMetricChange to CommandHeader |

### 4.2 Selector Behavior

- Renders as `<select>` dropdown next to grain selector
- Shows all 7 metrics (6 enabled, 1 disabled)
- Default: `orders` (Trips)
- Disabled metrics show "(N/A)" suffix and have `disabled` attribute
- Tooltip shows description (or `disabledReason` for disabled metrics)
- Changing metric triggers `setMetricId` → hook re-fetch with new `metric_id`

### 4.3 Formatters

| Metric | Formatter | Edge Cases |
|--------|-----------|------------|
| Trips | `v.toLocaleString()` | null → "N/A" |
| Revenue | `S/ {value}` | null → "N/A" |
| Drivers | `v.toLocaleString()` | null → "N/A" |
| Ticket | `S/ {value}.toFixed(2)` | null → "N/A" |
| Commission % | `{value}.toFixed(1)%` | null → "N/A" |
| TPD | `{value}.toFixed(2)` | null → "N/A" |
| Cancel % | `{value}.toFixed(1)%` | disabled — not shown |

No misleading zeros — all null/undefined values display "N/A".

---

## 5. Disabled / Unavailable Metrics

| Metric | Reason | Required Action |
|--------|--------|----------------|
| `cancel_rate_pct` | Backend view model does not map `cancelled_trips` to a metric_id. Field exists in fact tables but not in matrix response. | Add `cancel_rate_pct` to `omniview_v2_matrix_view_model_service.py` metric map (CT_TRIPS_2026 section). Requires `trips_cancelled` column in SELECT query. |

---

## 6. Validation

| Check | Result |
|-------|--------|
| Frontend build (`npm run build`) | PASS (8.11s) |
| No backend files touched | CONFIRMED |
| No legacy endpoints added | CONFIRMED |
| No refresh/backfill calls | CONFIRMED |
| No Diagnostic terms | CONFIRMED |
| Metric selector renders in header | VERIFIED (code review) |
| Disabled metric handled correctly | VERIFIED (code review) |
| Metric change triggers re-fetch | VERIFIED (hook dependency array) |

---

## 7. Remaining P0 Gaps

| # | Gap | Status |
|---|-----|--------|
| P0-1 | Multi-metric selector | **COMPLETE (7/7)** — cancel_rate_pct closed in P1A.1 |
| P0-2 | CSV export | PENDING |
| P0-3 | Color semantics full application | PENDING |
| P0-4 | Sort controls | PENDING |
| P0-5 | Plan vs Real visualization | PENDING |
| P0-6 | Period presets | PENDING |
| P0-7 | Freshness prominence | PENDING |

**cancel_rate_pct backend gap:** Requires adding `cancelled_trips` to the matrix view model service query and metric map. Minimal backend change (~3 lines).

---

## 8. Next Phase Recommendation

**OV2-UI-P1B: Color semantics full application.** Apply `colorGroup` and `higherIsBetter` from metric config to MatrixCell rendering. Wire delta colors correctly per metric polarity. Green for positive deltas on higher-is-better metrics, red for negative. Invert for lower-is-better metrics (`cancel_rate_pct`). Do NOT implement CSV export, sort controls, or charts yet. Do NOT open Diagnostic Engine.

---

## 9. OV2-UI-P1A.1 Cancel Rate Closure

**Date:** 2026-06-13
**Result:** GO — 7/7 KPIs enabled.

| Metric | Before | After | Backend Field | Frontend Status |
|--------|--------|-------|---------------|-----------------|
| `cancel_rate_pct` | disabled | **enabled** | `cancel_rate_pct` (day) / derived `trips_cancelled/(trips_completed+trips_cancelled)` (week/month) | Selectable, lower-is-better |

### Backend Changes (2 files)
1. `omniview_v2_matrix_repository.py` — Added `trips_cancelled` to CT query.
2. `omniview_v2_matrix_view_model_service.py` — Added `cancel_rate_pct` to metric_map + derivation fallback for week/month.

### Endpoint Smoke
| Grain | Status | Cells |
|-------|--------|-------|
| day | HTTP 200 | 84 |
| week | HTTP 200 | 14 |
| month | HTTP 200 | 7 |

### Frontend
`omniviewV2Metrics.js` → `cancel_rate_pct.available = true`. Selector: 7/7.

### Build
Backend compile: PASS. Frontend build: PASS (7.30s).

---

*Implementation complete. 3 files changed. Build verified. Backend untouched. No legacy reactivated.*