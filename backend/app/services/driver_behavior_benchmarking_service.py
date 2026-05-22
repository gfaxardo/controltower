"""
Driver Behavior Benchmarking Layer — Fase 2A.2
Compara patrones operativos de conductores TOP vs DECLINING/AT-RISK.
Fuente primaria: ops.driver_daily_activity_fact (pre-agregada, optimizada).
Fallback: public.trips_2026 solo si fact table no existe o está vacía.
Enriquecimiento desde trips_2026: opcional, apagado por defecto.
No genera recomendaciones. Solo diagnóstico comparativo.
"""
from __future__ import annotations

from typing import Any, Optional
from datetime import date, datetime, timedelta
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

TIMEOUT_MS = 120000
FACT_TABLE = "ops.driver_daily_activity_fact"

LIFECYCLE_GROUPS = [
    "TOP_PERFORMER",
    "STABLE",
    "GROWING",
    "DECLINING",
    "AT_RISK",
    "DORMANT",
    "CHURNED",
    "REACTIVATED",
]


def _cursor(conn):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
    return c


def _fact_table_exists_and_has_data(conn) -> tuple[bool, bool, Optional[dict]]:
    """Verifica si ops.driver_daily_activity_fact existe y tiene datos.
    Retorna (exists, has_data, metadata).
    metadata = { rows_count, drivers_count, min_date, max_date } si has_data."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'ops' AND table_name = 'driver_daily_activity_fact'
            ) AS table_exists
            """
        )
        row = cur.fetchone()
        if not row or not row.get("table_exists"):
            return False, False, None

        cur.execute(
            """
            SELECT
                COUNT(*) AS rows_count,
                COUNT(DISTINCT driver_id) AS drivers_count,
                MIN(activity_date) AS min_date,
                MAX(activity_date) AS max_date
            FROM ops.driver_daily_activity_fact
            """
        )
        meta = dict(cur.fetchone())
        has_data = (meta.get("rows_count") or 0) > 0
        return True, has_data, meta if has_data else None
    except Exception as e:
        logger.warning("Fact table check failed: %s", e)
        return False, False, None
    finally:
        cur.close()


def _resolve_primary_source(conn) -> dict:
    """Resuelve la fuente primaria y devuelve metadata de fuente.
    Retorna dict con: data_source, source_type, source_warning, fallback_reason, fact_meta."""
    exists, has_data, meta = _fact_table_exists_and_has_data(conn)

    if exists and has_data:
        return {
            "data_source": FACT_TABLE,
            "source_type": "pre_aggregated_fact",
            "source_warning": None,
            "fallback_reason": None,
            "fact_meta": meta,
            "use_trips_fallback": False,
        }

    if exists and not has_data:
        return {
            "data_source": "public.trips_2026",
            "source_type": "raw_trips_fallback",
            "source_warning": f"{FACT_TABLE} existe pero está vacía. Usando public.trips_2026 como fallback.",
            "fallback_reason": "fact_table_empty",
            "fact_meta": None,
            "use_trips_fallback": True,
        }

    return {
        "data_source": "public.trips_2026",
        "source_type": "raw_trips_fallback",
        "source_warning": f"{FACT_TABLE} no existe. Usando public.trips_2026 como fallback.",
        "fallback_reason": "fact_table_not_found",
        "fact_meta": None,
        "use_trips_fallback": True,
    }


