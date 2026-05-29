"""
Yango Loyalty Metric Definition Preview Service
Pilot phase — previews definition sets against reconciliation reference.
"""
from __future__ import annotations
import logging
from datetime import date
from typing import Any, Optional
from psycopg2.extras import RealDictCursor
from app.db.connection import get_db

logger = logging.getLogger(__name__)
TIMEOUT_MS = 120000


def get_sources() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM ops.yango_loyalty_source_registry WHERE is_active ORDER BY source_key")
        return [dict(r) for r in cur.fetchall()]


def get_definition_sets() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT ds.*, COUNT(r.rule_id) as rule_count
            FROM ops.yango_loyalty_metric_definition_sets ds
            LEFT JOIN ops.yango_loyalty_metric_rules r ON r.definition_set_id = ds.definition_set_id
            GROUP BY ds.definition_set_id, ds.program_key, ds.country, ds.city_norm,
                     ds.effective_from, ds.effective_to, ds.status, ds.validation_status,
                     ds.created_by, ds.approved_by, ds.approved_at, ds.notes, ds.created_at, ds.updated_at
            ORDER BY ds.definition_set_id
        """)
        return [dict(r) for r in cur.fetchall()]


def get_definition_set(set_id: str) -> Optional[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM ops.yango_loyalty_metric_definition_sets
            WHERE definition_set_id = %s
        """, (set_id,))
        ds = cur.fetchone()
        if not ds:
            return None
        result = dict(ds)
        cur.execute("""
            SELECT * FROM ops.yango_loyalty_metric_rules
            WHERE definition_set_id = %s ORDER BY metric_key
        """, (set_id,))
        result["rules"] = [dict(r) for r in cur.fetchall()]
        return result


def preview_all_sets(month_str: str = "2026-04", country: str = "PE", city: str = "lima") -> dict:
    month_start = date(int(month_str.split("-")[0]), int(month_str.split("-")[1]), 1)
    results = {"month": month_str, "country": country, "city": city, "previews": []}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT * FROM ops.yango_loyalty_official_reconciliation_reference
            WHERE month_start = %s AND country = %s AND city_norm = %s
        """, (month_str, country, city))
        refs = {r["metric_key"]: {"value": float(r["official_value"]), "target": float(r["official_target_value"] or 0)}
                for r in cur.fetchall()}

        cur.execute("SELECT definition_set_id FROM ops.yango_loyalty_metric_definition_sets ORDER BY definition_set_id")
        sets = [r["definition_set_id"] for r in cur.fetchall()]

        for ds_id in sets:
            cur.execute("""
                SELECT * FROM ops.yango_loyalty_metric_rules
                WHERE definition_set_id = %s ORDER BY metric_key
            """, (ds_id,))
            rules_list = [dict(r) for r in cur.fetchall()]
            preview = _preview_one_set(cur, ds_id, month_start, rules_list, refs)
            results["previews"].append(preview)

    return results


def get_operational_flow(month_str: str = "2026-04", country: str = "PE", city: str = "lima") -> dict:
    """Read YEGO Operational Flow from serving fact v2."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Serving fact v2 exists after migration 160 — query directly
        cur.execute("""
            SELECT * FROM ops.fct_yego_operational_flow_monthly_v2
            WHERE month_start = %(ms)s AND country = %(co)s AND city_norm = %(ci)s
            LIMIT 1
        """, {"ms": f"{month_str}-01", "co": country, "ci": city})
        row = cur.fetchone()

        if row:
            return {
                "scope": {"mode": "pilot", "city_norm": "lima",
                          "metric_universe": "yego_operational", "official_comparable": False},
                "summary": {
                        "yego_new_drivers": int(row["yego_new_drivers"]),
                        "yego_reactivated_drivers": int(row["yego_reactivated_drivers"]),
                        "yego_existing_active_drivers": int(row["yego_existing_active_drivers"]),
                        "yego_operational_new_plus_reactivated": int(row["yego_operational_new_plus_reactivated"]),
                        "false_new_drivers_detected": int(row["false_new_drivers_detected"]),
                        "reclassified_new_to_existing_or_reactivated": int(row["reclassified_new_to_existing_or_reactivated"]),
                        "vintage_risk_count": int(row["vintage_risk_count"]),
                        "vintage_risk_pct": float(row["vintage_risk_pct"] or 0),
                        "inactivity_window_days": int(row["inactivity_window_days"]),
                        "source_confidence": row["source_confidence"],
                        "coverage_status": row["coverage_status"],
                        "serving_source": "serving_fact_v2",
                    },
                    "historical_enrichment": {
                        "enabled": True,
                        "historical_sources": ["trips_2025", "trips_2026"],
                        "primary_current_source": "fleet_summary",
                        "rule": "trips only enrich historical presence, not current activity",
                    },
                    "scoring": {
                        "official_yango_scoring_status": "blocked_pending_yango_definition_validation",
                        "internal_metric_usage": "management_only",
                    },
                    "remediation": [
                        {"type": "internal_metric",
                         "message": "Indicador de gestion interna. No usar para scoring oficial Yango."},
                ],
            }

        # Fallback: compute live
        return _compute_operational_flow_live(month_str, country, city)


