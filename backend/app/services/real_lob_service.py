"""Servicio REAL LOB: viajes REAL por LOB desde tipo_servicio normalizado. Lee de MVs. Sin Plan."""
from app.db.connection import get_db
from app.settings import settings
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict, Any

from app.services.serving_guardrails import (
    QueryMode as _QM,
    ServingPolicy,
    SourceType as _ST,
    context_from_policy,
    execute_db_gated_query,
    register_policy,
)

logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_trips_by_lob_month"
MV_WEEKLY = "ops.mv_real_trips_by_lob_week"
REAL_LOB_STATEMENT_TIMEOUT_MS = 15000

_SERVING_POLICY = ServingPolicy(
    feature_name="Real LOB monthly",
    query_mode=_QM.SERVING,
    preferred_source=MV_MONTHLY,
    preferred_source_type=_ST.MV,
    strict_mode=True,
)
register_policy(_SERVING_POLICY)


def _is_dev() -> bool:
    return (getattr(settings, "ENVIRONMENT", "") or "").lower() in ("dev", "development")


def get_real_lob_meta() -> Dict[str, Any]:
    """Devuelve max_month, max_week, count_month, count_week desde las MVs."""
    out: Dict[str, Any] = {"max_month": None, "max_week": None, "count_month": 0, "count_week": 0}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = %s", (str(REAL_LOB_STATEMENT_TIMEOUT_MS),))
            cur.execute(f"SELECT MAX(month_start) FROM {MV_MONTHLY}")
            row = cur.fetchone()
            if row and row[0]:
                out["max_month"] = row[0].strftime("%Y-%m")
            cur.execute(f"SELECT COUNT(*) FROM {MV_MONTHLY}")
            out["count_month"] = cur.fetchone()[0] or 0
            cur.execute(f"SELECT MAX(week_start) FROM {MV_WEEKLY}")
            row = cur.fetchone()
            if row and row[0]:
                out["max_week"] = row[0].strftime("%Y-%m-%d")
            cur.execute(f"SELECT COUNT(*) FROM {MV_WEEKLY}")
            out["count_week"] = cur.fetchone()[0] or 0
            cur.close()
    except Exception as e:
        logger.warning("Real LOB meta: %s", e)
    return out


def _display_month(month_start) -> str:
    """Formato 'Dic 2025' o 'YYYY-MM'. Usamos YYYY-MM para consistencia."""
    if not month_start:
        return ""
    if hasattr(month_start, "strftime"):
        return month_start.strftime("%Y-%m")
    return str(month_start)[:7] if len(str(month_start)) >= 7 else str(month_start)


def _display_week(week_start) -> str:
    """Formato YYYY-MM-DD para semana (lunes)."""
    if not week_start:
        return ""
    if hasattr(week_start, "strftime"):
        return week_start.strftime("%Y-%m-%d")
    return str(week_start)[:10] if len(str(week_start)) >= 10 else str(week_start)


