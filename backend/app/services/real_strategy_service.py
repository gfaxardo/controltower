"""
Real LOB Strategy: KPIs ejecutivos, forecast (solo país y LOB_GROUP), rankings.
Lee de ops.v_real_country_month_forecast, v_real_country_lob_month, v_real_country_city_month.
No toca Plan vs Real REALKEY.
"""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

VIEW_COUNTRY_FORECAST = "ops.v_real_country_month_forecast"
VIEW_COUNTRY_LOB = "ops.v_real_country_lob_month"
VIEW_COUNTRY_CITY = "ops.v_real_country_city_month"
VIEW_COUNTRY_BASE = "ops.v_real_country_month"
STRATEGY_TIMEOUT_MS = 20000


def _default_month(cursor, country: str, year_real: Optional[int] = None) -> Optional[str]:
    if year_real is not None:
        cursor.execute(
            """
            SELECT MAX(month_start)::TEXT AS m FROM ops.v_real_country_month
            WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
              AND month_start >= %s::DATE AND month_start <= %s::DATE
            """,
            (country, f"{year_real}-01-01", f"{year_real}-12-31"),
        )
    else:
        cursor.execute(
            """
            SELECT MAX(month_start)::TEXT AS m FROM ops.v_real_country_month
            WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
            """,
            (country,),
        )
    r = cursor.fetchone()
    return r.get("m") if r and r.get("m") else None


