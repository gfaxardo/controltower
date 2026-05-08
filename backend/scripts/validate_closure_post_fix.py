"""
Validación post-fix incidente freshness (Fase 1.3): solo lectura BD + salida JSON-friendly.
Uso: cd backend && python -m scripts.validate_closure_post_fix
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def main() -> None:
    init_db_pool()
    out: dict = {}

    with get_db() as conn:
        c = conn.cursor(cursor_factory=RealDictCursor)

        checks = [
            "SELECT COUNT(*) AS n FROM ops.real_rollup_day_fact",
            "SELECT COUNT(*) AS n FROM ops.mv_real_rollup_day",
            "SELECT COUNT(*) AS n FROM ops.v_real_lob_coverage",
            "SELECT COUNT(*) AS n FROM ops.v_real_data_coverage",
            "SELECT COUNT(*) AS n FROM ops.v_revenue_quality_daily_summary",
        ]
        out["views_rowcounts"] = {}
        for sql in checks:
            c.execute(sql)
            k = sql.split("FROM ")[1].split()[0].rstrip(",")
            out["views_rowcounts"][k] = c.fetchone()["n"]

        c.execute(
            """
            SELECT LEFT(definition, 120) AS snip
            FROM pg_matviews
            WHERE schemaname = 'ops' AND matviewname = 'mv_real_lob_hour_v2'
            """
        )
        out["mv_hour_v2_source_snip"] = c.fetchone()["snip"]

        c.execute(
            """
            SELECT dataset_name, source_max_date::text, derived_max_date::text, status, checked_at::text,
                   LEFT(COALESCE(alert_reason,''), 200) AS alert_reason
            FROM (
              SELECT DISTINCT ON (dataset_name)
                dataset_name, source_max_date, derived_max_date, status, checked_at, alert_reason
              FROM ops.data_freshness_audit
              WHERE dataset_name IN (
                'real_operational', 'real_lob', 'real_lob_drill',
                'driver_lifecycle', 'driver_lifecycle_weekly', 'supply_weekly',
                'trips_base', 'trips_2026'
              )
              ORDER BY dataset_name, checked_at DESC
            ) t
            ORDER BY dataset_name
            """
        )
        out["data_freshness_audit_latest"] = [dict(r) for r in c.fetchall()]

        c.execute(
            """
            SELECT
              (SELECT MAX(trip_date)::date FROM ops.mv_real_lob_day_v2) AS mv_day_v2_max,
              (SELECT MAX(week_start)::date FROM ops.mv_real_lob_week_v3) AS mv_week_v3_max,
              (SELECT MAX(month_start)::date FROM ops.mv_real_lob_month_v3) AS mv_month_v3_max,
              (SELECT MAX(fecha_inicio_viaje)::date FROM ops.v_real_trip_fact_v2
                 WHERE fecha_inicio_viaje >= current_date - 200) AS fact_v2_max,
              (SELECT MAX(trip_day)::date FROM ops.real_rollup_day_fact) AS rollup_day_max,
              (SELECT MAX(last_completed_ts)::date FROM ops.mv_driver_lifecycle_base
                 WHERE last_completed_ts >= current_date - 200) AS driver_lifecycle_max,
              (SELECT MAX(week_start)::date FROM ops.mv_driver_weekly_stats
                 WHERE week_start >= current_date - 200) AS driver_weekly_mv_max,
              (SELECT MAX(week_start)::date FROM ops.mv_supply_segments_weekly
                 WHERE week_start >= current_date - 200) AS supply_weekly_mv_max
            """
        )
        row = dict(c.fetchone())
        out["max_dates"] = {
            k: (v.isoformat()[:10] if hasattr(v, "isoformat") else v)
            for k, v in row.items()
        }

        c.close()

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