def get_real_lob_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_name: Optional[str] = None,
    month: Optional[str] = None,
    year_real: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Viajes REAL por LOB (mensual). LOB = tipo_servicio normalizado.
    Orden: month_start ASC, trips DESC.
    Payload: month_start, display_month, trips, revenue (>=0), is_open, currency.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SET statement_timeout = %s", (str(REAL_LOB_STATEMENT_TIMEOUT_MS),))
            where: List[str] = []
            params: List[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
                params.append(city)
            if lob_name:
                where.append("LOWER(TRIM(lob)) = LOWER(TRIM(%s))")
                params.append(lob_name)

            if month:
                if len(month) == 7:
                    where.append("TO_CHAR(month_start, 'YYYY-MM') = %s")
                    params.append(month)
                else:
                    where.append("month_start = %s::DATE")
                    params.append(month)
            elif year_real is not None:
                where.append("month_start >= %s::DATE AND month_start <= %s::DATE")
                params.append(f"{year_real}-01-01")
                params.append(f"{year_real}-12-31")
            else:
                cursor.execute(f"SELECT MAX(month_start) AS m FROM {MV_MONTHLY}")
                r = cursor.fetchone()
                default_month = r.get("m") if r else None
                if default_month:
                    where.append("month_start = %s::DATE")
                    params.append(default_month)

            where_clause = " AND ".join(where) if where else "TRUE"
            _ctx = context_from_policy(_SERVING_POLICY, source_name=MV_MONTHLY)
            rows = execute_db_gated_query(
                _ctx, _SERVING_POLICY, cursor,
                f"""
                SELECT country, city, lob, month_start, trips, revenue, max_trip_ts, is_open, currency
                FROM {MV_MONTHLY}
                WHERE {where_clause}
                ORDER BY month_start ASC, trips DESC
                """,
                params,
                source_name=MV_MONTHLY, source_type="mv",
            )
            out = []
            for r in rows:
                row = dict(r)
                if row.get("month_start"):
                    row["period_date"] = row["month_start"].strftime("%Y-%m-%d")
                    row["display_month"] = _display_month(row["month_start"])
                row["revenue"] = max(0, float(row.get("revenue") or 0))
                row["lob_name"] = row.get("lob")  # compat FE
                out.append(row)
            cursor.close()
        if _is_dev():
            logger.debug("Real LOB monthly params=%s rows=%s", {"country": country, "city": city, "lob_name": lob_name, "month": month, "year_real": year_real}, len(out))
        logger.info("Real LOB monthly: %s registros", len(out))
        return out
    except Exception as e:
        logger.error("Error Real LOB monthly: %s", e)
        raise


def get_real_lob_weekly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_name: Optional[str] = None,
    week_start: Optional[str] = None,
    year_real: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Viajes REAL por LOB (semanal). Orden: week_start DESC, trips DESC.
    Payload: week_start, display_week, trips, revenue (>=0), is_open, currency.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SET statement_timeout = %s", (str(REAL_LOB_STATEMENT_TIMEOUT_MS),))
            where: List[str] = []
            params: List[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
                params.append(city)
            if lob_name:
                where.append("LOWER(TRIM(lob)) = LOWER(TRIM(%s))")
                params.append(lob_name)

            if week_start:
                where.append("week_start = %s::DATE")
                params.append(week_start)
            elif year_real is not None:
                where.append("week_start >= %s::DATE AND week_start <= %s::DATE")
                params.append(f"{year_real}-01-01")
                params.append(f"{year_real}-12-31")
            else:
                cursor.execute(f"SELECT MAX(week_start) AS w FROM {MV_WEEKLY}")
                r = cursor.fetchone()
                default_week = r.get("w") if r else None
                if default_week:
                    where.append("week_start = %s::DATE")
                    params.append(default_week)

            where_clause = " AND ".join(where) if where else "TRUE"
            _ctx = context_from_policy(_SERVING_POLICY, source_name=MV_WEEKLY)
            rows = execute_db_gated_query(
                _ctx, _SERVING_POLICY, cursor,
                f"""
                SELECT country, city, lob, week_start, trips, revenue, max_trip_ts, is_open, currency
                FROM {MV_WEEKLY}
                WHERE {where_clause}
                ORDER BY week_start DESC, trips DESC
                """,
                params,
                source_name=MV_WEEKLY, source_type="mv",
            )
            out = []
            for r in rows:
                row = dict(r)
                if row.get("week_start"):
                    row["period_date"] = row["week_start"].strftime("%Y-%m-%d")
                    row["display_week"] = _display_week(row["week_start"])
                row["revenue"] = max(0, float(row.get("revenue") or 0))
                row["lob_name"] = row.get("lob")
                out.append(row)
            cursor.close()
        if _is_dev():
            logger.debug("Real LOB weekly params=%s rows=%s", {"country": country, "city": city, "lob_name": lob_name, "week_start": week_start, "year_real": year_real}, len(out))
        logger.info("Real LOB weekly: %s registros", len(out))
        return out
    except Exception as e:
        logger.error("Error Real LOB weekly: %s", e)
        raise
