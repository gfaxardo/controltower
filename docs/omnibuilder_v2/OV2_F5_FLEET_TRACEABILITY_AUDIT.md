# OV2-F.5 — FLEET / SUBFLEET TRACEABILITY AUDIT

> **Date:** 2026-06-08
> **Status:** **PARTIAL**

---

## 1. FLEET DATA AVAILABILITY

| Table | fleet_display_name | is_subfleet | subfleet_name | parent_fleet_name |
|-------|-------------------|-------------|---------------|-------------------|
| `driver_day_slice_fact` (bridge) | ❌ | ❌ | ❌ | ❌ |
| `real_business_slice_day_fact` (legacy rows) | ✅ | ✅ | ✅ | ✅ |
| `real_business_slice_day_fact` (bridge rebuilt) | ❌ | ❌ | ❌ | ❌ |
| `business_slice_mapping_rules` | ✅ (fleet = business_slice) | ✅ | ✅ | ✅ |

## 2. ISSUE

Bridge-based day_fact rebuild lost fleet/subfleet columns. The bridge aggregates by driver/day/slice/park but does NOT include fleet hierarchy.

Legacy day_fact had these from the enriched resolution:
- `fleet_display_name` = "Yego." (the fleet/parent brand)
- `is_subfleet` = false (for top-level slices)
- `subfleet_name` = "" (no subfleets for Lima)

## 3. RECONSTRUCTION OPTIONS

| Option | Feasibility |
|--------|------------|
| A — Query legacy day_fact for fleet columns | Fleet data exists but day_fact was overwritten by bridge rebuild |
| B — Add fleet to bridge | Requires mapping rules query per driver-day-park |
| C — Use business_slice_mapping_rules as proxy | Each slice has a fleet mapping |

## 4. VERDICT

**PARTIAL** — Fleet/subfleet NOT available from bridge. Available from legacy day_fact (now overwritten). Can be reconstructed from `business_slice_mapping_rules` or by adding fleet columns to the bridge.

---

*End of Fleet Traceability Audit*