def _detect_fact_columns(conn) -> dict:
    """Descubre las columnas disponibles en la fact table."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'driver_daily_activity_fact'
            ORDER BY ordinal_position
            """
        )
        cols = {r["column_name"]: r["data_type"] for r in cur.fetchall()}

        available = {
            "trips": "completed_trips" in cols,
            "active_days_from_activity_date": "activity_date" in cols,
            "country": "country" in cols,
            "city": "city" in cols,
            "park_id": "park_id" in cols,
            "weekend_share": "activity_date" in cols,
            "revenue": False,
            "avg_ticket": False,
            "trip_hour": False,
            "distance": False,
            "duration": False,
            "tipo_servicio": False,
            "cancellation": False,
            "online_hours": False,
            "zone": False,
            "acceptance": False,
        }

        source_enriched = {
            "revenue": False,
            "avg_ticket": False,
            "trip_hour": False,
            "distance": False,
            "duration": False,
            "tipo_servicio": False,
            "cancellation": False,
        }
        available["_enrich_available"] = source_enriched
        return available
    except Exception:
        return {
            "trips": False, "active_days_from_activity_date": False,
            "country": False, "city": False, "park_id": False,
            "weekend_share": False, "revenue": False, "avg_ticket": False,
            "trip_hour": False, "distance": False, "duration": False,
            "tipo_servicio": False, "cancellation": False,
            "online_hours": False, "zone": False, "acceptance": False,
            "_enrich_available": {},
        }
    finally:
        cur.close()


def _date_range(period_days: int, end_date: Optional[str] = None) -> tuple[str, str, str, str]:
    """Devuelve (current_start, current_end, prior_start, prior_end) en YYYY-MM-DD."""
    if end_date:
        end_dt = date.fromisoformat(end_date)
    else:
        end_dt = date.today()
    current_start = end_dt - timedelta(days=period_days)
    prior_end = current_start
    prior_start = prior_end - timedelta(days=period_days)
    return (
        current_start.isoformat(),
        end_dt.isoformat(),
        prior_start.isoformat(),
        prior_end.isoformat(),
    )


def _build_available_metrics_info(source_info: dict, fact_available: dict) -> tuple[list, list]:
    """Construye listas de available_metrics y missing_metrics basadas en la fuente real."""
    if source_info["use_trips_fallback"]:
        available_list = ["trips", "active_days", "trip_date", "park_id"]
        missing_list = ["revenue", "avg_ticket", "trip_hour", "distance", "duration",
                        "online_hours", "zone", "acceptance", "tipo_servicio"]
        return available_list, missing_list

    avail = []
    missing = []
    for k, v in fact_available.items():
        if k.startswith("_"):
            continue
        if v:
            avail.append(k)
        else:
            missing.append(k)

    if "weekend_share" not in avail and fact_available.get("weekend_share"):
        avail.append("weekend_share")

    return avail, missing


def _build_driver_metrics_from_fact(
    country: Optional[str],
    city: Optional[str],
    current_start: str,
    current_end: str,
    prior_start: str,
    prior_end: str,
    period_days: int,
) -> tuple[str, dict]:
    """Construye la query SQL usando ops.driver_daily_activity_fact como fuente primaria."""

    current_where = [
        f"f.activity_date >= '{current_start}'::date",
        f"f.activity_date < '{current_end}'::date + INTERVAL '1 day'",
        "f.driver_id IS NOT NULL",
        "TRIM(f.driver_id) != ''",
    ]
    prior_where = [
        f"f.activity_date >= '{prior_start}'::date",
        f"f.activity_date < '{prior_end}'::date + INTERVAL '1 day'",
        "f.driver_id IS NOT NULL",
        "TRIM(f.driver_id) != ''",
    ]
    last_where = [
        "f.driver_id IS NOT NULL",
        "TRIM(f.driver_id) != ''",
    ]

    if city:
        current_where.append(f"f.city = '{city}'")
        prior_where.append(f"f.city = '{city}'")
    if country:
        current_where.append(f"f.country = '{country}'")
        prior_where.append(f"f.country = '{country}'")

    current_where_sql = "\n              AND ".join(current_where)
    prior_where_sql = "\n              AND ".join(prior_where)
    last_where_sql = "\n              AND ".join(last_where)

    day_end = (date.today() + timedelta(days=1)).isoformat()

    query = f"""
    WITH driver_current AS (
        SELECT
            f.driver_id AS driver_key,
            SUM(f.completed_trips) AS total_trips,
            COUNT(DISTINCT f.activity_date) AS active_days,
            COUNT(*) FILTER (WHERE EXTRACT(DOW FROM f.activity_date) IN (0, 6)) AS weekend_trips,
            MAX(f.city) FILTER (WHERE f.city IS NOT NULL) AS city,
            MAX(f.country) FILTER (WHERE f.country IS NOT NULL) AS country,
            MAX(f.park_id) FILTER (WHERE f.park_id IS NOT NULL) AS park_id
        FROM {FACT_TABLE} f
        WHERE {current_where_sql}
        GROUP BY f.driver_id
    ),
    driver_prior AS (
        SELECT
            f.driver_id AS driver_key,
            SUM(f.completed_trips) AS prior_trips
        FROM {FACT_TABLE} f
        WHERE {prior_where_sql}
        GROUP BY f.driver_id
    ),
    last_trip AS (
        SELECT
            f.driver_id AS driver_key,
            MAX(f.activity_date) AS last_trip_date
        FROM {FACT_TABLE} f
        WHERE {last_where_sql}
        GROUP BY f.driver_id
    )
    SELECT
        dc.*,
        COALESCE(dp.prior_trips, 0) AS prior_trips,
        lt.last_trip_date,
        ('{day_end}'::date - lt.last_trip_date::date) AS days_since_last_trip
    FROM driver_current dc
    LEFT JOIN driver_prior dp ON dp.driver_key = dc.driver_key
    LEFT JOIN last_trip lt ON lt.driver_key = dc.driver_key
    """

    return query, {}


