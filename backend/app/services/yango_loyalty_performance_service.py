"""
Yango Loyalty Performance Service ÔÇö Lima-Only Pilot
Control Foundation Hardening / Phase 1H.4

PILOT SCOPE: Lima only.
Metrics: AD, Supply Hours, Nuevos + Reactivados (N+R).

Sources:
  AD: ops.real_business_slice_month_fact (Auto regular only, matching Yango definition)
  SH: public.module_ct_fleet_summary_daily (ALL rows -> forced to Lima)
  N+R: Derived from trips history, filtered to fleet_summary driver universe

Scoring guardrails:
  - AD drift vs Yango ref >5%  -> blocked_pending_reconciliation
  - SH drift vs Yango ref >5%  -> blocked_pending_reconciliation
  - N+R drift vs Yango ref >10% -> blocked_pending_reconciliation
  - N+R provisional definition  -> blocked_pending_reconciliation
  - N+R runtime >5s             -> blocked_pending_reconciliation

NO Forecast. NO Suggestion. NO Decision. NO Action. NO AI.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 60000

PILOT_SCOPE = "lima_only"
PILOT_COUNTRY = "PE"
PILOT_CITY_NORM = "lima"
SOURCE_TABLE = "public.module_ct_fleet_summary_daily"
SOURCE_SCOPE_REASON = "fleet_summary_confirmed_lima_only"

UNSUPPORTED_CITIES = ["trujillo", "arequipa"]

NR_SOURCE = "derived_from_fleet_scope_trips"
NR_DEFINITION_STATUS = "provisional_pending_business_validation"
NR_SOURCE_CONFIDENCE = "medium_derived_from_trip_history"
NR_REACTIVATION_WINDOW_DAYS = 30

# Yango official reference values ÔÇö used for guardrail drift detection, NOT as targets
REF_AD_YANGO = 5601
REF_SH_YANGO = 357000
REF_NR_YANGO = 1064

GUARDRAIL_AD_DRIFT_PCT = 5
GUARDRAIL_SH_DRIFT_PCT = 5
GUARDRAIL_NR_DRIFT_PCT = 10


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(timeout_ms),))
    return c


def get_loyalty_performance(
    month: Optional[str] = None,
    country: str = "peru",
    city: Optional[str] = None,
    include_missing_targets: bool = True,
) -> dict[str, Any]:
    today = date.today()
    if month:
        try:
            parts = month.split("-")
            month_start = date(int(parts[0]), int(parts[1]), 1)
        except (ValueError, IndexError):
            month_start = date(today.year, today.month, 1)
    else:
        month_start = date(today.year, today.month, 1)

    month_str = month_start.strftime("%Y-%m")
    total_days = calendar.monthrange(month_start.year, month_start.month)[1]

    city_requested = city.lower().strip() if city else None

    if city_requested and city_requested in UNSUPPORTED_CITIES:
        return _unsupported_city_response(month_str, country, city_requested)

    try:
        with get_db() as conn:
            cur = _cursor(conn)

            lima_data = _fetch_lima_performance(cur, month_start)
            nr_data = _fetch_nr_lazy_stub(month_start)
            targets_data = _fetch_targets(cur, month_str)
            freshness = _compute_freshness(lima_data, today)

            city_result = _build_lima_city(lima_data, nr_data, targets_data,
                                           month_start, total_days, today)
            summary = _build_summary(city_result, nr_data, targets_data)
            target_status = _compute_target_status(targets_data)
            scoring = _compute_scoring(city_result, nr_data, targets_data)
            remediation = _build_remediation(target_status, freshness, scoring, nr_data)

            if city_result:
                city_result["scoring_status"] = scoring["scoring_status"]
                city_result["performance_goals_completed"] = scoring["performance_goals_completed"]
                city_result["performance_category"] = scoring["performance_category"]
                city_result["guardrail_flags"] = scoring.get("guardrail_flags", [])

            reconciliation = {
                "status": "pending" if scoring["scoring_status"] == "blocked_pending_reconciliation" else "ok",
                "ad_current": city_result["active_drivers_mtd"] if city_result else 0,
                "ad_reference": REF_AD_YANGO,
                "ad_drift_pct": round(abs((city_result["active_drivers_mtd"] - REF_AD_YANGO) / REF_AD_YANGO * 100), 1) if city_result else 0,
                "sh_current": round(city_result["supply_hours_mtd"]) if city_result else 0,
                "sh_reference": REF_SH_YANGO,
                "sh_drift_pct": round(abs((city_result["supply_hours_mtd"] - REF_SH_YANGO) / REF_SH_YANGO * 100), 1) if city_result else 0,
                "nr_current": city_result["new_plus_reactivated_mtd"] if city_result else 0,
                "nr_reference": REF_NR_YANGO,
                "nr_drift_pct": round(abs((city_result["new_plus_reactivated_mtd"] - REF_NR_YANGO) / REF_NR_YANGO * 100), 1) if city_result and city_result["new_plus_reactivated_mtd"] > 0 else 0,
                "guardrail_flags": scoring.get("guardrail_flags", []),
            }

            unsupported = [
                {"city_norm": c, "data_status": "not_available", "reason": "source_pending_enrichment"}
                for c in UNSUPPORTED_CITIES
            ]

            return {
                "month": month_str,
                "country": country,
                "data_until": freshness["data_until"],
                "freshness_status": freshness["status"],
                "target_status": target_status,
                "scoring_status": scoring["scoring_status"],
                "reconciliation": reconciliation,
                "scope": {
                    "mode": "pilot",
                    "pilot_scope": PILOT_SCOPE,
                    "country": PILOT_COUNTRY,
                    "city_norm": PILOT_CITY_NORM,
                    "source_table": SOURCE_TABLE,
                    "source_scope_reason": SOURCE_SCOPE_REASON,
                },
                "summary": summary,
                "cities": [city_result] if city_result else [],
                "unsupported_cities": unsupported,
                "remediation": remediation,
            }
    except Exception as e:
        logger.exception("yango_loyalty_performance: %s", e)
        return _error_response(month_str, country, str(e))


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Response builders
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _unsupported_city_response(month_str: str, country: str, city_norm: str) -> dict:
    return {
        "month": month_str, "country": country, "data_until": None,
        "freshness_status": "not_available", "target_status": "not_available",
        "scoring_status": "blocked_source_pending",
        "scope": {
            "mode": "pilot", "pilot_scope": PILOT_SCOPE,
            "country": PILOT_COUNTRY, "city_norm": PILOT_CITY_NORM,
            "source_table": SOURCE_TABLE, "source_scope_reason": SOURCE_SCOPE_REASON,
        },
        "summary": _empty_summary(with_nr=True),
        "cities": [{"city_norm": city_norm, "active_drivers_mtd": 0, "supply_hours_mtd": 0,
                     "new_drivers_mtd": 0, "reactivated_drivers_mtd": 0,
                     "new_plus_reactivated_mtd": 0, "data_status": "not_available",
                     "reason": "source_pending_enrichment",
                     "city_assignment_method": "not_in_pilot"}],
        "unsupported_cities": [{"city_norm": city_norm, "data_status": "not_available", "reason": "source_pending_enrichment"}],
        "remediation": [{"type": "unsupported_city",
                          "message": f"Fuente actual solo habilitada para Lima. Enriquecer tabla para activar {city_norm}."}],
    }


def _error_response(month_str: str, country: str, error_msg: str) -> dict:
    return {
        "month": month_str, "country": country, "data_until": None,
        "freshness_status": "error", "target_status": "error",
        "scoring_status": "blocked_error",
        "scope": {
            "mode": "pilot", "pilot_scope": PILOT_SCOPE,
            "country": PILOT_COUNTRY, "city_norm": PILOT_CITY_NORM,
            "source_table": SOURCE_TABLE, "source_scope_reason": SOURCE_SCOPE_REASON,
        },
        "summary": _empty_summary(with_nr=True),
        "cities": [], "unsupported_cities": [],
        "remediation": [{"type": "error", "message": f"Error: {error_msg[:200]}"}],
    }


def _empty_summary(with_nr: bool = False) -> dict:
    s = {
        "active_drivers_mtd": 0, "supply_hours_mtd": 0,
        "target_active_drivers": None, "target_supply_hours": None,
        "gap_active_drivers_vs_target": None, "gap_supply_hours_vs_target": None,
        "projected_supply_hours_eom": None,
        "performance_goals_completed": 0, "performance_category": None,
    }
    if with_nr:
        s.update({
            "new_drivers_mtd": 0, "reactivated_drivers_mtd": 0,
            "new_plus_reactivated_mtd": 0, "target_new_plus_reactivated": None,
            "gap_new_plus_reactivated_vs_target": None,
            "nr_source": None, "nr_definition_status": "not_available",
            "nr_source_confidence": None,
        })
    return s


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Data fetchers
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _fetch_lima_performance(cur, month_start: date) -> dict:
    cur.execute("""
        SELECT
            COUNT(DISTINCT driver_id) FILTER (WHERE count_orders_completed > 0) AS ad_fleet_summary,
            SUM(work_time_hours) AS supply_hours_mtd,
            MAX(fecha) AS data_until,
            COUNT(DISTINCT fecha) AS days_with_data
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date
    """, {"ms": month_start})
    sh_row = cur.fetchone()

    cur.execute("""
        SELECT SUM(active_drivers) AS active_drivers_mtd
        FROM ops.real_business_slice_month_fact
        WHERE month = %(ms)s AND country = 'peru' AND city = 'lima'
          AND business_slice_name = 'Auto regular'
    """, {"ms": month_start})
    ad_row = cur.fetchone()

    return {
        "active_drivers_mtd": int(ad_row["active_drivers_mtd"] or 0) if ad_row else 0,
        "supply_hours_mtd": float(sh_row["supply_hours_mtd"] or 0) if sh_row else 0,
        "data_until": sh_row["data_until"] if sh_row else None,
        "days_with_data": int(sh_row["days_with_data"] or 0) if sh_row else 0,
        "ad_fleet_summary": int(sh_row["ad_fleet_summary"] or 0) if sh_row else 0,
    }


def _fetch_nr_lazy_stub(month_start: date) -> dict:
    """Fast stub ÔÇö N+R is loaded lazily from operational-flow endpoint (serving fact v2)."""
    return {
        "new_drivers_mtd": 0,
        "reactivated_drivers_mtd": 0,
        "new_plus_reactivated_mtd": 0,
        "nr_source": "lazy_loaded_from_operational_flow_endpoint",
        "nr_definition_status": "lazy_cached",
        "nr_source_confidence": "lazy",
        "reactivation_window_days": 30,
    }


def _fetch_nr_lima_heavy(cur, month_start: date) -> dict:
    month_end = date(month_start.year, month_start.month,
                     calendar.monthrange(month_start.year, month_start.month)[1])
    reactivation_cutoff = month_start - timedelta(days=NR_REACTIVATION_WINDOW_DAYS)

    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park
            WHERE city = 'lima' AND country = 'peru'
        ),
        fleet_drivers AS (
            SELECT DISTINCT driver_id
            FROM public.module_ct_fleet_summary_daily
            WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date
        ),
        all_trips_history AS (
            SELECT t.conductor_id, t.fecha_inicio_viaje::date as trip_date
            FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
            UNION ALL
            SELECT t.conductor_id, t.fecha_inicio_viaje::date
            FROM public.trips_2025 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
        ),
        driver_first_trip AS (
            SELECT conductor_id, MIN(trip_date) as first_trip
            FROM all_trips_history
            WHERE conductor_id IN (SELECT driver_id FROM fleet_drivers)
            GROUP BY conductor_id
        ),
        active_current_month AS (
            SELECT DISTINCT t.conductor_id
            FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje >= %(ms)s AND t.fecha_inicio_viaje < %(me)s
              AND t.conductor_id IN (SELECT driver_id FROM fleet_drivers)
        ),
        last_activity_before_window AS (
            SELECT t.conductor_id, MAX(t.fecha_inicio_viaje::date) as last_trip
            FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje < %(ms)s
              AND t.conductor_id IN (SELECT driver_id FROM fleet_drivers)
            GROUP BY t.conductor_id
        )
        SELECT
            COUNT(*)::int as total_active,
            COUNT(*) FILTER (
                WHERE f.first_trip >= %(ms)s AND f.first_trip < %(me)s
            )::int as new_drivers,
            COUNT(*) FILTER (
                WHERE f.first_trip < %(ms)s
                  AND (l.last_trip IS NULL OR l.last_trip < %(rc)s)
            )::int as reactivated_drivers
        FROM active_current_month a
        LEFT JOIN driver_first_trip f ON f.conductor_id = a.conductor_id
        LEFT JOIN last_activity_before_window l ON l.conductor_id = a.conductor_id
    """, {"ms": month_start, "me": month_end, "rc": reactivation_cutoff})
    nr_row = cur.fetchone()

    new_d = nr_row["new_drivers"] if nr_row else 0
    rea_d = nr_row["reactivated_drivers"] if nr_row else 0

    return {
        "new_drivers_mtd": new_d,
        "reactivated_drivers_mtd": rea_d,
        "new_plus_reactivated_mtd": new_d + rea_d,
        "nr_source": NR_SOURCE,
        "nr_definition_status": NR_DEFINITION_STATUS,
        "nr_source_confidence": NR_SOURCE_CONFIDENCE,
        "reactivation_window_days": NR_REACTIVATION_WINDOW_DAYS,
    }


