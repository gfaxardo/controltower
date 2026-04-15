"""
Real LOB v2: endpoint único de datos con consolidación (agg_level) y totales.
GET /ops/real-lob/v2/data
Fuente: ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2.
"""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any, Tuple
import logging

from app.services.serving_guardrails import (
    QueryMode as _QM,
    ServingPolicy,
    SourceType as _ST,
    context_from_policy,
    execute_db_gated_query,
    register_policy,
)

logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_lob_month_v2"
MV_WEEKLY = "ops.mv_real_lob_week_v2"
DATA_TIMEOUT_MS = 20000

_SERVING_POLICY = ServingPolicy(
    feature_name="Real LOB v2 data",
    query_mode=_QM.SERVING,
    preferred_source=MV_MONTHLY,
    preferred_source_type=_ST.MV,
    strict_mode=True,
)
register_policy(_SERVING_POLICY)

AGG_LEVELS_MONTHLY = [
    "DETALLE", "TOTAL_PAIS", "TOTAL_CIUDAD", "TOTAL_PARK",
    "PARK_X_MES", "PARK_X_MES_X_LOB",
]
AGG_LEVELS_WEEKLY = [
    "DETALLE", "TOTAL_PAIS", "TOTAL_CIUDAD", "TOTAL_PARK",
    "PARK_X_SEMANA", "PARK_X_SEMANA_X_LOB",
]


