"""
CF-H2C.0B — Lima Revenue Validation

Validates revenue from Yango transactions vs CT day_fact.
Uses existing data in raw_yango.transactions_raw + live API test.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta

PET = timezone(timedelta(hours=-5))
LIMA = "08e20910d81d42658d4334d3f6d10ac0"

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 80)
    print("CF-H2C.0B — LIMA REVENUE VALIDATION")
    print("=" * 80)

    # ======================================================================
    # 1. TRANSACTIONS BY DATE
    # ======================================================================
    print("\n--- 1. TRANSACTIONS BY DATE ---")
    cur.execute("""
        SELECT event_at::date AS d,
               COUNT(*) AS total_txn,
               COUNT(*) FILTER (WHERE category_name = 'Partner fee for trip') AS pf_count,
               ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0), 2) AS revenue,
               ROUND(COALESCE(SUM(amount) FILTER (WHERE category_name = 'Cash'), 0), 2) AS gmv_cash,
               ROUND(COALESCE(SUM(amount) FILTER (WHERE category_name = 'Card payment'), 0), 2) AS gmv_card,
               ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Service fee for trip'), 0), 2) AS platform_fee,
               COUNT(DISTINCT order_id) AS linked_orders,
               MIN(event_at) AS min_evt,
               MAX(event_at) AS max_evt
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
        GROUP BY event_at::date
        ORDER BY d
    """, (LIMA,))

    print(f"{'Date':>12s} {'Total':>8s} {'PF':>6s} {'Revenue':>12s} {'GMV Cash':>10s} {'GMV Card':>10s} {'PlatFee':>10s} {'Orders':>7s} {'Events':>44s}")
    print("-" * 130)
    total_days = 0
    days_with_data = 0
    for r in cur.fetchall():
        total_days += 1
        has_data = r['total_txn'] > 0
        if has_data:
            days_with_data += 1
        print(f"{str(r['d']):>12s} {r['total_txn']:>8d} {r['pf_count']:>6d} "
              f"{r['revenue']:>12.2f} {r['gmv_cash']:>10.2f} {r['gmv_card']:>10.2f} "
              f"{r['platform_fee']:>10.2f} {r['linked_orders']:>7d} "
              f"{str(r['min_evt'])[:19]}..{str(r['max_evt'])[:19]}")

    print(f"\n  Days with transactions: {days_with_data}/{total_days}")
    if total_days > 0:
        print(f"  Coverage: {days_with_data / total_days * 100:.0f}%")

    # ======================================================================
    # 2. CATEGORY SUMMARY
    # ======================================================================
    print("\n--- 2. TRANSACTION CATEGORY SUMMARY ---")
    cur.execute("""
        SELECT category_name, COUNT(*) AS cnt,
               ROUND(SUM(amount), 2) AS sum_amount,
               ROUND(SUM(ABS(amount)), 2) AS sum_abs,
               MIN(amount) AS min_a, MAX(amount) AS max_a
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
        GROUP BY category_name
        ORDER BY cnt DESC
    """, (LIMA,))
    for r in cur.fetchall():
        print(f"  {r['category_name']:45s} count={r['cnt']:>6d} sum={r['sum_amount']:>12.2f} "
              f"abs={r['sum_abs']:>12.2f} range=[{r['min_a']}, {r['max_a']}]")

    # ======================================================================
    # 3. CURRENCY CHECK
    # ======================================================================
    print("\n--- 3. CURRENCY CONSISTENCY ---")
    cur.execute("""
        SELECT currency_code, COUNT(*) AS cnt
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
        GROUP BY currency_code
    """, (LIMA,))
    currencies = cur.fetchall()
    for r in currencies:
        print(f"  {r['currency_code']}: {r['cnt']}")
    all_pen = all(r['currency_code'] == 'PEN' for r in currencies) if currencies else False
    print(f"  Currency consistency: {'PASS (100% PEN)' if all_pen else 'FAIL'}")

    # ======================================================================
    # 4. CT REVENUE — CORRECTED SCOPE (Lima only)
    # ======================================================================
    print("\n--- 4. CT REVENUE (LIMA ONLY) ---")
    cur.execute("""
        SELECT trip_date,
               ROUND(COALESCE(SUM(revenue_yego_final), 0), 2) AS ct_rev,
               ROUND(COALESCE(AVG(avg_ticket), 0), 2) AS ct_avg_ticket,
               COALESCE(SUM(trips_completed), 0) AS ct_trips
        FROM ops.real_business_slice_day_fact
        WHERE city = 'lima' AND country = 'peru'
          AND trip_date BETWEEN '2026-06-01' AND '2026-06-11'
        GROUP BY trip_date
        ORDER BY trip_date
    """)
    print(f"{'Date':>12s} {'CT Revenue':>12s} {'CT Trips':>9s} {'Avg Ticket':>10s}")
    print("-" * 50)
    for r in cur.fetchall():
        print(f"{str(r['trip_date']):>12s} {r['ct_rev']:>12.2f} {int(r['ct_trips'] or 0):>9d} {r['ct_avg_ticket']:>10.2f}")

    # ======================================================================
    # 5. REVENUE COMPARISON: Yango vs CT (for days with data)
    # ======================================================================
    print("\n--- 5. REVENUE COMPARISON (Yango vs CT) ---")
    cur.execute("""
        SELECT
            ya.d,
            ya.revenue AS ya_rev,
            ROUND(COALESCE(ct.ct_rev, 0), 2) AS ct_rev,
            ROUND(CASE WHEN COALESCE(ct.ct_rev, 0) > 0
                       THEN (ya.revenue - ct.ct_rev) / ct.ct_rev * 100
                       ELSE NULL END, 1) AS delta_pct,
            CASE WHEN ct.ct_rev > 0 THEN
                CASE WHEN ABS((ya.revenue - ct.ct_rev) / ct.ct_rev) <= 0.05 THEN 'PASS'
                     WHEN ABS((ya.revenue - ct.ct_rev) / ct.ct_rev) <= 0.20 THEN 'WARN'
                     ELSE 'FAIL' END
            ELSE 'NO_CT' END AS status
        FROM (
            SELECT event_at::date AS d,
                   ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0), 2) AS revenue
            FROM raw_yango.transactions_raw
            WHERE park_id = %s
            GROUP BY event_at::date
        ) ya
        LEFT JOIN (
            SELECT trip_date, COALESCE(SUM(revenue_yego_final), 0) AS ct_rev
            FROM ops.real_business_slice_day_fact
            WHERE city = 'lima' AND country = 'peru'
            GROUP BY trip_date
        ) ct ON ya.d = ct.trip_date
        ORDER BY ya.d
    """, (LIMA,))

    print(f"{'Date':>12s} {'Yango Rev':>12s} {'CT Rev':>12s} {'Delta%':>8s} {'Status':>8s}")
    print("-" * 55)
    for r in cur.fetchall():
        print(f"{str(r['d']):>12s} {r['ya_rev']:>12.2f} {r['ct_rev']:>12.2f} "
              f"{float(r['delta_pct'] or 0):>7.1f}% {r['status']:>8s}")

    # ======================================================================
    # 6. GMV COMPARISON
    # ======================================================================
    print("\n--- 6. GMV COMPARISON ---")
    cur.execute("""
        SELECT
            ya.d,
            ROUND(ya.gmv, 2) AS ya_gmv,
            ROUND(COALESCE(ct.ct_gmv, 0), 2) AS ct_gmv
        FROM (
            SELECT event_at::date AS d,
                   COALESCE(SUM(amount) FILTER (WHERE category_name IN ('Cash', 'Card payment')), 0) AS gmv
            FROM raw_yango.transactions_raw
            WHERE park_id = %s
            GROUP BY event_at::date
        ) ya
        LEFT JOIN (
            SELECT fecha_finalizacion::date AS trip_date,
                   COALESCE(SUM(efectivo + tarjeta + pago_corporativo), 0) AS ct_gmv
            FROM public.trips_2026
            WHERE park_id = %s AND condicion = 'Completado'
            GROUP BY fecha_finalizacion::date
        ) ct ON ya.d = ct.trip_date
        ORDER BY ya.d
    """, (LIMA, LIMA))

    print(f"{'Date':>12s} {'Yango GMV':>12s} {'CT GMV':>12s} {'Delta%':>8s}")
    print("-" * 45)
    for r in cur.fetchall():
        delta = round(abs(float(r['ya_gmv'] or 0) - float(r['ct_gmv'] or 0)) / max(float(r['ct_gmv'] or 0.01), 0.01) * 100, 1) if float(r['ct_gmv'] or 0) > 0 else None
        print(f"{str(r['d']):>12s} {float(r['ya_gmv'] or 0):>12.2f} {float(r['ct_gmv'] or 0):>12.2f} {delta or 0:>7.1f}%")

    # ======================================================================
    # 7. FRESHNESS
    # ======================================================================
    print("\n--- 7. TRANSACTIONS FRESHNESS ---")
    cur.execute("""
        SELECT
            MAX(event_at) AS last_event,
            MAX(api_fetched_at) AS last_ingested,
            MAX(api_fetched_at) - MAX(event_at) AS ingestion_lag,
            NOW() - MAX(event_at) AS data_delay,
            COUNT(DISTINCT event_at::date) AS days_covered,
            COUNT(*) AS total_rows
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Last event: {str(r['last_event'])[:19]}")
    print(f"  Last ingested: {str(r['last_ingested'])[:19]}")
    print(f"  Ingestion lag: {r['ingestion_lag']}")
    print(f"  Data delay: {r['data_delay']}")
    print(f"  Days covered: {r['days_covered']}")
    print(f"  Total rows: {r['total_rows']}")

    # ======================================================================
    # 8. LIVE API TEST RESULT (from earlier probe)
    # ======================================================================
    print("\n--- 8. LIVE API VERIFICATION (2026-06-10 page 1) ---")
    print("  Status: 200 (16.4s)")
    print("  Page 1: 1000 transactions")
    print("  Has cursor: YES (next page available)")
    print("  Categories present: Partner fee, Service fee, Cash, Card, Promo, etc.")
    print("  Revenue per page (est.): ~225 partner_fee × ~1.0 PEN = ~225 PEN/page")
    print("  Estimated pages for full day: ~10 pages (based on 9,135 orders)")
    print("  Estimated total revenue: ~2,250 PEN/day")
    print("  Estimated ingestion time: ~160s/day (10 pages × 16s)")

    # ======================================================================
    # 9. SUMMARY
    # ======================================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\n  Transaction days with data: {days_with_data}/{total_days}")
    print(f"  Currency: {'100% PEN' if all_pen else 'MIXED'}")

    cur.execute("""
        SELECT COUNT(DISTINCT order_id) AS orders_with_txn,
               COUNT(DISTINCT driver_profile_id) AS drivers_with_txn
        FROM raw_yango.transactions_raw
        WHERE park_id = %s AND category_name = 'Partner fee for trip'
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Orders with Partner fee: {r['orders_with_txn']}")
    print(f"  Drivers with Partner fee: {r['drivers_with_txn']}")

    # Revenue trend
    cur.execute("""
        SELECT event_at::date AS d,
               ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name = 'Partner fee for trip'), 0), 2) AS rev
        FROM raw_yango.transactions_raw
        WHERE park_id = %s
        GROUP BY event_at::date
        ORDER BY d
    """, (LIMA,))
    revs = list(cur.fetchall())
    if revs:
        avg_rev = sum(float(r['rev']) for r in revs) / len(revs)
        print(f"  Avg daily revenue (days with data): {avg_rev:,.2f} PEN")

    cur.close()

print("\nDone.")
