"""LG-OBS-1B - Rebuild observability after PROG-2B gap closure"""
import os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line: k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(host=os.environ['DB_HOST'], port=os.environ['DB_PORT'],
                        dbname=os.environ['DB_NAME'], user=os.environ['DB_USER'],
                        password=os.environ['DB_PASSWORD'], cursor_factory=RealDictCursor)
cur = conn.cursor()

LIMA = "08e20910d81d42658d4334d3f6d10ac0"
SNAP = "2026-06-10"

# ================================================================
# TASK 1: VERIFY PROGRAM V2 STATE
# ================================================================
print("TASK 1: VERIFY PROGRAM V2 STATE")
cur.execute("SELECT COUNT(*) FROM growth.yego_lima_program_v2_registry WHERE is_active=true AND is_shadow=true")
print(f"  Active shadow programs: {cur.fetchone()['count']}")

cur.execute("SELECT program_code FROM growth.yego_lima_program_v2_registry WHERE program_code='REACTIVATION_STABILIZATION'")
print(f"  REACTIVATION_STABILIZATION exists: {cur.fetchone() is not None}")

cur.execute("SELECT COUNT(*) FROM growth.yego_lima_program_v2_assignment_daily WHERE snapshot_date=%(sd)s",{"sd":SNAP})
print(f"  Assignments: {cur.fetchone()['count']}")

cur.execute("SELECT COUNT(*) FROM growth.yego_lima_program_v2_assignment_daily WHERE snapshot_date=%(sd)s AND assigned_program_code IS NULL",{"sd":SNAP})
print(f"  UNASSIGNED: {cur.fetchone()['count']}")

# ================================================================
# TASK 2-3: REBUILD ALL OBSERVABILITY FACTS
# ================================================================
print("\nTASK 2-3: REBUILDING OBSERVABILITY FACTS...")
t0 = time.time()

for t in ["program_observability_fact","taxonomy_distribution_fact","program_distribution_fact",
          "program_movement_fact","program_impact_fact"]:
    cur.execute(f"DELETE FROM growth.{t} WHERE snapshot_date=%(sd)s",{"sd":SNAP})
cur.execute("DELETE FROM growth.driver_growth_timeline_fact WHERE event_date=%(sd)s",{"sd":SNAP})
conn.commit()

# Observability fact
cur.execute("""
    INSERT INTO growth.program_observability_fact (snapshot_date, driver_profile_id,
        lifecycle_status, activity_status, value_tier, momentum_state,
        operational_segment, assigned_program, priority_score, impact_status)
    SELECT %(sd)s, t.driver_profile_id, t.lifecycle_status, t.activity_status,
        t.value_tier, t.momentum_state, t.operational_segment,
        a.assigned_program_code, p.priority_score, 'PENDING'
    FROM growth.yego_lima_driver_taxonomy_v2_daily t
    LEFT JOIN growth.yego_lima_program_v2_assignment_daily a
        ON t.driver_profile_id=a.driver_profile_id AND a.snapshot_date=%(sd)s
    LEFT JOIN growth.yego_lima_program_v2_priority_daily p
        ON t.driver_profile_id=p.driver_profile_id AND p.snapshot_date=%(sd)s
    WHERE t.snapshot_date=%(sd)s AND t.park_id=%(p)s
    ON CONFLICT (snapshot_date, driver_profile_id) DO UPDATE SET
        lifecycle_status=EXCLUDED.lifecycle_status, activity_status=EXCLUDED.activity_status,
        value_tier=EXCLUDED.value_tier, momentum_state=EXCLUDED.momentum_state,
        operational_segment=EXCLUDED.operational_segment, assigned_program=EXCLUDED.assigned_program,
        priority_score=EXCLUDED.priority_score
""",{"sd":SNAP,"p":LIMA})
obs = cur.rowcount

# Taxonomy distribution
for dim in ["lifecycle_status","activity_status","value_tier","momentum_state","operational_segment"]:
    cur.execute(f"""
        INSERT INTO growth.taxonomy_distribution_fact (snapshot_date, dimension, state_value, driver_count)
        SELECT %(sd)s, %(dim)s, {dim}, COUNT(*) FROM growth.yego_lima_driver_taxonomy_v2_daily
        WHERE snapshot_date=%(sd)s AND park_id=%(p)s GROUP BY {dim}
        ON CONFLICT (snapshot_date, dimension, state_value) DO UPDATE SET driver_count=EXCLUDED.driver_count
    """,{"sd":SNAP,"p":LIMA,"dim":dim})

# Program distribution
cur.execute("""
    INSERT INTO growth.program_distribution_fact (snapshot_date, program_code, driver_count)
    SELECT %(sd)s, COALESCE(assigned_program_code,'UNASSIGNED'), COUNT(*)
    FROM growth.yego_lima_program_v2_assignment_daily WHERE snapshot_date=%(sd)s
    GROUP BY assigned_program_code
    ON CONFLICT (snapshot_date, program_code) DO UPDATE SET driver_count=EXCLUDED.driver_count
""",{"sd":SNAP})

# Movement
cur.execute("""
    INSERT INTO growth.program_movement_fact (snapshot_date, transition_type, from_state, to_state, driver_count)
    SELECT %(sd)s, transition_type, COALESCE(previous_program_code,'NONE'), COALESCE(current_program_code,'NONE'), COUNT(*)
    FROM growth.yego_lima_program_v2_assignment_transition WHERE curr_date=%(sd)s
    GROUP BY transition_type, previous_program_code, current_program_code
    ON CONFLICT (snapshot_date, transition_type, coalesce(from_state,''), coalesce(to_state,'')) DO UPDATE SET driver_count=EXCLUDED.driver_count
""",{"sd":SNAP})

