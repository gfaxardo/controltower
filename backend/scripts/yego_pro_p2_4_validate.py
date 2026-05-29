"""
Yego Pro Profitability P2.4 -- Validation Script
Refreshes new serving MVs and runs validation checks.
READ-ONLY after initial MV creation.
"""
import sys
import os
import csv
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import init_db_pool, get_db

PARK_ID = "64085dd85e124e2c808806f70d527ea8"
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

NEW_MVS = [
    "ops.mv_yego_pro_shift_daily",
    "ops.mv_yego_pro_driver_close_week",
    "ops.mv_yego_pro_weekly_financial_truth",
    "ops.mv_yego_pro_source_coverage",
]

def write_csv(filename, rows):
    path = os.path.join(REPORTS_DIR, filename)
    if not rows:
        print(f"  [SKIP] {filename} -- no rows")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK] {filename} -- {len(rows)} rows")

def run():
    print("=" * 70)
    print("YEGO PRO PROFITABILITY P2.4 -- DATA HARDENING VALIDATION")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    import psycopg2
    from app.settings import settings

    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        print("\n--- VALIDATION: Row counts and date ranges ---")
        validation_rows = []

        mvs_to_check = [
            "ops.mv_yego_pro_profitability_week",
            "ops.mv_yego_pro_profitability_day",
            "ops.mv_yego_pro_driver_profitability_week",
            "ops.mv_yego_pro_shift_profitability_week",
            "ops.mv_yego_pro_shift_daily",
            "ops.mv_yego_pro_driver_close_week",
            "ops.mv_yego_pro_weekly_financial_truth",
            "ops.mv_yego_pro_source_coverage",
        ]

        for mv in mvs_to_check:
            cur.execute("SELECT to_regclass(%s) IS NOT NULL", (mv,))
            exists = cur.fetchone()[0]

            if not exists:
                validation_rows.append({
                    "mv": mv, "exists": False, "row_count": 0,
                    "min_date": None, "max_date": None,
                    "status": "MISSING", "notes": "MV does not exist",
                })
                continue

            cur.execute(f"SELECT COUNT(*) FROM {mv}")
            row_count = cur.fetchone()[0]

            min_date = max_date = None
            for date_col in ["date", "week_start", "fecha"]:
                try:
                    cur.execute(f"SELECT MIN({date_col})::text, MAX({date_col})::text FROM {mv}")
                    mn, mx = cur.fetchone()
                    if mn: min_date = mn
                    if mx: max_date = mx
                    break
                except Exception:
                    continue

            cur.execute(f"""
                SELECT COUNT(*) AS null_count
                FROM {mv}
                WHERE park_id IS NULL
            """)
            null_park = cur.fetchone()[0]

            validation_rows.append({
                "mv": mv,
                "exists": True,
                "row_count": row_count,
                "min_date": min_date,
                "max_date": max_date,
                "null_park_id": null_park,
                "status": "OK" if row_count > 0 and null_park == 0 else (
                    "EMPTY" if row_count == 0 else "NULL_PARK"),
                "notes": "",
            })

        for v in validation_rows:
            print(f"  {v['mv']}: {v['row_count']} rows, {v['min_date']} -> {v['max_date']}, status={v['status']}")

        write_csv("yego_pro_p2_4_validation.csv", validation_rows)

        print("\n--- SOURCE COVERAGE SUMMARY ---")
        coverage = {}
        try:
            cur.execute(f"SELECT * FROM ops.mv_yego_pro_source_coverage LIMIT 1")
            row = cur.fetchone()
            if row:
                cols = [d[0] for d in cur.description]
                coverage = dict(zip(cols, row))
                for k in ["registered_drivers", "billing_weeks", "shift_days", "shift_rows",
                          "close_rows", "close_days", "close_drivers", "trip_rows", "trip_days",
                          "plate_coverage_pct", "close_driver_coverage_pct",
                          "financial_history_status", "operational_history_status"]:
                    print(f"  {k}: {coverage.get(k)}")
        except Exception as e:
            print(f"  [ERROR] Could not read source_coverage: {e}")

        coverage_rows = []
        if coverage:
            coverage_rows = [{
                "metric": k, "value": coverage.get(k),
            } for k in sorted(coverage.keys())]
        write_csv("yego_pro_p2_4_coverage.csv", coverage_rows)

        print("\n--- METRIC SOURCE OF TRUTH (P2.4 updated) ---")
        sot_rows = [
            {"layer": "PRODUCTION", "metric": "trips", "source": "module_calculated_shifts", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "PRODUCTION", "metric": "revenue_daily", "source": "module_calculated_shifts", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "PRODUCTION", "metric": "shift_type", "source": "module_calculated_shifts.tipo_turno", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "PRODUCTION", "metric": "vehicle_plate", "source": "module_calculated_shifts.placa", "role": "SOURCE_OF_TRUTH", "confidence": "MEDIUM"},
            {"layer": "PRODUCTION", "metric": "shift_duration", "source": "module_calculated_shifts.duracion_minutos", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "SETTLEMENT", "metric": "driver_payout_daily", "source": "module_driver_closes", "role": "SOURCE_OF_TRUTH", "confidence": "MEDIUM"},
            {"layer": "SETTLEMENT", "metric": "fuel_cost_daily", "source": "module_driver_closes", "role": "SOURCE_OF_TRUTH", "confidence": "MEDIUM"},
            {"layer": "SETTLEMENT", "metric": "km_validated", "source": "module_driver_closes.diferencia_odometro", "role": "SECONDARY_CHECK", "confidence": "LOW"},
            {"layer": "SETTLEMENT", "metric": "daily_settlement", "source": "module_driver_closes", "role": "SOURCE_OF_TRUTH", "confidence": "MEDIUM"},
            {"layer": "FINANCIAL", "metric": "revenue_weekly", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "platform_commission", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "fuel_cost_weekly", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "maintenance_weekly", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "driver_payout_weekly", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "profit_weekly", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
            {"layer": "FINANCIAL", "metric": "margin_pct", "source": "module_weekly_billing", "role": "SOURCE_OF_TRUTH", "confidence": "HIGH"},
        ]
        write_csv("yego_pro_p2_4_metric_sources.csv", sot_rows)

        for s in sot_rows:
            print(f"  [{s['layer']}] {s['metric']}: {s['source']} [{s['confidence']}]")

        cur.close()
    except Exception as e:
        print(f"  [ERROR] {e}")
    finally:
        conn.close()

    print("\n" + "=" * 70)
    print("VALIDATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    run()
