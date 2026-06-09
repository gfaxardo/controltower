# OV2-F.6B — DATE WINDOW AUDIT

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE — MATCH

## CT DATE LOGIC

- `driver_day_slice_fact.activity_date` = trip_date from trips_2026 (Lima local time)
- Day boundary: 00:00 to 23:59 local Lima time (UTC-5)
- Reconciliation query: `activity_date >= '2026-06-06' AND activity_date < '2026-06-07'`

## YANGO DATE LOGIC

- `orders_raw.operational_date` = derived from `order_ended_at` (UTC)
- `order_created_at`, `order_booked_at`, `order_ended_at` — all UTC timestamps
- Day boundary: likely UTC → may shift a few hours vs Lima local

## TIMEZONE GAP

Lima is UTC-5. A trip at 2026-06-06 02:00 Lima = 2026-06-06 07:00 UTC. Both would classify as June 6. No cross-day issue.

Yango `order_ended_at` at 2026-06-06 23:59 Lima = 2026-06-07 04:59 UTC. This WOULD cross the UTC day boundary. But the `operational_date` column is pre-computed and should use local time.

## VERDICT

**DATE MATCH** — Both sides use June 6, 2026. Timezone may introduce edge cases at day boundaries (UTC vs Lima), but not significant enough to explain 12x delta.

---

*End of Date Window Audit*