def _build_driver_metrics_from_trips(
    current_start: str,
    current_end: str,
    prior_start: str,
    prior_end: str,
    country: Optional[str],
    city: Optional[str],
) -> tuple[str, dict]:
    """Fallback: construye query desde public.trips_2026 cuando fact table no existe."""
    where_current = [
        "t.condicion = 'Completado'",
        f"t.fecha_inicio_viaje >= '{current_start}'::timestamp",
        f"t.fecha_inicio_viaje < '{current_end}'::timestamp + INTERVAL '1 day'",
        "t.conductor_id IS NOT NULL",
        "TRIM(t.conductor_id) != ''",
    ]
    where_prior = [
        "t.condicion = 'Completado'",
        f"t.fecha_inicio_viaje >= '{prior_start}'::timestamp",
        f"t.fecha_inicio_viaje < '{prior_end}'::timestamp + INTERVAL '1 day'",
        "t.conductor_id IS NOT NULL",
        "TRIM(t.conductor_id) != ''",
    ]

    park_join = ""
    if city or country:
        park_join = "LEFT JOIN dim.dim_park p ON t.park_id = p.park_id"

    if city:
        where_current.append(f"p.city = '{city}'")
        where_prior.append(f"p.city = '{city}'")
    if country:
        where_current.append(f"p.country = '{country}'")
        where_prior.append(f"p.country = '{country}'")

    where_current_sql = "\n              AND ".join(where_current)
    where_prior_sql = "\n              AND ".join(where_prior)
    day_end = (date.today() + timedelta(days=1)).isoformat()

    query = f"""
    WITH driver_current AS (
        SELECT
            t.conductor_id AS driver_key,
            COUNT(*) AS total_trips,
            COUNT(DISTINCT t.fecha_inicio_viaje::date) AS active_days,
            COUNT(*) FILTER (WHERE EXTRACT(DOW FROM t.fecha_inicio_viaje) IN (0, 6)) AS weekend_trips
        FROM public.trips_2026 t
        {park_join}
        WHERE {where_current_sql}
        GROUP BY t.conductor_id
    ),
    driver_prior AS (
        SELECT
            t.conductor_id AS driver_key,
            COUNT(*) AS prior_trips
        FROM public.trips_2026 t
        {park_join}
        WHERE {where_prior_sql}
        GROUP BY t.conductor_id
    ),
    last_trip AS (
        SELECT
            t.conductor_id AS driver_key,
            MAX(t.fecha_inicio_viaje) AS last_trip_date
        FROM public.trips_2026 t
        WHERE t.condicion = 'Completado'
          AND t.conductor_id IS NOT NULL
          AND TRIM(t.conductor_id) != ''
        GROUP BY t.conductor_id
    )
    SELECT
        dc.*,
        COALESCE(dp.prior_trips, 0) AS prior_trips,
        lt.last_trip_date,
        ('{day_end}'::date - lt.last_trip_date::date) AS days_since_last_trip
    FROM driver_current dc
    LEFT JOIN driver_prior dp ON dp.driver_key = dc.driver_key
    LEFT JOIN last_trip lt ON lt.driver_key = dc.driver_key
    """

    return query, {}


