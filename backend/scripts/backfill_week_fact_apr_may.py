"""Backfill FACT_WEEKLY for April-May 2026 using get_db() pool connection."""
from __future__ import annotations
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

def run():
    months = [('2026-04', '2026-04-01', '2026-04-30'), ('2026-05', '2026-05-01', '2026-05-31')]
    total_inserted = 0

    for label, start, end in months:
        print(f'Processing {label}...')
        t0 = time.perf_counter()

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = 600000")

            cur.execute(
                "DELETE FROM ops.real_business_slice_week_fact WHERE week_start >= %s AND week_start <= %s",
                (start, end)
            )
            d = cur.rowcount
            print(f'  Deleted {d}')

            cur.execute("""
                INSERT INTO ops.real_business_slice_week_fact
                SELECT r.week_start, r.country, r.city, r.business_slice_name,
                       r.fleet_display_name, r.is_subfleet, r.subfleet_name, r.parent_fleet_name,
                       r.trips_completed, r.trips_cancelled, r.active_drivers, r.avg_ticket,
                       r.commission_pct, r.trips_per_driver, r.revenue_yego_net, r.cancel_rate_pct,
                       NOW(), NOW(), r.revenue_yego_final, r.revenue_real_coverage_pct,
                       r.revenue_proxy_trips, r.revenue_real_trips,
                       r.ticket_sum_completed, r.ticket_count_completed, r.total_fare_completed_positive_sum
                FROM (
                    SELECT
                        date_trunc('week', t.trip_date)::date AS week_start,
                        dp.country, dp.city,
                        COALESCE(res.business_slice_name, '__UNMATCHED__') AS business_slice_name,
                        res.fleet_display_name,
                        COALESCE(res.is_subfleet, false) AS is_subfleet,
                        res.subfleet_name, res.parent_fleet_name,
                        COUNT(*) FILTER (WHERE t.completed_flag) AS trips_completed,
                        COUNT(*) FILTER (WHERE t.cancelled_flag) AS trips_cancelled,
                        COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag) AS active_drivers,
                        AVG(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket > 0) AS avg_ticket,
                        NULL::numeric AS commission_pct,
                        CASE WHEN COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag) > 0
                             THEN COUNT(*) FILTER (WHERE t.completed_flag)::numeric
                                  / COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag)
                             ELSE NULL END AS trips_per_driver,
                        SUM(t.revenue_yego_net) FILTER (WHERE t.completed_flag) AS revenue_yego_net,
                        CASE WHEN (COUNT(*) FILTER (WHERE t.completed_flag) + COUNT(*) FILTER (WHERE t.cancelled_flag)) > 0
                             THEN COUNT(*) FILTER (WHERE t.cancelled_flag)::numeric
                                  / (COUNT(*) FILTER (WHERE t.completed_flag) + COUNT(*) FILTER (WHERE t.cancelled_flag))
                             ELSE NULL END AS cancel_rate_pct,
                        SUM(t.revenue_yego_net) FILTER (WHERE t.completed_flag) AS revenue_yego_final,
                        NULL::numeric AS revenue_real_coverage_pct,
                        0::bigint AS revenue_proxy_trips,
                        0::bigint AS revenue_real_trips,
                        SUM(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket > 0) AS ticket_sum_completed,
                        COUNT(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket > 0)::bigint AS ticket_count_completed,
                        NULL::numeric AS total_fare_completed_positive_sum
                    FROM (
                        SELECT
                            fecha_inicio_viaje::date AS trip_date,
                            conductor_id::text AS driver_id,
                            park_id::text AS park_id,
                            lower(trim(condicion)) = 'completado' AS completed_flag,
                            lower(trim(condicion)) LIKE '%%cancel%%' AS cancelled_flag,
                            comision_empresa_asociada::numeric AS revenue_yego_net,
                            precio_yango_pro::numeric AS ticket
                        FROM public.trips_2026
                        WHERE fecha_inicio_viaje::date >= %s AND fecha_inicio_viaje::date <= %s
                    ) t
                    JOIN dim.dim_park dp ON lower(trim(t.park_id)) = lower(trim(dp.park_id::text))
                    LEFT JOIN LATERAL (
                        SELECT
                            rl.business_slice_name, rl.fleet_display_name,
                            rl.is_subfleet, rl.subfleet_name, rl.parent_fleet_name
                        FROM ops.business_slice_mapping_rules rl
                        WHERE rl.is_active
                          AND lower(trim(dp.park_id::text)) = lower(trim(rl.park_id::text))
                        ORDER BY rl.is_subfleet ASC
                        LIMIT 1
                    ) res ON TRUE
                    WHERE t.completed_flag OR t.cancelled_flag
                    GROUP BY 1,2,3,4,5,6,7,8
                ) r
                ON CONFLICT (
                    week_start, COALESCE(country,''::text), COALESCE(city,''::text),
                    business_slice_name, COALESCE(fleet_display_name,''::text),
                    is_subfleet, COALESCE(subfleet_name,''::text), COALESCE(parent_fleet_name,''::text)
                )
                DO UPDATE SET
                    trips_completed = EXCLUDED.trips_completed,
                    trips_cancelled = EXCLUDED.trips_cancelled,
                    active_drivers = EXCLUDED.active_drivers,
                    avg_ticket = EXCLUDED.avg_ticket,
                    trips_per_driver = EXCLUDED.trips_per_driver,
                    revenue_yego_net = EXCLUDED.revenue_yego_net,
                    cancel_rate_pct = EXCLUDED.cancel_rate_pct,
                    refreshed_at = NOW(),
                    loaded_at = NOW()
            """, (start, end))

            n = cur.rowcount
            total_inserted += n
            print(f'  Inserted {n} rows in {time.perf_counter()-t0:.1f}s')

        print(f'Done: {n} rows for {label}')

    print(f'\nTOTAL: {total_inserted} rows across all months')
    return 0 if total_inserted > 0 else 1

if __name__ == '__main__':
    raise SystemExit(run())
