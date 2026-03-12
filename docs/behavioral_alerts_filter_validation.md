# Behavioral Alerts — Filter Validation

**Date:** 2026-03-11  
**Phase:** 7 — Filter behavior validation

---

## Filters to test

| Filter | Expected | Pass/Fail (user) |
|--------|----------|-------------------|
| **Date range (from / to)** | Table and KPIs restricted to weeks in range. | Pending |
| **Baseline window (4 / 6 / 8)** | API receives baseline_window; view uses 6w; KPIs/table reflect filtered set. | Pending |
| **Country** | Only rows for selected country. | Pending |
| **City** | Only rows for selected city. | Pending |
| **Park** | Only rows for selected park. | Pending |
| **Segment current** | Only segment_current = selected (e.g. FT, PT). | Pending |
| **Movement type** | Only movement_type = selected (upshift, downshift, stable, drop, new). | Pending |
| **Alert type** | Only alert_type = selected. | Pending |
| **Severity** | Only severity = selected. | Pending |
| **Risk band** | Only risk_band = selected (stable, monitor, medium risk, high risk). | Pending |

---

## Cross-checks

- **Table vs filters:** Changing any filter should change the table rows and total count.
- **KPIs vs filters:** Summary counts (drivers monitored, critical drops, high_risk_drivers, etc.) should match the filtered set.
- **Export vs filters:** Downloaded file should contain only rows that match the active filters.
- **Drilldown context:** Driver detail is for the selected driver; date/week context should respect global from/to if used.

---

## Verification steps (user)

1. Load Behavioral Alerts with default filters; note KPI values and table row count.
2. Set **risk_band = high risk**; confirm table and KPIs update and "Alto riesgo" matches table count.
3. Set **alert_type = Critical Drop**; confirm only Critical Drop rows and "Caídas críticas" matches.
4. Set a narrow **date range**; confirm table and KPIs only for that range.
5. Trigger **Export CSV** with filters applied; open file and confirm rows match active filters and columns include risk_score, risk_band, movement_type.

---

## Note

Filter validation was **not** run during this closure (migrations not at 085). User to verify after environment is ready.
