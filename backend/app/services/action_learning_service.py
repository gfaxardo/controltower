"""
Learning Engine — evalúa resultados de acciones ejecutadas y provee feedback
de efectividad al Action Engine y al Orchestrator.

Consume:
  - ops.action_execution_log (acciones marcadas done/in_progress)
  - ops.action_evaluation_rules (métrica, dirección, ventana, umbral)
  - ops.mv_real_lob_day_v2 (baseline y post-medición para ops/supply/pricing)
  - ops.revenue_quality_alerts (para data_quality)

Produce:
  - UPDATE en action_execution_log (result_value_before, _after, delta, success_flag)
  - ops.action_effectiveness (vista agregada; lectura)

NO ejecuta acciones externas ni modifica reglas del engine.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

MV_DAY = "ops.mv_real_lob_day_v2"

EFFECTIVENESS_HIGH = 70.0
EFFECTIVENESS_LOW = 30.0
BOOST_FACTOR = 1.20
PENALTY_FACTOR = 0.80
NEUTRAL_FACTOR = 1.0
MIN_EXECUTIONS_FOR_SIGNAL = 3


def _f(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        x = float(v)
        return 0.0 if x != x else x
    except (TypeError, ValueError):
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════
# L3 — Evaluador de resultados
# ═══════════════════════════════════════════════════════════════════════════

def _measure_metric(
    cur: Any,
    metric: str,
    country: Optional[str],
    city: Optional[str],
    date_from: date,
    date_to: date,
) -> Optional[float]:
    """
    Mide una métrica operativa en la ventana [date_from, date_to).
    Retorna valor escalar o None si no hay datos.
    """
    co_clause = "AND country = %s" if country else ""
    ci_clause = "AND city = %s" if city else ""
    params: list = [date_from, date_to]
    if country:
        params.append(country)
    if city:
        params.append(city)

    if metric == "trips":
        cur.execute(f"""
            SELECT COALESCE(SUM(completed_trips), 0)::numeric AS val
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date < %s {co_clause} {ci_clause}
        """, params)
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    if metric == "revenue":
        cur.execute(f"""
            SELECT COALESCE(SUM(gross_revenue), 0)::numeric AS val
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date < %s {co_clause} {ci_clause}
        """, params)
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    if metric == "active_drivers":
        cur.execute("""
            SELECT COUNT(DISTINCT driver_id)::bigint AS val
            FROM ops.driver_segments
            WHERE segment IN ('active','high_performer','low_productivity')
            {co} {ci}
        """.format(
            co="AND country = %s" if country else "",
            ci="AND city = %s" if city else "",
        ), ([country] if country else []) + ([city] if city else []))
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    if metric == "trips_per_driver":
        trips = _measure_metric(cur, "trips", country, city, date_from, date_to)
        drivers = _measure_metric(cur, "active_drivers", country, city, date_from, date_to)
        if drivers and drivers > 0 and trips is not None:
            return round(trips / drivers, 4)
        return None

    if metric == "cancel_rate":
        cur.execute(f"""
            SELECT
                CASE WHEN SUM(requested_trips) > 0
                    THEN ROUND(SUM(cancelled_trips)::numeric / SUM(requested_trips)::numeric * 100, 4)
                    ELSE NULL
                END AS val
            FROM {MV_DAY}
            WHERE trip_date >= %s AND trip_date < %s {co_clause} {ci_clause}
        """, params)
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    if metric == "proxy_pct":
        cur.execute("""
            SELECT observed_value::numeric AS val
            FROM ops.revenue_quality_alerts
            WHERE metric = 'pct_proxy'
            ORDER BY check_ts DESC LIMIT 1
        """)
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    if metric == "data_quality_issue_count":
        cur.execute("""
            SELECT COUNT(*)::bigint AS val
            FROM ops.revenue_quality_alerts
            WHERE severity IN ('blocked','warning')
              AND check_ts >= %s::date::timestamptz
              AND check_ts < %s::date::timestamptz
        """, (date_from, date_to))
        r = cur.fetchone()
        return _f(r["val"]) if r else None

    logger.warning("Métrica no reconocida para evaluación: %s", metric)
    return None


def evaluate_executions(
    min_status: str = "done",
    force_re_evaluate: bool = False,
    limit: int = 500,
) -> Dict[str, Any]:
    """
    Evalúa acciones ejecutadas que tengan status = min_status (o 'in_progress')
    y que aún no hayan sido evaluadas (evaluated_at IS NULL), salvo force_re_evaluate.
    """
    evaluated = 0
    skipped = 0
    errors = 0

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '300000'")

        evaluated_filter = "" if force_re_evaluate else "AND l.evaluated_at IS NULL"
        cur.execute(f"""
            SELECT
                l.id AS log_id,
                l.action_id,
                l.action_plan_id,
                l.action_output_id,
                l.execution_date,
                l.status,
                COALESCE(p.country, eo.country) AS country,
                COALESCE(p.city, eo.city) AS city,
                r.result_metric,
                r.expected_direction,
                r.evaluation_window_days,
                r.success_threshold_pct
            FROM ops.action_execution_log l
            LEFT JOIN ops.action_plan_daily p ON p.id = l.action_plan_id
            LEFT JOIN ops.action_engine_output eo ON eo.id = l.action_output_id
            INNER JOIN ops.action_evaluation_rules r
                ON r.action_id = l.action_id AND r.is_active
            WHERE l.status IN (%s, 'in_progress')
              {evaluated_filter}
            ORDER BY l.execution_date ASC
            LIMIT %s
        """, (min_status, limit))

        rows = cur.fetchall()

        for row in rows:
            try:
                exec_date = row["execution_date"]
                window = int(row["evaluation_window_days"] or 7)
                metric = row["result_metric"]
                direction = row["expected_direction"]
                threshold_pct = _f(row["success_threshold_pct"])
                country = row.get("country") or None
                city = row.get("city") or None

                before_start = exec_date - timedelta(days=window)
                before_end = exec_date
                after_start = exec_date
                after_end = exec_date + timedelta(days=window)

                if after_end > date.today():
                    skipped += 1
                    continue

                val_before = _measure_metric(cur, metric, country, city, before_start, before_end)
                val_after = _measure_metric(cur, metric, country, city, after_start, after_end)

                if val_before is None or val_after is None:
                    skipped += 1
                    continue

                if direction == "down":
                    delta = val_before - val_after
                    if val_before > 0:
                        delta_pct = (delta / abs(val_before)) * 100.0
                    else:
                        delta_pct = 0.0
                else:
                    delta = val_after - val_before
                    if val_before > 0:
                        delta_pct = (delta / abs(val_before)) * 100.0
                    elif val_after > 0:
                        delta_pct = 100.0
                    else:
                        delta_pct = 0.0

                success = delta_pct >= threshold_pct

                cur.execute("""
                    UPDATE ops.action_execution_log
                    SET result_metric = %s,
                        result_value_before = %s,
                        result_value_after = %s,
                        result_delta = %s,
                        success_flag = %s,
                        evaluation_window_days = %s,
                        evaluated_at = now()
                    WHERE id = %s
                """, (
                    metric,
                    round(val_before, 6),
                    round(val_after, 6),
                    round(delta, 6),
                    success,
                    window,
                    row["log_id"],
                ))
                evaluated += 1
            except Exception as exc:
                logger.error("Error evaluando log_id=%s: %s", row.get("log_id"), exc)
                errors += 1

        cur.close()

    return {
        "evaluated": evaluated,
        "skipped": skipped,
        "errors": errors,
        "evaluated_at": datetime.utcnow().isoformat(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# L4 — Lectura de efectividad (desde vista ops.action_effectiveness)
# ═══════════════════════════════════════════════════════════════════════════

def get_effectiveness(
    action_id: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = []
        params: list = []
        if action_id:
            where.append("action_id = %s")
            params.append(action_id)
        if city:
            where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
            params.append(city)
        if country:
            where.append("country = %s")
            params.append(country)
        params.append(limit)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        cur.execute(f"""
            SELECT action_id, city, country,
                   executions_count, success_count, success_rate,
                   avg_result_delta, last_execution_at, last_evaluated_at
            FROM ops.action_effectiveness
            {w}
            ORDER BY executions_count DESC NULLS LAST
            LIMIT %s
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


