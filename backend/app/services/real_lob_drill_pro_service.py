"""
Real LOB Drill PRO: endpoints /ops/real-lob/drill y /ops/real-lob/drill/children.
Fuente: ops.mv_real_drill_dim_agg (breakdown lob|park|service_type) y cobertura vía ops.v_real_data_coverage
(resuelta en app.db.real_data_coverage_sql: vista canónica; fallback temporal documentado si falta la vista).
- Respuesta: countries[] con coverage, kpis (sobre lo visible), rows con periodo/estado/viajes/margen/km/b2b.
- Children: desglose por LOB (1 fila por lob_group), PARK (city, park_name), o SERVICE_TYPE (tipo_servicio).
"""
from app.db.real_data_coverage_sql import coverage_from_clause
from app.db.connection import get_db_drill
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging
import os
import json
import time

logger = logging.getLogger(__name__)
# #region agent log
def _debug_log_svc(location: str, message: str, data: dict, hypothesis_id: str):
    try:
        log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "debug-1c8c83.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId": "1c8c83", "timestamp": int(time.time() * 1000), "location": location, "message": message, "data": data, "hypothesisId": hypothesis_id}) + "\n")
    except Exception:
        pass
# #endregion

MV_DIM = "ops.mv_real_drill_dim_agg"
LOW_VOLUME_THRESHOLD = 20  # categorías con viajes < 20 se agrupan en LOW_VOLUME
LOW_SAMPLE_THRESHOLD = 30  # si viajes < 30 no mostrar pct_b2b como significativo (LOW SAMPLE)
# Drill consulta MV + varias vistas. Rol puede tener 15s: forzar 0 (sin límite) para esta request.
# Si el rol no permite override, el DBA debe ejecutar: ALTER ROLE yego_user SET statement_timeout TO '300s';
TIMEOUT_POSTGRES = "0"
# MV para desglose tipo_servicio por park (068)
MV_SERVICE_BY_PARK = "ops.mv_real_drill_service_by_park"


def _segment_filter(segment: Optional[str]) -> str:
    if not segment or segment.lower() == "all":
        return ""
    return " AND segment = %(segment)s "


