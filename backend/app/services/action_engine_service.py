"""
Action Engine — traduce métricas + alertas en acciones operativas priorizadas.

Consume:
  - ops.mv_real_lob_day_v2 (trips, revenue, cancellations)
  - ops.revenue_quality_alerts (alertas de calidad)
  - ops.v_real_trip_fact_v2 (revenue source distribution)

Produce:
  - ops.action_engine_output (acciones priorizadas por ciudad/día)

Priorización:
  priority_score = severity_weight * volume_factor * revenue_factor
  Donde:
    severity_weight: critical=100, high=70, medium=40, low=10
    volume_factor: log2(completed_trips + 1) normalizado a [1..10]
    revenue_factor: basado en revenue estimado del segmento
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

SEVERITY_WEIGHT = {"critical": 100, "high": 70, "medium": 40, "low": 10}

MV_DAY = "ops.mv_real_lob_day_v2"


def _f(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    try:
        f = float(v)
        return 0.0 if f != f else f  # NaN → 0
    except (TypeError, ValueError):
        return 0.0


def _priority(severity: str, completed: int, revenue: float) -> float:
    sw = SEVERITY_WEIGHT.get(severity, 10)
    vol = min(10, max(1, math.log2(completed + 1)))
    rev = min(10, max(1, math.log2(abs(revenue) + 1) / 3))
    return round(sw * vol * rev, 2)


def _action(
    country: str, city: str, action_id: str, name: str, severity: str,
    reason: str, metric: str, value: float, threshold: float,
    owner: str, completed: int = 0, revenue: float = 0,
    park_id: str = None,
) -> Dict[str, Any]:
    return {
        "country": country,
        "city": city,
        "park_id": park_id,
        "action_id": action_id,
        "action_name": name,
        "severity": severity,
        "priority_score": _priority(severity, completed, revenue),
        "reason": reason,
        "metric_name": metric,
        "metric_value": value,
        "threshold": threshold,
        "suggested_owner": owner,
    }


def run_action_engine(target_date: Optional[date] = None) -> Dict[str, Any]:
    """Ejecuta el engine y retorna acciones del día."""
    if target_date is None:
        target_date = date.today()

    actions: List[Dict[str, Any]] = []

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '300000'")

        # ── Métricas WoW por ciudad ──
        cur.execute(f"""
            WITH this_week AS (
                SELECT country, city,
                    SUM(completed_trips) AS trips,
                    SUM(gross_revenue) AS revenue,
                    SUM(cancelled_trips) AS cancelled,
                    SUM(requested_trips) AS requested,
                    COUNT(DISTINCT park_id) FILTER (WHERE completed_trips > 0) AS active_parks
                FROM {MV_DAY}
                WHERE trip_date >= %s::date - INTERVAL '7 days'
                  AND trip_date < %s::date
                GROUP BY country, city
            ),
            prev_week AS (
                SELECT country, city,
                    SUM(completed_trips) AS trips,
                    SUM(gross_revenue) AS revenue,
                    SUM(cancelled_trips) AS cancelled,
                    SUM(requested_trips) AS requested
                FROM {MV_DAY}
                WHERE trip_date >= %s::date - INTERVAL '14 days'
                  AND trip_date < %s::date - INTERVAL '7 days'
                GROUP BY country, city
            )
            SELECT
                tw.country, tw.city,
                tw.trips AS tw_trips, pw.trips AS pw_trips,
                tw.revenue AS tw_revenue, pw.revenue AS pw_revenue,
                tw.cancelled AS tw_cancelled, tw.requested AS tw_requested,
                pw.cancelled AS pw_cancelled, pw.requested AS pw_requested,
                tw.active_parks
            FROM this_week tw
            LEFT JOIN prev_week pw ON tw.country = pw.country AND tw.city = pw.city
            WHERE tw.trips > 50
        """, (target_date, target_date, target_date, target_date))

        for row in cur.fetchall():
            country = row["country"] or ""
            city = row["city"] or ""
            tw_t = int(row["tw_trips"] or 0)
            pw_t = int(row["pw_trips"] or 0)
            tw_r = _f(row["tw_revenue"])
            pw_r = _f(row["pw_revenue"])
            tw_canc = int(row["tw_cancelled"] or 0)
            tw_req = int(row["tw_requested"] or 0)
            pw_canc = int(row["pw_cancelled"] or 0)
            pw_req = int(row["pw_requested"] or 0)

            # ── Trips drop ──
            if pw_t > 50:
                trips_change = round(100.0 * (tw_t - pw_t) / pw_t, 2)
                if trips_change <= -20:
                    actions.append(_action(
                        country, city, "TRIPS_DROP_CITY",
                        "Investigar caída de viajes en ciudad", "high",
                        f"Viajes cayeron {trips_change}% WoW ({pw_t:,}→{tw_t:,})",
                        "trips_wow_change_pct", trips_change, -20,
                        "ops_city_manager", tw_t, tw_r,
                    ))

            # ── Revenue drop ──
            if pw_r > 100:
                rev_change = round(100.0 * (tw_r - pw_r) / pw_r, 2)
                if rev_change <= -30:
                    actions.append(_action(
                        country, city, "REVENUE_DROP_CITY",
                        "Investigar caída de revenue en ciudad", "high",
                        f"Revenue cayó {rev_change}% WoW ({pw_r:,.0f}→{tw_r:,.0f})",
                        "revenue_wow_change_pct", rev_change, -30,
                        "ops_city_manager", tw_t, tw_r,
                    ))

            # ── Zero revenue ──
            if tw_t > 100 and tw_r == 0:
                actions.append(_action(
                    country, city, "ZERO_REVENUE_CITY",
                    "Revenue cero en ciudad activa", "critical",
                    f"Ciudad {city}: {tw_t:,} completados pero revenue=0",
                    "city_revenue", 0, 1,
                    "data_engineering", tw_t, 0,
                ))

            # ── Cancel rate spike ──
            tw_cr = (tw_canc / tw_req * 100) if tw_req > 0 else 0
            pw_cr = (pw_canc / pw_req * 100) if pw_req > 0 else 0
            cr_change = round(tw_cr - pw_cr, 2)
            if cr_change >= 5 and tw_req > 100:
                actions.append(_action(
                    country, city, "CANCEL_RATE_SPIKE",
                    "Auditar cancelaciones elevadas", "high",
                    f"Cancel rate subió {cr_change}pp WoW ({pw_cr:.1f}%→{tw_cr:.1f}%)",
                    "cancel_rate_change_pp", cr_change, 5,
                    "ops_team", tw_t, tw_r,
                ))

        # ── Revenue quality alerts → acciones ──
        cur.execute("""
            SELECT domain, severity, metric, observed_value, threshold, message
            FROM ops.revenue_quality_alerts
            WHERE check_ts >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
              AND severity IN ('blocked', 'warning')
            ORDER BY check_ts DESC
        """)
        for row in cur.fetchall():
            metric = row["metric"]
            val = _f(row["observed_value"])

            if metric == "pct_proxy" and val >= 95:
                actions.append(_action(
                    "", "", "INGEST_ESCALATE",
                    "Escalar problema de ingestión de comisión", "critical",
                    row["message"], "pct_proxy", val, 95,
                    "data_engineering", 0, 0,
                ))
            elif metric == "precio_yango_pro_nan" and val > 0:
                domain = row["domain"]
                actions.append(_action(
                    "", "", "NAN_RAW_DATA",
                    "Limpiar NaN en datos fuente", "high",
                    row["message"], "nan_count_raw", val, 0,
                    "data_engineering", 0, 0,
                ))
            elif metric == "pct_missing_revenue" and val >= 5:
                actions.append(_action(
                    "", "", "MISSING_REVENUE",
                    "Viajes sin revenue (ni real ni proxy)", "high",
                    row["message"], "pct_missing_revenue", val, 5,
                    "data_engineering", 0, 0,
                ))
            elif metric == "trips_drift_pct" and val >= 15:
                actions.append(_action(
                    "", "", "DRIFT_CROSS_CHAIN",
                    "Auditoría de drift entre cadenas", "medium",
                    row["message"], "cross_chain_drift_pct", val, 15,
                    "data_engineering", 0, 0,
                ))

        # ── Data freshness ──
        cur.execute(f"""
            SELECT MAX(trip_date) AS last_date FROM {MV_DAY}
        """)
        r = cur.fetchone()
        if r and r["last_date"]:
            hours_old = (datetime.now() - datetime.combine(
                r["last_date"], datetime.min.time()
            )).total_seconds() / 3600
            if hours_old >= 48:
                actions.append(_action(
                    "", "", "DATA_FRESHNESS",
                    "Datos desactualizados en cadena crítica", "high",
                    f"Último dato en day_v2: {r['last_date']} ({hours_old:.0f}h de antigüedad)",
                    "hours_since_last_trip", round(hours_old, 1), 48,
                    "data_engineering", 0, 0,
                ))

        cur.close()

    # ── Deduplicar y ordenar por prioridad ──
    seen = set()
    deduped = []
    for a in actions:
        key = (a["action_id"], a["country"], a["city"], a.get("park_id"))
        if key not in seen:
            seen.add(key)
            deduped.append(a)
    deduped.sort(key=lambda x: x["priority_score"], reverse=True)

    return {
        "run_date": str(target_date),
        "generated_at": datetime.utcnow().isoformat(),
        "total_actions": len(deduped),
        "critical": sum(1 for a in deduped if a["severity"] == "critical"),
        "high": sum(1 for a in deduped if a["severity"] == "high"),
        "medium": sum(1 for a in deduped if a["severity"] == "medium"),
        "low": sum(1 for a in deduped if a["severity"] == "low"),
        "actions": deduped,
    }


def persist_action_output(result: Dict[str, Any]) -> int:
    """Persiste acciones en ops.action_engine_output con feedback de efectividad."""
    from app.services.action_learning_service import get_effectiveness_multipliers_bulk

    actions = result.get("actions", [])
    action_ids = list({a["action_id"] for a in actions})
    try:
        multipliers = get_effectiveness_multipliers_bulk(action_ids)
    except Exception as exc:
        logger.warning("effectiveness lookup failed (neutral fallback): %s", exc)
        multipliers = {aid: (1.0, "none") for aid in action_ids}

    with get_db() as conn:
        cur = conn.cursor()
        run_date = result.get("run_date", str(date.today()))
        cur.execute(
            "DELETE FROM ops.action_engine_output WHERE run_date = %s",
            (run_date,),
        )
        count = 0
        for a in actions:
            base_score = a["priority_score"]
            eff_mult, eff_scope = multipliers.get(a["action_id"], (1.0, "none"))
            final_score = round(base_score * eff_mult, 2)
            a["priority_score"] = final_score

            cur.execute("""
                INSERT INTO ops.action_engine_output
                    (run_date, country, city, park_id, action_id, action_name,
                     severity, priority_score, reason, metric_name,
                     metric_value, threshold, suggested_owner,
                     effectiveness_score, effectiveness_scope,
                     priority_score_base, priority_score_final)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s)
            """, (
                run_date, a.get("country"), a.get("city"), a.get("park_id"),
                a["action_id"], a["action_name"], a["severity"],
                final_score, a["reason"], a.get("metric_name"),
                a.get("metric_value"), a.get("threshold"),
                a.get("suggested_owner"),
                eff_mult, eff_scope, base_score, final_score,
            ))
            count += 1

        result["actions"].sort(key=lambda x: x["priority_score"], reverse=True)
        cur.close()
        return count


def get_today_actions(
    city: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Lee acciones del día desde la tabla persistente."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["run_date = CURRENT_DATE"]
        params: list = []
        if city:
            where.append("LOWER(city) = LOWER(%s)")
            params.append(city)
        if severity:
            where.append("severity = %s")
            params.append(severity)
        params.append(limit)
        cur.execute(f"""
            SELECT id, run_date, country, city, park_id, action_id, action_name,
                   severity, priority_score, reason, metric_name, metric_value,
                   threshold, suggested_owner, created_at
            FROM ops.action_engine_output
            WHERE {' AND '.join(where)}
            ORDER BY priority_score DESC
            LIMIT %s
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


