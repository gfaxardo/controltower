"""
Driver Lifecycle: KPIs y drilldown por park.
Fuentes: ops.mv_driver_lifecycle_base, ops.mv_driver_weekly_stats, ops.mv_driver_monthly_stats,
         ops.mv_driver_lifecycle_weekly_kpis, ops.mv_driver_lifecycle_monthly_kpis,
         ops.v_driver_weekly_churn_reactivation.
Park se deriva de weekly_stats/monthly_stats (park_id por driver-periodo). Activations por park
vía join base con weekly_stats en semana de activation_ts.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

TIMEOUT_MS = 60000


def _cursor(conn):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
    return c


def _park_names_lookup(conn, park_ids: list) -> dict:
    """Devuelve { park_id: park_name } desde dim.dim_park. Fallback: park_id como nombre."""
    if not park_ids:
        return {}
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT park_id, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text) AS park_name
            FROM dim.dim_park
            WHERE park_id = ANY(%s)
            """,
            (list(park_ids),),
        )
        return {r["park_id"]: r["park_name"] for r in cur.fetchall()}
    except Exception:
        return {}
    finally:
        cur.close()


def _cohort_mvs_exist(conn) -> tuple[bool, bool]:
    """Comprueba si existen las MVs de cohortes. Devuelve (kpis_exist, weekly_exist)."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT matviewname FROM pg_matviews
        WHERE schemaname = 'ops' AND matviewname IN ('mv_driver_cohort_kpis', 'mv_driver_cohorts_weekly')
    """)
    names = {r["matviewname"] for r in cur.fetchall()}
    cur.close()
    return "mv_driver_cohort_kpis" in names, "mv_driver_cohorts_weekly" in names


