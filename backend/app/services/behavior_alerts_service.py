"""
Behavioral Alerts — API service: summary, drivers list, driver detail, export.
Reads from ops.v_driver_behavior_alerts_weekly (or ops.mv_driver_behavior_alerts_weekly if preferred).
Filters: week_start, date_range, baseline_window (4/6/8; view currently implements 6), country, city, park, segment_current, alert_type, severity.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

# View: always live. MV: faster for heavy list/export (same schema as view).
_ALERTS_VIEW = "ops.v_driver_behavior_alerts_weekly"
_ALERTS_MV = "ops.mv_driver_behavior_alerts_weekly"
_LAST_TRIP_VIEW = "ops.v_driver_last_trip"
# Summary/counts use view (aggregates are relatively cheap). Drivers list and export use MV when available for speed.
_ALERTS_SOURCE = _ALERTS_VIEW
# Timeout (ms) for heavy queries when using view. Not needed when querying MV.
_BEHAVIOR_ALERTS_QUERY_TIMEOUT_MS = 600_000


def _build_where(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    movement_type: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
) -> tuple[str, list]:
    conditions = []
    params: list = []
    if week_start:
        conditions.append("week_start = %s::date")
        params.append(week_start)
    if from_date:
        conditions.append("week_start >= %s::date")
        params.append(from_date)
    if to_date:
        conditions.append("week_start <= %s::date")
        params.append(to_date)
    if country:
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country)
    if city:
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city)
    if park_id:
        conditions.append("park_id::text = %s")
        params.append(str(park_id))
    if segment_current:
        conditions.append("segment_current = %s")
        params.append(segment_current)
    if movement_type:
        conditions.append("movement_type = %s")
        params.append(movement_type)
    if alert_type:
        conditions.append("alert_type = %s")
        params.append(alert_type)
    if severity:
        conditions.append("severity = %s")
        params.append(severity)
    if risk_band:
        conditions.append("risk_band = %s")
        params.append(risk_band)
    where_sql = " AND ".join(conditions) if conditions else "1=1"
    return where_sql, params


def get_behavior_alerts_summary(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    movement_type: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
) -> dict[str, Any]:
    """KPI metrics: drivers_monitored, critical_drops, moderate_drops, strong_recoveries, silent_erosion, high_volatility, high_risk_drivers, medium_risk_drivers."""
    where_sql, params = _build_where(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, movement_type=movement_type,
        alert_type=alert_type, severity=severity, risk_band=risk_band,
    )
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    COUNT(DISTINCT driver_key) AS drivers_monitored,
                    COUNT(*) FILTER (WHERE alert_type = 'Sudden Stop') AS sudden_stop,
                    COUNT(*) FILTER (WHERE alert_type = 'Critical Drop') AS critical_drops,
                    COUNT(*) FILTER (WHERE alert_type = 'Moderate Drop') AS moderate_drops,
                    COUNT(*) FILTER (WHERE alert_type = 'Silent Erosion') AS silent_erosion,
                    COUNT(*) FILTER (WHERE alert_type = 'Strong Recovery') AS strong_recoveries,
                    COUNT(*) FILTER (WHERE alert_type = 'High Volatility') AS high_volatility,
                    COUNT(*) FILTER (WHERE alert_type = 'Stable Performer') AS stable_performer,
                    COUNT(*) FILTER (WHERE risk_band = 'high risk') AS high_risk_drivers,
                    COUNT(*) FILTER (WHERE risk_band = 'medium risk') AS medium_risk_drivers
                FROM {_ALERTS_SOURCE}
                WHERE {where_sql}
                """,
                params,
            )
            row = cur.fetchone()
            return dict(row) if row else {
                "drivers_monitored": 0,
                "sudden_stop": 0,
                "critical_drops": 0,
                "moderate_drops": 0,
                "strong_recoveries": 0,
                "silent_erosion": 0,
                "high_volatility": 0,
                "stable_performer": 0,
                "high_risk_drivers": 0,
                "medium_risk_drivers": 0,
            }
        finally:
            cur.close()


