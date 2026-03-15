"""
Pobla ops.real_drill_dim_fact desde mv_real_lob_day_v2 (granularidad day) y mv_real_lob_week_v3 (granularidad week).
Sustituye la fuente legacy (v_trips_real_canon). Ejecutar tras refresh de la cadena hourly-first.

Uso: cd backend && python -m scripts.populate_real_drill_from_hourly_chain
  --days 120   (ventana días para day)
  --weeks 18   (ventana semanas para week)
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
TABLE = "ops.real_drill_dim_fact"


def run(days: int, weeks: int, timeout_sec: int) -> bool:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    end_day = date.today()
    start_day = end_day - timedelta(days=days)
    end_week = end_day
    start_week = end_week - timedelta(weeks=weeks)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = %s", (str(timeout_sec * 1000),))

        # 1) Borrar filas en la ventana que vamos a repoblar (day y week)
        cur.execute("""
            DELETE FROM ops.real_drill_dim_fact
            WHERE (period_grain = 'day' AND period_start >= %s AND period_start <= %s)
               OR (period_grain = 'week' AND period_start >= %s AND period_start <= %s)
        """, (start_day, end_day, start_week, end_week))
        deleted = cur.rowcount
        logger.info("Eliminadas %s filas de real_drill_dim_fact en ventana", deleted)

        # 2) INSERT day desde day_v2 (breakdown lob, park, service_type)
        cur.execute(f"""
            INSERT INTO ops.real_drill_dim_fact (
                country, period_grain, period_start, segment, breakdown,
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'lob'::text, lob_group, NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
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
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'park'::text, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text),
                   park_id, city,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
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
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'day'::text, trip_date, segment_tag,
                   'service_type'::text, COALESCE(real_tipo_servicio_norm, 'unknown'),
                   NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
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
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'lob'::text, lob_group, NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
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
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'park'::text, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text),
                   park_id, city,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
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
                dimension_key, dimension_id, city, trips, margin_total, margin_per_trip,
                km_avg, b2b_trips, b2b_share, last_trip_ts
            )
            SELECT country, 'week'::text, week_start, segment_tag,
                   'service_type'::text, COALESCE(real_tipo_servicio_norm, 'unknown'),
                   NULL::text, NULL::text,
                   SUM(completed_trips)::bigint,
                   SUM(margin_total), CASE WHEN SUM(completed_trips) > 0 THEN SUM(margin_total) / SUM(completed_trips) ELSE NULL END,
                   CASE WHEN SUM(completed_trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(completed_trips) ELSE NULL END,
                   SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::bigint,
                   CASE WHEN SUM(completed_trips) > 0 THEN SUM(CASE WHEN segment_tag = 'B2B' THEN completed_trips ELSE 0 END)::numeric / SUM(completed_trips) ELSE NULL END,
                   MAX(max_trip_ts)
            FROM {MV_WEEK}
            WHERE week_start >= %s AND week_start <= %s
            GROUP BY country, week_start, segment_tag, real_tipo_servicio_norm
        """, (start_week, end_week))
        ins_svc_week = cur.rowcount

        conn.commit()
        cur.close()

    logger.info("real_drill_dim_fact: day lob=%s park=%s service_type=%s; week lob=%s park=%s service_type=%s",
                ins_lob_day, ins_park_day, ins_svc_day, ins_lob_week, ins_park_week, ins_svc_week)
    return True


def main():
    ap = argparse.ArgumentParser(description="Poblar real_drill_dim_fact desde day_v2 y week_v3")
    ap.add_argument("--days", type=int, default=120, help="Ventana días para period_grain=day")
    ap.add_argument("--weeks", type=int, default=18, help="Ventana semanas para period_grain=week")
    ap.add_argument("--timeout", type=int, default=3600, help="Statement timeout segundos")
    args = ap.parse_args()
    ok = run(days=args.days, weeks=args.weeks, timeout_sec=args.timeout)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