def _fetch_targets(cur, month_str: str) -> dict:
    targets: dict = {}
    try:
        cur.execute("""
            SELECT kpi_code, target_value
            FROM ops.yango_loyalty_monthly_goals
            WHERE month = %(m)s AND LOWER(city) = 'lima'
              AND kpi_code IN ('AD', 'SH', 'N_R')
        """, {"m": month_str})
        for row in cur.fetchall():
            targets[row["kpi_code"]] = float(row["target_value"])
    except Exception as e:
        logger.warning("Targets from yango_loyalty_monthly_goals: %s", e)
        try:
            cur.execute("""
                SELECT kpi_key, target_value FROM ops.yango_loyalty_targets
                WHERE month_key = %(m)s AND LOWER(city) = 'lima'
                  AND kpi_key IN ('ad', 'supply_hours', 'nuevos_reactivados')
            """, {"m": month_str})
            for row in cur.fetchall():
                m = {"ad": "AD", "supply_hours": "SH", "nuevos_reactivados": "N_R"}.get(row["kpi_key"])
                if m:
                    targets[m] = float(row["target_value"])
        except Exception:
            pass
    return targets


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Freshness
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _compute_freshness(lima_data: dict, today: date) -> dict:
    data_until = lima_data.get("data_until")
    if not data_until:
        return {"data_until": None, "status": "no_data"}
    if isinstance(data_until, datetime):
        data_until = data_until.date()
    yesterday = today - timedelta(days=1)
    status = "ok" if data_until >= yesterday else "warning" if (today - data_until).days <= 3 else "stale"
    return {"data_until": data_until.isoformat(), "status": status}


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# City response builder
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _build_lima_city(lima_data: dict, nr_data: dict, targets: dict,
                     month_start: date, total_days: int, today: date) -> Optional[dict]:
    ad_mtd = lima_data["active_drivers_mtd"]
    sh_mtd = lima_data["supply_hours_mtd"]
    new_mtd = nr_data["new_drivers_mtd"]
    rea_mtd = nr_data["reactivated_drivers_mtd"]
    nr_mtd = nr_data["new_plus_reactivated_mtd"]

    if ad_mtd == 0 and sh_mtd == 0:
        return None

    data_until = lima_data.get("data_until")
    if data_until:
        if isinstance(data_until, datetime):
            data_until = data_until.date()
        days_elapsed = (data_until - month_start).days + 1
    else:
        days_elapsed = (today - month_start).days if today.year == month_start.year and today.month == month_start.month else total_days
    days_elapsed = max(1, min(days_elapsed, total_days))
    expected_pct = round(days_elapsed / total_days, 4)

    t_ad = targets.get("AD")
    t_sh = targets.get("SH")
    t_nr = targets.get("N_R")

    expected_sh = round(t_sh * expected_pct, 1) if t_sh else None
    gap_ad = round(ad_mtd - t_ad, 0) if t_ad else None
    gap_sh = round(sh_mtd - t_sh, 1) if t_sh else None
    gap_sh_e = round(sh_mtd - expected_sh, 1) if expected_sh else None
    gap_nr = round(nr_mtd - t_nr, 0) if t_nr else None

    proj_sh = round(sh_mtd / expected_pct, 0) if expected_pct > 0 and sh_mtd > 0 else None

    has_targets = t_ad is not None or t_sh is not None or t_nr is not None

    return {
        "city_norm": "lima",
        "active_drivers_mtd": ad_mtd,
        "supply_hours_mtd": round(sh_mtd, 1),
        "new_drivers_mtd": new_mtd,
        "reactivated_drivers_mtd": rea_mtd,
        "new_plus_reactivated_mtd": nr_mtd,
        "target_active_drivers": t_ad,
        "target_supply_hours": t_sh,
        "target_new_plus_reactivated": t_nr,
        "expected_progress_pct": expected_pct,
        "expected_supply_hours_to_date": expected_sh,
        "gap_active_drivers_vs_target": gap_ad,
        "gap_supply_hours_vs_target": gap_sh,
        "gap_supply_hours_vs_expected": gap_sh_e,
        "gap_new_plus_reactivated_vs_target": gap_nr,
        "projected_supply_hours_eom": proj_sh,
        "nr_source": nr_data["nr_source"],
        "nr_definition_status": nr_data["nr_definition_status"],
        "nr_source_confidence": nr_data["nr_source_confidence"],
        "target_status": "configured" if has_targets else "missing_targets",
        "data_status": "ok",
        "city_assignment_method": "forced_lima_pilot",
        "city_assignment_confidence": "high_for_lima_only_source",
        "city_assignment_warning": None,
    }


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Summary builder
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _build_summary(city_result: Optional[dict], nr_data: dict, targets: dict) -> dict:
    if not city_result:
        return _empty_summary(with_nr=True)

    return {
        "active_drivers_mtd": city_result["active_drivers_mtd"],
        "supply_hours_mtd": city_result["supply_hours_mtd"],
        "new_drivers_mtd": city_result["new_drivers_mtd"],
        "reactivated_drivers_mtd": city_result["reactivated_drivers_mtd"],
        "new_plus_reactivated_mtd": city_result["new_plus_reactivated_mtd"],
        "target_active_drivers": city_result["target_active_drivers"],
        "target_supply_hours": city_result["target_supply_hours"],
        "target_new_plus_reactivated": city_result["target_new_plus_reactivated"],
        "gap_active_drivers_vs_target": city_result["gap_active_drivers_vs_target"],
        "gap_supply_hours_vs_target": city_result["gap_supply_hours_vs_target"],
        "gap_new_plus_reactivated_vs_target": city_result["gap_new_plus_reactivated_vs_target"],
        "projected_supply_hours_eom": city_result["projected_supply_hours_eom"],
        "nr_source": nr_data["nr_source"],
        "nr_definition_status": nr_data["nr_definition_status"],
        "nr_source_confidence": nr_data["nr_source_confidence"],
        "performance_goals_completed": 0,
        "performance_category": None,
        "scoring_status": "blocked_missing_targets",
    }


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Targets & Scoring
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _compute_target_status(targets: dict) -> str:
    has_ad = "AD" in targets
    has_sh = "SH" in targets
    has_nr = "N_R" in targets
    if has_ad and has_sh and has_nr:
        return "configured"
    if has_ad or has_sh or has_nr:
        return "partial"
    return "missing_targets"


