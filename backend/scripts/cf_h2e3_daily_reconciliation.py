"""
CF-H2E.3 — Daily Multipark Reconciliation Engine

Compares CT serving facts vs Yango shadow data per park per day.
Writes results to ops.yango_shadow_reconciliation_history.

Usage:
    python -m scripts.cf_h2e3_daily_reconciliation --date 2026-06-11
    python -m scripts.cf_h2e3_daily_reconciliation --date-from 2026-06-01 --date-to 2026-06-11
    python -m scripts.cf_h2e3_daily_reconciliation --all-parks --yesterday

Rules:
- No source promotion
- No modification of production facts
- Read-only on CT serving facts
- Read-only on Yango raw data
- Writes only to shadow reconciliation history table
"""
from __future__ import annotations

import argparse
import sys
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings
import psycopg2
from psycopg2.extras import execute_values

PILOT_PARKS = [
    ("08e20910d81d42658d4334d3f6d10ac0", "Yego Lima", "Lima", "peru"),
    ("851e30755bba4d298e2e837f571b4ab8", "Yego Trujillo", "Trujillo", "peru"),
    ("56e4607dfc354e0a9cde4f0aa7973003", "Yego Arequipa", "Arequipa", "peru"),
    ("64085dd85e124e2c808806f70d527ea8", "Yego Pro", "Lima", "peru"),
    ("e3e07c00ed914f82a59c03283a178d6e", "Yego TukTuk", "Lima", "peru"),
]

KPI_CONFIG = [
    ("trips_completed", "orders", "SUM(trips_completed)", "SUM(COALESCE(orders_completed,0))"),
    ("active_drivers", "drivers", "COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips > 0)", "SUM(COALESCE(unique_drivers,0))"),
    ("revenue", "revenue", "SUM(COALESCE(revenue_yego_final,0))", "SUM(COALESCE(revenue_partner_fee_amount,0))"),
]


def _db():
    return psycopg2.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        database=settings.DB_NAME, user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        options="-c statement_timeout=120000",
    )


def ensure_table():
    conn = _db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ops.yango_shadow_reconciliation_history (
            id              SERIAL PRIMARY KEY,
            park_id         TEXT NOT NULL,
            park_name       TEXT,
            reconciliation_date DATE NOT NULL,
            kpi_name        TEXT NOT NULL,
            ct_value        NUMERIC,
            yango_value     NUMERIC,
            delta_abs       NUMERIC,
            delta_pct       NUMERIC,
            status          TEXT NOT NULL DEFAULT 'OK',
            computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            notes           TEXT,
            UNIQUE(park_id, reconciliation_date, kpi_name)
        );
    """)
    conn.commit()
    conn.close()


def reconcile_park(park_id: str, park_name: str, city: str, target_date: str) -> List[Dict]:
    results = []
    conn = _db()
    cur = conn.cursor()

    for kpi_name, yango_kpi, ct_sql, yango_sql in KPI_CONFIG:
        # CT value from driver_day_slice_fact (driver bridge)
        cur.execute(f"""
            SELECT COALESCE({ct_sql}, 0)::numeric
            FROM ops.driver_day_slice_fact
            WHERE park_id = %s AND activity_date::date = %s
        """, (park_id, target_date))
        ct_val = float(cur.fetchone()[0] or 0)

        # Yango value from MVs
        cur.execute(f"""
            SELECT COALESCE({yango_sql}, 0)::numeric
            FROM raw_yango.mv_orders_day
            WHERE park_id = %s AND order_date = %s
        """, (park_id, target_date))
        y_val = float(cur.fetchone()[0] or 0)

        delta_abs = round(ct_val - y_val, 2)
        delta_pct = round(abs(delta_abs) / max(abs(y_val), 1) * 100, 2) if y_val != 0 else None

        if ct_val == 0 and y_val == 0:
            status = "NOT_COMPARABLE"
        elif ct_val == 0:
            status = "CT_MISSING"
        elif y_val == 0:
            status = "YANGO_MISSING"
        elif delta_pct is not None and delta_pct <= 1:
            status = "MATCH"
        elif delta_pct is not None and delta_pct <= 5:
            status = "MINOR_DELTA"
        elif delta_pct is not None and delta_pct <= 10:
            status = "WARNING"
        else:
            status = "MAJOR_DELTA"

        results.append({
            "park_id": park_id,
            "park_name": park_name,
            "reconciliation_date": target_date,
            "kpi_name": kpi_name,
            "ct_value": ct_val,
            "yango_value": y_val,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "status": status,
        })

    conn.close()
    return results


def save_results(results: List[Dict]):
    if not results:
        return
    conn = _db()
    cur = conn.cursor()
    rows = [
        (r["park_id"], r["park_name"], r["reconciliation_date"], r["kpi_name"],
         r["ct_value"], r["yango_value"], r["delta_abs"], r["delta_pct"], r["status"])
        for r in results
    ]
    execute_values(cur, """
        INSERT INTO ops.yango_shadow_reconciliation_history
            (park_id, park_name, reconciliation_date, kpi_name, ct_value, yango_value, delta_abs, delta_pct, status)
        VALUES %s
        ON CONFLICT (park_id, reconciliation_date, kpi_name) DO UPDATE SET
            ct_value = EXCLUDED.ct_value, yango_value = EXCLUDED.yango_value,
            delta_abs = EXCLUDED.delta_abs, delta_pct = EXCLUDED.delta_pct,
            status = EXCLUDED.status, computed_at = now()
    """, rows, page_size=50)
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="CF-H2E.3 Daily Multipark Reconciliation")
    ap.add_argument("--date", type=str)
    ap.add_argument("--date-from", type=str)
    ap.add_argument("--date-to", type=str)
    ap.add_argument("--yesterday", action="store_true")
    ap.add_argument("--all-parks", action="store_true", default=True)
    ap.add_argument("--park-id", type=str)
    args = ap.parse_args()

    ensure_table()

    if args.yesterday:
        target_date = (date.today() - timedelta(days=1)).isoformat()
        dates = [target_date]
    elif args.date:
        dates = [args.date]
    elif args.date_from:
        f = date.fromisoformat(args.date_from)
        t = date.fromisoformat(args.date_to) if args.date_to else date.today()
        dates = [(f + timedelta(days=i)).isoformat() for i in range((t - f).days + 1)]
    else:
        dates = [(date.today() - timedelta(days=1)).isoformat()]

    parks = PILOT_PARKS
    if args.park_id:
        parks = [p for p in PILOT_PARKS if p[0] == args.park_id]

    total_results = 0
    match_count = 0
    warn_count = 0

    for pid, pname, city, country in parks:
        for d in dates:
            results = reconcile_park(pid, pname, city, d)
            save_results(results)
            total_results += len(results)
            for r in results:
                if r["status"] in ("MATCH", "MINOR_DELTA"):
                    match_count += 1
                elif r["status"] in ("WARNING", "MAJOR_DELTA"):
                    warn_count += 1
                print(f"  {pname:<18} {d} {r['kpi_name']:<20} CT={r['ct_value']:>10.1f} Y={r['yango_value']:>10.1f} "
                      f"delta={r['delta_pct']:>6.1f}% [{r['status']}]")

    print(f"\nReconciliation complete.")
    print(f"  Parks: {len(parks)}  Dates: {len(dates)}  Results: {total_results}")
    print(f"  MATCH: {match_count}  WARN: {warn_count}  OTHER: {total_results - match_count - warn_count}")
    print(f"  Table: ops.yango_shadow_reconciliation_history")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
