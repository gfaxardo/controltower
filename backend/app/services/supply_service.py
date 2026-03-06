"""
Control Tower Supply (REAL): parks geo, series semanal/mensual, summary.
Fuente: dim.v_geo_park, ops.mv_supply_weekly, ops.mv_supply_monthly.
"""
from __future__ import annotations

from typing import Any, Optional
from app.db.connection import get_db
from app.services.supply_definitions import format_iso_week
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
                SELECT a.week_start, a.park_id, a.park_name, a.city, a.country, a.segment_week,
                       a.alert_type, a.severity,
                       a.baseline_avg AS baseline_mean, anom.baseline_std, anom.z_score,
                       a.current_value, a.delta_pct,
                       a.message_short, a.recommended_action
                FROM ops.mv_supply_alerts_weekly a
                LEFT JOIN ops.mv_supply_segment_anomalies_weekly anom
                  ON anom.week_start = a.week_start AND anom.park_id = a.park_id AND anom.segment_week = a.segment_week
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
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["priority_label"] = _alert_priority_label(r.get("severity"))
                r["week_display"] = format_iso_week(r.get("week_start"))
                r["baseline_mean"] = r.get("baseline_mean")  # alias from baseline_avg
                _add_alert_trend_context(r)
            return rows
        except Exception as e:
            logger.warning("get_supply_alerts: %s", e)
            return []
        finally:
            cur.close()


def _add_alert_trend_context(r: dict[str, Any]) -> None:
    """
    Añade contexto de tendencia a una fila de alerta (sin historial multi-semana).
    Regla: baseline en anomalías es 8w → baseline_window_weeks=8; current_vs_rolling_8w_delta = delta_pct.
    trend_context: sustained_deterioration (segment_drop), recovery/abrupt_change (segment_spike).
    abrupt_change: True si |delta_pct| >= 0.25 (cambio fuerte en una semana).
    """
    r["baseline_window_weeks"] = 8
    r["current_vs_rolling_4w_delta"] = None
    r["current_vs_rolling_8w_delta"] = r.get("delta_pct")
    atype = r.get("alert_type") or ""
    delta = r.get("delta_pct")
    delta_abs = abs(delta) if delta is not None else 0
    r["abrupt_change"] = delta_abs >= 0.25 if delta is not None else False
    r["sustained_deterioration"] = atype == "segment_drop"
    r["recovery"] = atype == "segment_spike"
    r["stable"] = False
    r["weeks_in_same_direction"] = None
    if atype == "segment_drop":
        r["trend_context"] = "abrupt_change" if r["abrupt_change"] else "sustained_deterioration"
    elif atype == "segment_spike":
        r["trend_context"] = "abrupt_change" if r["abrupt_change"] else "recovery"
    else:
        r["trend_context"] = "stable"


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
    log_supply_refresh_done("ok")


def log_supply_refresh_done(status: str = "ok", error_message: Optional[str] = None) -> None:
    """Registra una corrida de refresh en ops.supply_refresh_log (si existe la tabla)."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO ops.supply_refresh_log (started_at, finished_at, status, error_message)
                VALUES (now(), now(), %s, %s)
            """, (status, error_message[:500] if error_message else None))
            conn.commit()
    except Exception as e:
        logger.debug("log_supply_refresh_done (tabla puede no existir): %s", e)


def get_supply_segment_config() -> list[dict[str, Any]]:
    """
    Configuración de segmentos desde ops.driver_segment_config (en lugar de umbrales hardcodeados).
    Devuelve segment, min_trips, max_trips, priority (ordering). Solo filas is_active y vigentes (effective_from/to).
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT segment_code AS segment, min_trips_week AS min_trips, max_trips_week AS max_trips,
                       ordering AS priority
                FROM ops.driver_segment_config
                WHERE is_active
                  AND effective_from <= CURRENT_DATE
                  AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
                ORDER BY ordering DESC
            """)
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_supply_segment_config: %s (tabla puede no existir)", e)
            return []
        finally:
            cur.close()


