"""
Yego Pro Profitability — Overview Performance Audit (read-only)
Mide tiempos internos de get_overview() sin modificar lógica.
"""
import time
import json
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.yego_pro_profitability_service import (
    get_overview,
    PARK_ID,
    MV_WEEK,
    MV_DAY,
    MV_SOURCE_COVERAGE,
    _check_view_exists,
    _get_coverage,
    _safe_int,
    _safe_float,
    _metric,
)
from app.db.connection import get_db_quick
from psycopg2.extras import RealDictCursor


def instrumented_get_overview(park_id=PARK_ID):
    """Instrumented version that measures each step."""
    timings = {}
    t0 = time.perf_counter()

    t_conn_start = time.perf_counter()
    conn = get_db_quick(timeout_ms=15000)
    t_conn = (time.perf_counter() - t_conn_start) * 1000
    timings["db_connection_ms"] = round(t_conn, 1)

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # Step 1: _check_view_exists(MV_WEEK)
            t1 = time.perf_counter()
            mv_week_exists = _check_view_exists(cur, MV_WEEK)
            timings["check_view_MV_WEEK_ms"] = round((time.perf_counter() - t1) * 1000, 1)

            if not mv_week_exists:
                result = {
                    "status": "MISSING_SOURCE",
                    "source": MV_WEEK,
                    "message": f"Materialized view {MV_WEEK} not found.",
                }
                timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                return result, timings

            # Step 2: SELECT * FROM MV_WEEK LIMIT 1
            t2 = time.perf_counter()
            cur.execute(f"SELECT * FROM {MV_WEEK} ORDER BY week_start DESC LIMIT 1")
            week_row = cur.fetchone()
            timings["query_MV_WEEK_ms"] = round((time.perf_counter() - t2) * 1000, 1)

            # Step 3: SELECT * FROM MV_DAY LIMIT 30
            t3 = time.perf_counter()
            cur.execute(f"SELECT * FROM {MV_DAY} ORDER BY date DESC LIMIT 30")
            day_rows = cur.fetchall()
            timings["query_MV_DAY_ms"] = round((time.perf_counter() - t3) * 1000, 1)

            if not week_row and not day_rows:
                result = {"status": "NO_DATA", "park_id": park_id, "message": "No billing or trip data found"}
                timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                return result, timings

            # Step 4: SELECT COUNT(*) FROM MV_WEEK
            t4 = time.perf_counter()
            cur.execute(f"SELECT COUNT(*) AS cnt FROM {MV_WEEK}")
            cnt_row = cur.fetchone()
            billing_weeks = _safe_int(cnt_row.get("cnt")) or 0 if cnt_row else 0
            timings["query_COUNT_weeks_ms"] = round((time.perf_counter() - t4) * 1000, 1)

            # Step 5-6: _get_coverage()
            t5 = time.perf_counter()
            coverage = _get_coverage(cur)
            timings["get_coverage_total_ms"] = round((time.perf_counter() - t5) * 1000, 1)

            # Build result (same logic as original)
            trips_30d = sum(_safe_int(r.get("trips_completed")) or 0 for r in day_rows)
            cancelled_30d = sum(_safe_int(r.get("trips_cancelled")) or 0 for r in day_rows)
            revenue_30d = sum(_safe_float(r.get("revenue_gross")) or 0 for r in day_rows)
            drivers_30d = max((_safe_int(r.get("active_drivers")) or 0) for r in day_rows) if day_rows else 0

            kpis = {
                "trips_completed_30d": _metric(trips_30d, "trips_2026", "REAL", "HIGH"),
                "trips_cancelled_30d": _metric(cancelled_30d, "trips_2026", "REAL", "HIGH"),
                "cancellation_rate": _metric(round(cancelled_30d / max(trips_30d + cancelled_30d, 1), 4), "trips_2026", "DERIVED", "HIGH"),
                "revenue_gross_30d": _metric(revenue_30d, "trips_2026", "REAL", "HIGH"),
                "ticket_avg": _metric(round(revenue_30d / max(trips_30d, 1), 2), "trips_2026", "DERIVED", "HIGH"),
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

            result = {
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

            timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            return result, timings
        finally:
            cur.close()
    except Exception as e:
        timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        timings["error"] = str(e)[:100]
        return {"status": "ERROR", "message": str(e)[:100]}, timings


def main():
    runs = 5
    results = []
    print("=" * 70)
    print("YEGO PRO PROFITABILITY — OVERVIEW PERF AUDIT (BEFORE)")
    print("=" * 70)

    for i in range(runs):
        label = "COLD" if i == 0 else f"WARM #{i}"
        print(f"\n--- Run {i+1}/{runs} ({label}) ---")
        result, timings = instrumented_get_overview()
        timings["run"] = i + 1
        timings["label"] = label
        timings["status"] = result.get("status", "ERROR")
        timings["payload_bytes"] = len(json.dumps(result, default=str))
        results.append(timings)

        for k, v in timings.items():
            if k == "total_ms":
                print(f"  TOTAL: {v}ms {'<<<' if v > 5000 else ''}")
            elif isinstance(v, (int, float)):
                pct = round(v / max(timings["total_ms"], 1) * 100, 1)
                print(f"  {k}: {v}ms ({pct}%)")

    # Save CSV
    csv_path = Path("C:/cursor/controltower/controltower/reports/yego_pro_overview_perf_before.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["run", "label", "status", "total_ms", "db_connection_ms",
                  "check_view_MV_WEEK_ms", "query_MV_WEEK_ms", "query_MV_DAY_ms",
                  "query_COUNT_weeks_ms", "get_coverage_total_ms", "payload_bytes"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            writer.writerow(r)

    avg = sum(r["total_ms"] for r in results) / len(results)
    warm_avg = sum(r["total_ms"] for r in results[1:]) / max(len(results) - 1, 1)
    print(f"\n=== SUMMARY ===")
    print(f"  Cold: {results[0]['total_ms']}ms")
    print(f"  Warm avg (runs 2-{runs}): {warm_avg:.0f}ms")
    print(f"  Overall avg: {avg:.0f}ms")
    print(f"  Saved to: {csv_path}")


if __name__ == "__main__":
    main()