def get_real_strategy_country(
    country: str,
    year_real: Optional[int] = None,
    segment_tag: Optional[str] = None,
    period_type: str = "monthly",
) -> Dict[str, Any]:
    """
    GET /ops/real-strategy/country
    country required. Default: último mes disponible.
    Retorna: kpis (total_trips_ytd, growth_mom, b2b_ratio, forecast_next_month, forecast_growth,
            acceleration_index, concentration_index), trend, forecast, rankings (top cities).
    """
    if not country or not str(country).strip():
        return {"error": "country is required", "kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    out: Dict[str, Any] = {"kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(STRATEGY_TIMEOUT_MS),))
            # Mes por defecto (si year_real, último mes de ese año)
            default_m = _default_month(cur, country, year_real)
            if not default_m:
                return out
            if year_real is not None:
                where_period = "month_start >= %s::DATE AND month_start <= %s::DATE"
                params_period = [f"{year_real}-01-01", f"{year_real}-12-31"]
            else:
                where_period = "month_start = %s::DATE"
                params_period = [default_m]
            # Trend: últimos 12 meses (orden month_start DESC)
            cur.execute(
                f"""
                SELECT country, month_start, trips, trips_prev, growth_mom, b2b_trips, b2b_ratio,
                       forecast_next_month, forecast_growth, acceleration_index
                FROM {VIEW_COUNTRY_FORECAST}
                WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                  AND month_start <= %s::DATE
                  AND month_start >= (%s::DATE - INTERVAL '11 months')::DATE
                ORDER BY month_start DESC
                LIMIT 12
                """,
                (country, default_m, default_m),
            )
            trend = [dict(r) for r in cur.fetchall()]
            for r in trend:
                if r.get("month_start"):
                    r["month_start"] = r["month_start"].strftime("%Y-%m-%d")
                    r["display_month"] = r["month_start"][:7]
            out["trend"] = trend
            # KPIs del último mes (o del rango si year_real)
            cur.execute(
                f"""
                SELECT country, month_start, trips, trips_prev, growth_mom, b2b_trips, b2b_ratio,
                       forecast_next_month, forecast_growth, acceleration_index
                FROM {VIEW_COUNTRY_FORECAST}
                WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                  AND {where_period}
                ORDER BY month_start DESC
                LIMIT 1
                """,
                [country] + params_period,
            )
            row = cur.fetchone()
            if row:
                row = dict(row)
                total_trips = int(row.get("trips") or 0)
                # YTD: sumar todos los meses del año del month_start
                year_val = int(str(row.get("month_start") or default_m)[:4])
                cur.execute(
                    """
                    SELECT COALESCE(SUM(trips), 0) AS total
                    FROM ops.v_real_country_month
                    WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                      AND month_start >= %s::DATE AND month_start <= %s::DATE
                    """,
                    (country, f"{year_val}-01-01", f"{year_val}-12-31"),
                )
                ytd_row = cur.fetchone()
                total_trips_ytd = int(ytd_row.get("total") or 0) if ytd_row else total_trips
                month_val = row.get("month_start")
                month_str = month_val.strftime("%Y-%m-%d") if hasattr(month_val, "strftime") else str(month_val)[:10]
                out["kpis"] = {
                    "total_trips_ytd": total_trips_ytd,
                    "trips_last_month": total_trips,
                    "growth_mom": float(row["growth_mom"]) if row.get("growth_mom") is not None else None,
                    "b2b_ratio": float(row["b2b_ratio"]) if row.get("b2b_ratio") is not None else None,
                    "forecast_next_month": int(row["forecast_next_month"]) if row.get("forecast_next_month") is not None else None,
                    "forecast_growth": float(row["forecast_growth"]) if row.get("forecast_growth") is not None else None,
                    "acceleration_index": float(row["acceleration_index"]) if row.get("acceleration_index") is not None else None,
                    "concentration_index": None,
                    "last_month": month_str[:7],
                }
                # Concentration: top 3 cities / total (mismo mes)
                cur.execute(
                    """
                    WITH city_totals AS (
                        SELECT city, SUM(trips) AS trips
                        FROM ops.v_real_country_city_month
                        WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                          AND month_start = %s::DATE
                        GROUP BY city
                    ),
                    top3 AS (
                        SELECT SUM(trips) AS top3_trips FROM (
                            SELECT trips FROM city_totals ORDER BY trips DESC LIMIT 3
                        ) t
                    )
                    SELECT t.top3_trips, c.total
                    FROM top3 t
                    CROSS JOIN (SELECT SUM(trips) AS total FROM city_totals) c
                    """,
                    (country, default_m),
                )
                conc_row = cur.fetchone()
                if conc_row and conc_row.get("total") and float(conc_row["total"]) > 0:
                    out["kpis"]["concentration_index"] = round(
                        float(conc_row["top3_trips"] or 0) / float(conc_row["total"]), 4
                    )
                # Forecast objeto (solo si hay al menos 2 meses reales)
                if len(trend) >= 2 and out["kpis"].get("forecast_next_month") is not None:
                    out["forecast"] = {
                        "next_month": out["kpis"]["forecast_next_month"],
                        "forecast_growth": out["kpis"].get("forecast_growth"),
                        "disclaimer": "Proyección basada en tendencia histórica, no considera eventos externos.",
                    }
                else:
                    out["forecast"] = {"disclaimer": "Proyección basada en tendencia histórica, no considera eventos externos.", "available": False}
                # Rankings: ciudades último mes
                cur.execute(
                    f"""
                    SELECT country, city, month_start, trips, growth_mom, expansion_index
                    FROM {VIEW_COUNTRY_CITY}
                    WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s))
                      AND month_start = %s::DATE
                    ORDER BY trips DESC
                    LIMIT 50
                    """,
                    (country, default_m),
                )
                total_country_month = int(row.get("trips") or 0)
                rankings = []
                for r in cur.fetchall():
                    rr = dict(r)
                    if rr.get("month_start"):
                        rr["month_start"] = rr["month_start"].strftime("%Y-%m-%d")
                    rr["expansion_index"] = float(rr["expansion_index"]) if rr.get("expansion_index") is not None else None
                    rr["growth_mom"] = float(rr["growth_mom"]) if rr.get("growth_mom") is not None else None
                    rr["pct_country"] = round((float(rr.get("trips") or 0) / total_country_month * 100), 2) if total_country_month else None
                    rankings.append(rr)
                out["rankings"] = rankings
            cur.close()
        return out
    except Exception as e:
        logger.error("Real strategy country: %s", e)
        raise