def get_supply_freshness() -> dict[str, Any]:
    """
    Devuelve última semana disponible, última corrida de refresh y estado del pipeline.
    Regla: expected_week = lunes de la semana actual (floor_to_week(now));
    Fresh si last_week_available >= expected_week - 7 días y last_refresh >= ahora - 36 h.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT MAX(week_start) AS last_week_available
                FROM ops.mv_supply_segments_weekly
            """)
            row_week = cur.fetchone()
            last_week = row_week["last_week_available"] if row_week else None

            cur.execute("""
                SELECT finished_at AS last_refresh
                FROM ops.supply_refresh_log
                WHERE status = 'ok' AND finished_at IS NOT NULL
                ORDER BY finished_at DESC
                LIMIT 1
            """)
            row_refresh = cur.fetchone()
            last_refresh = row_refresh["last_refresh"] if row_refresh else None

            status = "unknown"
            if last_week is not None and last_refresh is not None:
                from datetime import datetime, timedelta, timezone
                now = datetime.now(timezone.utc)
                week_date = last_week.date() if hasattr(last_week, "date") else None
                if isinstance(last_week, str):
                    try:
                        from datetime import date as _d
                        week_date = _d.fromisoformat(last_week[:10])
                    except Exception:
                        week_date = None
                if week_date is not None:
                    today = now.date()
                    expected_week = today - timedelta(days=today.weekday())
                    expected_week_minus_7 = expected_week - timedelta(days=7)
                    cutoff_refresh = now - timedelta(hours=36)
                    refresh_ts = last_refresh
                    if getattr(refresh_ts, "tzinfo", None) is None:
                        refresh_ts = refresh_ts.replace(tzinfo=timezone.utc)
                    if week_date >= expected_week_minus_7 and refresh_ts >= cutoff_refresh:
                        status = "fresh"
                    else:
                        status = "stale"

            def _ser_date(v):
                if v is None:
                    return None
                if hasattr(v, "isoformat"):
                    return v.isoformat()[:10]
                return str(v)[:10]

            def _ser_ts(v):
                if v is None:
                    return None
                return v.isoformat() if hasattr(v, "isoformat") else str(v)

            return {
                "last_week_available": _ser_date(last_week),
                "last_refresh": _ser_ts(last_refresh),
                "status": status,
            }
        except Exception as e:
            logger.warning("get_supply_freshness: %s", e)
            return {"last_week_available": None, "last_refresh": None, "status": "unknown"}
        finally:
            cur.close()


# ─── Overview enhanced (trips, shares, WoW) ─────────────────────────────────
def get_supply_overview_enhanced(
    park_id: str,
    from_date: str,
    to_date: str,
    grain: str,
) -> dict[str, Any]:
    """
    Overview enriquecido: series con trips, avg_trips_per_driver, FT_share, PT_share,
    weak_supply_share; cuando grain=weekly añade métricas WoW (drivers_wow_pct, trips_wow_pct, etc.).
    No modifica MVs; calcula desde ops.mv_supply_weekly + ops.mv_supply_segments_weekly.
    """
    if not park_id or not from_date or not to_date:
        return {"summary": {}, "series": [], "series_with_wow": []}
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            period_col = "week_start" if grain == "weekly" else "month_start"
            table = "ops.mv_supply_weekly" if grain == "weekly" else "ops.mv_supply_monthly"
            cur.execute(
                f"""
                SELECT {period_col} AS period_start, park_id, park_name, city, country,
                       activations, active_drivers, churned, reactivated,
                       churn_rate, reactivation_rate, net_growth
                FROM {table}
                WHERE park_id = %s AND {period_col} >= %s::date AND {period_col} <= %s::date
                ORDER BY {period_col} DESC
                """,
                (park_id, from_date, to_date),
            )
            series_base = [dict(r) for r in cur.fetchall()]
            if not series_base:
                return {
                    "summary": {},
                    "series": [],
                    "series_with_wow": [],
                }
            period_ids = [str(r["period_start"]) for r in series_base]
            if grain == "weekly":
                cur.execute(
                    """
                    SELECT week_start, park_id,
                           SUM(trips_sum) AS trips,
                           SUM(drivers_count) FILTER (WHERE segment_week = 'FT') AS ft_drivers,
                           SUM(drivers_count) FILTER (WHERE segment_week = 'PT') AS pt_drivers,
                           SUM(drivers_count) FILTER (WHERE segment_week IN ('CASUAL', 'OCCASIONAL')) AS weak_drivers
                    FROM ops.mv_supply_segments_weekly
                    WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                    GROUP BY week_start, park_id
                    ORDER BY week_start DESC
                    """,
                    (park_id, from_date, to_date),
                )
                seg_rows = {str(r["week_start"]): dict(r) for r in cur.fetchall()}
            else:
                seg_rows = {}
            for row in series_base:
                pid = str(row["period_start"])
                ad = row.get("active_drivers") or 0
                seg = seg_rows.get(pid) or {}
                trips = int(seg.get("trips") or 0)
                ft_d = int(seg.get("ft_drivers") or 0)
                pt_d = int(seg.get("pt_drivers") or 0)
                weak_d = int(seg.get("weak_drivers") or 0)
                row["trips"] = trips
                row["avg_trips_per_driver"] = round(trips / ad, 4) if ad else None
                row["FT_share"] = round(100.0 * ft_d / ad, 4) if ad else None
                row["PT_share"] = round(100.0 * pt_d / ad, 4) if ad else None
                row["weak_supply_share"] = round(100.0 * weak_d / ad, 4) if ad else None
                row["period_display"] = format_iso_week(row.get("period_start")) if grain == "weekly" else str(row.get("period_start", ""))[:7]
            summary = _build_overview_summary(series_base, grain)
            if grain == "weekly" and len(series_base) >= 1:
                summary["period_label"] = f"{format_iso_week(series_base[-1].get('period_start'))} → {format_iso_week(series_base[0].get('period_start'))}"
                summary["period_weeks_count"] = len(series_base)
            elif series_base:
                summary["period_label"] = str(series_base[0].get("period_start", ""))[:10]
                summary["period_weeks_count"] = len(series_base)
            if grain == "weekly":
                _add_rolling_and_trend(series_base, summary)
            series_with_wow: list[dict[str, Any]] = []
            if grain == "weekly" and len(series_base) >= 2:
                for i, row in enumerate(series_base):
                    r = dict(row)
                    prev = series_base[i + 1] if i + 1 < len(series_base) else None
                    if prev:
                        _add_wow(r, prev, is_share=False)
                    series_with_wow.append(r)
            else:
                series_with_wow = [dict(r) for r in series_base]
            return {
                "summary": summary,
                "series": series_base,
                "series_with_wow": series_with_wow,
            }
        except Exception as e:
            logger.warning("get_supply_overview_enhanced: %s", e)
            return {"summary": {}, "series": [], "series_with_wow": []}
        finally:
            cur.close()


