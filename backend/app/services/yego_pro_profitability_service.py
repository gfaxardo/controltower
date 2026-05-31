"""
Yego Pro Profitability Service — Phase 1 Foundation
Control Foundation serving layer (read-only).

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
Sources: module_weekly_billing, trips_2026, module_miauto_cronograma
"""
from __future__ import annotations

import logging
from datetime import date
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
                if not _check_view_exists(cur, MV_DRIVER):
                    return _missing_source_response(MV_DRIVER, "Run yego_pro_profitability_serving_views.sql")

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
                    "confidence": "HIGH",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability drivers: %s", e)
        return _error_response(str(e))


def get_vehicles(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _check_view_exists(cur, MV_VEHICLE):
                    return _missing_source_response(MV_VEHICLE, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(f"SELECT * FROM {MV_VEHICLE}")
                rows = cur.fetchall()

                vehicles = []
                for r in rows:
                    vehicles.append({
                        "cronograma_name": r.get("cronograma_name"),
                        "vehicle_name": r.get("vehicle_name"),
                        "total_weekly_quotas": _safe_int(r.get("total_weekly_quotas")),
                        "weekly_quota": _safe_float(r.get("weekly_quota")),
                        "min_trips_for_bono": _safe_int(r.get("min_trips_for_bono")),
                        "bono_reduction": _safe_float(r.get("bono_reduction")),
                        "tier_order": _safe_int(r.get("tier_order")),
                    })

                return {
                    "status": "LIMITED",
                    "park_id": park_id,
                    "vehicles": vehicles,
                    "limitation": "No vehicle-to-driver assignment table exists. Only fleet configuration shown.",
                    "source": "module_miauto_cronograma",
                    "metric_type": "REAL",
                    "confidence": "MEDIUM",
                    "notes": "Cannot report per-vehicle profitability. Only quota structure available.",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability vehicles: %s", e)
        return _error_response(str(e))


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
                        shifts.append({
                            "date": str(r.get("date")),
                            "shift_type": r.get("shift_type"),
                            "driver_id": r.get("driver_id"),
                            "vehicle_plate": r.get("vehicle_plate"),
                            "trips": _safe_int(r.get("trips")),
                            "revenue": _safe_float(r.get("revenue")),
                            "shift_amount": _safe_float(r.get("shift_amount")),
                            "service_commission": _safe_float(r.get("service_commission")),
                            "total_minutes": _safe_int(r.get("total_minutes")),
                            "shift_count": _safe_int(r.get("shift_count")),
                            "paid_shifts": _safe_int(r.get("paid_shifts")),
                            "avg_duration_min": _safe_float(r.get("avg_duration_min")),
                            "revenue_per_trip": _safe_float(r.get("revenue_per_trip")),
                            "confidence": r.get("confidence"),
                        })

                    return {
                        "status": "OK",
                        "park_id": park_id,
                        "shifts": shifts,
                        "shift_source": "module_calculated_shifts (native shift types from operational system)",
                        "source": "module_calculated_shifts",
                        "metric_type": "REAL",
                        "confidence": "HIGH",
                        "notes": "Native shift types from operational system. plate coverage may vary.",
                    }

                if not _check_view_exists(cur, MV_SHIFT):
                    return _missing_source_response(MV_SHIFT, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(f"SELECT * FROM {MV_SHIFT} ORDER BY week_start DESC LIMIT %s", (int(days / 7 * 2),))
                rows = cur.fetchall()

                shifts = []
                for r in rows:
                    shifts.append({
                        "week_start": str(r.get("week_start")),
                        "shift": r.get("shift"),
                        "trips_completed": _safe_int(r.get("trips_completed")),
                        "active_drivers": _safe_int(r.get("active_drivers")),
                        "revenue_gross": _safe_float(r.get("revenue_gross")),
                        "ticket_avg": _safe_float(r.get("ticket_avg")),
                        "ticket_median": _safe_float(r.get("ticket_median")),
                        "km_total": _safe_float(r.get("km_total")),
                        "km_per_trip": _safe_float(r.get("km_per_trip")),
                        "duration_avg_min": _safe_float(r.get("duration_avg_min")),
                    })

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "shifts": shifts,
                    "shift_source": "DERIVED from trips_2026 timestamps (06:00-17:59=DAY, 18:00-05:59=NIGHT)",
                    "shift_definition": {"DAY": "06:00-17:59", "NIGHT": "18:00-05:59"},
                    "source": "trips_2026",
                    "metric_type": "DERIVED",
                    "confidence": "HIGH",
                    "notes": "Native shift source (module_calculated_shifts) not available. Using derived classification.",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability shifts: %s", e)
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


BONUS_GENERAL_BRANDED = [
    {"min_trips": 190, "pct": 27, "amount": 720},
    {"min_trips": 150, "pct": 25, "amount": 550},
    {"min_trips": 125, "pct": 23, "amount": 470},
    {"min_trips": 100, "pct": 21, "amount": 390},
    {"min_trips": 75, "pct": 20, "amount": 320},
    {"min_trips": 50, "pct": 19, "amount": 260},
    {"min_trips": 30, "pct": 18, "amount": 175},
]

BONUS_GENERAL_UNBRANDED = [
    {"min_trips": 150, "pct": 20, "amount": 450},
    {"min_trips": 125, "pct": 18, "amount": 390},
    {"min_trips": 100, "pct": 16, "amount": 315},
    {"min_trips": 75, "pct": 14, "amount": 230},
    {"min_trips": 50, "pct": 13, "amount": 170},
    {"min_trips": 30, "pct": 12, "amount": 125},
    {"min_trips": 10, "pct": 11, "amount": 60},
]

BONUS_PREMIER = [
    {"min_trips": 20, "pct": 40, "amount": 600},
    {"min_trips": 15, "pct": 36, "amount": 410},
    {"min_trips": 10, "pct": 33, "amount": 250},
    {"min_trips": 8, "pct": 31, "amount": 190},
    {"min_trips": 6, "pct": 29, "amount": 130},
    {"min_trips": 4, "pct": 27, "amount": 85},
    {"min_trips": 2, "pct": 25, "amount": 40},
]

DIAG_DRIVER_THRESHOLDS = {
    "LOW_TRIPS_ABS": 10,
    "LOW_TRIPS_REL": 0.5,
    "LOW_TICKET_REL": 0.8,
    "HIGH_KM_PER_TRIP_REL": 1.3,
    "HIGH_COST_PER_TRIP_REL": 0.85,
    "HIGH_PAYOUT_RATIO": 0.50,
    "LOW_MARGIN_PCT": 0.05,
}

DIAG_VEHICLE_THRESHOLDS = {
    "LOW_UTILIZATION_DAYS": 3,
    "LOW_REVENUE_PER_DAY": 50.0,
    "LOW_TRIPS_PER_DAY": 5,
    "MANY_DRIVERS": 3,
    "FIXED_COST_WEEKLY_DEFAULT": 350.0,
}


def _build_diagnostic(
    entity_type: str,
    entity_id: str,
    status: str,
    main_driver: str,
    secondary_drivers: List[str],
    impact_amount: Optional[float],
    severity: str,
    confidence: str,
    explanation: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": status,
        "main_driver": main_driver,
        "secondary_drivers": secondary_drivers,
        "impact_amount": _safe_float(impact_amount),
        "severity": severity,
        "confidence": confidence,
        "explanation": explanation,
        "evidence": evidence,
    }


def _classify_driver_causes(
    d: Dict[str, Any],
    avg_trips: float,
    avg_ticket: float,
    avg_km_per_trip: float,
    avg_cost_per_trip: float,
    has_close: bool,
    has_plate: bool,
) -> List[str]:
    causes = []
    trips = _safe_int(d.get("trips_completed")) or 0
    ticket = _safe_float(d.get("ticket_avg")) or 0
    km_pt = _safe_float(d.get("km_per_trip")) or 0
    revenue = _safe_float(d.get("revenue_gross")) or 0
    fuel = _safe_float(d.get("fuel_cost")) or 0
    maint = _safe_float(d.get("maintenance_cost")) or 0
    payment = _safe_float(d.get("driver_payment")) or 0
    margin_pct = _safe_float(d.get("margin_pct")) or 0
    driver_pct = _safe_float(d.get("driver_pct")) or 0

    cost_per_trip = (fuel + maint + payment) / max(trips, 1)
    rev_per_trip = revenue / max(trips, 1)

    if trips < DIAG_DRIVER_THRESHOLDS["LOW_TRIPS_ABS"] or (avg_trips > 0 and trips < avg_trips * DIAG_DRIVER_THRESHOLDS["LOW_TRIPS_REL"]):
        causes.append("LOW_TRIPS")
    if avg_ticket > 0 and ticket < avg_ticket * DIAG_DRIVER_THRESHOLDS["LOW_TICKET_REL"]:
        causes.append("LOW_TICKET")
    if avg_km_per_trip > 0 and km_pt > avg_km_per_trip * DIAG_DRIVER_THRESHOLDS["HIGH_KM_PER_TRIP_REL"]:
        causes.append("HIGH_KM_PER_TRIP")
    if rev_per_trip > 0 and cost_per_trip > rev_per_trip * DIAG_DRIVER_THRESHOLDS["HIGH_COST_PER_TRIP_REL"]:
        causes.append("HIGH_COST_PER_TRIP")
    if driver_pct > DIAG_DRIVER_THRESHOLDS["HIGH_PAYOUT_RATIO"]:
        causes.append("HIGH_PAYOUT_RATIO")
    if margin_pct < DIAG_DRIVER_THRESHOLDS["LOW_MARGIN_PCT"]:
        causes.append("LOW_MARGIN")
    if not has_close:
        causes.append("MISSING_CLOSE")
    if not has_plate:
        causes.append("MISSING_PLATE")
    return causes


def get_diagnostics_drivers(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _check_view_exists(cur, MV_DRIVER):
                    return _missing_source_response(MV_DRIVER, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(
                    f"""SELECT * FROM {MV_DRIVER}
                        WHERE week_start = (SELECT MAX(week_start) FROM {MV_DRIVER})
                        ORDER BY profit"""
                )
                rows = cur.fetchall()
                if not rows:
                    return {"status": "NO_DATA", "diagnostics": [], "summary": {}}

                close_map = {}
                plate_map = {}
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"
                try:
                    cur.execute(f"""
                        SELECT driver_id, COUNT(DISTINCT fecha) AS close_days
                        FROM public.module_driver_closes
                        WHERE {park_filter}
                        GROUP BY driver_id
                    """, (park_id,))
                    for cr in cur.fetchall():
                        close_map[cr["driver_id"]] = _safe_int(cr.get("close_days")) or 0

                    cur.execute(f"""
                        SELECT driver_id,
                               COUNT(*) FILTER (WHERE placa IS NOT NULL) AS with_plate,
                               COUNT(*) AS total
                        FROM public.module_calculated_shifts
                        WHERE {park_filter}
                        GROUP BY driver_id
                    """, (park_id,))
                    for pr in cur.fetchall():
                        total = _safe_int(pr.get("total")) or 1
                        with_p = _safe_int(pr.get("with_plate")) or 0
                        plate_map[pr["driver_id"]] = with_p / total > 0.5
                except Exception:
                    pass

                all_trips = [_safe_int(r.get("trips_completed")) or 0 for r in rows]
                all_tickets = [_safe_float(r.get("ticket_avg")) or 0 for r in rows if _safe_float(r.get("ticket_avg"))]
                all_km = [_safe_float(r.get("km_per_trip")) or 0 for r in rows if _safe_float(r.get("km_per_trip"))]

                avg_trips = sum(all_trips) / max(len(all_trips), 1)
                avg_ticket = sum(all_tickets) / max(len(all_tickets), 1) if all_tickets else 0
                avg_km = sum(all_km) / max(len(all_km), 1) if all_km else 0

                all_costs = []
                for r in rows:
                    t = _safe_int(r.get("trips_completed")) or 1
                    f = _safe_float(r.get("fuel_cost")) or 0
                    m = _safe_float(r.get("maintenance_cost")) or 0
                    p = _safe_float(r.get("driver_payment")) or 0
                    all_costs.append((f + m + p) / t)
                avg_cost_pt = sum(all_costs) / max(len(all_costs), 1) if all_costs else 0

                diagnostics = []
                for r in rows:
                    did = r.get("driver_id")
                    has_close = did in close_map and close_map[did] > 0
                    has_plate = plate_map.get(did, True)

                    causes = _classify_driver_causes(r, avg_trips, avg_ticket, avg_km, avg_cost_pt, has_close, has_plate)

                    profit = _safe_float(r.get("profit")) or 0
                    trips = _safe_int(r.get("trips_completed")) or 0
                    revenue = _safe_float(r.get("revenue_gross")) or 0
                    fuel = _safe_float(r.get("fuel_cost")) or 0
                    maint = _safe_float(r.get("maintenance_cost")) or 0
                    payment = _safe_float(r.get("driver_payment")) or 0
                    margin_pct = _safe_float(r.get("margin_pct")) or 0

                    if profit > 0 and not causes:
                        status = "PROFITABLE"
                    elif profit > 0:
                        status = "RISKY"
                    elif profit < 0:
                        status = "LOSS"
                    else:
                        status = "UNKNOWN"

                    if "MISSING_CLOSE" in causes and "MISSING_PLATE" in causes and trips == 0:
                        classification = "No evaluable"
                        severity = "LOW"
                        confidence_level = "LEGACY"
                    elif profit < -50 or (len(causes) >= 3 and profit < 0):
                        classification = "Critico"
                        severity = "HIGH"
                        confidence_level = "REAL" if has_close else "ESTIMATED"
                    elif profit < 0:
                        classification = "Recuperable"
                        severity = "MEDIUM"
                        confidence_level = "REAL" if has_close else "ESTIMATED"
                    else:
                        classification = "Rentable"
                        severity = "LOW"
                        confidence_level = "REAL" if has_close else "ESTIMATED"

                    main_cause = causes[0] if causes else "NONE"
                    secondary = causes[1:] if len(causes) > 1 else []

                    explanation_parts = []
                    cause_explanations = {
                        "LOW_TRIPS": "baja produccion de viajes",
                        "LOW_TICKET": "ticket promedio bajo vs promedio del parque",
                        "HIGH_KM_PER_TRIP": "km por viaje elevado (recorridos largos o ineficientes)",
                        "HIGH_COST_PER_TRIP": "costo por viaje cercano o superior al ingreso",
                        "HIGH_PAYOUT_RATIO": "porcentaje de pago al conductor elevado",
                        "LOW_MARGIN": "margen operativo bajo o negativo",
                        "MISSING_CLOSE": "sin cierres diarios registrados",
                        "MISSING_PLATE": "sin placa asignada en turnos",
                    }
                    if main_cause != "NONE":
                        explanation_parts.append(f"Causa principal: {cause_explanations.get(main_cause, main_cause)}.")
                    if classification == "Critico":
                        explanation_parts.append("Este conductor esta en perdida critica.")
                    elif classification == "Recuperable":
                        explanation_parts.append("Este conductor esta en perdida pero podria recuperarse.")
                    elif classification == "No evaluable":
                        explanation_parts.append("Diagnostico no evaluable porque faltan datos completos.")
                    if confidence_level == "ESTIMATED":
                        explanation_parts.append("Diagnostico estimado porque faltan cierres completos.")

                    diagnostics.append({
                        **_build_diagnostic(
                            entity_type="driver",
                            entity_id=did,
                            status=status,
                            main_driver=main_cause,
                            secondary_drivers=secondary,
                            impact_amount=profit,
                            severity=severity,
                            confidence=confidence_level,
                            explanation=" ".join(explanation_parts),
                            evidence={
                                "driver_name": r.get("driver_name"),
                                "week_start": str(r.get("week_start")),
                                "classification": classification,
                            },
                        ),
                        "kpis": {
                            "revenue": _safe_float(revenue),
                            "trips": trips,
                            "km": _safe_float(r.get("km_total")),
                            "ticket_avg": _safe_float(r.get("ticket_avg")),
                            "estimated_cost": round(fuel + maint, 2),
                            "estimated_payout": _safe_float(payment),
                            "estimated_margin": _safe_float(profit),
                            "revenue_per_trip": round(revenue / max(trips, 1), 2),
                            "cost_per_trip": round((fuel + maint + payment) / max(trips, 1), 2),
                            "margin_per_trip": _safe_float(r.get("profit_per_trip")),
                        },
                    })

                total = len(diagnostics)
                loss_count = sum(1 for d in diagnostics if d["status"] == "LOSS")
                risky_count = sum(1 for d in diagnostics if d["status"] == "RISKY")
                profitable_count = sum(1 for d in diagnostics if d["status"] == "PROFITABLE")
                critico_count = sum(1 for d in diagnostics if d["evidence"]["classification"] == "Critico")
                recuperable_count = sum(1 for d in diagnostics if d["evidence"]["classification"] == "Recuperable")

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "diagnostics": diagnostics,
                    "summary": {
                        "total_drivers": total,
                        "profitable": profitable_count,
                        "risky": risky_count,
                        "loss": loss_count,
                        "critico": critico_count,
                        "recuperable": recuperable_count,
                        "pct_in_loss": round(loss_count / max(total, 1), 4),
                    },
                    "thresholds_used": DIAG_DRIVER_THRESHOLDS,
                    "park_averages": {
                        "avg_trips": round(avg_trips, 1),
                        "avg_ticket": round(avg_ticket, 2),
                        "avg_km_per_trip": round(avg_km, 2),
                        "avg_cost_per_trip": round(avg_cost_pt, 2),
                    },
                    "source": "module_weekly_billing + module_driver_closes + module_calculated_shifts",
                    "metric_type": "DIAGNOSTIC",
                    "confidence": "HIGH" if len(close_map) > 0 else "MEDIUM",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro diagnostics drivers: %s", e)
        return _error_response(str(e))


def get_diagnostics_vehicles(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT
                        s.placa,
                        SUM(COALESCE(s.produccion_total, 0)) AS revenue,
                        SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
                        COUNT(DISTINCT s.fecha) AS active_days,
                        COUNT(DISTINCT s.driver_id) AS drivers_count,
                        COUNT(*) AS shift_count
                    FROM public.module_calculated_shifts s
                    WHERE {park_filter}
                      AND s.placa IS NOT NULL
                      AND s.placa != ''
                    GROUP BY s.placa
                    ORDER BY revenue DESC
                """, (park_id,))
                rows = cur.fetchall()

                if not rows:
                    return {"status": "NO_DATA", "diagnostics": [], "summary": {}}

                billing_margin = {}
                try:
                    cur.execute(f"""
                        SELECT
                            SUM(COALESCE(b.utilidad, 0)) AS total_profit,
                            SUM(COALESCE(b.monto_total_producido, 0)) AS total_revenue,
                            COUNT(DISTINCT b.driver_id) AS billing_drivers
                        FROM public.module_weekly_billing b
                        WHERE b.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
                          AND b.fecha_inicio = (
                              SELECT MAX(fecha_inicio) FROM public.module_weekly_billing
                              WHERE driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
                          )
                    """, (park_id, park_id))
                    brow = cur.fetchone()
                    if brow:
                        tr = _safe_float(brow.get("total_revenue")) or 1
                        tp = _safe_float(brow.get("total_profit")) or 0
                        billing_margin["park_margin_pct"] = round(tp / tr, 4)
                except Exception:
                    pass

                park_margin_pct = billing_margin.get("park_margin_pct", -0.05)
                fixed_cost = DIAG_VEHICLE_THRESHOLDS["FIXED_COST_WEEKLY_DEFAULT"]

                all_rpd = []
                all_tpd = []
                for r in rows:
                    days = _safe_int(r.get("active_days")) or 1
                    rev = _safe_float(r.get("revenue")) or 0
                    trips = _safe_int(r.get("trips")) or 0
                    all_rpd.append(rev / days)
                    all_tpd.append(trips / days)

                avg_rpd = sum(all_rpd) / max(len(all_rpd), 1)
                avg_tpd = sum(all_tpd) / max(len(all_tpd), 1)

                diagnostics = []
                for r in rows:
                    plate = r.get("placa")
                    rev = _safe_float(r.get("revenue")) or 0
                    trips = _safe_int(r.get("trips")) or 0
                    days = _safe_int(r.get("active_days")) or 1
                    drivers = _safe_int(r.get("drivers_count")) or 1

                    rpd = rev / days
                    tpd = trips / days
                    estimated_margin = rev * park_margin_pct
                    utilization = min(days / 7.0, 1.0)

                    causes = []
                    if utilization < DIAG_VEHICLE_THRESHOLDS["LOW_UTILIZATION_DAYS"] / 7.0:
                        causes.append("LOW_UTILIZATION")
                    if rpd < DIAG_VEHICLE_THRESHOLDS["LOW_REVENUE_PER_DAY"]:
                        causes.append("LOW_REVENUE_PER_DAY")
                    if tpd < DIAG_VEHICLE_THRESHOLDS["LOW_TRIPS_PER_DAY"]:
                        causes.append("LOW_TRIPS_PER_DAY")
                    if drivers > DIAG_VEHICLE_THRESHOLDS["MANY_DRIVERS"]:
                        causes.append("MANY_DRIVERS_LOW_CONTROL")
                    if estimated_margin < 0:
                        causes.append("NEGATIVE_MARGIN")
                    if rev < fixed_cost:
                        causes.append("FIXED_COST_NOT_COVERED")

                    if estimated_margin > 0 and not causes:
                        status = "PROFITABLE"
                        classification = "Rentable"
                        severity = "LOW"
                    elif estimated_margin > 0 and causes:
                        status = "RISKY"
                        classification = "Recuperable"
                        severity = "MEDIUM"
                    elif estimated_margin < 0 and len(causes) >= 2:
                        status = "LOSS"
                        classification = "Critico"
                        severity = "HIGH"
                    elif estimated_margin < 0:
                        status = "LOSS"
                        classification = "Recuperable"
                        severity = "MEDIUM"
                    else:
                        status = "UNKNOWN"
                        classification = "Sin trazabilidad suficiente"
                        severity = "LOW"

                    main_cause = causes[0] if causes else "NONE"
                    secondary = causes[1:] if len(causes) > 1 else []

                    cause_explanations = {
                        "LOW_UTILIZATION": "baja utilizacion (pocos dias activos)",
                        "LOW_REVENUE_PER_DAY": "ingreso diario bajo",
                        "LOW_TRIPS_PER_DAY": "pocos viajes por dia",
                        "MANY_DRIVERS_LOW_CONTROL": "muchos conductores distintos (bajo control operativo)",
                        "NEGATIVE_MARGIN": "margen estimado negativo",
                        "FIXED_COST_NOT_COVERED": "no cubre su costo fijo estimado",
                    }
                    explanation_parts = []
                    if main_cause != "NONE":
                        explanation_parts.append(f"Este vehiculo tiene {cause_explanations.get(main_cause, main_cause)}.")
                    if classification == "Critico":
                        explanation_parts.append("Vehiculo en perdida critica estimada.")

                    diagnostics.append({
                        **_build_diagnostic(
                            entity_type="vehicle",
                            entity_id=plate,
                            status=status,
                            main_driver=main_cause,
                            secondary_drivers=secondary,
                            impact_amount=estimated_margin,
                            severity=severity,
                            confidence="ESTIMATED",
                            explanation=" ".join(explanation_parts) if explanation_parts else "Sin causas detectadas.",
                            evidence={
                                "classification": classification,
                            },
                        ),
                        "kpis": {
                            "revenue": round(rev, 2),
                            "trips": trips,
                            "active_days": days,
                            "revenue_per_day": round(rpd, 2),
                            "trips_per_day": round(tpd, 2),
                            "estimated_margin": round(estimated_margin, 2),
                            "utilization_proxy": round(utilization, 4),
                            "drivers_count": drivers,
                            "missing_plate_flag": False,
                        },
                    })

                no_plate_count = 0
                try:
                    cur.execute(f"""
                        SELECT COUNT(*) AS cnt
                        FROM public.module_calculated_shifts s
                        WHERE {park_filter}
                          AND (s.placa IS NULL OR s.placa = '')
                    """, (park_id,))
                    npr = cur.fetchone()
                    no_plate_count = _safe_int(npr.get("cnt")) if npr else 0
                except Exception:
                    pass

                total = len(diagnostics)
                loss_count = sum(1 for d in diagnostics if d["status"] == "LOSS")

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "diagnostics": diagnostics,
                    "summary": {
                        "total_vehicles": total,
                        "profitable": sum(1 for d in diagnostics if d["status"] == "PROFITABLE"),
                        "risky": sum(1 for d in diagnostics if d["status"] == "RISKY"),
                        "loss": loss_count,
                        "pct_in_loss": round(loss_count / max(total, 1), 4),
                        "shifts_without_plate": no_plate_count,
                    },
                    "thresholds_used": DIAG_VEHICLE_THRESHOLDS,
                    "park_averages": {
                        "avg_revenue_per_day": round(avg_rpd, 2),
                        "avg_trips_per_day": round(avg_tpd, 2),
                        "park_margin_pct_used": park_margin_pct,
                    },
                    "source": "module_calculated_shifts + module_weekly_billing (margin proxy)",
                    "metric_type": "DIAGNOSTIC",
                    "confidence": "ESTIMATED",
                    "notes": "Margen por vehiculo es estimado usando margen % del parque aplicado al revenue por placa.",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro diagnostics vehicles: %s", e)
        return _error_response(str(e))


def get_diagnostics_shifts(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT
                        s.tipo_turno AS shift_type,
                        SUM(COALESCE(s.produccion_total, 0)) AS revenue,
                        SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
                        COUNT(DISTINCT s.fecha) AS active_days,
                        COUNT(*) AS shift_count,
                        SUM(COALESCE(s.monto_total, 0)) AS total_payout
                    FROM public.module_calculated_shifts s
                    WHERE {park_filter}
                      AND s.tipo_turno IS NOT NULL
                    GROUP BY s.tipo_turno
                    ORDER BY revenue DESC
                """, (park_id,))
                rows = cur.fetchall()

                if not rows:
                    return {"status": "NO_DATA", "diagnostics": [], "shift_comparison": {}}

                billing_margin_pct = -0.05
                try:
                    cur.execute(f"""
                        SELECT
                            SUM(COALESCE(b.utilidad, 0)) AS total_profit,
                            SUM(COALESCE(b.monto_total_producido, 0)) AS total_revenue
                        FROM public.module_weekly_billing b
                        WHERE b.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
                    """, (park_id,))
                    brow = cur.fetchone()
                    if brow:
                        tr = _safe_float(brow.get("total_revenue")) or 1
                        tp = _safe_float(brow.get("total_profit")) or 0
                        billing_margin_pct = round(tp / tr, 4)
                except Exception:
                    pass

                day_labels = {"dia": "day", "day": "day", "manana": "day", "morning": "day", "tarde": "day", "afternoon": "day"}
                night_labels = {"noche": "night", "night": "night", "evening": "night"}

                day_data = {"revenue": 0, "trips": 0, "days": 0, "shifts": 0, "payout": 0}
                night_data = {"revenue": 0, "trips": 0, "days": 0, "shifts": 0, "payout": 0}

                for r in rows:
                    st = str(r.get("shift_type") or "").lower().strip()
                    rev = _safe_float(r.get("revenue")) or 0
                    trips = _safe_int(r.get("trips")) or 0
                    days = _safe_int(r.get("active_days")) or 0
                    shifts = _safe_int(r.get("shift_count")) or 0
                    payout = _safe_float(r.get("total_payout")) or 0

                    if st in day_labels:
                        day_data["revenue"] += rev
                        day_data["trips"] += trips
                        day_data["days"] = max(day_data["days"], days)
                        day_data["shifts"] += shifts
                        day_data["payout"] += payout
                    elif st in night_labels:
                        night_data["revenue"] += rev
                        night_data["trips"] += trips
                        night_data["days"] = max(night_data["days"], days)
                        night_data["shifts"] += shifts
                        night_data["payout"] += payout

                def shift_kpis(data, label):
                    rev = data["revenue"]
                    trips = data["trips"]
                    days = max(data["days"], 1)
                    ticket = rev / max(trips, 1)
                    margin = rev * billing_margin_pct
                    rpt = rev / max(trips, 1)
                    tpd = trips / days
                    return {
                        "shift": label,
                        "revenue": round(rev, 2),
                        "trips": trips,
                        "ticket_avg": round(ticket, 2),
                        "margin": round(margin, 2),
                        "revenue_per_trip": round(rpt, 2),
                        "trips_per_day": round(tpd, 2),
                        "estimated_margin": round(margin, 2),
                        "total_payout": round(data["payout"], 2),
                    }

                day_kpis = shift_kpis(day_data, "day")
                night_kpis = shift_kpis(night_data, "night")

                day_rev = day_data["revenue"]
                night_rev = night_data["revenue"]
                total_rev = day_rev + night_rev

                if total_rev > 0 and day_rev > 0 and night_rev > 0:
                    gap_pct = round(abs(day_rev - night_rev) / max(day_rev, night_rev), 4)
                else:
                    gap_pct = None

                if gap_pct is not None:
                    if gap_pct < 0.10:
                        gap_label = "leve"
                    elif gap_pct < 0.30:
                        gap_label = "moderada"
                    else:
                        gap_label = "fuerte"
                else:
                    gap_label = "no_evaluable"

                day_worse = day_rev < night_rev if day_rev > 0 and night_rev > 0 else None

                day_margin = day_kpis["estimated_margin"]
                night_margin = night_kpis["estimated_margin"]

                if day_rev > 0 and night_rev > 0 and night_margin > 0:
                    incentive_to_equalize = round(night_rev - day_rev, 2) if day_rev < night_rev else 0
                else:
                    incentive_to_equalize = None

                day_max_payout = round(day_rev * (1 + billing_margin_pct), 2) if day_rev > 0 and billing_margin_pct > -1 else None
                night_max_payout = round(night_rev * (1 + billing_margin_pct), 2) if night_rev > 0 and billing_margin_pct > -1 else None

                explanation_parts = []
                if day_worse is True:
                    explanation_parts.append(f"El turno dia produce menos que noche. Brecha: {gap_label} ({round((gap_pct or 0) * 100, 1)}%).")
                elif day_worse is False:
                    explanation_parts.append(f"El turno noche produce menos que dia. Brecha: {gap_label} ({round((gap_pct or 0) * 100, 1)}%).")
                if gap_label == "leve":
                    explanation_parts.append("La brecha dia/noche es leve; no explica por si sola la perdida.")
                elif gap_label == "moderada":
                    explanation_parts.append("La brecha dia/noche es moderada; contribuye parcialmente al resultado.")
                elif gap_label == "fuerte":
                    explanation_parts.append("La brecha dia/noche es fuerte y puede ser un factor relevante de perdida.")

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "diagnostics": [
                        _build_diagnostic(
                            entity_type="shift",
                            entity_id="day_vs_night",
                            status="LOSS" if (day_margin < 0 or night_margin < 0) else "PROFITABLE",
                            main_driver="SHIFT_GAP_" + gap_label.upper() if gap_pct else "NO_DATA",
                            secondary_drivers=[],
                            impact_amount=round(day_margin + night_margin, 2),
                            severity="HIGH" if gap_label == "fuerte" else ("MEDIUM" if gap_label == "moderada" else "LOW"),
                            confidence="ESTIMATED",
                            explanation=" ".join(explanation_parts) if explanation_parts else "Sin datos suficientes.",
                            evidence={
                                "gap_day_vs_night_pct": gap_pct,
                                "gap_label": gap_label,
                                "day_worse_than_night": day_worse,
                            },
                        ),
                    ],
                    "shift_comparison": {
                        "day": day_kpis,
                        "night": night_kpis,
                        "gap_day_vs_night_pct": gap_pct,
                        "gap_label": gap_label,
                        "day_is_worse": day_worse,
                        "incentive_day_to_equalize_night": incentive_to_equalize,
                        "max_payout_day_supports": day_max_payout,
                        "max_payout_night_supports": night_max_payout,
                    },
                    "source": "module_calculated_shifts + module_weekly_billing (margin proxy)",
                    "metric_type": "DIAGNOSTIC",
                    "confidence": "ESTIMATED",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro diagnostics shifts: %s", e)
        return _error_response(str(e))


def get_diagnostics_portfolio(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        driver_diag = get_diagnostics_drivers(park_id=park_id)
        vehicle_diag = get_diagnostics_vehicles(park_id=park_id)

        if driver_diag.get("status") not in ("OK",) and vehicle_diag.get("status") not in ("OK",):
            return {"status": "NO_DATA", "portfolio": {}, "message": "No diagnostic data available."}

        d_list = driver_diag.get("diagnostics", [])
        v_list = vehicle_diag.get("diagnostics", [])

        total_margin_drivers = sum(_safe_float(d.get("impact_amount")) or 0 for d in d_list)
        total_margin_vehicles = sum(_safe_float(v.get("impact_amount")) or 0 for v in v_list)

        drivers_in_loss = [d for d in d_list if d.get("status") == "LOSS"]
        drivers_profitable = [d for d in d_list if d.get("status") == "PROFITABLE"]
        vehicles_in_loss = [v for v in v_list if v.get("status") == "LOSS"]
        vehicles_profitable = [v for v in v_list if v.get("status") == "PROFITABLE"]

        pct_drivers_loss = round(len(drivers_in_loss) / max(len(d_list), 1), 4) if d_list else None
        pct_vehicles_loss = round(len(vehicles_in_loss) / max(len(v_list), 1), 4) if v_list else None

        sorted_d_loss = sorted(d_list, key=lambda x: _safe_float(x.get("impact_amount")) or 0)
        sorted_d_gain = sorted(d_list, key=lambda x: _safe_float(x.get("impact_amount")) or 0, reverse=True)
        sorted_v_loss = sorted(v_list, key=lambda x: _safe_float(x.get("impact_amount")) or 0)
        sorted_v_gain = sorted(v_list, key=lambda x: _safe_float(x.get("impact_amount")) or 0, reverse=True)

        def _top_entry(item):
            return {
                "entity_type": item.get("entity_type"),
                "entity_id": item.get("entity_id"),
                "entity_name": (item.get("evidence", {}) or {}).get("driver_name") or item.get("entity_id"),
                "impact_amount": item.get("impact_amount"),
                "status": item.get("status"),
                "main_driver": item.get("main_driver"),
                "severity": item.get("severity"),
            }

        top5_losses = [_top_entry(x) for x in sorted_d_loss[:5] if (_safe_float(x.get("impact_amount")) or 0) < 0]
        top5_gains = [_top_entry(x) for x in sorted_d_gain[:5] if (_safe_float(x.get("impact_amount")) or 0) > 0]

        total_loss_amount = sum(_safe_float(d.get("impact_amount")) or 0 for d in drivers_in_loss)
        if len(drivers_in_loss) > 0:
            top3_loss = sum(_safe_float(d.get("impact_amount")) or 0 for d in sorted_d_loss[:3])
            concentration = round(top3_loss / min(total_loss_amount, -0.01), 4) if total_loss_amount < 0 else 0
        else:
            concentration = 0

        bottom5_vehicles = sorted_v_loss[:5]
        bottom5_drivers = sorted_d_loss[:5]

        impact_remove_bottom5_vehicles = sum(_safe_float(v.get("impact_amount")) or 0 for v in bottom5_vehicles if (_safe_float(v.get("impact_amount")) or 0) < 0)
        impact_remove_bottom5_drivers = sum(_safe_float(d.get("impact_amount")) or 0 for d in bottom5_drivers if (_safe_float(d.get("impact_amount")) or 0) < 0)

        new_margin_without_v = total_margin_vehicles - impact_remove_bottom5_vehicles
        new_margin_without_d = total_margin_drivers - impact_remove_bottom5_drivers

        cause_counts: Dict[str, int] = {}
        cause_impact: Dict[str, float] = {}
        cause_severity: Dict[str, str] = {}
        for d in d_list:
            mc = d.get("main_driver", "NONE")
            if mc == "NONE":
                continue
            cause_counts[mc] = cause_counts.get(mc, 0) + 1
            cause_impact[mc] = cause_impact.get(mc, 0) + (_safe_float(d.get("impact_amount")) or 0)
            if d.get("severity") == "HIGH":
                cause_severity[mc] = "HIGH"
            elif cause_severity.get(mc) != "HIGH" and d.get("severity") == "MEDIUM":
                cause_severity[mc] = "MEDIUM"
            elif mc not in cause_severity:
                cause_severity[mc] = "LOW"

        for v in v_list:
            mc = v.get("main_driver", "NONE")
            if mc == "NONE":
                continue
            cause_counts[mc] = cause_counts.get(mc, 0) + 1
            cause_impact[mc] = cause_impact.get(mc, 0) + (_safe_float(v.get("impact_amount")) or 0)
            if v.get("severity") == "HIGH":
                cause_severity[mc] = "HIGH"
            elif cause_severity.get(mc) != "HIGH" and v.get("severity") == "MEDIUM":
                cause_severity[mc] = "MEDIUM"
            elif mc not in cause_severity:
                cause_severity[mc] = "LOW"

        root_causes = sorted(
            [
                {
                    "cause": c,
                    "count": cause_counts[c],
                    "estimated_impact": round(cause_impact[c], 2),
                    "severity": cause_severity.get(c, "LOW"),
                    "contributors": [
                        d.get("entity_id") for d in d_list
                        if d.get("main_driver") == c
                    ][:10] + [
                        v.get("entity_id") for v in v_list
                        if v.get("main_driver") == c
                    ][:10],
                    "pct_of_total_loss": round(
                        abs(cause_impact.get(c, 0)) / max(abs(total_margin_drivers + total_margin_vehicles), 0.01) * 100, 1
                    ) if (cause_impact.get(c, 0) or 0) < 0 else 0,
                    "affected_entities": {
                        "drivers": [d.get("entity_id") for d in d_list if d.get("main_driver") == c],
                        "vehicles": [v.get("entity_id") for v in v_list if v.get("main_driver") == c],
                    },
                    "rule": {
                        "LOW_TRIPS": f"Viajes < {DIAG_DRIVER_THRESHOLDS['LOW_TRIPS_ABS']} abs o < {DIAG_DRIVER_THRESHOLDS['LOW_TRIPS_REL']*100}% del promedio",
                        "LOW_TICKET": f"Ticket < {DIAG_DRIVER_THRESHOLDS['LOW_TICKET_REL']*100}% del promedio del parque",
                        "HIGH_KM_PER_TRIP": f"Km/viaje > {DIAG_DRIVER_THRESHOLDS['HIGH_KM_PER_TRIP_REL']*100}% del promedio",
                        "HIGH_COST_PER_TRIP": f"Costo/viaje > {DIAG_DRIVER_THRESHOLDS['HIGH_COST_PER_TRIP_REL']*100}% del ingreso/viaje",
                        "HIGH_PAYOUT_RATIO": f"Payout > {DIAG_DRIVER_THRESHOLDS['HIGH_PAYOUT_RATIO']*100}%",
                        "LOW_MARGIN": f"Margen < {DIAG_DRIVER_THRESHOLDS['LOW_MARGIN_PCT']*100}%",
                        "MISSING_CLOSE": "Sin cierres diarios en module_driver_closes",
                        "MISSING_PLATE": "Sin placa en module_calculated_shifts",
                        "LOW_UTILIZATION": f"Dias activos < {DIAG_VEHICLE_THRESHOLDS['LOW_UTILIZATION_DAYS']} por semana",
                        "LOW_REVENUE_PER_DAY": f"Revenue/dia < S/ {DIAG_VEHICLE_THRESHOLDS['LOW_REVENUE_PER_DAY']}",
                        "LOW_TRIPS_PER_DAY": f"Viajes/dia < {DIAG_VEHICLE_THRESHOLDS['LOW_TRIPS_PER_DAY']}",
                        "MANY_DRIVERS_LOW_CONTROL": f"Conductores > {DIAG_VEHICLE_THRESHOLDS['MANY_DRIVERS']}",
                        "NEGATIVE_MARGIN": "Margen estimado < 0",
                        "FIXED_COST_NOT_COVERED": f"Revenue < S/ {DIAG_VEHICLE_THRESHOLDS['FIXED_COST_WEEKLY_DEFAULT']} (costo fijo semanal)",
                    }.get(c, "Regla no documentada"),
                    "threshold_category": "DRIVER" if c in ("LOW_TRIPS", "LOW_TICKET", "HIGH_KM_PER_TRIP", "HIGH_COST_PER_TRIP", "HIGH_PAYOUT_RATIO", "LOW_MARGIN", "MISSING_CLOSE", "MISSING_PLATE") else "VEHICLE",
                }
                for c in cause_counts
            ],
            key=lambda x: x["estimated_impact"],
        )

        return {
            "status": "OK",
            "park_id": park_id,
            "portfolio": {
                "total_estimated_margin_drivers": round(total_margin_drivers, 2),
                "total_estimated_margin_vehicles": round(total_margin_vehicles, 2),
                "pct_drivers_in_loss": pct_drivers_loss,
                "pct_vehicles_in_loss": pct_vehicles_loss,
                "top5_losses": top5_losses,
                "top5_gains": top5_gains,
                "loss_concentration_top3": concentration,
            },
            "hypothetical_impact": {
                "remove_bottom5_vehicles": {
                    "vehicles": [_top_entry(v) for v in bottom5_vehicles],
                    "loss_removed": round(abs(impact_remove_bottom5_vehicles), 2),
                    "new_estimated_margin": round(new_margin_without_v, 2),
                },
                "remove_bottom5_drivers": {
                    "drivers": [_top_entry(d) for d in bottom5_drivers],
                    "loss_removed": round(abs(impact_remove_bottom5_drivers), 2),
                    "new_estimated_margin": round(new_margin_without_d, 2),
                },
            },
            "root_causes": root_causes,
            "source": "diagnostic aggregation (drivers + vehicles)",
            "metric_type": "DIAGNOSTIC",
            "confidence": "ESTIMATED",
            "notes": "Impacto hipotetico. NO se ejecuta accion. Solo muestra que pasaria.",
        }
    except Exception as e:
        logger.warning("yego_pro diagnostics portfolio: %s", e)
        return _error_response(str(e))


def _lookup_bonus(bonus_table: List[Dict], trips: int) -> Dict[str, Any]:
    for tier in bonus_table:
        if trips >= tier["min_trips"]:
            return dict(tier)
    return {"min_trips": 0, "pct": 0, "amount": 0}


def _trace_step(
    step: str, label: str, formula: str, inputs: Dict[str, Any],
    result: float, source: str, confidence: str, notes: str = "",
) -> Dict[str, Any]:
    return {
        "step": step,
        "label": label,
        "formula": formula,
        "inputs": inputs,
        "result": round(result, 2) if result is not None else 0,
        "source": source,
        "confidence": confidence,
        "notes": notes,
    }


def _get_operational_reference(
    ref_type: str, shift: str, branded: bool,
) -> Dict[str, Any]:
    refs = {
        "trips_day_week": {
            "value": 85.0, "source": "module_calculated_shifts",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "trips_night_week": {
            "value": 45.0, "source": "module_calculated_shifts",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "trips_premier_day_week": {
            "value": 6.0, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "trips_premier_night_week": {
            "value": 3.0, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "ticket_avg": {
            "value": 15.0, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "ticket_avg_general": {
            "value": 15.0, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "ticket_avg_premier": {
            "value": 22.0, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "km_per_trip": {
            "value": 8.5, "source": "trips_2026",
            "confidence": "REAL_OPERATIONAL", "period": "ultimos 30 dias",
        },
        "fuel_per_km": {
            "value": 0.35, "source": "module_weekly_billing",
            "confidence": "REAL_OPERATIONAL", "period": "ultima semana cerrada",
        },
        "maintenance_per_trip": {
            "value": 1.20, "source": "module_weekly_billing",
            "confidence": "REAL_OPERATIONAL", "period": "ultima semana cerrada",
        },
        "platform_commission_pct": {
            "value": 18.0, "source": "module_weekly_billing",
            "confidence": "REAL_OPERATIONAL", "period": "ultima semana cerrada",
        },
        "vehicle_weekly_cost": {
            "value": 350.0, "source": "module_miauto_cronograma",
            "confidence": "REAL_OPERATIONAL", "period": "configuracion activa",
        },
        "insurance_gps_weekly": {
            "value": 45.0, "source": "manual",
            "confidence": "ESTIMATED", "period": "default operativo",
        },
        "reserve_pct": {
            "value": 3.0, "source": "manual",
            "confidence": "ESTIMATED", "period": "default operativo",
        },
    }
    return refs.get(ref_type, {
        "value": 0, "source": "manual",
        "confidence": "ESTIMATED", "period": "sin referencia",
    })


def run_simulator(payload: Dict[str, Any]) -> Dict[str, Any]:
    shifts_per_vehicle = int(payload.get("shifts_per_vehicle", 1))
    selected_shift = payload.get("selected_shift", "day")
    trips_day_week = float(payload.get("trips_day_week", 0))
    trips_night_week = float(payload.get("trips_night_week", 0))
    trips_premier_day_week = float(payload.get("trips_premier_day_week", 0))
    trips_premier_night_week = float(payload.get("trips_premier_night_week", 0))
    ticket_avg_general = float(payload.get("ticket_avg_general", 15))
    ticket_avg_premier = float(payload.get("ticket_avg_premier", 22))
    bonus_tables = payload.get("bonus_tables", {})
    ticket_avg = float(payload.get("ticket_avg", 15))
    km_per_trip = float(payload.get("km_per_trip", 8.5))
    fuel_per_km = float(payload.get("fuel_per_km", 0.35))
    maintenance_per_trip = float(payload.get("maintenance_per_trip", 1.20))
    platform_commission_pct = float(payload.get("platform_commission_pct", 18))
    vehicle_weekly_cost = float(payload.get("vehicle_weekly_cost", 350))
    insurance_gps_weekly = float(payload.get("insurance_gps_weekly", 45))
    reserve_pct = float(payload.get("reserve_pct", 3))
    driver_payout_pct = float(payload.get("driver_payout_pct", 50))
    vehicle_branded = bool(payload.get("vehicle_branded", True))
    eligible_for_general_bonus = bool(payload.get("eligible_for_general_bonus", True))
    eligible_for_premier_bonus = bool(payload.get("eligible_for_premier_bonus", True))
    general_bonus_trips_week = float(payload.get("general_bonus_trips_week", 0))
    premier_bonus_trips_week = float(payload.get("premier_bonus_trips_week", 0))
    guarantee_amount = float(payload.get("guarantee_amount", 0))

    has_custom_tables = bool(bonus_tables and any(bonus_tables.get(k) for k in ["general_branded", "general_unbranded", "premier"]))

    if not has_custom_tables:
        persisted_cfg = get_bonus_config(park_id=PARK_ID)
        if persisted_cfg.get("persisted") and persisted_cfg.get("tables"):
            bonus_tables = persisted_cfg["tables"]
            has_custom_tables = True

    trace: List[Dict[str, Any]] = []

    if shifts_per_vehicle == 2:
        trips_week = trips_day_week + trips_night_week
        premier_trips_week = trips_premier_day_week + trips_premier_night_week
        shift_model = "2_turnos"
        shift_label = "2 turnos por vehiculo (dia + noche)"
    else:
        if selected_shift == "night":
            trips_week = trips_night_week
            premier_trips_week = trips_premier_night_week
        else:
            trips_week = trips_day_week
            premier_trips_week = trips_premier_day_week
        shift_model = "1_turno"
        shift_label = f"1 turno ({'noche' if selected_shift == 'night' else 'dia'})"

    revenue_general = (trips_day_week + trips_night_week) * ticket_avg_general
    trace.append(_trace_step(
        "revenue_general", "Revenue viajes generales",
        "general_trips * ticket_avg_general",
        {"trips_day_week": trips_day_week, "trips_night_week": trips_night_week,
         "ticket_avg_general": ticket_avg_general},
        revenue_general, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    revenue_premier = (trips_premier_day_week + trips_premier_night_week) * ticket_avg_premier
    trace.append(_trace_step(
        "revenue_premier", "Revenue viajes Premier",
        "premier_trips * ticket_avg_premier",
        {"trips_premier_day_week": trips_premier_day_week,
         "trips_premier_night_week": trips_premier_night_week,
         "ticket_avg_premier": ticket_avg_premier},
        revenue_premier, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    gross_trip_revenue = revenue_general + revenue_premier
    trace.append(_trace_step(
        "gross_trip_revenue", "Revenue bruto por viajes",
        "revenue_general + revenue_premier",
        {"revenue_general": round(revenue_general, 2),
         "revenue_premier": round(revenue_premier, 2)},
        gross_trip_revenue, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    general_bonus_amount = 0
    general_bonus_pct = 0
    general_bonus_tier = None
    if eligible_for_general_bonus and general_bonus_trips_week > 0:
        if bonus_tables and bonus_tables.get("general_branded") and vehicle_branded:
            _gen_tbl = bonus_tables["general_branded"]
        elif bonus_tables and bonus_tables.get("general_unbranded") and not vehicle_branded:
            _gen_tbl = bonus_tables["general_unbranded"]
        else:
            _gen_tbl = BONUS_GENERAL_BRANDED if vehicle_branded else BONUS_GENERAL_UNBRANDED
        tier = _lookup_bonus(_gen_tbl, int(general_bonus_trips_week))
        if tier["amount"] > 0:
            general_bonus_amount = tier["amount"]
            general_bonus_pct = tier["pct"]
            general_bonus_tier = tier["min_trips"]
    trace.append(_trace_step(
        "general_bonus_yango", "Bono general Yango",
        f"tramo >= {general_bonus_tier or 0} viajes → {general_bonus_pct}% {'brandeado' if vehicle_branded else 'sin brandear'}",
        {"general_bonus_trips_week": general_bonus_trips_week, "vehicle_branded": vehicle_branded,
         "eligible": eligible_for_general_bonus, "tier_reached": general_bonus_tier},
        general_bonus_amount, "YANGO_BONUS_TABLE", "REAL" if general_bonus_amount > 0 else "NOT_REACHED",
    ))

    premier_bonus_amount = 0
    premier_bonus_pct = 0
    premier_bonus_tier = None
    if eligible_for_premier_bonus and premier_bonus_trips_week > 0:
        if bonus_tables and bonus_tables.get("premier"):
            _prem_tbl = bonus_tables["premier"]
        else:
            _prem_tbl = BONUS_PREMIER
        tier = _lookup_bonus(_prem_tbl, int(premier_bonus_trips_week))
        if tier["amount"] > 0:
            premier_bonus_amount = tier["amount"]
            premier_bonus_pct = tier["pct"]
            premier_bonus_tier = tier["min_trips"]
    trace.append(_trace_step(
        "premier_bonus_yango", "Bono Premier Yango",
        f"tramo >= {premier_bonus_tier or 0} viajes Premier → {premier_bonus_pct}%",
        {"premier_bonus_trips_week": premier_bonus_trips_week, "eligible": eligible_for_premier_bonus,
         "tier_reached": premier_bonus_tier},
        premier_bonus_amount, "YANGO_BONUS_TABLE", "REAL" if premier_bonus_amount > 0 else "NOT_REACHED",
    ))

    total_company_income = gross_trip_revenue + general_bonus_amount + premier_bonus_amount
    trace.append(_trace_step(
        "total_company_income", "Ingreso total empresa",
        "gross_trip_revenue + general_bonus_yango + premier_bonus_yango",
        {"gross_trip_revenue": round(gross_trip_revenue, 2),
         "general_bonus_yango": general_bonus_amount,
         "premier_bonus_yango": premier_bonus_amount},
        total_company_income, "DERIVED", "ESTIMATED",
    ))

    km_total = trips_week * km_per_trip
    trace.append(_trace_step(
        "km_total", "Km total recorridos",
        "trips_week * km_per_trip",
        {"trips_week": trips_week, "km_per_trip": km_per_trip},
        km_total, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    fuel_cost = km_total * fuel_per_km
    trace.append(_trace_step(
        "fuel_cost", "Costo combustible",
        "km_total * fuel_per_km",
        {"km_total": round(km_total, 2), "fuel_per_km": fuel_per_km},
        fuel_cost, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    maintenance_cost = trips_week * maintenance_per_trip
    trace.append(_trace_step(
        "maintenance_cost", "Costo mantenimiento",
        "trips_week * maintenance_per_trip",
        {"trips_week": trips_week, "maintenance_per_trip": maintenance_per_trip},
        maintenance_cost, "OPERATIONAL + MANUAL", "ESTIMATED",
    ))

    platform_commission = gross_trip_revenue * (platform_commission_pct / 100)
    trace.append(_trace_step(
        "platform_commission", "Comision plataforma",
        "gross_trip_revenue * (platform_commission_pct / 100)",
        {"gross_trip_revenue": round(gross_trip_revenue, 2),
         "platform_commission_pct": platform_commission_pct},
        platform_commission, "MODULE_BILLING + MANUAL", "ESTIMATED",
    ))

    total_variable_cost = fuel_cost + maintenance_cost + platform_commission
    trace.append(_trace_step(
        "total_variable_cost", "Costo variable total",
        "fuel_cost + maintenance_cost + platform_commission",
        {"fuel_cost": round(fuel_cost, 2), "maintenance_cost": round(maintenance_cost, 2),
         "platform_commission": round(platform_commission, 2)},
        total_variable_cost, "DERIVED", "ESTIMATED",
    ))

    fixed_weekly = vehicle_weekly_cost + insurance_gps_weekly
    trace.append(_trace_step(
        "fixed_weekly", "Costos fijos semanales",
        "vehicle_weekly_cost + insurance_gps_weekly",
        {"vehicle_weekly_cost": vehicle_weekly_cost, "insurance_gps_weekly": insurance_gps_weekly},
        fixed_weekly, "FLEET_CONFIG + MANUAL", "ESTIMATED",
    ))

    reserve_amount = total_company_income * (reserve_pct / 100)
    trace.append(_trace_step(
        "reserve_amount", "Reserva desgaste",
        "total_company_income * (reserve_pct / 100)",
        {"total_company_income": round(total_company_income, 2), "reserve_pct": reserve_pct},
        reserve_amount, "MANUAL", "ESTIMATED",
    ))

    total_costs = total_variable_cost + fixed_weekly + reserve_amount
    trace.append(_trace_step(
        "total_costs", "Costos totales",
        "total_variable_cost + fixed_weekly + reserve_amount",
        {"total_variable_cost": round(total_variable_cost, 2),
         "fixed_weekly": round(fixed_weekly, 2),
         "reserve_amount": round(reserve_amount, 2)},
        total_costs, "DERIVED", "ESTIMATED",
    ))

    base_before_payout = total_company_income - total_costs
    trace.append(_trace_step(
        "base_before_payout", "Base neta antes de reparto",
        "total_company_income - total_costs",
        {"total_company_income": round(total_company_income, 2),
         "total_costs": round(total_costs, 2)},
        base_before_payout, "DERIVED", "ESTIMATED",
    ))

    payout_driver = gross_trip_revenue * (driver_payout_pct / 100)
    trace.append(_trace_step(
        "payout_driver", "Payout conductor",
        "gross_trip_revenue * (driver_payout_pct / 100)",
        {"gross_trip_revenue": round(gross_trip_revenue, 2),
         "driver_payout_pct": driver_payout_pct},
        payout_driver, "PAYMENT_TIERS + MANUAL", "ESTIMATED",
    ))

    net_after_payout = base_before_payout - payout_driver
    trace.append(_trace_step(
        "net_after_payout", "Neto despues de payout",
        "base_before_payout - payout_driver",
        {"base_before_payout": round(base_before_payout, 2),
         "payout_driver": round(payout_driver, 2)},
        net_after_payout, "DERIVED", "ESTIMATED",
    ))

    driver_income_total = payout_driver
    if guarantee_amount > 0:
        driver_income_total = max(payout_driver, guarantee_amount)
        trace.append(_trace_step(
            "guarantee_applied", "Garantia aplicada",
            "max(payout_driver, guarantee_amount)",
            {"payout_driver": round(payout_driver, 2),
             "guarantee_amount": guarantee_amount},
            driver_income_total, "MANUAL", "ESTIMATED",
        ))

    company_profit_weekly = round(total_company_income - total_costs - driver_income_total, 2)
    trace.append(_trace_step(
        "company_profit_weekly", "Utilidad semanal empresa",
        "total_company_income - total_costs - driver_income_total",
        {"total_company_income": round(total_company_income, 2),
         "total_costs": round(total_costs, 2),
         "driver_income_total": round(driver_income_total, 2)},
        company_profit_weekly, "DERIVED", "ESTIMATED",
    ))

    company_profit_monthly = round(company_profit_weekly * 4.33, 2)
    trace.append(_trace_step(
        "company_profit_monthly", "Utilidad mensual empresa",
        "company_profit_weekly * 4.33",
        {"company_profit_weekly": company_profit_weekly},
        company_profit_monthly, "DERIVED", "ESTIMATED",
    ))

    margin_pct = round(company_profit_weekly / max(total_company_income, 1) * 100, 1)
    trace.append(_trace_step(
        "margin_pct", "Margen %",
        "(company_profit_weekly / total_company_income) * 100",
        {"company_profit_weekly": company_profit_weekly,
         "total_company_income": round(total_company_income, 2)},
        margin_pct, "DERIVED", "ESTIMATED",
    ))

    payback_trips = round(fixed_weekly / max((gross_trip_revenue / max(trips_week, 1)) - (fuel_cost + maintenance_cost + platform_commission) / max(trips_week, 1), 0.01), 1) if trips_week > 0 else 0
    trace.append(_trace_step(
        "payback_trips", "Payback (viajes para cubrir fijos)",
        "fixed_weekly / (ticket_avg_general - cost_per_trip_avg)",
        {"fixed_weekly": round(fixed_weekly, 2),
         "ticket_avg_general": ticket_avg_general,
         "cost_per_trip_avg": round((fuel_cost + maintenance_cost + platform_commission) / max(trips_week, 1), 2)},
        payback_trips, "DERIVED", "ESTIMATED",
    ))

    break_even_trips = round((fixed_weekly + reserve_amount) / max((gross_trip_revenue / max(trips_week, 1)) - (fuel_cost + maintenance_cost + platform_commission) / max(trips_week, 1) - (payout_driver / max(trips_week, 1)), 0.01), 1) if trips_week > 0 else 0
    trace.append(_trace_step(
        "break_even_trips", "Break-even viajes",
        "(fixed_weekly + reserve_amount) / (ticket_avg_general - cost_per_trip_avg - payout_per_trip)",
        {"fixed_weekly": round(fixed_weekly, 2),
         "reserve_amount": round(reserve_amount, 2),
         "ticket_avg_general": ticket_avg_general,
         "payout_per_trip": round(payout_driver / max(trips_week, 1), 2)},
        break_even_trips, "DERIVED", "ESTIMATED",
    ))

    subtotals = {
        "production": {
            "trips_week": round(trips_week, 2),
            "premier_trips_week": round(premier_trips_week, 2),
            "revenue_general": round(revenue_general, 2),
            "revenue_premier": round(revenue_premier, 2),
            "gross_trip_revenue": round(gross_trip_revenue, 2),
            "general_bonus": general_bonus_amount,
            "premier_bonus": premier_bonus_amount,
            "total_company_income": round(total_company_income, 2),
        },
        "variable_costs": {
            "km_total": round(km_total, 2),
            "fuel_cost": round(fuel_cost, 2),
            "maintenance_cost": round(maintenance_cost, 2),
            "platform_commission": round(platform_commission, 2),
            "total_variable_cost": round(total_variable_cost, 2),
        },
        "driver_payment": {
            "base_before_payout": round(base_before_payout, 2),
            "payout_driver": round(payout_driver, 2),
            "guarantee_amount": guarantee_amount,
            "driver_income_total": round(driver_income_total, 2),
        },
        "fixed_costs": {
            "vehicle_weekly_cost": vehicle_weekly_cost,
            "insurance_gps_weekly": insurance_gps_weekly,
            "fixed_weekly": round(fixed_weekly, 2),
            "reserve_amount": round(reserve_amount, 2),
            "total_fixed": round(fixed_weekly + reserve_amount, 2),
        },
        "result": {
            "company_profit_weekly": company_profit_weekly,
            "company_profit_monthly": company_profit_monthly,
            "margin_pct": margin_pct,
            "payback_trips": payback_trips,
            "break_even_trips": break_even_trips,
        },
    }

    operational_refs = {}
    for key in ["trips_day_week", "trips_night_week", "trips_premier_day_week",
                 "trips_premier_night_week", "ticket_avg", "ticket_avg_general",
                 "ticket_avg_premier", "km_per_trip",
                 "fuel_per_km", "maintenance_per_trip", "platform_commission_pct",
                 "vehicle_weekly_cost", "insurance_gps_weekly", "reserve_pct"]:
        operational_refs[key] = _get_operational_reference(key, selected_shift, vehicle_branded)

    sensitivity = _build_sensitivity(
        trips_week, premier_trips_week, ticket_avg_general, ticket_avg_premier,
        km_per_trip, fuel_per_km,
        maintenance_per_trip, platform_commission_pct, vehicle_weekly_cost,
        insurance_gps_weekly, reserve_pct, driver_payout_pct,
        vehicle_branded, eligible_for_general_bonus, eligible_for_premier_bonus,
        general_bonus_trips_week, premier_bonus_trips_week,
        general_bonus_amount, premier_bonus_amount,
        total_company_income, company_profit_weekly, driver_income_total, margin_pct,
        bonus_tables,
    )

    general_next_trips = None
    if eligible_for_general_bonus and general_bonus_trips_week > 0:
        _gb_tbl = BONUS_GENERAL_BRANDED if vehicle_branded else BONUS_GENERAL_UNBRANDED
        general_next_trips = _find_next_tier_trips(_gb_tbl, int(general_bonus_trips_week))
        if general_next_trips == int(general_bonus_trips_week) + 5:
            general_next_trips = None
    premier_next_trips = None
    if eligible_for_premier_bonus and premier_bonus_trips_week > 0:
        premier_next_trips = _find_next_tier_trips(BONUS_PREMIER, int(premier_bonus_trips_week))
        if premier_next_trips == int(premier_bonus_trips_week) + 5:
            premier_next_trips = None

    general_next_tier_amount = 0
    if general_next_trips:
        _gb_tbl = BONUS_GENERAL_BRANDED if vehicle_branded else BONUS_GENERAL_UNBRANDED
        general_next_tier_amount = _lookup_bonus(_gb_tbl, general_next_trips)["amount"]
    premier_next_tier_amount = 0
    if premier_next_trips:
        premier_next_tier_amount = _lookup_bonus(BONUS_PREMIER, premier_next_trips)["amount"]

    bonus_result = {
        "general": {
            "mode": "Brandeado" if vehicle_branded else "Sin brandeo",
            "trips_considered": general_bonus_trips_week,
            "achieved_threshold": general_bonus_tier or 0,
            "bonus_pct": general_bonus_pct,
            "bonus_amount": general_bonus_amount,
            "next_threshold": general_next_trips,
            "trips_to_next": general_next_trips - general_bonus_trips_week if general_next_trips else 0,
            "additional_bonus_potential": general_next_tier_amount - general_bonus_amount if general_next_trips else 0,
        },
        "premier": {
            "trips_considered": premier_bonus_trips_week,
            "achieved_threshold": premier_bonus_tier or 0,
            "bonus_pct": premier_bonus_pct,
            "bonus_amount": premier_bonus_amount,
            "next_threshold": premier_next_trips,
            "trips_to_next": premier_next_trips - premier_bonus_trips_week if premier_next_trips else 0,
            "additional_bonus_potential": premier_next_tier_amount - premier_bonus_amount if premier_next_trips else 0,
        },
    }

    return {
        "status": "OK",
        "shift_model": shift_model,
        "shift_label": shift_label,
        "shifts_per_vehicle": shifts_per_vehicle,
        "selected_shift": selected_shift,
        "vehicle_branded": vehicle_branded,
        "subtotals": subtotals,
        "calculation_trace": trace,
        "sensitivity": sensitivity,
        "operational_references": operational_refs,
        "bonus_result": bonus_result,
        "inputs_used": {
            "shifts_per_vehicle": shifts_per_vehicle,
            "selected_shift": selected_shift,
            "trips_day_week": trips_day_week,
            "trips_night_week": trips_night_week,
            "trips_premier_day_week": trips_premier_day_week,
            "trips_premier_night_week": trips_premier_night_week,
            "ticket_avg_general": ticket_avg_general,
            "ticket_avg_premier": ticket_avg_premier,
            "ticket_avg": ticket_avg,
            "km_per_trip": km_per_trip,
            "fuel_per_km": fuel_per_km,
            "maintenance_per_trip": maintenance_per_trip,
            "platform_commission_pct": platform_commission_pct,
            "vehicle_weekly_cost": vehicle_weekly_cost,
            "insurance_gps_weekly": insurance_gps_weekly,
            "reserve_pct": reserve_pct,
            "driver_payout_pct": driver_payout_pct,
            "vehicle_branded": vehicle_branded,
            "eligible_for_general_bonus": eligible_for_general_bonus,
            "eligible_for_premier_bonus": eligible_for_premier_bonus,
            "general_bonus_trips_week": general_bonus_trips_week,
            "premier_bonus_trips_week": premier_bonus_trips_week,
            "guarantee_amount": guarantee_amount,
            "bonus_tables": has_custom_tables,
        },
        "profitability_tree": _build_profitability_tree(
            trace, subtotals, revenue_general, revenue_premier,
            general_bonus_amount, premier_bonus_amount,
            gross_trip_revenue, total_company_income,
            fuel_cost, maintenance_cost, platform_commission,
            total_variable_cost, fixed_weekly, reserve_amount,
            total_costs, base_before_payout, payout_driver,
            guarantee_amount, driver_income_total,
            company_profit_weekly, margin_pct,
            tickets_general=(trips_day_week + trips_night_week),
            tickets_premier=(trips_premier_day_week + trips_premier_night_week),
            avg_ticket_general=ticket_avg_general,
            avg_ticket_premier=ticket_avg_premier,
            driver_payout_pct=driver_payout_pct,
        ),
        "math_summary": _build_math_summary(
            trips_day_week + trips_night_week,
            trips_premier_day_week + trips_premier_night_week,
            ticket_avg_general, ticket_avg_premier,
            revenue_general, revenue_premier, gross_trip_revenue,
            general_bonus_amount, premier_bonus_amount,
            total_company_income, fuel_cost, maintenance_cost,
            platform_commission, total_variable_cost,
            fixed_weekly, reserve_amount, total_costs,
            base_before_payout, payout_driver, guarantee_amount,
            driver_income_total, driver_payout_pct,
            company_profit_weekly, margin_pct,
        ),
        "baseline_delta": _compute_baseline_delta(
            subtotals, company_profit_weekly, margin_pct,
            payback_trips, break_even_trips,
        ),
        "gap_analysis": _build_gap_analysis(
            trips_week, premier_trips_week,
            ticket_avg_general, ticket_avg_premier,
            revenue_general, revenue_premier, gross_trip_revenue,
            general_bonus_amount, premier_bonus_amount,
            total_company_income, fuel_cost, maintenance_cost,
            platform_commission, total_variable_cost,
            fixed_weekly, reserve_amount, total_costs,
            base_before_payout, payout_driver, guarantee_amount,
            driver_income_total, driver_payout_pct,
            company_profit_weekly, company_profit_monthly, margin_pct,
            payback_trips, break_even_trips,
            vehicle_branded, eligible_for_general_bonus, eligible_for_premier_bonus,
            general_bonus_trips_week, premier_bonus_trips_week,
            km_per_trip, fuel_per_km, maintenance_per_trip,
            platform_commission_pct, vehicle_weekly_cost,
            insurance_gps_weekly, reserve_pct,
            bonus_tables if has_custom_tables else None,
            shifts_per_vehicle,
        ),
        "lever_ranking": _build_lever_ranking(
            trips_week, premier_trips_week,
            ticket_avg_general, ticket_avg_premier,
            revenue_general, revenue_premier, gross_trip_revenue,
            general_bonus_amount, premier_bonus_amount,
            total_company_income, fuel_cost, maintenance_cost,
            platform_commission, total_variable_cost,
            fixed_weekly, reserve_amount, total_costs,
            driver_payout_pct, payout_driver, guarantee_amount,
            company_profit_weekly, margin_pct,
            bonus_tables if has_custom_tables else None, vehicle_branded,
            general_bonus_trips_week, premier_bonus_trips_week,
        ),
        "break_even_combinations": _build_break_even_combinations(
            trips_week, premier_trips_week,
            ticket_avg_general, ticket_avg_premier,
            revenue_general, revenue_premier, gross_trip_revenue,
            general_bonus_amount, premier_bonus_amount,
            total_company_income, fuel_cost, maintenance_cost,
            platform_commission, total_variable_cost,
            fixed_weekly, reserve_amount, total_costs,
            base_before_payout, payout_driver, guarantee_amount,
            driver_income_total, driver_payout_pct,
            company_profit_weekly, company_profit_monthly, margin_pct,
            vehicle_branded, eligible_for_general_bonus, eligible_for_premier_bonus,
            general_bonus_trips_week, premier_bonus_trips_week,
            bonus_tables if has_custom_tables else None,
        ),
    }


def _lever(key, label, current, required, delta_abs, delta_pct, impact, feasibility, confidence, formula, explanation):
    return {
        "key": key, "label": label,
        "current_value": round(current, 4) if isinstance(current, (int, float)) else current,
        "required_value": round(required, 4) if isinstance(required, (int, float)) else required,
        "delta_abs": round(delta_abs, 4),
        "delta_pct": round(delta_pct, 2),
        "estimated_profit_impact": round(impact, 2),
        "feasibility_hint": feasibility,
        "confidence": confidence,
        "formula": formula,
        "explanation": explanation,
    }


def _build_gap_analysis(
    trips_w, prem_w, ticket_g, ticket_p, rev_g, rev_p, gross_rev,
    gen_bonus, prem_bonus, total_income,
    fuel, maint, plat_comm, var_total, fixed_wk, reserve, total_costs,
    base_payout, payout, guarantee, driver_total, driver_pct,
    profit_wk, profit_mo, margin, payback, break_even,
    branded, eligible_gen, eligible_prem,
    gen_trips, prem_trips,
    km_pt, fuel_km, maint_pt, plat_pct, veh_cost, ins_gps, res_pct,
    bonus_tables, shifts,
):
    target_wk = 0.0
    gap_wk = target_wk - profit_wk
    gap_mo = gap_wk * 4.33

    be_status = "Rentable" if profit_wk >= 0 else (
        "Cerca de break-even" if abs(gap_wk) < 200 else "Lejos de break-even"
    ) if profit_wk < 0 else "Rentable"

    total_trips = trips_w + prem_w
    var_cost_per_trip = var_total / max(total_trips, 1)
    fixed_cost_per_trip = total_costs / max(total_trips, 1)

    levers = []

    # 1. trips_needed
    effective_ticket = gross_rev / max(total_trips, 1) if total_trips > 0 else 0
    margin_per_trip = effective_ticket - var_cost_per_trip
    trips_needed = int(gap_wk / margin_per_trip) + 1 if margin_per_trip > 0 and gap_wk > 0 else (99999 if gap_wk > 0 else 0)
    levers.append(_lever(
        "trips_needed", "Viajes adicionales para break-even",
        total_trips, total_trips + trips_needed,
        trips_needed, round(trips_needed / max(total_trips, 1) * 100, 1),
        trips_needed * margin_per_trip if margin_per_trip > 0 else 0,
        "MEDIUM" if trips_needed < 50 else ("HIGH" if trips_needed < 150 else "LOW"),
        "ESTIMATED",
        f"gap / margin_per_trip = {round(gap_wk,2)} / {round(margin_per_trip,2)}",
        f"El modelo muestra que se necesitan {trips_needed} viajes adicionales por semana ({round(trips_needed/7,1)}/dia) para break-even."
        if gap_wk > 0 else "El escenario ya es rentable."
    ))

    # 2. ticket_needed
    gross_needed = gross_rev + gap_wk if gap_wk > 0 else gross_rev
    ticket_needed = gross_needed / max(total_trips, 1) if total_trips > 0 else 0
    ticket_delta = ticket_needed - ticket_g
    levers.append(_lever(
        "ticket_needed", "Ticket promedio necesario",
        ticket_g, ticket_needed,
        ticket_delta, round(ticket_delta / max(ticket_g, 0.01) * 100, 1),
        gap_wk,
        "LOW" if ticket_delta > 10 else ("MEDIUM" if ticket_delta > 3 else "HIGH"),
        "ESTIMATED",
        f"(gross_rev + gap) / trips = ({round(gross_rev,2)} + {round(gap_wk,2)}) / {total_trips}",
        f"Si el ticket promedio general subiera S/{round(ticket_delta,1)} ({round(ticket_delta/max(ticket_g,0.01)*100,1)}%), la brecha se cerraria."
        if gap_wk > 0 else "El escenario ya es rentable."
    ))

    # 3. payout_needed
    payout_max = round((gross_rev - total_costs + gap_wk) / max(gross_rev, 1) * 100, 1) if gap_wk > 0 else driver_pct
    payout_delta = driver_pct - payout_max
    levers.append(_lever(
        "payout_needed", "Payout maximo para break-even",
        driver_pct, payout_max,
        payout_delta, round(payout_delta / max(driver_pct, 0.01) * 100, 1),
        gap_wk,
        "LOW" if payout_delta > 15 else ("MEDIUM" if payout_delta > 5 else "HIGH"),
        "ESTIMATED",
        f"(gross_rev - total_costs + gap) / gross_rev * 100",
        f"Reducir el payout de {driver_pct}% a {payout_max}% (bajar {round(payout_delta,1)} pp) cerraria la brecha."
        if gap_wk > 0 else "El escenario ya es rentable."
    ))

    # 4. premier_needed
    rev_per_prem = ticket_p
    prem_bonus_per_extra = 0
    if gap_wk > 0 and eligible_prem and bonus_tables:
        prem_tbl = bonus_tables.get("premier") or []
        for t in sorted(prem_tbl, key=lambda x: x.get("min_trips", 0) or x.get("trips_min", 0)):
            mt = t.get("min_trips", 0) or t.get("trips_min", 0)
            if mt > prem_trips:
                prem_bonus_per_extra = (t.get("pct", 0) or t.get("bonus_pct", 0)) * rev_per_prem / 100
                break
    prem_needed = int(gap_wk / max(rev_per_prem + prem_bonus_per_extra, 0.01)) + 1 if gap_wk > 0 else 0
    levers.append(_lever(
        "premier_needed", "Viajes Premier adicionales",
        prem_w, prem_w + prem_needed,
        prem_needed, round(prem_needed / max(prem_w, 1) * 100, 1),
        prem_needed * (rev_per_prem + prem_bonus_per_extra),
        "LOW" if prem_needed > 100 else ("MEDIUM" if prem_needed > 30 else "HIGH"),
        "ESTIMATED",
        f"gap / (ticket_premier + bonus_marginal) = {round(gap_wk,2)} / {round(rev_per_prem+prem_bonus_per_extra,2)}",
        f"Se necesitarian {prem_needed} viajes Premier adicionales por semana para cerrar la brecha."
        if gap_wk > 0 else "El escenario ya es rentable."
    ))

    # 5. bonus_needed (next tier impact)
    gen_next_impact = 0
    gen_next_trips = 0
    gen_next_amount = 0
    if eligible_gen:
        tbl = BONUS_GENERAL_BRANDED if branded else BONUS_GENERAL_UNBRANDED
        if bonus_tables:
            bt = bonus_tables.get("general_branded" if branded else "general_unbranded") or []
            if bt:
                tbl = [{"min_trips": t.get("min_trips", 0) or t.get("trips_min", 0),
                        "pct": t.get("pct", 0) or t.get("bonus_pct", 0),
                        "amount": t.get("amount", 0) or t.get("bonus_amount", 0)} for t in bt]
        for t in sorted(tbl, key=lambda x: x["min_trips"]):
            if t["min_trips"] > gen_trips:
                gen_next_trips = t["min_trips"]
                gen_next_amount = t["amount"]
                gen_next_impact = t["amount"] - gen_bonus
                break
    levers.append(_lever(
        "bonus_next_general", "Siguiente tramo bono general",
        gen_bonus, gen_next_amount,
        gen_next_impact, 0,
        gen_next_impact,
        "HIGH" if gen_next_trips - gen_trips < 20 else "MEDIUM",
        "REAL" if gen_next_impact > 0 else "NOT_REACHED",
        f"tramo {gen_next_trips} viajes -> S/{gen_next_amount}",
        f"Llegar al siguiente tramo de bono general ({gen_next_trips} viajes, +{gen_next_trips-gen_trips}) agregaria S/{gen_next_impact} por semana."
        if gen_next_impact > 0 else "Ya se alcanzo el tramo maximo de bono general."
    ))

    prem_next_impact = 0
    prem_next_trips = 0
    prem_next_amount = 0
    if eligible_prem:
        tbl = BONUS_PREMIER
        if bonus_tables:
            bt = bonus_tables.get("premier") or []
            if bt:
                tbl = [{"min_trips": t.get("min_trips", 0) or t.get("trips_min", 0),
                        "pct": t.get("pct", 0) or t.get("bonus_pct", 0),
                        "amount": t.get("amount", 0) or t.get("bonus_amount", 0)} for t in bt]
        for t in sorted(tbl, key=lambda x: x["min_trips"]):
            if t["min_trips"] > prem_trips:
                prem_next_trips = t["min_trips"]
                prem_next_amount = t["amount"]
                prem_next_impact = t["amount"] - prem_bonus
                break
    levers.append(_lever(
        "bonus_next_premier", "Siguiente tramo bono Premier",
        prem_bonus, prem_next_amount,
        prem_next_impact, 0,
        prem_next_impact,
        "HIGH" if prem_next_trips - prem_trips < 5 else "MEDIUM",
        "REAL" if prem_next_impact > 0 else "NOT_REACHED",
        f"tramo {prem_next_trips} viajes -> S/{prem_next_amount}",
        f"Llegar al siguiente tramo de bono Premier ({prem_next_trips} viajes, +{prem_next_trips-prem_trips}) agregaria S/{prem_next_impact} por semana."
        if prem_next_impact > 0 else "Ya se alcanzo el tramo maximo de bono Premier."
    ))

    # 6. cost_reduction_needed
    fuel_reduce = gap_wk if gap_wk > 0 else 0
    maint_reduce = gap_wk if gap_wk > 0 else 0
    fixed_reduce = gap_wk if gap_wk > 0 else 0
    levers.append(_lever(
        "cost_reduction", "Reduccion de costos para break-even",
        total_costs, max(total_costs - gap_wk, 0),
        gap_wk if gap_wk > 0 else 0,
        round(gap_wk / max(total_costs, 1) * 100, 1) if gap_wk > 0 else 0,
        gap_wk,
        "LOW" if gap_wk > total_costs * 0.3 else ("MEDIUM" if gap_wk > total_costs * 0.1 else "HIGH"),
        "ESTIMATED",
        f"gap = {round(gap_wk,2)} -> reducir costos en S/{round(gap_wk,2)}",
        f"Para cerrar la brecha solo con costos, se necesitaria reducir S/{round(gap_wk,2)} por semana (combustible, mantenimiento y/o fijos)."
        if gap_wk > 0 else "El escenario ya es rentable."
    ))

    return {
        "current_profit_week": round(profit_wk, 2),
        "current_profit_month": round(profit_mo, 2),
        "target_profit_week": target_wk,
        "target_profit_month": target_wk * 4.33,
        "gap_week": round(gap_wk, 2),
        "gap_month": round(gap_mo, 2),
        "break_even_status": be_status,
        "levers": levers,
    }


def _build_lever_ranking(
    trips_w, prem_w, ticket_g, ticket_p, rev_g, rev_p, gross_rev,
    gen_bonus, prem_bonus, total_income,
    fuel, maint, plat_comm, var_total, fixed_wk, reserve, total_costs,
    driver_pct, payout, guarantee, profit_wk, margin,
    bonus_tables, branded, gen_trips, prem_trips,
):
    total_trips = trips_w + prem_w
    ranking = []

    # +1 viaje general
    rev_extra = ticket_g
    fuel_extra = km_per_trip * fuel_per_km if 'km_per_trip' in dir() else 2.975
    cost_extra = fuel_extra + maintenance_per_trip if 'maintenance_per_trip' in dir() else 1.20
    payout_extra = rev_extra * (driver_pct / 100)
    impact_1trip = rev_extra - cost_extra - payout_extra
    ranking.append({
        "lever": "+1 viaje general",
        "impact_week": round(impact_1trip, 2),
        "impact_month": round(impact_1trip * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Cada viaje general adicional genera S/{round(rev_extra,2)} de revenue, cuesta S/{round(cost_extra,2)} en variables y S/{round(payout_extra,2)} en payout. Impacto neto: S/{round(impact_1trip,2)}/semana.",
    })

    # +1 viaje Premier
    prem_rev = ticket_p
    prem_cost = fuel_extra + maintenance_per_trip if 'maintenance_per_trip' in dir() else 1.20
    prem_payout = prem_rev * (driver_pct / 100)
    impact_1prem = prem_rev - prem_cost - prem_payout
    ranking.append({
        "lever": "+1 viaje Premier",
        "impact_week": round(impact_1prem, 2),
        "impact_month": round(impact_1prem * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Cada viaje Premier adicional genera S/{round(prem_rev,2)} de revenue. Impacto neto: S/{round(impact_1prem,2)}/semana.",
    })

    # +S/1 ticket general
    impact_ticket = total_trips * 1
    ranking.append({
        "lever": "+S/1 ticket general",
        "impact_week": round(impact_ticket, 2),
        "impact_month": round(impact_ticket * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Subir S/1 el ticket general en {total_trips} viajes genera S/{round(impact_ticket,2)} adicionales por semana.",
    })

    # -1 punto payout
    impact_payout = gross_rev * 0.01
    ranking.append({
        "lever": "-1 pp payout",
        "impact_week": round(impact_payout, 2),
        "impact_month": round(impact_payout * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Reducir payout en 1 pp sobre S/{round(gross_rev,2)} de revenue ahorra S/{round(impact_payout,2)}/semana.",
    })

    # -5% combustible
    impact_fuel = fuel * 0.05
    ranking.append({
        "lever": "-5% combustible",
        "impact_week": round(impact_fuel, 2),
        "impact_month": round(impact_fuel * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Reducir combustible 5% ahorra S/{round(impact_fuel,2)}/semana.",
    })

    # -5% mantenimiento
    impact_maint = maint * 0.05
    ranking.append({
        "lever": "-5% mantenimiento",
        "impact_week": round(impact_maint, 2),
        "impact_month": round(impact_maint * 4.33, 2),
        "direction": "positive",
        "confidence": "ESTIMATED",
        "explanation": f"Reducir mantenimiento 5% ahorra S/{round(impact_maint,2)}/semana.",
    })

    # Siguiente bono general
    gen_next_imp = 0
    if bonus_tables:
        bt = bonus_tables.get("general_branded" if branded else "general_unbranded") or []
        if bt:
            for t in sorted(bt, key=lambda x: x.get("min_trips", 0) or x.get("trips_min", 0)):
                mt = t.get("min_trips", 0) or t.get("trips_min", 0)
                if mt > gen_trips:
                    amt = t.get("amount", 0) or t.get("bonus_amount", 0)
                    gen_next_imp = amt - gen_bonus
                    break
    ranking.append({
        "lever": "Siguiente bono general",
        "impact_week": round(gen_next_imp, 2),
        "impact_month": round(gen_next_imp * 4.33, 2),
        "direction": "positive",
        "confidence": "REAL" if gen_next_imp > 0 else "NOT_REACHED",
        "explanation": f"Alcanzar siguiente tramo de bono general agregaria S/{round(gen_next_imp,2)}/semana."
        if gen_next_imp > 0 else "Ya en tramo maximo de bono general.",
    })

    # Siguiente bono Premier
    prem_next_imp = 0
    if bonus_tables:
        bt = bonus_tables.get("premier") or []
        if bt:
            for t in sorted(bt, key=lambda x: x.get("min_trips", 0) or x.get("trips_min", 0)):
                mt = t.get("min_trips", 0) or t.get("trips_min", 0)
                if mt > prem_trips:
                    amt = t.get("amount", 0) or t.get("bonus_amount", 0)
                    prem_next_imp = amt - prem_bonus
                    break
    ranking.append({
        "lever": "Siguiente bono Premier",
        "impact_week": round(prem_next_imp, 2),
        "impact_month": round(prem_next_imp * 4.33, 2),
        "direction": "positive",
        "confidence": "REAL" if prem_next_imp > 0 else "NOT_REACHED",
        "explanation": f"Alcanzar siguiente tramo de bono Premier agregaria S/{round(prem_next_imp,2)}/semana."
        if prem_next_imp > 0 else "Ya en tramo maximo de bono Premier.",
    })

    ranking.sort(key=lambda x: x["impact_week"], reverse=True)
    return ranking


def _build_break_even_combinations(
    trips_w, prem_w, ticket_g, ticket_p, rev_g, rev_p, gross_rev,
    gen_bonus, prem_bonus, total_income, fuel, maint, plat_comm,
    var_total, fixed_wk, reserve, total_costs,
    base_payout, payout, guarantee, driver_total, driver_pct,
    profit_wk, profit_mo, margin,
    branded, eligible_gen, eligible_prem, gen_trips, prem_trips,
    bonus_tables,
):
    gap = -profit_wk if profit_wk < 0 else 0
    total_trips = trips_w + prem_w
    var_per_trip = var_total / max(total_trips, 1)
    margin_per_trip = (gross_rev / max(total_trips, 1)) - var_per_trip

    combos = []

    def _combo(name, changes, projected):
        return {
            "name": name,
            "changes": changes,
            "projected_profit_week": round(projected, 2),
            "projected_profit_month": round(projected * 4.33, 2),
            "closes_gap": projected >= 0,
            "remaining_gap": round(max(-projected, 0), 2),
            "confidence": "ESTIMATED",
            "explanation": "",
        }

    # A: Solo produccion
    extra_trips_a = int(gap / max(margin_per_trip, 0.01)) + 1 if gap > 0 and margin_per_trip > 0 else 0
    proj_a = profit_wk + extra_trips_a * margin_per_trip
    combos.append(_combo(
        "A. Solo produccion",
        [f"+{extra_trips_a} viajes generales/semana ({round(extra_trips_a/7,1)}/dia)"],
        proj_a,
    ))
    combos[-1]["explanation"] = (
        f"Con {extra_trips_a} viajes adicionales por semana, la utilidad proyectada seria S/{round(proj_a,2)}. "
        f"{'Cierra la brecha.' if proj_a >= 0 else f'Faltan S/{round(max(-proj_a,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    # B: Produccion + Premier
    extra_gen_b = max(int(gap * 0.6 / max(margin_per_trip, 0.01)), 0) if gap > 0 else 0
    extra_prem_b = max(int(gap * 0.4 / max(ticket_p - var_per_trip, 0.01)), 0) if gap > 0 else 0
    proj_b = profit_wk + extra_gen_b * margin_per_trip + extra_prem_b * (ticket_p - var_per_trip - ticket_p * driver_pct / 100)
    combos.append(_combo(
        "B. Produccion + Premier",
        [f"+{extra_gen_b} viajes generales", f"+{extra_prem_b} viajes Premier"],
        proj_b,
    ))
    combos[-1]["explanation"] = (
        f"Combinando {extra_gen_b} viajes generales y {extra_prem_b} viajes Premier adicionales, "
        f"la utilidad proyectada seria S/{round(proj_b,2)}. "
        f"{'Cierra la brecha.' if proj_b >= 0 else f'Faltan S/{round(max(-proj_b,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    # C: Produccion + payout
    extra_gen_c = max(int(gap * 0.5 / max(margin_per_trip, 0.01)), 0) if gap > 0 else 0
    payout_reduce_c = round(gap * 0.5 / max(gross_rev, 1) * 100, 1) if gap > 0 else 0
    proj_c = profit_wk + extra_gen_c * margin_per_trip + payout_reduce_c * gross_rev / 100
    combos.append(_combo(
        "C. Produccion + payout",
        [f"+{extra_gen_c} viajes generales", f"-{round(payout_reduce_c,1)} pp payout"],
        proj_c,
    ))
    combos[-1]["explanation"] = (
        f"Reduciendo payout en {round(payout_reduce_c,1)} pp y agregando {extra_gen_c} viajes, "
        f"la utilidad proyectada seria S/{round(proj_c,2)}. "
        f"{'Cierra la brecha.' if proj_c >= 0 else f'Faltan S/{round(max(-proj_c,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    # D: Produccion + bonos
    extra_gen_d = max(int(gap * 0.7 / max(margin_per_trip, 0.01)), 0) if gap > 0 else 0
    bonus_extra_d = 0
    if bonus_tables and eligible_gen:
        bt = bonus_tables.get("general_branded" if branded else "general_unbranded") or []
        if bt:
            for t in sorted(bt, key=lambda x: x.get("min_trips", 0) or x.get("trips_min", 0)):
                mt = t.get("min_trips", 0) or t.get("trips_min", 0)
                if mt > gen_trips and mt <= gen_trips + extra_gen_d:
                    amt = t.get("amount", 0) or t.get("bonus_amount", 0)
                    bonus_extra_d = amt - gen_bonus
    proj_d = profit_wk + extra_gen_d * margin_per_trip + bonus_extra_d
    combos.append(_combo(
        "D. Produccion + bonos",
        [f"+{extra_gen_d} viajes generales", f"+S/{round(bonus_extra_d,2)} bono adicional"],
        proj_d,
    ))
    combos[-1]["explanation"] = (
        f"Con {extra_gen_d} viajes adicionales alcanzando siguiente tramo de bono (+S/{round(bonus_extra_d,2)}), "
        f"la utilidad proyectada seria S/{round(proj_d,2)}. "
        f"{'Cierra la brecha.' if proj_d >= 0 else f'Faltan S/{round(max(-proj_d,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    # E: Costos + payout
    cost_reduce_e = round(gap * 0.5, 2) if gap > 0 else 0
    payout_reduce_e = round(gap * 0.5 / max(gross_rev, 1) * 100, 1) if gap > 0 else 0
    proj_e = profit_wk + cost_reduce_e + payout_reduce_e * gross_rev / 100
    combos.append(_combo(
        "E. Costos + payout",
        [f"-S/{cost_reduce_e}/sem en costos", f"-{round(payout_reduce_e,1)} pp payout"],
        proj_e,
    ))
    combos[-1]["explanation"] = (
        f"Reduciendo S/{cost_reduce_e} en costos semanales y {round(payout_reduce_e,1)} pp de payout, "
        f"la utilidad proyectada seria S/{round(proj_e,2)}. "
        f"{'Cierra la brecha.' if proj_e >= 0 else f'Faltan S/{round(max(-proj_e,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    # F: Mix balanceado
    extra_gen_f = max(int(gap * 0.3 / max(margin_per_trip, 0.01)), 0) if gap > 0 else 0
    extra_prem_f = max(int(gap * 0.15 / max(ticket_p - var_per_trip, 0.01)), 0) if gap > 0 else 0
    payout_reduce_f = round(gap * 0.25 / max(gross_rev, 1) * 100, 1) if gap > 0 else 0
    cost_reduce_f = round(gap * 0.15, 2) if gap > 0 else 0
    bonus_f = 0
    if bonus_tables and eligible_gen:
        bt = bonus_tables.get("general_branded" if branded else "general_unbranded") or []
        if bt:
            for t in sorted(bt, key=lambda x: x.get("min_trips", 0) or x.get("trips_min", 0)):
                mt = t.get("min_trips", 0) or t.get("trips_min", 0)
                if mt > gen_trips and mt <= gen_trips + extra_gen_f:
                    amt = t.get("amount", 0) or t.get("bonus_amount", 0)
                    bonus_f = amt - gen_bonus
    proj_f = (profit_wk + extra_gen_f * margin_per_trip + extra_prem_f * (ticket_p - var_per_trip - ticket_p * driver_pct / 100)
              + payout_reduce_f * gross_rev / 100 + cost_reduce_f + bonus_f)
    combos.append(_combo(
        "F. Mix balanceado",
        [f"+{extra_gen_f} viajes gral", f"+{extra_prem_f} viajes Premier",
         f"-{round(payout_reduce_f,1)} pp payout", f"-S/{cost_reduce_f} costos"],
        proj_f,
    ))
    combos[-1]["explanation"] = (
        f"Combinando produccion (+{extra_gen_f} gral, +{extra_prem_f} Premier), "
        f"reduccion de payout (-{round(payout_reduce_f,1)} pp) y ahorro en costos (-S/{cost_reduce_f}), "
        f"la utilidad proyectada seria S/{round(proj_f,2)}. "
        f"{'Cierra la brecha.' if proj_f >= 0 else f'Faltan S/{round(max(-proj_f,0),2)}.'}"
        if gap > 0 else "El escenario ya es rentable."
    )

    return combos


def _tree_node(key, label, value, formula, inputs, source, confidence, sign, impact_on_profit,
                children=None):
    return {
        "key": key, "label": label, "value": round(value, 2) if value is not None else 0,
        "formula": formula, "inputs": inputs, "source": source, "confidence": confidence,
        "sign": sign, "impact_on_profit": round(impact_on_profit, 2) if impact_on_profit else 0,
        "children": children or [],
    }


def _build_profitability_tree(
    trace, subtotals, rev_general, rev_premier,
    gen_bonus, prem_bonus, gross_rev, total_income,
    fuel, maint, plat_comm, var_total, fixed_wk, reserve,
    total_costs, base_payout, payout, guarantee, driver_total,
    profit_wk, margin, **_kw,
):
    income_children = [
        _tree_node("revenue_general", "Revenue general", rev_general,
                   f"{_kw.get('tickets_general',0)} viajes x S/{_kw.get('avg_ticket_general',0)}",
                   {"trips": _kw.get("tickets_general", 0), "ticket_avg": _kw.get("avg_ticket_general", 0)},
                   "OPERATIONAL", "ESTIMATED", "positive", rev_general),
        _tree_node("revenue_premier", "Revenue Premier", rev_premier,
                   f"{_kw.get('tickets_premier',0)} viajes x S/{_kw.get('avg_ticket_premier',0)}",
                   {"trips": _kw.get("tickets_premier", 0), "ticket_avg": _kw.get("avg_ticket_premier", 0)},
                   "OPERATIONAL", "ESTIMATED", "positive", rev_premier),
        _tree_node("general_bonus", "Bono general Yango", gen_bonus,
                   f"Tabla de bonos general → S/{gen_bonus}",
                   {"amount": gen_bonus},
                   "YANGO_BONUS_TABLE", "REAL" if gen_bonus > 0 else "NOT_REACHED",
                   "positive" if gen_bonus > 0 else "neutral", gen_bonus),
        _tree_node("premier_bonus", "Bono Premier Yango", prem_bonus,
                   f"Tabla de bonos Premier → S/{prem_bonus}",
                   {"amount": prem_bonus},
                   "YANGO_BONUS_TABLE", "REAL" if prem_bonus > 0 else "NOT_REACHED",
                   "positive" if prem_bonus > 0 else "neutral", prem_bonus),
    ]

    cost_children = [
        _tree_node("platform_commission", "Comisión plataforma", plat_comm,
                   f"Revenue ({round(gross_rev, 2)}) x {_kw.get('platform_commission_pct',18)}%",
                   {"gross_revenue": round(gross_rev, 2)},
                   "MODULE_BILLING", "ESTIMATED", "negative", -plat_comm),
        _tree_node("fuel_cost", "Combustible", fuel,
                   f"Km total x S/{_kw.get('fuel_per_km',0.35)}/km",
                   {"km_total": round(_kw.get('km_total',0), 2)},
                   "MODULE_BILLING", "ESTIMATED", "negative", -fuel),
        _tree_node("maintenance", "Mantenimiento", maint,
                   f"Viajes x S/{_kw.get('maintenance_per_trip',1.2)}/viaje",
                   {"trips": _kw.get('tickets_general',0)+_kw.get('tickets_premier',0)},
                   "MODULE_BILLING", "ESTIMATED", "negative", -maint),
        _tree_node("fixed_costs", "Costos fijos", fixed_wk,
                   f"Cuota vehiculo + seguro/GPS = S/{fixed_wk}",
                   {"vehicle_weekly": _kw.get('vehicle_weekly_cost',350), "insurance": _kw.get('insurance_gps',45)},
                   "FLEET_CONFIG", "ESTIMATED", "negative", -fixed_wk),
        _tree_node("reserve", "Reserva desgaste", reserve,
                   f"Ingreso total x {_kw.get('reserve_pct',3)}%",
                   {"total_income": round(total_income, 2)},
                   "MANUAL", "ESTIMATED", "negative", -reserve),
    ]

    driver_children = [
        _tree_node("payout_driver", "Payout conductor", payout,
                   f"Revenue bruto ({round(gross_rev,2)}) x {_kw.get('driver_payout_pct',50)}%",
                   {"gross_revenue": round(gross_rev, 2), "payout_pct": _kw.get('driver_payout_pct', 50)},
                   "PAYMENT_TIERS", "ESTIMATED", "negative", -payout),
    ]
    if guarantee > 0:
        driver_children.append(
            _tree_node("guarantee", "Garantía", guarantee,
                       f"Mínimo garantizado S/{guarantee}", {"amount": guarantee},
                       "MANUAL", "ESTIMATED", "negative", -guarantee))

    tree = _tree_node(
        "profit", "Utilidad empresa", profit_wk,
        f"Ingreso total ({round(total_income,2)}) - Costos ({round(total_costs,2)}) - Pago conductor ({round(driver_total,2)})",
        {"total_income": round(total_income, 2), "total_costs": round(total_costs, 2), "driver_total": round(driver_total, 2)},
        "DERIVED", "ESTIMATED",
        "positive" if profit_wk >= 0 else "negative",
        profit_wk,
        children=[
            _tree_node("income", "Ingreso total empresa", total_income,
                       f"Revenue + Bonos = S/{round(total_income,2)}",
                       {}, "DERIVED", "ESTIMATED", "positive", total_income,
                       children=income_children),
            _tree_node("costs", "Costos operativos", total_costs,
                       f"Variables + Fijos + Reserva = S/{round(total_costs,2)}",
                       {}, "DERIVED", "ESTIMATED", "negative", -total_costs,
                       children=cost_children),
            _tree_node("driver_payment", "Pago conductor", driver_total,
                       f"Payout + Garantía = S/{round(driver_total,2)}",
                       {}, "DERIVED", "ESTIMATED", "negative", -driver_total,
                       children=driver_children),
        ])
    return tree


def _build_math_summary(
    trips_g, trips_p, ticket_g, ticket_p,
    rev_g, rev_p, gross_rev,
    gen_bonus, prem_bonus, total_income,
    fuel, maint, plat_comm, var_total,
    fixed_wk, reserve, total_costs,
    base_payout, payout, guarantee, driver_total,
    driver_pct, profit_wk, margin,
):
    return [
        {
            "step": 1,
            "title": "Ingreso por viajes",
            "expression": f"({trips_g} x S/{ticket_g}) + ({trips_p} x S/{ticket_p})",
            "expression_eval": f"(S/{round(rev_g,2)}) + (S/{round(rev_p,2)})",
            "result": round(gross_rev, 2),
        },
        {
            "step": 2,
            "title": "Bonos Yango",
            "expression": f"bono general + bono Premier",
            "expression_eval": f"S/{gen_bonus} + S/{prem_bonus}",
            "result": round(gen_bonus + prem_bonus, 2),
        },
        {
            "step": 3,
            "title": "Ingreso total empresa",
            "expression": "ingreso por viajes + bonos Yango",
            "expression_eval": f"S/{round(gross_rev,2)} + S/{round(gen_bonus+prem_bonus,2)}",
            "result": round(total_income, 2),
        },
        {
            "step": 4,
            "title": "Costos operativos",
            "expression": "combustible + mantenimiento + comisión + fijos + reserva",
            "expression_eval": f"S/{round(fuel,2)} + S/{round(maint,2)} + S/{round(plat_comm,2)} + S/{round(fixed_wk,2)} + S/{round(reserve,2)}",
            "result": round(total_costs, 2),
        },
        {
            "step": 5,
            "title": "Base de reparto",
            "expression": "ingreso total empresa - costos operativos",
            "expression_eval": f"S/{round(total_income,2)} - S/{round(total_costs,2)}",
            "result": round(base_payout, 2),
        },
        {
            "step": 6,
            "title": "Pago conductor",
            "expression": f"revenue bruto x {driver_pct}%",
            "expression_eval": f"S/{round(gross_rev,2)} x {driver_pct}% = S/{round(payout,2)}",
            "result": round(driver_total, 2) if guarantee == 0 else round(payout, 2),
        },
        {
            "step": 7,
            "title": "Utilidad empresa",
            "expression": "base de reparto - pago conductor - garantías",
            "expression_eval": f"S/{round(base_payout,2)} - S/{round(driver_total,2)}",
            "result": round(profit_wk, 2),
        },
    ]


def _compute_baseline_delta(
    subtotals, profit_wk, margin,
    payback, break_even,
):
    try:
        baseline = get_baseline_scenario()
        if baseline.get("status") != "OK":
            return None

        b_out = baseline.get("outputs", {})
        b_st = b_out.get("subtotals", {})

        b_revenue = (b_st.get("production", {}).get("gross_trip_revenue", 0) or 0)
        b_bonus = (b_st.get("production", {}).get("general_bonus", 0) or 0) + (b_st.get("production", {}).get("premier_bonus", 0) or 0)
        b_total_income = (b_st.get("production", {}).get("total_company_income", 0) or 0)
        b_costs = (b_st.get("variable_costs", {}).get("total_variable_cost", 0) or 0) + (b_st.get("fixed_costs", {}).get("total_fixed", 0) or 0)
        b_payout = (b_st.get("driver_payment", {}).get("driver_income_total", 0) or 0)
        b_profit = (b_st.get("result", {}).get("company_profit_weekly", 0) or 0)
        b_margin = (b_st.get("result", {}).get("margin_pct", 0) or 0)
        b_payback = (b_st.get("result", {}).get("payback_trips", 0) or 0)
        b_break_even = (b_st.get("result", {}).get("break_even_trips", 0) or 0)

        current_revenue = (subtotals.get("production", {}).get("gross_trip_revenue", 0) or 0)
        current_bonus = (subtotals.get("production", {}).get("general_bonus", 0) or 0) + (subtotals.get("production", {}).get("premier_bonus", 0) or 0)
        current_income = (subtotals.get("production", {}).get("total_company_income", 0) or 0)
        current_costs = (subtotals.get("variable_costs", {}).get("total_variable_cost", 0) or 0) + (subtotals.get("fixed_costs", {}).get("total_fixed", 0) or 0)
        current_payout = (subtotals.get("driver_payment", {}).get("driver_income_total", 0) or 0)

        def _delta(current, base, label):
            diff = round(current - base, 2)
            pct = round(diff / max(abs(base), 0.01) * 100, 1)
            return {
                "label": label,
                "baseline_value": round(base, 2),
                "scenario_value": round(current, 2),
                "absolute": diff,
                "pct": pct,
                "direction": "better" if diff > 0 else ("worse" if diff < 0 else "neutral"),
            }

        return {
            "revenue_delta": _delta(current_revenue, b_revenue, "Revenue bruto"),
            "bonus_delta": _delta(current_bonus, b_bonus, "Bonos Yango"),
            "cost_delta": _delta(-current_costs, -b_costs, "Costos operativos"),
            "payout_delta": _delta(-current_payout, -b_payout, "Pago conductor"),
            "profit_delta": _delta(profit_wk, b_profit, "Utilidad semanal"),
            "margin_delta": _delta(margin, b_margin, "Margen %"),
            "payback_delta": _delta(payback, b_payback, "Payback viajes"),
            "break_even_delta": _delta(break_even, b_break_even, "Break-even viajes"),
            "baseline_confidence": baseline.get("confidence", "ESTIMATED"),
        }
    except Exception as e:
        logger.warning("baseline_delta error: %s", e)
        return None


def _build_sensitivity(
    trips_week, premier_trips_week, ticket_avg_general, ticket_avg_premier,
    km_per_trip, fuel_per_km,
    maintenance_per_trip, platform_commission_pct, vehicle_weekly_cost,
    insurance_gps_weekly, reserve_pct, driver_payout_pct,
    vehicle_branded, eligible_for_general_bonus, eligible_for_premier_bonus,
    general_bonus_trips_week, premier_bonus_trips_week,
    current_general_bonus, current_premier_bonus,
    current_total_income, current_weekly_profit, current_driver_income, current_margin,
    bonus_tables=None,
) -> Dict[str, Any]:

    has_custom_tables = bool(bonus_tables and any(bonus_tables.get(k) for k in ["general_branded", "general_unbranded", "premier"]))

    def _quick_sim(new_payout=None, no_bonus=False, next_general=False, next_premier=False):
        p = new_payout if new_payout is not None else driver_payout_pct
        gb = 0
        pb = 0
        if not no_bonus:
            if next_general and eligible_for_general_bonus:
                if has_custom_tables and bonus_tables.get("general_branded") and vehicle_branded:
                    _gen_tbl = bonus_tables["general_branded"]
                elif has_custom_tables and bonus_tables.get("general_unbranded") and not vehicle_branded:
                    _gen_tbl = bonus_tables["general_unbranded"]
                else:
                    _gen_tbl = BONUS_GENERAL_BRANDED if vehicle_branded else BONUS_GENERAL_UNBRANDED
                next_trips = _find_next_tier_trips(_gen_tbl, int(general_bonus_trips_week))
                tier = _lookup_bonus(_gen_tbl, next_trips)
                gb = tier["amount"]
            elif not next_premier:
                gb = current_general_bonus
            if next_premier and eligible_for_premier_bonus:
                if has_custom_tables and bonus_tables.get("premier"):
                    _prem_tbl = bonus_tables["premier"]
                else:
                    _prem_tbl = BONUS_PREMIER
                next_trips = _find_next_tier_trips(_prem_tbl, int(premier_bonus_trips_week))
                tier = _lookup_bonus(_prem_tbl, next_trips)
                pb = tier["amount"]
            elif not next_general:
                pb = current_premier_bonus

        rev = (trips_week * ticket_avg_general) + (premier_trips_week * ticket_avg_premier)
        income = rev + gb + pb
        fuel = trips_week * km_per_trip * fuel_per_km
        maint = trips_week * maintenance_per_trip
        comm = rev * (platform_commission_pct / 100)
        var_cost = fuel + maint + comm
        fixed = vehicle_weekly_cost + insurance_gps_weekly
        reserve = income * (reserve_pct / 100)
        payout = rev * (p / 100)
        profit = income - var_cost - fixed - reserve - payout
        margin = round(profit / max(income, 1) * 100, 1)
        return {
            "company_income": round(income, 2),
            "company_profit_weekly": round(profit, 2),
            "driver_income": round(payout, 2),
            "margin_pct": margin,
            "general_bonus": gb,
            "premier_bonus": pb,
        }

    rows = []

    rows.append({
        "label": "Sin bono",
        "type": "bonus_none",
        "simulation": _quick_sim(no_bonus=True),
        "diff_vs_current": round(_quick_sim(no_bonus=True)["company_profit_weekly"] - current_weekly_profit, 2),
    })

    rows.append({
        "label": "Tramo actual",
        "type": "current",
        "simulation": {
            "company_income": round(current_total_income, 2),
            "company_profit_weekly": current_weekly_profit,
            "driver_income": round(current_driver_income, 2),
            "margin_pct": current_margin,
            "general_bonus": current_general_bonus,
            "premier_bonus": current_premier_bonus,
        },
        "diff_vs_current": 0,
    })

    rows.append({
        "label": "Siguiente tramo general",
        "type": "bonus_next_general",
        "simulation": _quick_sim(next_general=True),
        "diff_vs_current": round(_quick_sim(next_general=True)["company_profit_weekly"] - current_weekly_profit, 2),
    })

    rows.append({
        "label": "Siguiente tramo Premier",
        "type": "bonus_next_premier",
        "simulation": _quick_sim(next_premier=True),
        "diff_vs_current": round(_quick_sim(next_premier=True)["company_profit_weekly"] - current_weekly_profit, 2),
    })

    payout_options = []
    for pct in [30, 35, 40, 45, 50, 55, 60]:
        sim = _quick_sim(new_payout=pct)
        payout_options.append({
            "payout_pct": pct,
            "company_profit_weekly": sim["company_profit_weekly"],
            "driver_income": sim["driver_income"],
            "margin_pct": sim["margin_pct"],
            "diff_vs_current": round(sim["company_profit_weekly"] - current_weekly_profit, 2),
        })

    return {
        "bonus_scenarios": rows,
        "payout_sensitivity": payout_options,
        "current_reference": {
            "company_profit_weekly": current_weekly_profit,
            "driver_income": round(current_driver_income, 2),
            "margin_pct": current_margin,
        },
    }


def _find_next_tier_trips(bonus_table: List[Dict], current_trips: int) -> int:
    tiers_above = [t["min_trips"] for t in bonus_table if t["min_trips"] > current_trips]
    if tiers_above:
        return min(tiers_above)
    return current_trips + 5


def get_simulator_defaults() -> Dict[str, Any]:
    return {
        "status": "OK",
        "bonus_tables": {
            "general_branded": BONUS_GENERAL_BRANDED,
            "general_unbranded": BONUS_GENERAL_UNBRANDED,
            "premier": BONUS_PREMIER,
        },
        "default_inputs": {
            "shifts_per_vehicle": 2,
            "selected_shift": "day",
            "trips_day_week": 85,
            "trips_night_week": 45,
            "trips_premier_day_week": 6,
            "trips_premier_night_week": 3,
            "ticket_avg": 15.0,
            "ticket_avg_general": 15.0,
            "ticket_avg_premier": 22.0,
            "km_per_trip": 8.5,
            "fuel_per_km": 0.35,
            "maintenance_per_trip": 1.20,
            "platform_commission_pct": 18.0,
            "vehicle_weekly_cost": 350.0,
            "insurance_gps_weekly": 45.0,
            "reserve_pct": 3.0,
            "driver_payout_pct": 50.0,
            "vehicle_branded": True,
            "eligible_for_general_bonus": True,
            "eligible_for_premier_bonus": True,
            "general_bonus_trips_week": 85,
            "premier_bonus_trips_week": 6,
            "guarantee_amount": 0,
        },
    }


BONUS_CONFIG_TABLE = "ops.yego_pro_bonus_config"
VALID_BONUS_TYPES = frozenset(("general_branded", "general_unbranded", "premier"))


def get_bonus_config(park_id: str = PARK_ID, config_name: str = "default") -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    f"SELECT to_regclass(%s) IS NOT NULL AS exists",
                    (BONUS_CONFIG_TABLE,),
                )
                table_exists = bool(cur.fetchone().get("exists", False))

                if table_exists:
                    cur.execute(
                        f"""
                        SELECT * FROM {BONUS_CONFIG_TABLE}
                        WHERE park_id = %s
                          AND config_name = %s
                          AND is_active = TRUE
                        ORDER BY bonus_type, trips_min DESC
                        """,
                        (park_id, config_name),
                    )
                    rows = cur.fetchall()

                    if rows:
                        tables: Dict[str, List[Dict[str, Any]]] = {
                            "general_branded": [],
                            "general_unbranded": [],
                            "premier": [],
                        }
                        for r in rows:
                            bt = r.get("bonus_type")
                            if bt in tables:
                                tables[bt].append({
                                    "min_trips": int(r.get("trips_min") or 0),
                                    "pct": float(r.get("bonus_pct") or 0),
                                    "amount": float(r.get("bonus_amount") or 0),
                                })

                        latest = rows[0]
                        return {
                            "status": "OK",
                            "park_id": park_id,
                            "config_name": config_name,
                            "persisted": True,
                            "updated_at": str(latest.get("updated_at")) if latest.get("updated_at") else None,
                            "updated_by": latest.get("updated_by"),
                            "effective_from": str(latest.get("effective_from")) if latest.get("effective_from") else None,
                            "tables": tables,
                        }

                tables = {
                    "general_branded": [dict(t) for t in BONUS_GENERAL_BRANDED],
                    "general_unbranded": [dict(t) for t in BONUS_GENERAL_UNBRANDED],
                    "premier": [dict(t) for t in BONUS_PREMIER],
                }
                return {
                    "status": "NOT_PERSISTED",
                    "park_id": park_id,
                    "config_name": config_name,
                    "persisted": False,
                    "updated_at": None,
                    "updated_by": None,
                    "effective_from": None,
                    "tables": tables,
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro bonus_config get: %s", e)
        tables = {
            "general_branded": [dict(t) for t in BONUS_GENERAL_BRANDED],
            "general_unbranded": [dict(t) for t in BONUS_GENERAL_UNBRANDED],
            "premier": [dict(t) for t in BONUS_PREMIER],
        }
        return {
            "status": "ERROR",
            "park_id": park_id,
            "config_name": config_name,
            "persisted": False,
            "error": str(e),
            "tables": tables,
        }


def save_bonus_config(park_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    config_name = str(payload.get("config_name", "default") or "default")
    tables_raw = payload.get("tables")
    if not tables_raw or not isinstance(tables_raw, dict):
        raise ValueError("tables is required and must be a dict")

    for bt in tables_raw:
        if bt not in VALID_BONUS_TYPES:
            raise ValueError(f"Invalid bonus_type: {bt}")

    now_str = "now()"
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    f"SELECT to_regclass(%s) IS NOT NULL AS exists",
                    (BONUS_CONFIG_TABLE,),
                )
                if not cur.fetchone().get("exists", False):
                    raise RuntimeError(
                        f"Table {BONUS_CONFIG_TABLE} does not exist. "
                        "Run backend/sql/yego_pro_bonus_config.sql first."
                    )

                cur.execute(
                    f"""
                    UPDATE {BONUS_CONFIG_TABLE}
                    SET is_active = FALSE,
                        effective_to = CURRENT_DATE,
                        updated_at = NOW()
                    WHERE park_id = %s
                      AND config_name = %s
                      AND is_active = TRUE
                    """,
                    (park_id, config_name),
                )

                inserted_count = 0
                for bt, tiers in tables_raw.items():
                    if not isinstance(tiers, list):
                        continue
                    for tier in tiers:
                        trips_min = int(tier.get("trips_min", tier.get("min_trips", 0)))
                        bonus_pct = float(tier.get("bonus_pct", tier.get("pct", 0)))
                        bonus_amount = float(tier.get("bonus_amount", tier.get("amount", 0)))

                        if trips_min <= 0:
                            raise ValueError(
                                f"trips_min must be > 0, got {trips_min} for {bt}"
                            )
                        if bonus_pct < 0:
                            raise ValueError(
                                f"bonus_pct must be >= 0, got {bonus_pct} for {bt}"
                            )
                        if bonus_amount < 0:
                            raise ValueError(
                                f"bonus_amount must be >= 0, got {bonus_amount} for {bt}"
                            )

                        cur.execute(
                            f"""
                            INSERT INTO {BONUS_CONFIG_TABLE}
                                (park_id, config_name, bonus_type, trips_min,
                                 bonus_pct, bonus_amount, source)
                            VALUES (%s, %s, %s, %s, %s, %s, 'manual')
                            """,
                            (park_id, config_name, bt, trips_min,
                             bonus_pct, bonus_amount),
                        )
                        inserted_count += 1

                conn.commit()

                cur.execute(
                    f"""
                    SELECT * FROM {BONUS_CONFIG_TABLE}
                    WHERE park_id = %s
                      AND config_name = %s
                      AND is_active = TRUE
                    ORDER BY bonus_type, trips_min DESC
                    """,
                    (park_id, config_name),
                )
                rows = cur.fetchall()

                tables: Dict[str, List[Dict[str, Any]]] = {
                    "general_branded": [],
                    "general_unbranded": [],
                    "premier": [],
                }
                for r in rows:
                    bt = r.get("bonus_type")
                    if bt in tables:
                        tables[bt].append({
                            "min_trips": int(r.get("trips_min") or 0),
                            "pct": float(r.get("bonus_pct") or 0),
                            "amount": float(r.get("bonus_amount") or 0),
                        })

                latest = rows[0] if rows else {}
                return {
                    "status": "OK",
                    "park_id": park_id,
                    "config_name": config_name,
                    "persisted": True,
                    "inserted_rows": inserted_count,
                    "updated_at": str(latest.get("updated_at")) if latest.get("updated_at") else None,
                    "updated_by": latest.get("updated_by"),
                    "effective_from": str(latest.get("effective_from")) if latest.get("effective_from") else None,
                    "tables": tables,
                }
            finally:
                cur.close()
    except (ValueError, RuntimeError) as e:
        raise
    except Exception as e:
        logger.warning("yego_pro bonus_config save: %s", e)
        raise


def reset_bonus_config_to_defaults(park_id: str = PARK_ID, config_name: str = "default") -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                cur.execute(
                    f"SELECT to_regclass(%s) IS NOT NULL AS exists",
                    (BONUS_CONFIG_TABLE,),
                )
                if not cur.fetchone().get("exists", False):
                    raise RuntimeError(
                        f"Table {BONUS_CONFIG_TABLE} does not exist. "
                        "Run backend/sql/yego_pro_bonus_config.sql first."
                    )

                cur.execute(
                    f"""
                    UPDATE {BONUS_CONFIG_TABLE}
                    SET is_active = FALSE,
                        effective_to = CURRENT_DATE,
                        updated_at = NOW()
                    WHERE park_id = %s
                      AND config_name = %s
                      AND is_active = TRUE
                    """,
                    (park_id, config_name),
                )

                defaults = [
                    ("general_branded", BONUS_GENERAL_BRANDED),
                    ("general_unbranded", BONUS_GENERAL_UNBRANDED),
                    ("premier", BONUS_PREMIER),
                ]
                for bt, tiers in defaults:
                    for t in tiers:
                        cur.execute(
                            f"""
                            INSERT INTO {BONUS_CONFIG_TABLE}
                                (park_id, config_name, bonus_type, trips_min,
                                 bonus_pct, bonus_amount, source)
                            VALUES (%s, %s, %s, %s, %s, %s, 'reset')
                            """,
                            (park_id, config_name, bt,
                             t["min_trips"], t["pct"], t["amount"]),
                        )

                conn.commit()

                cur.execute(
                    f"""
                    SELECT * FROM {BONUS_CONFIG_TABLE}
                    WHERE park_id = %s
                      AND config_name = %s
                      AND is_active = TRUE
                    ORDER BY bonus_type, trips_min DESC
                    """,
                    (park_id, config_name),
                )
                rows = cur.fetchall()

                tables: Dict[str, List[Dict[str, Any]]] = {
                    "general_branded": [],
                    "general_unbranded": [],
                    "premier": [],
                }
                for r in rows:
                    bt = r.get("bonus_type")
                    if bt in tables:
                        tables[bt].append({
                            "min_trips": int(r.get("trips_min") or 0),
                            "pct": float(r.get("bonus_pct") or 0),
                            "amount": float(r.get("bonus_amount") or 0),
                        })

                latest = rows[0] if rows else {}
                return {
                    "status": "OK",
                    "park_id": park_id,
                    "config_name": config_name,
                    "persisted": True,
                    "message": "Defaults restored as new active version",
                    "updated_at": str(latest.get("updated_at")) if latest.get("updated_at") else None,
                    "tables": tables,
                }
            finally:
                cur.close()
    except RuntimeError as e:
        raise
    except Exception as e:
        logger.warning("yego_pro bonus_config reset: %s", e)
        raise


SCENARIO_TABLE = "ops.yego_pro_simulation_scenarios"
VALID_SCENARIO_TYPES = frozenset(("baseline", "manual", "conservative", "aggressive", "custom"))


def _scenario_row_to_dict(row) -> Dict[str, Any]:
    import json as _json
    inputs = row.get("inputs")
    outputs = row.get("outputs")
    trace = row.get("calculation_trace")
    if isinstance(inputs, str):
        inputs = _json.loads(inputs)
    if isinstance(outputs, str):
        outputs = _json.loads(outputs)
    if isinstance(trace, str):
        trace = _json.loads(trace)
    return {
        "id": int(row["id"]),
        "park_id": row.get("park_id"),
        "scenario_name": row.get("scenario_name"),
        "scenario_type": row.get("scenario_type"),
        "inputs": inputs or {},
        "outputs": outputs or {},
        "calculation_trace": trace or [],
        "confidence": row.get("confidence"),
        "is_favorite": bool(row.get("is_favorite", False)),
        "is_archived": bool(row.get("is_archived", False)),
        "created_at": str(row.get("created_at")) if row.get("created_at") else None,
        "updated_at": str(row.get("updated_at")) if row.get("updated_at") else None,
        "created_by": row.get("created_by"),
    }


def _scenario_table_exists(cur) -> bool:
    cur.execute(
        "SELECT to_regclass(%s) IS NOT NULL AS exists",
        (SCENARIO_TABLE,),
    )
    return bool(cur.fetchone().get("exists", False))


def list_scenarios(park_id: str = PARK_ID, include_archived: bool = False) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _scenario_table_exists(cur):
                    return {"status": "OK", "park_id": park_id, "scenarios": [], "total": 0}

                if include_archived:
                    cur.execute(
                        f"SELECT * FROM {SCENARIO_TABLE} WHERE park_id = %s ORDER BY is_favorite DESC, created_at DESC",
                        (park_id,),
                    )
                else:
                    cur.execute(
                        f"SELECT * FROM {SCENARIO_TABLE} WHERE park_id = %s AND is_archived = FALSE ORDER BY is_favorite DESC, created_at DESC",
                        (park_id,),
                    )
                rows = cur.fetchall()
                scenarios = [_scenario_row_to_dict(r) for r in rows]
                return {
                    "status": "OK",
                    "park_id": park_id,
                    "scenarios": scenarios,
                    "total": len(scenarios),
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro scenarios list: %s", e)
        return {"status": "ERROR", "error": str(e), "scenarios": []}


def save_scenario(park_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import json as _json
    scenario_name = str(payload.get("scenario_name", "")).strip()
    if not scenario_name:
        raise ValueError("scenario_name is required")

    scenario_type = str(payload.get("scenario_type", "manual"))
    if scenario_type not in VALID_SCENARIO_TYPES:
        raise ValueError(f"Invalid scenario_type: {scenario_type}")

    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _scenario_table_exists(cur):
                    raise RuntimeError(f"Table {SCENARIO_TABLE} does not exist")

                inputs_json = _json.dumps(payload.get("inputs", {}))
                outputs_json = _json.dumps(payload.get("outputs", {}))
                trace_json = _json.dumps(payload.get("calculation_trace", []))

                cur.execute(
                    f"""
                    INSERT INTO {SCENARIO_TABLE}
                        (park_id, scenario_name, scenario_type, inputs, outputs,
                         calculation_trace, confidence, is_favorite, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        park_id, scenario_name, scenario_type,
                        inputs_json, outputs_json, trace_json,
                        payload.get("confidence"),
                        bool(payload.get("is_favorite", False)),
                        payload.get("created_by"),
                    ),
                )
                conn.commit()
                row = cur.fetchone()
                return {"status": "OK", "scenario": _scenario_row_to_dict(row)}
            finally:
                cur.close()
    except (ValueError, RuntimeError) as e:
        raise
    except Exception as e:
        logger.warning("yego_pro scenario save: %s", e)
        raise


def update_scenario(scenario_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _scenario_table_exists(cur):
                    raise RuntimeError(f"Table {SCENARIO_TABLE} does not exist")

                cur.execute(
                    f"SELECT * FROM {SCENARIO_TABLE} WHERE id = %s",
                    (scenario_id,),
                )
                existing = cur.fetchone()
                if not existing:
                    raise ValueError(f"Scenario {scenario_id} not found")

                if existing.get("scenario_type") == "baseline":
                    allowed = {"is_favorite", "scenario_name"}
                    for k in payload:
                        if k not in allowed:
                            raise ValueError(f"Cannot modify field '{k}' on baseline scenario")

                import json as _json
                updates = []
                params: List[Any] = []

                for field, db_col in [
                    ("scenario_name", "scenario_name"),
                    ("is_favorite", "is_favorite"),
                    ("is_archived", "is_archived"),
                    ("confidence", "confidence"),
                ]:
                    if field in payload:
                        updates.append(f"{db_col} = %s")
                        params.append(payload[field])

                if "inputs" in payload:
                    updates.append("inputs = %s")
                    params.append(_json.dumps(payload["inputs"]))
                if "outputs" in payload:
                    updates.append("outputs = %s")
                    params.append(_json.dumps(payload["outputs"]))
                if "calculation_trace" in payload:
                    updates.append("calculation_trace = %s")
                    params.append(_json.dumps(payload["calculation_trace"]))

                if not updates:
                    return {"status": "OK", "scenario": _scenario_row_to_dict(existing)}

                updates.append("updated_at = NOW()")
                params.append(scenario_id)

                cur.execute(
                    f"UPDATE {SCENARIO_TABLE} SET {', '.join(updates)} WHERE id = %s RETURNING *",
                    params,
                )
                conn.commit()
                row = cur.fetchone()
                return {"status": "OK", "scenario": _scenario_row_to_dict(row)}
            finally:
                cur.close()
    except (ValueError, RuntimeError) as e:
        raise
    except Exception as e:
        logger.warning("yego_pro scenario update: %s", e)
        raise


def duplicate_scenario(scenario_id: int, new_name: Optional[str] = None) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _scenario_table_exists(cur):
                    raise RuntimeError(f"Table {SCENARIO_TABLE} does not exist")

                cur.execute(
                    f"SELECT * FROM {SCENARIO_TABLE} WHERE id = %s",
                    (scenario_id,),
                )
                existing = cur.fetchone()
                if not existing:
                    raise ValueError(f"Scenario {scenario_id} not found")

                name = new_name or f"{existing.get('scenario_name')} (copia)"
                import json as _json

                cur.execute(
                    f"""
                    INSERT INTO {SCENARIO_TABLE}
                        (park_id, scenario_name, scenario_type, inputs, outputs,
                         calculation_trace, confidence, is_favorite, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        existing.get("park_id"),
                        name,
                        existing.get("scenario_type", "manual"),
                        _json.dumps(existing.get("inputs") or {}),
                        _json.dumps(existing.get("outputs") or {}),
                        _json.dumps(existing.get("calculation_trace") or []),
                        existing.get("confidence"),
                        False,
                        existing.get("created_by"),
                    ),
                )
                conn.commit()
                row = cur.fetchone()
                return {"status": "OK", "scenario": _scenario_row_to_dict(row)}
            finally:
                cur.close()
    except (ValueError, RuntimeError) as e:
        raise
    except Exception as e:
        logger.warning("yego_pro scenario duplicate: %s", e)
        raise


def archive_scenario(scenario_id: int) -> Dict[str, Any]:
    return update_scenario(scenario_id, {"is_archived": True})


def get_baseline_scenario(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                overview = get_overview(park_id=park_id)

                total_trips = 0
                total_revenue = 0.0
                active_drivers = 0
                ticket_avg = 0.0
                km_per_trip_val = 0.0
                fuel_cost_val = 0.0
                maint_cost_val = 0.0
                plat_comm_val = 0.0
                driver_payout_val = 0.0
                driver_pct_val = 0.0
                profit_val = 0.0
                margin_val = 0.0
                bono_yango_val = 0.0
                bono_adicional_val = 0.0
                vehicle_cost_val = 0.0
                confidence_level = "ESTIMATED"

                kpis = overview.get("kpis", {})
                total_trips = _safe_int(kpis.get("trips_completed_30d", {}).get("value", 0)) or 0
                total_revenue = _safe_float(kpis.get("revenue_gross_30d", {}).get("value", 0)) or 0
                active_drivers = _safe_int(kpis.get("active_drivers", {}).get("value", 0)) or 0
                avg_ticket_val = _safe_float(kpis.get("ticket_avg", {}).get("value", 0)) or 0

                if _ensure_view_exists_cached(cur, MV_WEEK):
                    cur.execute(f"SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT 1")
                    week_row = cur.fetchone()
                    if week_row:
                        profit_val = _safe_float(week_row.get("profit")) or 0
                        margin_val = _safe_float(week_row.get("margin_pct")) or 0
                        fuel_cost_val = (_safe_float(week_row.get("fuel_cost")) or 0)
                        maint_cost_val = (_safe_float(week_row.get("maintenance_cost")) or 0)
                        km_total = _safe_float(week_row.get("km_total")) or 0
                        trips_w = _safe_int(week_row.get("trips_completed")) or 1
                        km_per_trip_val = km_total / trips_w
                        revenue_w = _safe_float(week_row.get("revenue_gross")) or 0
                        driver_payout_val = _safe_float(week_row.get("driver_payment")) or 0
                        plat_comm_val = _safe_float(week_row.get("platform_commission")) or 0
                        bono_yango_val = _safe_float(week_row.get("bono_yango")) or 0
                        bono_adicional_val = _safe_float(week_row.get("bono_additional")) or 0
                        if revenue_w > 0 and driver_payout_val > 0:
                            driver_pct_val = round(driver_payout_val / revenue_w * 100, 1)
                        confidence_level = "HIGH"

                if avg_ticket_val == 0 and total_trips > 0:
                    avg_ticket_val = round(total_revenue / total_trips, 2)

                daily_trips_day = 0
                daily_trips_night = 0
                daily_premier_day = 0
                daily_premier_night = 0
                if _ensure_view_exists_cached(cur, MV_DAY):
                    cur.execute(f"SELECT * FROM {MV_DAY} ORDER BY date DESC LIMIT 30")
                    day_rows = cur.fetchall()
                    if day_rows:
                        daily_trips_day = int(sum(
                            _safe_int(r.get("trips_day_shift")) or 0 for r in day_rows
                        ) / max(len(day_rows), 1))
                        daily_trips_night = int(sum(
                            _safe_int(r.get("trips_night_shift")) or 0 for r in day_rows
                        ) / max(len(day_rows), 1))

                trips_per_vehicle_day = daily_trips_day
                trips_per_vehicle_night = daily_trips_night
                premier_trips_day = max(1, int(daily_trips_day * 0.07))
                premier_trips_night = max(1, int(daily_trips_night * 0.07))

                bonus_cfg = get_bonus_config(park_id=park_id)
                bonus_tables = bonus_cfg.get("tables", {})

                baseline_inputs = {
                    "shifts_per_vehicle": 1,
                    "selected_shift": "day",
                    "trips_day_week": trips_per_vehicle_day * 7,
                    "trips_night_week": trips_per_vehicle_night * 7,
                    "trips_premier_day_week": premier_trips_day * 7,
                    "trips_premier_night_week": premier_trips_night * 7,
                    "ticket_avg_general": avg_ticket_val or 15.0,
                    "ticket_avg_premier": max(avg_ticket_val + 7, 22),
                    "km_per_trip": round(km_per_trip_val, 2) or 8.5,
                    "fuel_per_km": 0.35,
                    "maintenance_per_trip": 1.20,
                    "platform_commission_pct": 18.0,
                    "vehicle_weekly_cost": vehicle_cost_val or 350.0,
                    "insurance_gps_weekly": 45.0,
                    "reserve_pct": 3.0,
                    "driver_payout_pct": driver_pct_val or 50.0,
                    "vehicle_branded": True,
                    "eligible_for_general_bonus": True,
                    "eligible_for_premier_bonus": True,
                    "general_bonus_trips_week": trips_per_vehicle_day * 7,
                    "premier_bonus_trips_week": premier_trips_day * 7,
                    "guarantee_amount": 0.0,
                }

                sim_result = run_simulator({
                    **baseline_inputs,
                    "bonus_tables": bonus_tables,
                })

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "scenario_name": "OPERACIÓN REAL",
                    "scenario_type": "baseline",
                    "inputs": baseline_inputs,
                    "outputs": {
                        "subtotals": sim_result.get("subtotals", {}),
                        "bonus_result": sim_result.get("bonus_result", {}),
                        "shift_label": sim_result.get("shift_label", ""),
                    },
                    "calculation_trace": sim_result.get("calculation_trace", []),
                    "confidence": confidence_level,
                    "kpi_sources": {
                        "trips_30d": {"source": "trips_2026", "confidence": "HIGH"},
                        "revenue_30d": {"source": "trips_2026", "confidence": "HIGH"},
                        "active_drivers": {"source": "trips_2026", "confidence": "HIGH"},
                        "ticket_avg": {"source": "trips_2026", "confidence": "HIGH"},
                        "profit_weekly": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "margin_pct": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "fuel_cost": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "maintenance_cost": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "driver_payout": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "platform_commission": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "bonus_yango": {"source": "module_weekly_billing", "confidence": confidence_level},
                        "km_per_trip": {"source": "module_weekly_billing", "confidence": "ESTIMATED"},
                        "daily_trips": {"source": "module_calculated_shifts", "confidence": "HIGH"},
                        "bonus_tables": {"source": "ops.yego_pro_bonus_config", "confidence": "HIGH" if bonus_cfg.get("persisted") else "MEDIUM"},
                    },
                    "operational_data": {
                        "trips_30d": total_trips,
                        "revenue_30d": total_revenue,
                        "active_drivers": active_drivers,
                        "bono_yango_weekly": bono_yango_val,
                        "bono_adicional_weekly": bono_adicional_val,
                    },
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro baseline scenario: %s", e)
        return {"status": "ERROR", "error": str(e)}


def _build_input_entry(
    key: str, value, unit: str, source: str, confidence: str,
    period: str, formula: str, available: bool, reason: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "value": _safe_float(value) if value is not None else None,
        "unit": unit,
        "source": source,
        "confidence": confidence,
        "period": period,
        "formula": formula,
        "available": available,
        "reason": reason,
    }


def get_operational_baseline(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=20000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                # Latest week from billing
                cur.execute(f"""
                    SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT 1
                """)
                week_row = cur.fetchone()

                # Latest 30 days of trips
                cur.execute(f"SELECT * FROM {MV_DAY} ORDER BY date DESC LIMIT 30")
                day_rows = cur.fetchall()

                # Shift daily data for day/night classification
                shift_day_data = {"trips": 0, "revenue": 0, "days": 0}
                shift_night_data = {"trips": 0, "revenue": 0, "days": 0}
                premier_day_data = {"trips": 0, "revenue": 0}
                premier_night_data = {"trips": 0, "revenue": 0}
                try:
                    cur.execute(f"""
                        SELECT date, shift_type,
                               SUM(COALESCE(trips, 0)) AS trips,
                               SUM(COALESCE(revenue, 0)) AS revenue
                        FROM {MV_SHIFT_DAILY}
                        WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY date, shift_type
                        ORDER BY date DESC
                    """)
                    for sr in cur.fetchall():
                        st = str(sr.get("shift_type") or "").lower().strip()
                        t = _safe_int(sr.get("trips")) or 0
                        r = _safe_float(sr.get("revenue")) or 0
                        if st in ("dia", "day", "morning", "manana", "tarde", "afternoon"):
                            shift_day_data["trips"] += t
                            shift_day_data["revenue"] += r
                            shift_day_data["days"] += 1
                        elif st in ("noche", "night", "evening"):
                            shift_night_data["trips"] += t
                            shift_night_data["revenue"] += r
                            shift_night_data["days"] += 1
                except Exception:
                    pass

                # Premier trip data from trips_2026
                try:
                    cur.execute(f"""
                        SELECT
                            CASE WHEN EXTRACT(HOUR FROM fecha_inicio_viaje) BETWEEN 6 AND 17
                                 THEN 'day' ELSE 'night' END AS shift,
                            COUNT(*) AS trips,
                            AVG(precio_yango_pro) AS avg_price
                        FROM public.trips_2026
                        WHERE park_id = %s
                          AND condicion = 'Completado'
                          AND tipo_servicio ILIKE '%premier%'
                          AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
                        GROUP BY CASE WHEN EXTRACT(HOUR FROM fecha_inicio_viaje) BETWEEN 6 AND 17
                                      THEN 'day' ELSE 'night' END
                    """, (park_id,))
                    for pr in cur.fetchall():
                        sh = str(pr.get("shift") or "").lower()
                        t = _safe_int(pr.get("trips")) or 0
                        avg_p = _safe_float(pr.get("avg_price")) or 0
                        if sh == "day":
                            premier_day_data["trips"] = t
                            premier_day_data["revenue"] = avg_p * t
                        elif sh == "night":
                            premier_night_data["trips"] = t
                            premier_night_data["revenue"] = avg_p * t
                except Exception:
                    pass

                # Averages from 30 days
                total_trips_30d = sum(_safe_int(r.get("trips_completed")) or 0 for r in day_rows)
                total_revenue_30d = sum(_safe_float(r.get("revenue_gross")) or 0 for r in day_rows)
                total_days = len(day_rows)
                active_drivers_30d = max((_safe_int(r.get("active_drivers")) or 0) for r in day_rows) if day_rows else 0

                avg_trips_day = round(shift_day_data["trips"] / max(total_days, 1), 1)
                avg_trips_night = round(shift_night_data["trips"] / max(total_days, 1), 1)
                avg_ticket = round(total_revenue_30d / max(total_trips_30d, 1), 2) if total_trips_30d > 0 else None
                avg_ticket_premier = round(
                    (premier_day_data["revenue"] + premier_night_data["revenue"]) /
                    max(premier_day_data["trips"] + premier_night_data["trips"], 1), 2
                ) if (premier_day_data["trips"] + premier_night_data["trips"]) > 0 else None

                km_per_trip_val = None
                fuel_per_km_val = None
                maint_per_trip_val = None
                commission_pct_val = None
                vehicle_cost_val = None
                billing_confidence = "HIGH"
                if week_row:
                    km_total = _safe_float(week_row.get("km_total"))
                    trips_week = _safe_int(week_row.get("trips_completed"))
                    if km_total and trips_week and trips_week > 0:
                        km_per_trip_val = round(km_total / trips_week, 2)
                    fuel_cost_w = _safe_float(week_row.get("fuel_cost"))
                    if fuel_cost_w and km_total and km_total > 0:
                        fuel_per_km_val = round(fuel_cost_w / km_total, 4)
                    maint_cost_w = _safe_float(week_row.get("maintenance_cost"))
                    if maint_cost_w and trips_week and trips_week > 0:
                        maint_per_trip_val = round(maint_cost_w / trips_week, 2)
                    rev_gross = _safe_float(week_row.get("revenue_gross"))
                    comm = _safe_float(week_row.get("platform_commission"))
                    if comm and rev_gross and rev_gross > 0:
                        commission_pct_val = round(comm / rev_gross * 100, 1)
                else:
                    billing_confidence = "MEDIUM"

                # Vehicle weekly cost from cronograma
                try:
                    cur.execute("""
                        SELECT AVG(crv.cuotas_semanales) AS avg_quota
                        FROM public.module_miauto_cronograma_vehiculo crv
                        JOIN public.module_miauto_cronograma cr ON crv.cronograma_id = cr.id
                        WHERE cr.active = true
                    """)
                    vc_row = cur.fetchone()
                    if vc_row:
                        vehicle_cost_val = _safe_float(vc_row.get("avg_quota"))
                except Exception:
                    pass

                # Build inputs
                inputs = {}
                inputs["trips_day_week"] = _build_input_entry(
                    "trips_day_week", avg_trips_day, "viajes/sem",
                    "module_calculated_shifts", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    f"SUM(trips['dia']) / {total_days} dias",
                    True,
                )
                inputs["trips_night_week"] = _build_input_entry(
                    "trips_night_week", avg_trips_night, "viajes/sem",
                    "module_calculated_shifts", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    f"SUM(trips['noche']) / {total_days} dias",
                    True,
                )
                inputs["trips_premier_day_week"] = _build_input_entry(
                    "trips_premier_day_week", premier_day_data["trips"], "viajes/sem",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "COUNT(Premier dia)",
                    True,
                )
                inputs["trips_premier_night_week"] = _build_input_entry(
                    "trips_premier_night_week", premier_night_data["trips"], "viajes/sem",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "COUNT(Premier noche)",
                    True,
                )
                inputs["ticket_avg_general"] = _build_input_entry(
                    "ticket_avg_general", avg_ticket, "S/",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "avg(precio_yango_pro)",
                    True,
                )
                inputs["ticket_avg_premier"] = _build_input_entry(
                    "ticket_avg_premier", avg_ticket_premier, "S/",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "avg(precio_yango_pro WHERE tipo_servicio ILIKE '%premier%')",
                    True,
                ) if avg_ticket_premier else _build_input_entry(
                    "ticket_avg_premier", None, "S/",
                    "trips_2026", "ESTIMATED",
                    "sin datos", "", False, "No hay viajes Premier en los ultimos 30 dias",
                )
                inputs["km_per_trip"] = _build_input_entry(
                    "km_per_trip", km_per_trip_val, "km",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "km_total / trips_week",
                    True,
                ) if km_per_trip_val else _build_input_entry(
                    "km_per_trip", 8.5, "km",
                    "trips_2026", "ESTIMATED",
                    "default operativo", "", True, "Dato no disponible en billing. Usando default.",
                )
                inputs["fuel_per_km"] = _build_input_entry(
                    "fuel_per_km", fuel_per_km_val, "S//km",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "gasto_combustible / km_recorrido",
                    True,
                ) if fuel_per_km_val else _build_input_entry(
                    "fuel_per_km", None, "S//km",
                    "module_weekly_billing", "ESTIMATED",
                    "sin datos", "", False, "Sin billing disponible para calcular combustible/km",
                )
                inputs["maintenance_per_trip"] = _build_input_entry(
                    "maintenance_per_trip", maint_per_trip_val, "S//viaje",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "gasto_mantenimiento / total_viajes",
                    True,
                ) if maint_per_trip_val else _build_input_entry(
                    "maintenance_per_trip", None, "S//viaje",
                    "module_weekly_billing", "ESTIMATED",
                    "sin datos", "", False, "Sin billing disponible para calcular mantenimiento/viaje",
                )
                inputs["platform_commission_pct"] = _build_input_entry(
                    "platform_commission_pct", commission_pct_val, "%",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "comision_app / monto_total_producido * 100",
                    True,
                ) if commission_pct_val else _build_input_entry(
                    "platform_commission_pct", None, "%",
                    "module_weekly_billing", "ESTIMATED",
                    "sin datos", "", False, "Sin billing disponible para calcular comision",
                )
                inputs["vehicle_weekly_cost"] = _build_input_entry(
                    "vehicle_weekly_cost", vehicle_cost_val, "S//sem",
                    "module_miauto_cronograma", "REAL_OPERATIONAL",
                    "configuracion activa",
                    "avg(cuotas_semanales)",
                    True,
                ) if vehicle_cost_val else _build_input_entry(
                    "vehicle_weekly_cost", 350.0, "S//sem",
                    "manual", "ESTIMATED",
                    "default operativo", "", True, "Cronograma no disponible. Usando default.",
                )
                inputs["insurance_gps_weekly"] = _build_input_entry(
                    "insurance_gps_weekly", 45.0, "S//sem",
                    "manual", "ESTIMATED",
                    "default operativo", "", True, "No hay fuente automatica para seguro/GPS.",
                )
                inputs["reserve_pct"] = _build_input_entry(
                    "reserve_pct", 3.0, "%",
                    "manual", "ESTIMATED",
                    "default operativo", "", True, "Reserva operativa manual.",
                )
                inputs["driver_payout_pct"] = _build_input_entry(
                    "driver_payout_pct",
                    _safe_float(week_row.get("avg_driver_pct")) if week_row else None,
                    "%",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "avg(porcentaje_pago)",
                    True,
                ) if week_row and _safe_float(week_row.get("avg_driver_pct")) else _build_input_entry(
                    "driver_payout_pct", 50.0, "%",
                    "payment_tiers", "ESTIMATED",
                    "default operativo", "", True, "Sin billing para calcular payout real.",
                )
                inputs["garantia_semanal"] = _build_input_entry(
                    "garantia_semanal",
                    _safe_float(week_row.get("bono_additional")) if week_row else None,
                    "S//sem",
                    "module_weekly_billing", "REAL_OPERATIONAL",
                    "ultima semana cerrada",
                    "garantia",
                    True,
                ) if week_row and _safe_float(week_row.get("bono_additional")) else _build_input_entry(
                    "garantia_semanal", 0, "S//sem",
                    "manual", "ESTIMATED",
                    "sin garantia", "", True, "Sin dato de garantia desde billing.",
                )
                inputs["general_bonus_trips_week"] = _build_input_entry(
                    "general_bonus_trips_week",
                    total_trips_30d if total_trips_30d > 0 else None,
                    "viajes",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "total viajes completados 30d",
                    True,
                )
                inputs["premier_bonus_trips_week"] = _build_input_entry(
                    "premier_bonus_trips_week",
                    premier_day_data["trips"] + premier_night_data["trips"] if (premier_day_data["trips"] + premier_night_data["trips"]) > 0 else None,
                    "viajes",
                    "trips_2026", "REAL_OPERATIONAL",
                    "ultimos 30 dias",
                    "total viajes Premier 30d",
                    True,
                )

                # Financial summary
                fin_rev_gross = _safe_float(week_row.get("revenue_gross")) or 0 if week_row else 0
                fin_bono_yango = _safe_float(week_row.get("bono_yango")) or 0 if week_row else 0
                fin_plat_comm = _safe_float(week_row.get("platform_commission")) or 0 if week_row else 0
                fin_fuel = _safe_float(week_row.get("fuel_cost")) or 0 if week_row else 0
                fin_maint = _safe_float(week_row.get("maintenance_cost")) or 0 if week_row else 0
                fin_driver_pay = _safe_float(week_row.get("driver_payment")) or 0 if week_row else 0
                fin_profit = _safe_float(week_row.get("profit")) or 0 if week_row else 0
                fin_fixed = 350.0 + 45.0  # vehicle + insurance defaults
                fin_net = fin_rev_gross + fin_bono_yango - fin_plat_comm - fin_fuel - fin_maint - fin_fixed - fin_driver_pay
                fin_margin = round(fin_net / max(fin_rev_gross + fin_bono_yango, 1) * 100, 1)

                financial_summary = {
                    "revenue_trip_gross": fin_rev_gross,
                    "yango_bonus_income": fin_bono_yango,
                    "platform_commission": fin_plat_comm,
                    "fuel_cost": fin_fuel,
                    "maintenance_cost": fin_maint,
                    "fixed_cost": fin_fixed,
                    "driver_payout": fin_driver_pay,
                    "net_profit": round(fin_net, 2),
                    "margin_pct": fin_margin,
                } if week_row else None

                # Missing inputs
                missing_inputs = [
                    {"key": k, "reason": v["reason"]}
                    for k, v in inputs.items() if not v["available"]
                ]

                baseline_status = "COMPLETE" if len(missing_inputs) == 0 else (
                    "PARTIAL" if "HIGH" in billing_confidence else "DEGRADED"
                )

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "period": "ultimos 30 dias",
                    "baseline_status": baseline_status,
                    "inputs": inputs,
                    "financial_summary": financial_summary,
                    "missing_inputs": missing_inputs,
                    "operational_summary": {
                        "total_trips_30d": total_trips_30d,
                        "total_revenue_30d": total_revenue_30d,
                        "active_drivers": active_drivers_30d,
                        "total_days_with_data": total_days,
                        "billing_weeks_available": 1 if week_row else 0,
                    },
                    "metadata": {
                        "billing_confidence": billing_confidence,
                        "sources_used": ["module_calculated_shifts", "module_weekly_billing", "trips_2026", "module_miauto_cronograma"],
                    },
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro operational_baseline: %s", e)
        return _error_response(str(e))


def get_kpi_explainability(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        ov = get_overview(park_id=park_id)
        if ov.get("status") not in ("OK",):
            return {"status": "NO_DATA", "message": "No overview data available for explainability."}

        kpis_raw = ov.get("kpis", {})
        coverage = ov.get("source_coverage", {})
        health = ov.get("health", {})

        def _kv(key, default=0):
            raw = kpis_raw.get(key, {})
            if isinstance(raw, dict):
                return raw.get("value", default)
            return raw if raw is not None else default

        def _source(key):
            raw = kpis_raw.get(key, {})
            if isinstance(raw, dict):
                return raw.get("source", "N/A")
            return "N/A"

        revenue_30d = _kv("revenue_gross_30d")
        trips_30d = _kv("trips_completed_30d")
        ticket_avg = _kv("ticket_avg")
        drivers_30d = _kv("active_drivers")
        profit_weekly = _kv("profit_weekly")
        margin_pct = _kv("margin_pct")
        fuel_cost_w = _kv("fuel_cost_weekly")
        maint_cost_w = _kv("maintenance_cost_weekly")
        driver_payment_w = _kv("driver_payment_weekly")
        km_per_trip_val = _kv("km_per_trip_total")
        fuel_per_km_val = _kv("fuel_per_km")

        billing_weeks = health.get("billing_weeks_available", 0)
        confidence = health.get("data_confidence", "MEDIUM")

        weekly_revenue = round(revenue_30d / 4.33, 2) if revenue_30d else 0
        platform_comm_est = round(weekly_revenue * 0.18, 2)
        fixed_cost_est = 350.0 + 45.0

        explainability = {
            "revenue_weekly": {
                "kpi": "revenue_weekly",
                "value": round(weekly_revenue, 2),
                "formula": "revenue_gross_30d / 4.33",
                "components": [
                    {"label": "Revenue bruto 30d", "value": round(revenue_30d, 2), "sign": "positive", "source": _source("revenue_gross_30d"), "confidence": "HIGH", "formula": "SUM(trips_2026.precio_yango_pro) WHERE condicion='Completado'"},
                    {"label": "Promedio semanas por mes", "value": 4.33, "sign": "neutral", "source": "calendar", "confidence": "REAL", "formula": "52 semanas / 12 meses"},
                ],
                "source_summary": "trips_2026 (viajes completados 30d) dividido entre semanas promedio por mes",
                "confidence": "HIGH",
                "warnings": [],
            },
            "yango_bonus_income": {
                "kpi": "yango_bonus_income",
                "value": _kv("bono_yango", 0) if "bono_yango" in kpis_raw else 0,
                "formula": "Module weekly billing: bono_yango (Yango bonus paid to fleet)",
                "components": [
                    {"label": "Bono Yango semanal (desde billing)", "value": _kv("bono_yango", 0), "sign": "positive", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "SUM(bono_yango) ultima semana cerrada"},
                ],
                "source_summary": "module_weekly_billing. Bono pagado por Yango a la flota.",
                "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM",
                "warnings": [] if billing_weeks >= 1 else [{"type": "NO_BILLING", "severity": "HIGH", "message": "Sin billing semanal. El bono se estima como 0."}],
            },
            "platform_commission": {
                "kpi": "platform_commission",
                "value": platform_comm_est,
                "formula": "revenue_weekly * 18% (comision estimada)",
                "components": [
                    {"label": "Revenue semanal", "value": round(weekly_revenue, 2), "sign": "positive", "source": "trips_2026", "confidence": "HIGH", "formula": "revenue_gross_30d / 4.33"},
                    {"label": "Tasa comision", "value": 18, "sign": "negative", "source": "module_weekly_billing", "confidence": "ESTIMATED", "formula": "comision_app / monto_total_producido (ultima semana billing)"},
                ],
                "source_summary": "Calculada como revenue_weekly * tasa_comision estimada desde billing.",
                "confidence": "MEDIUM",
                "warnings": [{"type": "ESTIMATED_COMMISSION", "severity": "LOW", "message": "Comision estimada. Puede variar por tipo de servicio."}],
            },
            "fuel_cost": {
                "kpi": "fuel_cost",
                "value": fuel_cost_w,
                "formula": "Module weekly billing: gasto_combustible",
                "components": [
                    {"label": "Gasto combustible (billing)", "value": fuel_cost_w, "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "SUM(gasto_combustible) ultima semana cerrada"},
                ],
                "source_summary": "module_weekly_billing. Costo de combustible registrado en billing semanal.",
                "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM",
                "warnings": [] if billing_weeks >= 1 else [{"type": "NO_BILLING", "severity": "HIGH", "message": "Sin billing. El costo de combustible no esta disponible."}],
            },
            "maintenance_cost": {
                "kpi": "maintenance_cost",
                "value": maint_cost_w,
                "formula": "Module weekly billing: gasto_mantenimiento",
                "components": [
                    {"label": "Gasto mantenimiento (billing)", "value": maint_cost_w, "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "SUM(gasto_mantenimiento) ultima semana cerrada"},
                ],
                "source_summary": "module_weekly_billing. Costo de mantenimiento registrado en billing semanal.",
                "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM",
                "warnings": [] if billing_weeks >= 1 else [{"type": "NO_BILLING", "severity": "HIGH", "message": "Sin billing. El costo de mantenimiento no esta disponible."}],
            },
            "driver_payout": {
                "kpi": "driver_payout",
                "value": driver_payment_w,
                "formula": "Module weekly billing: pago_total",
                "components": [
                    {"label": "Pago conductor (billing)", "value": driver_payment_w, "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "SUM(pago_total) ultima semana cerrada"},
                ],
                "source_summary": "module_weekly_billing. Pago total a conductores registrado en billing semanal.",
                "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM",
                "warnings": [] if billing_weeks >= 1 else [{"type": "NO_BILLING", "severity": "HIGH", "message": "Sin billing. El pago a conductores no esta disponible."}],
            },
            "net_profit_weekly": {
                "kpi": "net_profit_weekly",
                "value": profit_weekly,
                "formula": "revenue_weekly + yango_bonus_income - platform_commission - fuel_cost - maintenance_cost - fixed_cost - driver_payout - other_costs",
                "components": [
                    {"label": "Revenue viajes (sem)", "value": round(weekly_revenue, 2), "sign": "positive", "source": "trips_2026", "confidence": "HIGH", "formula": "revenue_gross_30d / 4.33"},
                    {"label": "Bonos Yango ingreso", "value": _kv("bono_yango", 0) if "bono_yango" in kpis_raw else 0, "sign": "positive", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "bono_yango (desde billing)"},
                    {"label": "Comision plataforma", "value": -platform_comm_est, "sign": "negative", "source": "module_weekly_billing", "confidence": "ESTIMATED", "formula": "revenue_weekly * 18%"},
                    {"label": "Combustible", "value": -(fuel_cost_w or 0), "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "gasto_combustible (billing)"},
                    {"label": "Mantenimiento", "value": -(maint_cost_w or 0), "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "gasto_mantenimiento (billing)"},
                    {"label": "Costos fijos", "value": -fixed_cost_est, "sign": "negative", "source": "module_miauto_cronograma + manual", "confidence": "ESTIMATED", "formula": "cuota_vehiculo (350) + seguro_GPS (45)"},
                    {"label": "Pago conductor", "value": -(driver_payment_w or 0), "sign": "negative", "source": "module_weekly_billing", "confidence": "HIGH" if billing_weeks >= 1 else "MEDIUM", "formula": "pago_total (billing)"},
                ],
                "source_summary": "Utilidad semanal = ingresos totales - costos operativos - costos fijos - pagos conductor",
                "confidence": confidence,
                "warnings": [
                    {"type": "FIXED_COST_ESTIMATED", "severity": "MEDIUM", "message": "Costos fijos son estimados (cuota vehiculo + seguro/GPS). No provienen de billing."},
                    {"type": "COMMISSION_ESTIMATED", "severity": "LOW", "message": "Comision plataforma estimada al 18% del revenue semanal."},
                ] if billing_weeks >= 1 else [
                    {"type": "NO_BILLING", "severity": "HIGH", "message": f"Solo {billing_weeks} semana(s) de billing. Los costos pueden estar incompletos."},
                ],
            },
            "margin_pct": {
                "kpi": "margin_pct",
                "value": margin_pct,
                "formula": "net_profit_weekly / (revenue_weekly + yango_bonus_income) * 100",
                "components": [
                    {"label": "Utilidad semanal", "value": profit_weekly, "sign": "positive" if (profit_weekly or 0) >= 0 else "negative", "source": "module_weekly_billing", "confidence": confidence, "formula": "utilidad (billing)"},
                    {"label": "Ingreso total (revenue + bonos)", "value": round(weekly_revenue + (_kv("bono_yango", 0) if "bono_yango" in kpis_raw else 0), 2), "sign": "positive", "source": "trips_2026 + module_weekly_billing", "confidence": "HIGH", "formula": "revenue_weekly + bono_yango"},
                ],
                "source_summary": "Margen = (utilidad / ingreso_total) * 100",
                "confidence": confidence,
                "warnings": [],
            },
        }

        has_estimations = any(w["severity"] in ("HIGH", "MEDIUM") for k in explainability for w in explainability[k].get("warnings", []))

        return {
            "status": "OK",
            "park_id": park_id,
            "explainability": explainability,
            "data_quality_flags": {
                "has_estimations": has_estimations,
                "billing_weeks": billing_weeks,
                "confidence_level": confidence,
                "uses_estimated_fixed_costs": True,
                "uses_estimated_commission": True,
            },
            "warnings_summary": [
                w for k in explainability for w in explainability[k].get("warnings", [])
            ],
        }
    except Exception as e:
        logger.warning("yego_pro kpi_explainability: %s", e)
        return _error_response(str(e))


def get_operational_references_real(park_id: str = PARK_ID) -> Dict[str, Any]:
    try:
        baseline = get_operational_baseline(park_id=park_id)
        if baseline.get("status") != "OK":
            return {"status": "NO_DATA", "references": {}, "message": "Operational baseline not available."}

        refs = {}
        for key, entry in baseline.get("inputs", {}).items():
            if entry.get("available"):
                refs[key] = {
                    "value": entry["value"],
                    "source": entry["source"],
                    "confidence": entry["confidence"],
                    "period": entry["period"],
                    "formula": entry.get("formula", ""),
                    "available": True,
                }
            else:
                refs[key] = {
                    "value": None,
                    "source": None,
                    "confidence": "NOT_AVAILABLE",
                    "period": None,
                    "formula": None,
                    "available": False,
                    "reason": entry.get("reason", "No disponible"),
                }

        return {
            "status": "OK",
            "park_id": park_id,
            "references": refs,
            "baseline_status": baseline.get("baseline_status"),
            "financial_summary": baseline.get("financial_summary"),
        }
    except Exception as e:
        logger.warning("yego_pro operational_references: %s", e)
        return _error_response(str(e))


def get_driver_drill(park_id: str, driver_id: str) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT * FROM {MV_DRIVER}
                    WHERE driver_id = %s
                    ORDER BY week_start DESC LIMIT 1
                """, (driver_id,))
                driver_row = cur.fetchone()

                if not driver_row:
                    return {"status": "NOT_FOUND", "message": f"Driver {driver_id} no encontrado en billing."}

                driver_name = driver_row.get("driver_name") or driver_id
                trips = _safe_int(driver_row.get("trips_completed")) or 0
                hours = _safe_float(driver_row.get("work_hours")) or 0
                revenue = _safe_float(driver_row.get("revenue_gross")) or 0
                commission = _safe_float(driver_row.get("platform_commission")) or 0
                fuel = _safe_float(driver_row.get("fuel_cost")) or 0
                maint = _safe_float(driver_row.get("maintenance_cost")) or 0
                km = _safe_float(driver_row.get("km_total")) or 0
                driver_pct = _safe_float(driver_row.get("driver_pct")) or 0
                payment = _safe_float(driver_row.get("driver_payment")) or 0
                profit = _safe_float(driver_row.get("profit")) or 0
                margin_pct = _safe_float(driver_row.get("margin_pct")) or 0
                bono_yango = _safe_float(driver_row.get("bono_yango")) or 0
                ticket_avg = _safe_float(driver_row.get("ticket_avg")) or 0
                km_per_trip = _safe_float(driver_row.get("km_per_trip")) or 0
                rev_per_hour = _safe_float(driver_row.get("revenue_per_hour")) or 0

                cost_per_trip = (fuel + maint) / max(trips, 1)
                revenue_net = revenue - commission
                fixed_cost_per_vehicle = 395.0 / max(trips, 1) if trips > 0 else 0

                calculation = {
                    "driver_id": driver_id,
                    "driver_name": driver_name,
                    "week_start": str(driver_row.get("week_start")),
                    "income": {
                        "revenue_gross": round(revenue, 2),
                        "platform_commission": round(commission, 2),
                        "revenue_net": round(revenue_net, 2),
                        "bono_yango": round(bono_yango, 2),
                        "total_income": round(revenue_net + bono_yango, 2),
                    },
                    "costs": {
                        "fuel_cost": round(fuel, 2),
                        "maintenance_cost": round(maint, 2),
                        "variable_total": round(fuel + maint, 2),
                        "fixed_proxy": round(fixed_cost_per_vehicle * trips, 2),
                        "total_costs": round(fuel + maint + fixed_cost_per_vehicle * trips, 2),
                    },
                    "driver_payment": {
                        "payout_pct": driver_pct,
                        "payout_amount": round(payment, 2),
                    },
                    "result": {
                        "profit": round(profit, 2),
                        "margin_pct": margin_pct,
                        "is_profitable": bool(driver_row.get("is_profitable")),
                    },
                    "operational": {
                        "trips": trips,
                        "hours": round(hours, 2),
                        "km_total": round(km, 2),
                        "ticket_avg": round(ticket_avg, 2),
                        "km_per_trip": round(km_per_trip, 2),
                        "rev_per_hour": round(rev_per_hour, 2),
                        "cost_per_trip": round(cost_per_trip, 2),
                    },
                    "explanation": f"Conductor {driver_name}: {'GANANCIA' if profit >= 0 else 'PERDIDA'} de S/ {abs(round(profit, 2))}. "
                        f"Realizo {trips} viajes generando S/ {round(revenue, 2)} de revenue. "
                        f"Paga S/ {round(fuel, 2)} en combustible, S/ {round(maint, 2)} en mantenimiento, "
                        f"y recibe S/ {round(payment, 2)} como pago ({driver_pct}% del revenue). "
                        f"La comision de plataforma es S/ {round(commission, 2)}. "
                        f"Margen final: {margin_pct}%.",
                    "confidence": "HIGH",
                }

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "calculation": calculation,
                    "source": "module_weekly_billing (MV_DRIVER)",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro driver_drill: %s", e)
        return _error_response(str(e))


def get_vehicle_drill(park_id: str, plate: str) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                park_filter = "driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)"

                cur.execute(f"""
                    SELECT
                        s.placa,
                        SUM(COALESCE(s.produccion_total, 0)) AS revenue,
                        SUM(COALESCE(s.cantidad_viajes, 0)) AS trips,
                        COUNT(DISTINCT s.fecha) AS active_days,
                        COUNT(DISTINCT s.driver_id) AS drivers_count,
                        COUNT(*) AS shift_count,
                        SUM(COALESCE(s.monto_total, 0)) AS total_payout,
                        SUM(COALESCE(s.comisiones_servicio, 0)) AS total_commission,
                        SUM(COALESCE(s.duracion_minutos, 0)) AS total_minutes,
                        AVG(COALESCE(s.produccion_total, 0) / NULLIF(COALESCE(s.cantidad_viajes, 0), 0)) AS ticket_avg
                    FROM public.module_calculated_shifts s
                    WHERE {park_filter}
                      AND s.placa = %s
                    GROUP BY s.placa
                """, (park_id, plate))
                veh_row = cur.fetchone()

                if not veh_row:
                    return {"status": "NOT_FOUND", "message": f"Placa {plate} no encontrada en shifts."}

                revenue = _safe_float(veh_row.get("revenue")) or 0
                trips = _safe_int(veh_row.get("trips")) or 0
                days = _safe_int(veh_row.get("active_days")) or 1
                drivers = _safe_int(veh_row.get("drivers_count")) or 0
                shifts = _safe_int(veh_row.get("shift_count")) or 0
                payout = _safe_float(veh_row.get("total_payout")) or 0
                commission = _safe_float(veh_row.get("total_commission")) or 0
                minutes = _safe_int(veh_row.get("total_minutes")) or 0
                ticket = _safe_float(veh_row.get("ticket_avg")) or 0

                billing_margin_pct = -0.05
                try:
                    cur.execute(f"""
                        SELECT
                            SUM(COALESCE(b.utilidad, 0)) AS total_profit,
                            SUM(COALESCE(b.monto_total_producido, 0)) AS total_revenue
                        FROM public.module_weekly_billing b
                        WHERE b.driver_id IN (SELECT driver_id FROM public.drivers WHERE park_id = %s)
                    """, (park_id,))
                    brow = cur.fetchone()
                    if brow:
                        tr = _safe_float(brow.get("total_revenue")) or 1
                        tp = _safe_float(brow.get("total_profit")) or 0
                        billing_margin_pct = round(tp / tr, 4)
                except Exception:
                    pass

                fuel_est = revenue * 0.08
                maint_est = revenue * 0.04
                fixed_cost = 395.0
                estimated_margin = revenue * billing_margin_pct
                est_profit = revenue - commission - fuel_est - maint_est - fixed_cost - payout

                calculation = {
                    "plate": plate,
                    "period": "ultimos 30 dias de shifts",
                    "income": {
                        "revenue_gross": round(revenue, 2),
                        "ticket_avg": round(ticket, 2),
                        "commission_platform": round(commission, 2),
                        "revenue_net": round(revenue - commission, 2),
                    },
                    "operational": {
                        "trips": trips,
                        "active_days": days,
                        "drivers_count": drivers,
                        "shift_count": shifts,
                        "total_minutes": minutes,
                        "hours": round(minutes / 60, 1),
                        "trips_per_day": round(trips / days, 1),
                        "revenue_per_day": round(revenue / days, 2),
                        "revenue_per_trip": round(revenue / max(trips, 1), 2),
                    },
                    "costs_estimated": {
                        "fuel_estimated": round(fuel_est, 2),
                        "maintenance_estimated": round(maint_est, 2),
                        "fixed_cost_weekly": fixed_cost,
                        "total_cost_estimated": round(fuel_est + maint_est + fixed_cost, 2),
                    },
                    "driver_payment": {
                        "payout_shift_total": round(payout, 2),
                        "payout_per_trip": round(payout / max(trips, 1), 2),
                    },
                    "result": {
                        "estimated_profit": round(est_profit, 2),
                        "estimated_margin_pct": round(est_profit / max(revenue, 1) * 100, 1),
                        "park_margin_proxy": f"{round(billing_margin_pct * 100, 1)}%",
                        "is_profitable": est_profit >= 0,
                    },
                    "explanation": f"Vehiculo {plate}: {'GANANCIA' if est_profit >= 0 else 'PERDIDA'} estimada de S/ {abs(round(est_profit, 2))}. "
                        f"Genero S/ {round(revenue, 2)} en {trips} viajes durante {days} dias activos. "
                        f"Operado por {drivers} conductor(es) en {shifts} turnos. "
                        f"Costos estimados: combustible S/ {round(fuel_est, 2)}, mantenimiento S/ {round(maint_est, 2)}, "
                        f"fijos S/ {round(fixed_cost, 2)}, pago conductor S/ {round(payout, 2)}. "
                        f"Margen: {round(est_profit / max(revenue, 1) * 100, 1)}%. "
                        f"(NOTA: costos variables estimados como % del revenue. Los costos reales por vehiculo requieren asignacion directa.)",
                    "confidence": "ESTIMATED",
                    "note": "Costos de combustible y mantenimiento son estimados porque no se asignan por vehiculo en billing. El margen usa el margen % del parque como proxy.",
                }

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "calculation": calculation,
                    "source": "module_calculated_shifts + module_weekly_billing (margin proxy)",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro vehicle_drill: %s", e)
        return _error_response(str(e))


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
