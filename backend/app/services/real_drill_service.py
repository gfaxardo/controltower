"""Real LOB drill-down: summary por país/periodo, by-lob y by-park. Fuente: MV ops.mv_real_rollup_day y vistas drill."""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from psycopg2 import ProgrammingError, OperationalError
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

REFRESH_MV_HINT = "Las vistas de drill no están disponibles. Ejecute: alembic upgrade head"

# Columnas mapeadas usadas en vistas (para logs de auditoría)
DRILL_VIEW_COLUMNS = (
    "trip_ts, trip_date, country, city, park_id, park_name_resolved, park_bucket, "
    "lob_group, segment_tag, comision_empresa_asociada, distancia_km"
)


class RealDrillMvNotPopulatedError(Exception):
    """MV o vistas drill no existen o no están pobladas."""

    def __init__(self, hint: str = ""):
        self.hint = hint or REFRESH_MV_HINT
        super().__init__(self.hint)

VIEW_COUNTRY_MONTH = "ops.v_real_drill_country_month"
VIEW_COUNTRY_WEEK = "ops.v_real_drill_country_week"
VIEW_LOB_MONTH = "ops.v_real_drill_lob_month"
VIEW_LOB_WEEK = "ops.v_real_drill_lob_week"
VIEW_PARK_MONTH = "ops.v_real_drill_park_month"
VIEW_PARK_WEEK = "ops.v_real_drill_park_week"
VIEW_BASE = "ops.v_real_trips_base_drill"
MV_ROLLUP = "ops.mv_real_rollup_day"
VIEW_COVERAGE = "ops.v_real_data_coverage"
TIMEOUT_MS = 20000


def _view_country(period_type: str):
    return VIEW_COUNTRY_MONTH if period_type == "monthly" else VIEW_COUNTRY_WEEK


def _view_lob(period_type: str):
    return VIEW_LOB_MONTH if period_type == "monthly" else VIEW_LOB_WEEK


def _view_park(period_type: str):
    return VIEW_PARK_MONTH if period_type == "monthly" else VIEW_PARK_WEEK


def _period_expr_mv(period_type: str) -> str:
    """Expresión de periodo para MV (usa trip_day)."""
    return "date_trunc('month', trip_day)::date" if period_type == "monthly" else "date_trunc('week', trip_day)::date"


def get_real_drill_meta() -> Dict[str, Any]:
    """Último periodo disponible mensual y semanal."""
    out: Dict[str, Any] = {"last_period_monthly": None, "last_period_weekly": None}
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            try:
                cur.execute("SELECT MAX(period_start)::TEXT FROM ops.v_real_drill_country_month")
                row = cur.fetchone()
                if row and row[0]:
                    out["last_period_monthly"] = row[0][:7] if len(row[0]) >= 7 else row[0]
                cur.execute("SELECT MAX(period_start)::TEXT FROM ops.v_real_drill_country_week")
                row = cur.fetchone()
                if row and row[0]:
                    out["last_period_weekly"] = row[0]
            except ProgrammingError as e:
                if "does not exist" in (str(e) or ""):
                    conn.rollback()
            cur.close()
    except Exception as e:
        logger.warning("Real drill meta: %s", e)
    return out


