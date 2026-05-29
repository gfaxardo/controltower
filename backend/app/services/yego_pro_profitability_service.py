"""
Yego Pro Profitability Service — Phase 1.3 Trust-Based Fallback Layer
Control Foundation serving layer (read-only).

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
Sources: module_weekly_billing, trips_2026, module_miauto_cronograma,
         module_calculated_shifts, module_driver_closes

Trust hierarchy:
  Production: module_calculated_shifts (REAL_OPERATIONAL) > trips (FALLBACK_OPERATIONAL)
  Settlement: module_driver_closes (REAL_SETTLEMENT) > assumptions (ESTIMATED)
  Financial:  module_weekly_billing (REAL_FINANCIAL) > shifts+assumptions (ESTIMATED_FINANCIAL) > legacy (LEGACY_MODEL)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db_quick

logger = logging.getLogger(__name__)

PARK_ID = "64085dd85e124e2c808806f70d527ea8"

MV_WEEK = "ops.mv_yego_pro_profitability_week"
MV_DAY = "ops.mv_yego_pro_profitability_day"
MV_DRIVER = "ops.mv_yego_pro_driver_profitability_week"
MV_VEHICLE = "ops.mv_yego_pro_vehicle_profitability_week"
MV_SHIFT = "ops.mv_yego_pro_shift_profitability_week"
MV_SHIFT_DAILY = "ops.mv_yego_pro_shift_daily"
MV_CLOSE_WEEK = "ops.mv_yego_pro_driver_close_week"
MV_FINANCIAL_TRUTH = "ops.mv_yego_pro_weekly_financial_truth"
MV_SOURCE_COVERAGE = "ops.mv_yego_pro_source_coverage"

SOURCE_PRIORITY = {
    "production": [
        {"source": "module_calculated_shifts", "confidence": "REAL", "label": "REAL_OPERATIONAL"},
        {"source": "trips_2026", "confidence": "ESTIMATED", "label": "FALLBACK_OPERATIONAL"},
    ],
    "settlement": [
        {"source": "module_driver_closes", "confidence": "REAL", "label": "REAL_SETTLEMENT"},
        {"source": "assumptions", "confidence": "ESTIMATED", "label": "ESTIMATED"},
    ],
    "financial": [
        {"source": "module_weekly_billing", "confidence": "REAL", "label": "REAL_FINANCIAL"},
        {"source": "module_calculated_shifts+assumptions", "confidence": "ESTIMATED", "label": "ESTIMATED_FINANCIAL"},
        {"source": "legacy_defaults", "confidence": "LEGACY", "label": "LEGACY_MODEL"},
    ],
}

COST_ASSUMPTIONS = {
    "fuel_per_trip_soles": 3.5,
    "maintenance_per_trip_soles": 1.2,
    "platform_commission_pct": 0.25,
    "default_driver_pct": 0.45,
    "fixed_cost_daily_soles": 15.0,
}

# Module-level view existence cache — avoids repeated to_regclass calls per request
_VIEWS_CACHE: Dict[str, bool] = {}


def _ensure_view_exists_cached(cur, view_name: str) -> bool:
    if view_name in _VIEWS_CACHE:
        return _VIEWS_CACHE[view_name]
    exists = _check_view_exists(cur, view_name)
    _VIEWS_CACHE[view_name] = exists
    return exists


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _check_view_exists(cur, view_name: str) -> bool:
    schema, name = view_name.split(".")
    cur.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS exists",
        (view_name,),
    )
    row = cur.fetchone()
    return bool(row and row.get("exists", False))


def _get_coverage(cur) -> dict:
    if not _ensure_view_exists_cached(cur, MV_SOURCE_COVERAGE):
        return {
            "billing_weeks": 0,
            "billing_drivers": 0,
            "shift_days": 0,
            "shift_drivers": 0,
            "close_days": 0,
            "close_driver_coverage_pct": 0,
            "plate_coverage_pct": 0,
            "financial_history_status": "NONE",
            "operational_history_status": "NONE",
            "registered_drivers": 0,
        }
    cur.execute(f"SELECT * FROM {MV_SOURCE_COVERAGE} LIMIT 1")
    row = cur.fetchone()
    if not row:
        return {}
    return {
        "registered_drivers": _safe_int(row.get("registered_drivers")) or 0,
        "trip_rows": _safe_int(row.get("trip_rows")) or 0,
        "trip_days": _safe_int(row.get("trip_days")) or 0,
        "trip_drivers": _safe_int(row.get("trip_drivers")) or 0,
        "shift_rows": _safe_int(row.get("shift_rows")) or 0,
        "shift_days": _safe_int(row.get("shift_days")) or 0,
        "shift_drivers": _safe_int(row.get("shift_drivers")) or 0,
        "shifts_with_plate": _safe_int(row.get("shifts_with_plate")) or 0,
        "shifts_without_plate": _safe_int(row.get("shifts_without_plate")) or 0,
        "plate_coverage_pct": _safe_float(row.get("plate_coverage_pct")) or 0,
        "close_rows": _safe_int(row.get("close_rows")) or 0,
        "close_days": _safe_int(row.get("close_days")) or 0,
        "close_drivers": _safe_int(row.get("close_drivers")) or 0,
        "close_driver_coverage_pct": _safe_float(row.get("close_driver_coverage_pct")) or 0,
        "billing_rows": _safe_int(row.get("billing_rows")) or 0,
        "billing_weeks": _safe_int(row.get("billing_weeks")) or 0,
        "billing_drivers": _safe_int(row.get("billing_drivers")) or 0,
        "billing_min_date": str(row.get("billing_min_date")) if row.get("billing_min_date") else None,
        "billing_max_date": str(row.get("billing_max_date")) if row.get("billing_max_date") else None,
        "financial_history_status": row.get("financial_history_status") or "NONE",
        "operational_history_status": row.get("operational_history_status") or "NONE",
    }


def _metric(value, source: str, metric_type: str, confidence: str, notes: str = "") -> Dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "metric_type": metric_type,
        "confidence": confidence,
        "notes": notes,
    }


def get_overview(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    "SELECT "
                    "to_regclass(%s) IS NOT NULL AS _wk, "
                    "to_regclass(%s) IS NOT NULL AS _cov",
                    (MV_WEEK, MV_SOURCE_COVERAGE),
                )
                vc = cur.fetchone()
                if not vc.get("_wk"):
                    return _missing_source_response(MV_WEEK, "Run yego_pro_profitability_serving_views.sql")
                _VIEWS_CACHE[MV_WEEK] = True
                _VIEWS_CACHE[MV_SOURCE_COVERAGE] = bool(vc.get("_cov"))

                cur.execute(f"SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT 1")
                week_row = cur.fetchone()

                cur.execute(f"SELECT * FROM {MV_DAY} ORDER BY date DESC LIMIT 30")
                day_rows = cur.fetchall()

                if not week_row and not day_rows:
                    return {"status": "NO_DATA", "park_id": park_id, "message": "No billing or trip data found"}

                trips_30d = sum(_safe_int(r.get("trips_completed")) or 0 for r in day_rows)
                cancelled_30d = sum(_safe_int(r.get("trips_cancelled")) or 0 for r in day_rows)
                revenue_30d = sum(_safe_float(r.get("revenue_gross")) or 0 for r in day_rows)
                drivers_30d = max((_safe_int(r.get("active_drivers")) or 0) for r in day_rows) if day_rows else 0

                kpis = {
                    "trips_completed_30d": _metric(trips_30d, "trips_2026", "REAL", "HIGH"),
                    "trips_cancelled_30d": _metric(cancelled_30d, "trips_2026", "REAL", "HIGH"),
                    "cancellation_rate": _metric(
                        round(cancelled_30d / max(trips_30d + cancelled_30d, 1), 4), "trips_2026", "DERIVED", "HIGH"
                    ),
                    "revenue_gross_30d": _metric(revenue_30d, "trips_2026", "REAL", "HIGH"),
                    "ticket_avg": _metric(
                        round(revenue_30d / max(trips_30d, 1), 2), "trips_2026", "DERIVED", "HIGH"
                    ),
                    "active_drivers": _metric(drivers_30d, "trips_2026", "REAL", "HIGH"),
                }

                if week_row:
                    kpis.update({
                        "work_hours_weekly": _metric(_safe_float(week_row.get("work_hours")), "module_weekly_billing", "REAL", "HIGH"),
                        "revenue_per_hour": _metric(_safe_float(week_row.get("revenue_per_hour")), "module_weekly_billing", "DERIVED", "HIGH"),
                        "trips_per_hour": _metric(_safe_float(week_row.get("trips_per_hour")), "module_weekly_billing", "DERIVED", "HIGH"),
                        "fuel_cost_weekly": _metric(_safe_float(week_row.get("fuel_cost")), "module_weekly_billing", "REAL", "HIGH"),
                        "maintenance_cost_weekly": _metric(_safe_float(week_row.get("maintenance_cost")), "module_weekly_billing", "REAL", "HIGH"),
                        "driver_payment_weekly": _metric(_safe_float(week_row.get("driver_payment")), "module_weekly_billing", "REAL", "HIGH"),
                        "profit_weekly": _metric(_safe_float(week_row.get("profit")), "module_weekly_billing", "REAL", "HIGH"),
                        "profit_per_trip": _metric(_safe_float(week_row.get("profit_per_trip")), "module_weekly_billing", "DERIVED", "HIGH"),
                        "margin_pct": _metric(_safe_float(week_row.get("margin_pct")), "module_weekly_billing", "DERIVED", "HIGH"),
                        "km_per_trip_total": _metric(_safe_float(week_row.get("km_per_trip")), "module_weekly_billing", "DERIVED", "HIGH", "Includes dead km"),
                        "fuel_per_km": _metric(_safe_float(week_row.get("fuel_per_km")), "module_weekly_billing", "DERIVED", "HIGH"),
                    })

                billing_weeks = 0

                coverage = _get_coverage(cur)
                billing_weeks = coverage.get("billing_weeks", 0)

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "park_name": "Yego Lima",
                    "kpis": kpis,
                    "health": {
                        "profit_status": "LOSS" if week_row and (_safe_float(week_row.get("profit")) or 0) < 0 else "PROFIT",
                        "billing_weeks_available": coverage.get("billing_weeks", billing_weeks),
                        "shift_days_available": coverage.get("shift_days", 0),
                        "data_confidence": "HIGH" if billing_weeks >= 4 else ("MEDIUM" if billing_weeks >= 1 else "LOW"),
                        "days_with_trips": len(day_rows),
                        "financial_history_status": coverage.get("financial_history_status", "PARTIAL"),
                        "operational_history_status": coverage.get("operational_history_status", "HEALTHY"),
                    },
                    "source_coverage": coverage,
                    "data_confidence_by_layer": {
                        "operation": "HIGH",
                        "driver_closes": coverage.get("close_driver_coverage_pct", 0) >= 80 and "HIGH" or "MEDIUM",
                        "billing": billing_weeks >= 4 and "HIGH" or "PARTIAL",
                        "simulation": "NOT_AVAILABLE",
                    },
                    "metadata": {
                        "sources": ["trips_2026", "module_calculated_shifts", "module_driver_closes", "module_weekly_billing"],
                        "last_billing_week": str(week_row.get("week_start")) if week_row else None,
                        "last_trip_date": str(day_rows[0].get("date")) if day_rows else None,
                    },
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability overview: %s", e)
        return _error_response(str(e))


def get_weekly(park_id: str = PARK_ID, weeks: int = 12) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _check_view_exists(cur, MV_WEEK):
                    return _missing_source_response(MV_WEEK, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(f"SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT %s", (weeks,))
                rows = cur.fetchall()

                result_weeks = []
                for r in rows:
                    result_weeks.append({
                        "week_start": str(r.get("week_start")),
                        "week_end": str(r.get("week_end")),
                        "active_drivers": _safe_int(r.get("active_drivers")),
                        "trips_completed": _safe_int(r.get("trips_completed")),
                        "work_hours": _safe_float(r.get("work_hours")),
                        "revenue_gross": _safe_float(r.get("revenue_gross")),
                        "revenue_net": _safe_float(r.get("revenue_net")),
                        "platform_commission": _safe_float(r.get("platform_commission")),
                        "km_total": _safe_float(r.get("km_total")),
                        "fuel_cost": _safe_float(r.get("fuel_cost")),
                        "maintenance_cost": _safe_float(r.get("maintenance_cost")),
                        "driver_payment": _safe_float(r.get("driver_payment")),
                        "profit": _safe_float(r.get("profit")),
                        "bono_yango": _safe_float(r.get("bono_yango")),
                        "bono_additional": _safe_float(r.get("bono_additional")),
                        "ticket_avg": _safe_float(r.get("ticket_avg")),
                        "km_per_trip": _safe_float(r.get("km_per_trip")),
                        "revenue_per_hour": _safe_float(r.get("revenue_per_hour")),
                        "trips_per_hour": _safe_float(r.get("trips_per_hour")),
                        "profit_per_trip": _safe_float(r.get("profit_per_trip")),
                        "margin_pct": _safe_float(r.get("margin_pct")),
                    })

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "weeks": result_weeks,
                    "total_weeks": len(result_weeks),
                    "source": "module_weekly_billing",
                    "metric_type": "REAL",
                    "confidence": "HIGH" if len(result_weeks) >= 4 else "MEDIUM",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability weekly: %s", e)
        return _error_response(str(e))


def get_daily(park_id: str = PARK_ID, days: int = 30) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _check_view_exists(cur, MV_DAY):
                    return _missing_source_response(MV_DAY, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(f"SELECT * FROM {MV_DAY} ORDER BY date DESC LIMIT %s", (days,))
                rows = cur.fetchall()

                result_days = []
                for r in rows:
                    result_days.append({
                        "date": str(r.get("date")),
                        "trips_completed": _safe_int(r.get("trips_completed")),
                        "trips_cancelled": _safe_int(r.get("trips_cancelled")),
                        "active_drivers": _safe_int(r.get("active_drivers")),
                        "revenue_gross": _safe_float(r.get("revenue_gross")),
                        "ticket_avg": _safe_float(r.get("ticket_avg")),
                        "km_total_passenger": _safe_float(r.get("km_total_passenger")),
                        "km_per_trip_passenger": _safe_float(r.get("km_per_trip_passenger")),
                        "duration_avg_min": _safe_float(r.get("duration_avg_min")),
                        "trips_day_shift": _safe_int(r.get("trips_day_shift")),
                        "trips_night_shift": _safe_int(r.get("trips_night_shift")),
                        "revenue_day_shift": _safe_float(r.get("revenue_day_shift")),
                        "revenue_night_shift": _safe_float(r.get("revenue_night_shift")),
                    })

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "days": result_days,
                    "total_days": len(result_days),
                    "source": "trips_2026",
                    "metric_type": "REAL",
                    "confidence": "HIGH",
                    "notes": "km_per_trip_passenger is passenger-only distance (field stored in meters, converted to km)",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability daily: %s", e)
        return _error_response(str(e))


def get_drivers(park_id: str = PARK_ID, week_start: Optional[str] = None) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                has_mv = _check_view_exists(cur, MV_DRIVER)
                rows = []
                if has_mv:
                    if week_start:
                        cur.execute(
                            f"SELECT * FROM {MV_DRIVER} WHERE week_start = %s ORDER BY profit DESC",
                            (week_start,),
                        )
                    else:
                        cur.execute(
                            f"""SELECT * FROM {MV_DRIVER}
                                WHERE week_start = (SELECT MAX(week_start) FROM {MV_DRIVER})
                                ORDER BY profit DESC"""
                        )
                    rows = cur.fetchall()

                if rows:
                    drivers = []
                    profitable_count = 0
                    for r in rows:
                        is_prof = bool(r.get("is_profitable"))
                        if is_prof:
                            profitable_count += 1
                        drivers.append({
                            "driver_id": r.get("driver_id"),
                            "driver_name": r.get("driver_name"),
                            "week_start": str(r.get("week_start")),
                            "trips_completed": _safe_int(r.get("trips_completed")),
                            "work_hours": _safe_float(r.get("work_hours")),
                            "revenue_gross": _safe_float(r.get("revenue_gross")),
                            "revenue_per_hour": _safe_float(r.get("revenue_per_hour")),
                            "trips_per_hour": _safe_float(r.get("trips_per_hour")),
                            "km_total": _safe_float(r.get("km_total")),
                            "km_per_trip": _safe_float(r.get("km_per_trip")),
                            "fuel_cost": _safe_float(r.get("fuel_cost")),
                            "maintenance_cost": _safe_float(r.get("maintenance_cost")),
                            "driver_pct": _safe_float(r.get("driver_pct")),
                            "driver_payment": _safe_float(r.get("driver_payment")),
                            "profit": _safe_float(r.get("profit")),
                            "profit_per_trip": _safe_float(r.get("profit_per_trip")),
                            "margin_pct": _safe_float(r.get("margin_pct")),
                            "bono_yango": _safe_float(r.get("bono_yango")),
                            "is_profitable": is_prof,
                            "confidence": "REAL",
                            "source": "module_weekly_billing",
                        })

                    return {
                        "status": "OK",
                        "park_id": park_id,
                        "drivers": drivers,
                        "summary": {
                            "total_drivers": len(drivers),
                            "profitable_count": profitable_count,
                            "loss_count": len(drivers) - profitable_count,
                            "pct_profitable": round(profitable_count / max(len(drivers), 1), 4),
                        },
                        "source": "module_weekly_billing",
                        "metric_type": "REAL",
                        "confidence": "REAL",
                    }

                return _get_drivers_fallback(cur, park_id)
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability drivers: %s", e)
        return _error_response(str(e))


def _get_drivers_fallback(cur, park_id: str) -> Dict[str, Any]:
    park_filter = "s.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"
    cur.execute(f"""
        SELECT
            s.driver_id,
            d.first_name || ' ' || COALESCE(d.last_name, '') AS driver_name,
            SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
            SUM(COALESCE(s.produccion_total, 0)) AS revenue,
            SUM(COALESCE(s.duracion_minutos, 0)) / 60.0 AS work_hours,
            COUNT(DISTINCT s.fecha) AS shift_days,
            STRING_AGG(DISTINCT s.placa, ', ') FILTER (WHERE s.placa IS NOT NULL) AS plates
        FROM public.module_calculated_shifts s
        LEFT JOIN public.drivers d ON d.driver_id = s.driver_id
        WHERE {park_filter}
        GROUP BY s.driver_id, d.first_name, d.last_name
        HAVING SUM(COALESCE(s.cantidad_viajes, 0)) > 0
        ORDER BY SUM(COALESCE(s.produccion_total, 0)) DESC
    """, (park_id,))
    shift_rows = cur.fetchall()

    if not shift_rows:
        return {
            "status": "NO_DATA",
            "park_id": park_id,
            "drivers": [],
            "message": "No se puede estimar esta vista porque falta produccion y cierre.",
            "confidence": "NOT_AVAILABLE",
        }

    close_map = {}
    cur.execute(f"""
        SELECT c.driver_id,
               SUM(COALESCE(c.total_ingresos, 0)) AS total_income,
               SUM(COALESCE(c.gnv_soles, 0) + COALESCE(c.gasolina_soles, 0)) AS fuel_real,
               SUM(COALESCE(c.resta, 0)) AS driver_payout_real,
               COUNT(*) AS close_count
        FROM public.module_driver_closes c
        WHERE c.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
        GROUP BY c.driver_id
    """, (park_id,))
    for cr in cur.fetchall():
        close_map[cr["driver_id"]] = cr

    drivers = []
    for r in shift_rows:
        did = r["driver_id"]
        trips = _safe_int(r.get("trips")) or 0
        revenue = _safe_float(r.get("revenue")) or 0
        work_hours = _safe_float(r.get("work_hours"))
        close_data = close_map.get(did)

        if close_data and close_data.get("close_count", 0) > 0:
            fuel_cost = _safe_float(close_data.get("fuel_real")) or 0
            driver_payout = _safe_float(close_data.get("driver_payout_real")) or 0
            cost_confidence = "REAL"
            cost_source = "module_driver_closes"
        else:
            fuel_cost = round(trips * COST_ASSUMPTIONS["fuel_per_trip_soles"], 2)
            driver_payout = round(revenue * COST_ASSUMPTIONS["default_driver_pct"], 2)
            cost_confidence = "ESTIMATED"
            cost_source = "module_calculated_shifts + assumptions"

        maintenance_cost = round(trips * COST_ASSUMPTIONS["maintenance_per_trip_soles"], 2)
        estimated_margin = round(revenue - fuel_cost - maintenance_cost - driver_payout, 2)
        margin_pct = round(estimated_margin / max(revenue, 1), 4) if revenue > 0 else None

        drivers.append({
            "driver_id": did,
            "driver_name": (r.get("driver_name") or "").strip() or None,
            "trips": trips,
            "revenue": revenue,
            "work_hours": work_hours,
            "km": None,
            "estimated_cost": round(fuel_cost + maintenance_cost + driver_payout, 2),
            "estimated_fuel": fuel_cost,
            "estimated_maintenance": maintenance_cost,
            "estimated_driver_payout": driver_payout,
            "estimated_margin": estimated_margin,
            "margin_pct": margin_pct,
            "is_profitable": estimated_margin > 0 if estimated_margin is not None else None,
            "confidence": "ESTIMATED",
            "source": cost_source,
            "warning": "Rentabilidad estimada; faltan cierres completos.",
        })

    profitable_count = sum(1 for d in drivers if d.get("is_profitable"))
    return {
        "status": "OK",
        "park_id": park_id,
        "drivers": drivers,
        "summary": {
            "total_drivers": len(drivers),
            "profitable_count": profitable_count,
            "loss_count": len(drivers) - profitable_count,
            "pct_profitable": round(profitable_count / max(len(drivers), 1), 4),
        },
        "source": "module_calculated_shifts + assumptions",
        "metric_type": "ESTIMATED",
        "confidence": "ESTIMATED",
        "warning": "No hay cierres financieros suficientes. Mostrando estimacion operativa basada en produccion diaria.",
        "trust_layer": SOURCE_PRIORITY["financial"][1],
    }


def get_vehicles(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                vehicles_config = []
                if _check_view_exists(cur, MV_VEHICLE):
                    cur.execute(f"SELECT * FROM {MV_VEHICLE}")
                    for r in cur.fetchall():
                        vehicles_config.append({
                            "cronograma_name": r.get("cronograma_name"),
                            "vehicle_name": r.get("vehicle_name"),
                            "total_weekly_quotas": _safe_int(r.get("total_weekly_quotas")),
                            "weekly_quota": _safe_float(r.get("weekly_quota")),
                            "min_trips_for_bono": _safe_int(r.get("min_trips_for_bono")),
                            "bono_reduction": _safe_float(r.get("bono_reduction")),
                            "tier_order": _safe_int(r.get("tier_order")),
                            "confidence": "REAL",
                            "source": "module_miauto_cronograma",
                        })

                vehicles_estimated = _get_vehicles_from_shifts(cur, park_id)

                if vehicles_estimated:
                    return {
                        "status": "OK",
                        "park_id": park_id,
                        "vehicles": vehicles_estimated,
                        "fleet_config": vehicles_config,
                        "source": "module_calculated_shifts + assumptions",
                        "metric_type": "ESTIMATED",
                        "confidence": "ESTIMATED",
                        "warning": "No hay verdad financiera por vehiculo. Mostrando estimacion basada en produccion por placa.",
                        "trust_layer": SOURCE_PRIORITY["production"][0],
                    }

                if vehicles_config:
                    return {
                        "status": "LIMITED",
                        "park_id": park_id,
                        "vehicles": vehicles_config,
                        "limitation": "No vehicle-to-driver assignment table exists. Only fleet configuration shown.",
                        "source": "module_miauto_cronograma",
                        "metric_type": "REAL",
                        "confidence": "REAL",
                        "notes": "Cannot report per-vehicle profitability. Only quota structure available.",
                    }

                return {
                    "status": "NO_DATA",
                    "park_id": park_id,
                    "vehicles": [],
                    "message": "No se puede estimar esta vista porque falta produccion y cierre.",
                    "confidence": "NOT_AVAILABLE",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability vehicles: %s", e)
        return _error_response(str(e))


def _get_vehicles_from_shifts(cur, park_id: str) -> List[Dict[str, Any]]:
    park_filter = "s.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"
    cur.execute(f"""
        SELECT
            COALESCE(s.placa, '__SIN_PLACA__') AS plate,
            SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
            SUM(COALESCE(s.produccion_total, 0)) AS revenue,
            SUM(COALESCE(s.duracion_minutos, 0)) / 60.0 AS work_hours,
            COUNT(DISTINCT s.fecha) AS shift_days,
            COUNT(DISTINCT s.driver_id) AS drivers_count
        FROM public.module_calculated_shifts s
        WHERE {park_filter}
        GROUP BY COALESCE(s.placa, '__SIN_PLACA__')
        HAVING SUM(COALESCE(s.cantidad_viajes, 0)) > 0
        ORDER BY SUM(COALESCE(s.produccion_total, 0)) DESC
    """, (park_id,))
    rows = cur.fetchall()
    if not rows:
        return []

    vehicles = []
    for r in rows:
        plate = r.get("plate")
        is_unknown = plate == "__SIN_PLACA__"
        trips = _safe_int(r.get("trips")) or 0
        revenue = _safe_float(r.get("revenue")) or 0

        fuel_cost = round(trips * COST_ASSUMPTIONS["fuel_per_trip_soles"], 2)
        maintenance_cost = round(trips * COST_ASSUMPTIONS["maintenance_per_trip_soles"], 2)
        driver_payout = round(revenue * COST_ASSUMPTIONS["default_driver_pct"], 2)
        estimated_margin = round(revenue - fuel_cost - maintenance_cost - driver_payout, 2)

        vehicles.append({
            "plate": "Sin placa registrada" if is_unknown else plate,
            "vehicle_id": None if is_unknown else plate,
            "trips": trips,
            "revenue": revenue,
            "km": None,
            "estimated_cost": round(fuel_cost + maintenance_cost + driver_payout, 2),
            "estimated_margin": estimated_margin,
            "margin_pct": round(estimated_margin / max(revenue, 1), 4) if revenue > 0 else None,
            "shift_days": _safe_int(r.get("shift_days")),
            "drivers_count": _safe_int(r.get("drivers_count")),
            "confidence": "ESTIMATED",
            "source": "module_calculated_shifts + assumptions",
            "warning": "Rentabilidad estimada; falta verdad financiera por vehiculo." if not is_unknown else "Impacto agregado de turnos sin placa asignada.",
        })
    return vehicles


def get_shifts(park_id: str = PARK_ID, days: int = 35) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                has_native = _check_view_exists(cur, MV_SHIFT_DAILY)

                if has_native:
                    cur.execute(
                        f"SELECT * FROM {MV_SHIFT_DAILY} ORDER BY date DESC, shift_type LIMIT %s",
                        (days * 4,),
                    )
                    rows = cur.fetchall()

                    shifts = []
                    for r in rows:
                        trips = _safe_int(r.get("trips")) or 0
                        revenue = _safe_float(r.get("revenue")) or 0
                        ticket_avg = round(revenue / max(trips, 1), 2) if trips > 0 else None
                        estimated_margin = _estimate_shift_margin(trips, revenue)

                        shifts.append({
                            "date": str(r.get("date")),
                            "shift_type": r.get("shift_type"),
                            "driver_id": r.get("driver_id"),
                            "vehicle_plate": r.get("vehicle_plate"),
                            "trips": trips,
                            "revenue": revenue,
                            "ticket_avg": ticket_avg,
                            "shift_amount": _safe_float(r.get("shift_amount")),
                            "service_commission": _safe_float(r.get("service_commission")),
                            "total_minutes": _safe_int(r.get("total_minutes")),
                            "shift_count": _safe_int(r.get("shift_count")),
                            "paid_shifts": _safe_int(r.get("paid_shifts")),
                            "avg_duration_min": _safe_float(r.get("avg_duration_min")),
                            "revenue_per_trip": _safe_float(r.get("revenue_per_trip")),
                            "estimated_margin": estimated_margin,
                            "confidence": "REAL_OPERATIONAL",
                            "margin_confidence": "ESTIMATED_FINANCIAL",
                        })

                    return {
                        "status": "OK",
                        "park_id": park_id,
                        "shifts": shifts,
                        "shift_source": "module_calculated_shifts (native shift types from operational system)",
                        "source": "module_calculated_shifts",
                        "metric_type": "REAL",
                        "confidence": "REAL",
                        "margin_confidence": "ESTIMATED_FINANCIAL",
                        "notes": "Produccion real desde sistema operativo. Margen estimado con supuestos de costos.",
                        "trust_layer": SOURCE_PRIORITY["production"][0],
                    }

                has_shift_mv = _check_view_exists(cur, MV_SHIFT)
                if has_shift_mv:
                    cur.execute(f"SELECT * FROM {MV_SHIFT} ORDER BY week_start DESC LIMIT %s", (int(days / 7 * 2),))
                    rows = cur.fetchall()
                    if rows:
                        shifts = []
                        for r in rows:
                            trips = _safe_int(r.get("trips_completed")) or 0
                            revenue = _safe_float(r.get("revenue_gross")) or 0
                            estimated_margin = _estimate_shift_margin(trips, revenue)
                            shifts.append({
                                "week_start": str(r.get("week_start")),
                                "shift": r.get("shift"),
                                "trips_completed": trips,
                                "active_drivers": _safe_int(r.get("active_drivers")),
                                "revenue_gross": revenue,
                                "ticket_avg": _safe_float(r.get("ticket_avg")),
                                "ticket_median": _safe_float(r.get("ticket_median")),
                                "km_total": _safe_float(r.get("km_total")),
                                "km_per_trip": _safe_float(r.get("km_per_trip")),
                                "duration_avg_min": _safe_float(r.get("duration_avg_min")),
                                "estimated_margin": estimated_margin,
                                "confidence": "REAL_OPERATIONAL",
                                "margin_confidence": "ESTIMATED_FINANCIAL",
                            })

                        return {
                            "status": "OK",
                            "park_id": park_id,
                            "shifts": shifts,
                            "shift_source": "DERIVED from trips_2026 timestamps (06:00-17:59=DAY, 18:00-05:59=NIGHT)",
                            "shift_definition": {"DAY": "06:00-17:59", "NIGHT": "18:00-05:59"},
                            "source": "trips_2026",
                            "metric_type": "DERIVED",
                            "confidence": "REAL_OPERATIONAL",
                            "margin_confidence": "ESTIMATED_FINANCIAL",
                            "notes": "Clasificacion derivada de timestamps. Margen estimado con supuestos.",
                            "trust_layer": SOURCE_PRIORITY["production"][1],
                        }

                return _get_shifts_fallback(cur, park_id)
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability shifts: %s", e)
        return _error_response(str(e))


def _estimate_shift_margin(trips: int, revenue: float) -> Optional[float]:
    if trips <= 0 or revenue <= 0:
        return None
    fuel = trips * COST_ASSUMPTIONS["fuel_per_trip_soles"]
    maint = trips * COST_ASSUMPTIONS["maintenance_per_trip_soles"]
    payout = revenue * COST_ASSUMPTIONS["default_driver_pct"]
    return round(revenue - fuel - maint - payout, 2)


def _get_shifts_fallback(cur, park_id: str) -> Dict[str, Any]:
    park_filter = "s.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"
    cur.execute(f"""
        SELECT
            s.fecha AS date,
            s.tipo_turno AS shift_type,
            SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
            SUM(COALESCE(s.produccion_total, 0)) AS revenue,
            SUM(COALESCE(s.duracion_minutos, 0)) AS total_minutes,
            COUNT(DISTINCT s.driver_id) AS active_drivers
        FROM public.module_calculated_shifts s
        WHERE {park_filter}
        GROUP BY s.fecha, s.tipo_turno
        HAVING SUM(COALESCE(s.cantidad_viajes, 0)) > 0
        ORDER BY s.fecha DESC, s.tipo_turno
        LIMIT 200
    """, (park_id,))
    rows = cur.fetchall()
    if not rows:
        return {
            "status": "NO_DATA",
            "park_id": park_id,
            "shifts": [],
            "message": "No se puede estimar esta vista porque falta produccion y cierre.",
            "confidence": "NOT_AVAILABLE",
        }

    shifts = []
    for r in rows:
        trips = _safe_int(r.get("trips")) or 0
        revenue = _safe_float(r.get("revenue")) or 0
        ticket_avg = round(revenue / max(trips, 1), 2) if trips > 0 else None
        estimated_margin = _estimate_shift_margin(trips, revenue)

        shifts.append({
            "date": str(r.get("date")),
            "shift_type": r.get("shift_type"),
            "trips": trips,
            "revenue": revenue,
            "ticket_avg": ticket_avg,
            "total_minutes": _safe_int(r.get("total_minutes")),
            "active_drivers": _safe_int(r.get("active_drivers")),
            "estimated_margin": estimated_margin,
            "confidence": "REAL_OPERATIONAL",
            "margin_confidence": "ESTIMATED_FINANCIAL",
        })

    return {
        "status": "OK",
        "park_id": park_id,
        "shifts": shifts,
        "source": "module_calculated_shifts",
        "metric_type": "REAL",
        "confidence": "REAL_OPERATIONAL",
        "margin_confidence": "ESTIMATED_FINANCIAL",
        "warning": "No hay cierres financieros suficientes. Mostrando produccion real con margen estimado.",
        "trust_layer": SOURCE_PRIORITY["production"][0],
    }


def get_waterfall(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                has_billing = _check_view_exists(cur, MV_WEEK)
                week_row = None
                if has_billing:
                    cur.execute(f"SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT 1")
                    week_row = cur.fetchone()

                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"
                cur.execute(f"""
                    SELECT
                        SUM(COALESCE(cantidad_viajes, 0)) AS trips,
                        SUM(COALESCE(produccion_total, 0)) AS revenue,
                        SUM(COALESCE(duracion_minutos, 0)) / 60.0 AS hours
                    FROM public.module_calculated_shifts
                    WHERE {park_filter}
                """, (park_id,))
                shift_agg = cur.fetchone() or {}
                shift_trips = _safe_int(shift_agg.get("trips")) or 0
                shift_revenue = _safe_float(shift_agg.get("revenue")) or 0

                cur.execute(f"""
                    SELECT
                        SUM(COALESCE(gnv_soles, 0) + COALESCE(gasolina_soles, 0)) AS fuel_real,
                        SUM(COALESCE(resta, 0)) AS payout_real,
                        COUNT(*) AS close_count
                    FROM public.module_driver_closes
                    WHERE {park_filter}
                """, (park_id,))
                close_agg = cur.fetchone() or {}
                has_close_data = (_safe_int(close_agg.get("close_count")) or 0) > 0

                steps = []

                if week_row:
                    rev = _safe_float(week_row.get("revenue_gross")) or 0
                    steps.append({"label": "Revenue bruto", "value": rev, "confidence": "REAL", "source": "module_weekly_billing"})
                    fuel = _safe_float(week_row.get("fuel_cost")) or 0
                    steps.append({"label": "Combustible", "value": -abs(fuel), "confidence": "REAL", "source": "module_weekly_billing"})
                    maint = _safe_float(week_row.get("maintenance_cost")) or 0
                    steps.append({"label": "Mantenimiento", "value": -abs(maint), "confidence": "REAL", "source": "module_weekly_billing"})
                    payout = _safe_float(week_row.get("driver_payment")) or 0
                    steps.append({"label": "Payout conductor", "value": -abs(payout), "confidence": "REAL", "source": "module_weekly_billing"})
                    commission = _safe_float(week_row.get("platform_commission")) or 0
                    if commission:
                        steps.append({"label": "Comision plataforma", "value": -abs(commission), "confidence": "REAL", "source": "module_weekly_billing"})
                    profit = _safe_float(week_row.get("profit")) or 0
                    steps.append({"label": "Utilidad neta", "value": profit, "confidence": "REAL", "source": "module_weekly_billing"})
                elif shift_revenue > 0:
                    steps.append({"label": "Revenue bruto", "value": shift_revenue, "confidence": "REAL", "source": "module_calculated_shifts"})

                    if has_close_data:
                        fuel_real = _safe_float(close_agg.get("fuel_real")) or 0
                        steps.append({"label": "Combustible", "value": -abs(fuel_real), "confidence": "REAL", "source": "module_driver_closes"})
                    else:
                        fuel_est = round(shift_trips * COST_ASSUMPTIONS["fuel_per_trip_soles"], 2)
                        steps.append({"label": "Combustible estimado", "value": -abs(fuel_est), "confidence": "ESTIMATED", "source": "assumptions"})

                    maint_est = round(shift_trips * COST_ASSUMPTIONS["maintenance_per_trip_soles"], 2)
                    steps.append({"label": "Mantenimiento estimado", "value": -abs(maint_est), "confidence": "ESTIMATED", "source": "assumptions"})

                    if has_close_data:
                        payout_real = _safe_float(close_agg.get("payout_real")) or 0
                        steps.append({"label": "Payout conductor", "value": -abs(payout_real), "confidence": "REAL", "source": "module_driver_closes"})
                    else:
                        payout_est = round(shift_revenue * COST_ASSUMPTIONS["default_driver_pct"], 2)
                        steps.append({"label": "Payout conductor estimado", "value": -abs(payout_est), "confidence": "ESTIMATED", "source": "assumptions"})

                    fixed_est = round(COST_ASSUMPTIONS["fixed_cost_daily_soles"] * 30, 2)
                    steps.append({"label": "Costo fijo estimado", "value": -abs(fixed_est), "confidence": "LEGACY", "source": "legacy_defaults"})

                    total_costs = sum(abs(s["value"]) for s in steps if s["value"] < 0)
                    net = round(shift_revenue - total_costs, 2)
                    steps.append({"label": "Utilidad estimada", "value": net, "confidence": "ESTIMATED", "source": "module_calculated_shifts + assumptions"})
                else:
                    return {
                        "status": "NO_DATA",
                        "park_id": park_id,
                        "steps": [],
                        "message": "No se puede estimar esta vista porque falta produccion y cierre.",
                        "confidence": "NOT_AVAILABLE",
                    }

                has_all_real = all(s["confidence"] == "REAL" for s in steps)
                overall_confidence = "REAL" if has_all_real else "ESTIMATED"

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "steps": steps,
                    "source": "module_weekly_billing" if week_row else "module_calculated_shifts + assumptions",
                    "confidence": overall_confidence,
                    "is_partial": not has_all_real,
                    "warning": None if has_all_real else "Waterfall parcial: algunos costos son estimados. Cada linea indica su nivel de confianza.",
                    "trust_layer": SOURCE_PRIORITY["financial"][0] if week_row else SOURCE_PRIORITY["financial"][1],
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability waterfall: %s", e)
        return _error_response(str(e))


def get_input_mapping(park_id: str = PARK_ID) -> Dict[str, Any]:
    inputs_production: List[Dict[str, Any]] = [
        {"key": "trips_daily", "source": "module_calculated_shifts", "source_table": "public.module_calculated_shifts", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "revenue_daily", "source": "module_calculated_shifts", "source_table": "public.module_calculated_shifts", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "shift_type", "source": "module_calculated_shifts.tipo_turno", "source_table": "public.module_calculated_shifts", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "vehicle_plate", "source": "module_calculated_shifts.placa", "source_table": "public.module_calculated_shifts", "metric_type": "REAL", "confidence": "MEDIUM", "role": "SOURCE_OF_TRUTH", "coverage": "55%"},
        {"key": "shift_duration", "source": "module_calculated_shifts.duracion_minutos", "source_table": "public.module_calculated_shifts", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
    ]

    inputs_settlement: List[Dict[str, Any]] = [
        {"key": "driver_payout_daily", "source": "module_driver_closes", "source_table": "public.module_driver_closes", "metric_type": "REAL", "confidence": "MEDIUM", "role": "SOURCE_OF_TRUTH", "coverage": "35.7%"},
        {"key": "fuel_cost_daily", "source": "module_driver_closes (gnv_soles + gasolina_soles)", "source_table": "public.module_driver_closes", "metric_type": "REAL", "confidence": "MEDIUM", "role": "SOURCE_OF_TRUTH"},
        {"key": "km_validated", "source": "module_driver_closes.diferencia_odometro", "source_table": "public.module_driver_closes", "metric_type": "REAL", "confidence": "LOW", "role": "SECONDARY_CHECK"},
        {"key": "daily_settlement", "source": "module_driver_closes (liquida_efectivo + liquida_yape)", "source_table": "public.module_driver_closes", "metric_type": "REAL", "confidence": "MEDIUM", "role": "SOURCE_OF_TRUTH"},
    ]

    inputs_financial: List[Dict[str, Any]] = [
        {"key": "revenue_weekly", "source": "module_weekly_billing.monto_total_producido", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "platform_commission", "source": "module_weekly_billing.comision_app", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "fuel_cost_weekly", "source": "module_weekly_billing.gasto_combustible", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "maintenance_cost_weekly", "source": "module_weekly_billing.gasto_mantenimiento", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "driver_payout_weekly", "source": "module_weekly_billing.pago_total", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "profit_weekly", "source": "module_weekly_billing.utilidad", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "km_weekly", "source": "module_weekly_billing.km_recorrido", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "bonus_weekly", "source": "module_weekly_billing (bono_yango + bono_adic_viajes)", "source_table": "public.module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
        {"key": "margin_pct", "source": "module_weekly_billing (utilidad / monto_total_producido)", "source_table": "public.module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "role": "SOURCE_OF_TRUTH"},
    ]

    inputs_not_available: List[Dict[str, Any]] = [
        {"key": "supply_hours_real", "source": "module_ct_fleet_summary_daily", "reason": "Table empty for this park", "remediation": "Proxy: use horas_trabajo from billing"},
        {"key": "acceptance_rate", "source": "summary_daily", "reason": "0 records for park_id", "remediation": "NOT_AVAILABLE"},
        {"key": "vehicle_driver_assignment", "source": "N/A", "reason": "No vehicle-to-driver assignment table. Partial via module_calculated_shifts.placa (55% coverage)", "remediation": "Use placa field in shifts as proxy. Cannot report per-vehicle profitability for all drivers."},
    ]

    payment_tiers: List[Dict[str, Any]] = [
        {"min_trips_weekly": 90, "driver_pct": 30},
        {"min_trips_weekly": 95, "driver_pct": 35},
        {"min_trips_weekly": 100, "driver_pct": 40},
        {"min_trips_weekly": 107, "driver_pct": 45},
        {"min_trips_weekly": 117, "driver_pct": 50},
        {"min_trips_weekly": 128, "driver_pct": 55},
        {"min_trips_weekly": 140, "driver_pct": 60},
    ]

    return {
        "status": "OK",
        "park_id": park_id,
        "source_of_truth": {
            "production": "module_calculated_shifts (shifts diarios, turnos, produccion)",
            "settlement": "module_driver_closes (liquidacion diaria, validacion km, combustible)",
            "financial": "module_weekly_billing (verdad financiera semanal, P&L consolidado)",
        },
        "inputs_production": inputs_production,
        "inputs_settlement": inputs_settlement,
        "inputs_financial": inputs_financial,
        "inputs_not_available": inputs_not_available,
        "payment_tiers": payment_tiers,
        "source": "module_calculated_shifts + module_driver_closes + module_weekly_billing",
        "notes": "Production = shifts (native). Settlement = closes (daily operational). Financial = billing (weekly truth).",
    }


def get_quality(park_id: str = PARK_ID) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    try:
        with get_db_quick(timeout_ms=10000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                for view_name, label in [
                    (MV_WEEK, "Weekly Profitability MV"),
                    (MV_DAY, "Daily Profitability MV"),
                    (MV_DRIVER, "Driver Profitability MV"),
                    (MV_VEHICLE, "Vehicle Config MV"),
                    (MV_SHIFT, "Shift Profitability MV"),
                    (MV_SHIFT_DAILY, "Shift Daily MV (native)"),
                    (MV_CLOSE_WEEK, "Driver Close Week MV"),
                    (MV_FINANCIAL_TRUTH, "Weekly Financial Truth MV"),
                    (MV_SOURCE_COVERAGE, "Source Coverage MV"),
                ]:
                    exists = _check_view_exists(cur, view_name)
                    row_count = 0
                    freshness = None
                    if exists:
                        cur.execute(f"SELECT COUNT(*) AS cnt FROM {view_name}")
                        cnt_row = cur.fetchone()
                        row_count = _safe_int(cnt_row.get("cnt")) if cnt_row else 0
                        cur.execute(f"SELECT MAX(refreshed_at) AS last_refresh FROM {view_name}")
                        fr_row = cur.fetchone()
                        freshness = str(fr_row.get("last_refresh")) if fr_row and fr_row.get("last_refresh") else None

                    checks.append({
                        "view": view_name,
                        "label": label,
                        "exists": exists,
                        "row_count": row_count,
                        "last_refresh": freshness,
                        "status": "OK" if exists and row_count > 0 else ("EMPTY" if exists else "MISSING"),
                    })

                coverage = _get_coverage(cur)

                billing_weeks = coverage.get("billing_weeks", 0)
                shift_days = coverage.get("shift_days", 0)
                plate_cov = coverage.get("plate_coverage_pct", 0)
                close_cov = coverage.get("close_driver_coverage_pct", 0)

                if billing_weeks < 4:
                    warnings.append({
                        "type": "FINANCIAL_HISTORY",
                        "severity": "HIGH" if billing_weeks == 0 else "MEDIUM",
                        "message": f"Billing solo tiene {billing_weeks} semana(s). Se necesitan 4+ semanas para tendencias confiables.",
                    })
                if billing_weeks < 1:
                    warnings.append({
                        "type": "NO_FINANCIAL_DATA",
                        "severity": "HIGH",
                        "message": "Sin datos de billing. Imposible calcular rentabilidad financiera.",
                    })
                if shift_days < 7:
                    warnings.append({
                        "type": "SHIFT_COVERAGE",
                        "severity": "MEDIUM" if shift_days > 0 else "HIGH",
                        "message": f"Shift daily data tiene {shift_days} dias. Se esperan 7+ dias.",
                    })
                if plate_cov < 80:
                    warnings.append({
                        "type": "VEHICLE_DRIVER_LINK",
                        "severity": "MEDIUM",
                        "message": f"Cobertura placa-vehiculo: {plate_cov}%. Bajo 80%. Asignacion vehiculo-conductor parcial.",
                    })
                if close_cov < 80:
                    warnings.append({
                        "type": "DRIVER_CLOSE_COVERAGE",
                        "severity": "MEDIUM",
                        "message": f"Cobertura de cierres de conductor: {close_cov}%. Bajo 80%.",
                    })

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM public.drivers WHERE park_id = %s",
                    (park_id,),
                )
                dr_row = cur.fetchone()
                driver_count = _safe_int(dr_row.get("cnt")) if dr_row else 0

                cur.execute(
                    """SELECT COUNT(*) AS cnt, MAX(fecha_inicio_viaje::date) AS last_date
                       FROM public.trips_2026
                       WHERE park_id = %s AND condicion = 'Completado'""",
                    (park_id,),
                )
                tr_row = cur.fetchone()
                trip_count = _safe_int(tr_row.get("cnt")) if tr_row else 0
                last_trip = str(tr_row.get("last_date")) if tr_row and tr_row.get("last_date") else None

                cur.execute(
                    """SELECT COUNT(*) AS cnt FROM public.module_weekly_billing
                       WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)""",
                    (park_id,),
                )
                bl_row = cur.fetchone()
                billing_count = _safe_int(bl_row.get("cnt")) if bl_row else 0

                trust_layer_summary = _build_trust_layer_summary(coverage)

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "serving_views": checks,
                    "source_coverage": coverage,
                    "warnings": warnings,
                    "warning_count": len(warnings),
                    "raw_sources": {
                        "drivers_in_park": driver_count,
                        "trips_completed": trip_count,
                        "last_trip_date": last_trip,
                        "billing_records": billing_count,
                    },
                    "overall": "HEALTHY" if all(c["status"] == "OK" for c in checks) and len(warnings) == 0 else ("DEGRADED" if any(c["status"] == "MISSING" for c in checks) else "OPERATIONAL"),
                    "trust_layer_summary": trust_layer_summary,
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability quality: %s", e)
        return _error_response(str(e))


def get_root_cause_audit(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=30000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT s.driver_id, s.fecha, s.tipo_turno,
                           s.cantidad_viajes AS trips, s.produccion_total AS revenue,
                           s.placa, s.monto_total, s.duracion_minutos,
                           NOT EXISTS (
                               SELECT 1 FROM public.module_driver_closes c
                               WHERE c.driver_id = s.driver_id AND c.fecha = s.fecha
                           ) AS missing_close
                    FROM public.module_calculated_shifts s
                    WHERE {park_filter}
                    ORDER BY s.fecha DESC, s.driver_id
                """, (park_id,))

                shift_rows = cur.fetchall()
                missing_closes = [r for r in shift_rows if r.get("missing_close")]
                has_close = [r for r in shift_rows if not r.get("missing_close")]

                cur.execute(f"""
                    SELECT c.driver_id, c.fecha, c.placa,
                           c.total_ingresos, c.total_gastos, c.resta,
                           c.gnv_soles, c.gasolina_soles,
                           c.calculated_shift_ids,
                           NOT EXISTS (
                               SELECT 1 FROM public.module_calculated_shifts s
                               WHERE s.driver_id = c.driver_id AND s.fecha = c.fecha
                           ) AS missing_production
                    FROM public.module_driver_closes c
                    WHERE {park_filter}
                    ORDER BY c.fecha DESC
                """, (park_id,))

                close_rows = cur.fetchall()
                closes_no_prod = [r for r in close_rows if r.get("missing_production")]

                cur.execute(f"""
                    SELECT s.driver_id,
                           SUM(COALESCE(s.cantidad_viajes, 0)) AS total_trips,
                           SUM(COALESCE(s.produccion_total, 0)) AS total_revenue,
                           COUNT(DISTINCT s.fecha) AS shift_days,
                           COUNT(*) AS shift_count,
                           COUNT(*) FILTER (WHERE s.placa IS NOT NULL) AS shifts_with_plate,
                           COUNT(*) FILTER (WHERE s.placa IS NULL) AS shifts_without_plate,
                           STRING_AGG(DISTINCT s.placa, ', ') FILTER (WHERE s.placa IS NOT NULL) AS plates
                    FROM public.module_calculated_shifts s
                    WHERE {park_filter}
                    GROUP BY s.driver_id
                    ORDER BY total_revenue DESC
                """, (park_id,))
                driver_shift_rows = cur.fetchall()

                cur.execute(f"""
                    SELECT c.driver_id,
                           COUNT(*) AS close_count,
                           COUNT(DISTINCT c.fecha) AS close_days,
                           SUM(COALESCE(c.total_ingresos, 0)) AS total_income,
                           SUM(COALESCE(c.resta, 0)) AS total_remainder,
                           STRING_AGG(DISTINCT c.placa, ', ') FILTER (WHERE c.placa IS NOT NULL) AS close_plates
                    FROM public.module_driver_closes c
                    WHERE {park_filter}
                    GROUP BY c.driver_id
                """, (park_id,))
                driver_close_rows = cur.fetchall()
                close_map = {r["driver_id"]: r for r in driver_close_rows}

                driver_detail = []
                for ds in driver_shift_rows:
                    did = ds["driver_id"]
                    close = close_map.get(did, {})
                    driver_detail.append({
                        "driver_id": did,
                        "shift_days": _safe_int(ds.get("shift_days")) or 0,
                        "total_trips": _safe_int(ds.get("total_trips")) or 0,
                        "total_revenue": _safe_float(ds.get("total_revenue")) or 0,
                        "shifts_with_plate": _safe_int(ds.get("shifts_with_plate")) or 0,
                        "shifts_without_plate": _safe_int(ds.get("shifts_without_plate")) or 0,
                        "has_closes": bool(close),
                        "close_days": _safe_int(close.get("close_days")) or 0,
                        "close_income": _safe_float(close.get("total_income")),
                        "close_remainder": _safe_float(close.get("total_remainder")),
                    })

                missing_closes_list = []
                for r in missing_closes[:50]:
                    missing_closes_list.append({
                        "driver_id": r.get("driver_id"),
                        "fecha": str(r.get("fecha")),
                        "tipo_turno": r.get("tipo_turno"),
                        "trips": _safe_int(r.get("trips")),
                        "revenue": _safe_float(r.get("revenue")),
                        "placa": r.get("placa"),
                        "duracion_minutos": _safe_int(r.get("duracion_minutos")),
                    })

                missing_plates_list = []
                for r in shift_rows:
                    if not r.get("placa"):
                        missing_plates_list.append({
                            "driver_id": r.get("driver_id"),
                            "fecha": str(r.get("fecha")),
                            "tipo_turno": r.get("tipo_turno"),
                            "trips": _safe_int(r.get("trips")),
                            "revenue": _safe_float(r.get("revenue")),
                        })

                cur.execute(f"""
                    SELECT
                        ws.week_start,
                        ws.drivers,
                        ws.trips,
                        ws.revenue,
                        b.has_billing IS NOT NULL AND b.has_billing AS has_billing
                    FROM (
                        SELECT
                            DATE_TRUNC('week', s.fecha)::date AS week_start,
                            COUNT(DISTINCT s.driver_id) AS drivers,
                            SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
                            SUM(COALESCE(s.produccion_total, 0)) AS revenue
                        FROM public.module_calculated_shifts s
                        WHERE {park_filter}
                        GROUP BY DATE_TRUNC('week', s.fecha)::date
                    ) ws
                    LEFT JOIN (
                        SELECT DISTINCT fecha_inicio AS week_start, TRUE AS has_billing
                        FROM public.module_weekly_billing
                        WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
                    ) b ON ws.week_start = b.week_start
                    ORDER BY ws.week_start DESC
                """, (park_id, park_id))
                week_rows = cur.fetchall()

                prod_no_billing = [r for r in week_rows if not r.get("has_billing")]
                billing_weeks_present = [r for r in week_rows if r.get("has_billing")]

                billing_support_list = []
                for r in billing_weeks_present:
                    billing_support_list.append({
                        "week_start": str(r.get("week_start")),
                        "drivers": _safe_int(r.get("drivers")),
                        "trips": _safe_int(r.get("trips")) or 0,
                        "revenue": _safe_float(r.get("revenue")) or 0,
                    })

                summary = []
                total_drivers = len(driver_detail)
                drivers_no_close = sum(1 for d in driver_detail if not d["has_closes"])
                drivers_no_close_pct = round(drivers_no_close / max(total_drivers, 1) * 100, 1)
                shifts_no_plate = len(missing_plates_list)
                total_shifts = len(shift_rows)
                plate_no_pct = round(shifts_no_plate / max(total_shifts, 1) * 100, 1)

                if drivers_no_close > 0:
                    summary.append({
                        "finding": f"{drivers_no_close} de {total_drivers} conductores ({drivers_no_close_pct}%) tienen produccion sin cierre.",
                        "severity": "HIGH" if drivers_no_close_pct > 50 else "MEDIUM",
                        "impact": "Liquidacion diaria no registrada para estos conductores.",
                    })
                if shifts_no_plate > 0:
                    summary.append({
                        "finding": f"{shifts_no_plate} de {total_shifts} shifts ({plate_no_pct}%) no tienen placa registrada.",
                        "severity": "HIGH" if plate_no_pct > 50 else "MEDIUM",
                        "impact": "Asignacion vehiculo-conductor incompleta.",
                    })
                if prod_no_billing:
                    summary.append({
                        "finding": f"{len(prod_no_billing)} semanas tienen produccion sin billing.",
                        "severity": "HIGH",
                        "impact": "Facturacion semanal incompleta para estas semanas.",
                    })
                if missing_closes:
                    summary.append({
                        "finding": f"{len(missing_closes)} registros de shift no tienen cierre diario asociado.",
                        "severity": "HIGH" if len(missing_closes) > 100 else "MEDIUM",
                        "impact": "Proceso de cierre diario no cubre toda la produccion.",
                    })

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "missing_driver_closes": missing_closes_list,
                    "missing_driver_closes_count": len(missing_closes),
                    "closes_without_production": [
                        {
                            "driver_id": r.get("driver_id"),
                            "fecha": str(r.get("fecha")),
                            "placa": r.get("placa"),
                            "total_ingresos": _safe_float(r.get("total_ingresos")),
                            "total_gastos": _safe_float(r.get("total_gastos")),
                            "resta": _safe_float(r.get("resta")),
                            "gnv_soles": _safe_float(r.get("gnv_soles")),
                            "gasolina_soles": _safe_float(r.get("gasolina_soles")),
                        } for r in closes_no_prod[:50]
                    ],
                    "closes_without_production_count": len(closes_no_prod),
                    "missing_plates": missing_plates_list[:50],
                    "missing_plates_count": len(missing_plates_list),
                    "plate_coverage": {
                        "shifts_with_plate": total_shifts - shifts_no_plate,
                        "shifts_without_plate": shifts_no_plate,
                        "total_shifts": total_shifts,
                        "coverage_pct": round((total_shifts - shifts_no_plate) / max(total_shifts, 1) * 100, 1),
                    },
                    "driver_close_detail": driver_detail,
                    "close_coverage": {
                        "drivers_with_close": total_drivers - drivers_no_close,
                        "drivers_without_close": drivers_no_close,
                        "total_drivers": total_drivers,
                        "coverage_pct": round((total_drivers - drivers_no_close) / max(total_drivers, 1) * 100, 1),
                    },
                    "production_without_billing": [
                        {
                            "week_start": str(r.get("week_start")),
                            "drivers": _safe_int(r.get("drivers")),
                            "trips": _safe_int(r.get("trips")) or 0,
                            "revenue": _safe_float(r.get("revenue")) or 0,
                        } for r in prod_no_billing
                    ],
                    "billing_with_support": billing_support_list,
                    "billing_weeks_count": len(billing_weeks_present),
                    "root_cause_summary": summary,
                    "notes": "Root cause analysis based on module_calculated_shifts, module_driver_closes, and module_weekly_billing.",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability root_cause: %s", e)
        return _error_response(str(e))