def _compute_scoring(city_result: Optional[dict], nr_data: dict, targets: dict) -> dict:
    results = {
        "scoring_status": "blocked_missing_targets",
        "performance_goals_completed": 0,
        "performance_category": None,
    }

    if not city_result:
        return results

    # Guardrail: check drift vs Yango reference
    ad_val = city_result.get("active_drivers_mtd", 0)
    sh_val = city_result.get("supply_hours_mtd", 0)
    nr_val = city_result.get("new_plus_reactivated_mtd", 0)

    ad_drift = abs(ad_val - REF_AD_YANGO) / REF_AD_YANGO * 100 if REF_AD_YANGO else 0
    sh_drift = abs(sh_val - REF_SH_YANGO) / REF_SH_YANGO * 100 if REF_SH_YANGO else 0
    nr_drift = abs(nr_val - REF_NR_YANGO) / REF_NR_YANGO * 100 if REF_NR_YANGO else 0

    guardrail_blocks = []
    if ad_drift > GUARDRAIL_AD_DRIFT_PCT:
        guardrail_blocks.append(f"AD_drift_{ad_drift:.0f}pct")
    if sh_drift > GUARDRAIL_SH_DRIFT_PCT:
        guardrail_blocks.append(f"SH_drift_{sh_drift:.0f}pct")
    if nr_drift > GUARDRAIL_NR_DRIFT_PCT and nr_val > 0:
        guardrail_blocks.append(f"NR_drift_{nr_drift:.0f}pct")
    if nr_data.get("nr_definition_status") == "provisional_pending_business_validation":
        guardrail_blocks.append("NR_provisional_definition")
    if nr_val > 0:
        guardrail_blocks.append("NR_runtime_source_no_serving_fact")

    if guardrail_blocks:
        results["scoring_status"] = "blocked_pending_yango_definition_validation"
        results["guardrail_flags"] = guardrail_blocks
        return results

    t_ad = targets.get("AD")
    t_sh = targets.get("SH")
    t_nr = targets.get("N_R")

    if t_ad is None or t_sh is None or t_nr is None:
        results["scoring_status"] = "blocked_missing_targets"
        return results

    r_ad = ad_val
    r_sh = sh_val
    r_nr = nr_val

    if r_ad is None or r_sh is None or r_nr is None or (r_ad == 0 and r_sh == 0 and r_nr == 0):
        results["scoring_status"] = "blocked_missing_results"
        return results

    ad_met = (r_ad or 0) >= (t_ad or float('inf'))
    sh_met = (r_sh or 0) >= (t_sh or float('inf'))
    nr_met = (r_nr or 0) >= (t_nr or float('inf'))

    goals = sum([ad_met, sh_met, nr_met])
    cat = "oro" if goals >= 3 else "plata" if goals >= 2 else "bronce"

    return {
        "scoring_status": "enabled",
        "performance_goals_completed": goals,
        "performance_category": cat,
    }


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Remediation
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def _build_remediation(target_status: str, freshness: dict, scoring: dict, nr_data: dict) -> list[dict]:
    items = []

    if target_status == "missing_targets":
        items.append({
            "type": "missing_targets",
            "message": "Configura metas de AD, Supply Hours y N+R para Lima.",
        })
    elif target_status == "partial":
        items.append({
            "type": "partial_targets",
            "message": "Faltan metas. Configura AD, SH y N+R para desbloquear scoring.",
        })

    if nr_data["nr_definition_status"] == "provisional_pending_business_validation":
        items.append({
            "type": "nr_provisional",
            "message": f"N+R usa definicion provisional (reactivacion: {NR_REACTIVATION_WINDOW_DAYS}d inactividad). Pendiente validacion de negocio.",
        })

    if scoring["scoring_status"] == "enabled":
        items.append({
            "type": "scoring_active",
            "message": f"Scoring Performance Lima activo: {scoring['performance_goals_completed']}/3 metas ({scoring['performance_category'].capitalize()}).",
        })

    if freshness["status"] == "stale":
        items.append({"type": "stale_data",
                       "message": f"Datos desactualizados. Ultima fecha: {freshness['data_until']}."})
    elif freshness["status"] == "no_data":
        items.append({"type": "no_data",
                       "message": "Sin datos disponibles para este periodo."})

    return items


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Bootstrap ÔÇö ultra-lightweight initial render endpoint
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def get_loyalty_bootstrap() -> dict[str, Any]:
    """Ultra-lightweight endpoint for initial shell render (<1s).
    Reads only from fast serving facts in a single SQL round-trip.
    No trips. No preview. No MV refresh."""
    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_str = month_start.strftime("%Y-%m")
    total_days = calendar.monthrange(today.year, today.month)[1]

    result = {
        "scope": {
            "mode": "pilot",
            "country": PILOT_COUNTRY,
            "city_norm": PILOT_CITY_NORM,
            "lima_only": True,
        },
        "status": {
            "official_scoring_status": "blocked_pending_yango_definition_validation",
            "performance_category": None,
            "operational_flow_available": False,
            "performance_available": False,
        },
        "cards": {
            "active_drivers_mtd": None,
            "supply_hours_mtd": None,
            "yego_operational_new_plus_reactivated": None,
        },
        "month": month_str,
        "day_of_month": today.day,
        "total_days": total_days,
        "remediation": [],
    }

    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET LOCAL statement_timeout = '3000'")

            cur.execute("""
                SELECT
                    (SELECT COALESCE(SUM(active_drivers), 0)::int
                     FROM ops.real_business_slice_month_fact
                     WHERE month = %(ms)s AND country = 'peru' AND city = 'lima'
                       AND business_slice_name = 'Auto regular') AS ad,
                    (SELECT COALESCE(SUM(work_time_hours), 0)
                     FROM public.module_ct_fleet_summary_daily
                     WHERE fecha >= %(ms)s AND fecha < (%(ms)s + interval '1 month')::date) AS sh,
                    (SELECT yego_operational_new_plus_reactivated::int
                     FROM ops.fct_yego_operational_flow_monthly_v2
                     WHERE month_start = %(nr_ms)s AND country = 'PE' AND city_norm = 'lima'
                     LIMIT 1) AS nr
            """, {"ms": month_start, "nr_ms": f"{month_str}-01"})
            row = cur.fetchone()

            if row:
                ad_val = int(row["ad"]) if row["ad"] is not None else None
                sh_val = float(row["sh"]) if row["sh"] is not None else None
                nr_val = int(row["nr"]) if row["nr"] is not None else None

                if ad_val:
                    result["cards"]["active_drivers_mtd"] = ad_val
                    result["status"]["performance_available"] = True
                else:
                    result["remediation"].append({"type": "ad_unavailable", "message": "AD no disponible temporalmente."})

                if sh_val:
                    result["cards"]["supply_hours_mtd"] = round(sh_val, 1)
                else:
                    result["remediation"].append({"type": "sh_unavailable", "message": "Supply Hours no disponible temporalmente."})

                if nr_val:
                    result["cards"]["yego_operational_new_plus_reactivated"] = nr_val
                    result["status"]["operational_flow_available"] = True

    except Exception as e:
        logger.warning("bootstrap failed: %s", e)
        result["remediation"].append({"type": "connection_error", "message": "Conexion a base de datos no disponible."})

    return result


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Loyalty History ÔÇö multi-month serving-fact readout
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