def get_real_lob_v2_data(
    period_type: str = "monthly",
    agg_level: str = "DETALLE",
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    lob_group: Optional[str] = None,
    tipo_servicio: Optional[str] = None,
    segment_tag: Optional[str] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Datos Real LOB v2 con consolidación. Totales suman exactamente lo que hay en rows.
    segment_tag: "Todos" | "B2B" | "B2C". Si "Todos" o vacío, no filtra por segmento.
    year: si None, últimos 12 meses (preferible). Si entero, ese año.
    """
    is_monthly = (period_type or "monthly").lower() == "monthly"
    mv = MV_MONTHLY if is_monthly else MV_WEEKLY
    period_col = "month_start" if is_monthly else "week_start"
    agg = (agg_level or "DETALLE").strip().upper()
    if is_monthly and agg in ("PARK_X_SEMANA", "PARK_X_SEMANA_X_LOB"):
        agg = "PARK_X_MES" if agg == "PARK_X_SEMANA" else "PARK_X_MES_X_LOB"
    if not is_monthly and agg in ("PARK_X_MES", "PARK_X_MES_X_LOB"):
        agg = "PARK_X_SEMANA" if agg == "PARK_X_MES" else "PARK_X_SEMANA_X_LOB"

    where_clause, params = _build_where(
        country=country, city=city, park_id=park_id,
        lob_group=lob_group, tipo_servicio=tipo_servicio, segment_tag=segment_tag,
        year=year, period_col=period_col, is_monthly=is_monthly, mv=mv,
    )
    select_sql, group_sql, order_sql = _agg_sql(mv, period_col, agg, is_monthly)
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(DATA_TIMEOUT_MS),))
            sql = f"""
                WITH base AS (
                    SELECT * FROM {mv} WHERE {where_clause}
                ),
                agg AS (
                    {select_sql}
                )
                SELECT * FROM agg {order_sql}
            """
            _ctx = context_from_policy(_SERVING_POLICY, source_name=mv)
            rows = execute_db_gated_query(
                _ctx, _SERVING_POLICY, cur, sql, params,
                source_name=mv, source_type="mv",
            )
            _serialize_rows(rows, period_col)
            # Totales: sumar trips y b2b_trips de rows (coherencia)
            total_trips = sum(int(r.get("trips") or 0) for r in rows)
            total_b2b = sum(int(r.get("b2b_trips") or 0) for r in rows)
            b2b_ratio = (total_b2b / total_trips) if total_trips else None
            meta = _get_meta(cur, mv, period_col)
            cur.close()
        return {
            "totals": {
                "trips": total_trips,
                "b2b_trips": total_b2b,
                "b2b_ratio": round(total_b2b / total_trips, 4) if total_trips else None,
                "rows": len(rows),
            },
            "rows": rows,
            "meta": meta,
        }
    except Exception as e:
        logger.error("Real LOB v2 data: %s", e)
        raise


def _build_where(
    country: Optional[str],
    city: Optional[str],
    park_id: Optional[str],
    lob_group: Optional[str],
    tipo_servicio: Optional[str],
    segment_tag: Optional[str],
    year: Optional[int],
    period_col: str,
    is_monthly: bool,
    mv: str,
) -> Tuple[str, List[Any]]:
    conditions = ["TRUE"]
    params: List[Any] = []
    if country and str(country).strip():
        conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
        params.append(country.strip())
    if city and str(city).strip():
        conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
        params.append(city.strip())
    if park_id and str(park_id).strip():
        conditions.append("TRIM(park_id::text) = TRIM(%s)")
        params.append(str(park_id).strip())
    if lob_group and str(lob_group).strip():
        conditions.append("LOWER(TRIM(lob_group)) = LOWER(TRIM(%s))")
        params.append(lob_group.strip())
    if tipo_servicio and str(tipo_servicio).strip():
        conditions.append("LOWER(TRIM(real_tipo_servicio_norm)) = LOWER(TRIM(%s))")
        params.append(tipo_servicio.strip())
    if segment_tag and str(segment_tag).strip() and segment_tag.strip() != "Todos":
        conditions.append("segment_tag = %s")
        params.append(segment_tag.strip())
    if year is not None:
        conditions.append(f"{period_col} >= %s::DATE AND {period_col} <= %s::DATE")
        params.append(f"{year}-01-01")
        params.append(f"{year}-12-31")
    else:
        # Últimos 12 meses vía subquery
        conditions.append(
            f"{period_col} >= ((SELECT MAX({period_col}) FROM {mv}) - INTERVAL '11 months')"
        )
        conditions.append(f"{period_col} <= (SELECT MAX({period_col}) FROM {mv})")
    where_clause = " AND ".join(conditions)
    return where_clause, params


def _agg_sql(mv: str, period_col: str, agg: str, is_monthly: bool) -> Tuple[str, str, str]:
    """Devuelve (SELECT para CTE agg, GROUP BY, ORDER BY)."""
    base_select = f"""
        country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag,
        {period_col},
        SUM(trips) AS trips,
        SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
    """
    if agg == "DETALLE":
        select_sql = f"SELECT {base_select} FROM base GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, {period_col}"
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    if agg == "TOTAL_PAIS":
        select_sql = f"""
            SELECT country, {period_col} AS period_start,
                   SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
            FROM base GROUP BY country, {period_col}
        """
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    if agg == "TOTAL_CIUDAD":
        select_sql = f"""
            SELECT country, city, {period_col} AS period_start,
                   SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
            FROM base GROUP BY country, city, {period_col}
        """
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    if agg == "TOTAL_PARK":
        select_sql = f"""
            SELECT country, city, park_id, park_name, {period_col} AS period_start,
                   SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
            FROM base GROUP BY country, city, park_id, park_name, {period_col}
        """
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    if agg == "PARK_X_MES" or agg == "PARK_X_SEMANA":
        select_sql = f"""
            SELECT country, city, park_id, park_name, {period_col} AS period_start,
                   SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
            FROM base GROUP BY country, city, park_id, park_name, {period_col}
        """
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    if agg == "PARK_X_MES_X_LOB" or agg == "PARK_X_SEMANA_X_LOB":
        select_sql = f"""
            SELECT country, city, park_id, park_name, lob_group, {period_col} AS period_start,
                   SUM(trips) AS trips, SUM(CASE WHEN segment_tag = 'B2B' THEN trips ELSE 0 END) AS b2b_trips
            FROM base GROUP BY country, city, park_id, park_name, lob_group, {period_col}
        """
        order_sql = f"ORDER BY {period_col} DESC, trips DESC"
        return select_sql, "", order_sql
    # default DETALLE
    select_sql = f"SELECT {base_select} FROM base GROUP BY country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag, {period_col}"
    order_sql = f"ORDER BY {period_col} DESC, trips DESC"
    return select_sql, "", order_sql


def _serialize_rows(rows: List[Dict], period_col: str) -> None:
    for r in rows:
        dt = r.get(period_col) or r.get("period_start")
        if dt and hasattr(dt, "strftime"):
            r["period_start"] = dt.strftime("%Y-%m-%d")
            r["display_period"] = dt.strftime("%Y-%m") if period_col == "month_start" else dt.strftime("%Y-%m-%d")
        if r.get("park_name") is not None and not hasattr(r["park_name"], "strip"):
            r["park_name"] = str(r.get("park_name") or r.get("park_id") or "")


def _get_meta(cur, mv: str, period_col: str) -> Dict[str, Any]:
    cur.execute(f"SELECT MAX({period_col}) AS last FROM {mv}")
    row = cur.fetchone()
    last = row.get("last") if row else None
    key = "last_month_real" if period_col == "month_start" else "last_week_real"
    return {key: last.strftime("%Y-%m-%d") if last and hasattr(last, "strftime") else None}