def log_action_execution(
    action_output_id: int,
    action_id: str,
    owner: str,
    status: str = "pending",
    notes: str = None,
) -> int:
    """Registra la ejecución/tracking de una acción."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ops.action_execution_log
                (action_output_id, action_id, owner, status, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (action_output_id, action_id, owner, status, notes))
        new_id = cur.fetchone()[0]
        cur.close()
        return new_id


# ── Compat API legacy (ActionEngineView): cohortes + export ───────────────
# El engine actual persiste en ops.action_engine_output (acciones ciudad/día).
# Estas funciones proyectan esas filas al shape que esperan /ops/action-engine/*.


def _parse_api_date(s: Optional[str]) -> Optional[date]:
    if not s or not str(s).strip():
        return None
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except ValueError:
        return None


def _severity_to_ui_priority(sev: Optional[str]) -> str:
    if not sev:
        return "medium"
    s = str(sev).lower()
    if s == "critical":
        return "high"
    if s in ("high", "medium", "low"):
        return s
    return "medium"


def _action_engine_where(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    week_start: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> tuple[str, list[Any]]:
    parts: list[str] = []
    params: list[Any] = []
    ws = _parse_api_date(week_start)
    fd = _parse_api_date(from_date)
    td = _parse_api_date(to_date)
    if ws:
        parts.append("run_date = %s")
        params.append(ws)
    else:
        if fd:
            parts.append("run_date >= %s")
            params.append(fd)
        if td:
            parts.append("run_date <= %s")
            params.append(td)
        if not fd and not td:
            parts.append("run_date >= CURRENT_DATE - INTERVAL '120 days'")
    if country and str(country).strip():
        parts.append("country IS NOT NULL AND LOWER(TRIM(country::text)) = LOWER(TRIM(%s))")
        params.append(str(country).strip())
    if city and str(city).strip():
        parts.append("city IS NOT NULL AND LOWER(TRIM(city::text)) = LOWER(TRIM(%s))")
        params.append(str(city).strip())
    if park_id and str(park_id).strip():
        parts.append("park_id IS NOT NULL AND TRIM(park_id::text) = TRIM(%s)")
        params.append(str(park_id).strip())
    if cohort_type and str(cohort_type).strip():
        parts.append("action_id = %s")
        params.append(str(cohort_type).strip())
    if priority and str(priority).strip():
        parts.append("severity = %s")
        params.append(str(priority).strip().lower())
    where = " AND ".join(parts) if parts else "TRUE"
    return where, params


def _row_to_cohort_row(r: dict) -> dict[str, Any]:
    rd = r.get("run_date")
    ws = rd.isoformat()[:10] if hasattr(rd, "isoformat") else str(rd or "")[:10]
    sev = r.get("severity")
    return {
        "cohort_type": r.get("action_id"),
        "week_start": ws,
        "week_label": ws,
        "cohort_size": 1,
        "dominant_segment": "—",
        "avg_risk_score": float(r.get("priority_score") or 0),
        "avg_delta_pct": None,
        "suggested_priority": _severity_to_ui_priority(sev),
        "suggested_channel": r.get("suggested_owner") or "",
        "action_objective": r.get("reason"),
    }


def _row_to_recommendation(r: dict) -> dict[str, Any]:
    rd = r.get("run_date")
    ws = rd.isoformat()[:10] if hasattr(rd, "isoformat") else str(rd or "")[:10]
    return {
        "action_name": r.get("action_name"),
        "cohort_type": r.get("action_id"),
        "cohort_size": 1,
        "week_label": ws,
        "week_start": ws,
        "avg_delta_pct": None,
        "suggested_priority": _severity_to_ui_priority(r.get("severity")),
        "suggested_channel": r.get("suggested_owner") or "",
        "action_objective": r.get("reason"),
    }


def _row_to_export_row(r: dict) -> dict[str, Any]:
    rd = r.get("run_date")
    ws = rd.isoformat()[:10] if hasattr(rd, "isoformat") else str(rd or "")[:10]
    aid = r.get("action_id") or ""
    city = r.get("city") or ""
    key = f"{aid}|{city}|{ws}"
    return {
        "driver_key": key,
        "driver_name": r.get("action_name"),
        "week_start": ws,
        "week_label": ws,
        "country": r.get("country"),
        "city": r.get("city"),
        "park_id": r.get("park_id"),
        "park_name": None,
        "segment_current": aid,
        "segment_previous": None,
        "movement_type": None,
        "trips_current_week": r.get("metric_value"),
        "avg_trips_baseline": r.get("threshold"),
        "delta_abs": None,
        "delta_pct": None,
        "alert_type": aid,
        "severity": r.get("severity"),
        "risk_score": r.get("priority_score"),
        "risk_band": None,
        "cohort_type": aid,
    }


def get_action_engine_summary(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict[str, Any]:
    """KPIs derivados de ops.action_engine_output (compat UI cohortes)."""
    del segment_current  # no aplica al output operativo actual
    where, params = _action_engine_where(
        from_date, to_date, week_start, country, city, park_id, cohort_type, priority,
    )
    sql = f"""
        WITH base AS (
            SELECT * FROM ops.action_engine_output WHERE {where}
        )
        SELECT
            (SELECT COUNT(*)::int FROM base) AS n,
            (SELECT COUNT(*)::int FROM base WHERE severity IN ('high', 'critical')) AS n_high,
            (SELECT COUNT(*)::int FROM (SELECT DISTINCT action_id, run_date FROM base) d) AS n_groups
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            row = cur.fetchone() or {}
            cur.close()
    except Exception as exc:
        logger.warning("get_action_engine_summary: %s", exc)
        return {
            "actionable_drivers": 0,
            "cohorts_detected": 0,
            "high_priority_cohorts": 0,
            "recoverable_drivers": 0,
            "high_value_at_risk": 0,
            "near_upgrade_opportunities": 0,
            "note": "Sin datos o tabla no disponible.",
        }
    n = int(row.get("n") or 0)
    n_high = int(row.get("n_high") or 0)
    n_groups = int(row.get("n_groups") or 0)
    return {
        "actionable_drivers": n,
        "cohorts_detected": n_groups,
        "high_priority_cohorts": n_high,
        "recoverable_drivers": 0,
        "high_value_at_risk": 0,
        "near_upgrade_opportunities": 0,
        "note": "Valores desde acciones operativas (no cohortes de conductores).",
    }