def get_real_drill_coverage() -> List[Dict[str, Any]]:
    """Cobertura por país: last_trip_date, last_month_with_data, last_week_with_data."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            try:
                cur.execute("""
                    SELECT
                        country,
                        last_trip_date::text AS last_trip_date,
                        last_trip_ts,
                        last_month_with_data::text AS last_month_with_data,
                        last_week_with_data::text AS last_week_with_data
                    FROM ops.v_real_data_coverage
                    ORDER BY country
                """)
                rows = cur.fetchall()
                return [dict(r) for r in rows] if rows else []
            except ProgrammingError as e:
                if "does not exist" in (str(e) or "") or "relation" in (str(e) or "").lower():
                    conn.rollback()
                    logger.warning("Real drill coverage: view missing, rollback done, returning []")
                    return []
                raise
    except Exception as e:
        logger.warning("Real drill coverage: %s", e)
        return []


def get_real_drill_summary(
    period_type: str = "monthly",
    segment: Optional[str] = None,
    limit_periods: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Timeline por país y periodo (calendario completo).
    segment: Todos | B2B | B2C. Orden: period_start DESC.
    """
    logger.debug(
        "Real drill summary: using base drill view + mapped columns: %s | period=%s segment=%s",
        DRILL_VIEW_COLUMNS,
        period_type,
        segment or "Todos",
    )
    if limit_periods is None:
        limit_periods = 24 if period_type == "monthly" else 26
    view = _view_country(period_type)
    limit_val = max(limit_periods * 2, 100)

    if segment == "Todos" or not segment or segment.upper() not in ("B2B", "B2C"):
        sql = f"""
            SELECT country, period_start, trips, b2b_trips,
                margin_total_raw, margin_total_pos, margin_unit_pos, distance_total_km, km_prom,
                b2b_pct, last_trip_ts, expected_last_date, falta_data, estado
            FROM {view}
            ORDER BY period_start DESC, trips DESC
            LIMIT %s
        """
        try:
            with get_db() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
                try:
                    cur.execute(sql, [limit_val])
                except ProgrammingError as e:
                    if "does not exist" in (str(e) or ""):
                        conn.rollback()
                        return []
                    raise
                rows = cur.fetchall()
                out = [dict(r) for r in rows] if rows else []
                for r in out:
                    r["expected_last_date"] = r.get("expected_last_date")
                    if r.get("expected_last_date") and hasattr(r["expected_last_date"], "isoformat"):
                        r["expected_last_date"] = r["expected_last_date"].isoformat()[:10] if r["expected_last_date"] else None
                return out
        except Exception as e:
            logger.error("Real drill summary: %s", e)
            raise

    # segment B2B o B2C: query calendarizada desde MV (rápido, sin fullscan)
    seg = segment.upper()
    period_expr = _period_expr_mv(period_type)
    sql_seg = f"""
        WITH
        bounds AS (
            SELECT
                COALESCE((SELECT MIN(min_month) FROM {VIEW_COVERAGE} WHERE min_month IS NOT NULL), date_trunc('month', CURRENT_DATE)::date) AS min_month,
                COALESCE((SELECT MIN(min_week) FROM {VIEW_COVERAGE} WHERE min_week IS NOT NULL), date_trunc('week', CURRENT_DATE)::date) AS min_week,
                date_trunc('month', CURRENT_DATE)::date AS current_month,
                date_trunc('week', CURRENT_DATE)::date AS current_week
        ),
        calendar AS (
            SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
            FROM bounds b
            WHERE %s = 'monthly'
            UNION ALL
            SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
            FROM bounds b
            WHERE %s = 'weekly'
        ),
        countries AS (
            SELECT country FROM (VALUES ('co'),('pe')) v(country)
        ),
        agg AS (
            SELECT
                country,
                {period_expr} AS period_start,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total_raw) AS margin_total_raw,
                SUM(margin_total_pos) AS margin_total_pos,
                SUM(distance_total_km) AS distance_total_km,
                MAX(last_trip_ts) AS last_trip_ts
            FROM {MV_ROLLUP}
            WHERE country IN ('co','pe') AND segment_tag = %s
            GROUP BY country, {period_expr}
        ),
        combined AS (
            SELECT
                c.country,
                cal.period_start,
                COALESCE(a.trips, 0) AS trips,
                COALESCE(a.b2b_trips, 0) AS b2b_trips,
                a.margin_total_raw,
                a.margin_total_pos,
                CASE WHEN COALESCE(a.trips, 0) > 0 AND a.margin_total_pos IS NOT NULL THEN a.margin_total_pos / a.trips ELSE NULL END AS margin_unit_pos,
                a.distance_total_km,
                CASE WHEN COALESCE(a.trips, 0) > 0 AND a.distance_total_km IS NOT NULL THEN a.distance_total_km / a.trips ELSE NULL END AS km_prom,
                1.0::numeric AS b2b_pct,
                a.last_trip_ts,
                CASE WHEN %s = 'monthly' THEN LEAST(CURRENT_DATE - 1, (cal.period_start + interval '1 month' - interval '1 day')::date)
                     ELSE LEAST(CURRENT_DATE - 1, cal.period_start + 6) END AS expected_last_date,
                (CASE WHEN %s = 'monthly' THEN (cal.period_start = (SELECT current_month FROM bounds)) ELSE (cal.period_start = (SELECT current_week FROM bounds)) END)
                    AND (a.last_trip_ts IS NULL OR a.last_trip_ts::date < (CASE WHEN %s = 'monthly' THEN LEAST(CURRENT_DATE - 1, (cal.period_start + interval '1 month' - interval '1 day')::date) ELSE LEAST(CURRENT_DATE - 1, cal.period_start + 6) END))
                    AS falta_data,
                CASE
                    WHEN (CASE WHEN %s = 'monthly' THEN (cal.period_start = (SELECT current_month FROM bounds)) ELSE (cal.period_start = (SELECT current_week FROM bounds)) END)
                         AND (a.last_trip_ts IS NULL OR a.last_trip_ts::date < (CASE WHEN %s = 'monthly' THEN LEAST(CURRENT_DATE - 1, (cal.period_start + interval '1 month' - interval '1 day')::date) ELSE LEAST(CURRENT_DATE - 1, cal.period_start + 6) END))
                    THEN 'FALTA_DATA'
                    WHEN (CASE WHEN %s = 'monthly' THEN (cal.period_start = (SELECT current_month FROM bounds)) ELSE (cal.period_start = (SELECT current_week FROM bounds)) END)
                    THEN 'ABIERTO'
                    WHEN (cal.period_start < (CASE WHEN %s = 'monthly' THEN (SELECT current_month FROM bounds) ELSE (SELECT current_week FROM bounds) END)) AND COALESCE(a.trips, 0) = 0
                    THEN 'VACIO'
                    ELSE 'CERRADO'
                END AS estado
            FROM countries c
            CROSS JOIN (SELECT DISTINCT period_start FROM calendar) cal
            LEFT JOIN agg a ON a.country = c.country AND a.period_start = cal.period_start
        )
        SELECT country, period_start, trips, b2b_trips,
            margin_total_raw, margin_total_pos, margin_unit_pos, distance_total_km, km_prom,
            b2b_pct, last_trip_ts, expected_last_date, falta_data, estado
        FROM combined
        ORDER BY period_start DESC, trips DESC
        LIMIT %s
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            try:
                cur.execute(sql_seg, [period_type, period_type, seg, period_type, period_type, period_type, period_type, period_type, period_type, limit_val])
            except ProgrammingError as e:
                if "does not exist" in (str(e) or ""):
                    conn.rollback()
                    return []
                raise
            rows = cur.fetchall()
            out = [dict(r) for r in rows] if rows else []
            for r in out:
                if r.get("expected_last_date") and hasattr(r["expected_last_date"], "isoformat"):
                    r["expected_last_date"] = r["expected_last_date"].isoformat()[:10] if r["expected_last_date"] else None
            return out
    except Exception as e:
        logger.error("Real drill summary segment: %s", e)
        raise


def get_real_drill_summary_countries(
    period_type: str = "monthly",
    segment: Optional[str] = None,
    limit_periods: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Summary por país: { countries: [ { country, coverage, kpis, rows } ], meta }.
    KPIs calculados sobre los rows visibles (periodo en pantalla). Orden: pe, co.
    """
    flat_rows = get_real_drill_summary(
        period_type=period_type,
        segment=segment,
        limit_periods=limit_periods,
    )
    coverage_list = get_real_drill_coverage()
    coverage_by_country = { (c.get("country") or "").strip().lower(): c for c in coverage_list }

    by_country: Dict[str, List[Dict[str, Any]]] = {}
    for r in flat_rows:
        c = (r.get("country") or "").strip().lower()
        if c not in ("co", "pe"):
            continue
        if c not in by_country:
            by_country[c] = []
        by_country[c].append(r)

    def kpis_from_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_trips = sum((x.get("trips") or 0) for x in rows)
        total_b2b = sum((x.get("b2b_trips") or 0) for x in rows)
        margin_total_pos = sum((x.get("margin_total_pos") or 0) for x in rows)
        distance_total_km = sum((x.get("distance_total_km") or 0) for x in rows)
        last_period = None
        for x in rows:
            ps = x.get("period_start")
            if ps and (x.get("trips") or 0) > 0:
                if hasattr(ps, "isoformat"):
                    last_period = ps.isoformat()[:10] if ps else None
                else:
                    last_period = str(ps)[:10]
                break
        if last_period is None and rows:
            ps = rows[0].get("period_start")
            if hasattr(ps, "isoformat"):
                last_period = ps.isoformat()[:10] if ps else None
            else:
                last_period = str(ps)[:10] if ps else None
        if period_type == "monthly" and last_period and len(str(last_period)) >= 7:
            last_period = str(last_period)[:7]
        return {
            "total_trips": total_trips,
            "margin_total_pos": round(margin_total_pos, 4) if margin_total_pos is not None else None,
            "margin_unit_pos": round(margin_total_pos / total_trips, 4) if total_trips and margin_total_pos is not None else None,
            "km_prom": round(distance_total_km / total_trips, 4) if total_trips and distance_total_km is not None else None,
            "b2b_trips": total_b2b,
            "b2b_pct": round(total_b2b / total_trips, 4) if total_trips else None,
            "last_period": last_period,
        }

    countries_out: List[Dict[str, Any]] = []
    for country_code in ("pe", "co"):
        if country_code not in by_country:
            countries_out.append({
                "country": country_code,
                "coverage": coverage_by_country.get(country_code) or {},
                "kpis": kpis_from_rows([]),
                "rows": [],
            })
            continue
        rows = by_country[country_code]
        cov = coverage_by_country.get(country_code) or {}
        countries_out.append({
            "country": country_code,
            "coverage": {
                "last_trip_date": cov.get("last_trip_date"),
                "last_month_with_data": cov.get("last_month_with_data"),
                "last_week_with_data": cov.get("last_week_with_data"),
            },
            "kpis": kpis_from_rows(rows),
            "rows": rows,
        })

    meta = get_real_drill_meta()
    return {
        "countries": countries_out,
        "meta": {
            "last_period_monthly": meta.get("last_period_monthly"),
            "last_period_weekly": meta.get("last_period_weekly"),
        },
    }


