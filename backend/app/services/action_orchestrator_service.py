"""
Orquestador operativo — convierte salida del Action Engine en planes diarios ejecutables.

Consume:
  - ops.action_engine_output (no recalcula reglas del engine)
  - ops.action_playbooks
  - ops.driver_segments (vista)
  - ops.mv_real_lob_day_v2 (volumen / revenue para priorización final)

Produce:
  - ops.action_plan_daily (regeneración completa por día)
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

SEVERITY_BOOST = {"critical": 1.3, "high": 1.15, "medium": 1.0, "low": 0.9}

VOLUME_CAP_MIN = 10
VOLUME_CAP_MAX = 2000

FALLBACK_STEPS = (
    "Asignar owner sugerido → revisar métrica y umbral en el motivo del engine → "
    "definir hipótesis → acción concreta en 24h → medir mismo KPI a las 72h."
)


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


def _volume_from_formula(formula: str, seg: Dict[str, int]) -> int:
    """Interpreta default_volume_formula sembrada en ops.action_playbooks (sin eval arbitrario)."""
    f = (formula or "").strip()
    if f.isdigit():
        return int(f)
    a = seg.get("active", 0)
    i7 = seg.get("inactive_7d", 0)
    lp = seg.get("low_productivity", 0)
    hp = seg.get("high_performer", 0)
    if f == "GREATEST(100, FLOOR(inactive_7d * 0.30))":
        return max(100, int(i7 * 0.30))
    if f == "GREATEST(50, FLOOR(active * 0.20))":
        return max(50, int(a * 0.20))
    if f == "GREATEST(40, FLOOR(low_productivity * 0.35))":
        return max(40, int(lp * 0.35))
    if f == "GREATEST(30, FLOOR(active * 0.10))":
        return max(30, int(a * 0.10))
    if f == "GREATEST(25, FLOOR(active * 0.08))":
        return max(25, int(a * 0.08))
    if f == "GREATEST(25, FLOOR(high_performer * 0.12))":
        return max(25, int(hp * 0.12))
    if f in ("500", "400", "300"):
        return int(f)
    logger.warning("Fórmula de volumen no reconocida: %s — usando 50", f)
    return 50


def _refine_priority_score(
    base: float,
    severity: str,
    city_trips: int,
    city_revenue: float,
    city_size_trips: int,
) -> float:
    """Priorización final: severidad, volumen de viajes, revenue y tamaño de ciudad."""
    sev = SEVERITY_BOOST.get((severity or "low").lower(), 1.0)
    vol = math.log10(max(city_trips, 0) + 10.0) / 3.0
    vol = min(2.0, max(0.55, vol))
    rev = math.log10(abs(city_revenue) + 100.0) / 5.0
    rev = min(1.5, max(0.65, rev))
    csize = math.log10(max(city_size_trips, 0) + 50.0) / 4.0
    csize = min(1.45, max(0.65, csize))
    return round(float(base) * sev * vol * rev * csize, 2)


def _segment_counts(
    cur: Any,
    country: Optional[str],
    city: Optional[str],
    park_id: Optional[str],
) -> Dict[str, int]:
    keys = ("active", "inactive_7d", "inactive_30d", "low_productivity", "high_performer", "dormant")
    empty = {k: 0 for k in keys}
    if city:
        params: Tuple = (country or "", city)
        if park_id:
            cur.execute(
                """
                SELECT segment, COUNT(*)::bigint AS n
                FROM ops.driver_segments
                WHERE country = %s AND city = %s AND park_id = %s
                GROUP BY segment
                """,
                (country or "", city, str(park_id)),
            )
        else:
            cur.execute(
                """
                SELECT segment, COUNT(*)::bigint AS n
                FROM ops.driver_segments
                WHERE country = %s AND city = %s
                GROUP BY segment
                """,
                params,
            )
    else:
        cur.execute(
            """
            SELECT segment, COUNT(*)::bigint AS n
            FROM ops.driver_segments
            GROUP BY segment
            """
        )
    out = dict(empty)
    for row in cur.fetchall():
        s = row["segment"]
        if s in out:
            out[s] = int(row["n"] or 0)
    return out


def _city_rollup(
    cur: Any, target_date: date
) -> Tuple[Dict[Tuple[str, str], Dict[str, float]], Dict[str, float]]:
    """Por (country, city): trips_7d, revenue_7d. Totales globales bajo clave __global__."""
    cur.execute(
        """
        SELECT country, city,
               SUM(completed_trips)::bigint AS trips,
               SUM(gross_revenue)::numeric AS revenue
        FROM ops.mv_real_lob_day_v2
        WHERE trip_date >= %s::date - INTERVAL '7 days'
          AND trip_date < %s::date
        GROUP BY country, city
        """,
        (target_date, target_date),
    )
    by_city: Dict[Tuple[str, str], Dict[str, float]] = {}
    g_trips = 0.0
    g_rev = 0.0
    for row in cur.fetchall():
        co = row["country"] or ""
        ci = row["city"] or ""
        t = float(row["trips"] or 0)
        r = _f(row["revenue"])
        by_city[(co, ci)] = {"trips": t, "revenue": r}
        g_trips += t
        g_rev += r
    return by_city, {"trips": g_trips, "revenue": g_rev}


def run_action_orchestrator(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Regenera ops.action_plan_daily para plan_date = target_date (default hoy).
    Requiere filas previas en ops.action_engine_output para esa run_date.
    """
    if target_date is None:
        target_date = date.today()

    from app.services.action_learning_service import get_effectiveness_multipliers_bulk

    inserted = 0
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '300000'")

        cur.execute(
            "DELETE FROM ops.action_plan_daily WHERE plan_date = %s",
            (target_date,),
        )

        by_city, global_roll = _city_rollup(cur, target_date)

        cur.execute(
            """
            SELECT
                e.id AS engine_output_id,
                e.run_date,
                e.country,
                e.city,
                e.park_id,
                e.action_id,
                e.action_name,
                e.severity,
                e.priority_score AS engine_priority_score,
                e.reason,
                e.metric_name,
                e.metric_value,
                c.action_type,
                c.expected_impact AS catalog_expected_impact,
                pb.playbook_id,
                pb.default_volume_formula,
                pb.target_segment AS playbook_target_segment,
                pb.execution_steps,
                pb.expected_impact AS playbook_expected_impact
            FROM ops.action_engine_output e
            INNER JOIN ops.action_catalog c ON c.action_id = e.action_id AND c.is_active
            LEFT JOIN LATERAL (
                SELECT p.*
                FROM ops.action_playbooks p
                WHERE p.action_id = e.action_id AND p.is_active
                ORDER BY p.playbook_id
                LIMIT 1
            ) pb ON TRUE
            WHERE e.run_date = %s
            ORDER BY e.priority_score DESC
            """,
            (target_date,),
        )
        rows = cur.fetchall()

        action_ids_in_rows = list({r["action_id"] for r in rows})
        try:
            eff_map = get_effectiveness_multipliers_bulk(action_ids_in_rows)
        except Exception as exc:
            logger.warning("effectiveness lookup (orchestrator) failed: %s", exc)
            eff_map = {}

        for row in rows:
            country = row.get("country") or ""
            city = row.get("city") or None
            park_id = row.get("park_id")
            seg = _segment_counts(cur, country or None, city, park_id)

            formula = row.get("default_volume_formula") or "50"
            target_segment = row.get("playbook_target_segment") or "active"
            steps = row.get("execution_steps") or FALLBACK_STEPS
            playbook_id = row.get("playbook_id")
            exp_impact = row.get("playbook_expected_impact") or row.get(
                "catalog_expected_impact"
            )

            if row.get("playbook_id"):
                vol = _volume_from_formula(formula, seg)
            else:
                vol = max(30, int(seg.get("active", 0) * 0.05) + 20)

            eff_mult, eff_scope = eff_map.get(row["action_id"], (1.0, "none"))
            if eff_scope != "none":
                vol = int(vol * eff_mult)
            vol = max(VOLUME_CAP_MIN, min(VOLUME_CAP_MAX, vol))

            ck = (country, city or "")
            roll = by_city.get(ck) if city else None
            if roll is None:
                if city:
                    roll = {"trips": float(seg.get("active", 0) * 12), "revenue": 0.0}
                else:
                    roll = global_roll

            city_trips = int(roll.get("trips", 0))
            city_rev = float(roll.get("revenue", 0.0))
            city_size = city_trips if city_trips > 0 else int(global_roll.get("trips", 0))

            refined = _refine_priority_score(
                _f(row.get("engine_priority_score")),
                row.get("severity") or "low",
                city_trips,
                city_rev,
                city_size,
            )

            cur.execute(
                """
                INSERT INTO ops.action_plan_daily (
                    plan_date, country, city, park_id,
                    action_id, action_name, action_type,
                    severity, priority_score,
                    suggested_volume, target_segment,
                    suggested_playbook_id, suggested_playbook_text,
                    expected_impact, status, source,
                    engine_reason, engine_output_id
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    target_date,
                    country or None,
                    city,
                    park_id,
                    row["action_id"],
                    row["action_name"],
                    row["action_type"],
                    row["severity"],
                    refined,
                    vol,
                    target_segment,
                    playbook_id,
                    steps,
                    exp_impact,
                    "ready",
                    "action_engine",
                    row.get("reason"),
                    row.get("engine_output_id"),
                ),
            )
            inserted += 1

        cur.close()

    return {
        "plan_date": str(target_date),
        "generated_at": datetime.utcnow().isoformat(),
        "source_rows": len(rows),
        "plans_inserted": inserted,
    }


def get_action_plans(
    plan_date: Optional[date] = None,
    city: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    if plan_date is None:
        plan_date = date.today()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        where = ["plan_date = %s"]
        params: List[Any] = [plan_date]
        if city:
            where.append("LOWER(TRIM(city)) = LOWER(TRIM(%s))")
            params.append(city)
        params.extend([limit, offset])
        cur.execute(
            f"""
            SELECT id, plan_date, country, city, park_id, action_id, action_name,
                   action_type, severity, priority_score, suggested_volume,
                   target_segment, suggested_playbook_id, suggested_playbook_text,
                   expected_impact, status, source, engine_reason, created_at
            FROM ops.action_plan_daily
            WHERE {' AND '.join(where)}
            ORDER BY priority_score DESC NULLS LAST, city NULLS LAST, action_id
            LIMIT %s OFFSET %s
            """,
            params,
        )
        out = [dict(r) for r in cur.fetchall()]
        cur.close()
        return out


def log_plan_execution(
    action_plan_id: int,
    action_id: str,
    owner: str,
    status: str = "pending",
    notes: Optional[str] = None,
) -> int:
    """Tracking humano sobre una fila de action_plan_daily (no ejecuta acciones externas)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ops.action_execution_log
                (action_plan_id, action_id, owner, status, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (action_plan_id, action_id, owner, status, notes),
        )
        new_id = cur.fetchone()[0]
        cur.close()
        return new_id