def get_behavior_alerts_drivers(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    movement_type: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
    order_by: str = "risk_score",
    order_dir: str = "desc",
) -> dict[str, Any]:
    """Filtered alert rows for table. order_by: risk_score | severity | delta_pct | week_start; default risk_score DESC, delta_pct ASC."""
    where_sql, params = _build_where(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, movement_type=movement_type,
        alert_type=alert_type, severity=severity, risk_band=risk_band,
    )
    # Order: support all columns used by sortable table headers (whitelist).
    _order_whitelist = {
        "risk_score": "a.risk_score",
        "severity": "a.severity",
        "delta_pct": "a.delta_pct",
        "week_start": "a.week_start",
        "driver_key": "a.driver_key",
        "driver_name": "a.driver_name",
        "country": "a.country",
        "city": "a.city",
        "park_name": "a.park_name",
        "segment_current": "a.segment_current",
        "trips_current_week": "a.trips_current_week",
        "avg_trips_baseline": "a.avg_trips_baseline",
        "alert_type": "a.alert_type",
        "risk_band": "a.risk_band",
        "last_trip_date": "lt.last_trip_date",
    }
    order_col = _order_whitelist.get(order_by, "a.risk_score")
    dir_sql = "DESC" if (order_dir or "desc").lower() == "desc" else "ASC"
    if order_by == "risk_score":
        order_secondary = ", a.delta_pct ASC NULLS LAST" if dir_sql == "DESC" else ", a.delta_pct DESC NULLS LAST"
    else:
        order_secondary = ", a.week_start DESC"
    # WHERE for aliased MV (a.): prefix column names so JOIN with lt works.
    where_sql_a = (
        where_sql.replace("LOWER(TRIM(country))", "LOWER(TRIM(a.country))")
        .replace("LOWER(TRIM(city))", "LOWER(TRIM(a.city))")
        .replace("week_start", "a.week_start")
        .replace("park_id", "a.park_id")
        .replace("segment_current", "a.segment_current")
        .replace("movement_type", "a.movement_type")
        .replace("alert_type", "a.alert_type")
        .replace("severity", "a.severity")
        .replace("risk_band", "a.risk_band")
    )
    params.extend([limit, offset])
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = %s", (str(_BEHAVIOR_ALERTS_QUERY_TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT
                    a.driver_key,
                    a.driver_name,
                    a.week_start,
                    a.week_label,
                    a.country,
                    a.city,
                    a.park_id,
                    a.park_name,
                    a.segment_current,
                    a.segment_previous,
                    a.movement_type,
                    a.trips_current_week,
                    a.avg_trips_baseline,
                    a.delta_abs,
                    a.delta_pct,
                    a.alert_type,
                    a.severity,
                    a.risk_score,
                    a.risk_band,
                    a.risk_score_behavior,
                    a.risk_score_migration,
                    a.risk_score_fragility,
                    a.risk_score_value,
                    a.weeks_declining_consecutively,
                    a.weeks_rising_consecutively,
                    lt.last_trip_date
                FROM {_ALERTS_MV} a
                LEFT JOIN {_LAST_TRIP_VIEW} lt ON lt.driver_key = a.driver_key
                WHERE {where_sql_a}
                ORDER BY {order_col} {dir_sql} NULLS LAST {order_secondary}
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute(
                f"SELECT COUNT(*) AS n FROM {_ALERTS_MV} WHERE {where_sql}",
                params[:-2],
            )
            total = cur.fetchone()["n"]
            return {"data": rows, "total": total, "limit": limit, "offset": offset}
        finally:
            cur.close()


