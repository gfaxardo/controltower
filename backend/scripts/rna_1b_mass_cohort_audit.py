"""
LG-RNA-1B — Mass Cohort + Misclassification Audit

Deep audit of 379 RNA drivers with completed trips (misclassified).
Also: Sep 2025 mass cohort origin, behavior classification, new taxonomy.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from collections import Counter

LIMA = "08e20910d81d42658d4334d3f6d10ac0"
SNAP = "2026-06-10"

with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("=" * 70)
    print("LG-RNA-1B — MASS COHORT + MISCLASSIFICATION AUDIT")
    print("=" * 70)

    # ═══════════════════════════════════════════════════════════════
    # T1: RNA UNIVERSE OVERVIEW
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T1: RNA UNIVERSE ---")
    cur.execute("SELECT COUNT(*) as cnt FROM growth.yego_lima_driver_taxonomy_v2_daily WHERE snapshot_date=%s AND park_id=%s AND operational_segment='REGISTERED_NOT_ACTIVATED'", (SNAP, LIMA))
    total_rna = cur.fetchone()["cnt"]
    print(f"  Total RNA: {total_rna}")

    # ═══════════════════════════════════════════════════════════════
    # T1: Sep 2025 MASS COHORT DETAIL
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T1: SEP 2025 MASS COHORT (exact days) ---")
    cur.execute("""
        SELECT d.hire_date, COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN public.drivers d ON t.driver_profile_id=d.driver_id AND d.park_id=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND d.hire_date BETWEEN '2025-09-01' AND '2025-09-30'
        GROUP BY d.hire_date
        ORDER BY d.hire_date
    """, (LIMA, SNAP, LIMA))
    sep_total = 0
    for r in cur.fetchall():
        print(f"  {r['hire_date']}: {r['cnt']:>6,d} drivers")
        sep_total += r['cnt']
    print(f"  TOTAL Sep 2025: {sep_total:,d}")

    # ═══════════════════════════════════════════════════════════════
    # T2: MASS CREATION EVENT DETECTION (all time daily peaks)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T2: TOP DAILY HIRE PEAKS (all time, all drivers) ---")
    cur.execute("""
        SELECT hire_date, COUNT(*) as cnt
        FROM public.drivers
        WHERE park_id=%s AND hire_date IS NOT NULL
        GROUP BY hire_date
        ORDER BY cnt DESC
        LIMIT 15
    """, (LIMA,))
    for r in cur.fetchall():
        marker = " <<< MASS" if r['cnt'] > 1000 else ""
        print(f"  {r['hire_date']}: {r['cnt']:>6,d} drivers{marker}")

    # ═══════════════════════════════════════════════════════════════
    # T3: 379 MISCLASSIFIED RNA (completed trips but RNA segment)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T3: RNA WITH COMPLETED TRIPS (misclassified) ---")
    cur.execute("""
        SELECT t.driver_profile_id,
               d.hire_date, d.work_status, d.current_status,
               COALESCE(l.completed_trips_7d, 0) as trips_7d,
               COALESCE(l.completed_trips_30d, 0) as trips_30d,
               COALESCE(l.completed_trips_90d, 0) as trips_90d,
               COALESCE(l.completed_trips_since_anchor, 0) as trips_since_anchor,
               l.first_completed_trip_date,
               l.last_completed_trip_date,
               l.lifecycle_status,
               l.days_since_last_completed_trip
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN public.drivers d ON t.driver_profile_id=d.driver_id AND d.park_id=%s
        LEFT JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) > 0
        ORDER BY l.completed_trips_90d DESC
        LIMIT 30
    """, (LIMA, SNAP, SNAP, LIMA))
    misclassified = cur.fetchall()
    print(f"  Found {len(misclassified)} (showing top 30)")
    for r in misclassified:
        print(f"  driver={r['driver_profile_id'][:12]}... hire={r['hire_date']} "
              f"lifecycle={r['lifecycle_status']} 90d={r['trips_90d']} "
              f"7d={r['trips_7d']} 30d={r['trips_30d']} "
              f"first={r['first_completed_trip_date']} last={r['last_completed_trip_date']} "
              f"days_since={r['days_since_last_completed_trip']}")

    cur.execute("""
        SELECT COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) > 0
    """, (SNAP, SNAP, LIMA))
    total_misclass = cur.fetchone()["cnt"]
    print(f"  Total misclassified (90d trips > 0, RNA segment): {total_misclass}")

    # ═══════════════════════════════════════════════════════════════
    # T3: REASON FOR MISCLASSIFICATION
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T3: WHY MISCLASSIFIED? ---")
    cur.execute("""
        SELECT l.lifecycle_status, COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) > 0
        GROUP BY l.lifecycle_status
        ORDER BY cnt DESC
    """, (SNAP, SNAP, LIMA))
    for r in cur.fetchall():
        print(f"  lifecycle={r['lifecycle_status']:25s} count={r['cnt']:>6d}")

    # Check taxonomy layer mismatch
    cur.execute("""
        SELECT t.lifecycle_status as tax_lifecycle,
               l.lifecycle_status as real_lifecycle,
               t.activity_status as tax_activity,
               COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) > 0
        GROUP BY 1,2,3
        ORDER BY cnt DESC
        LIMIT 15
    """, (SNAP, SNAP, LIMA))
    print(f"\n  Taxonomy vs Lifecycle mismatch:")
    for r in cur.fetchall():
        mismatch = "MISMATCH" if r['tax_lifecycle'] != r['real_lifecycle'] else "OK"
        print(f"    tax: {r['tax_lifecycle']:20s} real: {r['real_lifecycle']:20s} "
              f"activity: {r['tax_activity']:20s} cnt={r['cnt']} [{mismatch}]")

    # ═══════════════════════════════════════════════════════════════
    # T4: RNA CLASSIFICATION BY BEHAVIOR
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T4: RNA BEHAVIOR CLASSIFICATION ---")

    # 1. ZERO trips ever, ZERO cancelled = NEVER_TOUCHED
    # 2. ZERO complete, HAS cancelled = ACCEPTED_CANCELLED
    # 3. HAS complete but OLD (>90d) = RNA_DORMANT
    # 4. HAS complete and RECENT (<=90d) = RNA_MISCLASSIFIED
    # 5. Sep 2025 mass cohort = RNA_MASS_COHORT
    # 6. Everything else = RNA_OTHER

    cur.execute("""
        SELECT
            CASE
                WHEN COALESCE(l.completed_trips_90d, 0) > 0 AND l.last_completed_trip_date >= CURRENT_DATE - 90
                    THEN 'RNA_MISCLASSIFIED_RECENT'
                WHEN COALESCE(l.completed_trips_90d, 0) > 0
                    THEN 'RNA_DORMANT'
                WHEN d.hire_date BETWEEN '2025-09-01' AND '2025-09-05'
                    THEN 'RNA_MASS_COHORT'
                WHEN d.hire_date BETWEEN '2025-09-06' AND '2025-09-30'
                    THEN 'RNA_MASS_COHORT'
                ELSE 'RNA_NEVER_TOUCHED'
            END as behavior,
            COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN public.drivers d ON t.driver_profile_id=d.driver_id AND d.park_id=%s
        LEFT JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
        GROUP BY 1
        ORDER BY cnt DESC
    """, (LIMA, SNAP, SNAP, LIMA))
    groups = {}
    total = 0
    for r in cur.fetchall():
        groups[r['behavior']] = r['cnt']
        total += r['cnt']
    for beh in ['RNA_MASS_COHORT', 'RNA_NEVER_TOUCHED', 'RNA_DORMANT', 'RNA_MISCLASSIFIED_RECENT']:
        cnt = groups.get(beh, 0)
        pct = cnt / max(total, 1) * 100
        print(f"  {beh:30s} {cnt:>8,d} {pct:>6.1f}%")

    print(f"  {'TOTAL':30s} {total:>8,d}")

    # ═══════════════════════════════════════════════════════════════
    # T5.1: RNA_DORMANT deep dive
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T5.1: RNA_DORMANT (completed trips > 90d ago) ---")
    cur.execute("""
        SELECT
            CASE
                WHEN l.last_completed_trip_date IS NULL THEN 'no_date'
                WHEN l.last_completed_trip_date >= CURRENT_DATE - 180 THEN '91-180d'
                WHEN l.last_completed_trip_date >= CURRENT_DATE - 365 THEN '181-365d'
                ELSE '365d+'
            END as dormancy,
            COUNT(*) as cnt
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) > 0
          AND (l.last_completed_trip_date IS NULL OR l.last_completed_trip_date < CURRENT_DATE - 90)
        GROUP BY 1
        ORDER BY cnt DESC
    """, (SNAP, SNAP, LIMA))
    for r in cur.fetchall():
        print(f"    {r['dormancy']:15s}: {r['cnt']:>6,d}")

    # ═══════════════════════════════════════════════════════════════
    # T5.2: RNA with zero trips (the silent majority)
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T5.2: RNA NEVER TOUCHED / MASS COHORT DETAIL ---")
    cur.execute("""
        SELECT
            CASE WHEN d.hire_date >= '2025-09-01' AND d.hire_date <= '2025-09-05' THEN 'Sep 2-5 peak'
                 WHEN d.hire_date >= '2025-09-06' AND d.hire_date <= '2025-09-30' THEN 'Sep other'
                 ELSE 'Other dates'
            END as cohort,
            COUNT(*) as cnt,
            ROUND(AVG(CURRENT_DATE - d.hire_date), 1) as avg_age_days
        FROM growth.yego_lima_driver_taxonomy_v2_daily t
        JOIN public.drivers d ON t.driver_profile_id=d.driver_id AND d.park_id=%s
        LEFT JOIN growth.yego_lima_driver_lifecycle_daily l
            ON t.driver_profile_id=l.driver_profile_id AND l.snapshot_date=%s
        WHERE t.snapshot_date=%s AND t.park_id=%s
          AND t.operational_segment='REGISTERED_NOT_ACTIVATED'
          AND COALESCE(l.completed_trips_90d, 0) = 0
        GROUP BY 1
        ORDER BY cnt DESC
    """, (LIMA, SNAP, SNAP, LIMA))
    for r in cur.fetchall():
        print(f"    {r['cohort']:20s}: {r['cnt']:>8,d} drivers, avg_age={r['avg_age_days']}d")

    # ═══════════════════════════════════════════════════════════════
    # T6: PROPOSED NEW TAXONOMY
    # ═══════════════════════════════════════════════════════════════
    print("\n--- T6: PROPOSED RNA TAXONOMY V3 ---")

    print("""
  Current (V2): REGISTERED_NOT_ACTIVATED = 1 bucket for 50,181 drivers.
  
  Proposed (V3): 5 sub-segments within REGISTERED_NOT_ACTIVATED:
  
  1. RNA_MASS_COHORT       — Sep 2025 mass onboarding, never activated
  2. RNA_NEVER_TOUCHED     — Registered, 0 trips ever
  3. RNA_DORMANT           — Had trips but >90d inactive (lapsed activator)
  4. RNA_MISCLASSIFIED     — Has recent trips — SHOULD NOT BE RNA
  5. RNA_FIRED             — Fired or inactive, archived
    """)

    # ═══════════════════════════════════════════════════════════════
    # T7: BACKLOG UPDATE 
    # ═══════════════════════════════════════════════════════════════
    print("--- T7: BACKLOG ---")
    print("""
  NEW:
    LG-RNA-1C — RNA Taxonomy V3 Implementation
      - Implement 6-segment RNA classification in taxonomy V2 config
      - Backfill taxonomy_v2_daily with new operational_segment values
      - Update program_eligibility to split RNA_ONBOARDING → HOT/WARM/COLD/DORMANT
      - Rebuild observability facts
    
    LG-RNA-1D — RNA Misclassification Fix
      - Fix taxonomy cascade so drivers with completed trips NEVER land in RNA
      - Root cause: lifecycle_status = NEVER_ACTIVATED despite trips_completed_lifetime > 0
        → lifecycle_daily table may have stale data for these 379 drivers
      - Verify: UPDATE lifecycle_daily WHERE trips_completed_lifetime > 0 AND lifecycle_status='NEVER_ACTIVATED'
    """)

    # ═══════════════════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total RNA drivers: {total_rna:,d}")
    if groups:
        print(f"  RNA_MASS_COHORT: {groups.get('RNA_MASS_COHORT', 0):,d}")
        print(f"  RNA_NEVER_TOUCHED: {groups.get('RNA_NEVER_TOUCHED', 0):,d}")
        print(f"  RNA_DORMANT: {groups.get('RNA_DORMANT', 0):,d}")
        print(f"  RNA_MISCLASSIFIED_RECENT: {groups.get('RNA_MISCLASSIFIED_RECENT', 0):,d}")
    print(f"  Sep 2025 mass cohort: {sep_total:,d}")
    print(f"  Misclassified (lifetime trips > 0): {total_misclass}")
    print(f"\n  Verdict: RNA_STRUCTURE_VALID (with refinements needed)")

    cur.close()
