# OV2-C.2 — CELL CONTRACT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture

---

## 1. CELL DATA CONTRACT

Every matrix cell must receive the following fields from the backend (or derived from the shell contract already defined in OV2-C.0/C.1):

### 1.1 Identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| metric_id | string | YES | Canonical metric identifier (orders, revenue, active_drivers, etc.) |
| label | string | YES | Human-readable label (Orders Completed) |
| slice_id | string | NO | Business slice identifier (for slice-level matrices) |
| slice_label | string | NO | Human-readable slice name |

### 1.2 Value

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| value | number\|null | YES | Raw numeric value. null if unavailable. |
| formatted_value | string | YES | Formatted for display (e.g. "14,213" or "5,832.27 PEN") |
| unit | string | YES | Unit of measurement (count, PEN, percent, ratio, hours) |

### 1.3 Source

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_system | string | YES | CT_TRIPS_2026 or YANGO_API_RAW |
| source_table | string | YES | Full table/view name (e.g. ops.real_business_slice_day_fact) |
| grain | string | YES | hour, day, week, month |

### 1.4 Period

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| period | string | YES | Period identifier (ISO date for day, week_start for week, month for month) |
| period_status | string | YES | CLOSED, PARTIAL, CURRENT, FUTURE, NO_PLAN, NO_REAL |

### 1.5 Trust

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| canonical_ready | boolean | YES | Is this source certified for operational decisions? |
| coverage_pct | number | YES | Data coverage for this period (0-100) |
| freshness | string | YES | How recent is the data? (e.g. "5m ago", "stale 2h") |
| confidence | string | YES | HIGH, MEDIUM, LOW |
| is_estimated | boolean | YES | Is this value estimated/derived rather than direct? |

### 1.6 Warnings

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| warning_codes | string[] | YES | Codes for active warnings on this cell (e.g. ["REVENUE_DELTA", "SHORT_SERIES"]) |

### 1.7 Lineage

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| lineage_refs | object | YES | { origin_table, origin_field, aggregation, filters_applied } |

### 1.8 Comparison (only in compare mode)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| comparison_status | string | NO | MATCH, MINOR_DELTA, MAJOR_DELTA, NOT_COMPARABLE |
| delta_value | number\|null | NO | Absolute difference between sources |
| delta_pct | number\|null | NO | Percentage difference |

### 1.9 Status

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| cell_status | string | YES | OK, WARNING, BLOCKED, NOT_COMPARABLE |

---

## 2. CELL STATUS LOGIC

```
cell_status = OK
if value is null → cell_status = BLOCKED
if any warning_code has severity=critical → cell_status = BLOCKED
if coverage_pct < 50 → cell_status = BLOCKED
if is_estimated and confidence=LOW → cell_status = WARNING
if coverage_pct < 95 → cell_status = WARNING
if period_status in (PARTIAL, NO_PLAN, NO_REAL) → cell_status = WARNING
if canonical_ready=false → no status change (handled by source badge)
if comparison_status=MAJOR_DELTA → cell_status = WARNING
```

**Frontend rule:** Frontend does NOT compute cell_status. Backend returns it.

---

## 3. CELL RENDERING

| cell_status | Background | Border | Text | Icon |
|-------------|-----------|--------|------|------|
| OK | white | none | default | none |
| WARNING | amber-50 (#fffbeb) | left amber-500 | default | ⚠ subtle |
| BLOCKED | red-50 (#fef2f2) | left red-500 | gray-400 | 🚫 |
| NOT_COMPARABLE | gray-50 | none | gray-400 | — |

### Badges visible on cell:
- PARTIAL (amber) — period has incomplete data
- ESTIMATED (purple) — value is derived, not direct
- SHADOW (purple) — source is not canonical
- DELTA (amber/red) — comparison delta (only in compare mode)

---

## 4. CELL TOOLTIP (hover)

Before clicking, tooltip shows:
- metric_id + label
- period + period_status badge

After clicking → full inspector opens.

---

## 5. CELL COMPUTATION RULES

| What the CELL does | What the CELL does NOT do |
|-------------------|--------------------------|
| Render value + unit | Calculate WoW/MoM delta |
| Apply status color | Fetch data |
| Show badges | Transform values |
| Respond to click | Compute pacing |
| Show tooltip on hover | Project future values |
| Highlight on focus | Persist state |

All computation is backend-side. The cell is a pure render component.