def _build_distribution_from_fact(
    dimension: str,
    driver_keys: list,
    current_start: str,
    current_end: str,
) -> str:
    """Construye query de distribución desde fact table para city/park."""
    if not driver_keys:
        return "SELECT NULL AS label, 0 AS trips, 0 AS driver_count WHERE FALSE"

    driver_list = "', '".join(str(dk) for dk in driver_keys)

    if dimension == "city":
        dim_col = "COALESCE(NULLIF(TRIM(f.city), ''), 'UNKNOWN')"
    elif dimension == "park":
        dim_col = "COALESCE(NULLIF(TRIM(f.park_id), ''), 'UNKNOWN')"
    else:
        return "SELECT NULL AS label, 0 AS trips, 0 AS driver_count WHERE FALSE"

    return f"""
    SELECT
        {dim_col} AS label,
        SUM(f.completed_trips) AS trips,
        COUNT(DISTINCT f.driver_id) AS driver_count
    FROM {FACT_TABLE} f
    WHERE f.driver_id IN ('{driver_list}')
      AND f.activity_date >= '{current_start}'::date
      AND f.activity_date < '{current_end}'::date + INTERVAL '1 day'
    GROUP BY label
    ORDER BY trips DESC
    """


def _classify_driver(driver: dict, top_threshold: int, period_days: int) -> str:
    """Clasifica un conductor en un grupo lifecycle según sus métricas."""
    trips = driver.get("total_trips") or 0
    active_days = driver.get("active_days") or 0
    prior_trips = driver.get("prior_trips") or 0
    days_since_last = driver.get("days_since_last_trip")

    if days_since_last is not None:
        if days_since_last >= 30:
            return "CHURNED"
        if days_since_last >= 14:
            return "DORMANT"

    if trips == 0:
        return "DORMANT"

    is_top = trips >= top_threshold and active_days >= (period_days * 0.3)

    if prior_trips > 0:
        delta_pct = (trips - prior_trips) / prior_trips * 100
    elif trips > 0:
        delta_pct = 100
    else:
        delta_pct = 0

    if is_top:
        return "TOP_PERFORMER"

    if trips <= 3 and active_days <= 3:
        return "AT_RISK"

    if delta_pct <= -40:
        return "AT_RISK"

    if delta_pct <= -25:
        return "DECLINING"

    if delta_pct >= 25:
        return "GROWING"

    return "STABLE"


