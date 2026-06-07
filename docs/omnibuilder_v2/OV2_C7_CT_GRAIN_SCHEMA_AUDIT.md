# OV2-C.7 — CT GRAIN SCHEMA AUDIT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / CT Grain Expansion
> **Status:** AUDIT COMPLETE

---

## 1. CT GRAIN TABLES

| Grain | Table | Date Key | Rows (lima/peru) | Date Range |
|-------|-------|----------|-------------------|------------|
| hour | `ops.real_business_slice_hour_fact` | `hour_start` | **0** | N/A |
| day | `ops.real_business_slice_day_fact` | `trip_date` | ~6/day | 2025-01 to 2026-06 |
| week | `ops.real_business_slice_week_fact` | `week_start` | 367 | 2025-02 to 2026-04 |
| month | `ops.real_business_slice_month_fact` | `month` | 92 | 2025-02 to 2026-06 |

---

## 2. COMMON COLUMNS (available in all grain tables)

| Column | Type | Description |
|--------|------|-------------|
| `trips_completed` | bigint | Completed trips |
| `revenue_yego_final` | numeric | Revenue (final, with COALESCE fallback) |
| `active_drivers` | bigint | Active drivers count |
| `business_slice_name` | text | Slice name (row identifier) |
| `country` | text | Country filter |
| `city` | text | City filter |

### Columns that vary by table

| Column | day | week | month | hour |
|--------|-----|------|-------|------|
| `trips_cancelled` | YES | YES | YES | YES |
| `avg_ticket` | YES | YES | YES | ? |
| `commission_pct` | YES | YES | YES | ? |
| `trips_per_driver` | YES | YES | ? | ? |
| `cancel_rate_pct` | YES | YES | NO | ? |
| `completados_por_hora` | NO | NO | YES | ? |
| `cancelados_por_hora` | NO | NO | YES | ? |
| `total_fare_completed_positive_sum` | NO | NO | NO | YES |

**Repository uses only guaranteed columns:** `trips_completed`, `revenue_yego_final`, `active_drivers`, `business_slice_name`. This ensures all grains work without column-not-found errors.

---

## 3. GRAIN SUPPORT STATUS

| Grain | Matrix API | Data Available | Notes |
|-------|-----------|---------------|-------|
| hour | NOT_SUPPORTED | NO (0 rows) | Table exists but empty for lima/peru. Schema ready when data populates. |
| day | **SUPPORTED** | YES | Active. 6 slices per day. |
| week | **SUPPORTED** | YES | 367 rows. Date key: `week_start` (Monday). |
| month | **SUPPORTED** | YES | 92 rows. Date key: `month` (first day of month). |

---

## 4. SOURCE TABLE BY GRAIN

| Grain | source_table value |
|-------|-------------------|
| hour | `ops.real_business_slice_hour_fact` |
| day | `ops.real_business_slice_day_fact` |
| week | `ops.real_business_slice_week_fact` |
| month | `ops.real_business_slice_month_fact` |

---

## 5. TEST RESULTS

| Grain | Date Range | Rows × Cols | Cells |
|-------|-----------|-------------|-------|
| day | 2026-06-04 to 2026-06-04 | 6 × 1 | 6 |
| week | 2026-03-01 to 2026-05-31 | 6 × 8 | 48 |
| month | 2026-01-01 to 2026-06-01 | 6 × 6 | 36 |
| hour | 2026-06-04 to 2026-06-04 | 0 × 1 | 0 (NO_DATA) |

---

## 6. YANGO GRAINS (unchanged)

| Grain | Status |
|-------|--------|
| day | SUPPORTED |
| week | NOT_SUPPORTED |
| month | NOT_SUPPORTED |
| hour | NOT_SUPPORTED |

---

## 7. LIMITATIONS

| Limitation | Impact |
|-----------|--------|
| CT hour has 0 rows | Table created but no data ingested for lima/peru. May have data for other cities. |
| Month table has different columns | Repository uses only common columns (safe) |
| Week data ends April 2026 | Recent weeks may not be populated. Depends on refresh schedule. |
| No plan data in matrix | Plan vs Real is separate section, not in /matrix endpoint |
