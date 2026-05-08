"""Servicio para comparación Plan vs Real mensual (REALKEY: sin LOB, sin homologación)."""
from datetime import date
import time

from app.db.connection import get_db
import psycopg2
from psycopg2 import errors as pg_errors
from psycopg2.extras import RealDictCursor
import logging
from typing import Optional, List, Dict, Any, Tuple, Iterator

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
# FASE 1.5B: snapshot pre-agregado (refresh: ops.refresh_plan_vs_real_monthly_facts o pipeline)
MV_PLAN_VS_REAL_MONTHLY = "ops.mv_plan_vs_real_monthly_fact"
MV_PLAN_VS_REAL_MONTHLY_CANONICAL = "ops.mv_plan_vs_real_monthly_fact_canonical"


def _plan_vs_real_relations_for_read(use_canonical: bool) -> Iterator[str]:
    """Orden: MV si settings lo permiten, luego vista realkey (fallback ante MV ausente)."""
    from app.settings import settings

    view = VIEW_REALKEY_CANONICAL if use_canonical else VIEW_REALKEY
    if not getattr(settings, "USE_PLAN_VS_REAL_MONTHLY_MV", True):
        yield view
        return
    mv = MV_PLAN_VS_REAL_MONTHLY_CANONICAL if use_canonical else MV_PLAN_VS_REAL_MONTHLY
    yield mv
    yield view


def _should_fallback_plan_vs_real_to_view(exc: BaseException) -> bool:
    """Solo fallback por relación ausente / no creada aún; no enmascarar timeouts u otros errores."""
    code = getattr(exc, "pgcode", None) or ""
    if code == "42P01":  # undefined_table
        return True
    if isinstance(exc, pg_errors.UndefinedTable):
        return True
    msg = str(exc).lower()
    return "does not exist" in msg and ("mv_plan_vs_real_monthly_fact" in msg or "relation" in msg)


def refresh_plan_vs_real_monthly_materialized_views(concurrent: bool = True) -> None:
    """
    REFRESH de ambas MVs Plan vs Real (legacy + canónica). Conexión dedicada, statement_timeout=0.
    Tras CONCURRENTLY fallido, reintenta sin CONCURRENTLY en la misma sesión.
    """
    from app.settings import settings

    params = {
        "host": settings.DB_HOST or "localhost",
        "port": settings.DB_PORT or 5432,
        "dbname": settings.DB_NAME or "yego_integral",
        "user": settings.DB_USER or "",
        "password": settings.DB_PASSWORD or "",
        "options": "-c statement_timeout=0 -c lock_timeout=0",
    }
    conn = psycopg2.connect(**params)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        for full_name in (MV_PLAN_VS_REAL_MONTHLY, MV_PLAN_VS_REAL_MONTHLY_CANONICAL):
            try:
                if concurrent:
                    cur.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {full_name}")
                else:
                    cur.execute(f"REFRESH MATERIALIZED VIEW {full_name}")
            except Exception as e:
                if concurrent:
                    logger.warning(
                        "plan_vs_real: REFRESH CONCURRENTLY %s falló (%s); reintento sin CONCURRENTLY",
                        full_name,
                        e,
                    )
                    cur.execute(f"REFRESH MATERIALIZED VIEW {full_name}")
                else:
                    raise
        cur.close()
        logger.info("plan_vs_real: refresh MV mensuales completado")
    finally:
        conn.close()