def get_weekly(
    from_date: str,
    to_date: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    KPIs semanales. Si park_id no se pasa, incluye breakdown_by_park.
    """
    with get_db() as conn:
        cur = _cursor(conn)
        # Global KPIs en rango (desde weekly_kpis)
        cur.execute(
            """
            SELECT week_start::text AS period_start,
                   activations,
                   active_drivers,
                   churn_flow AS churned,
                   reactivated
            FROM ops.mv_driver_lifecycle_weekly_kpis
            WHERE week_start >= %s::date AND week_start <= %s::date
            ORDER BY week_start
            """,
            (from_date, to_date),
        )
        rows = cur.fetchall()
        kpis = [dict(r) for r in rows] if rows else []

        breakdown_by_park: list[dict] = []
        if not park_id or (park_id and str(park_id).strip() == ""):
            # Activations por park: base join weekly_stats en semana de activación
            cur.execute(
                """
                WITH act_week AS (
                    SELECT
                        b.driver_key,
                        DATE_TRUNC('week', b.activation_ts)::date AS week_start
                    FROM ops.mv_driver_lifecycle_base b
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                ),
                act_by_park AS (
                    SELECT w.week_start, w.park_id,
                           COUNT(*) AS activations
                    FROM act_week a
                    JOIN ops.mv_driver_weekly_stats w
                      ON w.driver_key = a.driver_key AND w.week_start = a.week_start
                    WHERE w.park_id IS NOT NULL
                    GROUP BY w.week_start, w.park_id
                ),
                active_by_park AS (
                    SELECT week_start, park_id,
                           COUNT(DISTINCT driver_key) AS active_drivers
                    FROM ops.mv_driver_weekly_stats
                    WHERE week_start >= %s::date AND week_start <= %s::date
                      AND park_id IS NOT NULL
                    GROUP BY week_start, park_id
                ),
                churn_by_park AS (
                    SELECT w.week_start, w.park_id, COUNT(DISTINCT w.driver_key) AS churned
                    FROM ops.mv_driver_weekly_stats w
                    WHERE w.week_start >= %s::date AND w.week_start <= %s::date
                      AND w.park_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM ops.mv_driver_weekly_stats n
                        WHERE n.driver_key = w.driver_key
                          AND n.week_start = w.week_start + 7
                      )
                    GROUP BY w.week_start, w.park_id
                ),
                react_by_park AS (
                    SELECT week_start, park_id, COUNT(*) AS reactivated
                    FROM ops.v_driver_weekly_churn_reactivation
                    WHERE reactivated_week AND week_start >= %s::date AND week_start <= %s::date
                      AND park_id IS NOT NULL
                    GROUP BY week_start, park_id
                )
                SELECT
                    COALESCE(ax.week_start, ad.week_start)::text AS period_start,
                    COALESCE(ax.park_id, ad.park_id) AS park_id,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers,
                    COALESCE(cf.churned, 0) AS churned,
                    COALESCE(rx.reactivated, 0) AS reactivated
                FROM act_by_park ax
                FULL OUTER JOIN active_by_park ad
                  ON ad.week_start = ax.week_start AND ad.park_id = ax.park_id
                LEFT JOIN churn_by_park cf
                  ON cf.week_start = COALESCE(ax.week_start, ad.week_start)
                  AND cf.park_id = COALESCE(ax.park_id, ad.park_id)
                LEFT JOIN react_by_park rx
                  ON rx.week_start = COALESCE(ax.week_start, ad.week_start)
                  AND rx.park_id = COALESCE(ax.park_id, ad.park_id)
                ORDER BY period_start, park_id
                """,
                (from_date, to_date, from_date, to_date, from_date, to_date, from_date, to_date),
            )
            breakdown_by_park = [dict(r) for r in cur.fetchall()]

        elif park_id:
            # Filtrar kpis por park: agregar desde stats solo para ese park
            cur.execute(
                """
                WITH act_week AS (
                    SELECT b.driver_key, DATE_TRUNC('week', b.activation_ts)::date AS week_start
                    FROM ops.mv_driver_lifecycle_base b
                    JOIN ops.mv_driver_weekly_stats w
                      ON w.driver_key = b.driver_key
                      AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                      AND w.park_id = %s
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                ),
                act_agg AS (
                    SELECT week_start, COUNT(*) AS activations FROM act_week GROUP BY 1
                ),
                active_agg AS (
                    SELECT week_start, COUNT(DISTINCT driver_key) AS active_drivers
                    FROM ops.mv_driver_weekly_stats
                    WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                    GROUP BY 1
                ),
                churn_agg AS (
                    SELECT w.week_start, COUNT(DISTINCT w.driver_key) AS churned
                    FROM ops.mv_driver_weekly_stats w
                    WHERE w.park_id = %s AND w.week_start >= %s::date AND w.week_start <= %s::date
                      AND NOT EXISTS (
                        SELECT 1 FROM ops.mv_driver_weekly_stats n
                        WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
                      )
                    GROUP BY 1
                ),
                react_agg AS (
                    SELECT week_start, COUNT(*) AS reactivated
                    FROM ops.v_driver_weekly_churn_reactivation
                    WHERE park_id = %s AND reactivated_week
                      AND week_start >= %s::date AND week_start <= %s::date
                    GROUP BY 1
                )
                SELECT
                    k.week_start::text AS period_start,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers,
                    COALESCE(cf.churned, 0) AS churned,
                    COALESCE(rx.reactivated, 0) AS reactivated
                FROM ops.mv_driver_lifecycle_weekly_kpis k
                LEFT JOIN act_agg ax ON ax.week_start = k.week_start
                LEFT JOIN active_agg ad ON ad.week_start = k.week_start
                LEFT JOIN churn_agg cf ON cf.week_start = k.week_start
                LEFT JOIN react_agg rx ON rx.week_start = k.week_start
                WHERE k.week_start >= %s::date AND k.week_start <= %s::date
                ORDER BY k.week_start
                """,
                (
                    park_id, from_date, to_date,
                    park_id, from_date, to_date,
                    park_id, from_date, to_date,
                    park_id, from_date, to_date,
                    from_date, to_date,
                ),
            )
            kpis = [dict(r) for r in cur.fetchall()]

        cur.close()

    out = {"from": from_date, "to": to_date, "period_type": "week", "kpis": kpis}
    if breakdown_by_park:
        out["breakdown_by_park"] = breakdown_by_park
    return out


def get_monthly(
    from_date: str,
    to_date: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """KPIs mensuales. Si no se pasa park_id, incluye breakdown_by_park."""
    with get_db() as conn:
        cur = _cursor(conn)
        cur.execute(
            """
            SELECT month_start::text AS period_start,
                   activations,
                   active_drivers
            FROM ops.mv_driver_lifecycle_monthly_kpis
            WHERE month_start >= %s::date AND month_start <= %s::date
            ORDER BY month_start
            """,
            (from_date, to_date),
        )
        rows = cur.fetchall()
        kpis = [dict(r) for r in rows] if rows else []

        breakdown_by_park = []
        if not park_id or (park_id and str(park_id).strip() == ""):
            cur.execute(
                """
                WITH act_month AS (
                    SELECT b.driver_key, DATE_TRUNC('month', b.activation_ts)::date AS month_start
                    FROM ops.mv_driver_lifecycle_base b
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('month', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('month', b.activation_ts)::date <= %s::date
                ),
                act_by_park AS (
                    SELECT m.month_start, m.park_id, COUNT(*) AS activations
                    FROM act_month a
                    JOIN ops.mv_driver_monthly_stats m
                      ON m.driver_key = a.driver_key AND m.month_start = a.month_start
                    WHERE m.park_id IS NOT NULL
                    GROUP BY m.month_start, m.park_id
                ),
                active_by_park AS (
                    SELECT month_start, park_id, COUNT(DISTINCT driver_key) AS active_drivers
                    FROM ops.mv_driver_monthly_stats
                    WHERE month_start >= %s::date AND month_start <= %s::date AND park_id IS NOT NULL
                    GROUP BY month_start, park_id
                )
                SELECT
                    COALESCE(ax.month_start, ad.month_start)::text AS period_start,
                    COALESCE(ax.park_id, ad.park_id) AS park_id,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers
                FROM act_by_park ax
                FULL OUTER JOIN active_by_park ad
                  ON ad.month_start = ax.month_start AND ad.park_id = ax.park_id
                ORDER BY period_start, park_id
                """,
                (from_date, to_date, from_date, to_date),
            )
            breakdown_by_park = [dict(r) for r in cur.fetchall()]
        elif park_id:
            cur.execute(
                """
                WITH act_month AS (
                    SELECT b.driver_key, DATE_TRUNC('month', b.activation_ts)::date AS month_start
                    FROM ops.mv_driver_lifecycle_base b
                    JOIN ops.mv_driver_monthly_stats m
                      ON m.driver_key = b.driver_key
                      AND m.month_start = DATE_TRUNC('month', b.activation_ts)::date
                      AND m.park_id = %s
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('month', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('month', b.activation_ts)::date <= %s::date
                ),
                act_agg AS (SELECT month_start, COUNT(*) AS activations FROM act_month GROUP BY 1),
                active_agg AS (
                    SELECT month_start, COUNT(DISTINCT driver_key) AS active_drivers
                    FROM ops.mv_driver_monthly_stats
                    WHERE park_id = %s AND month_start >= %s::date AND month_start <= %s::date
                    GROUP BY 1
                )
                SELECT
                    k.month_start::text AS period_start,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers
                FROM ops.mv_driver_lifecycle_monthly_kpis k
                LEFT JOIN act_agg ax ON ax.month_start = k.month_start
                LEFT JOIN active_agg ad ON ad.month_start = k.month_start
                WHERE k.month_start >= %s::date AND k.month_start <= %s::date
                ORDER BY k.month_start
                """,
                (park_id, from_date, to_date, park_id, from_date, to_date, from_date, to_date),
            )
            kpis = [dict(r) for r in cur.fetchall()]

        cur.close()

    out = {"from": from_date, "to": to_date, "period_type": "month", "kpis": kpis}
    if breakdown_by_park:
        out["breakdown_by_park"] = breakdown_by_park
    return out


def get_drilldown(
    period_type: str,
    period_start: str,
    metric: str,
    park_id: str,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    Lista paginada de driver_key para (period_start, metric, park_id).
    metric: activations | churned | reactivated | active | fulltime | parttime
    """
    if not park_id or str(park_id).strip() == "":
        return {"error": "park_id is required for drilldown", "drivers": [], "total": 0, "page": page, "page_size": page_size}

    offset = (page - 1) * page_size
    with get_db() as conn:
        cur = _cursor(conn)

        if period_type == "week":
            period_col = "week_start"
            stats_table = "ops.mv_driver_weekly_stats"
            churn_view = "ops.v_driver_weekly_churn_reactivation"
        else:
            period_col = "month_start"
            stats_table = "ops.mv_driver_monthly_stats"
            churn_view = None  # no reactivation/churn view for monthly in same form

        drivers: list[dict] = []
        total = 0

        if metric == "activations":
            trunc_arg = "week" if period_type == "week" else "month"
            cur.execute(
                f"""
                SELECT b.driver_key, b.activation_ts, b.last_completed_ts
                FROM ops.mv_driver_lifecycle_base b
                JOIN {stats_table} s ON s.driver_key = b.driver_key
                  AND s.{period_col} = DATE_TRUNC(%s, b.activation_ts)::date
                  AND s.park_id = %s
                WHERE b.activation_ts IS NOT NULL
                  AND DATE_TRUNC(%s, b.activation_ts)::date = %s::date
                ORDER BY b.driver_key
                LIMIT %s OFFSET %s
                """,
                (trunc_arg, park_id, trunc_arg, period_start, page_size, offset),
            )
            rows = cur.fetchall()
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM ops.mv_driver_lifecycle_base b
                JOIN {stats_table} s ON s.driver_key = b.driver_key
                  AND s.{period_col} = DATE_TRUNC(%s, b.activation_ts)::date
                  AND s.park_id = %s
                WHERE b.activation_ts IS NOT NULL
                  AND DATE_TRUNC(%s, b.activation_ts)::date = %s::date
                """,
                (trunc_arg, park_id, trunc_arg, period_start),
            )
            total = cur.fetchone()["count"]
            drivers = [{"driver_key": r["driver_key"], "activation_ts": str(r["activation_ts"]) if r.get("activation_ts") else None, "last_completed_ts": str(r["last_completed_ts"]) if r.get("last_completed_ts") else None} for r in rows]

        elif metric == "active":
            cur.execute(
                f"""
                SELECT driver_key FROM {stats_table}
                WHERE {period_col} = %s::date AND park_id = %s
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (period_start, park_id, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) FROM {stats_table} WHERE {period_col} = %s::date AND park_id = %s",
                (period_start, park_id),
            )
            total = cur.fetchone()["count"]

        elif metric == "churned" and period_type == "week":
            cur.execute(
                """
                SELECT w.driver_key
                FROM ops.mv_driver_weekly_stats w
                WHERE w.week_start = %s::date AND w.park_id = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM ops.mv_driver_weekly_stats n
                    WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
                  )
                ORDER BY w.driver_key LIMIT %s OFFSET %s
                """,
                (period_start, park_id, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) FROM ops.mv_driver_weekly_stats w
                WHERE w.week_start = %s::date AND w.park_id = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM ops.mv_driver_weekly_stats n
                    WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
                  )
                """,
                (period_start, park_id),
            )
            total = cur.fetchone()["count"]

        elif metric == "reactivated" and period_type == "week" and churn_view:
            cur.execute(
                """
                SELECT driver_key FROM ops.v_driver_weekly_churn_reactivation
                WHERE week_start = %s::date AND park_id = %s AND reactivated_week
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (period_start, park_id, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                "SELECT COUNT(*) FROM ops.v_driver_weekly_churn_reactivation WHERE week_start = %s::date AND park_id = %s AND reactivated_week",
                (period_start, park_id),
            )
            total = cur.fetchone()["count"]

        elif metric == "fulltime":
            wm_col = "work_mode_week" if period_type == "week" else "work_mode_month"
            cur.execute(
                f"""
                SELECT driver_key FROM {stats_table}
                WHERE {period_col} = %s::date AND park_id = %s AND {wm_col} = 'FT'
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (period_start, park_id, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) FROM {stats_table} WHERE {period_col} = %s::date AND park_id = %s AND {wm_col} = 'FT'",
                (period_start, park_id),
            )
            total = cur.fetchone()["count"]

        elif metric == "parttime":
            wm_col = "work_mode_week" if period_type == "week" else "work_mode_month"
            cur.execute(
                f"""
                SELECT driver_key FROM {stats_table}
                WHERE {period_col} = %s::date AND park_id = %s AND {wm_col} = 'PT'
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (period_start, park_id, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) FROM {stats_table} WHERE {period_col} = %s::date AND park_id = %s AND {wm_col} = 'PT'",
                (period_start, park_id),
            )
            total = cur.fetchone()["count"]

        else:
            cur.close()
            return {
                "error": f"metric '{metric}' not supported for period_type '{period_type}' or requires driver-week/month stats MV",
                "drivers": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }

        cur.close()

    return {
        "period_type": period_type,
        "period_start": period_start,
        "metric": metric,
        "park_id": park_id,
        "drivers": drivers,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_base_metrics(
    from_date: str,
    to_date: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Métricas base: time_to_first_trip (avg, median), lifetime_days (avg, median).
    Filtro por park: usa weekly_stats si existe, si no driver_park_id.
    """
    with get_db() as conn:
        cur = _cursor(conn)
        park_val = None if park_id == "PARK_DESCONOCIDO" else park_id
        if park_id and str(park_id).strip():
            # Con park: join con weekly_stats en semana de activación, o driver_park_id
            try:
                cur.execute(
                    """
                    WITH base_park AS (
                        SELECT b.driver_key, b.ttf_days_from_registered, b.lifetime_days
                        FROM ops.mv_driver_lifecycle_base b
                        LEFT JOIN ops.mv_driver_weekly_stats w
                          ON w.driver_key = b.driver_key
                          AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                        WHERE b.activation_ts IS NOT NULL
                          AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                          AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                          AND COALESCE(w.park_id, b.driver_park_id) IS NOT DISTINCT FROM %s
                    )
                    SELECT
                        AVG(ttf_days_from_registered) AS time_to_first_trip_avg,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS time_to_first_trip_median,
                        AVG(lifetime_days) AS lifetime_days_avg,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lifetime_days) AS lifetime_days_median,
                        COUNT(*) AS driver_count
                    FROM base_park
                    WHERE ttf_days_from_registered IS NOT NULL OR lifetime_days IS NOT NULL
                    """,
                    (from_date, to_date, park_val),
                )
            except Exception:
                # Fallback: solo driver_park_id si weekly_stats no existe
                cur.execute(
                    """
                    SELECT
                        AVG(ttf_days_from_registered) AS time_to_first_trip_avg,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS time_to_first_trip_median,
                        AVG(lifetime_days) AS lifetime_days_avg,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lifetime_days) AS lifetime_days_median,
                        COUNT(*) AS driver_count
                    FROM ops.mv_driver_lifecycle_base
                    WHERE activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', activation_ts)::date <= %s::date
                      AND driver_park_id IS NOT DISTINCT FROM %s
                    """,
                    (from_date, to_date, park_val),
                )
        else:
            cur.execute(
                """
                SELECT
                    AVG(ttf_days_from_registered) AS time_to_first_trip_avg,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ttf_days_from_registered) AS time_to_first_trip_median,
                    AVG(lifetime_days) AS lifetime_days_avg,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY lifetime_days) AS lifetime_days_median,
                    COUNT(*) AS driver_count
                FROM ops.mv_driver_lifecycle_base
                WHERE activation_ts IS NOT NULL
                  AND DATE_TRUNC('week', activation_ts)::date >= %s::date
                  AND DATE_TRUNC('week', activation_ts)::date <= %s::date
                """,
                (from_date, to_date),
            )
        row = cur.fetchone()
        cur.close()
    return {
        "from": from_date,
        "to": to_date,
        "park_id": park_id,
        "time_to_first_trip_avg": float(row["time_to_first_trip_avg"] or 0),
        "time_to_first_trip_median": float(row["time_to_first_trip_median"] or 0),
        "lifetime_days_avg": float(row["lifetime_days_avg"] or 0),
        "lifetime_days_median": float(row["lifetime_days_median"] or 0),
        "driver_count": row["driver_count"] or 0,
    }


def get_base_metrics_drilldown(
    from_date: str,
    to_date: str,
    park_id: str,
    metric: str,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Drilldown de base metrics: lista drivers con ttf_days o lifetime_days."""
    if not park_id or str(park_id).strip() == "":
        return {"error": "park_id required", "drivers": [], "total": 0, "page": page, "page_size": page_size}
    order_col = "ttf_days_from_registered" if metric == "time_to_first_trip" else "lifetime_days"
    if metric not in ("time_to_first_trip", "lifetime_days"):
        return {"error": "metric must be time_to_first_trip or lifetime_days", "drivers": [], "total": 0, "page": page, "page_size": page_size}
    park_val = None if park_id == "PARK_DESCONOCIDO" else park_id
    offset = (page - 1) * page_size
    with get_db() as conn:
        cur = _cursor(conn)
        try:
            cur.execute(
                f"""
                WITH base_park AS (
                    SELECT b.driver_key, b.ttf_days_from_registered, b.lifetime_days, b.activation_ts
                    FROM ops.mv_driver_lifecycle_base b
                    LEFT JOIN ops.mv_driver_weekly_stats w
                      ON w.driver_key = b.driver_key
                      AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                      AND COALESCE(w.park_id, b.driver_park_id) IS NOT DISTINCT FROM %s
                )
                SELECT driver_key, ttf_days_from_registered, lifetime_days, activation_ts
                FROM base_park
                ORDER BY {order_col} DESC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                (from_date, to_date, park_val, page_size, offset),
            )
            drivers = [dict(r) for r in cur.fetchall()]
            cur.execute(
                """
                WITH base_park AS (
                    SELECT b.driver_key
                    FROM ops.mv_driver_lifecycle_base b
                    LEFT JOIN ops.mv_driver_weekly_stats w
                      ON w.driver_key = b.driver_key
                      AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                      AND COALESCE(w.park_id, b.driver_park_id) IS NOT DISTINCT FROM %s
                )
                SELECT COUNT(*) FROM base_park
                """,
                (from_date, to_date, park_val),
            )
            total = cur.fetchone()["count"]
        except Exception:
            drivers = []
            total = 0
        cur.close()
    return {
        "from": from_date,
        "to": to_date,
        "park_id": park_id,
        "metric": metric,
        "drivers": drivers,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_parks_summary(from_date: str, to_date: str, period_type: str = "week") -> dict[str, Any]:
    """Ranking de parks por activations, churn_rate, net_growth, mix FT/PT en el rango."""
    with get_db() as conn:
        cur = _cursor(conn)
        if period_type == "week":
            cur.execute(
                """
                WITH act AS (
                    SELECT w.park_id, COUNT(*) AS activations
                    FROM ops.mv_driver_lifecycle_base b
                    JOIN ops.mv_driver_weekly_stats w
                      ON w.driver_key = b.driver_key
                      AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                      AND w.park_id IS NOT NULL
                    GROUP BY w.park_id
                ),
                active AS (
                    SELECT park_id, SUM(drivers) AS active_drivers FROM (
                        SELECT park_id, week_start, COUNT(DISTINCT driver_key) AS drivers
                        FROM ops.mv_driver_weekly_stats
                        WHERE week_start >= %s::date AND week_start <= %s::date AND park_id IS NOT NULL
                        GROUP BY park_id, week_start
                    ) x GROUP BY park_id
                ),
                churn AS (
                    SELECT w.park_id, COUNT(DISTINCT w.driver_key) AS churned
                    FROM ops.mv_driver_weekly_stats w
                    WHERE w.week_start >= %s::date AND w.week_start <= %s::date AND w.park_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM ops.mv_driver_weekly_stats n
                        WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
                      )
                    GROUP BY w.park_id
                ),
                react AS (
                    SELECT park_id, COUNT(*) AS reactivated
                    FROM ops.v_driver_weekly_churn_reactivation
                    WHERE reactivated_week AND week_start >= %s::date AND week_start <= %s::date AND park_id IS NOT NULL
                    GROUP BY park_id
                ),
                ft_pt AS (
                    SELECT park_id,
                           COUNT(*) FILTER (WHERE work_mode_week = 'FT') AS ft,
                           COUNT(*) FILTER (WHERE work_mode_week = 'PT') AS pt
                    FROM ops.mv_driver_weekly_stats
                    WHERE week_start >= %s::date AND week_start <= %s::date AND park_id IS NOT NULL
                    GROUP BY park_id
                )
                SELECT
                    COALESCE(ax.park_id, ad.park_id) AS park_id,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers,
                    COALESCE(c.churned, 0) AS churned,
                    COALESCE(r.reactivated, 0) AS reactivated,
                    (COALESCE(ax.activations, 0) + COALESCE(r.reactivated, 0) - COALESCE(c.churned, 0)) AS net_growth,
                    COALESCE(f.ft, 0) AS fulltime,
                    COALESCE(f.pt, 0) AS parttime
                FROM act ax
                FULL OUTER JOIN active ad ON ad.park_id = ax.park_id
                LEFT JOIN churn c ON c.park_id = COALESCE(ax.park_id, ad.park_id)
                LEFT JOIN react r ON r.park_id = COALESCE(ax.park_id, ad.park_id)
                LEFT JOIN ft_pt f ON f.park_id = COALESCE(ax.park_id, ad.park_id)
                ORDER BY activations DESC NULLS LAST
                """,
                (from_date, to_date, from_date, to_date, from_date, to_date, from_date, to_date, from_date, to_date),
            )
        else:
            cur.execute(
                """
                WITH act AS (
                    SELECT m.park_id, COUNT(*) AS activations
                    FROM ops.mv_driver_lifecycle_base b
                    JOIN ops.mv_driver_monthly_stats m
                      ON m.driver_key = b.driver_key
                      AND m.month_start = DATE_TRUNC('month', b.activation_ts)::date
                    WHERE b.activation_ts IS NOT NULL
                      AND DATE_TRUNC('month', b.activation_ts)::date >= %s::date
                      AND DATE_TRUNC('month', b.activation_ts)::date <= %s::date
                      AND m.park_id IS NOT NULL
                    GROUP BY m.park_id
                ),
                active AS (
                    SELECT park_id, SUM(drivers) AS active_drivers FROM (
                        SELECT park_id, month_start, COUNT(DISTINCT driver_key) AS drivers
                        FROM ops.mv_driver_monthly_stats
                        WHERE month_start >= %s::date AND month_start <= %s::date AND park_id IS NOT NULL
                        GROUP BY park_id, month_start
                    ) x GROUP BY park_id
                ),
                ft_pt AS (
                    SELECT park_id,
                           COUNT(*) FILTER (WHERE work_mode_month = 'FT') AS ft,
                           COUNT(*) FILTER (WHERE work_mode_month = 'PT') AS pt
                    FROM ops.mv_driver_monthly_stats
                    WHERE month_start >= %s::date AND month_start <= %s::date AND park_id IS NOT NULL
                    GROUP BY park_id
                )
                SELECT
                    COALESCE(ax.park_id, ad.park_id) AS park_id,
                    COALESCE(ax.activations, 0) AS activations,
                    COALESCE(ad.active_drivers, 0) AS active_drivers,
                    0 AS churned,
                    0 AS reactivated,
                    COALESCE(ax.activations, 0) AS net_growth,
                    COALESCE(f.ft, 0) AS fulltime,
                    COALESCE(f.pt, 0) AS parttime
                FROM act ax
                FULL OUTER JOIN active ad ON ad.park_id = ax.park_id
                LEFT JOIN ft_pt f ON f.park_id = COALESCE(ax.park_id, ad.park_id)
                ORDER BY activations DESC NULLS LAST
                """,
                (from_date, to_date, from_date, to_date, from_date, to_date),
            )
        rows = cur.fetchall()
        park_ids = list({r.get("park_id") for r in rows if r.get("park_id") is not None})
        park_names = _park_names_lookup(conn, park_ids)
        cur.close()

    summary = [dict(r) for r in rows]
    for row in summary:
        pid = row.get("park_id")
        row["park_name"] = park_names.get(pid, (pid if pid is not None and str(pid).strip() else "PARK_DESCONOCIDO"))
        ad = row.get("active_drivers") or 0
        row["churn_rate"] = round((row.get("churned") or 0) / ad, 4) if ad else 0
        row["reactivation_rate"] = round((row.get("reactivated") or 0) / ad, 4) if ad else 0
        ft = row.get("fulltime") or 0
        pt = row.get("parttime") or 0
        row["mix_ft_pt"] = f"FT:{ft} PT:{pt}" if (ft + pt) > 0 else "-"

    return {"from": from_date, "to": to_date, "period_type": period_type, "parks": summary}


def get_series(
    grain: str,
    from_date: str,
    to_date: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Serie por periodo (week_start o month_start) con métricas.
    grain: weekly | monthly. park_id opcional. Orden: más reciente → más antiguo.
    """
    with get_db() as conn:
        cur = _cursor(conn)
        park_val = None if (park_id == "PARK_DESCONOCIDO" or not (park_id and str(park_id).strip())) else park_id

        if grain == "weekly":
            if not park_val:
                cur.execute(
                    """
                    SELECT
                        week_start::text AS period_start,
                        COALESCE(activations, 0) AS activations,
                        COALESCE(active_drivers, 0) AS active_drivers,
                        COALESCE(churn_flow, 0) AS churned,
                        COALESCE(reactivated, 0) AS reactivated
                    FROM ops.mv_driver_lifecycle_weekly_kpis
                    WHERE week_start >= %s::date AND week_start <= %s::date
                    ORDER BY week_start DESC
                    """,
                    (from_date, to_date),
                )
            else:
                cur.execute(
                    """
                    WITH act AS (
                        SELECT DATE_TRUNC('week', b.activation_ts)::date AS week_start, COUNT(*) AS activations
                        FROM ops.mv_driver_lifecycle_base b
                        JOIN ops.mv_driver_weekly_stats w
                          ON w.driver_key = b.driver_key AND w.week_start = DATE_TRUNC('week', b.activation_ts)::date
                        WHERE b.activation_ts IS NOT NULL AND w.park_id = %s
                          AND DATE_TRUNC('week', b.activation_ts)::date >= %s::date
                          AND DATE_TRUNC('week', b.activation_ts)::date <= %s::date
                        GROUP BY 1
                    ),
                    active AS (
                        SELECT week_start, COUNT(DISTINCT driver_key) AS active_drivers
                        FROM ops.mv_driver_weekly_stats
                        WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                        GROUP BY 1
                    ),
                    churn AS (
                        SELECT w.week_start, COUNT(DISTINCT w.driver_key) AS churned
                        FROM ops.mv_driver_weekly_stats w
                        WHERE w.park_id = %s AND w.week_start >= %s::date AND w.week_start <= %s::date
                          AND NOT EXISTS (
                            SELECT 1 FROM ops.mv_driver_weekly_stats n
                            WHERE n.driver_key = w.driver_key AND n.week_start = w.week_start + 7
                          )
                        GROUP BY w.week_start
                    ),
                    react AS (
                        SELECT week_start, COUNT(*) AS reactivated
                        FROM ops.v_driver_weekly_churn_reactivation
                        WHERE park_id = %s AND reactivated_week
                          AND week_start >= %s::date AND week_start <= %s::date
                        GROUP BY 1
                    ),
                    ft_pt AS (
                        SELECT week_start,
                               COUNT(*) FILTER (WHERE work_mode_week = 'FT') AS ft,
                               COUNT(*) FILTER (WHERE work_mode_week = 'PT') AS pt
                        FROM ops.mv_driver_weekly_stats
                        WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                        GROUP BY 1
                    ),
                    cal AS (
                        SELECT DISTINCT week_start FROM ops.mv_driver_weekly_stats
                        WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                    )
                    SELECT
                        cal.week_start::text AS period_start,
                        COALESCE(ax.activations, 0) AS activations,
                        COALESCE(ad.active_drivers, 0) AS active_drivers,
                        COALESCE(c.churned, 0) AS churned,
                        COALESCE(r.reactivated, 0) AS reactivated,
                        COALESCE(f.ft, 0) AS ft,
                        COALESCE(f.pt, 0) AS pt
                    FROM cal
                    LEFT JOIN act ax ON ax.week_start = cal.week_start
                    LEFT JOIN active ad ON ad.week_start = cal.week_start
                    LEFT JOIN churn c ON c.week_start = cal.week_start
                    LEFT JOIN react r ON r.week_start = cal.week_start
                    LEFT JOIN ft_pt f ON f.week_start = cal.week_start
                    ORDER BY cal.week_start DESC
                    """,
                    (park_val, from_date, to_date, park_val, from_date, to_date, park_val, from_date, to_date,
                     park_val, from_date, to_date, park_val, from_date, to_date, park_val, from_date, to_date),
                )
            rows = cur.fetchall()
            out_rows = []
            for r in rows:
                d = dict(r)
                ad = d.get("active_drivers") or 0
                ch = d.get("churned") or 0
                re = d.get("reactivated") or 0
                d["churn_rate"] = round(ch / ad, 4) if ad else 0
                d["reactivation_rate"] = round(re / ad, 4) if ad else 0
                d["net_growth"] = (d.get("activations") or 0) - ch + re
                ft = d.pop("ft", 0) or 0
                pt = d.pop("pt", 0) or 0
                d["mix_ft_pt"] = f"FT:{ft} PT:{pt}" if (ft + pt) > 0 else "-"
                out_rows.append(d)
            rows = out_rows

        else:
            # monthly
            if not park_val:
                cur.execute(
                    """
                    WITH k AS (
                        SELECT month_start, activations, active_drivers
                        FROM ops.mv_driver_lifecycle_monthly_kpis
                        WHERE month_start >= %s::date AND month_start <= %s::date
                    ),
                    churn AS (
                        SELECT m.month_start, COUNT(DISTINCT m.driver_key) AS churned
                        FROM ops.mv_driver_monthly_stats m
                        WHERE m.month_start >= %s::date AND m.month_start <= %s::date
                          AND NOT EXISTS (
                            SELECT 1 FROM ops.mv_driver_monthly_stats n
                            WHERE n.driver_key = m.driver_key
                              AND n.month_start = m.month_start + INTERVAL '1 month'
                          )
                        GROUP BY m.month_start
                    ),
                    react AS (
                        SELECT m.month_start, COUNT(DISTINCT m.driver_key) AS reactivated
                        FROM ops.mv_driver_monthly_stats m
                        WHERE m.month_start >= %s::date AND m.month_start <= %s::date
                          AND NOT EXISTS (
                            SELECT 1 FROM ops.mv_driver_monthly_stats p
                            WHERE p.driver_key = m.driver_key
                              AND p.month_start = m.month_start - INTERVAL '1 month'
                          )
                        GROUP BY m.month_start
                    ),
                    ft_pt AS (
                        SELECT month_start,
                               COUNT(*) FILTER (WHERE work_mode_month = 'FT') AS ft,
                               COUNT(*) FILTER (WHERE work_mode_month = 'PT') AS pt
                        FROM ops.mv_driver_monthly_stats
                        WHERE month_start >= %s::date AND month_start <= %s::date
                        GROUP BY 1
                    )
                    SELECT
                        k.month_start::text AS period_start,
                        COALESCE(k.activations, 0) AS activations,
                        COALESCE(k.active_drivers, 0) AS active_drivers,
                        COALESCE(c.churned, 0) AS churned,
                        COALESCE(r.reactivated, 0) AS reactivated,
                        COALESCE(f.ft, 0) AS ft,
                        COALESCE(f.pt, 0) AS pt
                    FROM k
                    LEFT JOIN churn c ON c.month_start = k.month_start
                    LEFT JOIN react r ON r.month_start = k.month_start
                    LEFT JOIN ft_pt f ON f.month_start = k.month_start
                    ORDER BY k.month_start DESC
                    """,
                    (from_date, to_date, from_date, to_date, from_date, to_date, from_date, to_date),
                )
            else:
                cur.execute(
                    """
                    WITH cal AS (
                        SELECT DISTINCT month_start FROM ops.mv_driver_monthly_stats
                        WHERE park_id = %s AND month_start >= %s::date AND month_start <= %s::date
                    ),
                    act AS (
                        SELECT DATE_TRUNC('month', b.activation_ts)::date AS month_start, COUNT(*) AS activations
                        FROM ops.mv_driver_lifecycle_base b
                        JOIN ops.mv_driver_monthly_stats m
                          ON m.driver_key = b.driver_key AND m.month_start = DATE_TRUNC('month', b.activation_ts)::date
                        WHERE b.activation_ts IS NOT NULL AND m.park_id = %s
                          AND DATE_TRUNC('month', b.activation_ts)::date >= %s::date
                          AND DATE_TRUNC('month', b.activation_ts)::date <= %s::date
                        GROUP BY 1
                    ),
                    active AS (
                        SELECT month_start, COUNT(DISTINCT driver_key) AS active_drivers
                        FROM ops.mv_driver_monthly_stats
                        WHERE park_id = %s AND month_start >= %s::date AND month_start <= %s::date
                        GROUP BY 1
                    ),
                    churn AS (
                        SELECT m.month_start, COUNT(DISTINCT m.driver_key) AS churned
                        FROM ops.mv_driver_monthly_stats m
                        WHERE m.park_id = %s AND m.month_start >= %s::date AND m.month_start <= %s::date
                          AND NOT EXISTS (
                            SELECT 1 FROM ops.mv_driver_monthly_stats n
                            WHERE n.driver_key = m.driver_key
                              AND n.month_start = m.month_start + INTERVAL '1 month'
                          )
                        GROUP BY m.month_start
                    ),
                    react AS (
                        SELECT m.month_start, COUNT(DISTINCT m.driver_key) AS reactivated
                        FROM ops.mv_driver_monthly_stats m
                        WHERE m.park_id = %s AND m.month_start >= %s::date AND m.month_start <= %s::date
                          AND NOT EXISTS (
                            SELECT 1 FROM ops.mv_driver_monthly_stats p
                            WHERE p.driver_key = m.driver_key
                              AND p.month_start = m.month_start - INTERVAL '1 month'
                          )
                        GROUP BY m.month_start
                    ),
                    ft_pt AS (
                        SELECT month_start,
                               COUNT(*) FILTER (WHERE work_mode_month = 'FT') AS ft,
                               COUNT(*) FILTER (WHERE work_mode_month = 'PT') AS pt
                        FROM ops.mv_driver_monthly_stats
                        WHERE park_id = %s AND month_start >= %s::date AND month_start <= %s::date
                        GROUP BY 1
                    )
                    SELECT
                        cal.month_start::text AS period_start,
                        COALESCE(ax.activations, 0) AS activations,
                        COALESCE(ad.active_drivers, 0) AS active_drivers,
                        COALESCE(c.churned, 0) AS churned,
                        COALESCE(r.reactivated, 0) AS reactivated,
                        COALESCE(f.ft, 0) AS ft,
                        COALESCE(f.pt, 0) AS pt
                    FROM cal
                    LEFT JOIN act ax ON ax.month_start = cal.month_start
                    LEFT JOIN active ad ON ad.month_start = cal.month_start
                    LEFT JOIN churn c ON c.month_start = cal.month_start
                    LEFT JOIN react r ON r.month_start = cal.month_start
                    LEFT JOIN ft_pt f ON f.month_start = cal.month_start
                    ORDER BY cal.month_start DESC
                    """,
                    (park_val, from_date, to_date, park_val, from_date, to_date, park_val, from_date, to_date,
                     park_val, from_date, to_date, park_val, from_date, to_date, park_val, from_date, to_date),
                )
            rows = cur.fetchall()
            out_rows = []
            for r in rows:
                d = dict(r)
                ad = d.get("active_drivers") or 0
                ch = d.get("churned") or 0
                re = d.get("reactivated") or 0
                d["churn_rate"] = round(ch / ad, 4) if ad else 0
                d["reactivation_rate"] = round(re / ad, 4) if ad else 0
                d["net_growth"] = (d.get("activations") or 0) - ch + re
                ft = d.pop("ft", 0) or 0
                pt = d.pop("pt", 0) or 0
                d["mix_ft_pt"] = f"FT:{ft} PT:{pt}" if (ft + pt) > 0 else "-"
                out_rows.append(d)
            rows = out_rows

        cur.close()

    return {
        "grain": grain,
        "from": from_date,
        "to": to_date,
        "park_id": park_id,
        "rows": rows if isinstance(rows, list) else [dict(x) for x in rows],
    }


