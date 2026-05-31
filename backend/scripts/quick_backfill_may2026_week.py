"""
Script liviano: poblar FACT_WEEKLY para May 2026 desde public.trips_2026.
Similar al quick_backfill_may2026 pero agregando por week_start.
"""
from __future__ import annotations
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db_audit

SQL_WEEK_INSERT = """
INSERT INTO ops.real_business_slice_week_fact
SELECT
    r.week_start,
    r.country,
    r.city,
    r.business_slice_name,
    r.fleet_display_name,
    r.is_subfleet,
    r.subfleet_name,
    r.parent_fleet_name,
    r.trips_completed,
    r.trips_cancelled,
    r.active_drivers,
    r.avg_ticket,
    r.commission_pct,
    r.trips_per_driver,
    r.revenue_yego_net,
    r.cancel_rate_pct,
    NOW() AS refreshed_at,
    NOW() AS loaded_at,
    r.revenue_yego_final,
    r.revenue_real_coverage_pct,
    r.revenue_proxy_trips,
    r.revenue_real_trips,
    r.ticket_sum_completed,
    r.ticket_count_completed,
    r.total_fare_completed_positive_sum
FROM (
    SELECT
        date_trunc('week', t.trip_date)::date AS week_start,
        dp.country,
        dp.city,
        res.business_slice_name,
        res.fleet_display_name,
        res.is_subfleet,
        res.subfleet_name,
        res.parent_fleet_name,
        COUNT(*) FILTER (WHERE t.completed_flag) AS trips_completed,
        COUNT(*) FILTER (WHERE t.cancelled_flag) AS trips_cancelled,
        COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag) AS active_drivers,
        AVG(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket IS NOT NULL) AS avg_ticket,
        CASE
            WHEN SUM(t.total_fare) FILTER (WHERE t.completed_flag AND t.total_fare IS NOT NULL AND t.total_fare > 0) > 0
            THEN SUM(t.revenue_yego_net) FILTER (WHERE t.completed_flag AND t.total_fare IS NOT NULL AND t.total_fare > 0)
                 / SUM(t.total_fare) FILTER (WHERE t.completed_flag AND t.total_fare IS NOT NULL AND t.total_fare > 0)
            ELSE NULL
        END AS commission_pct,
        CASE
            WHEN COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag) > 0
            THEN COUNT(*) FILTER (WHERE t.completed_flag)::numeric
                 / COUNT(DISTINCT t.driver_id) FILTER (WHERE t.completed_flag)
            ELSE NULL
        END AS trips_per_driver,
        SUM(t.revenue_yego_net) FILTER (WHERE t.completed_flag) AS revenue_yego_net,
        CASE
            WHEN (COUNT(*) FILTER (WHERE t.completed_flag) + COUNT(*) FILTER (WHERE t.cancelled_flag)) > 0
            THEN COUNT(*) FILTER (WHERE t.cancelled_flag)::numeric
                 / (COUNT(*) FILTER (WHERE t.completed_flag) + COUNT(*) FILTER (WHERE t.cancelled_flag))
            ELSE NULL
        END AS cancel_rate_pct,
        SUM(ABS(t.revenue_yego_net)) FILTER (WHERE t.completed_flag AND t.revenue_yego_net IS NOT NULL) AS revenue_yego_final,
        CASE
            WHEN COUNT(*) FILTER (WHERE t.completed_flag) > 0
            THEN ROUND(100.0 * COUNT(*) FILTER (WHERE t.completed_flag AND t.revenue_yego_net IS NOT NULL) / COUNT(*) FILTER (WHERE t.completed_flag), 2)
            ELSE NULL
        END AS revenue_real_coverage_pct,
        COUNT(*) FILTER (WHERE t.completed_flag AND t.revenue_yego_net IS NULL)::bigint AS revenue_proxy_trips,
        COUNT(*) FILTER (WHERE t.completed_flag AND t.revenue_yego_net IS NOT NULL)::bigint AS revenue_real_trips,
        SUM(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket IS NOT NULL) AS ticket_sum_completed,
        COUNT(t.ticket) FILTER (WHERE t.completed_flag AND t.ticket IS NOT NULL)::bigint AS ticket_count_completed,
        SUM(t.total_fare) FILTER (WHERE t.completed_flag AND t.total_fare IS NOT NULL AND t.total_fare > 0) AS total_fare_completed_positive_sum
    FROM (
        SELECT
            fecha_inicio_viaje::date AS trip_date,
            conductor_id::text AS driver_id,
            park_id::text AS park_id,
            CASE WHEN lower(trim(condicion)) = 'completado' THEN TRUE ELSE FALSE END AS completed_flag,
            CASE WHEN lower(trim(condicion)) LIKE '%cancel%' THEN TRUE ELSE FALSE END AS cancelled_flag,
            comision_empresa_asociada::numeric AS revenue_yego_net,
            precio_yango_pro::numeric AS ticket,
            COALESCE(efectivo::numeric,0)+COALESCE(tarjeta::numeric,0)+COALESCE(pago_corporativo::numeric,0) AS total_fare
        FROM public.trips_2026
        WHERE fecha_inicio_viaje::date >= '2026-05-01' AND fecha_inicio_viaje::date <= '2026-05-31'
    ) t
    JOIN dim.dim_park dp ON lower(trim(t.park_id)) = lower(trim(dp.park_id::text))
    LEFT JOIN public.drivers d ON t.driver_id = d.driver_id::text
    INNER JOIN LATERAL (
        WITH rules AS (SELECT * FROM ops.business_slice_mapping_rules WHERE is_active),
        m AS (
            SELECT rl.business_slice_name, rl.fleet_display_name, rl.is_subfleet, rl.subfleet_name, rl.parent_fleet_name, rl.rule_type,
                CASE rl.rule_type WHEN 'park_plus_works_terms' THEN 3 WHEN 'park_plus_tipo_servicio' THEN 2 WHEN 'park_only' THEN 1 ELSE 0 END AS spec_score
            FROM rules rl
            WHERE lower(trim(dp.park_id::text)) = lower(trim(rl.park_id::text))
              AND ((rl.rule_type='park_only') OR (rl.rule_type='park_plus_tipo_servicio' AND rl.tipo_servicio_values IS NOT NULL)
                   OR (rl.rule_type='park_plus_works_terms' AND rl.works_terms_values IS NOT NULL
                       AND EXISTS (SELECT 1 FROM unnest(rl.works_terms_values) wv WHERE ops.normalized_works_terms(d.works_terms::text) = ops.normalized_works_terms(wv::text))))
        ),
        best AS (SELECT DISTINCT ON (spec_score) * FROM m ORDER BY spec_score DESC, is_subfleet ASC, COALESCE(parent_fleet_name,'') ASC)
        SELECT business_slice_name, fleet_display_name, is_subfleet, subfleet_name, parent_fleet_name FROM best LIMIT 1
    ) res ON TRUE
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
    commission_pct = EXCLUDED.commission_pct,
    trips_per_driver = EXCLUDED.trips_per_driver,
    revenue_yego_net = EXCLUDED.revenue_yego_net,
    cancel_rate_pct = EXCLUDED.cancel_rate_pct,
    refreshed_at = EXCLUDED.refreshed_at, loaded_at = EXCLUDED.loaded_at,
    revenue_yego_final = EXCLUDED.revenue_yego_final,
    revenue_real_coverage_pct = EXCLUDED.revenue_real_coverage_pct,
    revenue_proxy_trips = EXCLUDED.revenue_proxy_trips,
    revenue_real_trips = EXCLUDED.revenue_real_trips,
    ticket_sum_completed = EXCLUDED.ticket_sum_completed,
    ticket_count_completed = EXCLUDED.ticket_count_completed,
    total_fare_completed_positive_sum = EXCLUDED.total_fare_completed_positive_sum
"""

def main():
    print("Iniciando carga directa de FACT_WEEKLY para May 2026...")
    t0 = time.perf_counter()
    with get_db_audit(timeout_ms=3_600_000) as conn:
        cur = conn.cursor()
        t_pre = time.perf_counter()
        cur.execute("DELETE FROM ops.real_business_slice_week_fact WHERE week_start >= '2026-05-01' AND week_start <= '2026-05-31'")
        deleted = cur.rowcount
        conn.commit()
        print(f"  {deleted} filas eliminadas en {time.perf_counter()-t_pre:.1f}s")
        t_ins = time.perf_counter()
        cur.execute(SQL_WEEK_INSERT)
        inserted = cur.rowcount
        conn.commit()
        print(f"  {inserted} filas insertadas en {time.perf_counter()-t_ins:.1f}s")
        print(f"  TOTAL: {time.perf_counter()-t0:.1f}s")
        cur.close()
    print(f"\nOK. FACT_WEEKLY ahora tiene {inserted} filas para May 2026.")
    return 0 if inserted > 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
