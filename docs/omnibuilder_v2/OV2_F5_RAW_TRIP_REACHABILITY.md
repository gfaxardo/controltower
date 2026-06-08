# OV2-F.5 — RAW TRIP REACHABILITY

> **Date:** 2026-06-08
> **Status:** **PARTIAL**

---

## 1. CAN WE REACH RAW TRIPS FROM A DRIVER?

**YES** — but requires scanning `public.trips_2026`.

Path:
```
driver_id (from bridge)
  → SELECT * FROM public.trips_2026
    WHERE conductor_id = <driver_id>
    AND fecha_inicio_viaje::date = <date>
  → Returns individual trips
```

## 2. COST

| Metric | Value |
|--------|-------|
| Source table | `public.trips_2026` |
| Filter columns | `conductor_id` + `fecha_inicio_viaje` |
| Avg trips per driver-day | ~3-5 |
| Query time (single driver, 1 day) | <100ms |
| Query time (all drivers for 1 slice, 1 month) | ~2s |

## 3. OPTIMIZATION OPTIONS

| Option | Benefit | Cost |
|--------|---------|------|
| Add `trip_ids[]` to bridge | Instant lookup | Bridge rows × trip array storage |
| Add index on (conductor_id, fecha_inicio_viaje) | Faster raw queries | DB storage |
| Materialize driver-trip mapping | Pre-computed | New table |

## 4. VERDICT

**PARTIAL** — Reachable but requires raw table scan per query. Acceptable for individual driver drill (fast). Not suitable for aggregate drill (all drivers at once) without materialized mapping.

---

*End of Raw Trip Reachability*