def _build_trust_layer_summary(coverage: dict) -> Dict[str, Any]:
    billing_weeks = coverage.get("billing_weeks", 0)
    shift_days = coverage.get("shift_days", 0)
    close_cov = coverage.get("close_driver_coverage_pct", 0)

    real_items = []
    estimated_items = []
    legacy_items = []
    not_available_items = []

    if shift_days > 0:
        real_items.append("Produccion diaria (viajes, revenue, turnos) desde module_calculated_shifts")
    else:
        not_available_items.append("Produccion diaria: sin datos de shifts")

    if close_cov >= 80:
        real_items.append("Liquidaciones de conductores (combustible, payout) desde module_driver_closes")
    elif close_cov > 0:
        estimated_items.append(f"Liquidaciones parciales ({close_cov}% cobertura). Drivers sin cierre usan supuestos.")
    else:
        estimated_items.append("Liquidaciones estimadas: sin cierres registrados. Usando supuestos de costos.")

    if billing_weeks >= 4:
        real_items.append(f"Facturacion semanal ({billing_weeks} semanas) desde module_weekly_billing")
    elif billing_weeks >= 1:
        estimated_items.append(f"Facturacion parcial ({billing_weeks} semana). Insuficiente para tendencias.")
    else:
        not_available_items.append("Facturacion semanal: sin datos de billing")

    legacy_items.append("Costos fijos diarios: estimacion basada en defaults historicos")
    not_available_items.append("Simulacion y recomendaciones: no disponible aun")

    upgrade_path = []
    if billing_weeks < 4:
        upgrade_path.append(f"Completar {4 - billing_weeks} semanas mas de billing para verdad financiera.")
    if close_cov < 80:
        upgrade_path.append(f"Mejorar cobertura de cierres de {close_cov}% a 80%+ para liquidacion real.")
    if shift_days < 7:
        upgrade_path.append("Registrar 7+ dias de shifts para cobertura operativa completa.")

    return {
        "REAL": real_items,
        "ESTIMATED": estimated_items,
        "LEGACY": legacy_items,
        "NOT_AVAILABLE": not_available_items,
        "upgrade_path": upgrade_path,
    }


