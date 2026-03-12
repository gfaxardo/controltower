"""
Driver Behavioral Deviation Engine — driver-level time-window behavior.
Additive; does not replace Behavioral Alerts or Action Engine.
Reads from: ops.mv_driver_segments_weekly, ops.v_driver_last_trip, dim.v_geo_park, ops.v_dim_driver_resolved.
Computes per-driver: recent vs baseline windows, delta_pct, days_since_last_trip, alert_type, risk_score, suggested_action.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db_audit
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

_DRIVER_SEGMENTS = "ops.mv_driver_segments_weekly"
_LAST_TRIP = "ops.v_driver_last_trip"
_GEO = "dim.v_geo_park"
_DRIVER_NAME = "ops.v_dim_driver_resolved"
# Queries scan driver-week data; use dedicated connection with 5 min timeout (not pool)
_DRIVER_BEHAVIOR_QUERY_TIMEOUT_MS = 300_000


def _reference_week(conn, cursor) -> Optional[str]:
    cursor.execute(f"SELECT MAX(week_start)::text AS w FROM {_DRIVER_SEGMENTS}")
    row = cursor.fetchone()
    return row["w"] if row and row.get("w") else None


def _build_driver_level_query(
    reference_week_s: str,
    recent_weeks: int,
    baseline_weeks: int,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    inactivity_status: Optional[str] = None,
    min_baseline_trips: Optional[float] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "risk_score",
    order_dir: str = "desc",
) -> tuple[str, list]:
    ref = reference_week_s
    rw, bw = max(1, recent_weeks), max(1, baseline_weeks)
    conditions = []
    params: list = [ref, rw, bw, rw, ref, rw, bw, rw]
    # Base CTE: driver-weeks in full range
    # recent: week_start <= ref AND week_start > ref - rw*7
    # baseline: week_start <= ref - rw*7 AND week_start > ref - (rw+bw)*7
    having_conditions = []
    if country:
        having_conditions.append("(g.country IS NOT NULL AND LOWER(TRIM(g.country)) = LOWER(TRIM(%s)))")
        params.append(country)
    if city:
        having_conditions.append("(g.city IS NOT NULL AND LOWER(TRIM(g.city)) = LOWER(TRIM(%s)))")
        params.append(city)
    if park_id:
        having_conditions.append("d.park_id::text = %s")
        params.append(str(park_id))
    if segment_current:
        having_conditions.append("base.current_segment = %s")
        params.append(segment_current)
    having_sql = " AND ".join(having_conditions) if having_conditions else "1=1"

    # Inactivity status filter: map to days_since_last_trip range
    days_filter = ""
    if inactivity_status:
        if inactivity_status == "active":
            days_filter = " AND COALESCE(base.days_since_last_trip, 999) <= 3"
        elif inactivity_status == "cooling":
            days_filter = " AND COALESCE(base.days_since_last_trip, 999) BETWEEN 4 AND 7"
        elif inactivity_status == "dormant_risk":
            days_filter = " AND COALESCE(base.days_since_last_trip, 999) BETWEEN 8 AND 14"
        elif inactivity_status == "churn_risk":
            days_filter = " AND COALESCE(base.days_since_last_trip, 999) >= 15"

    alert_filter = ""
    if alert_type:
        alert_filter = " AND base.alert_type = %s"
        params.append(alert_type)
    if severity:
        alert_filter += " AND base.severity = %s"
        params.append(severity)
    if risk_band:
        alert_filter += " AND base.risk_band = %s"
        params.append(risk_band)
    if min_baseline_trips is not None:
        alert_filter += " AND base.baseline_avg_weekly_trips >= %s"
        params.append(min_baseline_trips)

    order_col = "risk_score"
    if order_by in ("delta_pct", "days_since_last_trip", "driver_key", "recent_avg_weekly_trips"):
        order_col = order_by
    dir_sql = "DESC" if (order_dir or "desc").lower() == "desc" else "ASC"
    if order_col == "delta_pct":
        # more negative = worse, so usually we want ASC for "worst first"
        dir_sql = "ASC" if (order_dir or "asc").lower() == "asc" else "DESC"
    params.extend([limit, offset])

    sql = f"""
