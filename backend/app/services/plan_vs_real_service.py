"""Servicio para comparación Plan vs Real mensual (REALKEY: sin LOB, sin homologación)."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict, Any

# FASE DECISION READINESS: importar semántica KPI para guardrail de alertas.
# Las alertas de brecha (gap_trips_pct, gap_revenue_pct) solo usan KPIs
# con decision_role == "decision_ready" (trips_completed, revenue, gmv, cancellations).
# Los KPIs distinct (active_drivers) y ratio (avg_ticket, take_rate) quedan excluidos.
try:
    from app.config.kpi_semantics import KPI_SEMANTICS, is_decision_ready  # noqa: F401
    _KPI_SEMANTICS_AVAILABLE = True
except ImportError:
    _KPI_SEMANTICS_AVAILABLE = False

logger = logging.getLogger(__name__)

# @deprecated — Prefer VIEW_REALKEY_CANONICAL cuando parity sea MATCH o MINOR_DIFF. No añadir nuevos consumidores.
# Vista legacy: ops.v_plan_vs_real_realkey_final
# Vista canónica (real desde v_trips_real_canon): ops.v_plan_vs_real_realkey_canonical
# Llave: (country, city, park_id, real_tipo_servicio, period_date)
VIEW_REALKEY = "ops.v_plan_vs_real_realkey_final"
VIEW_REALKEY_CANONICAL = "ops.v_plan_vs_real_realkey_canonical"


def get_latest_parity_audit(scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Lee el último registro de ops.plan_vs_real_parity_audit.
    scope: 'global', 'pe', 'co' o None (usa el más reciente de cualquier scope).
    Retorna dict con diagnosis, data_completeness, max_diff_pct, run_at; o None si no hay datos.
    """
    try:
        with get_db() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            if scope:
                cursor.execute(
                    """
                    SELECT scope, diagnosis, data_completeness, max_diff_pct, run_at
                    FROM ops.plan_vs_real_parity_audit
                    WHERE scope = %s
                    ORDER BY run_at DESC
                    LIMIT 1
                    """,
                    (scope.strip().lower(),),
                )
            else:
                cursor.execute(
                    """
                    SELECT scope, diagnosis, data_completeness, max_diff_pct, run_at
                    FROM ops.plan_vs_real_parity_audit
                    ORDER BY run_at DESC
                    LIMIT 1
                    """
                )
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None
    except Exception as e:
        logger.warning(f"plan_vs_real: no se pudo leer parity audit: {e}")
        return None


def log_plan_vs_real_source_usage(source: str, endpoint: str, request_params: Optional[Dict[str, Any]] = None) -> None:
    """Registra uso de fuente (legacy/canonical) en ops.plan_vs_real_source_usage_log."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ops.plan_vs_real_source_usage_log (used_at, source, endpoint, request_params, created_at)
                VALUES (NOW(), %s, %s, %s, NOW())
                """,
                (source, endpoint, __import__("json").dumps(request_params or {})),
            )
            conn.commit()
            cursor.close()
    except Exception as e:
        logger.debug(f"plan_vs_real: log usage no escrito: {e}")


def get_plan_vs_real_monthly(
    country: Optional[str] = None,
    city: Optional[str] = None,
    real_tipo_servicio: Optional[str] = None,
    park_id: Optional[str] = None,
    month: Optional[str] = None,
    year: Optional[int] = None,
    use_canonical: bool = False,
) -> List[Dict[str, Any]]:
    """
    Obtiene comparación Plan vs Real mensual desde ops.v_plan_vs_real_realkey_final.
    Sin LOB: dimensión es real_tipo_servicio (y park_name), no lob_base/segment.
    Filtros opcionales: country, city, real_tipo_servicio, park_id, month (YYYY-MM o YYYY-MM-DD), year (empuja filtro a DB).
    use_canonical: si True, lee de v_plan_vs_real_realkey_canonical (real desde v_trips_real_canon).
    year: si se pasa, filtra period_date en ese año (reduce scan; recomendado para paridad).
    Retorna filas con: country, city, park_id, park_name, real_tipo_servicio, period_date (como month),
    trips_plan, trips_real, revenue_plan, revenue_real, gap_trips, gap_revenue, status_bucket.
    """
    view = VIEW_REALKEY_CANONICAL if use_canonical else VIEW_REALKEY
    try:
        with get_db() as conn:
            # Parity/audit: con year se hace scan acotado pero vistas pueden ser pesadas; alargar timeout solo para esta sesión.
            if year is not None:
                try:
                    conn.cursor().execute("SET statement_timeout = '600000'")  # 10 min (ms)
                except Exception:
                    pass
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            where_conditions = []
            params: List[Any] = []

            if year is not None:
                where_conditions.append("period_date >= %s::DATE AND period_date < %s::DATE")
                params.extend([f"{year}-01-01", f"{year + 1}-01-01"])
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
                FROM {view}
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
    use_canonical: bool = False,
) -> List[Dict[str, Any]]:
    """
    Alertas Plan vs Real desde ops.v_plan_vs_real_realkey_final (o _canonical si use_canonical).
    Solo filas matched (trips_plan AND trips_real no null). Calcula gap_trips_pct, gap_revenue_pct y alert_level.
    """
    view = VIEW_REALKEY_CANONICAL if use_canonical else VIEW_REALKEY
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
                    FROM {view}
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


# ─── FASE DECISION READINESS: guardrail de alertas por KPI semántico ─────────
#
# Esta función es el punto de extensión para consumidores que iteren sobre
# múltiples KPIs dinámicamente. La query de get_alerts_monthly ya solo usa
# "trips" y "revenue" (ambos decision_ready), por lo que es correcta sin
# necesidad de filtro en SQL. El patrón siguiente aplica cuando se añadan
# nuevos KPIs dinámicos:
#
#   from app.config.kpi_semantics import KPI_SEMANTICS
#   for kpi, meta in KPI_SEMANTICS.items():
#       if meta["decision_role"] != "decision_ready":
#           continue          # ← guardrail: excluir distinct y ratio de alertas
#       ... compute alerts for kpi ...

def filter_decision_ready_kpis(kpi_list: List[str]) -> List[str]:
    """
    Filtra una lista de KPI keys para devolver solo los que tienen
    decision_role == "decision_ready" según KPI_SEMANTICS.

    Uso:
        safe_kpis = filter_decision_ready_kpis(["trips_completed", "active_drivers", "avg_ticket"])
        # → ["trips_completed"]

    Garantiza que ningún KPI distinct o ratio se use como base de alerta aditiva.
    """
    if not _KPI_SEMANTICS_AVAILABLE:
        return kpi_list
    return [k for k in kpi_list if is_decision_ready(k)]