SIMULATOR_LEGACY_DEFAULTS = {
    "trips_per_day": {"value": 15, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "viajes/dia"},
    "days_per_week": {"value": 6, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "dias"},
    "ticket_avg": {"value": 16.0, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "S/"},
    "km_per_trip": {"value": 9.0, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "km"},
    "fuel_cost_per_km": {"value": 0.20, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "S//km"},
    "maintenance_cost_per_km": {"value": 0.15, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "S//km"},
    "platform_commission_pct": {"value": 0.25, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "%"},
    "driver_payout_pct": {"value": 0.45, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "%"},
    "fixed_daily_cost": {"value": 15.0, "source": "LEGACY", "confidence": "LEGACY", "editable": True, "unit": "S//dia"},
    "vehicle_monthly_quota": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S//mes"},
    "insurance_gps_monthly": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S//mes"},
    "capital_to_recover": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S/"},
    "payback_target_months": {"value": 60, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "meses"},
    "weekly_bonus_day": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S//sem"},
    "weekly_bonus_night": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S//sem"},
    "guarantee_weekly": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "S//sem"},
    "wear_reserve_pct": {"value": 0.0, "source": "MANUAL", "confidence": "LEGACY", "editable": True, "unit": "%"},
}


def get_simulator_defaults(park_id: str = PARK_ID) -> Dict[str, Any]:
    inputs = {}
    for k, v in SIMULATOR_LEGACY_DEFAULTS.items():
        inputs[k] = dict(v)

    try:
        with get_db_quick(timeout_ms=10000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT
                        AVG(cantidad_viajes) AS avg_trips_day,
                        AVG(produccion_total / NULLIF(cantidad_viajes, 0)) AS avg_ticket,
                        COUNT(DISTINCT fecha) AS shift_days,
                        COUNT(DISTINCT driver_id) AS active_drivers,
                        SUM(cantidad_viajes) AS total_trips,
                        SUM(produccion_total) AS total_revenue,
                        SUM(duracion_minutos) / NULLIF(SUM(cantidad_viajes), 0) AS avg_minutes_per_trip
                    FROM public.module_calculated_shifts
                    WHERE {park_filter}
                      AND cantidad_viajes > 0
                """, (park_id,))
                shift_agg = cur.fetchone() or {}

                avg_trips_day = _safe_float(shift_agg.get("avg_trips_day"))
                avg_ticket = _safe_float(shift_agg.get("avg_ticket"))
                shift_days = _safe_int(shift_agg.get("shift_days")) or 0
                active_drivers = _safe_int(shift_agg.get("active_drivers")) or 0
                total_trips = _safe_int(shift_agg.get("total_trips")) or 0
                total_revenue = _safe_float(shift_agg.get("total_revenue")) or 0

                if avg_trips_day and avg_trips_day > 0:
                    inputs["trips_per_day"] = {"value": round(avg_trips_day, 1), "source": "OPERATIONAL", "confidence": "REAL", "editable": True, "unit": "viajes/dia"}
                if avg_ticket and avg_ticket > 0:
                    inputs["ticket_avg"] = {"value": round(avg_ticket, 2), "source": "OPERATIONAL", "confidence": "REAL", "editable": True, "unit": "S/"}

                cur.execute(f"""
                    SELECT
                        tipo_turno,
                        AVG(produccion_total) AS avg_revenue,
                        AVG(cantidad_viajes) AS avg_trips,
                        COUNT(*) AS shift_count
                    FROM public.module_calculated_shifts
                    WHERE {park_filter}
                      AND cantidad_viajes > 0
                    GROUP BY tipo_turno
                """, (park_id,))
                shift_type_rows = cur.fetchall()
                shift_breakdown = {}
                for sr in shift_type_rows:
                    st = sr.get("tipo_turno")
                    if st:
                        shift_breakdown[st] = {
                            "avg_revenue": _safe_float(sr.get("avg_revenue")),
                            "avg_trips": _safe_float(sr.get("avg_trips")),
                            "count": _safe_int(sr.get("shift_count")),
                        }

                cur.execute(f"""
                    SELECT
                        AVG(COALESCE(gnv_soles, 0) + COALESCE(gasolina_soles, 0)) AS avg_fuel_daily,
                        AVG(diferencia_odometro) AS avg_km_daily
                    FROM public.module_driver_closes
                    WHERE {park_filter}
                      AND (gnv_soles > 0 OR gasolina_soles > 0)
                """, (park_id,))
                close_agg = cur.fetchone() or {}
                avg_fuel_daily = _safe_float(close_agg.get("avg_fuel_daily"))
                avg_km_daily = _safe_float(close_agg.get("avg_km_daily"))

                if avg_km_daily and avg_km_daily > 0 and avg_trips_day and avg_trips_day > 0:
                    km_per_trip = round(avg_km_daily / avg_trips_day, 2)
                    inputs["km_per_trip"] = {"value": km_per_trip, "source": "OPERATIONAL", "confidence": "REAL", "editable": True, "unit": "km"}

                if avg_fuel_daily and avg_km_daily and avg_km_daily > 0:
                    fuel_per_km = round(avg_fuel_daily / avg_km_daily, 4)
                    inputs["fuel_cost_per_km"] = {"value": fuel_per_km, "source": "OPERATIONAL", "confidence": "REAL", "editable": True, "unit": "S//km"}

                derived = {}
                trips_week = inputs["trips_per_day"]["value"] * inputs["days_per_week"]["value"]
                ticket = inputs["ticket_avg"]["value"]
                km_trip = inputs["km_per_trip"]["value"]
                derived["gross_revenue_week"] = {"value": round(trips_week * ticket, 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S/"}
                derived["km_week"] = {"value": round(trips_week * km_trip, 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "km"}
                derived["fuel_cost_week"] = {"value": round(trips_week * km_trip * inputs["fuel_cost_per_km"]["value"], 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S/"}
                derived["maintenance_cost_week"] = {"value": round(trips_week * km_trip * inputs["maintenance_cost_per_km"]["value"], 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S/"}
                rev_net = trips_week * ticket * (1 - inputs["platform_commission_pct"]["value"])
                derived["net_revenue_week"] = {"value": round(rev_net, 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S/"}
                derived["driver_payout_week"] = {"value": round(rev_net * inputs["driver_payout_pct"]["value"], 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S/"}
                derived["revenue_per_km"] = {"value": round(ticket / max(km_trip, 0.1), 2), "source": "DERIVED", "confidence": "ESTIMATED", "unit": "S//km"}

                operational_context = {
                    "shift_days_available": shift_days,
                    "active_drivers": active_drivers,
                    "total_trips": total_trips,
                    "total_revenue": total_revenue,
                    "shift_breakdown": shift_breakdown,
                }

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "inputs": inputs,
                    "derived": derived,
                    "operational_context": operational_context,
                    "source_priority": SOURCE_PRIORITY,
                    "notes": "Inputs OPERATIONAL provienen de produccion real. Inputs LEGACY son supuestos del modelo Excel.",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability simulator defaults: %s", e)
        return {
            "status": "OK",
            "park_id": park_id,
            "inputs": inputs,
            "derived": {},
            "operational_context": {},
            "notes": f"Usando defaults legacy. Error al consultar data operativa: {str(e)[:200]}",
        }


def run_simulation(params: Dict[str, Any]) -> Dict[str, Any]:
    trips_per_day = float(params.get("trips_per_day", 15))
    days_per_week = float(params.get("days_per_week", 6))
    ticket_avg = float(params.get("ticket_avg", 16))
    km_per_trip = float(params.get("km_per_trip", 9))
    fuel_cost_per_km = float(params.get("fuel_cost_per_km", 0.20))
    maintenance_cost_per_km = float(params.get("maintenance_cost_per_km", 0.15))
    platform_commission_pct = float(params.get("platform_commission_pct", 0.25))
    driver_payout_pct = float(params.get("driver_payout_pct", 0.45))
    fixed_daily_cost = float(params.get("fixed_daily_cost", 15))
    weekly_bonus_day = float(params.get("weekly_bonus_day", 0))
    weekly_bonus_night = float(params.get("weekly_bonus_night", 0))
    guarantee_weekly = float(params.get("guarantee_weekly", 0))
    vehicle_monthly_quota = float(params.get("vehicle_monthly_quota", 0))
    insurance_gps_monthly = float(params.get("insurance_gps_monthly", 0))
    capital_to_recover = float(params.get("capital_to_recover", 0))
    payback_target_months = float(params.get("payback_target_months", 60))
    wear_reserve_pct = float(params.get("wear_reserve_pct", 0))
    scenario_name = params.get("scenario_name", "Escenario")

    trips_week = trips_per_day * days_per_week
    gross_revenue_week = trips_week * ticket_avg
    km_week = trips_week * km_per_trip

    platform_commission = gross_revenue_week * platform_commission_pct
    net_revenue = gross_revenue_week - platform_commission

    fuel_cost = km_week * fuel_cost_per_km
    maintenance_cost = km_week * maintenance_cost_per_km
    fixed_cost = fixed_daily_cost * days_per_week
    vehicle_weekly = vehicle_monthly_quota / 4.33
    insurance_weekly = insurance_gps_monthly / 4.33

    driver_payout = net_revenue * driver_payout_pct
    bonuses = weekly_bonus_day + weekly_bonus_night

    guarantee_adjustment = 0.0
    if guarantee_weekly > 0 and driver_payout < guarantee_weekly:
        guarantee_adjustment = guarantee_weekly - driver_payout

    wear_reserve = gross_revenue_week * wear_reserve_pct if wear_reserve_pct > 0 else 0

    total_costs = (
        platform_commission
        + fuel_cost
        + maintenance_cost
        + fixed_cost
        + driver_payout
        + bonuses
        + guarantee_adjustment
        + vehicle_weekly
        + insurance_weekly
        + wear_reserve
    )

    net_profit_week = gross_revenue_week - total_costs
    net_profit_month = net_profit_week * 4.33
    margin_pct = net_profit_week / max(gross_revenue_week, 1)

    driver_income_week = driver_payout + bonuses + guarantee_adjustment
    driver_income_month = driver_income_week * 4.33

    if net_profit_month > 0 and capital_to_recover > 0:
        company_recovery_months = capital_to_recover / net_profit_month
    elif capital_to_recover > 0:
        company_recovery_months = None
    else:
        company_recovery_months = 0

    payback_gap_months = None
    if company_recovery_months is not None and payback_target_months > 0:
        payback_gap_months = round(company_recovery_months - payback_target_months, 1)

    break_even_costs_week = (
        fuel_cost + maintenance_cost + fixed_cost
        + vehicle_weekly + insurance_weekly + wear_reserve
    )
    if ticket_avg > 0 and driver_payout_pct < 1:
        net_per_trip = ticket_avg * (1 - platform_commission_pct) * (1 - driver_payout_pct) - (km_per_trip * (fuel_cost_per_km + maintenance_cost_per_km))
        break_even_trips_week = break_even_costs_week / max(net_per_trip, 0.01) if net_per_trip > 0 else None
    else:
        break_even_trips_week = None

    break_even_revenue_week = break_even_trips_week * ticket_avg if break_even_trips_week else None

    if margin_pct >= 0.10:
        status = "VIABLE"
    elif margin_pct >= 0:
        status = "RISKY"
    else:
        status = "LOSS"

    confidence_items = []
    for k in ["trips_per_day", "ticket_avg", "km_per_trip", "fuel_cost_per_km"]:
        src = params.get(f"{k}_source", "MANUAL")
        confidence_items.append({"input": k, "source": src})

    return {
        "status": "OK",
        "scenario_name": scenario_name,
        "inputs_used": {
            "trips_per_day": trips_per_day,
            "days_per_week": days_per_week,
            "ticket_avg": ticket_avg,
            "km_per_trip": km_per_trip,
            "fuel_cost_per_km": fuel_cost_per_km,
            "maintenance_cost_per_km": maintenance_cost_per_km,
            "platform_commission_pct": platform_commission_pct,
            "driver_payout_pct": driver_payout_pct,
            "fixed_daily_cost": fixed_daily_cost,
            "weekly_bonus_day": weekly_bonus_day,
            "weekly_bonus_night": weekly_bonus_night,
            "guarantee_weekly": guarantee_weekly,
            "vehicle_monthly_quota": vehicle_monthly_quota,
            "insurance_gps_monthly": insurance_gps_monthly,
            "capital_to_recover": capital_to_recover,
            "payback_target_months": payback_target_months,
            "wear_reserve_pct": wear_reserve_pct,
        },
        "results": {
            "gross_revenue_week": round(gross_revenue_week, 2),
            "platform_commission": round(platform_commission, 2),
            "net_revenue_week": round(net_revenue, 2),
            "fuel_cost": round(fuel_cost, 2),
            "maintenance_cost": round(maintenance_cost, 2),
            "fixed_cost": round(fixed_cost, 2),
            "vehicle_weekly_cost": round(vehicle_weekly, 2),
            "insurance_weekly_cost": round(insurance_weekly, 2),
            "driver_payout": round(driver_payout, 2),
            "bonuses": round(bonuses, 2),
            "guarantee_adjustment": round(guarantee_adjustment, 2),
            "wear_reserve": round(wear_reserve, 2),
            "total_costs": round(total_costs, 2),
            "net_profit_week": round(net_profit_week, 2),
            "net_profit_month": round(net_profit_month, 2),
            "margin_pct": round(margin_pct, 4),
            "driver_income_week": round(driver_income_week, 2),
            "driver_income_month": round(driver_income_month, 2),
            "company_recovery_months": round(company_recovery_months, 1) if company_recovery_months is not None else None,
            "payback_gap_months": payback_gap_months,
            "break_even_trips_week": round(break_even_trips_week, 1) if break_even_trips_week else None,
            "break_even_revenue_week": round(break_even_revenue_week, 2) if break_even_revenue_week else None,
            "trips_week": round(trips_week, 1),
            "km_week": round(km_week, 1),
            "status": status,
        },
        "confidence": confidence_items,
        "explanation": _build_simulation_explanation(status, margin_pct, net_profit_week, driver_income_week, company_recovery_months, payback_target_months),
    }


def _build_simulation_explanation(status: str, margin_pct: float, net_profit_week: float, driver_income_week: float, recovery_months, payback_target: float) -> str:
    lines = []
    if status == "VIABLE":
        lines.append(f"Escenario viable: margen {margin_pct*100:.1f}%, utilidad semanal S/ {net_profit_week:.2f}.")
    elif status == "RISKY":
        lines.append(f"Escenario riesgoso: margen {margin_pct*100:.1f}%. Utilidad positiva pero baja.")
    else:
        lines.append(f"Escenario en perdida: margen {margin_pct*100:.1f}%, perdida semanal S/ {abs(net_profit_week):.2f}.")

    lines.append(f"Ingreso conductor semanal: S/ {driver_income_week:.2f}.")

    if recovery_months is not None and recovery_months > 0:
        if recovery_months <= payback_target:
            lines.append(f"Payback en {recovery_months:.0f} meses (dentro del objetivo de {payback_target:.0f}).")
        else:
            lines.append(f"Payback en {recovery_months:.0f} meses (excede objetivo de {payback_target:.0f} meses).")
    elif recovery_months is None:
        lines.append("No es posible recuperar capital con utilidad negativa.")

    return " ".join(lines)


def _missing_source_response(view_name: str, remediation: str) -> Dict[str, Any]:
    return {
        "status": "MISSING_SOURCE",
        "missing_view": view_name,
        "remediation": remediation,
        "message": f"Serving view {view_name} does not exist. Create it first.",
    }


def _error_response(error: str) -> Dict[str, Any]:
    return {
        "status": "ERROR",
        "error": error[:500],
        "remediation": "Check database connectivity and view existence.",
    }
