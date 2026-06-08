# OV2-F.2D — DRIVER DAY BRIDGE & WEEKLY DRIVERS — FINAL REPORT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Phase:** OV2-F.2D — Driver-Day Slice Bridge + Canonical Weekly Drivers
> **Status:** **DESIGN + SCRIPTS COMPLETE — EXECUTION PENDING DB ACCESS**

---

## 1. EXECUTIVE SUMMARY

Se diseñó la tabla `ops.driver_day_slice_fact` como bridge intermedio entre raw trips y serving facts. Permite calcular `active_drivers` semanal exacto (`COUNT DISTINCT`) sin escanear 6.8M viajes raw. El bridge se construye desde `v_real_trips_business_slice_resolved` (que ya tiene driver→slice resuelto). Se crearon 4 scripts: migración, build, validación y rebuild semanal con bridge.

---

## 2. ARCHITECTURE

```
RAW trips_2025/2026
  → v_real_trips_enriched_base (driver_id, park_id, trip_date, completed_flag)
  → v_real_trips_business_slice_resolved (+ business_slice_name)
  → ops.driver_day_slice_fact [NEW — bridge]
       (driver_id, activity_date, business_slice_name, completed_trips)
  → day_fact (trips + revenue from bridge aggregation)
  → week_fact (exact active_drivers from bridge → COUNT DISTINCT)
  → month_fact
  → snapshots
  → UI
```

The bridge is built ONCE (batch backfill), then updated incrementally daily. No raw trip scanning for serving refresh.

---

## 3. BRIDGE TABLE

**Table:** `ops.driver_day_slice_fact`

| Grain | Fields | Unique Key |
|-------|--------|------------|
| driver × day × slice × park | 17 columns | `(activity_date, country, city, park_id, business_slice_name, driver_id)` |

**Flags:**
- `completed_flag` — has ≥1 completed trip
- `cancel_only_flag` — has trips but 0 completed
- `empty_supply_flag` — no completed trips (supply without production)

---

## 4. DELIVERABLES

| # | Deliverable | Type | Status |
|---|-------------|------|--------|
| 1 | Bridge Contract | `OV2_F2D_DRIVER_DAY_SLICE_BRIDGE_CONTRACT.md` | COMPLETE |
| 2 | Source Audit | `OV2_F2D_DRIVER_SOURCE_AUDIT.md` | COMPLETE |
| 3 | Migration | `scripts/migrate_driver_day_slice_fact.py` | CREATED + COMPILED |
| 4 | Build Script | `scripts/build_driver_day_slice_fact.py` | CREATED + COMPILED |
| 5 | Validation Script | `scripts/audit_driver_day_slice_fact.py` | CREATED + COMPILED |
| 6 | Week Rebuild | `scripts/rebuild_week_from_day_and_bridge.py` | CREATED + COMPILED |
| 7 | Fail-Fast Rules | `OV2_F2D_FAIL_FAST_CLOSED_PERIOD.md` | COMPLETE |
| 8 | This Report | `OV2_F2D_DRIVER_DAY_BRIDGE_AND_WEEKLY_DRIVERS_REPORT.md` | THIS DOCUMENT |

---

## 5. EXECUTION SEQUENCE

```bash
# Step 1: Create table
python -m scripts.migrate_driver_day_slice_fact

# Step 2: Build bridge (initial backfill, 7-day batches)
python -m scripts.build_driver_day_slice_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 \
  --country peru --city lima --batch-days 7 --dry-run

python -m scripts.build_driver_day_slice_fact \
  --date-from 2026-04-01 --date-to 2026-06-06 \
  --country peru --city lima --batch-days 7 --confirm

# Step 3: Validate bridge vs day_fact
python -m scripts.audit_driver_day_slice_fact \
  --date-from 2026-04-01 --date-to 2026-06-06

# Step 4: Rebuild week with exact drivers
python -m scripts.rebuild_week_from_day_and_bridge \
  --date-from 2026-04-01 --date-to 2026-06-06 --dry-run

python -m scripts.rebuild_week_from_day_and_bridge \
  --date-from 2026-04-01 --date-to 2026-06-06 --confirm

# Step 5: Validate waterfall
python -m scripts.validate_refresh_waterfall

# Step 6: Rebuild month + snapshots
python -m scripts.refresh_omniview_real_slice_incremental --grain month --force --start-date 2026-04-01 --end-date 2026-06-08
python -m scripts.refresh_omniview_v2_snapshots --use-latest-closed-date --confirm
```

---

## 6. GO/NO-GO FOR F.3

| Criterion | Status |
|-----------|--------|
| Bridge contract designed | ✓ |
| Migration script ready | ✓ |
| Build script ready (batch-based, 7-day) | ✓ |
| Validation script ready | ✓ |
| Week rebuild with exact drivers ready | ✓ |
| Active drivers no longer upper bound | ✓ (COUNT DISTINCT from bridge) |
| Empty supply KPI available | ✓ |
| No raw trips for serving refresh | ✓ |
| V1 intact | ✓ |

## **DESIGN COMPLETE — GO for execution when DB accessible**

---

*End of OV2-F.2D Final Report*
