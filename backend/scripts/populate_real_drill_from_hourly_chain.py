"""
Pobla ops.real_drill_dim_fact desde mv_real_lob_day_v2 (day), mv_real_lob_week_v3 (week) y mv_real_lob_month_v3 (month).
Ejecutar tras refresh de la cadena hourly-first.

Uso: cd backend && python -m scripts.populate_real_drill_from_hourly_chain
  --days 120   (ventana días para day)
  --weeks 18   (ventana semanas para week)
  --months 6   (ventana meses para month; drill mensual requiere month con cancelled_trips)
  --timeout 3600
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MV_DAY = "ops.mv_real_lob_day_v2"
MV_WEEK = "ops.mv_real_lob_week_v3"
MV_MONTH = "ops.mv_real_lob_month_v3"
TABLE = "ops.real_drill_dim_fact"


def run(days: int, weeks: int, months: int, timeout_sec: int) -> bool:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    end_day = date.today()
    start_day = end_day - timedelta(days=days)
    end_week = end_day
    start_week = end_week - timedelta(weeks=weeks)
    # Ventana month: desde hace N meses hasta el mes actual (primer día de cada mes)
    end_month = end_day.replace(day=1)
    start_month = end_month
    for _ in range(max(0, months - 1)):
        start_month = (start_month - timedelta(days=1)).replace(day=1)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = %s", (str(timeout_sec * 1000),))

        # 1) Borrar filas en la ventana que vamos a repoblar (day, week, month)
        cur.execute("""
            DELETE FROM ops.real_drill_dim_fact
            WHERE (period_grain = 'day' AND period_start >= %s AND period_start <= %s)
               OR (period_grain = 'week' AND period_start >= %s AND period_start <= %s)
               OR (period_grain = 'month' AND period_start >= %s AND period_start <= %s)
        """, (start_day, end_day, start_week, end_week, start_month, end_month))
        deleted = cur.rowcount
        logger.info("Eliminadas %s filas de real_drill_dim_fact en ventana (day/week/month)", deleted)

        # 2) INSERT day desde day_v2 (breakdown lob, park, service_type)
        # Margen en positivo (semántica negocio): ABS(SUM(margin_total)); cancelaciones desde day_v2
        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'lob'::text, lob_group, NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date <= %s
            GROUP BY country, trip_date, segment_tag, lob_group
        """, (start_day, end_day))
        ins_lob_day = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'park'::text, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text),
                   park_id, city,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date <= %s
            GROUP BY country, trip_date, segment_tag, city, park_id, park_name
        """, (start_day, end_day))
        ins_park_day = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'service_type'::text, COALESCE(real_tipo_servicio_norm, 'unknown'),
                   NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date <= %s
            GROUP BY country, trip_date, segment_tag, real_tipo_servicio_norm
        """, (start_day, end_day))
        ins_svc_day = cur.rowcount

        # 3) INSERT week desde week_v3 (lob, park, service_type)
        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'lob'::text, lob_group, NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_WEEK}
            WHERE week_start >= %s AND week_start <= %s
            GROUP BY country, week_start, segment_tag, lob_group
        """, (start_week, end_week))
        ins_lob_week = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'park'::text, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text),
                   park_id, city,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_WEEK}
            WHERE week_start >= %s AND week_start <= %s
            GROUP BY country, week_start, segment_tag, city, park_id, park_name
        """, (start_week, end_week))
        ins_park_week = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'service_type'::text, COALESCE(real_tipo_servicio_norm, 'unknown'),
                   NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_WEEK}
            WHERE week_start >= %s AND week_start <= %s
            GROUP BY country, week_start, segment_tag, real_tipo_servicio_norm
        """, (start_week, end_week))
        ins_svc_week = cur.rowcount

        # 4) INSERT month desde month_v3 (lob, park, service_type) — necesario para drill mensual con cancelaciones
        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'month'::text, month_start, segment_tag,
                   'lob'::text, lob_group, NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_MONTH}
            WHERE month_start >= %s AND month_start <= %s
            GROUP BY country, month_start, segment_tag, lob_group
        """, (start_month, end_month))
        ins_lob_month = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'month'::text, month_start, segment_tag,
                   'park'::text, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text),
                   park_id, city,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_MONTH}
            WHERE month_start >= %s AND month_start <= %s
            GROUP BY country, month_start, segment_tag, city, park_id, park_name
        """, (start_month, end_month))
        ins_park_month = cur.rowcount

        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, cancelled_trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'month'::text, month_start, segment_tag,
                   'service_type'::text, COALESCE(real_tipo_servicio_norm, 'unknown'),
                   NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(cancelled_trips)::bigint,
                   ABS(SUM(margin_total)), CASE WHEN SUM(completed_trips) > 0 THEN ABS(SUM(margin_total)) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_MONTH}
            WHERE month_start >= %s AND month_start <= %s
            GROUP BY country, month_start, segment_tag, real_tipo_servicio_norm
        """, (start_month, end_month))
        ins_svc_month = cur.rowcount

        conn.commit()
        cur.close()
    # Fin del bloque: INSERTs ya guardados. El UPDATE de segmentación se hace en otra conexión
    # para que, si el servidor cierra por timeout/memoria, no se pierdan los INSERTs.

    logger.info("real_drill_dim_fact: day lob=%s park=%s svc=%s; week lob=%s park=%s svc=%s; month lob=%s park=%s svc=%s",
                ins_lob_day, ins_park_day, ins_svc_day, ins_lob_week, ins_park_week, ins_svc_week,
                ins_lob_month, ins_park_month, ins_svc_month)

    # 5) Actualizar segmentación en conexión aparte (vista pesada; si falla no perdemos los INSERTs)
    seg_timeout_sec = min(900, max(120, timeout_sec // 4))  # entre 2 y 15 min
    try:
        with get_db() as conn2:
            cur2 = conn2.cursor(cursor_factory=RealDictCursor)
            cur2.execute("SET statement_timeout = %s", (str(seg_timeout_sec * 1000),))
            cur2.execute("""
                UPDATE ops.real_drill_dim_fact d
                SET
                    active_drivers = a.active_drivers,
                    cancel_only_drivers = a.cancel_only_drivers,
                    activity_drivers = a.activity_drivers,
                    cancel_only_pct = a.cancel_only_pct
                FROM ops.v_real_driver_segment_agg a
                WHERE d.country = a.country
                  AND d.period_grain = a.period_grain
                  AND d.period_start = a.period_start
                  AND d.segment = a.segment_tag
                  AND d.breakdown = a.breakdown
                  AND COALESCE(TRIM(d.dimension_key), '') = COALESCE(TRIM(a.dimension_key), '')
                  AND COALESCE(TRIM(d.dimension_id), '') = COALESCE(TRIM(a.dimension_id), '')
                  AND COALESCE(TRIM(d.city), '') = COALESCE(TRIM(a.city), '')
            """)
            updated_seg = cur2.rowcount
            logger.info("real_drill_dim_fact: segmentación conductores actualizada en %s filas (timeout %ss)", updated_seg, seg_timeout_sec)
            cur2.close()
    except Exception as e:
        logger.warning(
            "Segmentación conductores (v_real_driver_segment_agg) no aplicada: %s. "
            "Los datos de viajes/cancelaciones ya están guardados. Puedes volver a ejecutar solo el UPDATE más tarde o aumentar timeout en el servidor.",
            e
        )

    return True


def main():
    ap = argparse.ArgumentParser(description="Poblar real_drill_dim_fact desde day_v2, week_v3 y month_v3")
    ap.add_argument("--days", type=int, default=120, help="Ventana días para period_grain=day")
    ap.add_argument("--weeks", type=int, default=18, help="Ventana semanas para period_grain=week")
    ap.add_argument("--months", type=int, default=6, help="Ventana meses para period_grain=month (drill mensual)")
    ap.add_argument("--timeout", type=int, default=3600, help="Statement timeout segundos")
    args = ap.parse_args()
    ok = run(days=args.days, weeks=args.weeks, months=args.months, timeout_sec=args.timeout)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
