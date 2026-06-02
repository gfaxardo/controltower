"""
DEPRECATED — CF-H1J.7: este script produce week_fact incompleta.

PROBLEMAS CONOCIDOS:
- active_drivers = NULL (no computa COUNT DISTINCT desde enriched)
- date_trunc('week') no respeta ISO weeks (Lunes→Domingo)
- Puede dejar week_fact con datos parciales si se ejecuta sin dia_fact completo

Para backfill productivo usa el incremental:
  python -m scripts.refresh_omniview_real_slice_incremental --grain week

Para bypass de emergencia (solo backfill historico autorizado):
  python -m scripts.backfill_week_from_day_fact --allow-legacy-weekly-dangerous
"""
from __future__ import annotations
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

LEGACY_BLOCK_MSG = (
    "NO-GO: backfill_week_from_day_fact.py esta DEPRECATED.\n"
    "Este script produce week_fact incompleta:\n"
    "  - active_drivers queda en NULL\n"
    "  - No usa ISO weeks correctas (usa date_trunc)\n"
    "  - Puede generar datos parciales\n"
    "Usa el incremental refresh:\n"
    "  python -m scripts.refresh_omniview_real_slice_incremental --grain week\n"
    "Si necesitas backfill historico controlado, usa:\n"
    "  --allow-legacy-weekly-dangerous"
)

if __name__ == "__main__":
    if "--allow-legacy-weekly-dangerous" not in sys.argv:
        print(LEGACY_BLOCK_MSG, file=sys.stderr)
        raise SystemExit(1)

    print(
        "WARNING: Ejecutando legacy backfill_week_from_day_fact con "
        "--allow-legacy-weekly-dangerous. Esto NO debe usarse para refresh productivo.",
        file=sys.stderr,
    )

    from app.db.connection import get_db

    SQL = """
    INSERT INTO ops.real_business_slice_week_fact
    SELECT
        date_trunc('week', r.trip_date)::date AS week_start,
        r.country, r.city, r.business_slice_name,
        r.fleet_display_name,
        COALESCE(r.is_subfleet, false),
        r.subfleet_name, r.parent_fleet_name,
        SUM(r.trips_completed)::bigint,
        SUM(r.trips_cancelled)::bigint,
        NULL::bigint AS active_drivers,
        CASE WHEN SUM(r.trip_count_filtered) > 0
             THEN SUM(r.ticket_sum) / SUM(r.trip_count_filtered) ELSE NULL END AS avg_ticket,
        NULL::numeric AS commission_pct,
        CASE WHEN SUM(r.trips_completed) > 0 AND NULLIF(SUM(r.driver_days), 0) IS NOT NULL AND SUM(r.driver_days) > 0
             THEN SUM(r.trips_completed)::numeric / SUM(r.driver_days) ELSE NULL END AS trips_per_driver,
        SUM(r.revenue_sum) AS revenue_yego_net,
        CASE WHEN (SUM(r.trips_completed) + SUM(r.trips_cancelled)) > 0
             THEN SUM(r.trips_cancelled)::numeric / (SUM(r.trips_completed) + SUM(r.trips_cancelled))
             ELSE NULL END AS cancel_rate_pct,
        NOW(), NOW(),
        SUM(r.revenue_sum) AS revenue_yego_final,
        NULL::numeric, 0::bigint, 0::bigint,
        SUM(r.ticket_sum) AS ticket_sum_completed,
        SUM(r.trip_count_filtered)::bigint AS ticket_count_completed,
        NULL::numeric
    FROM (
        SELECT
            trip_date, country, city, business_slice_name,
            fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name,
            trips_completed, trips_cancelled,
            active_drivers AS driver_days,
            avg_ticket * trips_completed AS ticket_sum,
            CASE WHEN avg_ticket IS NOT NULL THEN trips_completed ELSE 0 END AS trip_count_filtered,
            revenue_yego_net AS revenue_sum
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= %s AND trip_date <= %s
    ) r
    GROUP BY 1,2,3,4,5,6,7,8
    ON CONFLICT (
        week_start, COALESCE(country,''::text), COALESCE(city,''::text),
        business_slice_name, COALESCE(fleet_display_name,''::text),
        is_subfleet, COALESCE(subfleet_name,''::text), COALESCE(parent_fleet_name,''::text)
    )
    DO UPDATE SET
        trips_completed = EXCLUDED.trips_completed,
        trips_cancelled = EXCLUDED.trips_cancelled,
        avg_ticket = EXCLUDED.avg_ticket,
        trips_per_driver = EXCLUDED.trips_per_driver,
        revenue_yego_net = EXCLUDED.revenue_yego_net,
        cancel_rate_pct = EXCLUDED.cancel_rate_pct,
        refreshed_at = NOW(),
        loaded_at = NOW()
    """

    def run():
        months = [('2026-04', '2026-04-01', '2026-04-30'), ('2026-05', '2026-05-01', '2026-05-31')]
        total = 0
        for label, start, end in months:
            print(f'Processing {label}...')
            t0 = time.perf_counter()
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SET statement_timeout = 600000")
                cur.execute("DELETE FROM ops.real_business_slice_week_fact WHERE week_start >= %s AND week_start <= %s", (start, end))
                d = cur.rowcount
                cur.execute(SQL, (start, end))
                n = cur.rowcount
                total += n
                print(f'  Deleted {d}, Inserted {n} in {time.perf_counter()-t0:.1f}s')
        print(f'\nTOTAL: {total} rows')
        return 0 if total > 0 else 1

    raise SystemExit(run())
