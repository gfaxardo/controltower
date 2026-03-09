"""
Vista diaria Real LOB: KPIs por día y comparativos D-1, mismo día semana pasada, promedio 4 mismos días.
Fuente: ops.real_rollup_day_fact.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.db.connection import get_db
from app.services.period_semantics_service import get_last_closed_day
from psycopg2.extras import RealDictCursor

TABLE = "ops.real_rollup_day_fact"

BaselineKind = Literal["D-1", "same_weekday_previous_week", "same_weekday_avg_4w"]


def _float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _agg_day(cursor, day: date, country: str | None) -> dict[str, Any]:
    params: list[Any] = [day.isoformat()]
    where = "trip_day = %s::date"
    if country and str(country).strip():
        where += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params.append(str(country).strip())
    cursor.execute(
        f"""
        SELECT
            SUM(trips) AS trips,
            SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) AS margin_total,
            SUM(b2b_trips) AS b2b_trips,
            SUM(distance_total_km) AS distance_total_km,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) / SUM(trips) ELSE NULL END AS margin_trip,
            CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(distance_total_km, 0))::numeric / SUM(trips) ELSE NULL END AS km_prom
        FROM {TABLE}
        WHERE {where}
        """,
        params,
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def get_daily_summary(
    day: date | str | None = None,
    country: str | None = None,
) -> dict[str, Any]:
    """
    KPIs agregados para un día. Si day es None, usa último día cerrado (ayer).
    """
    ref = date.today()
    target = get_last_closed_day(ref) if day is None else (day if isinstance(day, date) else date.fromisoformat(str(day)[:10]))
    out: dict[str, Any] = {
        "trip_day": target.isoformat(),
        "is_default": day is None,
        "by_country": [],
    }
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")
            countries = ["pe", "co"] if not country or not str(country).strip() else [str(country).strip().lower()]
            for c in countries:
                if c not in ("pe", "co"):
                    continue
                agg = _agg_day(cur, target, c)
                trips = _float(agg.get("trips"))
                margin = _float(agg.get("margin_total"))
                margin_trip = _float(agg.get("margin_trip"))
                km_prom = _float(agg.get("km_prom"))
                b2b = _float(agg.get("b2b_trips"))
                b2b_pct = (b2b / (trips or 1) * 100) if b2b is not None and trips else None
                out["by_country"].append({
                    "country": c,
                    "trips": int(trips) if trips is not None else None,
                    "margin_total": round(margin, 4) if margin is not None else None,
                    "margin_trip": round(margin_trip, 4) if margin_trip is not None else None,
                    "km_prom": round(km_prom, 4) if km_prom is not None else None,
                    "b2b_trips": int(b2b) if b2b is not None else None,
                    "b2b_pct": round(b2b_pct, 2) if b2b_pct is not None else None,
                })
            cur.close()
    except Exception as e:
        out["error"] = str(e)
    return out


def _comparative_row(
    value_current: float | None,
    value_baseline: float | None,
    metric_name: str,
) -> dict[str, Any]:
    cur = value_current if value_current is not None else 0.0
    base = value_baseline if value_baseline is not None else 0.0
    delta_abs = (cur - base) if (value_current is not None or value_baseline is not None) else None
    delta_pct = (delta_abs / base * 100) if base != 0 and delta_abs is not None else None
    if base == 0:
        trend = "flat" if cur == 0 else "up"
    else:
        trend = "up" if cur > base else ("down" if cur < base else "flat")
    return {
        "metric": metric_name,
        "value_current": value_current,
        "value_baseline": value_baseline,
        "delta_abs": round(delta_abs, 4) if delta_abs is not None else None,
        "delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
        "trend_direction": trend,
    }


def get_daily_comparative(
    day: date | str | None = None,
    country: str | None = None,
    baseline: BaselineKind = "D-1",
) -> dict[str, Any]:
    """
    Comparativo diario: día consultado vs baseline elegido.
    baseline: D-1 (día anterior), same_weekday_previous_week, same_weekday_avg_4w.
    """
    ref = date.today()
    target = get_last_closed_day(ref) if day is None else (day if isinstance(day, date) else date.fromisoformat(str(day)[:10]))

    baseline_dates: list[date] = []
    baseline_label = ""
    if baseline == "D-1":
        baseline_dates = [target - timedelta(days=1)]
        baseline_label = "D-1 (día anterior)"
    elif baseline == "same_weekday_previous_week":
        baseline_dates = [target - timedelta(days=7)]
        baseline_label = "Mismo día de la semana pasada (WoW same weekday)"
    elif baseline == "same_weekday_avg_4w":
        baseline_dates = [target - timedelta(days=7 * i) for i in range(1, 5)]
        baseline_label = "Promedio últimos 4 mismos días de la semana"

    out: dict[str, Any] = {
        "trip_day": target.isoformat(),
        "baseline": baseline,
        "baseline_label": baseline_label,
        "comparative_context": baseline_label,
        "by_country": [],
    }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")

            curr_agg_by_country: dict[str, dict] = {}
            base_agg_by_country: dict[str, dict] = {}
            for c in ["pe", "co"]:
                curr_agg_by_country[c] = _agg_day(cur, target, c)
            for c in ["pe", "co"]:
                if baseline == "same_weekday_avg_4w":
                    trips_sum = 0
                    margin_sum = 0
                    b2b_sum = 0
                    dist_sum = 0
                    for bd in baseline_dates:
                        row = _agg_day(cur, bd, c)
                        trips_sum += _float(row.get("trips")) or 0
                        margin_sum += _float(row.get("margin_total")) or 0
                        b2b_sum += _float(row.get("b2b_trips")) or 0
                        dist_sum += _float(row.get("distance_total_km")) or 0
                    n = len(baseline_dates)
                    base_agg_by_country[c] = {
                        "trips": trips_sum / n if n else None,
                        "margin_total": margin_sum / n if n else None,
                        "b2b_trips": b2b_sum / n if n else None,
                        "distance_total_km": dist_sum / n if n else None,
                        "margin_trip": (margin_sum / trips_sum) if trips_sum else None,
                        "km_prom": (dist_sum / trips_sum) if trips_sum else None,
                    }
                else:
                    bd = baseline_dates[0]
                    base_agg_by_country[c] = _agg_day(cur, bd, c)

            for c in ["pe", "co"]:
                curr = curr_agg_by_country.get(c) or {}
                base = base_agg_by_country.get(c) or {}
                trips_c = _float(curr.get("trips"))
                trips_b = _float(base.get("trips"))
                margin_c = _float(curr.get("margin_total"))
                margin_b = _float(base.get("margin_total"))
                margin_trip_c = _float(curr.get("margin_trip"))
                margin_trip_b = _float(base.get("margin_trip"))
                km_c = _float(curr.get("km_prom"))
                km_b = _float(base.get("km_prom"))
                b2b_c = _float(curr.get("b2b_trips"))
                b2b_b = _float(base.get("b2b_trips"))
                b2b_pct_c = (b2b_c / (trips_c or 1) * 100) if b2b_c is not None and trips_c else None
                b2b_pct_b = (b2b_b / (trips_b or 1) * 100) if b2b_b is not None and trips_b else None
                metrics = [
                    _comparative_row(trips_c, trips_b, "viajes"),
                    _comparative_row(margin_c, margin_b, "margen_total"),
                    _comparative_row(margin_trip_c, margin_trip_b, "margen_trip"),
                    _comparative_row(km_c, km_b, "km_prom"),
                    _comparative_row(b2b_pct_c, b2b_pct_b, "b2b_pct"),
                ]
                out["by_country"].append({"country": c, "metrics": metrics})
            cur.close()
    except Exception as e:
        out["error"] = str(e)
    return out


def _daily_table_query(
    cur: Any,
    target: date,
    country: str | None,
    group_by: str,
) -> list[dict[str, Any]]:
    """Ejecuta query de tabla diaria por dimension_key; devuelve lista de filas."""
    where = "trip_day = %s::date"
    params: list[Any] = [target.isoformat()]
    if country and str(country).strip():
        where += " AND LOWER(TRIM(country)) = LOWER(TRIM(%s))"
        params.append(str(country).strip())
    if group_by == "park":
        cur.execute(
            f"""
            SELECT country, city, park_id, COALESCE(park_name_resolved, park_id::text) AS dimension_key,
                   SUM(trips) AS trips, SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) AS margin_total,
                   SUM(b2b_trips) AS b2b_trips,
                   CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) / SUM(trips) ELSE NULL END AS margin_trip,
                   CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(distance_total_km, 0))::numeric / SUM(trips) ELSE NULL END AS km_prom
            FROM {TABLE}
            WHERE {where}
            GROUP BY country, city, park_id, park_name_resolved
            ORDER BY SUM(trips) DESC
            """,
            params,
        )
    else:
        cur.execute(
            f"""
            SELECT country, lob_group AS dimension_key,
                   SUM(trips) AS trips, SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) AS margin_total,
                   SUM(b2b_trips) AS b2b_trips,
                   CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(margin_total_pos, margin_total_raw, 0)) / SUM(trips) ELSE NULL END AS margin_trip,
                   CASE WHEN SUM(trips) > 0 THEN SUM(COALESCE(distance_total_km, 0))::numeric / SUM(trips) ELSE NULL END AS km_prom
            FROM {TABLE}
            WHERE {where}
            GROUP BY country, lob_group
            ORDER BY SUM(trips) DESC
            """,
            params,
        )
    rows = []
    for r in cur.fetchall() or []:
        row = dict(r)
        trips = _float(row.get("trips"))
        row["b2b_pct"] = round((_float(row.get("b2b_trips")) or 0) / (trips or 1) * 100, 2) if trips else None
        rows.append(row)
    return rows


def get_daily_table(
    day: date | str | None = None,
    country: str | None = None,
    group_by: Literal["lob", "park", "service_type"] = "lob",
    baseline: BaselineKind | None = None,
) -> dict[str, Any]:
    """
    Tabla diaria: filas por LOB o park. Si baseline se indica, cada fila incluye *_baseline, *_delta_pct, *_trend.
    """
    target = get_last_closed_day() if day is None else (day if isinstance(day, date) else date.fromisoformat(str(day)[:10]))
    out: dict[str, Any] = {"trip_day": target.isoformat(), "group_by": group_by, "baseline": baseline, "rows": []}

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = '15000'")
            current_rows = _daily_table_query(cur, target, country, group_by)
            if not baseline:
                out["rows"] = current_rows
                cur.close()
                return out

            # Baseline dates
            if baseline == "D-1":
                baseline_dates = [target - timedelta(days=1)]
            elif baseline == "same_weekday_previous_week":
                baseline_dates = [target - timedelta(days=7)]
            else:  # same_weekday_avg_4w
                baseline_dates = [target - timedelta(days=7 * i) for i in range(1, 5)]

            baseline_rows: list[dict[str, Any]] = []
            for bd in baseline_dates:
                baseline_rows.extend(_daily_table_query(cur, bd, country, group_by))
            # Aggregate baseline by (country, dimension_key): sum trips/margin then average if 4w
            from collections import defaultdict
            key_to_vals: dict[tuple[str, str], list[dict]] = defaultdict(list)
            for r in baseline_rows:
                key = (str(r.get("country") or ""), str(r.get("dimension_key") or ""))
                key_to_vals[key].append(r)
            n = len(baseline_dates)
            baseline_agg: dict[tuple[str, str], dict] = {}
            for key, list_r in key_to_vals.items():
                trips_sum = sum(_float(r.get("trips")) or 0 for r in list_r)
                margin_sum = sum(_float(r.get("margin_total")) or 0 for r in list_r)
                b2b_sum = sum(_float(r.get("b2b_trips")) or 0 for r in list_r)
                dist_sum = sum((_float(r.get("km_prom")) or 0) * (_float(r.get("trips")) or 0) for r in list_r)
                trips_avg = trips_sum / n if n else 0
                margin_avg = margin_sum / n if n else 0
                margin_trip_b = (margin_sum / trips_sum) if trips_sum else None
                km_prom_b = (dist_sum / trips_sum) if trips_sum else None
                b2b_pct_b = (b2b_sum / trips_sum * 100) if trips_sum else None
                baseline_agg[key] = {
                    "trips": trips_avg, "margin_total": margin_avg, "margin_trip": margin_trip_b,
                    "km_prom": km_prom_b, "b2b_pct": round(b2b_pct_b, 2) if b2b_pct_b is not None else None,
                }
            # Merge into current rows
            for row in current_rows:
                key = (str(row.get("country") or ""), str(row.get("dimension_key") or ""))
                base = baseline_agg.get(key) or {}
                tc = _float(row.get("trips"))
                tb = _float(base.get("trips"))
                mc = _float(row.get("margin_total"))
                mb = _float(base.get("margin_total"))
                mtc = _float(row.get("margin_trip"))
                mtb = _float(base.get("margin_trip"))
                kc = _float(row.get("km_prom"))
                kb = _float(base.get("km_prom"))
                bc = _float(row.get("b2b_pct"))
                bb = _float(base.get("b2b_pct"))
                def _dp(c: float | None, b: float | None) -> float | None:
                    if b is None or b == 0:
                        return None
                    if c is None:
                        return None
                    return round((c - b) / b * 100, 2)
                def _tr(c: float | None, b: float | None) -> str:
                    if b is None or b == 0:
                        return "flat" if (c or 0) == 0 else "up"
                    return "up" if (c or 0) > b else ("down" if (c or 0) < b else "flat")
                row["trips_baseline"] = round(tb, 4) if tb is not None else None
                row["trips_delta_pct"] = _dp(tc, tb)
                row["trips_trend"] = _tr(tc, tb)
                row["margin_total_baseline"] = round(mb, 4) if mb is not None else None
                row["margin_total_delta_pct"] = _dp(mc, mb)
                row["margin_total_trend"] = _tr(mc, mb)
                row["margin_trip_baseline"] = round(mtb, 4) if mtb is not None else None
                row["margin_trip_delta_pct"] = _dp(mtc, mtb)
                row["km_prom_baseline"] = round(kb, 4) if kb is not None else None
                row["km_prom_delta_pct"] = _dp(kc, kb)
                row["b2b_pct_baseline"] = bb
                row["b2b_pct_delta_pp"] = round((bc or 0) - (bb or 0), 2) if bc is not None and bb is not None else None
                row["b2b_pct_trend"] = _tr(bc, bb)
            out["rows"] = current_rows
            out["baseline_label"] = {"D-1": "D-1 (día anterior)", "same_weekday_previous_week": "Mismo día semana pasada", "same_weekday_avg_4w": "Promedio 4 mismos días"}.get(baseline, baseline)
            cur.close()
    except Exception as e:
        out["error"] = str(e)
    return out