def _build_overview_summary(series_base: list[dict], grain: str) -> dict[str, Any]:
    """Summary del último periodo + sumas para el rango. growth_rate = (active_N - active_N-1) / active_N-1."""
    if not series_base:
        return {}
    last = series_base[0]
    ad = last.get("active_drivers") or 0
    trips = last.get("trips") or 0
    ft_sh = last.get("FT_share")
    pt_sh = last.get("PT_share")
    weak_sh = last.get("weak_supply_share")
    out = {
        "activations_sum": sum((r.get("activations") or 0) for r in series_base),
        "churned_sum": sum((r.get("churned") or 0) for r in series_base),
        "reactivated_sum": sum((r.get("reactivated") or 0) for r in series_base),
        "net_growth_sum": sum((r.get("net_growth") or 0) for r in series_base),
        "active_drivers_last_period": last.get("active_drivers"),
        "churn_rate_weighted": last.get("churn_rate"),
        "reactivation_rate_weighted": last.get("reactivation_rate"),
        "periods_count": len(series_base),
        "trips": trips,
        "avg_trips_per_driver": round(trips / ad, 4) if ad else None,
        "FT_share": ft_sh,
        "PT_share": pt_sh,
        "weak_supply_share": weak_sh,
    }
    if len(series_base) >= 2:
        prev_ad = series_base[1].get("active_drivers") or 0
        if prev_ad and (ad is not None or last.get("active_drivers") is not None):
            out["growth_rate"] = round((ad - prev_ad) / prev_ad, 6)
        else:
            out["growth_rate"] = None
    else:
        out["growth_rate"] = None
    return out


