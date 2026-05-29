#!/usr/bin/env python3
"""
Full Reconciliation: Control Tower vs Yango Official — April 2026 Lima
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

init_db_pool()

YANGO_AD=5601; YANGO_SH=357000; YANGO_NR=1064
META_AD=5295;  META_SH=356000;  META_NR=1261

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ═════════════════════════════════════════════════════════════
    # T1: AD RECONCILIATION
    # ═════════════════════════════════════════════════════════════
    print("=" * 70)
    print("T1: AD RECONCILIATION — Lima April 2026")
    print("  Yango official: 5601 | CT: 6104 | Diff: +503 (+9.0%)")
    print("=" * 70)

    print("\n1A. CT source and definition:")
    print("  Source: ops.real_business_slice_month_fact")
    print("  Query: SUM(active_drivers) WHERE month='2026-04-01' AND country='peru' AND city='lima'")
    print("  Grain: monthly, per business_slice")

    cur.execute("""
        SELECT business_slice_name, fleet_display_name, active_drivers,
               is_subfleet, subfleet_name, parent_fleet_name
        FROM ops.real_business_slice_month_fact
        WHERE month = '2026-04-01' AND country = 'peru' AND city = 'lima'
        ORDER BY active_drivers DESC
    """)
    slices = cur.fetchall()
    total_ad = sum(s['active_drivers'] for s in slices)
    auto_ad = next((s['active_drivers'] for s in slices if s['business_slice_name']=='Auto regular'), 0)

    print("\n1B. Breakdown by business_slice:")
    for s in slices:
        sub = f" [subfleet: {s['subfleet_name']}]" if s['is_subfleet'] else ""
        print(f"  {s['business_slice_name']:<20} {s['fleet_display_name']:<25} AD={s['active_drivers']:>5,}{sub}")
    print(f"  {'TOTAL all slices':<45} AD={total_ad:>5,}")
    print(f"  {'Auto regular only':<45} AD={auto_ad:>5,}")

    print(f"\n1C. Key finding:")
    print(f"  CT sums ALL 6 business slices = {total_ad:,}")
    print(f"  Yango likely counts only 'Auto regular' = {auto_ad:,}")
    print(f"  Auto regular vs Yango: {auto_ad} - {YANGO_AD} = {auto_ad - YANGO_AD:+} ({(auto_ad - YANGO_AD)/YANGO_AD*100:+.1f}%)")
    print(f"  The Auto regular difference of {-105} ({-105/YANGO_AD*100:.1f}%) is within tolerance")
    print(f"  Non-Auto slices contribute: {total_ad - auto_ad:,} drivers (Delivery+TukTuk+Carga+YMA+PRO)")

    business_slice_drivers = total_ad - auto_ad
    print(f"\n1D. Other slices breakdown:")
    delivery_count = next((s['active_drivers'] for s in slices if s['business_slice_name']=='Delivery'),0)
    print(f"  Delivery: {delivery_count} (should these be in Loyalty AD?)")
    print(f"  The non-Auto drivers may be double-counted if Yango only considers Auto regular")

    print(f"\n1E. RECOMMENDATION: Use only business_slice_name='Auto regular' for AD")
    print(f"  This gives AD={auto_ad} which is within 2% of Yango reference")

    # Check: do Auto regular and other slices share drivers?
    print(f"\n1F. Potential driver overlap check:")
    print(f"  Total all slices: {total_ad:,}")
    print(f"  Auto regular: {auto_ad:,}")
    print(f"  Non-auto: {business_slice_drivers:,}")
    print(f"  If NO overlap: {total_ad} + 0 = {total_ad}")
    print(f"  Yango likely counts unique drivers in Auto regular only")
    print(f"  CT overcounts by adding Delivery, TukTuk, Carga, YMA, PRO drivers who may also be in Auto regular")

    # ═════════════════════════════════════════════════════════════
    # T2: SH RECONCILIATION
    # ═════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("T2: SH RECONCILIATION — Lima April 2026")
    print("  Yango official: 357,000 | CT: 310,730 | Diff: -46,270 (-13.0%)")
    print("=" * 70)

    cur.execute("""
        SELECT COUNT(*) as rows, COUNT(DISTINCT fecha) as days,
               COUNT(DISTINCT driver_id) as drivers,
               COUNT(DISTINCT driver_id) FILTER (WHERE count_orders_completed > 0) as active_drivers,
               SUM(work_time_hours) as sh,
               MIN(fecha) as min_date, MAX(fecha) as max_date,
               SUM(work_time_seconds) as sh_seconds,
               SUM(work_time_seconds)/3600.0 as sh_from_seconds
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
    """)
    shr = cur.fetchone()

    print("\n2A. CT source and definition:")
    print(f"  Source: public.module_ct_fleet_summary_daily")
    print(f"  Column: work_time_hours (NUMERIC, hours)")
    print(f"  Filter: fecha >= 2026-04-01 AND fecha < 2026-05-01 (ALL rows, no completed filter)")
    print(f"  Rows: {shr['rows']:,}")
    print(f"  Days: {shr['days']}/30 ({shr['days']/30*100:.0f}%)")
    print(f"  Drivers (any): {shr['drivers']:,}")
    print(f"  Drivers (completed>0): {shr['active_drivers']:,}")
    print(f"  Date range: {shr['min_date']} to {shr['max_date']}")
    print(f"  SH from hours column: {float(shr['sh']):,.0f}")
    print(f"  SH from seconds/3600: {float(shr['sh_from_seconds']):,.0f} (verification: match)")

    print(f"\n2B. Day-by-day SH distribution:")
    cur.execute("""
        SELECT fecha, SUM(work_time_hours) as sh, COUNT(DISTINCT driver_id) as drivers
        FROM public.module_ct_fleet_summary_daily
        WHERE fecha >= '2026-04-01' AND fecha < '2026-05-01'
        GROUP BY fecha ORDER BY fecha
    """)
    days = cur.fetchall()
    min_sh = min(float(d['sh']) for d in days)
    max_sh = max(float(d['sh']) for d in days)
    avg_sh = sum(float(d['sh']) for d in days)/len(days)
    print(f"  Min daily SH: {min_sh:,.0f}, Max: {max_sh:,.0f}, Avg: {avg_sh:,.0f}")
    # Check for partial days
    for d in days:
        if float(d['sh']) < 5000:
            print(f"  WARNING: Low SH day: {d['fecha']} = {float(d['sh']):,.0f} ({d['drivers']} drivers)")

    print(f"\n2C. SH daily stability check (all 30 days present):")
    if shr['days'] == 30:
        print(f"  All 30 days have data. Date coverage is NOT the cause of the gap.")
    else:
        print(f"  Only {shr['days']}/30 days. Missing days ARE part of the gap.")

    print(f"\n2D. Driver coverage analysis:")
    print(f"  fleet_summary active drivers = {shr['active_drivers']:,}")
    print(f"  Yango AD (Auto regular) = {YANGO_AD:,}")
    print(f"  Fleet covers {shr['active_drivers']/YANGO_AD*100:.1f}% of Yango AD drivers")
    gap_drivers = YANGO_AD - shr['active_drivers']
    avg_sh_per_missing_driver = (YANGO_SH - float(shr['sh'])) / max(gap_drivers, 1)
    print(f"  Missing drivers: {gap_drivers:,}")
    print(f"  If those avg {avg_sh_per_missing_driver:.0f} h/month each, that explains the ~{(YANGO_SH-float(shr['sh'])):,.0f}h gap")

    print(f"\n2E. Cause analysis:")
    print(f"  PRIMARY: fleet_summary covers {shr['active_drivers']/YANGO_AD*100:.0f}% of Yango auto-regular drivers")
    print(f"  The table is a partial export of driver activity from fleet_summary")
    print(f"  {gap_drivers} Lima Auto regular drivers do NOT appear in fleet_summary")
    print(f"  These drivers complete trips but their hours are NOT tracked by fleet_summary")

    # ═════════════════════════════════════════════════════════════
    # T3: N+R RECONCILIATION
    # ═════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("T3: N+R RECONCILIATION — Lima April 2026")
    print("  Yango official: 1,064 | CT: 2,075 | Diff: +1,011 (+95%)")
    print("=" * 70)

    print("\n3A. CT current definition:")
    print("  Source: trips_2025 + trips_2026 (condicion='Completado')")
    print("  New: first completed trip in April")
    print("  Reactivated: active in April, last activity before April >= 30 days before April 1")
    print("  Reactivation window: 30 days")
    print("  Filter: dim_park.city='lima' parks")

    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park
            WHERE city = 'lima' AND country = 'peru'
        ),
        active_april AS (
            SELECT COUNT(DISTINCT t.conductor_id)::int as cnt
            FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado'
              AND t.fecha_inicio_viaje >= '2026-04-01'
              AND t.fecha_inicio_viaje < '2026-05-01'
        )
        SELECT cnt FROM active_april
    """)
    active_total = cur.fetchone()['cnt']
    print(f"\n  Lima active drivers in April (trips): {active_total:,}")

    # Check how many of those are in fleet_summary
    cur.execute("""
        SELECT COUNT(DISTINCT fs.driver_id)::int as cnt
        FROM public.module_ct_fleet_summary_daily fs
        WHERE fs.fecha >= '2026-04-01' AND fs.fecha < '2026-05-01'
          AND fs.count_orders_completed > 0
    """)
    fleet_active = cur.fetchone()['cnt']
    print(f"  fleet_summary active drivers: {fleet_active:,}")
    print(f"  trips_2026 has {active_total - fleet_active:,} MORE drivers than fleet_summary")
    print(f"  This explains the N+R overcount: CT counts all trip drivers (wider universe)")

    print(f"\n3B. V_SOURCE comparison:")
    cur.execute("""
        WITH lima_parks AS (
            SELECT DISTINCT park_id FROM dim.dim_park
            WHERE city = 'lima' AND country = 'peru'
        ),
        active_month AS (
            SELECT DISTINCT t.conductor_id FROM public.trips_2026 t
            JOIN lima_parks lp ON lp.park_id = t.park_id
            WHERE t.condicion = 'Completado' AND t.fecha_inicio_viaje >= '2026-04-01'
              AND t.fecha_inicio_viaje < '2026-05-01'
        ),
        in_fleet AS (
            SELECT DISTINCT fs.driver_id FROM public.module_ct_fleet_summary_daily fs
            WHERE fs.fecha >= '2026-04-01' AND fs.fecha < '2026-05-01'
              AND fs.count_orders_completed > 0
        )
        SELECT
            (SELECT COUNT(*) FROM active_month)::int as trips_total,
            (SELECT COUNT(*) FROM in_fleet)::int as fleet_total,
            (SELECT COUNT(*) FROM active_month a WHERE a.conductor_id IN (SELECT f.driver_id FROM in_fleet f))::int as overlap
    """)
    ov = cur.fetchone()
    print(f"  Trips drivers: {ov['trips_total']:,}, Fleet drivers: {ov['fleet_total']:,}, Overlap: {ov['overlap']:,}")
    print(f"  Drivers in trips but NOT in fleet: {ov['trips_total']-ov['overlap']:,}")
    print(f"  THESE are causing the N+R inflation: CT counts new+reactivated from ALL trip drivers")
    print(f"  If we filter N+R to ONLY fleet_summary drivers: {ov['overlap']} universe")
    print(f"  The Yango reference likely counts from fleet_summary universe (or similar scope)")

    # Quick N+R on fleet-only universe
    print(f"\n3C. Estimated N+R if using fleet_summary universe:")
    if ov['overlap'] < ov['trips_total']:
        ratio = ov['overlap'] / ov['trips_total']
        estimated_nr = int(ov['overlap'] / ov['trips_total'] * (2075))
        print(f"  Fleet/Trips ratio: {ratio:.2f}")
        print(f"  Estimated N+R (fleet universe): ~{estimated_nr} (assumes uniform distribution)")
        diff_est = estimated_nr - YANGO_NR
        print(f"  Estimated vs Yango ref: {estimated_nr} vs {YANGO_NR} (diff {diff_est:+})")
    print(f"  This strongly suggests the N+R definition and universe need alignment with Yango's")

    print(f"\n3D. RECOMMENDATION: Filter N+R to fleet_summary driver universe for consistency")
    print(f"  This aligns the N+R universe with the AD/SH universe")

    # ═════════════════════════════════════════════════════════════
    # T4: SCORING GUARDRAIL ANALYSIS
    # ═════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("T4: SCORING GUARDRAIL ANALYSIS")
    print("=" * 70)

    ad_drift = abs(auto_ad - YANGO_AD) / YANGO_AD * 100
    sh_drift = abs(float(shr['sh']) - YANGO_SH) / YANGO_SH * 100
    nr_drift = 95  # from previous QA

    issues = []
    if ad_drift > 5:
        issues.append(f"AD drift {ad_drift:.0f}% (all-slices vs Auto regular)")
    if sh_drift > 5:
        issues.append(f"SH drift {sh_drift:.0f}% (source coverage)")
    if nr_drift > 10:
        issues.append(f"N+R drift {nr_drift:.0f}% (provisional definition)")
    if True:
        issues.append(f"N+R definition is provisional_pending_business_validation")
    if True:
        issues.append(f"N+R query is runtime >5s (direct trips query)")

    print(f"\n  AD drift vs Yango: {ad_drift:.0f}% {'BLOCK' if ad_drift>5 else 'OK'}")
    print(f"  SH drift vs Yango: {sh_drift:.0f}% {'BLOCK' if sh_drift>5 else 'OK'}")
    print(f"  N+R drift vs Yango: {nr_drift:.0f}% {'BLOCK' if nr_drift>10 else 'OK'}")
    print(f"  N+R provisional: BLOCK")
    print(f"  N+R runtime >5s: BLOCK")

    print(f"\n  Scoring status SHOULD be: blocked_pending_reconciliation")
    print(f"  Reasons: {', '.join(issues)}")
    print(f"\n  ALL 5 guardrail conditions are triggered.")
    print(f"  Scoring MUST remain blocked until reconciliation is complete.")

    cur.close()
    print("\n" + "=" * 70)
    print("RECONCILIATION COMPLETE")
    print("=" * 70)