def get_real_strategy_lob(
    country: str,
    year_real: Optional[int] = None,
    segment_tag: Optional[str] = None,
    lob_group: Optional[str] = None,
    period_type: str = "monthly",
) -> Dict[str, Any]:
    """
    GET /ops/real-strategy/lob
    country required. Retorna distribución LOB con participation_pct, growth_mom, forecast_next_month, momentum_score.
    momentum_score = weighted_growth_last_3_months (0.5*M0 + 0.3*M-1 + 0.2*M-2 en términos de growth).
    """
    if not country or not str(country).strip():
        return {"error": "country is required", "kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    out: Dict[str, Any] = {"kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(STRATEGY_TIMEOUT_MS),))
            default_m = _default_month(cur, country, year_real)
            if not default_m:
                return out
            if year_real is not None:
                where_period = "month_start >= %s::DATE AND month_start <= %s::DATE"
                params_period = [f"{year_real}-01-01", f"{year_real}-12-31"]
            else:
                where_period = "month_start = %s::DATE"
                params_period = [default_m]
            # LOB agregado: desde v_real_country_lob_month (ya tiene forecast_next_month)
            where_lob = ["LOWER(TRIM(country)) = LOWER(TRIM(%s))", where_period]
            params_lob = [country] + params_period
            if lob_group:
                where_lob.append("LOWER(TRIM(lob_group)) = LOWER(TRIM(%s))")
                params_lob.append(lob_group)
            cur.execute(
                f"""
                SELECT country, lob_group, month_start, trips, growth_mom, forecast_next_month
                FROM {VIEW_COUNTRY_LOB}
                WHERE {' AND '.join(where_lob)}
                ORDER BY month_start DESC, trips DESC
                """,
                params_lob,
            )
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                if r.get("month_start"):
                    r["month_start"] = r["month_start"].strftime("%Y-%m-%d")
            # Por LOB: usar el último mes del rango (first row per lob_group al estar ORDER BY month_start DESC)
            by_lob: Dict[str, Dict] = {}
            for r in rows:
                lob = r.get("lob_group") or "UNCLASSIFIED"
                if lob not in by_lob:
                    by_lob[lob] = {
                        "trips": int(r.get("trips") or 0),
                        "growth_mom": float(r["growth_mom"]) if r.get("growth_mom") is not None else None,
                        "forecast_next_month": int(r["forecast_next_month"]) if r.get("forecast_next_month") is not None else None,
                    }
            cur.execute(
                """
                SELECT SUM(trips) AS total FROM ops.v_real_country_month
                WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s)) AND month_start = %s::DATE
                """,
                (country, default_m),
            )
            tot_row = cur.fetchone()
            total_country = int(tot_row.get("total") or 0) if tot_row else 0
            rankings = []
            for lob, data in by_lob.items():
                participation = (data["trips"] / total_country) if total_country else None
                momentum_score = data["growth_mom"]
                rankings.append({
                    "lob_group": lob,
                    "trips": data["trips"],
                    "participation_pct": round(participation * 100, 2) if participation is not None else None,
                    "growth_mom": data["growth_mom"],
                    "forecast_next_month": data["forecast_next_month"],
                    "momentum_score": round(momentum_score, 4) if momentum_score is not None else None,
                })
            rankings.sort(key=lambda x: (x["trips"] or 0), reverse=True)
            out["rankings"] = rankings
            out["kpis"] = {"total_trips": total_country, "last_month": default_m[:7]}
            cur.close()
        return out
    except Exception as e:
        logger.error("Real strategy LOB: %s", e)
        raise


def get_real_strategy_cities(
    country: str,
    year_real: Optional[int] = None,
    segment_tag: Optional[str] = None,
    period_type: str = "monthly",
) -> Dict[str, Any]:
    """
    GET /ops/real-strategy/cities
    country required. Ranking ciudades: city, trips, growth_mom, pct_country, expansion_index.
    """
    if not country or not str(country).strip():
        return {"error": "country is required", "kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    out: Dict[str, Any] = {"kpis": {}, "trend": [], "forecast": {}, "rankings": []}
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(STRATEGY_TIMEOUT_MS),))
            default_m = _default_month(cur, country, year_real)
            if not default_m:
                return out
            if year_real is not None:
                where_period = "month_start >= %s::DATE AND month_start <= %s::DATE"
                params_period = [f"{year_real}-01-01", f"{year_real}-12-31"]
            else:
                where_period = "month_start = %s::DATE"
                params_period = [default_m]
            cur.execute(
                """
                SELECT SUM(trips) AS total FROM ops.v_real_country_month
                WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s)) AND """ + where_period,
                [country] + params_period,
            )
            tot_row = cur.fetchone()
            total_country = int(tot_row.get("total") or 0) if tot_row else 0
            cur.execute(
                f"""
                SELECT country, city, month_start, trips, growth_mom, expansion_index
                FROM {VIEW_COUNTRY_CITY}
                WHERE LOWER(TRIM(country)) = LOWER(TRIM(%s)) AND {where_period}
                ORDER BY month_start DESC, trips DESC
                LIMIT 100
                """,
                [country] + params_period,
            )
            rows = cur.fetchall()
            rankings = []
            for r in rows:
                rr = dict(r)
                if rr.get("month_start"):
                    rr["month_start"] = rr["month_start"].strftime("%Y-%m-%d")
                pct = (float(rr.get("trips") or 0) / total_country * 100) if total_country else None
                rr["pct_country"] = round(pct, 2) if pct is not None else None
                rr["expansion_index"] = float(rr["expansion_index"]) if rr.get("expansion_index") is not None else None
                rr["growth_mom"] = float(rr["growth_mom"]) if rr.get("growth_mom") is not None else None
                rankings.append(rr)
            out["rankings"] = rankings
            out["kpis"] = {"total_trips": total_country, "last_month": default_m[:7] if len(default_m) >= 7 else default_m}
            cur.close()
        return out
    except Exception as e:
        logger.error("Real strategy cities: %s", e)
        raise
