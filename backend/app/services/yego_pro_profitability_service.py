"""
Yego Pro Profitability Service — Phase 1 Foundation
Control Foundation serving layer (read-only).

Park: 64085dd85e124e2c808806f70d527ea8 (Lima)
Sources: module_weekly_billing, trips_2026, module_miauto_cronograma
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
