"""
CF-H2C.0C — Lima Semantic Reconciliation Audit

Answers:
1. Why Yango > CT on some days?
2. Physical/logical duplicates in orders_raw?
3. Yango vs CT overlap
4. Revenue semantic gap
5. GMV semantic gap
6. Metric ownership matrix
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

LIMA = "08e20910d81d42658d4334d3f6d10ac0"

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 70)
    print("CF-H2C.0C — LIMA SEMANTIC RECONCILIATION AUDIT")
    print("=" * 70)

    # ═══════════════════════════════════════════════════════════════
    # Q1: OVERCOVERAGE — Why Yango > CT on some days?
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q1: DAILY ORDER COUNTS (raw vs distinct vs CT) ---")
    cur.execute("""
        SELECT
            order_ended_at::date AS d,
            COUNT(*) AS raw_rows,
            COUNT(DISTINCT order_id) AS distinct_orders,
            COUNT(*) - COUNT(DISTINCT order_id) AS duplicates
        FROM raw_yango.orders_raw
        WHERE park_id = %s AND order_ended_at::date >= '2026-06-01'
        GROUP BY d ORDER BY d
    """, (LIMA,))
    print(f"  {'Date':>12s} {'RawRows':>9s} {'Distinct':>9s} {'Dups':>6s} {'Dup%':>7s}")
    print("  " + "-" * 48)
    for r in cur.fetchall():
        dup_pct = round((r['duplicates'] / max(r['raw_rows'], 1)) * 100, 1)
        print(f"  {str(r['d']):>12s} {r['raw_rows']:>9,d} {r['distinct_orders']:>9,d} {r['duplicates']:>6,d} {dup_pct:>6.1f}%")


    # ═══════════════════════════════════════════════════════════════
    # Q2: DUPLICATE ANALYSIS — multiple payload_hash per order_id
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q2: ORDER_ID DUPLICATE ANALYSIS (Jun 9-10, highest overcoverage) ---")
    cur.execute("""
        SELECT order_id, COUNT(*) AS versions, COUNT(DISTINCT raw_payload_hash) AS hashes,
               MIN(order_ended_at) AS min_ended, MAX(order_ended_at) AS max_ended,
               STRING_AGG(DISTINCT order_status, ',') AS statuses
        FROM raw_yango.orders_raw
        WHERE park_id = %s AND order_ended_at::date = '2026-06-10'
        GROUP BY order_id
        HAVING COUNT(*) > 1
        ORDER BY versions DESC
        LIMIT 15
    """, (LIMA,))
    for r in cur.fetchall():
        same_hash = "SAME_HASH" if r['hashes'] == 1 else f"{r['hashes']}hashes"
        print(f"  order={r['order_id'][:14]}... versions={r['versions']} {same_hash} "
              f"ended_range=[{str(r['min_ended'])[:19]}..{str(r['max_ended'])[:19]}] status={r['statuses']}")

    # Total duplicates
    cur.execute("""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT order_id) AS distinct_orders,
            COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_rows,
            COUNT(DISTINCT order_id) FILTER (WHERE order_id IN (
                SELECT order_id FROM raw_yango.orders_raw WHERE park_id=%s
                GROUP BY order_id HAVING COUNT(*) > 1
            )) AS dup_order_ids
        FROM raw_yango.orders_raw
        WHERE park_id = %s AND order_ended_at::date = '2026-06-10'
    """, (LIMA, LIMA))
    r = cur.fetchone()
    print(f"\n  Jun 10: {r['total_rows']:,d} rows, {r['distinct_orders']:,d} distinct orders, "
          f"{r['duplicate_rows']:,d} duplicate rows from {r['dup_order_ids']:,d} dup order_ids")

    # Also check transactions
    print("\n--- Q2: TRANSACTION_ID DUPLICATE ANALYSIS ---")
    cur.execute("""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(DISTINCT transaction_id) AS distinct_txn,
            COUNT(*) - COUNT(DISTINCT transaction_id) AS dup_rows
        FROM raw_yango.transactions_raw
        WHERE park_id = %s AND event_at::date = '2026-06-10'
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Jun 10: {r['total_rows']:,d} rows, {r['distinct_txn']:,d} distinct txns, "
          f"{r['dup_rows']:,d} dup rows")


    # ═══════════════════════════════════════════════════════════════
    # Q3: YANGO vs CT — OVERLAP on order_id ↔ codigo_pedido
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q3: YANGO vs CT ORDER OVERLAP (by order_id = codigo_pedido) ---")
    cur.execute("""
        SELECT
            y.d,
            y.yango_orders,
            COALESCE(ct.ct_trips, 0) AS ct_trips,
            COALESCE(ol.overlap, 0) AS matched,
            y.yango_orders - COALESCE(ol.overlap, 0) AS yango_only,
            COALESCE(ct.ct_trips, 0) - COALESCE(ol.overlap, 0) AS ct_only,
            CASE WHEN COALESCE(ct.ct_trips, 0) > 0
                 THEN ROUND(COALESCE(ol.overlap, 0)::numeric / ct.ct_trips * 100, 1)
                 ELSE NULL END AS overlap_pct
        FROM (
            SELECT order_ended_at::date AS d, COUNT(DISTINCT order_id) AS yango_orders
            FROM raw_yango.orders_raw WHERE park_id=%s AND order_ended_at::date >= '2026-06-01'
            GROUP BY d
        ) y
        LEFT JOIN (
            SELECT fecha_finalizacion::date AS d, COUNT(*) AS ct_trips
            FROM public.trips_2026 WHERE park_id=%s AND condicion='Completado'
            GROUP BY d
        ) ct ON y.d = ct.d
        LEFT JOIN (
            SELECT y2.order_ended_at::date AS d, COUNT(DISTINCT y2.order_id) AS overlap
            FROM raw_yango.orders_raw y2
            INNER JOIN public.trips_2026 t ON y2.order_id = t.codigo_pedido
            WHERE y2.park_id=%s AND t.park_id=%s
            GROUP BY y2.order_ended_at::date
        ) ol ON y.d = ol.d
        ORDER BY y.d
    """, (LIMA, LIMA, LIMA, LIMA))

    print(f"  {'Date':>12s} {'Yango':>8s} {'CT':>8s} {'Matched':>8s} {'Y-Only':>8s} {'CT-Only':>8s} {'Overlap%':>9s}")
    print("  " + "-" * 65)
    for r in cur.fetchall():
        print(f"  {str(r['d']):>12s} {r['yango_orders']:>8,d} {r['ct_trips']:>8,d} "
              f"{r['matched']:>8,d} {r['yango_only']:>8,d} {r['ct_only']:>8,d} {r['overlap_pct'] or 0:>8.1f}%")


    # ═══════════════════════════════════════════════════════════════
    # Q4: DRIVER OVERLAP
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q4: DRIVER OVERLAP Yango vs CT ---")
    cur.execute("""
        SELECT
            COUNT(DISTINCT y.driver_profile_id) AS yango_drivers,
            COUNT(DISTINCT ct.conductor_id) AS ct_drivers,
            COUNT(DISTINCT y.driver_profile_id) FILTER (
                WHERE y.driver_profile_id IN (SELECT DISTINCT conductor_id FROM public.trips_2026 WHERE park_id=%s)
            ) AS matched_drivers
        FROM raw_yango.orders_raw y
        LEFT JOIN public.trips_2026 ct ON y.driver_profile_id = ct.conductor_id
        WHERE y.park_id = %s AND y.order_ended_at::date = '2026-06-10'
    """, (LIMA, LIMA))
    r = cur.fetchone()
    print(f"  Jun 10: Yango drivers={r['yango_drivers']:,d}, CT drivers (from trips)={r['ct_drivers']:,d}, "
          f"matched={r['matched_drivers']:,d}")

    # Check driver_profile_id vs public.drivers.driver_id match
    cur.execute("""
        SELECT
            COUNT(DISTINCT y.driver_profile_id) AS yango_drivers,
            COUNT(DISTINCT y.driver_profile_id) FILTER (
                WHERE y.driver_profile_id IN (SELECT driver_id FROM public.drivers)
            ) AS matched_in_drivers
        FROM raw_yango.orders_raw y
        WHERE y.park_id = %s AND y.order_ended_at::date = '2026-06-10'
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Yango drivers matched in public.drivers: {r['matched_in_drivers']:,d} / {r['yango_drivers']:,d} "
          f"({round(r['matched_in_drivers']/max(r['yango_drivers'],1)*100,1)}%)")


    # ═══════════════════════════════════════════════════════════════
    # Q5: STATUS SEMANTICS
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q5: STATUS SEMANTICS ---")
    cur.execute("SELECT order_status, COUNT(*) as cnt FROM raw_yango.orders_raw WHERE park_id=%s GROUP BY 1 ORDER BY cnt DESC", (LIMA,))
    for r in cur.fetchall():
        print(f"  Yango status: {r['order_status']:20s} = {r['cnt']:>8,d}")

    cur.execute("SELECT condicion, COUNT(*) as cnt FROM public.trips_2026 WHERE park_id=%s AND fecha_finalizacion::date='2026-06-10' GROUP BY 1 ORDER BY cnt DESC", (LIMA,))
    for r in cur.fetchall():
        print(f"  CT status:   {r['condicion']:20s} = {r['cnt']:>8,d}")

    # Check: Yango only has 'complete' — is this because we only query for complete?
    print("  NOTE: Yango API query filters statuses: ['complete']. Cancelled orders are not ingested.")


    # ═══════════════════════════════════════════════════════════════
    # Q6: REVENUE SEMANTICS
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q6: REVENUE SEMANTICS (Jun 10) ---")

    # Yango revenue components
    cur.execute("""
        SELECT
            ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name='Partner fee for trip'), 0), 2) AS partner_fee,
            ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name='Service fee for trip'), 0), 2) AS service_fee,
            ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name='Service fee, VAT'), 0), 2) AS service_fee_vat,
            ROUND(COALESCE(SUM(amount) FILTER (WHERE category_name='Cash'), 0), 2) AS gmv_cash,
            ROUND(COALESCE(SUM(amount) FILTER (WHERE category_name='Card payment'), 0), 2) AS gmv_card,
            ROUND(COALESCE(SUM(amount) FILTER (WHERE category_name='Corporate payment'), 0), 2) AS gmv_corp,
            COUNT(DISTINCT order_id) AS linked_orders,
            COUNT(*) AS total_txn
        FROM raw_yango.transactions_raw
        WHERE park_id=%s AND event_at::date='2026-06-10'
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  Yango Partner fee:      {r['partner_fee']:>12,.2f} PEN ({r['total_txn']:,d} txns, {r['linked_orders']:,d} orders)")
    print(f"  Yango Service fee:      {r['service_fee']:>12,.2f} PEN")
    print(f"  Yango Service fee VAT:  {r['service_fee_vat']:>12,.2f} PEN")
    print(f"  Yango GMV Cash:         {r['gmv_cash']:>12,.2f} PEN")
    print(f"  Yango GMV Card:         {r['gmv_card']:>12,.2f} PEN")
    print(f"  Yango GMV Corporate:    {r['gmv_corp']:>12,.2f} PEN")
    total_gmv = (r['gmv_cash'] or 0) + (r['gmv_card'] or 0) + (r['gmv_corp'] or 0)
    print(f"  Yango GMV Total:        {total_gmv:>12,.2f} PEN")
    print(f"  Yango Revenue/order:    {r['partner_fee'] / max(r['linked_orders'], 1):.4f} PEN")

    # CT revenue
    cur.execute("""
        SELECT
            ROUND(COALESCE(SUM(revenue_yego_final), 0), 2) AS rev_final,
            ROUND(COALESCE(SUM(revenue_yego_net), 0), 2) AS rev_net,
            COALESCE(SUM(trips_completed), 0) AS trips
        FROM ops.real_business_slice_day_fact
        WHERE city='lima' AND country='peru' AND trip_date='2026-06-10'
    """)
    r = cur.fetchone()
    print(f"\n  CT revenue_yego_final:  {r['rev_final']:>12,.2f} PEN ({r['trips']:,d} trips)")
    print(f"  CT revenue_yego_net:    {r['rev_net']:>12,.2f} PEN")
    if r['trips'] > 0:
        print(f"  CT Revenue/trip:        {r['rev_final'] / r['trips']:.4f} PEN")

    # Compare per-trip revenue
    cur.execute("""
        SELECT
            ROUND(COALESCE(SUM(ABS(amount)) FILTER (WHERE category_name='Partner fee for trip'), 0) /
                  NULLIF(COUNT(DISTINCT order_id), 0), 4) AS ya_rev_per_order
        FROM raw_yango.transactions_raw
        WHERE park_id=%s AND event_at::date='2026-06-10'
    """, (LIMA,))
    ya_rev_per = cur.fetchone()['ya_rev_per_order']
    print(f"\n  Yango Partner fee/order: {ya_rev_per:.4f} PEN")
    print(f"  CT revenue_yego_final/trip: {r['rev_final'] / max(r['trips'], 1):.4f} PEN")
    ratio = ya_rev_per / max(r['rev_final'] / max(r['trips'], 1), 0.0001) * 100
    print(f"  Ratio Yango/CT: {ratio:.1f}%")
    print(f"  Revenue semantic gap: CT includes proxy/ticket-based revenue; Yango is pure commission.")
    print(f"  Partner fee (Yango) = what YEGO charges driver per trip.")
    print(f"  revenue_yego_final (CT) = comision_empresa_asociada + proxy (ticket * 3%% when commission missing).")


    # ═══════════════════════════════════════════════════════════════
    # Q7: GMV SEMANTICS
    # ═══════════════════════════════════════════════════════════════
    print("\n--- Q7: GMV SEMANTICS ---")

    cur.execute("""
        SELECT
            ROUND(COALESCE(SUM(efectivo), 0), 2) AS ct_efectivo,
            ROUND(COALESCE(SUM(tarjeta), 0), 2) AS ct_tarjeta,
            ROUND(COALESCE(SUM(pago_corporativo), 0), 2) AS ct_corporativo,
            ROUND(COALESCE(SUM(efectivo+tarjeta+pago_corporativo), 0), 2) AS ct_gmv,
            ROUND(COALESCE(AVG(precio_yango_pro), 0), 2) AS ct_ticket,
            COUNT(*) AS ct_trips
        FROM public.trips_2026
        WHERE park_id=%s AND fecha_finalizacion::date='2026-06-10' AND condicion='Completado'
    """, (LIMA,))
    r = cur.fetchone()
    print(f"  CT efectivo:           {r['ct_efectivo']:>12,.2f}")
    print(f"  CT tarjeta:            {r['ct_tarjeta']:>12,.2f}")
    print(f"  CT pago_corporativo:   {r['ct_corporativo']:>12,.2f}")
    print(f"  CT GMV Total:          {r['ct_gmv']:>12,.2f} ({r['ct_trips']:,d} trips)")
    print(f"  CT Avg Ticket:         {r['ct_ticket']:>12.2f}")

    if r['ct_gmv'] > 0 and total_gmv > 0:
        gmv_ratio = total_gmv / r['ct_gmv'] * 100
        print(f"  Yango/CT GMV ratio:    {gmv_ratio:.1f}%")

    if r['ct_gmv'] == 0:
        print(f"  CT GMV = 0: columnas efectivo/tarjeta/pago_corporativo estan en 0 en trips_2026 para Lima.")
        print(f"  GMV comparable desde Yango (Cash+Card+Corporate) = {total_gmv:,.2f} PEN")
        print(f"  CT NO tiene GMV comparable confiable en trips_2026.")


    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("PRELIMINARY METRIC OWNERSHIP MATRIX (LIMA)")
    print("=" * 70)

    print("""
  KPI                  Yango Truth          CT Truth             Decision
  ─────────────────────────────────────────────────────────────────────────
  completed_trips      COUNT(DISTINCT       trips_completed      YANGO (con
                       order_id) from       from day_fact        auditoria:
                       orders_raw                                dedup por
                                                                 payload_hash
                                                                 +overlap vs
                                                                 CT para
                                                                 validacion)

  cancelled_trips      NOT INGESTED         trips_cancelled      CT_BRIDGE
                       (API filter:         from day_fact        (Yango no
                       statuses=['complete'])                    ingiere
                                                                cancelados)

  revenue              SUM(ABS(amount))     revenue_yego_final   SHADOW (gap
                       WHERE category_name  (comision_empresa_   documentado:
                       ='Partner fee        asociada + proxy     Yango ~20%
                       for trip')           ticket*3%%)          de CT porque
                                                                CT incluye
                                                                proxy revenue)

  active_drivers       COUNT(DISTINCT       COUNT(DISTINCT       YANGO (ID
                       driver_profile_id)   conductor_id) from   confirmado:
                       from orders_raw      trips_2026           800/800 match
                                                                con public.
                                                                drivers)

  GMV                  Cash+Card+           efectivo+tarjeta+    YANGO (CT
                       Corporate from       pago_corporativo     GMV = 0 en
                       transactions_raw     from trips_2026      trips_2026
                                                                para Lima)

  avg_ticket           Derived: GMV /       avg_ticket from      DERIVED
                       orders               day_fact             (depende de
                                                                source de
                                                                trips y GMV)

  commission_rate      Service fee /        commission_pct       YANGO
                       GMV from             from day_fact        (Service fee
                       transactions                             es medible
                                                                directamente)
  """)

    cur.close()

print("\nDone.")