def get_behavior_alerts_driver_detail(
    driver_key: str,
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    weeks: int = 8,
) -> dict[str, Any]:
    """Driver timeline: trips, segment, baseline, deviation, alert, risk_score, risk_band, risk_reasons."""
    where_sql, params = _build_where(week_start=week_start, from_date=from_date, to_date=to_date)
    params = [driver_key] + params
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    driver_key,
                    driver_name,
                    week_start,
                    week_label,
                    country,
                    city,
                    park_id,
                    park_name,
                    trips_current_week,
                    segment_current,
                    segment_previous,
                    movement_type,
                    avg_trips_baseline,
                    delta_abs,
                    delta_pct,
                    z_score_simple,
                    alert_type,
                    severity,
                    risk_score,
                    risk_band,
                    risk_score_behavior,
                    risk_score_migration,
                    risk_score_fragility,
                    risk_score_value,
                    weeks_declining_consecutively,
                    weeks_rising_consecutively
                FROM {_ALERTS_SOURCE}
                WHERE driver_key::text = %s AND {where_sql}
                ORDER BY week_start DESC
                LIMIT %s
                """,
                params + [weeks],
            )
            rows = [dict(r) for r in cur.fetchall()]
            risk_reasons: list[str] = []
            if rows:
                r0 = rows[0]
                if r0.get("delta_pct") is not None and float(r0.get("delta_pct", 0)) < 0:
                    risk_reasons.append(f"baseline drop {float(r0['delta_pct']) * 100:.0f}%")
                if (r0.get("weeks_declining_consecutively") or 0) >= 1:
                    risk_reasons.append(f"{r0.get('weeks_declining_consecutively')} consecutive declining weeks")
                if r0.get("movement_type") in ("downshift", "drop") and r0.get("segment_previous"):
                    risk_reasons.append(f"downgrade {r0.get('segment_previous')} -> {r0.get('segment_current', '')}")
                if (r0.get("avg_trips_baseline") or 0) >= 40:
                    risk_reasons.append("historically high-volume driver")
            return {"driver_key": driver_key, "data": rows, "total": len(rows), "risk_reasons": risk_reasons}
        finally:
            cur.close()


def get_behavior_alerts_export(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    movement_type: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    """Export rows with filters. Columns include movement_type, alert_severity (severity), risk_score, risk_band."""
    where_sql, params = _build_where(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, movement_type=movement_type,
        alert_type=alert_type, severity=severity, risk_band=risk_band,
    )
    params.append(max_rows)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("SET statement_timeout = %s", (str(_BEHAVIOR_ALERTS_QUERY_TIMEOUT_MS),))
            cur.execute(
                f"""
                SELECT
                    a.driver_key,
                    a.driver_name,
                    a.country,
                    a.city,
                    a.park_name,
                    a.week_label,
                    a.segment_current,
                    a.movement_type,
                    a.trips_current_week,
                    a.avg_trips_baseline,
                    a.delta_abs,
                    a.delta_pct,
                    a.weeks_declining_consecutively,
                    a.weeks_rising_consecutively,
                    a.alert_type,
                    a.severity AS alert_severity,
                    a.risk_score,
                    a.risk_band,
                    lt.last_trip_date
                FROM {_ALERTS_MV} a
                LEFT JOIN {_LAST_TRIP_VIEW} lt ON lt.driver_key = a.driver_key
                WHERE {where_sql.replace("LOWER(TRIM(country))", "LOWER(TRIM(a.country))").replace("LOWER(TRIM(city))", "LOWER(TRIM(a.city))").replace("week_start", "a.week_start").replace("park_id", "a.park_id").replace("segment_current", "a.segment_current").replace("movement_type", "a.movement_type").replace("alert_type", "a.alert_type").replace("severity", "a.severity").replace("risk_band", "a.risk_band")}
                ORDER BY a.risk_score DESC NULLS LAST, a.delta_pct ASC NULLS LAST, a.week_start DESC
                LIMIT %s
                """,
                params,
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            cur.close()


def get_behavior_alerts_insight(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    movement_type: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    risk_band: Optional[str] = None,
) -> dict[str, Any]:
    """Automated summary text for insight panel; includes high/medium risk counts."""
    summary = get_behavior_alerts_summary(
        week_start=week_start, from_date=from_date, to_date=to_date,
        country=country, city=city, park_id=park_id,
        segment_current=segment_current, movement_type=movement_type,
        alert_type=alert_type, severity=severity, risk_band=risk_band,
    )
    lines = []
    if (summary.get("sudden_stop") or 0) > 0:
        lines.append(f"{summary['sudden_stop']} Sudden Stop (dejaron de producir en la semana analizada).")
    if (summary.get("high_risk_drivers") or 0) > 0:
        lines.append(f"{summary['high_risk_drivers']} conductores en alto riesgo esta semana.")
    if (summary.get("medium_risk_drivers") or 0) > 0:
        lines.append(f"{summary['medium_risk_drivers']} en riesgo medio.")
    if (summary.get("critical_drops") or 0) > 0:
        lines.append(f"{summary['critical_drops']} conductores con caída crítica respecto a su línea base.")
    if (summary.get("moderate_drops") or 0) > 0:
        lines.append(f"{summary['moderate_drops']} con caída moderada.")
    if (summary.get("strong_recoveries") or 0) > 0:
        lines.append(f"{summary['strong_recoveries']} conductores muestran fuerte recuperación vs línea base.")
    if (summary.get("silent_erosion") or 0) > 0:
        lines.append(f"{summary['silent_erosion']} con erosión silenciosa (semanas consecutivas a la baja).")
    if (summary.get("high_volatility") or 0) > 0:
        lines.append(f"{summary['high_volatility']} con alta volatilidad.")
    if (summary.get("stable_performer") or 0) > 0:
        lines.append(f"{summary['stable_performer']} estables.")
    text = " ".join(lines) if lines else "Sin alertas en el rango seleccionado."
    return {"summary": summary, "insight_text": text}
