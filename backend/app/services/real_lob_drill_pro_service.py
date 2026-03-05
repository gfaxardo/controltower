"""
Real LOB Drill PRO: endpoints /ops/real-lob/drill y /ops/real-lob/drill/children.
Fuente: ops.mv_real_drill_dim_agg (breakdown lob|park|service_type) y ops.v_real_data_coverage.
- Respuesta: countries[] con coverage, kpis (sobre lo visible), rows con periodo/estado/viajes/margen/km/b2b.
- Children: desglose por LOB (1 fila por lob_group), PARK (city, park_name), o SERVICE_TYPE (tipo_servicio).
"""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

MV_DIM = "ops.mv_real_drill_dim_agg"
VIEW_COVERAGE = "ops.v_real_data_coverage"
TIMEOUT_MS = 20000


def _segment_filter(segment: Optional[str]) -> str:
    if not segment or segment.lower() == "all":
        return ""
    return " AND segment = %(segment)s "


def get_drill(
    period: str = "month",
    desglose: str = "PARK",
    segmento: Optional[str] = None,
    country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GET /ops/real-lob/drill
    period: month | week
    desglose: LOB | PARK (solo define tipo de subfila al expandir)
    segmento: all | b2c | b2b
    country: all | pe | co
    Devuelve: { countries: [ { country, coverage, kpis, rows } ], meta? }
    """
    period_type = "month" if period == "month" else "week"
    seg_param = None
    if segmento and segmento.lower() in ("b2c", "b2b"):
        seg_param = segmento.upper()

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))

            # Coverage por país (v_real_data_coverage) + freshness desde canon (v_real_freshness_trips)
            cur.execute(f"""
                SELECT country,
                    last_trip_date::text AS last_day_with_data,
                    last_month_with_data::text AS last_month_with_data,
                    last_week_with_data::text AS last_week_with_data
                FROM {VIEW_COVERAGE}
                WHERE country IN ('pe','co')
                ORDER BY country
            """)
            coverage_rows = cur.fetchall()
            coverage_by_country = {r["country"]: dict(r) for r in coverage_rows} if coverage_rows else {}
            cur.execute("""
                SELECT country, last_trip_date::text, max_trip_ts
                FROM ops.v_real_freshness_trips
                WHERE country IN ('pe','co')
                ORDER BY country
            """)
            freshness_rows = cur.fetchall()
            for r in freshness_rows:
                c = r["country"]
                if c in coverage_by_country:
                    coverage_by_country[c]["freshness_last_trip_date"] = r["last_trip_date"]
                    coverage_by_country[c]["freshness_max_trip_ts"] = str(r["max_trip_ts"]) if r.get("max_trip_ts") else None

            # Calendario: meses o semanas hasta el actual
            if period_type == "month":
                cur.execute("""
                    WITH bounds AS (
                        SELECT
                            COALESCE((SELECT MIN(min_month) FROM ops.v_real_data_coverage), date_trunc('month', CURRENT_DATE)::date) AS min_month,
                            date_trunc('month', CURRENT_DATE)::date AS current_month
                    )
                    SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
                    FROM bounds b
                    ORDER BY period_start DESC
                """)
            else:
                cur.execute("""
                    WITH bounds AS (
                        SELECT
                            COALESCE((SELECT MIN(min_week) FROM ops.v_real_data_coverage), date_trunc('week', CURRENT_DATE)::date) AS min_week,
                            date_trunc('week', CURRENT_DATE)::date AS current_week
                    )
                    SELECT (generate_series(b.min_week, b.current_week, '1 week'::interval))::date AS period_start
                    FROM bounds b
                    ORDER BY period_start DESC
                """)
            calendar = [r["period_start"] for r in cur.fetchall()]

            # Países a devolver (si country=all, pe y co; si no, solo el indicado)
            countries_to_fetch = ["pe", "co"] if (not country or country.lower() == "all") else [country.strip().lower()]

            countries_out: List[Dict[str, Any]] = []
            for ccode in countries_to_fetch:
                if ccode not in ("pe", "co"):
                    continue
                cov = coverage_by_country.get(ccode) or {}
                # Agregado por (country, period_start) desde MV dimensional (breakdown=lob)
                params = {"country": ccode, "period_grain": period_type}
                if seg_param:
                    params["segment"] = seg_param
                where_seg = _segment_filter(segmento)
                cur.execute(f"""
                    SELECT
                        period_start,
                        SUM(trips) AS viajes,
                        SUM(margin_total) AS margen_total,
                        SUM(b2b_trips) AS viajes_b2b,
                        MAX(last_trip_ts) AS last_trip_ts
                    FROM {MV_DIM}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND breakdown = 'lob' {where_seg}
                    GROUP BY period_start
                """, params)
                agg_rows = {r["period_start"]: dict(r) for r in cur.fetchall()}

                # margen_trip y km_prom a nivel periodo: desde MV dimensional
                cur.execute(f"""
                    SELECT
                        period_start,
                        SUM(trips) AS viajes,
                        SUM(margin_total) AS margen_total,
                        CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                        CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                        SUM(b2b_trips) AS viajes_b2b,
                        MAX(last_trip_ts) AS last_trip_ts
                    FROM {MV_DIM}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND breakdown = 'lob' {where_seg}
                    GROUP BY period_start
                """, params)
                agg_detail = {r["period_start"]: dict(r) for r in cur.fetchall()}

                expected_loaded = "CURRENT_DATE - 1"
                if period_type == "month":
                    period_end_expr = "(period_start + interval '1 month' - interval '1 day')::date"
                else:
                    period_end_expr = "period_start + 6"

                rows: List[Dict[str, Any]] = []
                for ps in calendar:
                    ad = agg_detail.get(ps)
                    viajes = (ad.get("viajes") or 0) if ad else 0
                    margen_total = (ad.get("margen_total")) if ad else None
                    margen_trip = (ad.get("margen_trip")) if ad else None
                    km_prom = (ad.get("km_prom")) if ad else None
                    viajes_b2b = (ad.get("viajes_b2b") or 0) if ad else 0
                    last_ts = ad.get("last_trip_ts") if ad else None
                    pct_b2b = (viajes_b2b / viajes) if viajes else None

                    # Estado: Falta data / Abierto / Cerrado / Vacío (period_end vs expected_loaded_until)
                    from datetime import date, timedelta
                    today = date.today()
                    expected_loaded_until = today - timedelta(days=1)
                    if ps:
                        if period_type == "month":
                            y, m = (ps.year, ps.month) if hasattr(ps, "year") else (int(str(ps)[:4]), int(str(ps)[5:7]))
                            if m == 12:
                                period_end_expected = date(y, 12, 31)
                            else:
                                period_end_expected = date(y, m + 1, 1) - timedelta(days=1)
                        else:
                            pd = ps if hasattr(ps, "day") else date(int(str(ps)[:4]), int(str(ps)[5:7]), int(str(ps)[8:10]))
                            period_end_expected = pd + timedelta(days=6)
                    else:
                        period_end_expected = expected_loaded_until

                    last_day_with_data = last_ts.date() if last_ts and hasattr(last_ts, "date") else (last_ts if last_ts else None)
                    if period_end_expected and expected_loaded_until is not None:
                        if period_end_expected <= expected_loaded_until:
                            if last_day_with_data is not None and last_day_with_data >= period_end_expected:
                                estado = "CERRADO"
                            else:
                                estado = "FALTA_DATA"
                        else:
                            if last_day_with_data is not None and last_day_with_data >= expected_loaded_until:
                                estado = "ABIERTO"
                            else:
                                estado = "FALTA_DATA"
                    else:
                        estado = "VACIO" if viajes == 0 else "CERRADO"

                    period_label = str(ps)[:7] if period_type == "month" and ps else str(ps)[:10] if ps else ""
                    row = {
                        "period_start": ps.isoformat()[:10] if hasattr(ps, "isoformat") else str(ps)[:10],
                        "period_label": period_label,
                        "estado": estado,
                        "viajes": viajes,
                        "margen_total": round(float(margen_total), 4) if margen_total is not None else None,
                        "margen_trip": round(float(margen_trip), 4) if margen_trip is not None else None,
                        "km_prom": round(float(km_prom), 4) if km_prom is not None else None,
                        "viajes_b2b": viajes_b2b,
                        "pct_b2b": round(float(pct_b2b), 4) if pct_b2b is not None else None,
                        "expected_last_date": expected_loaded_until.isoformat()[:10] if expected_loaded_until and hasattr(expected_loaded_until, "isoformat") else (str(expected_loaded_until)[:10] if expected_loaded_until else None),
                        "children": [],
                    }
                    row["trips"] = row["viajes"]
                    row["margin_total_pos"] = row["margen_total"]
                    row["margin_unit_pos"] = row["margen_trip"]
                    row["b2b_trips"] = row["viajes_b2b"]
                    rows.append(row)

                # KPIs del país = suma de lo visible (rows) (convertir Decimal/float a float para evitar TypeError)
                total_viajes = sum(float(r["viajes"]) for r in rows)
                total_margen = sum(float(r["margen_total"] or 0) for r in rows)
                total_b2b = sum(float(r["viajes_b2b"]) for r in rows)
                total_km_sum = sum(float(r["km_prom"] or 0) * float(r["viajes"]) for r in rows)
                kpis = {
                    "viajes": int(total_viajes),
                    "margen_total": round(total_margen, 4) if total_margen else None,
                    "margen_trip": round(total_margen / total_viajes, 4) if total_viajes else None,
                    "km_prom": round(total_km_sum / total_viajes, 4) if total_viajes else None,
                    "viajes_b2b": int(total_b2b),
                    "pct_b2b": round(total_b2b / total_viajes, 4) if total_viajes else None,
                    "ultimo_periodo": rows[0]["period_start"] if rows else None,
                }
                # Alias para frontend que espera total_trips, margin_total_pos, etc.
                kpis["total_trips"] = kpis["viajes"]
                kpis["margin_total_pos"] = kpis["margen_total"]
                kpis["margin_unit_pos"] = kpis["margen_trip"]
                kpis["b2b_trips"] = kpis["viajes_b2b"]
                kpis["b2b_pct"] = kpis["pct_b2b"]
                kpis["last_period"] = kpis["ultimo_periodo"]

                countries_out.append({
                    "country": ccode,
                    "coverage": {
                        "last_day_with_data": cov.get("last_day_with_data"),
                        "last_month_with_data": cov.get("last_month_with_data"),
                        "last_week_with_data": cov.get("last_week_with_data"),
                    },
                    "kpis": kpis,
                    "rows": rows,
                })

            cur.close()
        return {"countries": countries_out}
    except Exception as e:
        logger.exception("Real LOB drill PRO: %s", e)
        raise


def get_drill_children(
    country: str,
    period: str,
    period_start: str,
    desglose: str,
    segmento: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    GET /ops/real-lob/drill/children
    Desglose por LOB (1 fila por lob_group), PARK (city, park_name), o SERVICE_TYPE (economico, confort, etc.).
    Orden: viajes DESC.
    """
    period_grain = "month" if period == "month" else "week"
    seg_param = None
    if segmento and segmento.lower() in ("b2c", "b2b"):
        seg_param = segmento.upper()
    where_seg = _segment_filter(segmento)
    params: Dict[str, Any] = {"country": country.strip().lower(), "period_grain": period_grain, "period_start": period_start}
    if seg_param:
        params["segment"] = seg_param

    desg_upper = desglose.upper()
    if desg_upper not in ("LOB", "PARK", "SERVICE_TYPE"):
        desg_upper = "LOB"

    breakdown_map = {"LOB": "lob", "PARK": "park", "SERVICE_TYPE": "service_type"}

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
            cur.execute(f"""
                SELECT
                    dimension_key,
                    dimension_id,
                    city,
                    SUM(trips) AS viajes,
                    SUM(margin_total) AS margen_total,
                    CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                    CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                    SUM(b2b_trips) AS viajes_b2b,
                    (SUM(b2b_trips)::numeric / NULLIF(SUM(trips), 0)) AS pct_b2b
                FROM {MV_DIM}
                WHERE country = %(country)s AND period_grain = %(period_grain)s AND period_start = %(period_start)s::date
                  AND breakdown = %(breakdown)s {where_seg}
                GROUP BY dimension_key, dimension_id, city
                ORDER BY SUM(trips) DESC
            """, {**params, "breakdown": breakdown_map[desg_upper]})
            rows = cur.fetchall()
            out = []
            for r in rows:
                row = dict(r)
                if desg_upper == "PARK":
                    if row.get("city") is None or (isinstance(row.get("city"), str) and str(row.get("city")).lower() == "sin_city"):
                        row["city"] = "SIN_CITY"
                    if row.get("dimension_key") is None or str(row.get("dimension_key", "")).strip() == "":
                        row["park_name"] = "SIN_PARK"
                    else:
                        row["park_name"] = row["dimension_key"]
                    row["park_name_resolved"] = row.get("park_name")
                elif desg_upper == "LOB":
                    row["lob_group"] = row.get("dimension_key")
                elif desg_upper == "SERVICE_TYPE":
                    row["service_type"] = row.get("dimension_key")
                row["margin_total_pos"] = row.get("margen_total")
                row["margin_unit_pos"] = row.get("margen_trip")
                row["km_prom"] = round(float(row["km_prom"]), 4) if row.get("km_prom") is not None else None
                row["trips"] = row.get("viajes")
                row["b2b_trips"] = row.get("viajes_b2b")
                out.append(row)
            cur.close()
        return out
    except Exception as e:
        logger.exception("Real LOB drill PRO children: %s", e)
        raise