def _compute_operational_flow_live(month_str, country, city):
    """Fallback: compute operational flow live if serving fact is unavailable."""
    from datetime import timedelta
    month_start = date(int(month_str.split("-")[0]), int(month_str.split("-")[1]), 1)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        inactivity_days = 30
        cut = month_start - timedelta(days=inactivity_days)

        cur.execute("""SELECT COUNT(DISTINCT driver_id)::int FROM public.module_ct_fleet_summary_daily
                       WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date AND work_time_hours > 0""", {"ms": month_start})
        active = cur.fetchone()

        cur.execute("""WITH first_sh AS (SELECT driver_id, MIN(fecha) as d FROM public.module_ct_fleet_summary_daily WHERE work_time_hours > 0 GROUP BY driver_id)
                       SELECT COUNT(*)::int FROM first_sh WHERE d >= %(ms)s AND d < (%(ms)s + interval '1 month')::date""", {"ms": month_start})
        new_d = cur.fetchone()['count']

        cur.execute("""WITH cur AS (SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date AND work_time_hours > 0),
                       hist AS (SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily WHERE fecha < %(ms)s AND work_time_hours > 0),
                       recent AS (SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily WHERE fecha >= %(cut)s AND fecha < %(ms)s AND work_time_hours > 0)
                       SELECT COUNT(DISTINCT c.driver_id)::int FROM cur c JOIN hist h ON h.driver_id=c.driver_id WHERE c.driver_id NOT IN (SELECT driver_id FROM recent)""", {"ms": month_start, "cut": cut})
        rea_d = cur.fetchone()['count']

        return {"scope": {"mode": "pilot", "city_norm": "lima", "metric_universe": "yego_operational", "official_comparable": False},
                "summary": {"yego_new_drivers": new_d, "yego_reactivated_drivers": rea_d, "yego_operational_new_plus_reactivated": new_d+rea_d,
                            "false_new_drivers_detected": 0, "inactivity_window_days": 30, "serving_source": "runtime_fallback"},
                "scoring": {"official_yango_scoring_status": "blocked_pending_yango_definition_validation", "internal_metric_usage": "management_only"},
                "remediation": [{"type":"runtime_fallback","message":"Serving fact no disponible. Calculo runtime (menos preciso)."}]}


def get_validation_pack(month_str: str = "2026-04", country: str = "PE", city: str = "lima") -> dict:
    preview = preview_all_sets(month_str, country, city)

    questions = [
        "Active Driver: viaje completado, supply hours > 0, conexion, lifecycle o registro?",
        "Universo de drivers: solo Auto regular o incluye Delivery/TukTuk/Carga/YMA/PRO?",
        "Nuevo: primer viaje historico, primera conexion, registro aprobado, o incorporacion al partner?",
        "Reactivado: cuantos dias de inactividad? Se mide por viajes o conexion?",
        "Fuente oficial del reporte: trips, fleet_summary, lifecycle o reporte KAM?",
        "La fuente esta disponible como tabla consultable en DB?",
    ]

    risks = [
        "N+R definicion inflada +176% en hybrid_ct_default",
        "SH cobertura 87% — fleet_summary no cubre todos los drivers Lima",
        "Preview runtime ~10s — requiere serving fact para UI publica",
        "Todas las definiciones N+R son provisionales — no validadas por Yango",
    ]

    return {
        "month": month_str,
        "country": country,
        "city": city,
        "yango_reference": preview.get("previews", [{}])[0].get("ad_reference") is not None,
        "previews": preview["previews"],
        "best_candidate": "hybrid_ct_default",
        "risks": risks,
        "pending_questions": questions,
        "recommendation": "Validar definiciones N+R con Yango antes de activar scoring. AD y SH son confiables.",
        "scoring_allowed": False,
        "next_step": "Enviar validation pack a Yango. Una vez respondido, activar definition set y cargar metas.",
    }


