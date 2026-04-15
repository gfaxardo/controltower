"""Real LOB v2: country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag (B2B/B2C). Lee de MVs."""
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

MV_MONTHLY_V2 = "ops.mv_real_lob_month_v2"
MV_WEEKLY_V2 = "ops.mv_real_lob_week_v2"
REAL_LOB_TIMEOUT_MS = 15000

_SERVING_POLICY = ServingPolicy(
    feature_name="Real LOB monthly v2",
    query_mode=_QM.SERVING,
    preferred_source=MV_MONTHLY_V2,
    preferred_source_type=_ST.MV,
    strict_mode=True,
)
register_policy(_SERVING_POLICY)


def _is_dev() -> bool:
    return (getattr(settings, "ENVIRONMENT", "") or "").lower() in ("dev", "development")


def get_real_lob_meta_v2() -> Dict[str, Any]:
    """Meta para v2: max_month, max_week."""
    out: Dict[str, Any] = {"max_month": None, "max_week": None}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = %s", (str(REAL_LOB_TIMEOUT_MS),))
            cur.execute(f"SELECT MAX(month_start) FROM {MV_MONTHLY_V2}")
            row = cur.fetchone()
            if row and row[0]:
                out["max_month"] = row[0].strftime("%Y-%m")
            cur.execute(f"SELECT MAX(week_start) FROM {MV_WEEKLY_V2}")
            row = cur.fetchone()
            if row and row[0]:
                out["max_week"] = row[0].strftime("%Y-%m-%d")
            cur.close()
    except Exception as e:
        logger.warning("Real LOB v2 meta: %s", e)
    return out


def get_real_lob_monthly_v2(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    lob_group: Optional[str] = None,
    real_tipo_servicio: Optional[str] = None,
    segment_tag: Optional[str] = None,
    month: Optional[str] = None,
    year_real: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Real LOB v2 mensual. Filtros: country, city, park_id, lob_group, real_tipo_servicio_norm, segment_tag.
    Default periodo: último mes si no month/year_real. Orden: month_start ASC, trips DESC.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SET statement_timeout = %s", (str(REAL_LOB_TIMEOUT_MS),))
            where: List[str] = []
            params: List[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
                params.append(city)
            if park_id:
                where.append("TRIM(park_id::text) = TRIM(%s)")
                params.append(park_id)
            if lob_group:
                where.append("LOWER(TRIM(lob_group)) = LOWER(TRIM(%s))")
                params.append(lob_group)
            if real_tipo_servicio:
                where.append("LOWER(TRIM(real_tipo_servicio_norm)) = LOWER(TRIM(%s))")
                params.append(real_tipo_servicio)
            if segment_tag:
                where.append("segment_tag = %s")
                params.append(segment_tag)

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
                cursor.execute(f"SELECT MAX(month_start) AS m FROM {MV_MONTHLY_V2}")
                r = cursor.fetchone()
                default_month = r.get("m") if r else None
                if default_month:
                    where.append("month_start = %s::DATE")
                    params.append(default_month)

            where_clause = " AND ".join(where) if where else "TRUE"
            _ctx = context_from_policy(_SERVING_POLICY, source_name=MV_MONTHLY_V2)
            rows = execute_db_gated_query(
                _ctx, _SERVING_POLICY, cursor,
                f"""
                SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                       month_start, trips, revenue, max_trip_ts, is_open
                FROM {MV_MONTHLY_V2}
                WHERE {where_clause}
                ORDER BY month_start ASC, trips DESC
                """,
                params,
                source_name=MV_MONTHLY_V2, source_type="mv",
            )
            out = []
            for r in rows:
                row = dict(r)
                if row.get("month_start"):
                    row["period_date"] = row["month_start"].strftime("%Y-%m-%d")
                    row["display_month"] = row["month_start"].strftime("%Y-%m")
                row["revenue"] = max(0, float(row.get("revenue") or 0))
                row["currency"] = "PEN" if (row.get("country") or "").lower() == "pe" else "COP" if (row.get("country") or "").lower() == "co" else None
                out.append(row)
            cursor.close()
        logger.info("Real LOB v2 monthly: %s registros", len(out))
        return out
    except Exception as e:
        logger.error("Error Real LOB v2 monthly: %s", e)
        raise


def get_real_lob_weekly_v2(
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    lob_group: Optional[str] = None,
    real_tipo_servicio: Optional[str] = None,
    segment_tag: Optional[str] = None,
    week_start: Optional[str] = None,
    year_real: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Real LOB v2 semanal. Mismos filtros. Default: última semana. Orden: week_start DESC, trips DESC.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SET statement_timeout = %s", (str(REAL_LOB_TIMEOUT_MS),))
            where: List[str] = []
            params: List[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
                params.append(city)
            if park_id:
                where.append("TRIM(park_id::text) = TRIM(%s)")
                params.append(park_id)
            if lob_group:
                where.append("LOWER(TRIM(lob_group)) = LOWER(TRIM(%s))")
                params.append(lob_group)
            if real_tipo_servicio:
                where.append("LOWER(TRIM(real_tipo_servicio_norm)) = LOWER(TRIM(%s))")
                params.append(real_tipo_servicio)
            if segment_tag:
                where.append("segment_tag = %s")
                params.append(segment_tag)

            if week_start:
                where.append("week_start = %s::DATE")
                params.append(week_start)
            elif year_real is not None:
                where.append("week_start >= %s::DATE AND week_start <= %s::DATE")
                params.append(f"{year_real}-01-01")
                params.append(f"{year_real}-12-31")
            else:
                cursor.execute(f"SELECT MAX(week_start) AS w FROM {MV_WEEKLY_V2}")
                r = cursor.fetchone()
                default_week = r.get("w") if r else None
                if default_week:
                    where.append("week_start = %s::DATE")
                    params.append(default_week)

            where_clause = " AND ".join(where) if where else "TRUE"
            _ctx = context_from_policy(_SERVING_POLICY, source_name=MV_WEEKLY_V2)
            rows = execute_db_gated_query(
                _ctx, _SERVING_POLICY, cursor,
                f"""
                SELECT country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
                       week_start, trips, revenue, max_trip_ts, is_open
                FROM {MV_WEEKLY_V2}
                WHERE {where_clause}
                ORDER BY week_start DESC, trips DESC
                """,
                params,
                source_name=MV_WEEKLY_V2, source_type="mv",
            )
            out = []
            for r in rows:
                row = dict(r)
                if row.get("week_start"):
                    row["period_date"] = row["week_start"].strftime("%Y-%m-%d")
                    row["display_week"] = row["week_start"].strftime("%Y-%m-%d")
                row["revenue"] = max(0, float(row.get("revenue") or 0))
                row["currency"] = "PEN" if (row.get("country") or "").lower() == "pe" else "COP" if (row.get("country") or "").lower() == "co" else None
                out.append(row)
            cursor.close()
        logger.info("Real LOB v2 weekly: %s registros", len(out))
        return out
    except Exception as e:
        logger.error("Error Real LOB v2 weekly: %s", e)
        raise