def _apply_low_volume_service_type(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrupa filas con viajes < LOW_VOLUME_THRESHOLD en una sola fila 'LOW_VOLUME'."""
    if not rows:
        return rows
    high = [r for r in rows if (r.get("viajes") or 0) >= LOW_VOLUME_THRESHOLD]
    low = [r for r in rows if (r.get("viajes") or 0) < LOW_VOLUME_THRESHOLD]
    if not low:
        return rows
    total_v = sum(float(r.get("viajes") or 0) for r in low)
    total_m = sum(float(r.get("margen_total") or 0) for r in low)
    total_b2b = sum(float(r.get("viajes_b2b") or 0) for r in low)
    km_weighted = sum(float(r.get("km_prom") or 0) * float(r.get("viajes") or 0) for r in low)
    agg = {
        "dimension_key": "LOW_VOLUME",
        "dimension_id": None,
        "city": None,
        "viajes": int(total_v),
        "margen_total": round(total_m, 4) if total_m else None,
        "margen_trip": round(total_m / total_v, 4) if total_v else None,
        "km_prom": round(km_weighted / total_v, 4) if total_v else None,
        "viajes_b2b": int(total_b2b),
        "pct_b2b": round(total_b2b / total_v, 4) if total_v else None,
        "service_type": "LOW_VOLUME",
        "margin_total_pos": round(total_m, 4) if total_m else None,
        "margin_unit_pos": round(total_m / total_v, 4) if total_v else None,
        "trips": total_v,
        "b2b_trips": total_b2b,
    }
    out = high + [agg]
    out.sort(key=lambda x: x.get("viajes") or 0, reverse=True)
    return out


def _prev_period_start(ps: Any, period_type: str) -> Any:
    """Fecha de inicio del periodo anterior (semana -7d, mes -1 mes)."""
    if not ps:
        return None
    from datetime import date, timedelta
    if hasattr(ps, "year"):
        d = ps
    else:
        s = str(ps)[:10]
        d = date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    if period_type == "week":
        return d - timedelta(days=7)
    # month
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _delta_pct(current: float, previous: float) -> Optional[float]:
    if previous is None or previous == 0:
        return None
    if current is None:
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 2)


def _trend(current: float, previous: float) -> str:
    if previous is None or previous == 0:
        return "flat" if (current or 0) == 0 else "up"
    cur = float(current or 0)
    prev = float(previous)
    if abs(cur - prev) < 1e-9:
        return "flat"
    return "up" if cur > prev else "down"


def _add_row_comparative(
    row: Dict[str, Any],
    ad: Optional[Dict],
    prev_ad: Optional[Dict],
    is_partial: bool,
    period_type: str,
) -> None:
    """Añade campos WoW/MoM por fila: *_prev, *_delta_pct, *_trend, is_partial_comparison."""
    row["is_partial_comparison"] = is_partial
    row["comparative_type"] = "WoW" if period_type == "week" else "MoM"
    if not prev_ad:
        row["viajes_prev"] = None
        row["viajes_delta_pct"] = None
        row["viajes_trend"] = "flat"
        row["margen_total_prev"] = None
        row["margen_total_delta_pct"] = None
        row["margen_total_trend"] = "flat"
        row["margen_trip_prev"] = None
        row["margen_trip_delta_pct"] = None
        row["cancelaciones_prev"] = None
        row["cancelaciones_delta_pct"] = None
        row["cancelaciones_trend"] = "flat"
        row["km_prom_prev"] = None
        row["km_prom_delta_pct"] = None
        row["pct_b2b_prev"] = None
        row["pct_b2b_delta_pp"] = None
        row["pct_b2b_trend"] = "flat"
        return
    viajes_prev = _float(prev_ad.get("viajes"))
    viajes_cur = _float(ad.get("viajes")) if ad else None
    row["viajes_prev"] = int(viajes_prev) if viajes_prev is not None else None
    row["viajes_delta_pct"] = _delta_pct(viajes_cur or 0, viajes_prev)
    row["viajes_trend"] = _trend(viajes_cur or 0, viajes_prev or 0)
    margen_prev = _float(prev_ad.get("margen_total"))
    margen_cur = _float(ad.get("margen_total")) if ad else None
    row["margen_total_prev"] = round(margen_prev, 4) if margen_prev is not None else None
    row["margen_total_delta_pct"] = _delta_pct(margen_cur, margen_prev)
    row["margen_total_trend"] = _trend(margen_cur or 0, margen_prev or 0)
    mt_prev = _float(prev_ad.get("margen_trip"))
    mt_cur = _float(ad.get("margen_trip")) if ad else None
    row["margen_trip_prev"] = round(mt_prev, 4) if mt_prev is not None else None
    row["margen_trip_delta_pct"] = _delta_pct(mt_cur, mt_prev)
    row["margen_trip_trend"] = _trend(mt_cur or 0, mt_prev or 0)
    canc_prev = _float(prev_ad.get("cancelaciones"))
    canc_cur = _float(ad.get("cancelaciones")) if ad else None
    row["cancelaciones_prev"] = int(canc_prev) if canc_prev is not None else None
    row["cancelaciones_delta_pct"] = _delta_pct(canc_cur or 0, canc_prev)
    row["cancelaciones_trend"] = _trend(canc_cur or 0, canc_prev or 0)
    km_prev = _float(prev_ad.get("km_prom"))
    km_cur = _float(ad.get("km_prom")) if ad else None
    row["km_prom_prev"] = round(km_prev, 4) if km_prev is not None else None
    row["km_prom_delta_pct"] = _delta_pct(km_cur, km_prev)
    row["km_prom_trend"] = _trend(km_cur or 0, km_prev or 0)
    b2b_prev = _float(prev_ad.get("viajes_b2b")) or 0
    trips_prev = _float(prev_ad.get("viajes")) or 0
    pct_b2b_prev = (b2b_prev / trips_prev * 100) if trips_prev else None
    # row["pct_b2b"] es ratio 0-1; convertir a % para delta_pp y trend
    pct_b2b_cur = (float(row.get("pct_b2b")) * 100) if row.get("pct_b2b") is not None else None
    row["pct_b2b_prev"] = round(pct_b2b_prev, 2) if pct_b2b_prev is not None else None
    if pct_b2b_prev is not None and pct_b2b_cur is not None:
        row["pct_b2b_delta_pp"] = round(pct_b2b_cur - pct_b2b_prev, 2)
    else:
        row["pct_b2b_delta_pp"] = None
    row["pct_b2b_trend"] = _trend(pct_b2b_cur or 0, pct_b2b_prev or 0)


def _add_child_comparative(
    row: Dict[str, Any],
    prev_row: Optional[Dict[str, Any]],
    period_type: str,
) -> None:
    """Añade campos WoW/MoM por item disgregado: *_delta_pct, *_trend (misma semántica que fila principal)."""
    row["comparative_type"] = "WoW" if period_type == "week" else "MoM"
    if not prev_row:
        row["viajes_delta_pct"] = None
        row["viajes_trend"] = "flat"
        row["margen_total_delta_pct"] = None
        row["margen_total_trend"] = "flat"
        row["margen_trip_delta_pct"] = None
        row["margen_trip_trend"] = "flat"
        row["cancelaciones_delta_pct"] = None
        row["cancelaciones_trend"] = "flat"
        row["km_prom_delta_pct"] = None
        row["km_prom_trend"] = "flat"
        row["pct_b2b_delta_pp"] = None
        row["pct_b2b_trend"] = "flat"
        return
    viajes_cur = _float(row.get("viajes"))
    viajes_prev = _float(prev_row.get("viajes"))
    row["viajes_delta_pct"] = _delta_pct(viajes_cur or 0, viajes_prev)
    row["viajes_trend"] = _trend(viajes_cur or 0, viajes_prev or 0)
    margen_cur = _float(row.get("margen_total"))
    margen_prev = _float(prev_row.get("margen_total"))
    row["margen_total_delta_pct"] = _delta_pct(margen_cur, margen_prev)
    row["margen_total_trend"] = _trend(margen_cur or 0, margen_prev or 0)
    mt_cur = _float(row.get("margen_trip"))
    mt_prev = _float(prev_row.get("margen_trip"))
    row["margen_trip_delta_pct"] = _delta_pct(mt_cur, mt_prev)
    row["margen_trip_trend"] = _trend(mt_cur or 0, mt_prev or 0)
    canc_cur = _float(row.get("cancelaciones"))
    canc_prev = _float(prev_row.get("cancelaciones"))
    row["cancelaciones_delta_pct"] = _delta_pct(canc_cur or 0, canc_prev)
    row["cancelaciones_trend"] = _trend(canc_cur or 0, canc_prev or 0)
    km_cur = _float(row.get("km_prom"))
    km_prev = _float(prev_row.get("km_prom"))
    row["km_prom_delta_pct"] = _delta_pct(km_cur, km_prev)
    row["km_prom_trend"] = _trend(km_cur or 0, km_prev or 0)
    b2b_cur = _float(row.get("viajes_b2b")) or 0
    trips_cur = _float(row.get("viajes")) or 0
    b2b_prev = _float(prev_row.get("viajes_b2b")) or 0
    trips_prev = _float(prev_row.get("viajes")) or 0
    pct_b2b_cur = (b2b_cur / trips_cur * 100) if trips_cur else None
    pct_b2b_prev = (b2b_prev / trips_prev * 100) if trips_prev else None
    if pct_b2b_prev is not None and pct_b2b_cur is not None:
        row["pct_b2b_delta_pp"] = round(pct_b2b_cur - pct_b2b_prev, 2)
    else:
        row["pct_b2b_delta_pp"] = None
    row["pct_b2b_trend"] = _trend(pct_b2b_cur or 0, pct_b2b_prev or 0)


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_drill_parks(country: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lista de parks para el filtro del drill. Fuente: ops.real_drill_dim_fact (breakdown=park).
    Garantiza que el dropdown Park se pueble con el mismo universo que el drill, independiente del desglose.
    """
    try:
        with get_db_drill() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")
            if country and str(country).strip():
                cur.execute("""
                    SELECT DISTINCT country, city, dimension_id AS park_id, dimension_key AS park_name
                    FROM ops.real_drill_dim_fact
                    WHERE breakdown = 'park'
                      AND country = %(country)s
                      AND dimension_id IS NOT NULL AND TRIM(COALESCE(dimension_id,'')) <> ''
                    ORDER BY country, city, dimension_key
                """, {"country": str(country).strip().lower()})
            else:
                cur.execute("""
                    SELECT DISTINCT country, city, dimension_id AS park_id, dimension_key AS park_name
                    FROM ops.real_drill_dim_fact
                    WHERE breakdown = 'park'
                      AND dimension_id IS NOT NULL AND TRIM(COALESCE(dimension_id,'')) <> ''
                    ORDER BY country, city, dimension_key
                """)
            rows = cur.fetchall()
            out = []
            for r in rows:
                p = dict(r)
                if p.get("park_name") is None or (isinstance(p.get("park_name"), str) and not p["park_name"].strip()):
                    p["park_name"] = str(p.get("park_id") or "")
                # Etiqueta canónica: park_name — city — country (no solo nombre)
                name = (p.get("park_name") or "").strip() or "Sin park"
                city = (p.get("city") or "").strip() or "Sin ciudad"
                country = (p.get("country") or "").strip() or "Sin país"
                p["park_label"] = f"{name} — {city} — {country}"
                out.append(p)
            cur.close()
            return out
    except Exception as e:
        logger.exception("Real LOB drill parks: %s", e)
        raise


def get_drill(
    period: str = "month",
    desglose: str = "PARK",
    segmento: Optional[str] = None,
    country: Optional[str] = None,
    park_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GET /ops/real-lob/drill
    period: month | week
    desglose: LOB | PARK | SERVICE_TYPE
    segmento: all | b2c | b2b
    country: all | pe | co
    park_id: opcional; si se indica, KPIs y filas se limitan a ese park (breakdown=park + filtro).
    Devuelve: { countries: [ { country, coverage, kpis, rows } ], meta? }
    """
    period_type = "month" if period == "month" else "week"
    seg_param = None
    if segmento and segmento.lower() in ("b2c", "b2b"):
        seg_param = segmento.upper()

    # #region agent log
    _debug_log_svc("real_lob_drill_pro_service.py:get_drill", "get_drill entered", {"period": period, "desglose": desglose}, "H3_H4")
    # #endregion
    logger.info("Real LOB drill PRO: opening dedicated connection (statement_timeout=0)")
    try:
        with get_db_drill() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # Conexión drill ya tiene statement_timeout=0 por options; por si acaso:
            cur.execute("SET LOCAL statement_timeout = %s", (TIMEOUT_POSTGRES,))
            # Reducir spill a disco (evitar DiskFull): más RAM, menos pgsql_tmp
            cur.execute("SET LOCAL work_mem = '256MB'")

            # #region agent log
            _debug_log_svc("real_lob_drill_pro_service.py:before_first_select", "about to run first SELECT (coverage)", {}, "H5")
            # #endregion
            cov_sql, _cov_fallback = coverage_from_clause(cur)
            # Coverage por país (vista canónica o fallback) + freshness desde real_rollup_day_fact
            cur.execute(f"""
                SELECT country,
                    last_trip_date::text AS last_day_with_data,
                    last_month_with_data::text AS last_month_with_data,
                    last_week_with_data::text AS last_week_with_data
                FROM {cov_sql} AS cov
                ORDER BY country
            """)
            coverage_rows = cur.fetchall()
            coverage_by_country = {r["country"]: dict(r) for r in coverage_rows} if coverage_rows else {}
            # Freshness desde fact table (15K filas) en vez de v_real_freshness_trips
            # que escanea v_trips_real_canon (58M filas con DISTINCT ON → GB de temp files).
            cur.execute("""
                SELECT country,
                       MAX(trip_day)::text AS last_trip_date,
                       MAX(last_trip_ts) AS max_trip_ts
                FROM ops.real_rollup_day_fact
                WHERE country IN ('pe','co')
                GROUP BY country
                ORDER BY country
            """)
            freshness_rows = cur.fetchall()
            # Coverage modo incremental (v_real_lob_coverage): min/max cargado, ventana config
            lob_coverage = {}
            try:
                cur.execute("""
                    SELECT min_trip_date_loaded::text, max_trip_date_loaded::text, recent_days_config, computed_at
                    FROM ops.v_real_lob_coverage
                """)
                r = cur.fetchone()
                if r:
                    lob_coverage = {
                        "min_trip_date_loaded": r.get("min_trip_date_loaded"),
                        "max_trip_date_loaded": r.get("max_trip_date_loaded"),
                        "recent_days_config": r.get("recent_days_config"),
                        "computed_at": str(r.get("computed_at")) if r.get("computed_at") else None,
                    }
            except Exception:
                pass
            for r in freshness_rows:
                c = r["country"]
                if c in coverage_by_country:
                    coverage_by_country[c]["freshness_last_trip_date"] = r["last_trip_date"]
                    coverage_by_country[c]["freshness_max_trip_ts"] = str(r["max_trip_ts"]) if r.get("max_trip_ts") else None

            # Calendario: meses o semanas hasta el actual
            if period_type == "month":
                cur.execute(f"""
                    WITH bounds AS (
                        SELECT
                            COALESCE((SELECT MIN(min_month) FROM {cov_sql} AS c), date_trunc('month', CURRENT_DATE)::date) AS min_month,
                            date_trunc('month', CURRENT_DATE)::date AS current_month
                    )
                    SELECT (generate_series(b.min_month, b.current_month, '1 month'::interval))::date AS period_start
                    FROM bounds b
                    ORDER BY period_start DESC
                """)
            else:
                cur.execute(f"""
                    WITH bounds AS (
                        SELECT
                            COALESCE((SELECT MIN(min_week) FROM {cov_sql} AS c), date_trunc('week', CURRENT_DATE)::date) AS min_week,
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
                # Agregado por (country, period_start): si park_id indicado, usar breakdown=park y filtrar
                params = {"country": ccode, "period_grain": period_type}
                if seg_param:
                    params["segment"] = seg_param
                where_seg = _segment_filter(segmento)
                if park_id and str(park_id).strip():
                    params["park_id"] = str(park_id).strip()
                    where_park = " AND dimension_id = %(park_id)s "
                    breakdown_use = "park"
                else:
                    where_park = ""
                    breakdown_use = "lob"
                cur.execute(f"""
                    SELECT
                        period_start,
                        SUM(trips) AS viajes,
                        SUM(margin_total) AS margen_total,
                        SUM(b2b_trips) AS viajes_b2b,
                        MAX(last_trip_ts) AS last_trip_ts
                    FROM {MV_DIM}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND breakdown = %(breakdown_use)s {where_seg} {where_park}
                    GROUP BY period_start
                """, {**params, "breakdown_use": breakdown_use})
                agg_rows = {r["period_start"]: dict(r) for r in cur.fetchall()}

                # margen_trip, km_prom, cancelaciones (mig 103), segmentación conductores (mig 106)
                cur.execute(f"""
                    SELECT
                        period_start,
                        SUM(trips) AS viajes,
                        COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones,
                        SUM(margin_total) AS margen_total,
                        CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                        CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                        SUM(b2b_trips) AS viajes_b2b,
                        MAX(last_trip_ts) AS last_trip_ts,
                        SUM(COALESCE(active_drivers, 0))::bigint AS active_drivers,
                        SUM(COALESCE(cancel_only_drivers, 0))::bigint AS cancel_only_drivers,
                        SUM(COALESCE(activity_drivers, 0))::bigint AS activity_drivers,
                        CASE WHEN SUM(COALESCE(activity_drivers, 0)) > 0
                             THEN ROUND(100.0 * SUM(COALESCE(cancel_only_drivers, 0)) / SUM(COALESCE(activity_drivers, 0)), 4)
                             ELSE NULL END AS cancel_only_pct
                    FROM {MV_DIM}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND breakdown = %(breakdown_use)s {where_seg} {where_park}
                    GROUP BY period_start
                """, {**params, "breakdown_use": breakdown_use})
                agg_detail = {r["period_start"]: dict(r) for r in cur.fetchall()}
                # Normalizar margen a signo positivo (semántica negocio) para WoW coherente
                for ad in agg_detail.values():
                    if ad.get("margen_total") is not None:
                        try:
                            ad["margen_total"] = abs(float(ad["margen_total"]))
                        except (TypeError, ValueError):
                            pass
                    if ad.get("margen_trip") is not None:
                        try:
                            ad["margen_trip"] = abs(float(ad["margen_trip"]))
                        except (TypeError, ValueError):
                            pass

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

                    # Estado: Falta data / Abierto / Cerrado / Vacío.
                    # Regla global: solo "Falta data" cuando última fecha con data < ayer (derived_max_date <= today-2).
                    # expected_loaded_until = ayer; si last_day_with_data >= ayer -> no falta data.
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
                    cancelaciones = int(ad.get("cancelaciones") or 0) if ad else 0
                    active_drivers = int(ad.get("active_drivers") or 0) if ad else 0
                    cancel_only_drivers = int(ad.get("cancel_only_drivers") or 0) if ad else 0
                    activity_drivers = int(ad.get("activity_drivers") or 0) if ad else 0
                    cancel_only_pct = round(float(ad.get("cancel_only_pct")), 4) if ad and ad.get("cancel_only_pct") is not None else None
                    row = {
                        "period_start": ps.isoformat()[:10] if hasattr(ps, "isoformat") else str(ps)[:10],
                        "period_label": period_label,
                        "estado": estado,
                        "viajes": viajes,
                        "cancelaciones": cancelaciones,
                        "margen_total": round(float(margen_total), 4) if margen_total is not None else None,
                        "margen_trip": round(float(margen_trip), 4) if margen_trip is not None else None,
                        "km_prom": round(float(km_prom), 4) if km_prom is not None else None,
                        "viajes_b2b": viajes_b2b,
                        "pct_b2b": round(float(pct_b2b), 4) if pct_b2b is not None else None,
                        "active_drivers": active_drivers,
                        "cancel_only_drivers": cancel_only_drivers,
                        "activity_drivers": activity_drivers,
                        "cancel_only_pct": cancel_only_pct,
                        "expected_last_date": expected_loaded_until.isoformat()[:10] if expected_loaded_until and hasattr(expected_loaded_until, "isoformat") else (str(expected_loaded_until)[:10] if expected_loaded_until else None),
                        "children": [],
                    }
                    row["trips"] = row["viajes"]
                    row["margin_total_pos"] = row["margen_total"]
                    row["margin_unit_pos"] = row["margen_trip"]
                    row["b2b_trips"] = row["viajes_b2b"]
                    # WoW / MoM por fila: periodo anterior y deltas
                    prev_ps = _prev_period_start(ps, period_type)
                    prev_ad = agg_detail.get(prev_ps) if prev_ps else None
                    _add_row_comparative(row, ad, prev_ad, is_partial=(estado == "ABIERTO"), period_type=period_type)
                    rows.append(row)

                # KPIs del país = suma de lo visible (rows) (convertir Decimal/float a float para evitar TypeError)
                total_viajes = sum(float(r["viajes"]) for r in rows)
                total_cancelaciones = sum(int(r.get("cancelaciones") or 0) for r in rows)
                total_margen = sum(float(r["margen_total"] or 0) for r in rows)
                total_b2b = sum(float(r["viajes_b2b"]) for r in rows)
                total_km_sum = sum(float(r["km_prom"] or 0) * float(r["viajes"]) for r in rows)
                total_active_drivers = sum(int(r.get("active_drivers") or 0) for r in rows)
                total_cancel_only_drivers = sum(int(r.get("cancel_only_drivers") or 0) for r in rows)
                total_activity_drivers = sum(int(r.get("activity_drivers") or 0) for r in rows)
                # pct_b2b solo significativo si viajes >= LOW_SAMPLE_THRESHOLD; si no, LOW SAMPLE
                pct_b2b_val = round(total_b2b / total_viajes, 4) if total_viajes else None
                if total_viajes and total_viajes < LOW_SAMPLE_THRESHOLD:
                    pct_b2b_val = None  # no mostrar % B2B para muestras pequeñas
                cancel_only_pct_val = round(100.0 * total_cancel_only_drivers / total_activity_drivers, 4) if total_activity_drivers else None
                kpis = {
                    "viajes": int(total_viajes),
                    "cancelaciones": total_cancelaciones,
                    "margen_total": round(total_margen, 4) if total_margen else None,
                    "margen_trip": round(total_margen / total_viajes, 4) if total_viajes else None,
                    "km_prom": round(total_km_sum / total_viajes, 4) if total_viajes else None,
                    "viajes_b2b": int(total_b2b),
                    "pct_b2b": pct_b2b_val,
                    "pct_b2b_low_sample": bool(total_viajes and total_viajes < LOW_SAMPLE_THRESHOLD),
                    "ultimo_periodo": rows[0]["period_start"] if rows else None,
                    "active_drivers": total_active_drivers,
                    "cancel_only_drivers": total_cancel_only_drivers,
                    "activity_drivers": total_activity_drivers,
                    "cancel_only_pct": cancel_only_pct_val,
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

            # Chequeo automático: SUM(viajes) por breakdown debe coincidir con total (lob/park/service_type)
            breakdown_valid = True
            try:
                cur.execute("""
                    SELECT bool_and(breakdown_valid) AS all_valid
                    FROM ops.v_audit_breakdown_sum
                    WHERE country = ANY(%s) AND period_grain = %s
                """, (countries_to_fetch, period_type))
                r = cur.fetchone()
                if r and r.get("all_valid") is False:
                    breakdown_valid = False
            except Exception:
                breakdown_valid = False
            cur.close()
        # #region agent log
        _debug_log_svc("real_lob_drill_pro_service.py:success", "drill completed", {"countries_count": len(countries_out)}, "H4")
        # #endregion
        # Meta con semántica temporal para UI (última cerrada vs actual abierta)
        from app.services.period_semantics_service import (
            get_last_closed_week,
            get_current_open_week,
            get_last_closed_month,
            get_current_open_month,
            format_week_label,
            format_month_label,
        )
        from datetime import date
        ref = date.today()
        last_cw = get_last_closed_week(ref)
        curr_ow = get_current_open_week(ref)
        last_cm = get_last_closed_month(ref)
        curr_om = get_current_open_month(ref)
        meta = {
            "last_closed_week": last_cw.isoformat(),
            "last_closed_week_label": format_week_label(last_cw, closed=True),
            "current_open_week": curr_ow.isoformat(),
            "current_open_week_label": format_week_label(curr_ow, closed=False),
            "last_closed_month": last_cm.isoformat(),
            "last_closed_month_label": format_month_label(last_cm, closed=True),
            "current_open_month": curr_om.isoformat(),
            "current_open_month_label": format_month_label(curr_om, closed=False),
            "breakdown_valid": breakdown_valid,
        }
        return {"countries": countries_out, "lob_coverage": lob_coverage, "meta": meta}
    except Exception as e:
        # #region agent log
        _debug_log_svc("real_lob_drill_pro_service.py:except", "drill failed", {"error_type": type(e).__name__, "error_msg": str(e)}, "H5")
        # #endregion
        logger.exception("Real LOB drill PRO: %s", e)
        raise


def get_drill_children(
    country: str,
    period: str,
    period_start: str,
    desglose: str,
    segmento: Optional[str] = None,
    park_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    GET /ops/real-lob/drill/children
    Desglose por LOB (1 fila por lob_group), PARK (city, park_name), o SERVICE_TYPE (economico, confort, etc.).
    Si desglose=SERVICE_TYPE y park_id está indicado, el desglose se limita a ese park (consulta a fuente).
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
    # LOW_VOLUME no se muestra en UI (solo control interno); excluir cuando desglose = LOB
    where_low_volume = " AND (dimension_key IS NULL OR dimension_key <> 'LOW_VOLUME') " if desg_upper == "LOB" else ""

    # Cuando desglose=SERVICE_TYPE y hay park_id: leer desde MV (068) para respuesta rápida
    if desg_upper == "SERVICE_TYPE" and park_id and str(park_id).strip():
        try:
            with get_db_drill() as conn:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SET statement_timeout = %s", (TIMEOUT_POSTGRES,))
                segment_cond = "" if seg_param is None else " AND segment = %(segment)s "
                qparams = {
                    "country": country.strip().lower(),
                    "period_grain": period_grain,
                    "period_start": period_start,
                    "park_id": str(park_id).strip(),
                    "segment": seg_param or "B2C",
                }
                cur.execute(f"""
                    SELECT
                        tipo_servicio_norm AS dimension_key,
                        SUM(trips) AS viajes,
                        SUM(margin_total) AS margen_total,
                        CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                        CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                        SUM(b2b_trips) AS viajes_b2b
                    FROM {MV_SERVICE_BY_PARK}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND period_start = %(period_start)s::date
                      AND park_id = %(park_id)s {segment_cond}
                    GROUP BY tipo_servicio_norm
                    ORDER BY SUM(trips) DESC
                """, qparams)
                rows = cur.fetchall()
                out = []
                for r in rows:
                    viajes = r.get("viajes") or 0
                    _mt = r.get("margen_total")
                    _mtr = r.get("margen_trip")
                    if _mt is not None:
                        try:
                            _mt = abs(float(_mt))
                        except (TypeError, ValueError):
                            pass
                    if _mtr is not None:
                        try:
                            _mtr = abs(float(_mtr))
                        except (TypeError, ValueError):
                            pass
                    row = {
                        "dimension_key": r.get("dimension_key"),
                        "dimension_id": None,
                        "city": None,
                        "viajes": viajes,
                        "margen_total": _mt,
                        "margen_trip": _mtr,
                        "km_prom": round(float(r["km_prom"]), 4) if r.get("km_prom") is not None else None,
                        "viajes_b2b": r.get("viajes_b2b"),
                        "pct_b2b": (float(r["viajes_b2b"]) / float(viajes)) if viajes else None,
                    }
                    row["service_type"] = row["dimension_key"]
                    row["margin_total_pos"] = row["margen_total"]
                    row["margin_unit_pos"] = row["margen_trip"]
                    row["trips"] = row["viajes"]
                    row["b2b_trips"] = row["viajes_b2b"]
                    # Fallback: mv_real_drill_service_by_park no tiene cancelled_trips ni segmentación conductores
                    row["cancelaciones"] = 0
                    row["active_drivers"] = None
                    row["cancel_only_drivers"] = None
                    row["activity_drivers"] = None
                    row["cancel_only_pct"] = None
                    out.append(row)
                # Comparativos WoW/MoM por item disgregado: periodo anterior
                period_type = "month" if period_grain == "month" else "week"
                from datetime import date
                ps_date = None
                if period_start and len(str(period_start)) >= 10:
                    s = str(period_start)[:10]
                    ps_date = date(int(s[:4]), int(s[5:7]), int(s[8:10]))
                prev_ps = _prev_period_start(ps_date, period_type) if ps_date else None
                if prev_ps:
                    qparams_prev = {**qparams, "period_start": prev_ps.isoformat()[:10]}
                    cur.execute(f"""
                        SELECT
                            tipo_servicio_norm AS dimension_key,
                            SUM(trips) AS viajes,
                            SUM(margin_total) AS margen_total,
                            CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                            CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                            SUM(b2b_trips) AS viajes_b2b
                        FROM {MV_SERVICE_BY_PARK}
                        WHERE country = %(country)s AND period_grain = %(period_grain)s AND period_start = %(period_start)s::date
                          AND park_id = %(park_id)s {segment_cond}
                        GROUP BY tipo_servicio_norm
                    """, qparams_prev)
                    prev_rows = cur.fetchall()
                    for pr in prev_rows:
                        if pr.get("margen_total") is not None:
                            try:
                                pr["margen_total"] = abs(float(pr["margen_total"]))
                            except (TypeError, ValueError):
                                pass
                        if pr.get("margen_trip") is not None:
                            try:
                                pr["margen_trip"] = abs(float(pr["margen_trip"]))
                            except (TypeError, ValueError):
                                pass
                    prev_by_key = {str(r.get("dimension_key")): r for r in prev_rows}
                    for row in out:
                        _add_child_comparative(row, prev_by_key.get(str(row.get("dimension_key"))), period_type)
                cur.close()
            return _apply_low_volume_service_type(out)
        except Exception as e:
            logger.exception("Real LOB drill PRO children (SERVICE_TYPE by park from MV): %s", e)
            raise

    try:
        from datetime import date as _date
        period_type = "month" if period_grain == "month" else "week"
        ps_date = None
        if period_start and len(str(period_start)) >= 10:
            s = str(period_start)[:10]
            ps_date = _date(int(s[:4]), int(s[5:7]), int(s[8:10]))
        prev_ps = _prev_period_start(ps_date, period_type) if ps_date else None

        with get_db_drill() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (TIMEOUT_POSTGRES,))
            # Cancelaciones (mig 103), segmentación conductores (mig 106)
            cur.execute(f"""
                SELECT
                    dimension_key,
                    dimension_id,
                    city,
                    SUM(trips) AS viajes,
                    COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones,
                    SUM(margin_total) AS margen_total,
                    CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                    CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                    SUM(b2b_trips) AS viajes_b2b,
                    (SUM(b2b_trips)::numeric / NULLIF(SUM(trips), 0)) AS pct_b2b,
                    SUM(COALESCE(active_drivers, 0))::bigint AS active_drivers,
                    SUM(COALESCE(cancel_only_drivers, 0))::bigint AS cancel_only_drivers,
                    SUM(COALESCE(activity_drivers, 0))::bigint AS activity_drivers,
                    CASE WHEN SUM(COALESCE(activity_drivers, 0)) > 0
                         THEN ROUND(100.0 * SUM(COALESCE(cancel_only_drivers, 0)) / SUM(COALESCE(activity_drivers, 0)), 4)
                         ELSE NULL END AS cancel_only_pct
                FROM {MV_DIM}
                WHERE country = %(country)s AND period_grain = %(period_grain)s AND period_start = %(period_start)s::date
                  AND breakdown = %(breakdown)s {where_seg}{where_low_volume}
                GROUP BY dimension_key, dimension_id, city
                ORDER BY SUM(trips) DESC
            """, {**params, "breakdown": breakdown_map[desg_upper]})
            rows = cur.fetchall()
            out = []
            for r in rows:
                row = dict(r)
                # Margen en positivo (semántica negocio)
                if row.get("margen_total") is not None:
                    try:
                        row["margen_total"] = abs(float(row["margen_total"]))
                    except (TypeError, ValueError):
                        pass
                if row.get("margen_trip") is not None:
                    try:
                        row["margen_trip"] = abs(float(row["margen_trip"]))
                    except (TypeError, ValueError):
                        pass
                if desg_upper == "PARK":
                    if row.get("city") is None or (isinstance(row.get("city"), str) and str(row.get("city")).lower() == "sin_city"):
                        row["city"] = "SIN_CITY"
                    if row.get("dimension_key") is None or str(row.get("dimension_key", "")).strip() == "":
                        row["park_name"] = "SIN_PARK"
                    else:
                        row["park_name"] = row["dimension_key"]
                    row["park_name_resolved"] = row.get("park_name")
                    # country para etiqueta canónica (params tiene country del request)
                    row["country"] = params.get("country") or ""
                    name = (row.get("park_name") or "").strip() or "Sin park"
                    city = (row.get("city") or "").strip() or "Sin ciudad"
                    country = (row.get("country") or "").strip() or "Sin país"
                    row["park_label"] = f"{name} — {city} — {country}"
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
            # Comparativos WoW/MoM por item disgregado
            if prev_ps:
                prev_start_str = prev_ps.isoformat()[:10]
                cur.execute(f"""
                    SELECT
                        dimension_key,
                        dimension_id,
                        city,
                        SUM(trips) AS viajes,
                        COALESCE(SUM(cancelled_trips), 0)::bigint AS cancelaciones,
                        SUM(margin_total) AS margen_total,
                        CASE WHEN SUM(trips) > 0 THEN SUM(margin_total) / SUM(trips) ELSE NULL END AS margen_trip,
                        CASE WHEN SUM(trips) > 0 THEN SUM(km_avg * trips) / NULLIF(SUM(trips), 0) ELSE NULL END AS km_prom,
                        SUM(b2b_trips) AS viajes_b2b,
                        (SUM(b2b_trips)::numeric / NULLIF(SUM(trips), 0)) AS pct_b2b
                    FROM {MV_DIM}
                    WHERE country = %(country)s AND period_grain = %(period_grain)s AND period_start = %(period_start)s::date
                      AND breakdown = %(breakdown)s {where_seg}{where_low_volume}
                    GROUP BY dimension_key, dimension_id, city
                """, {**params, "breakdown": breakdown_map[desg_upper], "period_start": prev_start_str})
                prev_rows = cur.fetchall()
                for pr in prev_rows:
                    if pr.get("margen_total") is not None:
                        try:
                            pr["margen_total"] = abs(float(pr["margen_total"]))
                        except (TypeError, ValueError):
                            pass
                    if pr.get("margen_trip") is not None:
                        try:
                            pr["margen_trip"] = abs(float(pr["margen_trip"]))
                        except (TypeError, ValueError):
                            pass
                prev_by_key = {str(r.get("dimension_key")): r for r in prev_rows}
                for row in out:
                    _add_child_comparative(row, prev_by_key.get(str(row.get("dimension_key"))), period_type)
            cur.close()
        if desg_upper == "SERVICE_TYPE":
            out = _apply_low_volume_service_type(out)
        return out
    except Exception as e:
        logger.exception("Real LOB drill PRO children: %s", e)
        raise