HISTORY_TIMEOUT_MS = 3000


def _cursor_history(conn):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET LOCAL statement_timeout = %s", (str(HISTORY_TIMEOUT_MS),))
    return c


_COUNTRY_NORM_MAP = {"peru": "PE", "pe": "PE"}


def _build_history_month(conn, month_start: date, month_str: str, city_norm: str, country: str) -> dict:
    cur = _cursor_history(conn)

    metrics = {
        "active_drivers": {
            "actual_value": None,
            "target_value": None,
            "metric_universe": "official_yango_aligned",
            "source_confidence": "high",
            "status": "no_data",
        },
        "supply_hours": {
            "actual_value": None,
            "target_value": None,
            "metric_universe": "official_yango_aligned",
            "source_confidence": "high",
            "status": "no_data",
        },
        "operational_flow": {
            "actual_value": None,
            "target_value": None,
            "metric_universe": "yego_operational_internal",
            "source_confidence": "medium",
            "status": "no_data",
            "detail": {
                "new_drivers": None,
                "reactivated_drivers": None,
            },
        },
    }

    try:
        cur.execute("""
            SELECT
                COALESCE(active_drivers_mtd, 0)::int AS active_drivers,
                COALESCE(supply_hours_mtd, 0) AS supply_hours
            FROM ops.mv_yango_loyalty_performance_monthly_v1
            WHERE month_start = %(ms)s
              AND LOWER(country) = LOWER(%(co)s)
              AND LOWER(city_norm) = LOWER(%(ci)s)
            LIMIT 1
        """, {"ms": month_start, "co": country, "ci": city_norm})
        mv_row = cur.fetchone()
        if mv_row:
            if mv_row["active_drivers"] is not None:
                metrics["active_drivers"]["actual_value"] = int(mv_row["active_drivers"])
            if mv_row["supply_hours"] is not None:
                metrics["supply_hours"]["actual_value"] = float(mv_row["supply_hours"])
    except Exception:
        metrics["active_drivers"]["source_confidence"] = "error"
        metrics["supply_hours"]["source_confidence"] = "error"

    country_flow = _COUNTRY_NORM_MAP.get(country.lower(), country.upper())
    try:
        cur.execute("""
            SELECT
                COALESCE(yego_operational_new_plus_reactivated, 0)::int AS nr,
                COALESCE(yego_new_drivers, 0)::int AS new_d,
                COALESCE(yego_reactivated_drivers, 0)::int AS react_d
            FROM ops.fct_yego_operational_flow_monthly_v2
            WHERE month_start = %(ms)s
              AND country = %(co)s
              AND LOWER(city_norm) = LOWER(%(ci)s)
            LIMIT 1
        """, {"ms": month_start, "co": country_flow, "ci": city_norm})
        flow_row = cur.fetchone()
        if flow_row:
            nr_val = int(flow_row["nr"]) if flow_row["nr"] is not None else None
            if nr_val is not None:
                metrics["operational_flow"]["actual_value"] = nr_val
            if flow_row.get("new_d") is not None:
                metrics["operational_flow"]["detail"]["new_drivers"] = int(flow_row["new_d"])
            if flow_row.get("react_d") is not None:
                metrics["operational_flow"]["detail"]["reactivated_drivers"] = int(flow_row["react_d"])
    except Exception:
        metrics["operational_flow"]["source_confidence"] = "error"

    targets = {}
    try:
        cur.execute("""
            SELECT kpi_code, target_value
            FROM ops.yango_loyalty_monthly_goals
            WHERE month = %(m)s AND LOWER(city) = LOWER(%(ci)s)
              AND kpi_code IN ('AD', 'SH', 'N_R')
        """, {"m": month_str, "ci": city_norm})
        for row in cur.fetchall():
            targets[row["kpi_code"]] = float(row["target_value"])
    except Exception:
        pass

    t_ad = targets.get("AD")
    t_sh = targets.get("SH")
    t_nr = targets.get("N_R")

    metrics["active_drivers"]["target_value"] = t_ad
    metrics["supply_hours"]["target_value"] = t_sh
    metrics["operational_flow"]["target_value"] = t_nr

    _set_history_metric_status(metrics["active_drivers"])
    _set_history_metric_status(metrics["supply_hours"])
    _set_history_metric_status(metrics["operational_flow"])

    return {
        "month_start": month_start.isoformat(),
        "metrics": metrics,
    }


