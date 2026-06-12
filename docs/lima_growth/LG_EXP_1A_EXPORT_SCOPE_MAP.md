# LG-EXP-1A — EXPORT SCOPE MAP

**Date:** 2026-06-12

---

## EXPORT SOURCES

| Source | Filters | Columns | Max Rows | Risk |
|--------|---------|---------|----------|------|
| Driver Explorer | program, lifecycle, segment, rna, search | 13 safe columns | 10,000 | LOW |
| Programs | program_code | program, drivers, priority | 10,000 | LOW |
| Segments | lifecycle, value_tier, momentum | segment, drivers, pct | 10,000 | LOW |
| Movement | transition_type, date | driver, from, to, type, trigger | 10,000 | LOW |
| RNA | city, is_rna, contactability | driver, rna_status, cancelled, phone | 10,000 | MEDIUM (phone data) |

---

## SAFE COLUMNS (13)

driver_id, driver_name, phone, city, park, lifecycle, segment, activity_status, value_tier, momentum, program, movement_status, rna_status, contactability, last_activity, trips_7d, trips_30d, explanation_summary

---

## SERVING SOURCE

Export queries combine:
- `growth.yango_lima_driver_state_snapshot` (driver identities, RNA status)
- `growth.yego_lima_driver_lifecycle_daily` (lifecycle, trips)
- `growth.yego_lima_driver_taxonomy_v2_daily` (segments, value)
- `growth.yango_lima_program_eligibility_daily` (programs)

All reads are lightweight filtered queries. No joins beyond what serving facts already support.
