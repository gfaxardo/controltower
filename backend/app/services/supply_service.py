"""
Control Tower Supply (REAL): parks geo, series semanal/mensual, summary.
Fuente: dim.v_geo_park, ops.mv_supply_weekly, ops.mv_supply_monthly.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


def get_supply_geo(
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> dict[str, Any]:
    """
    Geo para filtros Supply: countries distinct, cities distinct (filtradas por country), parks list.
    Fuente: dim.v_geo_park. Return: { "countries": [...], "cities": [...], "parks": [{ park_id, park_name, city, country }] }.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT park_id, park_name, city, country
                FROM dim.v_geo_park
                ORDER BY country, city, park_name
                """
            )
            rows = [dict(r) for r in cur.fetchall()]
            if not rows:
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM ops.v_dim_park_resolved
                    ORDER BY country NULLS LAST, city NULLS LAST, park_name
                    """
                )
                rows = [dict(r) for r in cur.fetchall()]
            countries = sorted({r["country"] for r in rows if r.get("country")})
            by_country = [r for r in rows if not country or (r.get("country") or "").strip() == country]
            cities = sorted({r["city"] for r in by_country if r.get("city")})
            by_city = [r for r in by_country if not city or (r.get("city") or "").strip() == city]
            parks = by_city
            return {"countries": countries, "cities": cities, "parks": parks}
        except Exception as e:
            logger.warning("get_supply_geo: %s", e)
            return {"countries": [], "cities": [], "parks": []}
        finally:
            cur.close()