def get_summary(
    grain: str,
    from_date: str,
    to_date: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Resumen (cards): activations_range, churned_range, reactivated_range,
    time_to_first_trip_avg_days, lifetime_avg_active_days, active_drivers_last_period.
    Consistente con get_series: active_drivers_last_period = primer periodo de series.
    """
    series = get_series(grain=grain, from_date=from_date, to_date=to_date, park_id=park_id)
    rows = series.get("rows") or []
    activations_range = sum((r.get("activations") or 0) for r in rows)
    churned_range = sum((r.get("churned") or 0) for r in rows)
    reactivated_range = sum((r.get("reactivated") or 0) for r in rows)
    active_drivers_last_period = rows[0].get("active_drivers") if rows else None

    base = get_base_metrics(from_date=from_date, to_date=to_date, park_id=park_id)
    time_to_first_trip_avg_days = base.get("time_to_first_trip_avg")
    lifetime_avg_active_days = base.get("lifetime_days_avg")

    return {
        "grain": grain,
        "from": from_date,
        "to": to_date,
        "park_id": park_id,
        "activations_range": activations_range,
        "churned_range": churned_range,
        "reactivated_range": reactivated_range,
        "time_to_first_trip_avg_days": time_to_first_trip_avg_days,
        "lifetime_avg_active_days": lifetime_avg_active_days,
        "active_drivers_last_period": active_drivers_last_period,
    }


def get_cohorts(
    from_cohort_week: str,
    to_cohort_week: str,
    park_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    KPIs de cohortes desde ops.mv_driver_cohort_kpis.
    params: from_cohort_week, to_cohort_week (YYYY-MM-DD lunes), park_id opcional.
    Si las MVs de cohortes no están desplegadas, devuelve cohorts=[] y cohort_mvs_not_deployed=True (200 OK).
    """
    with get_db() as conn:
        kpis_exist, _ = _cohort_mvs_exist(conn)
        if not kpis_exist:
            return {
                "from_cohort_week": from_cohort_week,
                "to_cohort_week": to_cohort_week,
                "cohorts": [],
                "cohort_mvs_not_deployed": True,
            }
        cur = _cursor(conn)
        if park_id and str(park_id).strip() != "":
            cur.execute(
                """
                SELECT cohort_week::text, park_id, cohort_size,
                       retention_w1, retention_w4, retention_w8, retention_w12
                FROM ops.mv_driver_cohort_kpis
                WHERE cohort_week >= %s::date AND cohort_week <= %s::date
                  AND park_id IS NOT DISTINCT FROM %s
                ORDER BY cohort_week DESC, park_id
                """,
                (from_cohort_week, to_cohort_week, park_id if park_id != "PARK_DESCONOCIDO" else None),
            )
        else:
            cur.execute(
                """
                SELECT cohort_week::text, park_id, cohort_size,
                       retention_w1, retention_w4, retention_w8, retention_w12
                FROM ops.mv_driver_cohort_kpis
                WHERE cohort_week >= %s::date AND cohort_week <= %s::date
                ORDER BY cohort_week DESC, park_id
                """,
                (from_cohort_week, to_cohort_week),
            )
        rows = cur.fetchall()
        cur.close()
    return {
        "from_cohort_week": from_cohort_week,
        "to_cohort_week": to_cohort_week,
        "cohorts": [dict(r) for r in rows],
    }


def get_cohort_drilldown(
    cohort_week: str,
    horizon: str,
    park_id: str,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """
    Lista paginada de driver_key para (cohort_week, horizon, park_id).
    horizon: base | w1 | w4 | w8 | w12
    - base = todos los drivers de la cohorte/park
    - w1 = active_w1 = true, etc.
    park_id obligatorio.
    Si la MV ops.mv_driver_cohorts_weekly no existe, devuelve drivers=[], total=0 y cohort_mvs_not_deployed=True (200 OK).
    """
    if not park_id or str(park_id).strip() == "":
        return {"error": "park_id is required for cohort drilldown", "drivers": [], "total": 0, "page": page, "page_size": page_size}
    if horizon not in ("base", "w1", "w4", "w8", "w12"):
        return {"error": "horizon must be base|w1|w4|w8|w12", "drivers": [], "total": 0, "page": page, "page_size": page_size}

    park_val = None if park_id == "PARK_DESCONOCIDO" else park_id
    offset = (page - 1) * page_size

    with get_db() as conn:
        _, weekly_exist = _cohort_mvs_exist(conn)
        if not weekly_exist:
            return {
                "cohort_week": cohort_week,
                "horizon": horizon,
                "park_id": park_id,
                "drivers": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "cohort_mvs_not_deployed": True,
            }
        cur = _cursor(conn)
        if horizon == "base":
            cur.execute(
                """
                SELECT driver_key FROM ops.mv_driver_cohorts_weekly
                WHERE cohort_week = %s::date AND park_id IS NOT DISTINCT FROM %s
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (cohort_week, park_val, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) FROM ops.mv_driver_cohorts_weekly
                WHERE cohort_week = %s::date AND park_id IS NOT DISTINCT FROM %s
                """,
                (cohort_week, park_val),
            )
            total = cur.fetchone()["count"]
        else:
            col = {"w1": "active_w1", "w4": "active_w4", "w8": "active_w8", "w12": "active_w12"}.get(horizon)
            if not col:
                cur.close()
                return {"error": f"horizon must be base|w1|w4|w8|w12", "drivers": [], "total": 0, "page": page, "page_size": page_size}
            cur.execute(
                f"""
                SELECT driver_key FROM ops.mv_driver_cohorts_weekly
                WHERE cohort_week = %s::date AND park_id IS NOT DISTINCT FROM %s AND {col} = 1
                ORDER BY driver_key LIMIT %s OFFSET %s
                """,
                (cohort_week, park_val, page_size, offset),
            )
            drivers = [{"driver_key": r["driver_key"]} for r in cur.fetchall()]
            cur.execute(
                f"""
                SELECT COUNT(*) FROM ops.mv_driver_cohorts_weekly
                WHERE cohort_week = %s::date AND park_id IS NOT DISTINCT FROM %s AND {col} = 1
                """,
                (cohort_week, park_val),
            )
            total = cur.fetchone()["count"]
        cur.close()

    return {
        "cohort_week": cohort_week,
        "horizon": horizon,
        "park_id": park_id,
        "drivers": drivers,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