def _build_group_benchmarks(drivers: list[dict], group_name: str, period_days: int) -> dict:
    """Construye el benchmark para un grupo de conductores."""
    if not drivers:
        return {
            "group_name": group_name,
            "drivers_count": 0,
            "total_trips": 0,
            "avg_trips_per_driver": 0,
            "avg_active_days": 0,
            "trips_per_active_day": 0,
            "consistency_score": 0,
            "avg_ticket": None,
            "revenue_per_driver": None,
            "peak_hour_share": None,
            "weekend_share": None,
            "avg_distance_km": None,
            "avg_duration_sec": None,
        }

    count = len(drivers)
    total_trips = sum(d.get("total_trips") or 0 for d in drivers)
    total_active_days = sum(d.get("active_days") or 0 for d in drivers)

    has_weekend = any(d.get("weekend_trips") is not None for d in drivers)
    weekend_trips = sum(d.get("weekend_trips") or 0 for d in drivers) if has_weekend else None

    avg_trips = round(total_trips / count, 2) if count else 0
    avg_active_days = round(total_active_days / count, 2) if count else 0
    trips_per_active_day = round(total_trips / total_active_days, 2) if total_active_days else 0

    consistency_scores = []
    for d in drivers:
        ad = d.get("active_days") or 0
        if period_days > 0:
            consistency_scores.append(round(ad / period_days, 4))
    consistency_score = round(sum(consistency_scores) / len(consistency_scores), 4) if consistency_scores else 0

    weekend_share = None
    if has_weekend and total_trips > 0:
        weekend_share = round(weekend_trips / total_trips, 4)

    result = {
        "group_name": group_name,
        "drivers_count": count,
        "total_trips": total_trips,
        "avg_trips_per_driver": avg_trips,
        "avg_active_days": avg_active_days,
        "trips_per_active_day": trips_per_active_day,
        "consistency_score": consistency_score,
        "avg_ticket": None,
        "revenue_per_driver": None,
        "peak_hour_share": None,
        "weekend_share": weekend_share,
        "avg_distance_km": None,
        "avg_duration_sec": None,
    }

    return result


def _compare_groups(top: dict, declining: dict, at_risk: dict) -> list[dict]:
    """Compara TOP_PERFORMER vs DECLINING y AT_RISK, devolviendo gaps e interpretaciones."""
    comparisons = []

    metrics_to_compare = [
        ("avg_trips_per_driver", "Viajes promedio por conductor", "trips"),
        ("avg_active_days", "Días activos promedio", "days"),
        ("trips_per_active_day", "Viajes por día activo", "trips/day"),
        ("consistency_score", "Score de consistencia", "ratio"),
        ("avg_ticket", "Ticket promedio", "currency"),
        ("revenue_per_driver", "Revenue por conductor", "currency"),
        ("peak_hour_share", "Proporción horas pico", "ratio"),
        ("weekend_share", "Proporción fines de semana", "ratio"),
    ]

    for metric_key, metric_label, unit in metrics_to_compare:
        top_val = top.get(metric_key)
        dec_val = declining.get(metric_key)
        risk_val = at_risk.get(metric_key)

        if top_val is None:
            continue

        gap_top_vs_dec = None
        gap_top_vs_risk = None
        interpretation = ""

        if dec_val is not None and top_val and dec_val:
            if unit == "currency":
                gap_top_vs_dec = round(top_val - dec_val, 2)
                if gap_top_vs_dec > 0:
                    interpretation = f"Los TOP_PERFORMER generan {abs(gap_top_vs_dec):.2f} más de {metric_label.lower()} que DECLINING."
                elif gap_top_vs_dec < 0:
                    interpretation = f"Los TOP_PERFORMER generan {abs(gap_top_vs_dec):.2f} menos de {metric_label.lower()} que DECLINING."
                else:
                    interpretation = f"Sin diferencia en {metric_label.lower()} entre TOP_PERFORMER y DECLINING."
            elif unit == "ratio":
                gap_top_vs_dec = round(top_val - dec_val, 4)
                pct = abs(gap_top_vs_dec) * 100
                if gap_top_vs_dec > 0:
                    interpretation = f"Los TOP_PERFORMER tienen {pct:.1f} puntos porcentuales más de {metric_label.lower()} que DECLINING."
                elif gap_top_vs_dec < 0:
                    interpretation = f"Los TOP_PERFORMER tienen {pct:.1f} puntos porcentuales menos de {metric_label.lower()} que DECLINING."
                else:
                    interpretation = f"Sin diferencia en {metric_label.lower()} entre TOP_PERFORMER y DECLINING."
            else:
                gap_top_vs_dec = round(top_val - dec_val, 2)
                if gap_top_vs_dec > 0:
                    pct = round(abs(gap_top_vs_dec) / max(dec_val, 0.01) * 100, 1)
                    interpretation = f"Los TOP_PERFORMER tienen {pct}% más {metric_label.lower()} que DECLINING."
                elif gap_top_vs_dec < 0:
                    pct = round(abs(gap_top_vs_dec) / max(top_val, 0.01) * 100, 1)
                    interpretation = f"Los TOP_PERFORMER tienen {pct}% menos {metric_label.lower()} que DECLINING."
                else:
                    interpretation = f"Sin diferencia en {metric_label.lower()} entre TOP_PERFORMER y DECLINING."

        if risk_val is not None and top_val and risk_val:
            if unit == "currency":
                gap_top_vs_risk = round(top_val - risk_val, 2)
            elif unit == "ratio":
                gap_top_vs_risk = round(top_val - risk_val, 4)
            else:
                gap_top_vs_risk = round(top_val - risk_val, 2)

            if not interpretation:
                if unit == "ratio":
                    pct_val = abs(gap_top_vs_risk) * 100
                    if gap_top_vs_risk > 0:
                        interpretation = f"Los TOP_PERFORMER tienen {pct_val:.1f} puntos porcentuales más de {metric_label.lower()} que AT_RISK."
                    elif gap_top_vs_risk < 0:
                        interpretation = f"Los TOP_PERFORMER tienen {pct_val:.1f} puntos porcentuales menos de {metric_label.lower()} que AT_RISK."
                else:
                    if gap_top_vs_risk > 0:
                        pct_val = round(abs(gap_top_vs_risk) / max(risk_val, 0.01) * 100, 1)
                        interpretation = f"Los TOP_PERFORMER tienen {pct_val}% más {metric_label.lower()} que AT_RISK."
                    elif gap_top_vs_risk < 0:
                        pct_val = round(abs(gap_top_vs_risk) / max(top_val, 0.01) * 100, 1)
                        interpretation = f"Los TOP_PERFORMER tienen {pct_val}% menos {metric_label.lower()} que AT_RISK."

        comparisons.append({
            "metric": metric_key,
            "metric_label": metric_label,
            "unit": unit,
            "top_performer_value": top_val,
            "declining_value": dec_val,
            "at_risk_value": risk_val,
            "gap_top_vs_declining": gap_top_vs_dec,
            "gap_top_vs_at_risk": gap_top_vs_risk,
            "interpretation": interpretation,
        })

    return comparisons