def get_supply_parks(
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Lista parks para filtros Supply. Fuente: dim.v_geo_park; fallback ops.v_dim_park_resolved.
    Orden: country, city, park_name. Regla: no mostrar park_id en UI; solo park_name, city, country.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if country and city:
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM dim.v_geo_park
                    WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                      AND LOWER(TRIM(city)) = LOWER(TRIM(%s))
                    ORDER BY park_name
                    """,
                    (country, city),
                )
            elif country:
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM dim.v_geo_park
                    WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                    ORDER BY city, park_name
                    """,
                    (country,),
                )
            else:
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM dim.v_geo_park
                    ORDER BY country, city, park_name
                    """
                )
            rows = [dict(r) for r in cur.fetchall()]
            if not rows:
                # Fallback: parks desde ops.v_dim_park_resolved (misma estructura legible)
                if country and city:
                    cur.execute(
                        """
                        SELECT park_id, park_name, city, country
                        FROM ops.v_dim_park_resolved
                        WHERE LOWER(TRIM(COALESCE(country, ''))) = LOWER(TRIM(%s))
                          AND LOWER(TRIM(COALESCE(city, ''))) = LOWER(TRIM(%s))
                        ORDER BY park_name
                        """,
                        (country, city),
                    )
                elif country:
                    cur.execute(
                        """
                        SELECT park_id, park_name, city, country
                        FROM ops.v_dim_park_resolved
                        WHERE LOWER(TRIM(COALESCE(country, ''))) = LOWER(TRIM(%s))
                        ORDER BY city NULLS LAST, park_name
                        """,
                        (country,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT park_id, park_name, city, country
                        FROM ops.v_dim_park_resolved
                        ORDER BY country NULLS LAST, city NULLS LAST, park_name
                        """
                    )
                rows = [dict(r) for r in cur.fetchall()]
            return rows
        except Exception as e:
            logger.warning("get_supply_parks: %s", e)
            try:
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM ops.v_dim_park_resolved
                    ORDER BY country NULLS LAST, city NULLS LAST, park_name
                    """
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception:
                return []
        finally:
            cur.close()


def get_supply_series(
    park_id: str,
    from_date: str,
    to_date: str,
    grain: str,
) -> list[dict[str, Any]]:
    """
    Serie por periodo (DESC). park_id obligatorio.
    grain: 'weekly' | 'monthly'
    """
    if not park_id or not from_date or not to_date:
        return []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if grain == "monthly":
                cur.execute(
                    """
                    SELECT month_start AS period_start, park_id, park_name, city, country,
                           activations, active_drivers, churned, reactivated,
                           churn_rate, reactivation_rate, net_growth
                    FROM ops.mv_supply_monthly
                    WHERE park_id = %s AND month_start >= %s::date AND month_start <= %s::date
                    ORDER BY month_start DESC
                    """,
                    (park_id, from_date, to_date),
                )
            else:
                cur.execute(
                    """
                    SELECT week_start AS period_start, park_id, park_name, city, country,
                           activations, active_drivers, churned, reactivated,
                           churn_rate, reactivation_rate, net_growth
                    FROM ops.mv_supply_weekly
                    WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                    ORDER BY week_start DESC
                    """,
                    (park_id, from_date, to_date),
                )
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("get_supply_series: %s", e)
            return []
        finally:
            cur.close()


def get_supply_summary(
    park_id: str,
    from_date: str,
    to_date: str,
    grain: str,
) -> dict[str, Any]:
    """
    Resumen del rango: sumas y promedios ponderados.
    """
    series = get_supply_series(park_id, from_date, to_date, grain)
    if not series:
        return {
            "activations_sum": 0,
            "churned_sum": 0,
            "reactivated_sum": 0,
            "net_growth_sum": 0,
            "active_drivers_last_period": None,
            "churn_rate_weighted": None,
            "reactivation_rate_weighted": None,
            "periods_count": 0,
        }

    activations_sum = sum((r.get("activations") or 0) for r in series)
    churned_sum = sum((r.get("churned") or 0) for r in series)
    reactivated_sum = sum((r.get("reactivated") or 0) for r in series)
    net_growth_sum = sum((r.get("net_growth") or 0) for r in series)
    # Último periodo del rango (más reciente) = primera fila (orden DESC)
    active_drivers_last = series[0].get("active_drivers") if series else None

    total_active = sum((r.get("active_drivers") or 0) for r in series)
    if total_active and churned_sum is not None:
        churn_rate_weighted = round(100.0 * churned_sum / total_active, 4)
    else:
        churn_rate_weighted = None
    base_react = total_active - churned_sum + reactivated_sum if total_active is not None else 0
    if base_react and reactivated_sum is not None:
        reactivation_rate_weighted = round(100.0 * reactivated_sum / base_react, 4)
    else:
        reactivation_rate_weighted = None

    return {
        "activations_sum": activations_sum,
        "churned_sum": churned_sum,
        "reactivated_sum": reactivated_sum,
        "net_growth_sum": net_growth_sum,
        "active_drivers_last_period": active_drivers_last,
        "churn_rate_weighted": churn_rate_weighted,
        "reactivation_rate_weighted": reactivation_rate_weighted,
        "periods_count": len(series),
    }


def get_supply_global_series(
    from_date: str,
    to_date: str,
    grain: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Agregado global por periodo (opcionalmente por country/city).
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            if grain == "monthly":
                if country and city:
                    cur.execute(
                        """
                        SELECT month_start AS period_start, country, city,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_monthly
                        WHERE month_start >= %s::date AND month_start <= %s::date
                          AND LOWER(TRIM(country)) = LOWER(TRIM(%s))
                          AND LOWER(TRIM(city)) = LOWER(TRIM(%s))
                        GROUP BY month_start, country, city
                        ORDER BY month_start DESC
                        """,
                        (from_date, to_date, country, city),
                    )
                elif country:
                    cur.execute(
                        """
                        SELECT month_start AS period_start, country, city,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_monthly
                        WHERE month_start >= %s::date AND month_start <= %s::date
                          AND LOWER(TRIM(country)) = LOWER(TRIM(%s))
                        GROUP BY month_start, country, city
                        ORDER BY month_start DESC
                        """,
                        (from_date, to_date, country),
                    )
                else:
                    cur.execute(
                        """
                        SELECT month_start AS period_start,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_monthly
                        WHERE month_start >= %s::date AND month_start <= %s::date
                        GROUP BY month_start
                        ORDER BY month_start DESC
                        """,
                        (from_date, to_date),
                    )
            else:
                if country and city:
                    cur.execute(
                        """
                        SELECT week_start AS period_start, country, city,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_weekly
                        WHERE week_start >= %s::date AND week_start <= %s::date
                          AND LOWER(TRIM(country)) = LOWER(TRIM(%s))
                          AND LOWER(TRIM(city)) = LOWER(TRIM(%s))
                        GROUP BY week_start, country, city
                        ORDER BY week_start DESC
                        """,
                        (from_date, to_date, country, city),
                    )
                elif country:
                    cur.execute(
                        """
                        SELECT week_start AS period_start, country, city,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_weekly
                        WHERE week_start >= %s::date AND week_start <= %s::date
                          AND LOWER(TRIM(country)) = LOWER(TRIM(%s))
                        GROUP BY week_start, country, city
                        ORDER BY week_start DESC
                        """,
                        (from_date, to_date, country),
                    )
                else:
                    cur.execute(
                        """
                        SELECT week_start AS period_start,
                               SUM(activations) AS activations,
                               SUM(active_drivers) AS active_drivers,
                               SUM(churned) AS churned,
                               SUM(reactivated) AS reactivated,
                               SUM(net_growth) AS net_growth
                        FROM ops.mv_supply_weekly
                        WHERE week_start >= %s::date AND week_start <= %s::date
                        GROUP BY week_start
                        ORDER BY week_start DESC
                        """,
                        (from_date, to_date),
                    )
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_supply_global_series: %s", e)
            return []
        finally:
            cur.close()


def get_supply_segments_series(
    park_id: str,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """
    Serie de segmentos por semana (ops.mv_supply_segments_weekly).
    park_id obligatorio. Orden: week_start DESC.
    """
    if not park_id or not from_date or not to_date:
        return []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                SELECT week_start, segment_week, drivers_count, trips_sum, share_of_active,
                       park_name, city, country
                FROM ops.mv_supply_segments_weekly
                WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                ORDER BY week_start DESC, segment_week
                """,
                (park_id, from_date, to_date),
            )
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_supply_segments_series: %s", e)
            return []
        finally:
            cur.close()


