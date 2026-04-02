#!/usr/bin/env python3
"""
Validacion post-backfill: compara day_fact vs month_fact y revisa integridad.

cd backend && python -m scripts._validate_day_fact
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db_audit

QUERIES = {
    "1_day_fact_summary": """
        SELECT 
            count(*) AS total_rows,
            count(DISTINCT trip_date) AS distinct_dates,
            min(trip_date) AS min_date,
            max(trip_date) AS max_date,
            count(*) FILTER (WHERE revenue_yego_net IS NOT NULL) AS rev_ok,
            count(*) FILTER (WHERE revenue_yego_net IS NULL) AS rev_null,
            sum(trips_completed) AS total_trips
        FROM ops.real_business_slice_day_fact
    """,
    "2_week_fact_summary": """
        SELECT 
            count(*) AS total_rows,
            count(DISTINCT week_start) AS distinct_weeks,
            min(week_start) AS min_ws,
            max(week_start) AS max_ws,
            count(*) FILTER (WHERE revenue_yego_net IS NOT NULL) AS rev_ok,
            count(*) FILTER (WHERE revenue_yego_net IS NULL) AS rev_null,
            sum(trips_completed) AS total_trips
        FROM ops.real_business_slice_week_fact
    """,
    "3_day_vs_month_trips": """
        SELECT 
            'month_fact' AS source,
            month, country,
            sum(trips_completed) AS trips,
            sum(revenue_yego_net) AS revenue,
            count(*) AS rows
        FROM ops.real_business_slice_month_fact
        WHERE month >= '2026-01-01'
        GROUP BY month, country
        
        UNION ALL
        
        SELECT 
            'day_fact_agg',
            date_trunc('month', trip_date)::date,
            country,
            sum(trips_completed),
            sum(revenue_yego_net),
            count(*)
        FROM ops.real_business_slice_day_fact
        WHERE trip_date >= '2026-01-01'
        GROUP BY date_trunc('month', trip_date), country
        
        ORDER BY 2 DESC, 1, 3
    """,
    "4_day_fact_by_month_revenue": """
        SELECT 
            date_trunc('month', trip_date)::date AS month,
            count(*) AS rows,
            sum(trips_completed) AS trips,
            count(DISTINCT trip_date) AS days,
            count(*) FILTER (WHERE revenue_yego_net IS NOT NULL) AS rev_ok,
            count(*) FILTER (WHERE revenue_yego_net IS NULL) AS rev_null,
            round(sum(revenue_yego_net)::numeric, 2) AS total_rev
        FROM ops.real_business_slice_day_fact
        GROUP BY date_trunc('month', trip_date)
        ORDER BY month DESC
    """,
    "5_week_fact_by_month": """
        SELECT 
            date_trunc('month', week_start)::date AS month,
            count(*) AS rows,
            sum(trips_completed) AS trips,
            count(DISTINCT week_start) AS weeks,
            count(*) FILTER (WHERE revenue_yego_net IS NOT NULL) AS rev_ok,
            round(sum(revenue_yego_net)::numeric, 2) AS total_rev
        FROM ops.real_business_slice_week_fact
        GROUP BY date_trunc('month', week_start)
        ORDER BY month DESC
    """,
    "6_day_fact_sample_with_rev": """
        SELECT trip_date, country, business_slice_name,
               trips_completed, active_drivers, avg_ticket,
               round(revenue_yego_net::numeric, 2) AS revenue,
               round(commission_pct::numeric, 4) AS commission,
               round(cancel_rate_pct::numeric, 4) AS cancel_rate
        FROM ops.real_business_slice_day_fact
        WHERE revenue_yego_net IS NOT NULL
        ORDER BY trip_date DESC, country, business_slice_name
        LIMIT 20
    """,
    "7_comparison_all_sources": """
        SELECT source, rows, min_date, max_date
        FROM (
            SELECT 'month_fact' AS source, count(*) AS rows,
                   min(month) AS min_date, max(month) AS max_date
            FROM ops.real_business_slice_month_fact
            UNION ALL
            SELECT 'day_fact', count(*), min(trip_date), max(trip_date)
            FROM ops.real_business_slice_day_fact
            UNION ALL
            SELECT 'week_fact', count(*), min(week_start), max(week_start)
            FROM ops.real_business_slice_week_fact
        ) t
        ORDER BY source
    """,
}


def main():
    with get_db_audit(timeout_ms=120_000) as conn:
        cur = conn.cursor()
        for label, sql in QUERIES.items():
            print(f"\n{'='*60}")
            print(f"  {label}")
            print(f"{'='*60}")
            try:
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                print("  " + " | ".join(cols))
                print("  " + "-" * min(len(" | ".join(cols)) + 4, 100))
                for r in rows:
                    print("  " + " | ".join(str(x) for x in r))
                if not rows:
                    print("  (sin filas)")
            except Exception as e:
                print(f"  ERROR: {e}")
                conn.rollback()
        cur.close()


if __name__ == "__main__":
    main()