def _add_rolling_and_trend(series_base: list[dict], summary: dict[str, Any]) -> None:
    """
    Añade al summary: rolling_4w_*, rolling_8w_*, trend_direction.
    Regla: series_base ordenado por periodo DESC (más reciente primero).
    - rolling_4w = media de las últimas 4 semanas; rolling_8w = media de las últimas 8.
    - trend_direction: compara media(0:4) vs media(4:8) en active_drivers;
      si recent_4 > prev_4 -> 'up', recent_4 < prev_4 -> 'down', sino 'flat'.
    Semanas insuficientes: campos null; trend_direction null si < 8 semanas.
    """
    if not series_base:
        return
    n = len(series_base)
    for key, getter in [
        ("active_drivers", lambda r: r.get("active_drivers") or 0),
        ("trips", lambda r: r.get("trips") or 0),
        ("FT_share", lambda r: r.get("FT_share")),
        ("weak_supply_share", lambda r: r.get("weak_supply_share")),
    ]:
        vals = [getter(r) for r in series_base]
        if key in ("FT_share", "weak_supply_share"):
            v4 = [v for v in vals[:4] if v is not None]
            v8 = [v for v in vals[:8] if v is not None]
            avg4 = round(sum(v4) / len(v4), 4) if len(v4) >= 4 else None
            avg8 = round(sum(v8) / len(v8), 4) if len(v8) >= 8 else None
        else:
            avg4 = round(sum(vals[:4]) / 4, 4) if n >= 4 else None
            avg8 = round(sum(vals[:8]) / 8, 4) if n >= 8 else None
        summary[f"rolling_4w_{key}"] = avg4
        summary[f"rolling_8w_{key}"] = avg8
    # trend_direction basado en active_drivers (últimas 4 vs 4 anteriores)
    if n >= 8:
        recent_4 = sum((r.get("active_drivers") or 0) for r in series_base[:4]) / 4
        prev_4 = sum((r.get("active_drivers") or 0) for r in series_base[4:8]) / 4
        if recent_4 > prev_4:
            summary["trend_direction"] = "up"
        elif recent_4 < prev_4:
            summary["trend_direction"] = "down"
        else:
            summary["trend_direction"] = "flat"
    else:
        summary["trend_direction"] = None


def _add_wow(
    current: dict,
    previous: dict,
    *,
    is_share: bool = False,
) -> None:
    """Añade campos WoW a current (drivers_wow_pct, trips_wow_pct o share_wow_pp)."""
    def pct(cur: Any, prev: Any) -> Optional[float]:
        if prev is None or prev == 0:
            return None
        c = (cur or 0)
        return round(100.0 * (c - prev) / prev, 4) if prev else None

    def pp(cur: Any, prev: Any) -> Optional[float]:
        if cur is None and prev is None:
            return None
        return round((cur or 0) - (prev or 0), 4)

    ad_cur = current.get("active_drivers") or 0
    ad_prev = previous.get("active_drivers") or 0
    current["drivers_wow_pct"] = pct(ad_cur, ad_prev)
    current["trips_wow_pct"] = pct(current.get("trips"), previous.get("trips"))
    atpd_cur = current.get("avg_trips_per_driver")
    atpd_prev = previous.get("avg_trips_per_driver")
    current["avg_trips_per_driver_wow_pct"] = pct(atpd_cur, atpd_prev)
    current["FT_share_wow_pp"] = pp(current.get("FT_share"), previous.get("FT_share"))
    current["PT_share_wow_pp"] = pp(current.get("PT_share"), previous.get("PT_share"))
    current["weak_supply_share_wow_pp"] = pp(current.get("weak_supply_share"), previous.get("weak_supply_share"))