def get_supply_alerts(
    week_start_from: Optional[str] = None,
    week_start_to: Optional[str] = None,
    park_id: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Alertas Supply PRO (ops.mv_supply_alerts_weekly).
    Filtros opcionales: rango de semanas, park_id, country, city, alert_type (segment_drop/segment_spike), severity (P0..P3).
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            q = """
                SELECT week_start, park_id, park_name, city, country, segment_week,
                       alert_type, severity, baseline_avg, current_value, delta_pct,
                       message_short, recommended_action
                FROM ops.mv_supply_alerts_weekly
                WHERE 1=1
            """
            params: list[Any] = []
            if week_start_from:
                q += " AND week_start >= %s::date"
                params.append(week_start_from)
            if week_start_to:
                q += " AND week_start <= %s::date"
                params.append(week_start_to)
            if park_id:
                q += " AND park_id = %s"
                params.append(park_id)
            if country:
                q += " AND LOWER(TRIM(COALESCE(country, ''))) = LOWER(TRIM(%s))"
                params.append(country)
            if city:
                q += " AND LOWER(TRIM(COALESCE(city, ''))) = LOWER(TRIM(%s))"
                params.append(city)
            if alert_type:
                q += " AND alert_type = %s"
                params.append(alert_type)
            if severity:
                q += " AND severity = %s"
                params.append(severity)
            q += " ORDER BY week_start DESC, park_id, segment_week, alert_type LIMIT %s"
            params.append(limit)
            cur.execute(q, params)
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_supply_alerts: %s", e)
            return []
        finally:
            cur.close()


def get_supply_alert_drilldown(
    week_start: str,
    park_id: str,
    segment_week: Optional[str] = None,
    alert_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Conductores afectados por una alerta (ops.v_supply_alert_drilldown).
    Filtra por week_start, park_id; opcional segment_week. Orden: impacto (baseline_trips_4w_avg DESC).
    """
    if not week_start or not park_id:
        return []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            q = """
                SELECT driver_key, week_start, park_id, segment_week_current,
                       prev_segment_week, trips_completed_week, baseline_trips_4w_avg, segment_change_type
                FROM ops.v_supply_alert_drilldown
                WHERE week_start = %s::date AND park_id = %s
            """
            params: list[Any] = [week_start, park_id]
            if segment_week:
                q += " AND segment_week = %s"
                params.append(segment_week)
            q += " ORDER BY baseline_trips_4w_avg DESC NULLS LAST"
            cur.execute(q, params)
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_supply_alert_drilldown: %s", e)
            return []
        finally:
            cur.close()


def refresh_supply_alerting_mvs() -> None:
    """Ejecuta ops.refresh_supply_alerting_mvs() (REFRESH CONCURRENTLY de las 4 MVs)."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT ops.refresh_supply_alerting_mvs()")
            conn.commit()
        except Exception as e:
            logger.warning("refresh_supply_alerting_mvs: %s", e)
            raise
        finally:
            cur.close()