def _preview_one_set(cur, ds_id: str, month_start: date, rules: list[dict], refs: dict) -> dict:
    ad, sh, new_d, rea_d = 0, 0, 0, 0
    statuses = []
    confidences = []

    for r in rules:
        mk = r["metric_key"]
        if mk == "active_drivers":
            ad = _calc_ad(cur, r, month_start)
        elif mk == "supply_hours":
            sh = _calc_sh(cur, r, month_start)
        elif mk == "new_drivers":
            new_d = _calc_new(cur, r, month_start)
        elif mk == "reactivated_drivers":
            rea_d = _calc_rea(cur, r, month_start)
        statuses.append(r["definition_status"])
        confidences.append(r["source_confidence"])

    nr = new_d + rea_d

    def _drift(val, ref_key):
        if ref_key in refs and val > 0:
            return round(abs(val - refs[ref_key]["value"]) / refs[ref_key]["value"] * 100, 1)
        return None

    ad_drift = _drift(ad, "active_drivers")
    sh_drift = _drift(sh, "supply_hours")
    nr_drift = _drift(nr, "new_plus_reactivated")

    max_drift = max(filter(None, [ad_drift or 0, sh_drift or 0, nr_drift or 0]))
    if any(s == "blocked" for s in statuses):
        validation = "blocked"
    elif max_drift <= 5:
        validation = "passed" if max_drift > 0 else "pending"
    elif max_drift <= 10:
        validation = "warning"
    else:
        validation = "blocked"

    return {
        "definition_set_id": ds_id,
        "active_drivers": ad,
        "supply_hours": round(sh, 1),
        "new_drivers": new_d,
        "reactivated_drivers": rea_d,
        "new_plus_reactivated": nr,
        "ad_reference": refs.get("active_drivers", {}).get("value"),
        "sh_reference": refs.get("supply_hours", {}).get("value"),
        "nr_reference": refs.get("new_plus_reactivated", {}).get("value"),
        "ad_diff_pct": ad_drift,
        "sh_diff_pct": sh_drift,
        "nr_diff_pct": nr_drift,
        "validation_status": validation,
        "definition_status": "provisional" if any(s != "final" for s in statuses) else "final",
        "source_confidence": "high" if all(c == "high" for c in confidences) else "medium" if all(c in ("high", "medium") for c in confidences) else "mixed",
    }


def _calc_ad(cur, rule: dict, ms: date) -> int:
    sk = rule["source_key"]
    if sk == "real_business_slice_month":
        cur.execute("""
            SELECT COALESCE(SUM(active_drivers), 0)::int as ad
            FROM ops.real_business_slice_month_fact
            WHERE month = %s AND country = 'peru' AND city = 'lima'
              AND business_slice_name = 'Auto regular'
        """, (ms,))
    elif sk in ("fleet_summary_daily", "fleet_summary_daily_active"):
        cur.execute("""
            SELECT COUNT(DISTINCT driver_id)::int as ad
            FROM public.module_ct_fleet_summary_daily
            WHERE fecha >= %s AND fecha < (%s + interval '1 month')::date
              AND count_orders_completed > 0
        """, (ms, ms))
    else:
        return 0
    r = cur.fetchone()
    return r["ad"] if r else 0


def _calc_sh(cur, rule: dict, ms: date) -> float:
    cur.execute("""
        SELECT COALESCE(SUM(work_time_hours), 0) as sh
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= %s AND fecha < (%s + interval '1 month')::date
    """, (ms, ms))
    r = cur.fetchone()
    return float(r["sh"]) if r else 0


