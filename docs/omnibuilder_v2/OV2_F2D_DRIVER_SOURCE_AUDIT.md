# OV2-F.2D — DRIVER SOURCE AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** AUDIT COMPLETE

---

## 1. AVAILABLE DRIVER DATA

| Source | driver_id | trip_date | park_id | business_slice | completed_flag | trips count |
|--------|-----------|-----------|---------|----------------|----------------|-------------|
| `public.trips_2025` | `conductor_id` | `fecha_inicio_viaje` | `park_id` | ❌ (raw) | `condicion='Completado'` | 1 per trip |
| `public.trips_2026` | `conductor_id` | `fecha_inicio_viaje` | `park_id` | ❌ (raw) | `condicion='Completado'` | 1 per trip |
| `ops.v_real_trips_enriched_base` | `driver_id` | `trip_date` | `park_id` | ❌ | `completed_flag` | 1 per trip |
| `ops.v_real_trips_business_slice_resolved` | `driver_id` | `trip_date` | `park_id` | ✅ `business_slice_name` | `completed_flag` | 1 per trip |
| `ops.driver_daily_activity_fact` | `driver_id` | `activity_date` | `park_id` | ❌ | ❌ (aggregated) | SUM(completed_trips) |

## 2. BEST SOURCE FOR BRIDGE

**`ops.v_real_trips_business_slice_resolved`**

This view already has:
- `driver_id` per trip
- `trip_date` per trip
- `business_slice_name` (resolved via mapping rules)
- `completed_flag` (boolean)
- `park_id`, `country`, `city`

Bridge build query:
```sql
SELECT trip_date::date AS activity_date, country, city, park_id,
       business_slice_name, driver_id,
       COUNT(*) FILTER (WHERE completed_flag) AS completed_trips,
       COUNT(*) AS total_trips
FROM ops.v_real_trips_business_slice_resolved
WHERE country = 'peru' AND city = 'lima'
  AND trip_date BETWEEN '2026-04-01' AND '2026-06-06'
  AND driver_id IS NOT NULL AND business_slice_name IS NOT NULL
GROUP BY 1,2,3,4,5,6
```

## 3. MISSING FIELDS

| Field | Available? | Source |
|-------|-----------|--------|
| driver_id | ✅ | `conductor_id` → `driver_id` |
| trip_date | ✅ | `fecha_inicio_viaje` |
| park_id | ✅ | Raw trips |
| country | ✅ | `dim.dim_park` |
| city | ✅ | `dim.dim_park` |
| business_slice_name | ✅ | Resolved view |
| completed_flag | ✅ | `condicion = 'Completado'` |
| cancelled_flag | ✅ | `condicion = 'Cancelado'` |
| timestamp | ✅ | `fecha_inicio_viaje` |

**No missing fields.** Can build complete driver-day-slice bridge from resolved view.

---

*End of Source Audit*