def get_real_drill_by_lob(
    period_type: str,
    country: str,
    period_start: str,
    segment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Desglose por LOB para un país y periodo. Orden: trips DESC."""
    view = _view_lob(period_type)
    country_lo = country.strip().lower()

    if segment == "Todos" or not segment or segment.upper() not in ("B2B", "B2C"):
        sql = f"""
            SELECT lob_group, trips, b2b_trips,
                margin_total_raw, margin_total_pos, margin_unit_pos, distance_total_km, km_prom
            FROM {view}
            WHERE LOWER(TRIM(country)) = %s AND period_start = %s::date
            ORDER BY trips DESC
        """
        params: List[Any] = [country_lo, period_start]
    else:
        seg = segment.upper()
        period_expr_mv = _period_expr_mv(period_type)
        sql = f"""
            SELECT
                lob_group,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total_raw) AS margin_total_raw,
                SUM(margin_total_pos) AS margin_total_pos,
                CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
                SUM(distance_total_km) AS distance_total_km,
                CASE WHEN SUM(trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom
            FROM {MV_ROLLUP}
            WHERE LOWER(TRIM(country)) = %s AND {period_expr_mv} = %s::date AND segment_tag = %s
            GROUP BY lob_group
            ORDER BY trips DESC
        """
        params = [country_lo, period_start, seg]

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            try:
                cur.execute(sql, params)
            except ProgrammingError as e:
                if "does not exist" in (str(e) or ""):
                    conn.rollback()
                    return []
                raise
            rows = cur.fetchall()
            out = [dict(r) for r in rows] if rows else []
            if segment and segment.upper() == "B2B":
                for r in out:
                    r["b2b_trips"] = r.get("trips") or 0
            return out
    except Exception as e:
        logger.error("Real drill by-lob: %s", e)
        raise


def get_real_drill_by_park(
    period_type: str,
    country: str,
    period_start: str,
    segment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Desglose por park para un país y periodo. Orden: trips DESC. Incluye park_bucket."""
    view = _view_park(period_type)
    country_lo = country.strip().lower()

    if segment == "Todos" or not segment or segment.upper() not in ("B2B", "B2C"):
        sql = f"""
            SELECT city, park_id, park_name_resolved, park_bucket,
                trips, b2b_trips,
                margin_total_raw, margin_total_pos, margin_unit_pos, distance_total_km, km_prom
            FROM {view}
            WHERE LOWER(TRIM(country)) = %s AND period_start = %s::date
            ORDER BY trips DESC
        """
        params: List[Any] = [country_lo, period_start]
    else:
        seg = segment.upper()
        period_expr_mv = _period_expr_mv(period_type)
        sql = f"""
            SELECT
                city,
                park_id,
                park_name_resolved,
                park_bucket,
                SUM(trips) AS trips,
                SUM(b2b_trips) AS b2b_trips,
                SUM(margin_total_raw) AS margin_total_raw,
                SUM(margin_total_pos) AS margin_total_pos,
                CASE WHEN SUM(trips) > 0 AND SUM(margin_total_pos) IS NOT NULL THEN SUM(margin_total_pos) / SUM(trips) ELSE NULL END AS margin_unit_pos,
                SUM(distance_total_km) AS distance_total_km,
                CASE WHEN SUM(trips) > 0 AND SUM(distance_total_km) IS NOT NULL THEN SUM(distance_total_km) / SUM(trips) ELSE NULL END AS km_prom
            FROM {MV_ROLLUP}
            WHERE LOWER(TRIM(country)) = %s AND {period_expr_mv} = %s::date AND segment_tag = %s
            GROUP BY city, park_id, park_name_resolved, park_bucket
            ORDER BY trips DESC
        """
        params = [country_lo, period_start, seg]

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            try:
                cur.execute(sql, params)
            except ProgrammingError as e:
                if "does not exist" in (str(e) or ""):
                    conn.rollback()
                    return []
                raise
            rows = cur.fetchall()
            out = [dict(r) for r in rows] if rows else []
            if segment and segment.upper() == "B2B":
                for r in out:
                    r["b2b_trips"] = r.get("trips") or 0
            return out
    except Exception as e:
        logger.error("Real drill by-park: %s", e)
        raise


def refresh_real_drill_mv() -> Dict[str, Any]:
    """
    Refresca la MV ops.mv_real_rollup_day (CONCURRENTLY si hay índice único).
    Uso interno: cron diario o POST /ops/real-drill/refresh.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SET statement_timeout = '0'")  # Sin límite para refresh (MV grande)
            try:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_rollup_day")
            except (ProgrammingError, OperationalError) as e:
                err = (str(e) or "").lower()
                if "concurrent" in err or "unique" in err or "unique index" in err:
                    conn.rollback()
                    cur.execute("REFRESH MATERIALIZED VIEW ops.mv_real_rollup_day")
                else:
                    raise
            cur.close()
        return {"ok": True, "message": "MV ops.mv_real_rollup_day refreshed"}
    except Exception as e:
        logger.error("Real drill MV refresh: %s", e)
        raise


def get_real_drill_totals(
    period_type: str = "monthly",
    segment: Optional[str] = None,
    limit_periods: Optional[int] = None,
) -> Dict[str, Any]:
    """Totales sobre el rango mostrado (deprecado: usar countries[].kpis). margin_total = margin_total_pos."""
    summary = get_real_drill_summary(
        period_type=period_type,
        segment=segment,
        limit_periods=limit_periods or (24 if period_type == "monthly" else 26),
    )
    total_trips = sum((r.get("trips") or 0) for r in summary)
    total_b2b = sum((r.get("b2b_trips") or 0) for r in summary)
    total_margin_pos = sum((r.get("margin_total_pos") or 0) for r in summary)
    total_distance_km = sum((r.get("distance_total_km") or 0) for r in summary)
    last_ts = None
    for r in summary:
        t = r.get("last_trip_ts")
        if t and (last_ts is None or t > last_ts):
            last_ts = t
    return {
        "total_trips": total_trips,
        "total_b2b_trips": total_b2b,
        "b2b_ratio_pct": round(100 * total_b2b / total_trips, 2) if total_trips else None,
        "margin_total": total_margin_pos,
        "margin_unit_avg_global": round(total_margin_pos / total_trips, 4) if total_trips else None,
        "distance_total_km": round(total_distance_km, 4) if total_distance_km is not None else None,
        "distance_km_avg_global": round(total_distance_km / total_trips, 4) if total_trips and total_distance_km is not None else None,
        "last_trip_ts": last_ts.isoformat() if hasattr(last_ts, "isoformat") else last_ts,
    }