# ─── Composition (segments + WoW) ───────────────────────────────────────────
def get_supply_composition(
    park_id: str,
    from_date: str,
    to_date: str,
) -> list[dict[str, Any]]:
    """
    Composición semanal por segmento con WoW. Fuente: ops.mv_supply_segments_weekly.
    Campos: week_start, segment_week, drivers_count, trips_sum, share_of_active,
    avg_trips_per_driver, drivers_wow_pct, trips_wow_pct, share_wow_pp.
    """
    if not park_id or not from_date or not to_date:
        return []
    raw = get_supply_segments_series(park_id, from_date, to_date)
    if not raw:
        return []
    # Total trips per week (park) para supply_contribution
    week_trips_total: dict[str, float] = {}
    for r in raw:
        w = str(r["week_start"])
        week_trips_total[w] = week_trips_total.get(w, 0) + (r.get("trips_sum") or 0)
    by_key: dict[tuple[str, str], dict] = {}
    for r in raw:
        k = (str(r["week_start"]), str(r.get("segment_week") or ""))
        by_key[k] = dict(r)
        ad = r.get("drivers_count") or 0
        ts = r.get("trips_sum") or 0
        by_key[k]["avg_trips_per_driver"] = round(ts / ad, 4) if ad else None
        tot = week_trips_total.get(str(r["week_start"])) or 0
        by_key[k]["supply_contribution"] = round(100.0 * ts / tot, 4) if tot else None
    weeks = sorted({r["week_start"] for r in raw}, reverse=True)
    for i, w in enumerate(weeks):
        prev_week = weeks[i + 1] if i + 1 < len(weeks) else None
        for seg in ("FT", "PT", "CASUAL", "OCCASIONAL", "DORMANT"):
            k = (str(w), seg)
            if k not in by_key:
                continue
            row = by_key[k]
            if prev_week:
                pk = (str(prev_week), seg)
                prev = by_key.get(pk)
                if prev:
                    row["drivers_wow_pct"] = _wow_pct(row.get("drivers_count"), prev.get("drivers_count"))
                    row["trips_wow_pct"] = _wow_pct(row.get("trips_sum"), prev.get("trips_sum"))
                    row["share_wow_pp"] = _wow_pp(row.get("share_of_active"), prev.get("share_of_active"))
                    dc_cur = row.get("drivers_count") or 0
                    dc_prev = prev.get("drivers_count") or 0
                    row["delta_drivers"] = dc_cur - dc_prev if (dc_cur is not None and dc_prev is not None) else None
                    row["delta_share"] = _wow_pp(row.get("share_of_active"), prev.get("share_of_active"))
                else:
                    row["drivers_wow_pct"] = None
                    row["trips_wow_pct"] = None
                    row["share_wow_pp"] = None
                    row["delta_drivers"] = None
                    row["delta_share"] = None
            else:
                row["drivers_wow_pct"] = None
                row["trips_wow_pct"] = None
                row["share_wow_pp"] = None
                row["delta_drivers"] = None
                row["delta_share"] = None
    # Rolling y trend por (week, segment): misma regla que overview (últimas 4 vs 4 anteriores)
    for i, w in enumerate(weeks):
        for seg in ("FT", "PT", "CASUAL", "OCCASIONAL", "DORMANT"):
            k = (str(w), seg)
            if k not in by_key:
                continue
            row = by_key[k]
            seg_4 = [by_key.get((str(weeks[i + j]), seg)) for j in range(4) if i + j < len(weeks)]
            seg_4 = [x for x in seg_4 if x is not None]
            drivers_4 = [x.get("drivers_count") or 0 for x in seg_4]
            row["rolling_4w_drivers_count"] = round(sum(drivers_4) / len(drivers_4), 4) if len(drivers_4) >= 4 else None
            seg_8 = [by_key.get((str(weeks[i + j]), seg)) for j in range(8) if i + j < len(weeks)]
            seg_8 = [x for x in seg_8 if x is not None]
            drivers_8 = [x.get("drivers_count") or 0 for x in seg_8]
            row["rolling_8w_drivers_count"] = round(sum(drivers_8) / len(drivers_8), 4) if len(drivers_8) >= 8 else None
            if i + 8 <= len(weeks):
                recent_4 = sum(by_key.get((str(weeks[i + j]), seg), {}).get("drivers_count") or 0 for j in range(4)) / 4
                prev_4 = sum(by_key.get((str(weeks[i + j]), seg), {}).get("drivers_count") or 0 for j in range(4, 8)) / 4
                if recent_4 > prev_4:
                    row["trend_direction"] = "up"
                elif recent_4 < prev_4:
                    row["trend_direction"] = "down"
                else:
                    row["trend_direction"] = "flat"
            else:
                row["trend_direction"] = None
    seg_order = {"FT": 0, "PT": 1, "CASUAL": 2, "OCCASIONAL": 3, "DORMANT": 4}
    out = list(by_key.values())
    for r in out:
        r["week_display"] = format_iso_week(r.get("week_start"))
    out.sort(key=lambda r: (r.get("week_start"), -seg_order.get(str(r.get("segment_week")), 99)), reverse=True)
    return out


def _wow_pct(cur: Any, prev: Any) -> Optional[float]:
    if prev is None or prev == 0:
        return None
    c = (cur or 0)
    return round(100.0 * (c - prev) / prev, 4)


def _wow_pp(cur: Any, prev: Any) -> Optional[float]:
    if cur is None and prev is None:
        return None
    return round((cur or 0) - (prev or 0), 4)


