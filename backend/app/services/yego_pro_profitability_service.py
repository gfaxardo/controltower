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