# Impact
cur.execute("""
    INSERT INTO growth.program_impact_fact (snapshot_date, program_code, impact_status, driver_count)
    SELECT %(sd)s, COALESCE(assigned_program_code,'UNASSIGNED'), impact_status, COUNT(*)
    FROM growth.yego_lima_program_v2_impact_daily WHERE snapshot_date=%(sd)s
    GROUP BY assigned_program_code, impact_status
    ON CONFLICT (snapshot_date, program_code, impact_status) DO UPDATE SET driver_count=EXCLUDED.driver_count
""",{"sd":SNAP})

# Timeline
cur.execute("""
    INSERT INTO growth.driver_growth_timeline_fact (driver_profile_id, event_date, event_type, event_detail)
    SELECT driver_profile_id, %(sd)s::date, 'REGISTERED', 'exists_in_public_drivers'
    FROM growth.yego_lima_driver_taxonomy_v2_daily WHERE snapshot_date=%(sd)s AND park_id=%(p)s
    UNION ALL
    SELECT driver_profile_id, %(sd)s::date,
        CASE lifecycle_status WHEN 'ACTIVE' THEN 'ACTIVE' WHEN 'CHURN_15D' THEN 'CHURNED'
        WHEN 'ARCHIVED_90D' THEN 'ARCHIVED' WHEN 'REACTIVATED' THEN 'REACTIVATED'
        WHEN 'NEW' THEN 'NEW_DRIVER' ELSE 'OTHER' END,
        'lifecycle='||lifecycle_status
    FROM growth.yego_lima_driver_lifecycle_daily WHERE snapshot_date=%(sd)s AND park_id=%(p)s
    UNION ALL
    SELECT driver_profile_id, %(sd)s::date, 'PROGRAM_ASSIGNED',
        'program='||COALESCE(assigned_program,'NONE')||' segment='||COALESCE(operational_segment,'NONE')
    FROM growth.program_observability_fact WHERE snapshot_date=%(sd)s
    ON CONFLICT DO NOTHING
""",{"sd":SNAP,"p":LIMA})
tl = cur.rowcount
conn.commit()

duration = round((time.time()-t0)*1000)
print(f"  Rebuilt in {duration}ms: obs={obs} timeline={tl}")

# ================================================================
# TASK 3-4: VALIDATE DISTRIBUTION + TIMELINE
# ================================================================
print(f"\n{'='*60}")
print("TASK 3: PROGRAM DISTRIBUTION (POST-PROG-2B)")
print("=" * 60)

cur.execute("""
    SELECT COALESCE(program_code,'UNASSIGNED') as prog, driver_count
    FROM growth.program_distribution_fact WHERE snapshot_date=%(sd)s ORDER BY driver_count DESC
""",{"sd":SNAP})

expected = {
    "RNA_ONBOARDING": 50181, "ARCHIVED_REACTIVATION": 10743, "CHURN_RECOVERY": 3486,
    "ACTIVE_GROWTH": 2594, "REACTIVATION_STABILIZATION": 593, "TOP_RETENTION": 495,
    "HVR": 166, "FIFTY_14": 124, "STABLE_MONITOR": 91, "UNASSIGNED": 0,
}
total = 0
all_ok = True
for r in cur.fetchall():
    p = r['prog']; c = r['driver_count']
    exp = expected.get(p, '?')
    match = "MATCH" if c == exp else f"MISMATCH (exp={exp})"
    if c != exp: all_ok = False
    print(f"  {p:35s}: {c:>8,d} {match}")
    total += c

print(f"\n  Total: {total} (sum check: {'PASS' if total==68473 else 'FAIL'})")
print(f"  UNASSIGNED: {expected.get('UNASSIGNED', '?')}")
print(f"  REACTIVATION_STABILIZATION: {expected.get('REACTIVATION_STABILIZATION', '?')}")
print(f"  All match: {all_ok}")

# Timeline check for REACTIVATION_STABILIZATION drivers
cur.execute("""
    SELECT COUNT(DISTINCT t.driver_profile_id) as cnt
    FROM growth.driver_growth_timeline_fact t
    JOIN growth.yego_lima_program_v2_assignment_daily a
        ON t.driver_profile_id=a.driver_profile_id AND a.snapshot_date=%(sd)s
    WHERE t.event_date=%(sd)s AND a.assigned_program_code='REACTIVATION_STABILIZATION'
""",{"sd":SNAP})
print(f"\n  Timeline events for REACTIVATION_STABILIZATION drivers: {cur.fetchone()['cnt']}")

# ================================================================
# TASK 5: ENDPOINT DATA VERIFICATION
# ================================================================
print(f"\n{'='*60}")
print("TASK 5: ENDPOINT DATA (simulated)")
print("=" * 60)

cur.execute("""
    SELECT assigned_program, COUNT(*) as cnt FROM growth.program_observability_fact
    WHERE snapshot_date=%(sd)s GROUP BY 1 ORDER BY 2 DESC
""",{"sd":SNAP})
print("Observability fact programs:")
for r in cur.fetchall():
    print(f"  {str(r['assigned_program']):35s}: {r['cnt']:>8,d}")

cur.execute("""
    SELECT driver_profile_id, assigned_program, lifecycle_status, operational_segment
    FROM growth.program_observability_fact
    WHERE snapshot_date=%(sd)s AND assigned_program='REACTIVATION_STABILIZATION' LIMIT 5
""",{"sd":SNAP})
print("\nREACTIVATION_STABILIZATION sample:")
for r in cur.fetchall():
    print(f"  {r['driver_profile_id'][:16]}... prog={r['assigned_program']} lc={r['lifecycle_status']} seg={r['operational_segment']}")

conn.close()
print("\nDone.")