def _period_bounds_yyyy_mm(month: str) -> Optional[Tuple[date, date]]:
    """
    Para filtro mes YYYY-MM devuelve [inicio_inclusivo, fin_exclusivo) para predicados
    sargables sobre period_date (evita TO_CHAR(period_date) que impide usar índices).
    """
    if not month or len(month) != 7 or month[4] != "-":
        return None
    try:
        y, mo = int(month[0:4]), int(month[5:7])
        if mo < 1 or mo > 12:
            return None
        start = date(y, mo, 1)
        if mo == 12:
            end = date(y + 1, 1, 1)
        else:
            end = date(y, mo + 1, 1)
        return (start, end)
    except (ValueError, TypeError):
        return None


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
    Obtiene comparación Plan vs Real mensual: prioriza ops.mv_plan_vs_real_monthly_fact[_canonical]
    con fallback a ops.v_plan_vs_real_realkey_final / _canonical.
    Sin LOB: dimensión es real_tipo_servicio (y park_name), no lob_base/segment.
    Filtros opcionales: country, city, real_tipo_servicio, park_id, month (YYYY-MM o YYYY-MM-DD), year (empuja filtro a DB).
    use_canonical: si True, lee MV/vista canónica (real desde v_trips_real_canon).
    year: si se pasa sin mes YYYY-MM, filtra period_date al año (reduce scan).
    Si month es YYYY-MM, se usa rango de fechas [inicio_mes, siguiente_mes) (sargable; reemplaza TO_CHAR en columna).
    Retorna filas con: country, city, park_id, park_name, real_tipo_servicio, period_date (como month),
    trips_plan, trips_real, revenue_plan, revenue_real, gap_trips, gap_revenue, status_bucket.
    """
    month_bounds = _period_bounds_yyyy_mm(month) if month else None
    try:
        with get_db() as conn:
            # Queries de año completo / fallback vista pueden ser pesadas.
            if year is not None and month_bounds is None:
                try:
                    tc = conn.cursor()
                    tc.execute("SET statement_timeout = '600000'")
                    tc.close()
                except Exception:
                    pass
            where_conditions = []
            params: List[Any] = []

            # Filtro de año completo solo si no hay mes YYYY-MM (más selectivo abajo).
            if year is not None and month_bounds is None:
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
            if month_bounds is not None:
                where_conditions.append("period_date >= %s::DATE AND period_date < %s::DATE")
                params.extend([month_bounds[0], month_bounds[1]])
            elif month:
                if len(month) == 7:  # YYYY-MM no parseado; fallback legacy
                    where_conditions.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                    params.append(month)
                else:
                    where_conditions.append("period_date = %s::DATE")
                    params.append(month)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query_sql = """
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
                FROM {relation}
                """ + f"""
                {where_clause}
                ORDER BY period_date DESC NULLS LAST, country, city, park_id, real_tipo_servicio
            """

            t_batch = time.perf_counter()
            results = None
            relation_used: Optional[str] = None
            attempts: List[Dict[str, Any]] = []
            from app.settings import settings as _settings

            for relation in _plan_vs_real_relations_for_read(use_canonical):
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                t_q = time.perf_counter()
                try:
                    cursor.execute(query_sql.format(relation=relation), params)
                    results = cursor.fetchall()
                    q_ms = (time.perf_counter() - t_q) * 1000
                    relation_used = relation
                    attempts.append(
                        {
                            "relation": relation,
                            "ok": True,
                            "query_ms": round(q_ms, 1),
                            "rows": len(results),
                        }
                    )
                    cursor.close()
                    break
                except Exception as e:
                    q_ms = (time.perf_counter() - t_q) * 1000
                    attempts.append(
                        {
                            "relation": relation,
                            "ok": False,
                            "query_ms": round(q_ms, 1),
                            "pgcode": getattr(e, "pgcode", None),
                            "error": str(e)[:240],
                        }
                    )
                    cursor.close()
                    if _should_fallback_plan_vs_real_to_view(e):
                        logger.warning(
                            "plan_vs_real_monthly: intento fallido relation=%s (ms=%.1f) pgcode=%s — fallback",
                            relation,
                            q_ms,
                            getattr(e, "pgcode", None),
                        )
                        conn.rollback()
                        continue
                    raise
            if results is None:
                raise RuntimeError("plan_vs_real: no se pudo leer ninguna fuente (MV ni vista)")

            t_build = time.perf_counter()
            out: List[Dict[str, Any]] = []
            for row in results:
                r = dict(row)
                if r.get("period_date"):
                    r["month"] = r["period_date"].strftime("%Y-%m-%d")
                # API contract: gap = plan - real (positive = plan ahead)
                r["gap_trips"] = (r["trips_plan"] or 0) - (r["trips_real"] or 0) if (r.get("trips_plan") is not None or r.get("trips_real") is not None) else None
                r["gap_revenue"] = (r["revenue_plan"] or 0) - (r["revenue_real"] or 0) if (r.get("revenue_plan") is not None or r.get("revenue_real") is not None) else None
                out.append(r)
            build_ms = (time.perf_counter() - t_build) * 1000
            total_ms = (time.perf_counter() - t_batch) * 1000

            logger.info(
                "plan_vs_real_monthly diag resolved=%s rows=%s build_ms=%.1f total_ms=%.1f use_canonical=%s USE_PLAN_VS_REAL_MONTHLY_MV=%s attempts=%s",
                relation_used,
                len(out),
                build_ms,
                total_ms,
                use_canonical,
                getattr(_settings, "USE_PLAN_VS_REAL_MONTHLY_MV", True),
                attempts,
            )
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
    Alertas Plan vs Real: misma prioridad MV → vista que get_plan_vs_real_monthly.
    Solo filas matched (trips_plan AND trips_real no null). Calcula gap_trips_pct, gap_revenue_pct y alert_level.
    """
    try:
        with get_db() as conn:
            where_base = ["trips_plan IS NOT NULL", "trips_real IS NOT NULL"]
            params: List[Any] = []

            if country:
                where_base.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            mb = _period_bounds_yyyy_mm(month) if month else None
            if mb is not None:
                where_base.append("period_date >= %s::DATE AND period_date < %s::DATE")
                params.extend([mb[0], mb[1]])
            elif month:
                if len(month) == 7:
                    where_base.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                    params.append(month)
                else:
                    where_base.append("period_date = %s::DATE")
                    params.append(month)

            where_clause = " AND ".join(where_base)
            query_template = (
                """
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
                    FROM {relation}
                    WHERE """
                + where_clause
                + """
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
            )

            t_batch = time.perf_counter()
            results = None
            relation_used: Optional[str] = None
            attempts: List[Dict[str, Any]] = []
            from app.settings import settings as _settings

            for relation in _plan_vs_real_relations_for_read(use_canonical):
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                t_q = time.perf_counter()
                try:
                    cursor.execute(query_template.format(relation=relation), params)
                    results = cursor.fetchall()
                    q_ms = (time.perf_counter() - t_q) * 1000
                    relation_used = relation
                    attempts.append({"relation": relation, "ok": True, "query_ms": round(q_ms, 1), "rows": len(results)})
                    cursor.close()
                    break
                except Exception as e:
                    q_ms = (time.perf_counter() - t_q) * 1000
                    attempts.append(
                        {
                            "relation": relation,
                            "ok": False,
                            "query_ms": round(q_ms, 1),
                            "pgcode": getattr(e, "pgcode", None),
                            "error": str(e)[:240],
                        }
                    )
                    cursor.close()
                    if _should_fallback_plan_vs_real_to_view(e):
                        logger.warning(
                            "plan_vs_real_alerts: intento fallido relation=%s (ms=%.1f) — fallback",
                            relation,
                            q_ms,
                        )
                        conn.rollback()
                        continue
                    raise
            if results is None:
                raise RuntimeError("plan_vs_real alerts: no se pudo leer ninguna fuente (MV ni vista)")

            rows = [dict(r) for r in results]
            total_ms = (time.perf_counter() - t_batch) * 1000
            logger.info(
                "plan_vs_real_alerts diag resolved=%s rows_fetched=%s total_ms=%.1f use_canonical=%s USE_PLAN_VS_REAL_MONTHLY_MV=%s attempts=%s",
                relation_used,
                len(rows),
                total_ms,
                use_canonical,
                getattr(_settings, "USE_PLAN_VS_REAL_MONTHLY_MV", True),
                attempts,
            )
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
