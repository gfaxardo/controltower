"""
Real mensual desde la canónica mensual histórica (sin dependencia 120d).

Fuente: ops.mv_real_monthly_canonical_hist (poblada desde v_trips_real_canon).
Grano: month_start, country. Métricas: trips, margin_total, active_drivers_core (desde viajes completados).
Soporta año y filtro país; city/lob_base/segment no se aplican en esta fuente (grano Resumen).
Ver docs/REAL_CANONICAL_CHAIN.md y REAL_DRIVER_GOVERNANCE.md.
"""
from __future__ import annotations

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Canónica mensual histórica completa (v_trips_real_canon, sin 120d)
TABLE_HIST = "ops.mv_real_monthly_canonical_hist"


def _get_currency_code(country: Optional[str]) -> str:
    """PE/peru->PEN, CO/colombia->COP. Default: PEN."""
    if not country:
        return "PEN"
    c = (country or "").lower().strip()
    if c in ("pe", "peru"):
        return "PEN"
    if c in ("co", "colombia"):
        return "COP"
    return "PEN"


def get_real_monthly_canonical(
    country: Optional[str] = None,
    city: Optional[str] = None,
    lob_base: Optional[str] = None,
    segment: Optional[str] = None,
    year: int = 2025,
) -> List[Dict]:
    """
    Obtiene datos REAL mensuales desde la canónica mensual histórica (mv_real_monthly_canonical_hist).
    No depende de la ventana 120d. Filtros aplicados: año y país (city/lob_base/segment no aplican en esta fuente).
    Mismo contrato que plan_real_split_service.get_real_monthly.
    """
    # Timeout generoso para lectura de MV (puede esperar si hay REFRESH en curso)
    _stmt_timeout_ms = 300000  # 5 min
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(_stmt_timeout_ms),))
            where_conditions = ["EXTRACT(YEAR FROM month_start) = %s"]
            params: List = [year]

            # MV guarda country como 'pe'/'co'/''. Aceptar pe|peru y co|colombia para paridad.
            if country:
                country_norm = (country or "").lower().strip()
                if country_norm == "pe":
                    country_norm = "peru"
                elif country_norm == "co":
                    country_norm = "colombia"
                if country_norm == "peru":
                    where_conditions.append("LOWER(TRIM(country)) IN ('pe', 'peru')")
                elif country_norm == "colombia":
                    where_conditions.append("LOWER(TRIM(country)) IN ('co', 'colombia')")
                else:
                    where_conditions.append("LOWER(TRIM(country)) = %s")
                    params.append(country_norm)

            # city, lob_base, segment: no existen en la MV histórica; se ignoran (grano Resumen = mes+país)
            where_sql = " AND ".join(where_conditions)
            # Una fila por mes (agregando por país si no hay filtro)
            query = f"""
                SELECT
                    month_start AS month,
                    SUM(trips) AS trips_real_completed,
                    SUM(COALESCE(margin_total, 0)) AS revenue_real_yego,
                    SUM(COALESCE(active_drivers_core, 0))::bigint AS active_drivers_real,
                    CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total, 0)) / SUM(trips) ELSE NULL END AS avg_ticket_real,
                    CASE WHEN SUM(COALESCE(active_drivers_core, 0)) > 0
                         THEN SUM(trips)::numeric / SUM(COALESCE(active_drivers_core, 0)) ELSE NULL END AS trips_per_driver,
                    CASE WHEN SUM(trips) > 0
                         THEN SUM(COALESCE(margin_total, 0)) / SUM(trips) ELSE NULL END AS margen_unitario_yego,
                    COUNT(DISTINCT country) AS country_count,
                    MAX(country) AS primary_country
                FROM {TABLE_HIST}
                WHERE {where_sql}
                GROUP BY month_start
                ORDER BY month_start
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            cur.close()

        currency_code = _get_currency_code(country)
        result: List[Dict] = []
        for row in rows:
            month = row["month"]
            period = month.strftime("%Y-%m") if hasattr(month, "strftime") else str(month)[:7]
            active_drivers_val = int(row["active_drivers_real"] or 0)
            trips_real = int(row["trips_real_completed"] or 0)
            trips_per_driver_val = float(row["trips_per_driver"]) if row.get("trips_per_driver") is not None else None
            if trips_per_driver_val is None and active_drivers_val and trips_real > 0:
                trips_per_driver_val = round(trips_real / active_drivers_val, 4)
            row_currency = currency_code
            if not country and row.get("primary_country") and (row.get("country_count") or 0) == 1:
                row_currency = _get_currency_code(row["primary_country"])
            result.append({
                "period": period,
                "month": str(month),
                "trips_real_completed": trips_real,
                "revenue_real_yego": float(row["revenue_real_yego"] or 0),
                "active_drivers_real": active_drivers_val,
                "avg_ticket_real": float(row["avg_ticket_real"]) if row.get("avg_ticket_real") is not None else None,
                "trips_per_driver": trips_per_driver_val,
                "margen_unitario_yego": float(row["margen_unitario_yego"]) if row.get("margen_unitario_yego") is not None else None,
                "currency_code": row_currency,
                "is_partial_real": False,
            })
        logger.info("Real monthly (canonical hist): %s periodos para year=%s", len(result), year)
        return result
    except Exception as e:
        logger.exception("get_real_monthly_canonical: %s", e)
        raise
