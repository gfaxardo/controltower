# Control Tower — Migration & Driver Lifecycle Scan (Read-Only)

**Purpose:** Diagnostic of where migration data originates, how weeks are calculated, current ordering logic, and segment taxonomy. No modifications.

---

## 1. Source Tables & MVs for Migrations

| Object | Type | Role |
|--------|------|------|
| **ops.mv_driver_segments_weekly** | Materialized View | **Primary source for migration.** One row per (driver_key, week_start). Columns: driver_key, week_start, park_id, trips_completed_week, segment_week, prev_segment_week, segment_change_type, weeks_active_rolling_4w, baseline_trips_4w_avg. `prev_segment_week` = LAG(segment_week) OVER (PARTITION BY driver_key ORDER BY week_start). |
| **ops.mv_supply_segments_weekly** | Materialized View | Aggregation of mv_driver_segments_weekly by (week_start, park_id, segment_week): drivers_count, trips_sum, share_of_active, etc. Used as **denominator** for migration_rate (drivers in from_segment previous week). |
| **ops.mv_driver_weekly_stats** | Materialized View | **Upstream** of mv_driver_segments_weekly. One row per (driver_key, week_start). Provides trips_completed_week, park_id. Segment is derived by JOIN to ops.driver_segment_config. |
| **ops.driver_segment_config** | Table | Segment definitions: segment_code, min_trips_week, max_trips_week, ordering, is_active, effective_from, effective_to. Used to assign segment_week and to compute segment_change_type (via ordering). |
| **ops.mv_driver_lifecycle_base** | Materialized View | One row per driver (activation_ts, last_completed_ts). Used for **lifecycle** KPIs (activations, cohorts). Not the source of segment transitions; segment transitions come from mv_driver_segments_weekly. |

**Conclusion:** Migration data originates from **ops.mv_driver_segments_weekly**. No separate “segment_transition” table; transitions are inferred from prev_segment_week → segment_week and segment_change_type.

---

## 2. How Weeks Are Calculated

- **week_start** in **ops.mv_driver_weekly_stats** (and thus in mv_driver_segments_weekly) is:
  - `DATE_TRUNC('week', completion_ts)::date`
  - In PostgreSQL, `DATE_TRUNC('week', ...)` uses **ISO week** (Monday as start of week).
- **week_start** is therefore the **Monday** of the week.
- **Display format** used in the app: `S{ISO_WEEK}-{YEAR}` (e.g. S8-2026), implemented in `supply_definitions.format_iso_week()` (Python) and can be replicated in SQL as:
  - `'S' || EXTRACT(WEEK FROM week_start)::text || '-' || EXTRACT(YEAR FROM week_start)::text`
  - Note: For ISO week, use `TO_CHAR(week_start, 'IYYY')` for ISO year and `EXTRACT(ISOYEAR FROM week_start)` / `EXTRACT(WEEK FROM week_start)` to match Python’s `date.isocalendar()`.

---

## 3. Existing Migration Queries

**Location:** `backend/app/services/supply_service.py` — `get_supply_migration()`, `get_supply_migration_drilldown()`.

**Query logic (get_supply_migration):**

- **FROM:** ops.mv_driver_segments_weekly.
- **Filter:** park_id = %s, week_start BETWEEN from_date AND to_date, and (prev_segment_week IS NOT NULL OR segment_change_type = 'new').
- **Aggregation:** GROUP BY week_start, park_id, prev_segment_week, segment_week, segment_change_type → COUNT(*) AS drivers_migrated.
- **Rate:** LEFT JOIN ops.mv_supply_segments_weekly AS prev ON prev.week_start = m.week_start - 7 AND prev.segment_week = m.from_segment (and park_id) → drivers_in_from_segment_previous_week. migration_rate = drivers_migrated / drivers_in_from_segment_previous_week.
- **Ordering:** ORDER BY m.week_start DESC, m.from_segment, m.to_segment.
- **Response:** List of rows with week_start, park_id, from_segment, to_segment, segment_change_type, drivers_migrated, migration_rate, week_display; plus summary { upgrades, downgrades, drops, revivals, stable }.

**No existing views** named `v_driver_segment_migrations_weekly`, `v_driver_segments_weekly_summary`, or `v_driver_segment_critical_movements`. These will be **new** analytical layers.

---

## 4. Current Ordering Logic

- **Segment ordering** is defined in **ops.driver_segment_config** column **ordering** (numeric). Migrations 065/067/078 define:
  - DORMANT (low), OCCASIONAL, CASUAL, PT, FT, ELITE, LEGEND (high).
- **segment_change_type** in mv_driver_segments_weekly is computed as:
  - **drop:** prev_segment_week IS NOT NULL AND segment_week = 'DORMANT'
  - **downshift:** prev_segment_week IS NOT NULL AND ord < prev_ord
  - **upshift:** prev_segment_week IS NOT NULL AND ord > prev_ord
  - **stable:** prev_segment_week IS NOT NULL AND ord = prev_ord
  - **new:** else (prev_segment_week IS NULL)
- **ord / prev_ord** come from driver_segment_config.ordering (078 uses config; 067 used hardcoded CASE for FT/PT/CASUAL/OCCASIONAL/DORMANT).
- **API mapping** to frontend: upshift → upgrade, downshift → downgrade, drop → drop, new → revival, stable → lateral (same).

---

## 5. Segment Taxonomy

- **Source:** ops.driver_segment_config (segment_code, min_trips_week, max_trips_week, ordering, is_active, effective_from, effective_to).
- **Current taxonomy (078):**
  - DORMANT: 0 (min 0, max implied)
  - OCCASIONAL: 1–4 (or similar band)
  - CASUAL: 5–29
  - PT: 30–59
  - FT: 60–119
  - ELITE: 120–179
  - LEGEND: 180+
- **Ordering (numeric)** is used for transition_type (upgrade/downgrade/same). No view currently exposes a single “segment_rank” function; rank is derived from config ordering in the MV definition.

---

## 6. Driver Lifecycle MVs (Context Only)

- **ops.mv_driver_lifecycle_base:** one row per driver (activation_ts, last_completed_ts).
- **ops.mv_driver_lifecycle_weekly_kpis:** aggregates by week_start (from activation_ts).
- **ops.mv_driver_lifecycle_monthly_kpis:** aggregates by month.

These are **not** the source for segment migration; they are used for activation/churn/cohort analytics. Segment migration is entirely based on **ops.mv_driver_segments_weekly** (and mv_driver_weekly_stats + driver_segment_config upstream).

---

## 7. Summary for New Analytical Layer

- **Base source for new views:** ops.mv_driver_segments_weekly (and optionally ops.mv_supply_segments_weekly for rates).
- **Week format:** week_start = Monday (ISO); week_label = S{ISO_WEEK}-{YEAR}.
- **Transition type:** Map segment_change_type (upshift/downshift/stable/drop/new) to upgrade/downgrade/same (and keep drop/revival for compatibility).
- **Segment rank:** Use driver_segment_config.ordering or equivalent for upgrade/downgrade/same logic in new views.
- **Park:** Current API is park-scoped; new views can include park_id for filtering and consistency with existing queries.

---

*Scan completed. No objects were modified.*
