# OV2-F.2D — DRIVER DAY SLICE BRIDGE CONTRACT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** CONTRACT DEFINED

---

## 1. TABLE: ops.driver_day_slice_fact

| Column | Type | Description |
|--------|------|-------------|
| `id` | BIGSERIAL PK | Surrogate key |
| `activity_date` | DATE NOT NULL | Day of driver activity |
| `country` | TEXT NOT NULL | Normalized country (from dim_park) |
| `city` | TEXT NOT NULL | Normalized city |
| `park_id` | TEXT NOT NULL | Park identifier |
| `business_slice_name` | TEXT NOT NULL | Resolved slice name |
| `driver_id` | TEXT NOT NULL | Driver identifier |
| `completed_trips` | INTEGER DEFAULT 0 | Trips completed |
| `cancelled_trips` | INTEGER DEFAULT 0 | Trips cancelled |
| `total_trips` | INTEGER DEFAULT 0 | All trips |
| `completed_flag` | BOOLEAN DEFAULT false | Has completed trips |
| `cancel_only_flag` | BOOLEAN DEFAULT false | Has trips but 0 completed |
| `empty_supply_flag` | BOOLEAN DEFAULT false | No trips completed (supply without production) |
| `first_completed_at` | TIMESTAMPTZ | Earliest completed trip |
| `last_completed_at` | TIMESTAMPTZ | Latest completed trip |
| `source_system` | TEXT DEFAULT 'CT_TRIPS_2026' | Data origin |
| `refreshed_at` | TIMESTAMPTZ DEFAULT now() | When this row was computed |
| `confidence` | TEXT DEFAULT 'HIGH' | HIGH/MEDIUM/LOW |
| `warning_codes` | TEXT[] DEFAULT '{}' | Array of warning codes |

## 2. GRAIN

**Unique key:** `(activity_date, country, city, park_id, business_slice_name, driver_id)`

One row per driver, per day, per business slice, per park. A driver who drives for multiple slices in a day gets multiple rows.

## 3. INDEXES

```sql
CREATE UNIQUE INDEX ix_dds_date_country_city_park_slice_driver
  ON ops.driver_day_slice_fact (activity_date, country, city, park_id, business_slice_name, driver_id);

CREATE INDEX ix_dds_activity_date ON ops.driver_day_slice_fact (activity_date);
CREATE INDEX ix_dds_country_city ON ops.driver_day_slice_fact (country, city);
CREATE INDEX ix_dds_business_slice ON ops.driver_day_slice_fact (business_slice_name);
CREATE INDEX ix_dds_driver_id ON ops.driver_day_slice_fact (driver_id, activity_date);
CREATE INDEX ix_dds_park_id ON ops.driver_day_slice_fact (park_id, activity_date);
```

## 4. USAGE FOR WEEK FACT

```sql
-- Exact weekly active drivers (no upper bound)
SELECT
    date_trunc('week', activity_date)::date AS week_start,
    business_slice_name,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0) AS active_drivers,
    COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips = 0 AND total_trips > 0) AS empty_supply_drivers,
    SUM(completed_trips) AS trips_completed
FROM ops.driver_day_slice_fact
WHERE country = 'peru' AND city = 'lima'
  AND activity_date BETWEEN '2026-04-01' AND '2026-06-06'
GROUP BY week_start, business_slice_name
```

## 5. BUILD STRATEGY

**Initial backfill:** Query `ops.v_real_trips_business_slice_resolved` once per 7-day batch, aggregate to driver-day-slice, INSERT into bridge.

**Incremental daily:** After initial build, only insert rows for new dates (D-1). No re-scanning of resolved view for past dates.

## 6. CLOSED PERIOD

- Rows with `activity_date < D-1` are IMMUTABLE (closed period)
- Backfill explicitly requires `--allow-backfill` flag
- Daily refresh only touches D-1 and D (today)

---

*End of Bridge Contract*