def _set_history_metric_status(metric: dict) -> None:
    if metric.get("source_confidence") == "error":
        metric["status"] = "no_data"
        return
    actual = metric.get("actual_value")
    if actual is None:
        metric["status"] = "no_data"
        return
    target = metric.get("target_value")
    if target is None:
        metric["status"] = "no_target"
        return
    if actual > target:
        metric["status"] = "above_target"
    elif actual < target:
        metric["status"] = "below_target"
    else:
        metric["status"] = "on_target"


def get_loyalty_history(
    months: int = 3,
    city: str = "lima",
    country: str = "peru",
) -> dict[str, Any]:
    today = date.today()
    current_month_start = date(today.year, today.month, 1)

    last_closed = date(current_month_start.year, current_month_start.month, 1) - timedelta(days=1)
    last_closed_start = date(last_closed.year, last_closed.month, 1)

    closed_months = []
    m = last_closed_start
    for _ in range(months):
        closed_months.append(m)
        m = date(m.year, m.month, 1) - timedelta(days=1)
        m = date(m.year, m.month, 1)

    city_norm = city.lower().strip()

    data = []
    try:
        with get_db() as conn:
            for month_start in closed_months:
                month_str = month_start.strftime("%Y-%m")
                month_data = _build_history_month(conn, month_start, month_str, city_norm, country)
                data.append(month_data)
    except Exception as e:
        logger.exception("get_loyalty_history: %s", e)

    return {
        "months_requested": months,
        "city": city_norm,
        "country": country,
        "data": data,
        "serving_sources": {
            "active_drivers": "ops.mv_yango_loyalty_performance_monthly_v1",
            "supply_hours": "ops.mv_yango_loyalty_performance_monthly_v1",
            "operational_flow": "ops.fct_yego_operational_flow_monthly_v2",
            "targets": "ops.yango_loyalty_monthly_goals",
        },
    }


# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ
# Loyalty City Comparison ÔÇö multi-city same-month readout
# ÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉÔòÉ

def get_loyalty_city_comparison(
    month: Optional[str] = None,
    country: str = "peru",
) -> dict[str, Any]:
    today = date.today()
    if month:
        try:
            parts = month.split("-")
            month_start = date(int(parts[0]), int(parts[1]), 1)
        except (ValueError, IndexError):
            month_start = date(today.year, today.month, 1)
    else:
        month_start = date(today.year, today.month, 1)

    month_str = month_start.strftime("%Y-%m")

    result = {
        "month": month_str,
        "country": country,
        "metrics": {
            "active_drivers": {
                "metric_universe": "official_yango_aligned",
                "source_confidence": "high",
                "supports_city_comparison": True,
                "cities": [],
            },
            "supply_hours": {
                "metric_universe": "official_yango_aligned",
                "source_confidence": "high",
                "supports_city_comparison": True,
                "cities": [],
            },
            "operational_flow": {
                "metric_universe": "yego_operational_internal",
                "source_confidence": "medium",
                "supports_city_comparison": False,
                "lima_only": True,
                "reason": "source_only_available_for_lima_pilot",
                "cities": [],
            },
        },
    }

    try:
        with get_db() as conn:
            cur = _cursor_history(conn)

            try:
                cur.execute("""
                    SELECT
                        LOWER(city_norm) AS city_norm,
                        COALESCE(active_drivers_mtd, 0)::int AS active_drivers,
                        COALESCE(supply_hours_mtd, 0) AS supply_hours
                    FROM ops.mv_yango_loyalty_performance_monthly_v1
                    WHERE month_start = %(ms)s
                      AND LOWER(country) = LOWER(%(co)s)
                """, {"ms": month_start, "co": country})
                for row in cur.fetchall():
                    cn = row["city_norm"]
                    ad = int(row["active_drivers"]) if row["active_drivers"] is not None else None
                    sh = float(row["supply_hours"]) if row["supply_hours"] is not None else None

                    result["metrics"]["active_drivers"]["cities"].append({
                        "city_norm": cn,
                        "actual_value": ad,
                        "target_value": None,
                        "gap": None,
                        "gap_pct": None,
                    })
                    result["metrics"]["supply_hours"]["cities"].append({
                        "city_norm": cn,
                        "actual_value": sh,
                        "target_value": None,
                        "gap": None,
                        "gap_pct": None,
                    })
            except Exception:
                result["metrics"]["active_drivers"]["source_confidence"] = "error"
                result["metrics"]["supply_hours"]["source_confidence"] = "error"

            country_flow = _COUNTRY_NORM_MAP.get(country.lower(), country.upper())
            try:
                cur.execute("""
                    SELECT
                        COALESCE(yego_operational_new_plus_reactivated, 0)::int AS nr
                    FROM ops.fct_yego_operational_flow_monthly_v2
                    WHERE month_start = %(ms)s
                      AND country = %(co)s
                      AND LOWER(city_norm) = 'lima'
                    LIMIT 1
                """, {"ms": month_start, "co": country_flow})
                flow_row = cur.fetchone()
                nr_val = int(flow_row["nr"]) if flow_row and flow_row["nr"] is not None else None
                result["metrics"]["operational_flow"]["cities"].append({
                    "city_norm": "lima",
                    "actual_value": nr_val,
                    "target_value": None,
                    "gap": None,
                    "gap_pct": None,
                })
            except Exception:
                result["metrics"]["operational_flow"]["source_confidence"] = "error"

            targets_by_city: dict = {}
            try:
                cur.execute("""
                    SELECT LOWER(city) AS city_norm, kpi_code, target_value
                    FROM ops.yango_loyalty_monthly_goals
                    WHERE month = %(m)s
                      AND kpi_code IN ('AD', 'SH', 'N_R')
                """, {"m": month_str})
                for row in cur.fetchall():
                    cn = row["city_norm"]
                    kpi = row["kpi_code"]
                    if cn not in targets_by_city:
                        targets_by_city[cn] = {}
                    targets_by_city[cn][kpi] = float(row["target_value"])
            except Exception:
                pass

            for city_entry in result["metrics"]["active_drivers"]["cities"]:
                cn = city_entry["city_norm"]
                t = targets_by_city.get(cn, {}).get("AD")
                if t is not None:
                    city_entry["target_value"] = t
                    if city_entry["actual_value"] is not None:
                        city_entry["gap"] = city_entry["actual_value"] - t
                        city_entry["gap_pct"] = round(city_entry["gap"] / t * 100, 2) if t != 0 else None

            for city_entry in result["metrics"]["supply_hours"]["cities"]:
                cn = city_entry["city_norm"]
                t = targets_by_city.get(cn, {}).get("SH")
                if t is not None:
                    city_entry["target_value"] = t
                    if city_entry["actual_value"] is not None:
                        city_entry["gap"] = round(city_entry["actual_value"] - t, 1)
                        city_entry["gap_pct"] = round(city_entry["gap"] / t * 100, 2) if t != 0 else None

            for city_entry in result["metrics"]["operational_flow"]["cities"]:
                cn = city_entry["city_norm"]
                t = targets_by_city.get(cn, {}).get("N_R")
                if t is not None:
                    city_entry["target_value"] = t
                    if city_entry["actual_value"] is not None:
                        city_entry["gap"] = city_entry["actual_value"] - t
                        city_entry["gap_pct"] = round(city_entry["gap"] / t * 100, 2) if t != 0 else None

    except Exception as e:
        logger.exception("get_loyalty_city_comparison: %s", e)

    return result
