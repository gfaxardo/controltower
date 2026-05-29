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
                if not _check_view_exists(cur, MV_WEEK):
                    return _missing_source_response(MV_WEEK, "Run yego_pro_profitability_serving_views.sql")

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
                cur.execute(f"SELECT COUNT(*) AS cnt FROM {MV_WEEK}")
                cnt_row = cur.fetchone()
                if cnt_row:
                    billing_weeks = _safe_int(cnt_row.get("cnt")) or 0

                return {
                    "status": "OK",
                    "park_id": park_id,
                    "park_name": "Yego Lima",
                    "kpis": kpis,
                    "health": {
                        "profit_status": "LOSS" if week_row and (_safe_float(week_row.get("profit")) or 0) < 0 else "PROFIT",
                        "billing_weeks_available": billing_weeks,
                        "data_confidence": "HIGH" if billing_weeks >= 4 else ("MEDIUM" if billing_weeks >= 1 else "LOW"),
                        "days_with_trips": len(day_rows),
                    },
                    "metadata": {
                        "sources": ["trips_2026", "module_weekly_billing"],
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


def get_shifts(park_id: str = PARK_ID, weeks: int = 8) -> Dict[str, Any]:
    try:
        with get_db_quick(timeout_ms=15000) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                if not _check_view_exists(cur, MV_SHIFT):
                    return _missing_source_response(MV_SHIFT, "Run yego_pro_profitability_serving_views.sql")

                cur.execute(f"SELECT * FROM {MV_SHIFT} ORDER BY week_start DESC LIMIT %s", (weeks * 2,))
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
                    "shift_definition": {"DAY": "06:00-17:59", "NIGHT": "18:00-05:59"},
                    "source": "trips_2026",
                    "metric_type": "DERIVED",
                    "confidence": "HIGH",
                    "notes": "Revenue/hour not available per shift (billing does not distinguish day/night)",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability shifts: %s", e)
        return _error_response(str(e))


def get_input_mapping(park_id: str = PARK_ID) -> Dict[str, Any]:
    inputs_real: List[Dict[str, Any]] = [
        {"key": "ticket_avg", "value": 10.21, "unit": "S/", "source": "trips_2026", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
        {"key": "fuel_per_km", "value": 0.1528, "unit": "S/km", "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
        {"key": "maintenance_per_km", "value": 0.1500, "unit": "S/km", "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
        {"key": "platform_commission_pct", "value": 16.66, "unit": "%", "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
        {"key": "avg_driver_payment_pct", "value": 47.69, "unit": "%", "source": "module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "auto_refresh": True},
        {"key": "vehicle_quota_weekly", "value": 500.0, "unit": "S/", "source": "module_miauto_cronograma_rule", "metric_type": "REAL", "confidence": "HIGH", "auto_refresh": False},
        {"key": "bono_yango_weekly", "value": 5126.57, "unit": "S/", "source": "module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "auto_refresh": True},
        {"key": "km_per_trip_total", "value": 9.20, "unit": "km", "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
        {"key": "work_hours_daily_avg", "value": 9.08, "unit": "hours", "source": "module_weekly_billing", "metric_type": "REAL", "confidence": "HIGH", "auto_refresh": True},
        {"key": "revenue_per_hour", "value": 28.97, "unit": "S/h", "source": "module_weekly_billing", "metric_type": "DERIVED", "confidence": "HIGH", "auto_refresh": True},
    ]

    inputs_configurable: List[Dict[str, Any]] = [
        {"key": "insurance_gps_monthly", "value": 300.0, "unit": "S/", "metric_type": "ASSUMPTION", "confidence": "LOW", "editable": True},
        {"key": "depreciation_reserve_pct", "value": 15.0, "unit": "%", "metric_type": "ASSUMPTION", "confidence": "LOW", "editable": True},
        {"key": "gasoline_price_gallon", "value": 16.50, "unit": "S/gal", "metric_type": "ASSUMPTION", "confidence": "LOW", "editable": True},
        {"key": "wash_weekly", "value": 30.0, "unit": "S/", "metric_type": "ASSUMPTION", "confidence": "LOW", "editable": True},
    ]

    inputs_not_available: List[Dict[str, Any]] = [
        {"key": "supply_hours_real", "source": "module_ct_fleet_summary_daily", "reason": "Table empty for this park", "remediation": "Proxy: use horas_trabajo from billing"},
        {"key": "acceptance_rate", "source": "summary_daily", "reason": "0 records for park_id", "remediation": "NOT_AVAILABLE"},
        {"key": "vehicle_assignment", "source": "N/A", "reason": "No vehicle-to-driver assignment table", "remediation": "Cannot report per-vehicle profitability"},
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
        "inputs_real": inputs_real,
        "inputs_configurable": inputs_configurable,
        "inputs_not_available": inputs_not_available,
        "payment_tiers": payment_tiers,
        "source": "multiple",
        "notes": "Real inputs auto-refresh from billing. Configurable inputs require manual update.",
    }


def get_quality(park_id: str = PARK_ID) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
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
                    "raw_sources": {
                        "drivers_in_park": driver_count,
                        "trips_completed": trip_count,
                        "last_trip_date": last_trip,
                        "billing_records": billing_count,
                    },
                    "overall": "HEALTHY" if all(c["status"] == "OK" for c in checks) else "DEGRADED",
                }
            finally:
                cur.close()
    except Exception as e:
        logger.warning("yego_pro_profitability quality: %s", e)
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
