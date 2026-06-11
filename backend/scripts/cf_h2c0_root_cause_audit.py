#!/usr/bin/env python3
"""
CF-H2C.0 — Yango Coverage Root Cause Analysis

Runs diagnostic queries to determine why Yango API shows fewer orders
than trips_2026 for 2026-06-10.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, timezone
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

PET = timezone(timedelta(hours=-5))
TARGET_DATE = "2026-06-10"

def sep(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ======================================================================
    # 1. PARKS AUDIT
    # ======================================================================
    sep("1. YANGO CREDENTIAL REGISTRY")
    cur.execute("""
        SELECT credential_id, park_id, fleet_name, country, city,
               env_var_name, is_active, notes
        FROM raw_yango.api_park_credentials_registry
        ORDER BY park_id
    """)
    rows = cur.fetchall()
    print(f"  Total parks in registry: {len(rows)}")
    for r in rows:
        print(f"  [{('ACTIVE' if r['is_active'] else 'INACTIVE'):8s}] "
              f"park={r['park_id']} fleet={r['fleet_name']} "
              f"city={r['city']} country={r['country']} env_prefix={r['env_var_name']}")

    sep("2. DISTINCT PARKS IN trips_2026 ON 2026-06-10")
    cur.execute("""
        SELECT park_id,
               COUNT(*) AS trips,
               COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed,
               COUNT(*) FILTER (WHERE condicion = 'Cancelado') AS cancelled,
               MIN(fecha_finalizacion::timestamp) AS min_ts,
               MAX(fecha_finalizacion::timestamp) AS max_ts
        FROM public.trips_2026
        WHERE fecha_finalizacion::date = %(d)s
        GROUP BY park_id
        ORDER BY trips DESC
    """, {"d": TARGET_DATE})
    rows = cur.fetchall()
    print(f"  Distinct parks with trips: {len(rows)}")
    total_ct = 0
    total_ct_completed = 0
    for r in rows:
        print(f"  park={r['park_id']} trips={r['trips']:>6d} completed={r['completed']:>6d} "
              f"cancelled={r['cancelled']:>5d} "
              f"range=[{str(r['min_ts'])[:19]} -> {str(r['max_ts'])[:19]}]")
        total_ct += r['trips']
        total_ct_completed += r['completed']
    print(f"  TOTAL: {total_ct} trips ({total_ct_completed} completed, {total_ct - total_ct_completed} cancelled)")

    # ======================================================================
    # 2. CT TRIPS BY HOUR AND STATUS
    # ======================================================================
    sep("3. CT trips_2026 BY HOUR (Lima) FOR 2026-06-10")
    cur.execute("""
        SELECT EXTRACT(HOUR FROM fecha_finalizacion AT TIME ZONE 'America/Lima')::int AS hour,
               COUNT(*) AS trips,
               COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed,
               COUNT(*) FILTER (WHERE condicion = 'Cancelado') AS cancelled
        FROM public.trips_2026
        WHERE fecha_finalizacion::date = %(d)s
        GROUP BY 1
        ORDER BY 1
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        bar = '#' * (r['trips'] // 100)
        print(f"  H{r['hour']:02d}: {r['trips']:>5d} trips ({r['completed']:>5d} completed, {r['cancelled']:>4d} cancelled) {bar}")

    # ======================================================================
    # 3. CT TRIPS BY STATUS
    # ======================================================================
    sep("4. CT trips_2026 BY STATUS FOR 2026-06-10")
    cur.execute("""
        SELECT condicion, COUNT(*) AS trips
        FROM public.trips_2026
        WHERE fecha_finalizacion::date = %(d)s
        GROUP BY condicion
        ORDER BY trips DESC
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        print(f"  {r['condicion']:30s}: {r['trips']:>6d}")

    # ======================================================================
    # 4. YANGO ORDERS BY PARK
    # ======================================================================
    sep("5. YANGO orders_raw ON 2026-06-10 (by ended_at UTC)")
    cur.execute("""
        SELECT park_id,
               COUNT(*) AS orders,
               COUNT(*) FILTER (WHERE order_status = 'complete') AS completed,
               COUNT(*) FILTER (WHERE order_status = 'cancelled') AS cancelled,
               MIN(order_ended_at) AS min_ended,
               MAX(order_ended_at) AS max_ended
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date = %(d)s
        GROUP BY park_id
        ORDER BY orders DESC
    """, {"d": TARGET_DATE})
    rows = cur.fetchall()
    total_ya = 0
    total_ya_completed = 0
    print(f"  Distinct parks with orders: {len(rows)}")
    for r in rows:
        print(f"  park={r['park_id']} orders={r['orders']:>6d} completed={r['completed']:>6d} "
              f"cancelled={r['cancelled']:>5d} "
              f"range=[{str(r['min_ended'])[:19]} -> {str(r['max_ended'])[:19]}]")
        total_ya += r['orders']
        total_ya_completed += r['completed']
    print(f"  TOTAL: {total_ya} orders ({total_ya_completed} completed, {total_ya - total_ya_completed} cancelled)")

    # ======================================================================
    # 5. YANGO ORDERS BY HOUR (UTC vs Lima)
    # ======================================================================
    sep("6. YANGO orders_raw BY HOUR (UTC) FOR 2026-06-10")
    cur.execute("""
        SELECT EXTRACT(HOUR FROM order_ended_at)::int AS hour_utc,
               COUNT(*) AS orders,
               COUNT(*) FILTER (WHERE order_status = 'complete') AS completed,
               COUNT(*) FILTER (WHERE order_status = 'cancelled') AS cancelled
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date = %(d)s
        GROUP BY 1
        ORDER BY 1
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        bar = '#' * (max(r['orders'] // 50, 1))
        print(f"  H{r['hour_utc']:02d} UTC: {r['orders']:>5d} orders ({r['completed']:>4d} completed, {r['cancelled']:>3d} cancelled) {bar}")

    sep("7. YANGO orders_raw BY HOUR (Lima) FOR 2026-06-10")
    cur.execute("""
        SELECT EXTRACT(HOUR FROM order_ended_at AT TIME ZONE 'America/Lima')::int AS hour_lima,
               COUNT(*) AS orders,
               COUNT(*) FILTER (WHERE order_status = 'complete') AS completed
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date = %(d)s
        GROUP BY 1
        ORDER BY 1
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        bar = '#' * (max(r['orders'] // 50, 1))
        print(f"  H{r['hour_lima']:02d} Lima: {r['orders']:>5d} orders ({r['completed']:>4d} completed) {bar}")

    # ======================================================================
    # 6. YANGO ORDERS BY STATUS
    # ======================================================================
    sep("8. YANGO orders_raw BY STATUS FOR 2026-06-10")
    cur.execute("""
        SELECT order_status, COUNT(*) AS orders
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date = %(d)s
        GROUP BY order_status
        ORDER BY orders DESC
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        print(f"  {r['order_status']:30s}: {r['orders']:>6d}")

    # ======================================================================
    # 7. YANGO ORDERS TIMESTAMP AUDIT (ended_at vs created_at vs booked_at)
    # ======================================================================
    sep("9. YANGO orders_raw TIMESTAMP RANGES FOR 2026-06-10")
    cur.execute("""
        SELECT
            MIN(order_created_at) AS min_created,
            MAX(order_created_at) AS max_created,
            MIN(order_booked_at) AS min_booked,
            MAX(order_booked_at) AS max_booked,
            MIN(order_ended_at) AS min_ended,
            MAX(order_ended_at) AS max_ended,
            MIN(order_ended_at AT TIME ZONE 'America/Lima') AS min_ended_lima,
            MAX(order_ended_at AT TIME ZONE 'America/Lima') AS max_ended_lima,
            COUNT(DISTINCT order_ended_at::date) AS distinct_dates
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date = %(d)s
    """, {"d": TARGET_DATE})
    r = cur.fetchone()
    print(f"  created_at   range: [{str(r['min_created'])[:19]}] -> [{str(r['max_created'])[:19]}]")
    print(f"  booked_at    range: [{str(r['min_booked'])[:19]}] -> [{str(r['max_booked'])[:19]}]")
    print(f"  ended_at UTC range: [{str(r['min_ended'])[:19]}] -> [{str(r['max_ended'])[:19]}]")
    print(f"  ended_at Lima rng: [{str(r['min_ended_lima'])[:19]}] -> [{str(r['max_ended_lima'])[:19]}]")
    print(f"  distinct ended_at dates: {r['distinct_dates']}")

    # ======================================================================
    # 8. YANGO ORDERS BROADER DATE WINDOW (1 day before/after)
    # ======================================================================
    sep("10. YANGO orders_raw 3-DAY WINDOW AROUND 2026-06-10")
    cur.execute("""
        SELECT order_ended_at::date AS ended_date,
               COUNT(*) AS orders,
               COUNT(*) FILTER (WHERE order_status = 'complete') AS completed
        FROM raw_yango.orders_raw
        WHERE order_ended_at::date BETWEEN '2026-06-09' AND '2026-06-11'
        GROUP BY 1
        ORDER BY 1
    """)
    for r in cur.fetchall():
        print(f"  {r['ended_date']}: {r['orders']:>6d} orders ({r['completed']:>5d} completed)")

    # Also check by created_at and booked_at
    cur.execute("""
        SELECT 'created_at' AS ts_field,
               order_created_at::date AS d,
               COUNT(*) AS orders
        FROM raw_yango.orders_raw
        WHERE order_created_at::date BETWEEN '2026-06-09' AND '2026-06-11'
        GROUP BY 2 ORDER BY 2
    """)
    print(f"\n  By created_at:")
    for r in cur.fetchall():
        print(f"    {r['d']}: {r['orders']:>6d} orders")

    cur.execute("""
        SELECT 'booked_at' AS ts_field,
               order_booked_at::date AS d,
               COUNT(*) AS orders
        FROM raw_yango.orders_raw
        WHERE order_booked_at::date BETWEEN '2026-06-09' AND '2026-06-11'
        GROUP BY 2 ORDER BY 2
    """)
    print(f"\n  By booked_at:")
    for r in cur.fetchall():
        print(f"    {r['d']}: {r['orders']:>6d} orders")

    # ======================================================================
    # 9. INGESTION RUN AUDIT
    # ======================================================================
    sep("11. YANGO INGESTION RUNS (recent)")
    cur.execute("""
        SELECT run_id, endpoint_group, park_id, date_from, date_to, status,
               records_fetched, records_inserted, record_skips, error_count,
               started_at, finished_at,
               current_page, pages_completed, expected_pages, max_concurrency,
               notes
        FROM raw_yango.api_ingestion_run
        ORDER BY started_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    print(f"  Total recent runs: {len(rows)}")
    for r in rows:
        park_short = r['park_id'][:8] + '...' if r['park_id'] else 'NONE'
        print(f"  [{r['status']:11s}] run={r['run_id'][:12]}... park={park_short} "
              f"endpoint={r['endpoint_group']:17s} "
              f"date=[{r['date_from']} -> {r['date_to']}] "
              f"fetched={r['records_fetched']:>6d} inserted={r['records_inserted']:>6d} "
              f"skipped={r['record_skips']:>5d} errors={r['error_count']:>3d} "
              f"pages={r['pages_completed']}/{r['expected_pages']} "
              f"started={str(r['started_at'])[:19]}")
        if r['notes']:
            print(f"          notes: {r['notes'][:200]}")

    # ======================================================================
    # 10. PAGE CHECKPOINT AUDIT
    # ======================================================================
    sep("12. YANGO PAGE CHECKPOINTS (recent)")
    cur.execute("""
        SELECT run_id, park_id, endpoint_group, target_date, page_number,
               status, records_count, records_inserted,
               started_at, finished_at, error_message_sanitized
        FROM raw_yango.api_ingestion_page_checkpoint
        ORDER BY started_at DESC NULLS LAST
        LIMIT 30
    """)
    rows = cur.fetchall()
    print(f"  Recent checkpoints: {len(rows)}")
    for r in rows:
        park_short = r['park_id'][:8] + '...' if r['park_id'] else 'NONE'
        err = f" err={r['error_message_sanitized'][:60]}" if r['error_message_sanitized'] else ''
        print(f"  [{r['status']:10s}] run={r['run_id'][:12]}... park={park_short} "
              f"endpoint={r['endpoint_group']:17s} date={r['target_date']} "
              f"page={r['page_number']:>3d} records={r['records_count']:>4d} "
              f"inserted={r['records_inserted']:>4d}{err}")

    # ======================================================================
    # 11. TRANSACTIONS AUDIT
    # ======================================================================
    sep("13. YANGO transactions_raw ON 2026-06-10")
    cur.execute("""
        SELECT park_id,
               COUNT(*) AS txn_count,
               COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS partner_fee_count,
               COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0) AS partner_fee_rev,
               MIN(event_at) AS min_event,
               MAX(event_at) AS max_event,
               COUNT(DISTINCT event_at::date) AS distinct_dates
        FROM raw_yango.transactions_raw
        WHERE event_at::date = %(d)s
        GROUP BY park_id
        ORDER BY txn_count DESC
    """, {"d": TARGET_DATE})
    rows = cur.fetchall()
    total_txn = 0
    for r in rows:
        print(f"  park={r['park_id']} txn={r['txn_count']:>5d} partner_fee={r['partner_fee_count']:>4d} "
              f"rev={r['partner_fee_rev']:>10.2f} "
              f"event_range=[{str(r['min_event'])[:19]} -> {str(r['max_event'])[:19]}]")
        total_txn += r['txn_count']
    print(f"  TOTAL transactions: {total_txn}")

    # 3-day window
    cur.execute("""
        SELECT event_at::date AS d,
               COUNT(*) AS txn,
               COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS pf
        FROM raw_yango.transactions_raw
        WHERE event_at::date BETWEEN '2026-06-09' AND '2026-06-11'
        GROUP BY 1 ORDER BY 1
    """)
    print(f"\n  By event_at (3-day window):")
    for r in cur.fetchall():
        print(f"    {r['d']}: {r['txn']:>6d} txn ({r['pf']:>4d} partner_fee)")

    # ======================================================================
    # 12. OPERATIONAL_DATE AUDIT
    # ======================================================================
    sep("14. YANGO orders_raw BY operational_date (migration 186)")
    try:
        cur.execute("""
            SELECT operational_date, COUNT(*) AS orders
            FROM raw_yango.orders_raw
            WHERE operational_date BETWEEN '2026-06-09' AND '2026-06-11'
            GROUP BY 1 ORDER BY 1
        """)
        for r in cur.fetchall():
            print(f"  operational_date={r['operational_date']}: {r['orders']:>6d} orders")
    except Exception as e:
        print(f"  [column may not exist]: {e}")

    # ======================================================================
    # 13. YANGO ORDERS TOTAL DATE RANGE
    # ======================================================================
    sep("15. YANGO orders_raw FULL DATE RANGE")
    cur.execute("""
        SELECT
            MIN(order_ended_at::date) AS min_date,
            MAX(order_ended_at::date) AS max_date,
            COUNT(DISTINCT order_ended_at::date) AS days_covered,
            COUNT(*) AS total_orders
        FROM raw_yango.orders_raw
    """)
    r = cur.fetchone()
    print(f"  Date range: {r['min_date']} -> {r['max_date']} ({r['days_covered']} days)")
    print(f"  Total orders in raw: {r['total_orders']}")

    cur.execute("""
        SELECT order_ended_at::date AS d, COUNT(*) AS orders
        FROM raw_yango.orders_raw
        GROUP BY 1 ORDER BY 1
    """)
    for row in cur.fetchall():
        print(f"    {row['d']}: {row['orders']:>6d} orders")

    # ======================================================================
    # 14. SEARCH PARKS IN BOTH SYSTEMS
    # ======================================================================
    sep("16. PARKS COMPARISON: Yango registry vs CT trips_2026")
    cur.execute("""
        SELECT y.park_id AS yango_park,
               y.fleet_name, y.is_active,
               COUNT(t.park_id) AS ct_trips_count
        FROM raw_yango.api_park_credentials_registry y
        LEFT JOIN public.trips_2026 t
            ON y.park_id = t.park_id
            AND t.fecha_finalizacion::date = %(d)s
        GROUP BY y.park_id, y.fleet_name, y.is_active
        ORDER BY ct_trips_count DESC
    """, {"d": TARGET_DATE})
    for r in cur.fetchall():
        match = "MATCH" if r['ct_trips_count'] > 0 else "NO CT DATA"
        print(f"  Yango park={r['yango_park']} fleet={r['fleet_name']} active={r['is_active']} -> CT trips={r['ct_trips_count']} [{match}]")

    # Parks in CT not in Yango
    cur.execute("""
        SELECT t.park_id, COUNT(*) AS trips
        FROM public.trips_2026 t
        WHERE t.fecha_finalizacion::date = %(d)s
          AND t.park_id NOT IN (
              SELECT park_id FROM raw_yango.api_park_credentials_registry
          )
        GROUP BY t.park_id
        ORDER BY trips DESC
    """, {"d": TARGET_DATE})
    rows = cur.fetchall()
    print(f"\n  Parks in CT but NOT in Yango registry: {len(rows)}")
    for r in rows:
        print(f"    park={r['park_id']} trips={r['trips']}")

    # ======================================================================
    # 15. SUMMARY
    # ======================================================================
    sep("SUMMARY")
    ct_park_count = len([r for r in cur.execute("SELECT DISTINCT park_id FROM public.trips_2026 WHERE fecha_finalizacion::date = %(d)s", {"d": TARGET_DATE}) or []])
    print(f"  CT parks with trips on {TARGET_DATE}: multiple (see section 2)")
    print(f"  Yango parks with orders on {TARGET_DATE}: multiple (see section 5)")
    print(f"  CT total completed trips: {total_ct_completed}")
    print(f"  Yango total completed orders: {total_ya_completed}")
    print(f"  Ratio Yango/CT: {total_ya_completed / max(total_ct_completed, 1) * 100:.1f}%")

    cur.close()