def get_action_engine_cohorts(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    del segment_current
    where, params = _action_engine_where(
        from_date, to_date, week_start, country, city, park_id, cohort_type, priority,
    )
    count_sql = f"SELECT COUNT(*)::int AS c FROM ops.action_engine_output WHERE {where}"
    data_sql = f"""
        SELECT id, run_date, country, city, park_id, action_id, action_name,
               severity, priority_score, reason, suggested_owner
        FROM ops.action_engine_output
        WHERE {where}
        ORDER BY priority_score DESC NULLS LAST, run_date DESC, id DESC
        LIMIT %s OFFSET %s
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(count_sql, params)
            total = int((cur.fetchone() or {}).get("c") or 0)
            cur.execute(data_sql, params + [limit, offset])
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("get_action_engine_cohorts: %s", exc)
        return {"data": [], "total": 0}
    return {"data": [_row_to_cohort_row(r) for r in rows], "total": total}


def get_action_engine_cohort_detail(
    cohort_type: str,
    week_start: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> dict[str, Any]:
    """El engine actual no expone conductores por cohorte; drill vacío."""
    del cohort_type, week_start, country, city, park_id, limit, offset
    return {
        "data": [],
        "total": 0,
        "note": "Detalle por conductor no disponible para acciones operativas ciudad/día.",
    }


def get_action_engine_recommendations(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    top_n: int = 5,
) -> dict[str, Any]:
    del segment_current
    where, params = _action_engine_where(
        from_date, to_date, week_start, country, city, park_id, None, None,
    )
    sql = f"""
        SELECT id, run_date, action_id, action_name, severity, suggested_owner, reason
        FROM ops.action_engine_output
        WHERE {where}
        ORDER BY priority_score DESC NULLS LAST, run_date DESC, id DESC
        LIMIT %s
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params + [top_n])
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("get_action_engine_recommendations: %s", exc)
        return {"data": []}
    return {"data": [_row_to_recommendation(r) for r in rows]}


def get_action_engine_export(
    week_start: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    park_id: Optional[str] = None,
    segment_current: Optional[str] = None,
    cohort_type: Optional[str] = None,
    priority: Optional[str] = None,
    max_rows: int = 10000,
) -> list[dict[str, Any]]:
    del segment_current
    where, params = _action_engine_where(
        from_date, to_date, week_start, country, city, park_id, cohort_type, priority,
    )
    cap = min(max(int(max_rows), 1), 50000)
    sql = f"""
        SELECT id, run_date, country, city, park_id, action_id, action_name,
               severity, priority_score, reason, metric_name, metric_value,
               threshold, suggested_owner
        FROM ops.action_engine_output
        WHERE {where}
        ORDER BY priority_score DESC NULLS LAST, run_date DESC, id DESC
        LIMIT %s
    """
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params + [cap])
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
    except Exception as exc:
        logger.warning("get_action_engine_export: %s", exc)
        return []
    return [_row_to_export_row(r) for r in rows]
