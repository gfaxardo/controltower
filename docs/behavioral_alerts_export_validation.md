# Behavioral Alerts — Export Validation

**Date:** 2026-03-11  
**Phase:** 8 — Export validation

---

## Test scenario

1. **Filters:** e.g. alert_type = Critical Drop, baseline_window = 6, date range = last 8 weeks (or recent period with data).
2. **Action:** Click "Exportar CSV" (or "Exportar Excel").
3. **Expected:** File downloads; name behavior_alerts.csv (or behavior_alerts.xlsx).

---

## Expected columns (in order)

driver_key, driver_name, country, city, park_name, week_label, segment_current, **movement_type**, trips_current_week, avg_trips_baseline, delta_abs, delta_pct, alert_type, **alert_severity**, **risk_score**, **risk_band**.

---

## Checks

| Check | Expected | Pass/Fail (user) |
|-------|----------|-------------------|
| File generated | CSV or Excel file downloads. | Pending |
| Columns present | All columns above present; movement_type, alert_severity, risk_score, risk_band included. | Pending |
| Rows match filters | Row set matches active filters (e.g. only Critical Drop if that filter was set). | Pending |
| No extra/missing columns | Same set as API export endpoint. | Pending |

---

## Verification steps (user)

1. Set filters (e.g. risk_band = high risk, from/to = last 2 months).
2. Click Exportar CSV.
3. Open the file; confirm header has movement_type, alert_severity, risk_score, risk_band.
4. Confirm row count is consistent with filtered table (or export max_rows limit).
5. Repeat with Exportar Excel if used.

---

## Note

Export validation was **not** run during this closure (migrations not at 085). User to verify after environment is ready.