WITH ref AS (SELECT %s::date AS r),
     recent_agg AS (
         SELECT
             d.driver_key,
             d.park_id,
             COUNT(*)::int AS recent_weeks_count,
             SUM(d.trips_completed_week)::numeric AS recent_window_trips,
             ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg_weekly_trips,
             MAX(d.segment_week) AS current_segment
         FROM {_DRIVER_SEGMENTS} d, ref
         WHERE d.week_start <= ref.r
           AND d.week_start > ref.r - (%s * INTERVAL '1 week')
         GROUP BY d.driver_key, d.park_id
     ),
     baseline_agg AS (
         SELECT
             d.driver_key,
             d.park_id,
             COUNT(*)::int AS baseline_active_weeks,
             SUM(d.trips_completed_week)::numeric AS baseline_window_trips,
             ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg_weekly_trips,
             ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.trips_completed_week))::numeric, 4) AS baseline_median_weekly_trips,
             ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev_weekly_trips
         FROM {_DRIVER_SEGMENTS} d, ref
         WHERE d.week_start <= ref.r - (%s * INTERVAL '1 week')
           AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
         GROUP BY d.driver_key, d.park_id
     ),
     streaks AS (
         SELECT
             driver_key,
             park_id,
             MAX(declining)::int AS declining_weeks_consecutive,
             MAX(rising)::int AS rising_weeks_consecutive
         FROM (
             SELECT
                 driver_key,
                 park_id,
                 week_start,
                 trips_completed_week,
                 LAG(trips_completed_week) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC) AS prev_trips,
                 SUM(CASE WHEN trips_completed_week < LAG(trips_completed_week) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC) THEN 1 ELSE 0 END)
                     OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS declining,
                 SUM(CASE WHEN trips_completed_week > LAG(trips_completed_week) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC) THEN 1 ELSE 0 END)
                     OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS rising
             FROM {_DRIVER_SEGMENTS} d, ref
             WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
         ) x
         WHERE prev_trips IS NOT NULL
         GROUP BY driver_key, park_id
     ),
     base AS (
         SELECT
             ra.driver_key,
             ra.park_id,
             %s AS recent_window_weeks,
             %s AS baseline_window_weeks,
             ra.recent_window_trips,
             ra.recent_avg_weekly_trips,
             ra.current_segment,
             ba.baseline_window_trips,
             ba.baseline_avg_weekly_trips,
             ba.baseline_median_weekly_trips,
             ba.baseline_stddev_weekly_trips,
             ba.baseline_active_weeks,
             (ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) AS delta_abs,
             CASE WHEN ba.baseline_avg_weekly_trips IS NULL OR ba.baseline_avg_weekly_trips = 0 THEN NULL
                  ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_avg_weekly_trips)::numeric, 6) END AS delta_pct,
             CASE WHEN ba.baseline_stddev_weekly_trips IS NULL OR ba.baseline_stddev_weekly_trips = 0 THEN NULL
                  ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_stddev_weekly_trips)::numeric, 4) END AS z_score_simple,
             COALESCE(s.declining_weeks_consecutive, 0)::int AS declining_weeks_consecutive,
             COALESCE(s.rising_weeks_consecutive, 0)::int AS rising_weeks_consecutive,
             (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip,
             CASE
                 WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 3 THEN 'active'
                 WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 7 THEN 'cooling'
                 WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 14 THEN 'dormant_risk'
                 ELSE 'churn_risk'
             END AS inactivity_status,
             COALESCE(g.country, 'UNKNOWN') AS country,
             COALESCE(g.city, 'UNKNOWN') AS city,
             COALESCE(g.park_name, ra.park_id::text) AS park_name,
             COALESCE(dr.driver_name, ra.driver_key::text) AS driver_name
         FROM ref,
              recent_agg ra
         JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
         LEFT JOIN streaks s ON s.driver_key = ra.driver_key AND (s.park_id IS NOT DISTINCT FROM ra.park_id)
         LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
         LEFT JOIN {_GEO} g ON g.park_id = ra.park_id
         LEFT JOIN {_DRIVER_NAME} dr ON dr.driver_id = ra.driver_key
         WHERE 1=1
     ),
     classified AS (
         SELECT
             base.*,
             CASE
                 WHEN base.days_since_last_trip >= 15 THEN 'Churn Risk'
                 WHEN base.days_since_last_trip >= 8 THEN 'Dormant Risk'
                 WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30 THEN 'Sharp Degradation'
                 WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15 THEN 'Moderate Degradation'
                 WHEN base.declining_weeks_consecutive >= 3 THEN 'Sustained Degradation'
                 WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'Recovery'
                 WHEN base.baseline_avg_weekly_trips IS NOT NULL AND base.baseline_avg_weekly_trips > 0
                      AND base.baseline_stddev_weekly_trips IS NOT NULL
                      AND (base.baseline_stddev_weekly_trips / base.baseline_avg_weekly_trips) > 0.5 THEN 'High Volatility'
                 ELSE 'Stable'
             END AS alert_type,
             CASE
                 WHEN base.days_since_last_trip >= 15 OR (base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30) THEN 'critical'
                 WHEN base.days_since_last_trip >= 8 OR base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15 OR base.declining_weeks_consecutive >= 3 THEN 'moderate'
                 WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'positive'
                 ELSE 'neutral'
             END AS severity
         FROM base
     ),
     with_risk AS (
         SELECT
             c.*,
             LEAST(100, GREATEST(0,
                 COALESCE(LEAST(40, CASE WHEN c.delta_pct < 0 THEN LEAST(40, (-c.delta_pct) * 40) ELSE 0 END), 0) +
                 COALESCE(LEAST(20, c.declining_weeks_consecutive * 5), 0) +
                 COALESCE(LEAST(20, CASE WHEN c.days_since_last_trip IS NOT NULL THEN LEAST(20, c.days_since_last_trip) ELSE 0 END), 0) +
                 COALESCE(LEAST(20, (COALESCE(c.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0)
             ))::int AS risk_score,
             CASE
                 WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN c.delta_pct < 0 THEN LEAST(40, (-c.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, c.declining_weeks_consecutive * 5), 0) + COALESCE(LEAST(20, CASE WHEN c.days_since_last_trip IS NOT NULL THEN LEAST(20, c.days_since_last_trip) ELSE 0 END), 0) + COALESCE(LEAST(20, (COALESCE(c.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 24 THEN 'stable'
                 WHEN LEAST(100, GREATEST(0, ...)) <= 49 THEN 'monitor'
                 WHEN LEAST(100, GREATEST(0, ...)) <= 74 THEN 'medium risk'
                 ELSE 'high risk'
             END AS risk_band
         FROM classified c
     )
    """
    # Simplify risk_band: compute in Python or use a single expression
    # I'll use a subquery that computes risk_score first then bands
    full_sql = f"""
WITH ref AS (SELECT %s::date AS r),
     recent_agg AS (
         SELECT d.driver_key, d.park_id,
                COUNT(*)::int AS recent_weeks_count,
                SUM(d.trips_completed_week)::numeric AS recent_window_trips,
                ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg_weekly_trips,
                MAX(d.segment_week) AS current_segment
         FROM {_DRIVER_SEGMENTS} d, ref
         WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
         GROUP BY d.driver_key, d.park_id
     ),
     baseline_agg AS (
         SELECT d.driver_key, d.park_id,
                COUNT(*)::int AS baseline_active_weeks,
                SUM(d.trips_completed_week)::numeric AS baseline_window_trips,
                ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg_weekly_trips,
                ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.trips_completed_week))::numeric, 4) AS baseline_median_weekly_trips,
                ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev_weekly_trips
         FROM {_DRIVER_SEGMENTS} d, ref
         WHERE d.week_start <= ref.r - (%s * INTERVAL '1 week')
           AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
         GROUP BY d.driver_key, d.park_id
     ),
     week_series AS (
         SELECT d.driver_key, d.park_id, d.week_start, d.trips_completed_week,
                LAG(d.trips_completed_week) OVER (PARTITION BY d.driver_key, d.park_id ORDER BY d.week_start DESC) AS prev_trips
         FROM {_DRIVER_SEGMENTS} d, ref
         WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
     ),
     streaks AS (
         SELECT driver_key, park_id,
                MAX(decl)::int AS declining_weeks_consecutive,
                MAX(ris)::int AS rising_weeks_consecutive
         FROM (
             SELECT driver_key, park_id,
                    SUM(CASE WHEN trips_completed_week < prev_trips THEN 1 ELSE 0 END) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS decl,
                    SUM(CASE WHEN trips_completed_week > prev_trips THEN 1 ELSE 0 END) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ris
             FROM week_series WHERE prev_trips IS NOT NULL
         ) x
         GROUP BY driver_key, park_id
     ),
     base AS (
         SELECT
             ra.driver_key, ra.park_id,
             %s AS recent_window_weeks, %s AS baseline_window_weeks,
             ra.recent_window_trips, ra.recent_avg_weekly_trips, ra.current_segment,
             ba.baseline_window_trips, ba.baseline_avg_weekly_trips, ba.baseline_median_weekly_trips,
             ba.baseline_stddev_weekly_trips, ba.baseline_active_weeks,
             (ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) AS delta_abs,
             CASE WHEN ba.baseline_avg_weekly_trips IS NULL OR ba.baseline_avg_weekly_trips = 0 THEN NULL
                  ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_avg_weekly_trips)::numeric, 6) END AS delta_pct,
             CASE WHEN ba.baseline_stddev_weekly_trips IS NULL OR ba.baseline_stddev_weekly_trips = 0 THEN NULL
                  ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_stddev_weekly_trips)::numeric, 4) END AS z_score_simple,
             COALESCE(s.declining_weeks_consecutive, 0)::int AS declining_weeks_consecutive,
             COALESCE(s.rising_weeks_consecutive, 0)::int AS rising_weeks_consecutive,
             (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip,
             CASE WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 3 THEN 'active'
                  WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 7 THEN 'cooling'
                  WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 14 THEN 'dormant_risk' ELSE 'churn_risk' END AS inactivity_status,
             COALESCE(g.country, 'UNKNOWN') AS country, COALESCE(g.city, 'UNKNOWN') AS city,
             COALESCE(g.park_name, ra.park_id::text) AS park_name,
             COALESCE(dr.driver_name, ra.driver_key::text) AS driver_name
         FROM ref, recent_agg ra
         JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
         LEFT JOIN streaks s ON s.driver_key = ra.driver_key AND (s.park_id IS NOT DISTINCT FROM ra.park_id)
         LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
         LEFT JOIN {_GEO} g ON g.park_id = ra.park_id
         LEFT JOIN {_DRIVER_NAME} dr ON dr.driver_id = ra.driver_key
         WHERE """ + having_sql.replace("base.", "ra.").replace("current_segment", "ra.current_segment") + """
     )
    """
    # Having referred to base which doesn't exist yet; do filter after classified. Let me simplify: do geo filter on ra.park_id via join to g and WHERE on g.country/g.city. So we need to join geo in base and filter there.
    # I'll write a simpler version that filters in the final SELECT and use a second query for count.
    return "", []  # placeholder - implement full query below in get_drivers


def get_driver_behavior_summary(
    recent_weeks: int = 4,
    baseline_weeks: int = 16,
    as_of_week: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    inactivity_status: Optional[str] = None,
) -> dict[str, Any]:
    """KPI counts for Driver Behavior tab. Driver-level; uses configurable windows."""
    with get_db_audit(_DRIVER_BEHAVIOR_QUERY_TIMEOUT_MS) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            ref = as_of_week or _reference_week(conn, cur)
            if not ref:
                return _empty_summary()
            rw, bw = max(1, recent_weeks), max(1, baseline_weeks)
            # SQL placeholders: ref, rw (recent_agg), rw (baseline_agg start), rw+bw (baseline_agg end) -> ref, rw, rw, rw, bw
            params: list = [ref, rw, rw, rw, bw]
            where_extra = []
            if country:
                where_extra.append("AND LOWER(TRIM(geo.country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where_extra.append("AND LOWER(TRIM(geo.city)) = LOWER(TRIM(%s))")
                params.append(city)
            if park_id:
                where_extra.append("AND cls.park_id::text = %s")
                params.append(str(park_id))
            if segment_current:
                where_extra.append("AND cls.current_segment = %s")
                params.append(segment_current)
            if alert_type:
                where_extra.append("AND cls.alert_type = %s")
                params.append(alert_type)
            if severity:
                where_extra.append("AND cls.severity = %s")
                params.append(severity)
            if risk_band:
                where_extra.append("AND cls.risk_band = %s")
                params.append(risk_band)
            if inactivity_status:
                if inactivity_status == "active":
                    where_extra.append("AND COALESCE(seg.days_since_last_trip, 999) <= 3")
                elif inactivity_status == "cooling":
                    where_extra.append("AND COALESCE(seg.days_since_last_trip, 999) BETWEEN 4 AND 7")
                elif inactivity_status == "dormant_risk":
                    where_extra.append("AND COALESCE(seg.days_since_last_trip, 999) BETWEEN 8 AND 14")
                elif inactivity_status == "churn_risk":
                    where_extra.append("AND COALESCE(seg.days_since_last_trip, 999) >= 15")
            we = " ".join(where_extra)

            cur.execute(f"""
                WITH ref AS (SELECT %s::date AS r),
                recent_agg AS (
                    SELECT d.driver_key, d.park_id,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg,
                           MAX(d.segment_week) AS current_segment
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                baseline_agg AS (
                    SELECT d.driver_key, d.park_id,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg,
                           ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r - (%s * INTERVAL '1 week')
                      AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                seg AS (
                    SELECT ra.driver_key, ra.park_id, ra.recent_avg AS recent_avg_weekly_trips, ra.current_segment,
                           ba.baseline_avg AS baseline_avg_weekly_trips, ba.baseline_stddev AS baseline_stddev_weekly_trips,
                           CASE WHEN ba.baseline_avg IS NULL OR ba.baseline_avg = 0 THEN NULL
                                ELSE ROUND(((ra.recent_avg - ba.baseline_avg) / ba.baseline_avg)::numeric, 6) END AS delta_pct,
                           (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip
                    FROM ref, recent_agg ra
                    JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
                    LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
                ),
                cls AS (
                    SELECT seg.*,
                           CASE WHEN seg.days_since_last_trip >= 15 THEN 'Churn Risk'
                            WHEN seg.days_since_last_trip >= 8 THEN 'Dormant Risk'
                            WHEN seg.delta_pct IS NOT NULL AND seg.delta_pct <= -0.30 THEN 'Sharp Degradation'
                            WHEN seg.delta_pct IS NOT NULL AND seg.delta_pct <= -0.15 THEN 'Moderate Degradation'
                            WHEN seg.delta_pct IS NOT NULL AND seg.delta_pct >= 0.25 THEN 'Recovery'
                            WHEN seg.baseline_stddev_weekly_trips IS NOT NULL AND seg.baseline_avg_weekly_trips > 0
                                 AND (seg.baseline_stddev_weekly_trips / seg.baseline_avg_weekly_trips) > 0.5 THEN 'High Volatility'
                            ELSE 'Stable' END AS alert_type,
                           CASE WHEN seg.days_since_last_trip >= 15 OR (seg.delta_pct IS NOT NULL AND seg.delta_pct <= -0.30) THEN 'critical'
                            WHEN seg.days_since_last_trip >= 8 OR (seg.delta_pct IS NOT NULL AND seg.delta_pct <= -0.15) THEN 'moderate'
                            WHEN seg.delta_pct IS NOT NULL AND seg.delta_pct >= 0.25 THEN 'positive' ELSE 'neutral' END AS severity,
                           LEAST(100, GREATEST(0,
                               COALESCE(LEAST(40, CASE WHEN seg.delta_pct < 0 THEN LEAST(40, (-seg.delta_pct) * 40) ELSE 0 END), 0) +
                               COALESCE(LEAST(20, seg.days_since_last_trip), 0) +
                               COALESCE(LEAST(20, (COALESCE(seg.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0)
                           ))::int AS risk_score,
                           CASE WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN seg.delta_pct < 0 THEN LEAST(40, (-seg.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, seg.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(seg.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 24 THEN 'stable'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN seg.delta_pct < 0 THEN LEAST(40, (-seg.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, seg.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(seg.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 49 THEN 'monitor'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN seg.delta_pct < 0 THEN LEAST(40, (-seg.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, seg.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(seg.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 74 THEN 'medium risk'
                            ELSE 'high risk' END AS risk_band
                    FROM seg
                )
                SELECT
                    COUNT(*)::int AS drivers_monitored,
                    COUNT(*) FILTER (WHERE cls.alert_type = 'Sharp Degradation')::int AS sharp_degradation,
                    COUNT(*) FILTER (WHERE cls.alert_type = 'Sustained Degradation')::int AS sustained_degradation,
                    COUNT(*) FILTER (WHERE cls.alert_type = 'Recovery')::int AS recovery_cases,
                    COUNT(*) FILTER (WHERE cls.alert_type IN ('Dormant Risk', 'Churn Risk'))::int AS dormant_risk_cases,
                    COUNT(*) FILTER (WHERE cls.risk_band = 'high risk' AND cls.baseline_avg_weekly_trips >= 40)::int AS high_value_at_risk,
                    ROUND(AVG(cls.days_since_last_trip)::numeric, 1) AS avg_days_since_last_trip
                FROM cls
                LEFT JOIN {_GEO} geo ON geo.park_id = cls.park_id
                WHERE 1=1 """ + we.replace("seg.", "cls."),
                params,
            )
            row = cur.fetchone()
            return dict(row) if row else _empty_summary()
        finally:
            cur.close()


def _empty_summary() -> dict[str, Any]:
    return {
        "drivers_monitored": 0,
        "sharp_degradation": 0,
        "sustained_degradation": 0,
        "recovery_cases": 0,
        "dormant_risk_cases": 0,
        "high_value_at_risk": 0,
        "avg_days_since_last_trip": None,
    }


def get_driver_behavior_drivers(
    recent_weeks: int = 4,
    baseline_weeks: int = 16,
    as_of_week: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    inactivity_status: Optional[str] = None,
    min_baseline_trips: Optional[float] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "risk_score",
    order_dir: str = "desc",
) -> dict[str, Any]:
    """Driver-level list with deviation metrics. Orders by risk_score DESC by default."""
    with get_db_audit(_DRIVER_BEHAVIOR_QUERY_TIMEOUT_MS) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            ref = as_of_week or _reference_week(conn, cur)
            if not ref:
                return {"data": [], "total": 0, "limit": limit, "offset": offset}
            rw, bw = max(1, recent_weeks), max(1, baseline_weeks)
            # SQL: ref, rw (recent_agg), rw (baseline start), rw+bw (baseline end), rw (week_series), rw, bw (base literals) -> ref, rw, rw, rw, bw, rw, rw, bw
            params: list = [ref, rw, rw, rw, bw, rw, rw, bw]
            # Build filter list for HAVING/WHERE
            having_parts = []
            if country:
                having_parts.append("LOWER(TRIM(geo.country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                having_parts.append("LOWER(TRIM(geo.city)) = LOWER(TRIM(%s))")
                params.append(city)
            if park_id:
                having_parts.append("ra.park_id::text = %s")
                params.append(str(park_id))
            if segment_current:
                having_parts.append("ra.current_segment = %s")
                params.append(segment_current)
            if alert_type:
                having_parts.append("cls.alert_type = %s")
                params.append(alert_type)
            if severity:
                having_parts.append("cls.severity = %s")
                params.append(severity)
            if risk_band:
                having_parts.append("cls.risk_band = %s")
                params.append(risk_band)
            if min_baseline_trips is not None:
                having_parts.append("cls.baseline_avg_weekly_trips >= %s")
                params.append(min_baseline_trips)
            if inactivity_status:
                if inactivity_status == "active":
                    having_parts.append("COALESCE(cls.days_since_last_trip, 999) <= 3")
                elif inactivity_status == "cooling":
                    having_parts.append("COALESCE(cls.days_since_last_trip, 999) BETWEEN 4 AND 7")
                elif inactivity_status == "dormant_risk":
                    having_parts.append("COALESCE(cls.days_since_last_trip, 999) BETWEEN 8 AND 14")
                elif inactivity_status == "churn_risk":
                    having_parts.append("COALESCE(cls.days_since_last_trip, 999) >= 15")
            where_sql = " AND " + " AND ".join(having_parts) if having_parts else ""
            # Main query selects FROM with_action, so WHERE/ORDER BY must not reference "cls"
            where_sql_main = where_sql.replace("cls.", "")

            ob = "risk_score DESC"
            if order_by == "delta_pct":
                ob = "delta_pct ASC NULLS LAST" if (order_dir or "asc").lower() == "asc" else "delta_pct DESC NULLS LAST"
            elif order_by == "days_since_last_trip":
                ob = "days_since_last_trip DESC NULLS LAST"
            elif order_by == "recent_avg_weekly_trips":
                ob = f"recent_avg_weekly_trips {order_dir or 'desc'}"
            params.extend([limit, offset])

            # Single query: compute driver-level + classify + filter + order + limit
            cur.execute(f"""
                WITH ref AS (SELECT %s::date AS r),
                recent_agg AS (
                    SELECT d.driver_key, d.park_id,
                           SUM(d.trips_completed_week)::numeric AS recent_window_trips,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg_weekly_trips,
                           MAX(d.segment_week) AS current_segment
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                baseline_agg AS (
                    SELECT d.driver_key, d.park_id,
                           COUNT(*)::int AS baseline_active_weeks,
                           SUM(d.trips_completed_week)::numeric AS baseline_window_trips,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg_weekly_trips,
                           ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.trips_completed_week))::numeric, 4) AS baseline_median_weekly_trips,
                           ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev_weekly_trips
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r - (%s * INTERVAL '1 week')
                      AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                week_series AS (
                    SELECT d.driver_key, d.park_id, d.week_start, d.trips_completed_week,
                           LAG(d.trips_completed_week) OVER (PARTITION BY d.driver_key, d.park_id ORDER BY d.week_start DESC) AS prev_trips
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
                ),
                strk AS (
                    SELECT driver_key, park_id,
                           MAX(decl)::int AS declining_weeks_consecutive,
                           MAX(ris)::int AS rising_weeks_consecutive
                    FROM (
                        SELECT driver_key, park_id,
                               SUM(CASE WHEN trips_completed_week < prev_trips THEN 1 ELSE 0 END) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS decl,
                               SUM(CASE WHEN trips_completed_week > prev_trips THEN 1 ELSE 0 END) OVER (PARTITION BY driver_key, park_id ORDER BY week_start DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS ris
                        FROM week_series WHERE prev_trips IS NOT NULL
                    ) x
                    GROUP BY driver_key, park_id
                ),
                base AS (
                    SELECT ra.driver_key, ra.park_id,
                           %s AS recent_window_weeks, %s AS baseline_window_weeks,
                           ra.recent_window_trips, ra.recent_avg_weekly_trips, ra.current_segment,
                           ba.baseline_window_trips, ba.baseline_avg_weekly_trips, ba.baseline_median_weekly_trips,
                           ba.baseline_stddev_weekly_trips, ba.baseline_active_weeks,
                           (ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) AS delta_abs,
                           CASE WHEN ba.baseline_avg_weekly_trips IS NULL OR ba.baseline_avg_weekly_trips = 0 THEN NULL
                                ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_avg_weekly_trips)::numeric, 6) END AS delta_pct,
                           CASE WHEN ba.baseline_stddev_weekly_trips IS NULL OR ba.baseline_stddev_weekly_trips = 0 THEN NULL
                                ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_stddev_weekly_trips)::numeric, 4) END AS z_score_simple,
                           COALESCE(s.declining_weeks_consecutive, 0)::int AS declining_weeks_consecutive,
                           COALESCE(s.rising_weeks_consecutive, 0)::int AS rising_weeks_consecutive,
                           (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip,
                           CASE WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 3 THEN 'active'
                                WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 7 THEN 'cooling'
                                WHEN (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int <= 14 THEN 'dormant_risk' ELSE 'churn_risk' END AS inactivity_status,
                           COALESCE(geo.country, 'UNKNOWN') AS country, COALESCE(geo.city, 'UNKNOWN') AS city,
                           COALESCE(geo.park_name, ra.park_id::text) AS park_name,
                           COALESCE(dr.driver_name, ra.driver_key::text) AS driver_name
                    FROM ref, recent_agg ra
                    JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
                    LEFT JOIN strk s ON s.driver_key = ra.driver_key AND (s.park_id IS NOT DISTINCT FROM ra.park_id)
                    LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
                    LEFT JOIN {_GEO} geo ON geo.park_id = ra.park_id
                    LEFT JOIN {_DRIVER_NAME} dr ON dr.driver_id = ra.driver_key
                ),
                cls AS (
                    SELECT base.*,
                           CASE WHEN base.days_since_last_trip >= 15 THEN 'Churn Risk'
                            WHEN base.days_since_last_trip >= 8 THEN 'Dormant Risk'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30 THEN 'Sharp Degradation'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15 THEN 'Moderate Degradation'
                            WHEN base.declining_weeks_consecutive >= 3 THEN 'Sustained Degradation'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'Recovery'
                            WHEN base.baseline_avg_weekly_trips IS NOT NULL AND base.baseline_avg_weekly_trips > 0
                                 AND base.baseline_stddev_weekly_trips IS NOT NULL
                                 AND (base.baseline_stddev_weekly_trips / base.baseline_avg_weekly_trips) > 0.5 THEN 'High Volatility'
                            ELSE 'Stable' END AS alert_type,
                           CASE WHEN base.days_since_last_trip >= 15 OR (base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30) THEN 'critical'
                            WHEN base.days_since_last_trip >= 8 OR (base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15) OR base.declining_weeks_consecutive >= 3 THEN 'moderate'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'positive' ELSE 'neutral' END AS severity,
                           LEAST(100, GREATEST(0,
                               COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) +
                               COALESCE(LEAST(20, base.declining_weeks_consecutive * 5), 0) +
                               COALESCE(LEAST(20, CASE WHEN base.days_since_last_trip IS NOT NULL THEN LEAST(20, base.days_since_last_trip) ELSE 0 END), 0) +
                               COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0)
                           ))::int AS risk_score,
                           CASE WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.declining_weeks_consecutive * 5), 0) + COALESCE(LEAST(20, CASE WHEN base.days_since_last_trip IS NOT NULL THEN LEAST(20, base.days_since_last_trip) ELSE 0 END), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 24 THEN 'stable'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.declining_weeks_consecutive * 5), 0) + COALESCE(LEAST(20, CASE WHEN base.days_since_last_trip IS NOT NULL THEN LEAST(20, base.days_since_last_trip) ELSE 0 END), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 49 THEN 'monitor'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.declining_weeks_consecutive * 5), 0) + COALESCE(LEAST(20, CASE WHEN base.days_since_last_trip IS NOT NULL THEN LEAST(20, base.days_since_last_trip) ELSE 0 END), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 74 THEN 'medium risk'
                            ELSE 'high risk' END AS risk_band
                    FROM base
                ),
                with_action AS (
                    SELECT cls.*,
                           CASE WHEN cls.delta_pct IS NOT NULL AND (cls.delta_pct < -0.05 OR cls.declining_weeks_consecutive >= 2) THEN 'Empeorando'
                            WHEN cls.delta_pct IS NOT NULL AND (cls.delta_pct >= 0.25 OR cls.rising_weeks_consecutive >= 2) THEN 'Recuperando'
                            WHEN cls.delta_pct IS NOT NULL AND cls.delta_pct > 0.05 THEN 'Mejorando'
                            WHEN cls.alert_type = 'High Volatility' THEN 'Volátil'
                            WHEN cls.days_since_last_trip >= 8 THEN 'Empeorando'
                            ELSE 'Estable' END AS behavior_direction,
                           CASE WHEN cls.alert_type IN ('Churn Risk', 'Dormant Risk') THEN 'reactivation_whatsapp'
                            WHEN cls.alert_type = 'Sharp Degradation' THEN 'outbound_retention_call'
                            WHEN cls.alert_type = 'Moderate Degradation' THEN 'loyalty_call'
                            WHEN cls.alert_type = 'Recovery' THEN 'coaching_push'
                            ELSE 'monitor_only' END AS suggested_channel,
                           CASE WHEN cls.alert_type IN ('Churn Risk', 'Dormant Risk') THEN 'Reactivación'
                            WHEN cls.alert_type = 'Sharp Degradation' THEN 'Retención prioritaria'
                            WHEN cls.alert_type = 'Moderate Degradation' THEN 'Contacto lealtad'
                            WHEN cls.alert_type = 'Recovery' THEN 'Refuerzo recuperación'
                            ELSE 'Solo seguimiento' END AS suggested_action,
                           (cls.delta_pct::numeric * 100)::text || '%% vs baseline, ' ||
                           COALESCE(cls.declining_weeks_consecutive::text, '0') || ' sem empeorando, ' ||
                           COALESCE(cls.days_since_last_trip::text, '?') || ' días sin viaje' AS rationale_short
                    FROM cls
                )
                SELECT * FROM with_action WHERE 1=1 """ + where_sql_main + f"""
                ORDER BY {ob}, driver_key
                LIMIT %s OFFSET %s
            """, params)
            rows = [dict(r) for r in cur.fetchall()]

            # Count total (same filters, no limit/offset). Count query has 5 CTE placeholders: ref, rw, rw, rw, bw
            count_params = params[:5] + params[8:-2]  # CTE params + filter params (skip the 3 extra for main query: rw, rw, bw)
            cur.execute(f"""
                WITH ref AS (SELECT %s::date AS r),
                recent_agg AS (
                    SELECT d.driver_key, d.park_id, ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg_weekly_trips, MAX(d.segment_week) AS current_segment
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                baseline_agg AS (
                    SELECT d.driver_key, d.park_id, ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg_weekly_trips,
                           ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev_weekly_trips
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.week_start <= ref.r - (%s * INTERVAL '1 week') AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                base AS (
                    SELECT ra.driver_key, ra.park_id, ra.recent_avg_weekly_trips, ra.current_segment, ba.baseline_avg_weekly_trips, ba.baseline_stddev_weekly_trips,
                           CASE WHEN ba.baseline_avg_weekly_trips IS NULL OR ba.baseline_avg_weekly_trips = 0 THEN NULL
                                ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_avg_weekly_trips)::numeric, 6) END AS delta_pct,
                           (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip
                    FROM ref, recent_agg ra
                    JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
                    LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
                ),
                cls AS (
                    SELECT base.*,
                           CASE WHEN base.days_since_last_trip >= 15 THEN 'Churn Risk' WHEN base.days_since_last_trip >= 8 THEN 'Dormant Risk'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30 THEN 'Sharp Degradation'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15 THEN 'Moderate Degradation'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'Recovery'
                            WHEN base.baseline_stddev_weekly_trips IS NOT NULL AND base.baseline_avg_weekly_trips > 0 AND (base.baseline_stddev_weekly_trips / base.baseline_avg_weekly_trips) > 0.5 THEN 'High Volatility'
                            ELSE 'Stable' END AS alert_type,
                           CASE WHEN base.days_since_last_trip >= 15 OR (base.delta_pct IS NOT NULL AND base.delta_pct <= -0.30) THEN 'critical'
                            WHEN base.days_since_last_trip >= 8 OR (base.delta_pct IS NOT NULL AND base.delta_pct <= -0.15) THEN 'moderate'
                            WHEN base.delta_pct IS NOT NULL AND base.delta_pct >= 0.25 THEN 'positive' ELSE 'neutral' END AS severity,
                           LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0)))::int AS risk_score,
                           CASE WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 24 THEN 'stable'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 49 THEN 'monitor'
                            WHEN LEAST(100, GREATEST(0, COALESCE(LEAST(40, CASE WHEN base.delta_pct < 0 THEN LEAST(40, (-base.delta_pct) * 40) ELSE 0 END), 0) + COALESCE(LEAST(20, base.days_since_last_trip), 0) + COALESCE(LEAST(20, (COALESCE(base.baseline_avg_weekly_trips, 0) / 10)::int + 5), 0))) <= 74 THEN 'medium risk' ELSE 'high risk' END AS risk_band
                    FROM base
                )
                SELECT COUNT(*)::int AS n FROM cls
                LEFT JOIN {_GEO} geo ON geo.park_id = cls.park_id
                WHERE 1=1 """ + where_sql,
                count_params,
            )
            total = cur.fetchone()["n"]
            return {"data": rows, "total": total, "limit": limit, "offset": offset}
        finally:
            cur.close()


def get_driver_behavior_driver_detail(
    driver_key: str,
    recent_weeks: int = 4,
    baseline_weeks: int = 16,
    as_of_week: Optional[str] = None,
) -> dict[str, Any]:
    """Single driver detail for drilldown: same metrics + weekly series for chart."""
    with get_db_audit(_DRIVER_BEHAVIOR_QUERY_TIMEOUT_MS) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            ref = as_of_week or _reference_week(conn, cur)
            if not ref:
                return {"driver_key": driver_key, "data": None, "weekly": []}
            rw, bw = max(1, recent_weeks), max(1, baseline_weeks)
            # Get driver-level row from same logic (single driver filter)
            params = [driver_key, ref, rw, bw, rw, ref, rw, bw, rw]
            cur.execute(f"""
                WITH ref AS (SELECT %s::date AS r),
                recent_agg AS (
                    SELECT d.driver_key, d.park_id, SUM(d.trips_completed_week)::numeric AS recent_window_trips,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS recent_avg_weekly_trips, MAX(d.segment_week) AS current_segment
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.driver_key::text = %s AND d.week_start <= ref.r AND d.week_start > ref.r - (%s * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                baseline_agg AS (
                    SELECT d.driver_key, d.park_id, COUNT(*)::int AS baseline_active_weeks,
                           ROUND(AVG(d.trips_completed_week)::numeric, 4) AS baseline_avg_weekly_trips,
                           ROUND(STDDEV_POP(d.trips_completed_week)::numeric, 4) AS baseline_stddev_weekly_trips
                    FROM {_DRIVER_SEGMENTS} d, ref
                    WHERE d.driver_key::text = %s AND d.week_start <= ref.r - (%s * INTERVAL '1 week') AND d.week_start > ref.r - ((%s + %s) * INTERVAL '1 week')
                    GROUP BY d.driver_key, d.park_id
                ),
                base AS (
                    SELECT ra.driver_key, ra.park_id, ra.recent_window_trips, ra.recent_avg_weekly_trips, ra.current_segment,
                           ba.baseline_avg_weekly_trips, ba.baseline_stddev_weekly_trips, ba.baseline_active_weeks,
                           (ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) AS delta_abs,
                           CASE WHEN ba.baseline_avg_weekly_trips IS NULL OR ba.baseline_avg_weekly_trips = 0 THEN NULL
                                ELSE ROUND(((ra.recent_avg_weekly_trips - ba.baseline_avg_weekly_trips) / ba.baseline_avg_weekly_trips)::numeric, 6) END AS delta_pct,
                           (ref.r + 6 - COALESCE(lt.last_trip_date, ref.r + 6))::int AS days_since_last_trip,
                           COALESCE(geo.country, 'UNKNOWN') AS country, COALESCE(geo.city, 'UNKNOWN') AS city, COALESCE(geo.park_name, ra.park_id::text) AS park_name,
                           COALESCE(dr.driver_name, ra.driver_key::text) AS driver_name
                    FROM ref, recent_agg ra
                    JOIN baseline_agg ba ON ba.driver_key = ra.driver_key AND (ba.park_id IS NOT DISTINCT FROM ra.park_id)
                    LEFT JOIN {_LAST_TRIP} lt ON lt.driver_key = ra.driver_key
                    LEFT JOIN {_GEO} geo ON geo.park_id = ra.park_id
                    LEFT JOIN {_DRIVER_NAME} dr ON dr.driver_id = ra.driver_key
                )
                SELECT * FROM base
            """, params)
            row = cur.fetchone()
            if not row:
                return {"driver_key": driver_key, "data": None, "weekly": []}
            # Weekly series for chart (recent + baseline weeks)
            cur.execute(f"""
                SELECT week_start, week_start::text AS week_label, trips_completed_week AS trips, segment_week AS segment
                FROM {_DRIVER_SEGMENTS} d
                WHERE d.driver_key::text = %s AND d.week_start <= %s::date AND d.week_start > %s::date - ((%s + %s) * INTERVAL '1 week')
                ORDER BY d.week_start ASC
            """, [driver_key, ref, ref, rw, bw])
            weekly = [dict(r) for r in cur.fetchall()]
            # Add behavior_direction and risk/action to row
            delta_pct = row.get("delta_pct")
            days = row.get("days_since_last_trip")
            if delta_pct is not None and delta_pct < -0.05:
                row["behavior_direction"] = "Empeorando"
            elif delta_pct is not None and delta_pct > 0.25:
                row["behavior_direction"] = "Recuperando"
            elif delta_pct is not None and delta_pct > 0.05:
                row["behavior_direction"] = "Mejorando"
            elif days is not None and days >= 8:
                row["behavior_direction"] = "Empeorando"
            else:
                row["behavior_direction"] = "Estable"
            d = row.get("delta_pct")
            days_val = row.get("days_since_last_trip") or 0
            base_avg = row.get("baseline_avg_weekly_trips") or 0
            risk = min(100, max(0,
                (min(40, int((-d * 40)) if d is not None and d < 0 else 0) +
                 min(20, days_val) +
                 min(20, int(base_avg / 10) + 5))
            ))
            row["risk_score"] = risk
            row["risk_band"] = "stable" if risk <= 24 else ("monitor" if risk <= 49 else ("medium risk" if risk <= 74 else "high risk"))
            row["alert_type"] = "Dormant Risk" if (days or 0) >= 8 else ("Sharp Degradation" if (delta_pct or 0) <= -0.30 else ("Recovery" if (delta_pct or 0) >= 0.25 else "Stable"))
            row["suggested_action"] = "Reactivación" if (days or 0) >= 8 else ("Retención prioritaria" if (delta_pct or 0) <= -0.30 else "Solo seguimiento")
            row["rationale_short"] = f"{((delta_pct or 0) * 100):.0f}% vs baseline, {days or 0} días sin viaje"
            return {"driver_key": driver_key, "data": dict(row), "weekly": weekly, "reference_week": ref, "recent_window_weeks": rw, "baseline_window_weeks": bw}
        finally:
            cur.close()


def get_driver_behavior_export(
    recent_weeks: int = 4,
    baseline_weeks: int = 16,
    as_of_week: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    inactivity_status: Optional[str] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    """Export driver list with same filters; respects max_rows."""
    out = get_driver_behavior_drivers(
        recent_weeks=recent_weeks,
        baseline_weeks=baseline_weeks,
        as_of_week=as_of_week,
        country=country,
        city=city,
        park_id=park_id,
        segment_current=segment_current,
        alert_type=alert_type,
        severity=severity,
        risk_band=risk_band,
        inactivity_status=inactivity_status,
        limit=max_rows,
        offset=0,
    )
    return out.get("data") or []
