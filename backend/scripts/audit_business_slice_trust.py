"""
Auditoría de trust para Business Slice / Omniview Matrix.

Valida:
- fuentes reales usadas por la cadena Business Slice
- estado de completados vs cancelados
- cobertura mapped/unmapped
- consistencia entre sum(rows) y total real por periodo

Salida: JSON legible por stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from psycopg2.extras import RealDictCursor

sys.path.append(".")

from app.db.connection import get_db


def _query_all(sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or [])
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def _query_one(sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> dict[str, Any]:
    rows = _query_all(sql, params)
    return rows[0] if rows else {}


def collect_sources() -> dict[str, Any]:
    regclasses = _query_all(
        """
        SELECT 'public.trips_all' AS object_name, to_regclass('public.trips_all')::text AS exists_name
        UNION ALL
        SELECT 'public.trips_2025', to_regclass('public.trips_2025')::text
        UNION ALL
        SELECT 'public.trips_2026', to_regclass('public.trips_2026')::text
        UNION ALL
        SELECT 'public.trips_unified', to_regclass('public.trips_unified')::text
        UNION ALL
        SELECT 'ops.v_real_trips_enriched_base', to_regclass('ops.v_real_trips_enriched_base')::text
        UNION ALL
        SELECT 'ops.v_real_trips_business_slice_resolved', to_regclass('ops.v_real_trips_business_slice_resolved')::text
        UNION ALL
        SELECT 'ops.real_business_slice_month_fact', to_regclass('ops.real_business_slice_month_fact')::text
        UNION ALL
        SELECT 'ops.real_business_slice_day_fact', to_regclass('ops.real_business_slice_day_fact')::text
        UNION ALL
        SELECT 'ops.real_business_slice_week_fact', to_regclass('ops.real_business_slice_week_fact')::text
        """
    )
    view_defs = _query_all(
        """
        SELECT
            c.relname AS view_name,
            pg_get_viewdef(c.oid, true) AS view_sql
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'ops'
          AND c.relname IN (
              'v_real_trips_enriched_base',
              'v_real_trips_business_slice_resolved',
              'v_business_slice_coverage_month'
          )
        ORDER BY c.relname
        """
    )
    source_dist = _query_all(
        """
        SELECT source_table, COUNT(*)::bigint AS rows
        FROM ops.v_real_trips_enriched_base
        GROUP BY source_table
        ORDER BY rows DESC, source_table
        """
    )
    return {
        "objects": regclasses,
        "view_definitions": view_defs,
        "enriched_base_source_distribution": source_dist,
    }


def collect_completed_cancelled() -> dict[str, Any]:
    return _query_one(
        """
        SELECT
            COUNT(*)::bigint AS total_rows,
            COUNT(*) FILTER (WHERE condicion = 'Completado')::bigint AS condicion_completado,
            COUNT(*) FILTER (
                WHERE lower(coalesce(condicion::text, '')) LIKE '%%cancel%%'
            )::bigint AS condicion_cancel_like,
            COUNT(*) FILTER (
                WHERE length(trim(coalesce(motivo_cancelacion::text, ''))) > 0
            )::bigint AS motivo_cancelacion_present,
            COUNT(*) FILTER (WHERE completed_flag)::bigint AS completed_flag_true,
            COUNT(*) FILTER (WHERE cancelled_flag)::bigint AS cancelled_flag_true,
            COUNT(*) FILTER (
                WHERE completed_flag
                  AND length(trim(coalesce(motivo_cancelacion::text, ''))) > 0
            )::bigint AS completed_with_cancel_reason,
            COUNT(*) FILTER (
                WHERE cancelled_flag
                  AND NOT (lower(coalesce(condicion::text, '')) LIKE '%%cancel%%')
            )::bigint AS cancelled_flag_without_cancel_condicion
        FROM ops.v_real_trips_enriched_base
        """
    )


def collect_coverage() -> dict[str, Any]:
    status_counts = _query_all(
        """
        SELECT resolution_status, COUNT(*)::bigint AS rows
        FROM ops.v_real_trips_business_slice_resolved
        GROUP BY resolution_status
        ORDER BY rows DESC, resolution_status
        """
    )
    by_status = {r["resolution_status"]: int(r["rows"]) for r in status_counts}
    total = sum(by_status.values())
    mapped = by_status.get("resolved", 0)
    unmapped = by_status.get("unmatched", 0) + by_status.get("conflict", 0)
    other = total - mapped - unmapped
    return {
        "status_counts": status_counts,
        "total_trips_real": total,
        "mapped_trips": mapped,
        "unmapped_trips": unmapped,
        "other_status_trips": other,
        "identity_holds": total == mapped + unmapped,
        "mapped_pct": round((mapped / total) * 100, 2) if total else None,
        "unmapped_pct": round((unmapped / total) * 100, 2) if total else None,
    }


def _consistency_for_monthly() -> list[dict[str, Any]]:
    return _query_all(
        """
        WITH periods AS (
            SELECT month
            FROM ops.real_business_slice_month_fact
            GROUP BY month
            ORDER BY month DESC
            LIMIT 3
        ),
        rows_sum AS (
            SELECT
                f.month AS period_key,
                SUM(f.trips_completed)::bigint AS rows_trips,
                SUM(f.revenue_yego_net)::numeric AS rows_revenue,
                SUM(f.active_drivers)::bigint AS rows_active_drivers
            FROM ops.real_business_slice_month_fact f
            JOIN periods p ON p.month = f.month
            GROUP BY f.month
        ),
        distinct_total AS (
            SELECT
                r.trip_month AS period_key,
                COUNT(*) FILTER (WHERE r.completed_flag)::bigint AS total_trips,
                SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)::numeric AS total_revenue,
                COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)::bigint AS total_active_drivers
            FROM ops.v_real_trips_business_slice_resolved r
            JOIN periods p ON p.month = r.trip_month
            WHERE r.resolution_status = 'resolved'
            GROUP BY r.trip_month
        )
        SELECT
            rs.period_key::text,
            rs.rows_trips, dt.total_trips,
            rs.rows_revenue, dt.total_revenue,
            rs.rows_active_drivers, dt.total_active_drivers,
            (rs.rows_trips - dt.total_trips) AS trips_diff,
            (rs.rows_revenue - dt.total_revenue) AS revenue_diff,
            (rs.rows_active_drivers - dt.total_active_drivers) AS active_drivers_diff
        FROM rows_sum rs
        JOIN distinct_total dt USING (period_key)
        ORDER BY rs.period_key DESC
        """
    )


def _consistency_for_weekly() -> list[dict[str, Any]]:
    return _query_all(
        """
        WITH periods AS (
            SELECT week_start
            FROM ops.real_business_slice_week_fact
            GROUP BY week_start
            ORDER BY week_start DESC
            LIMIT 3
        ),
        rows_sum AS (
            SELECT
                f.week_start AS period_key,
                SUM(f.trips_completed)::bigint AS rows_trips,
                SUM(f.revenue_yego_net)::numeric AS rows_revenue,
                SUM(f.active_drivers)::bigint AS rows_active_drivers
            FROM ops.real_business_slice_week_fact f
            JOIN periods p ON p.week_start = f.week_start
            GROUP BY f.week_start
        ),
        distinct_total AS (
            SELECT
                r.trip_week AS period_key,
                COUNT(*) FILTER (WHERE r.completed_flag)::bigint AS total_trips,
                SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)::numeric AS total_revenue,
                COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)::bigint AS total_active_drivers
            FROM ops.v_real_trips_business_slice_resolved r
            JOIN periods p ON p.week_start = r.trip_week
            WHERE r.resolution_status = 'resolved'
            GROUP BY r.trip_week
        )
        SELECT
            rs.period_key::text,
            rs.rows_trips, dt.total_trips,
            rs.rows_revenue, dt.total_revenue,
            rs.rows_active_drivers, dt.total_active_drivers,
            (rs.rows_trips - dt.total_trips) AS trips_diff,
            (rs.rows_revenue - dt.total_revenue) AS revenue_diff,
            (rs.rows_active_drivers - dt.total_active_drivers) AS active_drivers_diff
        FROM rows_sum rs
        JOIN distinct_total dt USING (period_key)
        ORDER BY rs.period_key DESC
        """
    )


def _consistency_for_daily() -> list[dict[str, Any]]:
    return _query_all(
        """
        WITH periods AS (
            SELECT trip_date
            FROM ops.real_business_slice_day_fact
            GROUP BY trip_date
            ORDER BY trip_date DESC
            LIMIT 7
        ),
        rows_sum AS (
            SELECT
                f.trip_date AS period_key,
                SUM(f.trips_completed)::bigint AS rows_trips,
                SUM(f.revenue_yego_net)::numeric AS rows_revenue,
                SUM(f.active_drivers)::bigint AS rows_active_drivers
            FROM ops.real_business_slice_day_fact f
            JOIN periods p ON p.trip_date = f.trip_date
            GROUP BY f.trip_date
        ),
        distinct_total AS (
            SELECT
                r.trip_date AS period_key,
                COUNT(*) FILTER (WHERE r.completed_flag)::bigint AS total_trips,
                SUM(r.revenue_yego_net) FILTER (WHERE r.completed_flag)::numeric AS total_revenue,
                COUNT(DISTINCT r.driver_id) FILTER (WHERE r.completed_flag)::bigint AS total_active_drivers
            FROM ops.v_real_trips_business_slice_resolved r
            JOIN periods p ON p.trip_date = r.trip_date
            WHERE r.resolution_status = 'resolved'
            GROUP BY r.trip_date
        )
        SELECT
            rs.period_key::text,
            rs.rows_trips, dt.total_trips,
            rs.rows_revenue, dt.total_revenue,
            rs.rows_active_drivers, dt.total_active_drivers,
            (rs.rows_trips - dt.total_trips) AS trips_diff,
            (rs.rows_revenue - dt.total_revenue) AS revenue_diff,
            (rs.rows_active_drivers - dt.total_active_drivers) AS active_drivers_diff
        FROM rows_sum rs
        JOIN distinct_total dt USING (period_key)
        ORDER BY rs.period_key DESC
        """
    )


def collect_matrix_consistency() -> dict[str, Any]:
    return {
        "monthly": _consistency_for_monthly(),
        "weekly": _consistency_for_weekly(),
        "daily": _consistency_for_daily(),
        "note": "active_drivers no es métrica aditiva por fila; el total real usa distinct driver_id y puede no cuadrar con SUM(rows).",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--section",
        choices=["all", "sources", "completed_cancelled", "coverage", "matrix_consistency"],
        default="all",
    )
    args = parser.parse_args()

    if args.section == "all":
        report = {
            "sources": collect_sources(),
            "completed_cancelled": collect_completed_cancelled(),
            "coverage": collect_coverage(),
            "matrix_consistency": collect_matrix_consistency(),
        }
    elif args.section == "sources":
        report = {"sources": collect_sources()}
    elif args.section == "completed_cancelled":
        report = {"completed_cancelled": collect_completed_cancelled()}
    elif args.section == "coverage":
        report = {"coverage": collect_coverage()}
    else:
        report = {"matrix_consistency": collect_matrix_consistency()}

    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
