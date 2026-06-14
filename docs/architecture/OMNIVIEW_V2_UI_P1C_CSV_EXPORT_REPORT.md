# OMNIVIEW V2 — UI P1C CSV EXPORT REPORT

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** COMPLETED — CSV export implemented
**Phase:** OV2-UI-P1C

---

## 0. Executive Decision

**GO: CSV EXPORT COMPLETE**

CSV export button added to CommandHeader. Exports current V2 matrix view (grain, metric, filters) with metadata, freshness data, and cells in wide + long format. No backend calls. Formula injection protection from V1 ported.

---

## 1. Scope

Implement client-side CSV export for Omniview V2 current view. Exports in-memory matrix data only. No backend export endpoint.

---

## 2. V1 Export Audit

| V1 Capability | Safe for V2? | Port? | Reason |
|--------------|-------------|-------|--------|
| `csvEscape` (formula injection protection) | YES | PORT_GENERIC | Generic safe escaping |
| `csvRow` / `csvSection` helpers | YES | PORT_GENERIC | Generic CSV construction |
| `timestamp` / `filename` generators | YES | PORT_GENERIC | Generic utilities |
| Metadata section builder | YES | ADAPT_FOR_V2 | V2 has different shape (no planVersion, has canonical_ready) |
| Matrix section (wide/long) | YES | ADAPT_FOR_V2 | V2 cells are in different format |
| YTD summary section | NO | DO_NOT_PORT | Belongs to projection/plan-vs-real, not in V2 yet |
| Opportunities summary | NO | DO_NOT_PORT | Belongs to Diagnostic/Action engines |
| Trust/evidence export | NO | DIAGNOSTIC_BLOCKED | Trust composite scoring belongs to Diagnostic Engine |
| V1-specific state shape | NO | DO_NOT_PORT | V2 has different state structure |
| `signalColorForKpi` for color export | NO | DO_NOT_PORT | Color semantics exported via tone labels, not hardcoded colors |
| `computeDeltas` runtime calculation | NO | DO_NOT_PORT | V2 deltas come from backend; no UI recalculation |

---

## 3. V2 Export Contract

### Sections

1. **Metadata** — 18 fields: product, grain, metric, filters, source, canonical_ready, freshness, row/column counts
2. **Freshness & Governance** — freshness status, coverage %, canonical_ready status
3. **Matrix (wide)** — Business Slice × Period matrix
4. **Matrix (long)** — normalized: row_label, period, value, formatted, delta, delta_pct, status

### Privacy/PII Guardrails

- No driver-level data exported
- No raw SQL queries exported
- No park_id driver details exported
- No inspector deep data exported
- Formula injection protection (V1 `csvEscape` ported)
- UTF-8 BOM for Excel compatibility

### N/A Handling

- `cell.value == null` → `"N/A"` (not `"0"`)
- `delta == null` → empty string
- Missing metadata field → empty string

---

## 4. Files Modified

| File | Change |
|------|--------|
| `omniviewV2Export.js` | **CREATED** — Export engine with metadata, matrix (wide+long), freshness sections |
| `OmniviewV2CommandHeader.jsx` | **MODIFIED** — Export CSV button (disabled when no data) |
| `OmniviewV2ShadowPage.jsx` | **MODIFIED** — `handleExportCsv` callback + imports |

---

## 5. Exported Fields

### Metadata (18 fields)
export_generated_at, product, grain, selected_metric_id, selected_metric_label, selected_metric_unit, selected_metric_polarity, view_mode, country, city, business_slice, park_id, date_from, date_to, source_system, canonical_ready, freshness_status, row_count, column_count

### Matrix Wide
Business Slice label + 1 column per period with formatted metric value

### Matrix Long
Business Slice, Period, Value, Formatted, Delta, Delta %, Status

---

## 6. Disabled / Error Behavior

| Condition | Button State | Tooltip |
|-----------|-------------|---------|
| `hasData == false` | Disabled (gray) | "No data available to export" |
| `matrixData == null` | Disabled (gray) | "No data available to export" |
| `cells.length == 0` | Disabled (gray) | "No data available to export" |
| Export error (catch) | Silent console.error | N/A |

---

## 7. Filename

`omniview_v2_<grain>_<metricId>_<YYYYMMDD_HHmm>.csv`

Example: `omniview_v2_day_orders_20260613_2130.csv`

---

## 8. Validation

| Check | Result |
|-------|--------|
| `npm run build` | PASS (9.50s) |
| Backend untouched | CONFIRMED |
| No legacy endpoints | CONFIRMED |
| No raw SQL exported | CONFIRMED |
| No driver PII exported | CONFIRMED |
| Button renders in CommandHeader | CONFIRMED |
| Button disabled when no data | CONFIRMED |
| Formula injection protection | CONFIRMED |

---

## 9. Remaining Gaps

| Gap | Status |
|-----|--------|
| P0-1: Multi-metric selector | COMPLETE |
| P0-2: CSV export | **COMPLETE** |
| P0-3: Color semantics | COMPLETE |
| P0-4: Sort controls | PENDING |
| P0-5: Plan vs Real visualization | PENDING |
| P0-6: Period presets | PENDING |

---

## 10. Next Phase

**OV2-UI-P1D: Sort Controls.** Add sort dropdown (alpha, impact, volume). Reorder matrix rows without refetch. Do NOT implement charts, period presets, or Diagnostic Engine.

---

*CSV export complete. Safe V1 patterns ported. No backend calls. No PII exported.*