def _fetch_and_classify_drivers(
    conn,
    country: Optional[str],
    city: Optional[str],
    period_days: int,
    source_info: dict,
) -> tuple[list[dict], dict, dict, tuple[str, str, str, str]]:
    """Obtiene métricas de conductores y los clasifica."""
    current_start, current_end, prior_start, prior_end = _date_range(period_days)

    if source_info["use_trips_fallback"]:
        query, _ = _build_driver_metrics_from_trips(
            current_start, current_end, prior_start, prior_end,
            country=country, city=city,
        )
    else:
        query, _ = _build_driver_metrics_from_fact(
            country, city, current_start, current_end,
            prior_start, prior_end, period_days,
        )

    cur = _cursor(conn)
    cur.execute(query)
    all_drivers = [dict(r) for r in cur.fetchall()]
    cur.close()

    if not all_drivers:
        classified = {}
        return all_drivers, classified, {}, (current_start, current_end, prior_start, prior_end)

    trips_list = sorted([d.get("total_trips") or 0 for d in all_drivers], reverse=True)
    n = len(trips_list)
    idx_80 = max(0, int(n * 0.20) - 1)
    top_threshold = trips_list[idx_80] if idx_80 < n else 0
    if top_threshold == 0 and n > 0:
        top_threshold = max(1, trips_list[0] // 2)

    classified = {}
    for d in all_drivers:
        group = _classify_driver(d, top_threshold, period_days)
        classified.setdefault(group, []).append(d)

    thresholds = {"top_threshold": top_threshold, "percentile_80_idx": idx_80}
    return all_drivers, classified, thresholds, (current_start, current_end, prior_start, prior_end)


def get_behavior_benchmarking_summary(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    """
    GET /driver-behavior/summary
    Resumen de benchmarking: total drivers, grupos, métricas disponibles y faltantes.
    """
    with get_db() as conn:
        source_info = _resolve_primary_source(conn)
        fact_available = _detect_fact_columns(conn)

        all_drivers, classified, thresholds, date_tuple = _fetch_and_classify_drivers(
            conn, country, city, period_days, source_info,
        )
        current_start, current_end, _p1, _p2 = date_tuple

    available_metrics, missing_metrics = _build_available_metrics_info(source_info, fact_available)

    return {
        "total_drivers_analyzed": len(all_drivers),
        "groups_count": len(classified),
        "top_performer_count": len(classified.get("TOP_PERFORMER", [])),
        "declining_count": len(classified.get("DECLINING", [])),
        "at_risk_count": len(classified.get("AT_RISK", [])),
        "available_metrics": available_metrics,
        "missing_metrics": missing_metrics,
        "data_source": source_info["data_source"],
        "source_type": source_info["source_type"],
        "source_warning": source_info["source_warning"],
        "fallback_reason": source_info["fallback_reason"],
        "enrich_from_trips": enrich_from_trips,
        "period_days": period_days,
        "date_range": {"from": current_start, "to": current_end},
        "fact_meta": source_info.get("fact_meta"),
        "groups_summary": {g: len(drvs) for g, drvs in sorted(classified.items())},
    }


def get_behavior_benchmarking_groups(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    """
    GET /driver-behavior/group-benchmarks
    Tabla comparativa de KPIs por grupo lifecycle.
    """
    with get_db() as conn:
        source_info = _resolve_primary_source(conn)
        fact_available = _detect_fact_columns(conn)

        all_drivers, classified, thresholds, date_tuple = _fetch_and_classify_drivers(
            conn, country, city, period_days, source_info,
        )
        current_start, current_end, _p1, _p2 = date_tuple

    groups = []
    for group_name in LIFECYCLE_GROUPS:
        drivers_in_group = classified.get(group_name, [])
        benchmarks = _build_group_benchmarks(drivers_in_group, group_name, period_days)
        groups.append(benchmarks)

    _, missing_metrics = _build_available_metrics_info(source_info, fact_available)

    return {
        "groups": groups,
        "period_days": period_days,
        "date_range": {"from": current_start, "to": current_end},
        "data_source": source_info["data_source"],
        "source_type": source_info["source_type"],
        "source_warning": source_info["source_warning"],
        "fallback_reason": source_info["fallback_reason"],
        "missing_metrics": missing_metrics,
    }


def get_behavior_benchmarking_top_vs_risk(
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
    enrich_from_trips: bool = False,
) -> dict[str, Any]:
    """
    GET /driver-behavior/top-vs-risk
    Comparación directa TOP_PERFORMER vs DECLINING vs AT_RISK.
    """
    group_data = get_behavior_benchmarking_groups(
        country=country, city=city, period_days=period_days, enrich_from_trips=enrich_from_trips,
    )
    groups = {g["group_name"]: g for g in group_data.get("groups", [])}

    defaults = {
        "group_name": "", "drivers_count": 0, "total_trips": 0,
        "avg_trips_per_driver": 0, "avg_active_days": 0, "trips_per_active_day": 0,
        "consistency_score": 0, "avg_ticket": None, "revenue_per_driver": None,
        "peak_hour_share": None, "weekend_share": None,
    }
    top = groups.get("TOP_PERFORMER", {**defaults, "group_name": "TOP_PERFORMER"})
    declining = groups.get("DECLINING", {**defaults, "group_name": "DECLINING"})
    at_risk = groups.get("AT_RISK", {**defaults, "group_name": "AT_RISK"})

    comparisons = _compare_groups(top, declining, at_risk)

    return {
        "comparisons": comparisons,
        "group_counts": {
            "top_performer": top.get("drivers_count", 0),
            "declining": declining.get("drivers_count", 0),
            "at_risk": at_risk.get("drivers_count", 0),
        },
        "period_days": period_days,
        "date_range": group_data.get("date_range", {}),
        "data_source": group_data.get("data_source"),
        "source_warning": group_data.get("source_warning"),
    }


def get_behavior_benchmarking_distributions(
    dimension: str,
    group_name: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    period_days: int = 28,
) -> dict[str, Any]:
    """
    GET /driver-behavior/distributions
    Distribución por dimensión (city, park, lob, day_of_week, hour) para un grupo.
    city y park usan fact table. lob, day_of_week, hour no disponibles sin trips.
    """
    valid_dimensions = ["city", "park", "lob", "day_of_week", "hour"]
    if dimension not in valid_dimensions:
        return {
            "available": False,
            "reason": f"Dimensión '{dimension}' no soportada. Válidas: {', '.join(valid_dimensions)}.",
            "distributions": [],
        }

    fact_dimensions = ["city", "park"]
    trips_dimensions = ["lob", "day_of_week", "hour"]

    if dimension in trips_dimensions:
        return {
            "available": False,
            "reason": (
                f"La dimensión '{dimension}' no está disponible desde {FACT_TABLE}. "
                "Requiere enriquecimiento desde public.trips_2026 (no habilitado por defecto por performance)."
            ),
            "distributions": [],
            "data_source": FACT_TABLE,
        }

    with get_db() as conn:
        source_info = _resolve_primary_source(conn)
        fact_available = _detect_fact_columns(conn)

        all_drivers, classified, thresholds, date_tuple = _fetch_and_classify_drivers(
            conn, country, city, period_days, source_info,
        )
        current_start, current_end, _p1, _p2 = date_tuple

        if not all_drivers:
            return {
                "available": True,
                "dimension": dimension,
                "distributions": [],
                "data_source": source_info["data_source"],
                "source_warning": source_info["source_warning"],
                "date_range": {"from": current_start, "to": current_end},
            }

        if group_name:
            targets = [group_name]
        else:
            targets = [g for g in LIFECYCLE_GROUPS if g in classified]

        cur = _cursor(conn)
        distributions = []
        for group in targets:
            drivers = classified.get(group, [])
            driver_keys = [d["driver_key"] for d in drivers]

            if not driver_keys:
                distributions.append({"group_name": group, "drivers_count": 0, "data": []})
                continue

            if source_info["use_trips_fallback"]:
                from app.db.connection import get_db as _get_db
                dist_query = f"""
                SELECT
                    COALESCE(NULLIF(TRIM(t.{'park_id' if dimension == 'park' else 'park_id'}), ''), 'UNKNOWN') AS label,
                    COUNT(*) AS trips,
                    COUNT(DISTINCT t.conductor_id) AS driver_count
                FROM public.trips_2026 t
                LEFT JOIN dim.dim_park p ON t.park_id = p.park_id
                WHERE t.condicion = 'Completado'
                  AND t.conductor_id IN ('{"', '".join(str(dk) for dk in driver_keys)}')
                  AND t.fecha_inicio_viaje >= '{current_start}'::timestamp
                  AND t.fecha_inicio_viaje < '{current_end}'::timestamp + INTERVAL '1 day'
                GROUP BY label
                ORDER BY trips DESC
                """
                if dimension == "city":
                    dist_query = dist_query.replace("COALESCE(NULLIF(TRIM(t.park_id), ''), 'UNKNOWN')", "COALESCE(p.city, 'UNKNOWN')")
            else:
                dist_query = _build_distribution_from_fact(
                    dimension, driver_keys, current_start, current_end,
                )

            cur.execute(dist_query)
            rows = [dict(r) for r in cur.fetchall()]
            distributions.append({"group_name": group, "drivers_count": len(drivers), "data": rows})

        cur.close()

    return {
        "available": True,
        "dimension": dimension,
        "distributions": distributions,
        "data_source": source_info["data_source"],
        "source_warning": source_info["source_warning"],
        "source_type": source_info["source_type"],
        "date_range": {"from": current_start, "to": current_end},
    }