def _calc_new(cur, rule: dict, ms: date) -> int:
    sk = rule["source_key"]
    signal = rule.get("activity_signal", "")
    if "fleet" in (sk or "") and "completed_trip" in (signal or ""):
        cur.execute("""
            WITH fleet_d AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %s AND fecha < (%s + interval '1 month')::date
                  AND count_orders_completed > 0
            ),
            first_trip AS (
                SELECT conductor_id, MIN(fecha_inicio_viaje::date) as ft
                FROM public.trips_2026 WHERE condicion = 'Completado'
                GROUP BY conductor_id
            )
            SELECT COUNT(*)::int FROM first_trip ft
            JOIN fleet_d fd ON fd.driver_id = ft.conductor_id
            WHERE ft.ft >= %s AND ft.ft < (%s + interval '1 month')::date
        """, (ms, ms, ms, ms))
        r = cur.fetchone()
        return r["count"] if r else 0

    if "fleet" in (sk or ""):
        cur.execute("""
            SELECT COUNT(DISTINCT driver_id)::int FROM public.module_ct_fleet_summary_daily
            WHERE fecha >= %s AND fecha < (%s + interval '1 month')::date
              AND driver_id NOT IN (
                  SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                  WHERE fecha < %s)
        """, (ms, ms, ms))
        r = cur.fetchone()
        return r["count"] if r else 0

    # trips-based
    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park WHERE city = 'lima' AND country = 'peru'
        ),
        first_trip AS (
            SELECT t.conductor_id, MIN(t.fecha_inicio_viaje::date) as ft
            FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
            GROUP BY t.conductor_id
            UNION ALL
            SELECT t.conductor_id, MIN(t.fecha_inicio_viaje::date) as ft
            FROM public.trips_2025 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
            GROUP BY t.conductor_id
        )
        SELECT COUNT(*)::int FROM (
            SELECT DISTINCT conductor_id, MIN(ft) as min_ft FROM first_trip GROUP BY conductor_id
        ) sq WHERE min_ft >= %s AND min_ft < (%s + interval '1 month')::date
    """, (ms, ms))
    r = cur.fetchone()
    return r["count"] if r else 0


def _calc_rea(cur, rule: dict, ms: date) -> int:
    inactive_days = rule.get("inactive_days") or 30
    cutoff = f"{ms}"  # month_start as date string for direct SQL use
    from datetime import timedelta
    rc = ms - timedelta(days=inactive_days)
    sk = rule["source_key"]
    signal = rule.get("activity_signal", "")

    if "fleet" in (sk or "") and "completed" in (signal or ""):
        cur.execute("""
            WITH fleet_current AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %s AND fecha < (%s + interval '1 month')::date
                  AND count_orders_completed > 0
            ),
            fleet_before AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha < %s AND count_orders_completed > 0
            ),
            trips_active AS (
                SELECT DISTINCT conductor_id FROM public.trips_2026
                WHERE condicion = 'Completado'
                  AND fecha_inicio_viaje >= %s AND fecha_inicio_viaje < (%s + interval '1 month')::date
            ),
            last_trip_before AS (
                SELECT conductor_id, MAX(fecha_inicio_viaje::date) as lt
                FROM public.trips_2026 WHERE condicion = 'Completado' AND fecha_inicio_viaje < %s
                GROUP BY conductor_id
            )
            SELECT COUNT(DISTINCT fc.driver_id)::int FROM fleet_current fc
            WHERE fc.driver_id IN (SELECT conductor_id FROM trips_active)
              AND fc.driver_id IN (SELECT driver_id FROM fleet_before)
              AND EXISTS (
                  SELECT 1 FROM last_trip_before ltb
                  WHERE ltb.conductor_id = fc.driver_id AND ltb.lt < %s)
        """, (ms, ms, ms, ms, ms, ms, rc))
        r = cur.fetchone()
        return r["count"] if r else 0

    if "fleet" in (sk or ""):
        cur.execute("""
            WITH fleet_current AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date
            ),
            fleet_prev AS (
                SELECT DISTINCT driver_id FROM public.module_ct_fleet_summary_daily
                WHERE fecha >= %(cut)s AND fecha < %(ms)s
            )
            SELECT COUNT(*)::int FROM fleet_current WHERE driver_id NOT IN (SELECT driver_id FROM fleet_prev)
        """, {"ms": ms, "cut": ms - timedelta(days=inactive_days)})
        r = cur.fetchone()
        return r["count"] if r else 0

    # trips-based
    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park WHERE city = 'lima' AND country = 'peru'
        ),
        active AS (
            SELECT DISTINCT t.conductor_id FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje >= %s AND t.fecha_inicio_viaje < (%s + interval '1 month')::date
        ),
        last AS (
            SELECT t.conductor_id, MAX(t.fecha_inicio_viaje::date) as lt FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje < %s
            GROUP BY t.conductor_id
        )
        SELECT COUNT(*)::int FROM active a
        JOIN last l ON l.conductor_id = a.conductor_id
        WHERE l.lt < %s
    """, (ms, ms, ms, rc))
    r = cur.fetchone()
    return r["count"] if r else 0