# ─── Migration (from_segment → to_segment) ───────────────────────────────────
def get_supply_migration(
    park_id: str,
    from_date: str,
    to_date: str,
) -> dict[str, Any]:
    """
    Agregados de migración por semana: from_segment, to_segment, drivers_migrated, migration_type.
    migration_rate = drivers_migrated / drivers_in_from_segment_previous_week (magnitud real).
    Devuelve { "data": [...], "summary": { "upgrades", "downgrades", "drops", "revivals" } } (summary = suma de drivers_migrated por tipo).
    Fuente: ops.mv_driver_segments_weekly; drivers en from_segment semana previa desde mv_supply_segments_weekly.
    """
    if not park_id or not from_date or not to_date:
        return {"data": [], "summary": {"upgrades": 0, "downgrades": 0, "drops": 0, "revivals": 0}}
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute(
                """
                WITH m AS (
                    SELECT week_start, park_id,
                           prev_segment_week AS from_segment,
                           segment_week AS to_segment,
                           segment_change_type,
                           COUNT(*)::bigint AS drivers_migrated
                    FROM ops.mv_driver_segments_weekly
                    WHERE park_id = %s AND week_start >= %s::date AND week_start <= %s::date
                      AND (prev_segment_week IS NOT NULL OR segment_change_type = 'new')
                    GROUP BY week_start, park_id, prev_segment_week, segment_week, segment_change_type
                )
                SELECT m.week_start, m.park_id, m.from_segment, m.to_segment, m.segment_change_type, m.drivers_migrated,
                       prev.drivers_count AS drivers_in_from_segment_previous_week
                FROM m
                LEFT JOIN ops.mv_supply_segments_weekly prev
                  ON prev.park_id = m.park_id
                 AND prev.week_start = m.week_start - 7
                 AND prev.segment_week = m.from_segment
                ORDER BY m.week_start DESC, m.from_segment, m.to_segment
                """,
                (park_id, from_date, to_date),
            )
            rows = [dict(r) for r in cur.fetchall()]
            type_map = {"upshift": "upgrade", "downshift": "downgrade", "drop": "drop", "new": "revival", "stable": "lateral"}
            for r in rows:
                r["migration_type"] = type_map.get(r.get("segment_change_type") or "", r.get("segment_change_type"))
                r["week_display"] = format_iso_week(r.get("week_start"))
                den = r.get("drivers_in_from_segment_previous_week")
                if den is not None and den and (r.get("drivers_migrated") or 0) is not None:
                    r["migration_rate"] = round((r["drivers_migrated"] or 0) / den, 6)
                else:
                    r["migration_rate"] = None
            summary = {"upgrades": 0, "downgrades": 0, "drops": 0, "revivals": 0}
            for r in rows:
                t = r.get("migration_type")
                n = r.get("drivers_migrated") or 0
                if t == "upgrade":
                    summary["upgrades"] += n
                elif t == "downgrade":
                    summary["downgrades"] += n
                elif t == "drop":
                    summary["drops"] += n
                elif t == "revival":
                    summary["revivals"] += n
            return {"data": rows, "summary": summary}
        except Exception as e:
            logger.warning("get_supply_migration: %s", e)
            return {"data": [], "summary": {"upgrades": 0, "downgrades": 0, "drops": 0, "revivals": 0}}
        finally:
            cur.close()


def get_supply_migration_drilldown(
    park_id: str,
    week_start: str,
    from_segment: Optional[str] = None,
    to_segment: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Lista de drivers que migraron en una semana (park, from_segment → to_segment).
    Fuente: ops.mv_driver_segments_weekly.
    """
    if not park_id or not week_start:
        return []
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            q = """
                SELECT driver_key, week_start, park_id, prev_segment_week AS from_segment,
                       segment_week AS to_segment, segment_change_type,
                       trips_completed_week, baseline_trips_4w_avg
                FROM ops.mv_driver_segments_weekly
                WHERE park_id = %s AND week_start = %s::date
            """
            params: list[Any] = [park_id, week_start]
            if from_segment:
                q += " AND prev_segment_week = %s"
                params.append(from_segment)
            if to_segment:
                q += " AND segment_week = %s"
                params.append(to_segment)
            q += " ORDER BY baseline_trips_4w_avg DESC NULLS LAST"
            cur.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
            type_map = {"upshift": "upgrade", "downshift": "downgrade", "drop": "drop", "new": "revival", "stable": "lateral"}
            for r in rows:
                r["migration_type"] = type_map.get(r.get("segment_change_type") or "", r.get("segment_change_type"))
            return rows
        except Exception as e:
            logger.warning("get_supply_migration_drilldown: %s", e)
            return []
        finally:
            cur.close()


def _alert_priority_label(severity: Optional[str]) -> str:
    """Mapeo P0/P1→High, P2→Medium, P3→Low."""
    if not severity:
        return "Low"
    s = (severity or "").strip().upper()
    if s in ("P0", "P1"):
        return "High"
    if s == "P2":
        return "Medium"
    if s == "P3":
        return "Low"
    return "Low"
