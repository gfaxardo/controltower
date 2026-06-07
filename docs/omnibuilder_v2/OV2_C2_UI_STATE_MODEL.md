# OV2-C.2 — UI STATE MODEL

> **Date:** 2026-06-06
> **Motor:** Control Foundation / UX Architecture

---

## 1. MINIMUM STATE

```javascript
const omniviewV2State = {
  // ── Filters ──────────────────────────────────────
  source_system: "CT_TRIPS_2026",     // "CT_TRIPS_2026" | "YANGO_API_RAW"
  grain: "day",                        // "hour" | "day" | "week" | "month"
  date_from: "2026-06-04",            // ISO date string
  date_to: "2026-06-04",              // ISO date string
  country: "peru",
  city: "lima",
  park_id: null,                       // Only set for YANGO_API_RAW source

  // ── UI Focus ─────────────────────────────────────
  selected_section: null,              // section_id of focused section
  selected_cell: null,                 // { row_index, column_index, metric_id }
  inspector_open: false,
  compare_mode: false,

  // ── Data ─────────────────────────────────────────
  shell_data: null,                    // OmniviewV2ShellResponse
  loading: false,
  error: null,
};
```

---

## 2. STATE FLOW

```
[Init] → source_system=CT, grain=day, period=today
  → fetch shell → loading=true
  → shell_data loaded → loading=false
  → render executive + sections + matrix
  → [Idle]

[Source Change] → set source_system=new
  → fetch shell with new source
  → if source=YANGO_API_RAW: park_id set, country/city cleared
  → [Idle]

[Grain Change] → set grain=new
  → validate source supports grain
  → if not supported: show GRAIN_NOT_SUPPORTED
  → fetch shell with new grain
  → [Idle]

[Period Change] → set date_from, date_to
  → fetch shell with new period
  → [Idle]

[Cell Click] → set selected_cell, inspector_open=true
  → no fetch — inspector uses existing shell_data

[Alert Click] → set selected_section=target_section
  → scroll to section or cell
  → if target is cell: open inspector

[Compare Toggle] → set compare_mode=true
  → fetch both sources (CT + Yango)
  → render ComparePanel
  → close → compare_mode=false, reset to single source
```

---

## 3. DATA FETCHING

### Hook: `useOmniviewV2Shell(source_system, grain, date_from, date_to, filters)`

```javascript
function useOmniviewV2Shell(source, grain, dateFrom, dateTo, filters) {
  // Calls GET /ops/omniview-v2/shell?source_system=&grain=&date_from=&date_to=
  // Returns { shellData, loading, error, refetch }
  // Re-fetches when any dependency changes
  // Debounce period changes (300ms)
  // Cache previous result for instant back-navigation
}
```

---

## 4. DERIVED STATE (computed, not stored)

| Derived value | Computation |
|--------------|-------------|
| canonical_ready | shell_data.canonical_ready |
| active_warnings_count | shell_data.sections[0].active_warnings_count |
| executive_kpis | shell_data.sections.find(s => s.section_id === "kpi_strip").kpis |
| coverage_status | shell_data.sections.find(s => s.section_id === "operational_coverage") |
| matrix_rows | Derived from kpis and grain. Structure depends on backend response format. |
| breadcrumb_items | [source_system, grain, `${date_from}–${date_to}`, selected_section, selected_cell?.metric_id] |

---

## 5. PERSISTENCE RULES

**Current phase (OV2-C.2): NO persistence.**

No localStorage. No sessionStorage. No URL params (yet).

**When persistence is added (OV2-C.3+):**

```javascript
const STORAGE_KEY = "omniview_v2_state_v1";  // versioned key

function saveState(state) {
  const payload = {
    version: 1,
    schema_version: "2026-06-06",
    state: {
      source_system: state.source_system,
      grain: state.grain,
      date_from: state.date_from,
      date_to: state.date_to,
      country: state.country,
      city: state.city,
    }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed.version !== 1) return null;         // version mismatch → reset
    if (!parsed.state.source_system) return null;  // invalid → reset
    return parsed.state;
  } catch {
    return null;  // corrupt → reset
  }
}
```

### Rules:
- Version key changes when schema changes.
- Validation on load: required fields must exist.
- If load fails: silent fallback to defaults.
- No error shown to user on persistence failure.
- Persist only filters. Never persist shell_data, selected_cell, inspector_open.

---

## 6. STATE INVARIANTS

| Invariant | Enforcement |
|-----------|------------|
| source_system is always a registered source | Dropdown only shows registered sources |
| grain is always supported by source | Dropdown filtered by source.supported_grains |
| date_from <= date_to | Period picker enforces |
| selected_cell references a real cell | Cleared on data reload |
| inspector_open implies selected_cell is set | Opened only via cell click |
| compare_mode never mixes sources in one view | Each source has its own labeled column |
| loading=true shows skeleton, not blank | Skeleton component renders during fetch |
| error shows retry, not crash | ErrorBoundary + EmptyState |