def get_evaluated_executions(
    action_id: Optional[str] = None,
    city: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["l.evaluated_at IS NOT NULL"]
        params: list = []
        if action_id:
            where.append("l.action_id = %s")
            params.append(action_id)
        if city:
            where.append("LOWER(TRIM(COALESCE(p.city, eo.city))) = LOWER(TRIM(%s))")
            params.append(city)
        params.extend([limit, offset])
        cur.execute(f"""
            SELECT l.id, l.action_id, l.execution_date, l.owner, l.status,
                   l.result_metric, l.result_value_before, l.result_value_after,
                   l.result_delta, l.success_flag, l.evaluation_window_days,
                   l.evaluated_at,
                   COALESCE(p.city, eo.city) AS city,
                   COALESCE(p.country, eo.country) AS country
            FROM ops.action_execution_log l
            LEFT JOIN ops.action_plan_daily p ON p.id = l.action_plan_id
            LEFT JOIN ops.action_engine_output eo ON eo.id = l.action_output_id
            WHERE {' AND '.join(where)}
            ORDER BY l.evaluated_at DESC NULLS LAST
            LIMIT %s OFFSET %s
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


def get_evaluation_rules(active_only: bool = True) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        w = "WHERE is_active" if active_only else ""
        cur.execute(f"""
            SELECT id, action_id, action_name, result_metric,
                   expected_direction, evaluation_window_days,
                   success_threshold_pct, is_active, created_at
            FROM ops.action_evaluation_rules
            {w}
            ORDER BY action_id
        """)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


# ═══════════════════════════════════════════════════════════════════════════
# L5 — Effectiveness multiplier (lookup jerárquico)
# ═══════════════════════════════════════════════════════════════════════════

def get_effectiveness_multiplier(
    action_id: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> Tuple[float, str]:
    """
    Retorna (multiplier, scope).
    Fallback jerárquico: city → country → global → none (neutro).
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        for scope, params in _effectiveness_scopes(action_id, country, city):
            cur.execute("""
                SELECT success_rate, executions_count
                FROM ops.action_effectiveness
                WHERE action_id = %s {extra}
                ORDER BY executions_count DESC
                LIMIT 1
            """.format(extra=params["extra"]), params["args"])
            row = cur.fetchone()
            if row and int(row["executions_count"] or 0) >= MIN_EXECUTIONS_FOR_SIGNAL:
                sr = _f(row["success_rate"])
                m = _sr_to_multiplier(sr)
                cur.close()
                return m, scope

        cur.close()
        return NEUTRAL_FACTOR, "none"


def get_effectiveness_multipliers_bulk(
    action_ids: List[str],
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Tuple[float, str]]:
    """Batch de multipliers para varios action_ids (evita N+1 queries)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT action_id, city, country, success_rate, executions_count
            FROM ops.action_effectiveness
            WHERE action_id = ANY(%s)
        """, (list(action_ids),))
        rows = cur.fetchall()
        cur.close()

    by_key: Dict[Tuple[str, Optional[str], Optional[str]], dict] = {}
    for r in rows:
        k = (r["action_id"], r.get("city"), r.get("country"))
        existing = by_key.get(k)
        if existing is None or int(r["executions_count"] or 0) > int(existing["executions_count"] or 0):
            by_key[k] = dict(r)

    result: Dict[str, Tuple[float, str]] = {}
    for aid in action_ids:
        for scope, ci_val, co_val in _lookup_chain(aid, country, city):
            k = (aid, ci_val, co_val)
            entry = by_key.get(k)
            if entry and int(entry["executions_count"] or 0) >= MIN_EXECUTIONS_FOR_SIGNAL:
                result[aid] = (_sr_to_multiplier(_f(entry["success_rate"])), scope)
                break
        else:
            result[aid] = (NEUTRAL_FACTOR, "none")
    return result


def _lookup_chain(
    action_id: str,
    country: Optional[str],
    city: Optional[str],
) -> List[Tuple[str, Optional[str], Optional[str]]]:
    chain = []
    if city and country:
        chain.append(("city", city, country))
    if country:
        chain.append(("country", None, country))
    chain.append(("global", None, None))
    return chain


def _effectiveness_scopes(
    action_id: str,
    country: Optional[str],
    city: Optional[str],
) -> List[Tuple[str, Dict]]:
    scopes = []
    if city and country:
        scopes.append(("city", {
            "extra": "AND LOWER(TRIM(city)) = LOWER(TRIM(%s)) AND country = %s",
            "args": (action_id, city, country),
        }))
    if country:
        scopes.append(("country", {
            "extra": "AND country = %s AND (city IS NULL OR city = '')",
            "args": (action_id, country),
        }))
    scopes.append(("global", {
        "extra": "",
        "args": (action_id,),
    }))
    return scopes


def _sr_to_multiplier(success_rate: float) -> float:
    if success_rate >= EFFECTIVENESS_HIGH:
        return BOOST_FACTOR
    if success_rate <= EFFECTIVENESS_LOW:
        return PENALTY_FACTOR
    return NEUTRAL_FACTOR
