"""Servicio para comparación Plan vs Real mensual (REALKEY: sin LOB, sin homologación)."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Vista oficial: ops.v_plan_vs_real_realkey_final
# Llave: (country, city, park_id, real_tipo_servicio, period_date)
VIEW_REALKEY = "ops.v_plan_vs_real_realkey_final"


def get_plan_vs_real_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    real_tipo_servicio: Optional[str] = None,
    park_id: Optional[str] = None,
    month: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Obtiene comparación Plan vs Real mensual desde ops.v_plan_vs_real_realkey_final.
    Sin LOB: dimensión es real_tipo_servicio (y park_name), no lob_base/segment.
    Filtros opcionales: country, city, real_tipo_servicio, park_id, month (YYYY-MM o YYYY-MM-DD).
    Retorna filas con: country, city, park_id, park_name, real_tipo_servicio, period_date (como month),
    trips_plan, trips_real, revenue_plan, revenue_real, gap_trips, gap_revenue, status_bucket.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where_conditions = []
            params: List[Any] = []

            if country:
                where_conditions.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where_conditions.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
                params.append(city)
            if real_tipo_servicio:
                where_conditions.append("LOWER(TRIM(real_tipo_servicio)) = LOWER(TRIM(%s))")
                params.append(real_tipo_servicio)
            if park_id:
                where_conditions.append("TRIM(park_id) = TRIM(%s)")
                params.append(park_id)
            if month:
                if len(month) == 7:  # YYYY-MM
                    where_conditions.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                    params.append(month)
                else:
                    where_conditions.append("period_date = %s::DATE")
                    params.append(month)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query = f"""
                SELECT
                    country,
                    city,
                    park_id,
                    park_name,
                    real_tipo_servicio,
                    period_date,
                    trips_plan,
                    trips_real,
                    revenue_plan,
                    revenue_real,
                    variance_trips,
                    variance_revenue,
                    CASE
                        WHEN trips_plan IS NOT NULL AND trips_real IS NOT NULL THEN 'matched'
                        WHEN trips_plan IS NOT NULL AND trips_real IS NULL THEN 'plan_only'
                        WHEN trips_plan IS NULL AND trips_real IS NOT NULL THEN 'real_only'
                        ELSE 'unknown'
                    END AS status_bucket
                FROM {VIEW_REALKEY}
                {where_clause}
                ORDER BY period_date DESC NULLS LAST, country, city, park_id, real_tipo_servicio
            """
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            out: List[Dict[str, Any]] = []
            for row in results:
                r = dict(row)
                if r.get("period_date"):
                    r["month"] = r["period_date"].strftime("%Y-%m-%d")
                # API contract: gap = plan - real (positive = plan ahead)
                r["gap_trips"] = (r["trips_plan"] or 0) - (r["trips_real"] or 0) if (r.get("trips_plan") is not None or r.get("trips_real") is not None) else None
                r["gap_revenue"] = (r["revenue_plan"] or 0) - (r["revenue_real"] or 0) if (r.get("revenue_plan") is not None or r.get("revenue_real") is not None) else None
                out.append(r)

            logger.info(f"Plan vs Real (realkey) obtenido: {len(out)} registros")
            return out
    except Exception as e:
        logger.error(f"Error al obtener comparación Plan vs Real: {e}")
        raise


def get_alerts_monthly(
    country: Optional[str] = None,
    month: Optional[str] = None,
    alert_level: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Alertas Plan vs Real desde ops.v_plan_vs_real_realkey_final.
    Solo filas matched (trips_plan AND trips_real no null). Calcula gap_trips_pct, gap_revenue_pct y alert_level.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where_base = ["trips_plan IS NOT NULL", "trips_real IS NOT NULL"]
            params: List[Any] = []

            if country:
                where_base.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if month:
                if len(month) == 7:
                    where_base.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                    params.append(month)
                else:
                    where_base.append("period_date = %s::DATE")
                    params.append(month)

            where_clause = " AND ".join(where_base)
            query = f"""
                WITH base AS (
                    SELECT
                        country,
                        city,
                        park_id,
                        park_name,
                        real_tipo_servicio,
                        period_date,
                        trips_plan,
                        trips_real,
                        revenue_plan,
                        revenue_real,
                        (trips_plan - trips_real) AS gap_trips,
                        (revenue_plan - revenue_real) AS gap_revenue,
                        CASE WHEN trips_plan > 0 THEN (trips_plan - trips_real)::NUMERIC / trips_plan * 100 ELSE NULL END AS gap_trips_pct,
                        CASE WHEN revenue_plan > 0 AND revenue_plan IS NOT NULL THEN (revenue_plan - revenue_real)::NUMERIC / revenue_plan * 100 ELSE NULL END AS gap_revenue_pct
                    FROM {VIEW_REALKEY}
                    WHERE {where_clause}
                )
                SELECT
                    country,
                    period_date,
                    city AS city_norm_real,
                    real_tipo_servicio AS lob_base,
                    NULL::text AS segment,
                    trips_plan AS projected_trips,
                    revenue_plan AS projected_revenue,
                    trips_real AS trips_real_completed,
                    revenue_real AS revenue_real_yego,
                    gap_trips,
                    gap_revenue,
                    gap_trips_pct,
                    gap_revenue_pct,
                    CASE
                        WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct >= 15 THEN 'CRITICO'
                        WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct >= 20 THEN 'CRITICO'
                        WHEN gap_revenue_pct IS NOT NULL AND gap_revenue_pct >= 8 THEN 'MEDIO'
                        WHEN gap_trips_pct IS NOT NULL AND gap_trips_pct >= 10 THEN 'MEDIO'
                        ELSE 'OK'
                    END AS alert_level
                FROM base
            """
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()

            rows = [dict(r) for r in results]
            if alert_level:
                rows = [r for r in rows if r.get("alert_level") == alert_level]
            # Ordenar por severidad
            order_map = {"CRITICO": 1, "MEDIO": 2, "OK": 3}
            for r in rows:
                r["month"] = r["period_date"].strftime("%Y-%m-%d") if r.get("period_date") else None
            rows.sort(key=lambda x: (order_map.get(x.get("alert_level") or "", 4), x.get("month") or "", x.get("country") or "", x.get("city_norm_real") or ""))

            logger.info(f"Alertas Plan vs Real (realkey) obtenidas: {len(rows)} registros")
            return rows
    except Exception as e:
        logger.error(f"Error al obtener alertas Plan vs Real: {e}")
        raise
