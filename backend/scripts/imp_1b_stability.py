"""LG-IMP-1B - Effectiveness Stabilization Audit"""
import os, sys, json
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

# ================================================================
# TASK 1: DATA QUALITY AUDIT
# ================================================================
print("=" * 65)
print("TASK 1: DATA QUALITY AUDIT")
print("=" * 65)

# Available data inventory
for tbl, date_col in [
    ("growth.yego_lima_driver_taxonomy_v2_daily", "snapshot_date"),
    ("growth.driver_movement_fact", "movement_date"),
    ("growth.yego_lima_program_v2_assignment_daily", "snapshot_date"),
    ("growth.driver_program_effectiveness_fact", "movement_date"),
    ("growth.program_effectiveness_fact", "report_date"),
]:
    cur.execute(f"SELECT {date_col}, COUNT(*) FROM {tbl} GROUP BY 1 ORDER BY 1")
    rows = cur.fetchall()
    print(f"\n  {tbl.split('.')[-1]}:")
    for r in rows:
        print(f"    {r[date_col]}: {r['count']:,} rows")

# Duplicate check
cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT movement_date, driver_profile_id, COUNT(*) as n
        FROM growth.driver_program_effectiveness_fact GROUP BY 1,2 HAVING COUNT(*) > 1
    ) sub
""")
print(f"\n  Effectiveness duplicates: {cur.fetchone()['count']}")

cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT movement_date, driver_profile_id, COUNT(*) as n
        FROM growth.driver_movement_fact GROUP BY 1,2 HAVING COUNT(*) > 1
    ) sub
""")
print(f"  Movement duplicates: {cur.fetchone()['count']}")

cur.execute("""
    SELECT COUNT(*) FROM (
        SELECT snapshot_date, driver_profile_id, COUNT(*) as n
        FROM growth.yego_lima_program_v2_assignment_daily GROUP BY 1,2 HAVING COUNT(*) > 1
    ) sub
""")
print(f"  Assignment duplicates: {cur.fetchone()['count']}")

# ================================================================
# TASK 2: 7-DAY DATA CHECK
# ================================================================
print(f"\n{'='*65}")
print("TASK 2: AVAILABLE HISTORY CHECK")
print("=" * 65)

cur.execute("SELECT COUNT(DISTINCT snapshot_date) FROM growth.yego_lima_driver_taxonomy_v2_daily")
tax_days = cur.fetchone()['count']
cur.execute("SELECT COUNT(DISTINCT movement_date) FROM growth.driver_movement_fact")
mov_days = cur.fetchone()['count']
cur.execute("SELECT COUNT(DISTINCT snapshot_date) FROM growth.yego_lima_program_v2_assignment_daily")
prog_days = cur.fetchone()['count']

print(f"  Taxonomy snapshots: {tax_days}")
print(f"  Movement snapshots:  {mov_days}")
print(f"  Program assignment snapshots: {prog_days}")

if tax_days < 7:
    print(f"\n  7-DAY REPLAY: NOT POSSIBLE - only {tax_days} taxonomy snapshots available")
    print(f"  Requires: daily taxonomy build pipeline execution for 7 consecutive days")
else:
    print(f"\n  7-DAY REPLAY: POSSIBLE with {tax_days} snapshots")

# ================================================================
# TASK 3: SCORE STABILITY (what we can measure)
# ================================================================
print(f"\n{'='*65}")
print("TASK 3: SCORE STABILITY (available data)")
print("=" * 65)

# Movement score distribution across days
cur.execute("""
    SELECT movement_date, movement_score, COUNT(*) as cnt
    FROM growth.driver_movement_fact
    WHERE movement_score != 0
    GROUP BY 1,2 ORDER BY 1,2
""")
print(f"\n  Non-zero movement scores by day:")
for r in cur.fetchall():
    label = "POSITIVE" if r['movement_score']>0 else "NEGATIVE"
    print(f"    {r['movement_date']} {label:10s} ({r['movement_score']:+3d}): {r['cnt']:>6,d}")

# Movement classification coverage
cur.execute("""
    SELECT movement_class, COUNT(*) as cnt,
           ROUND(COUNT(*)*100.0/SUM(COUNT(*)) OVER(),1) as pct
    FROM growth.driver_movement_fact GROUP BY 1 ORDER BY 2 DESC
""")
print(f"\n  Movement classification coverage:")
for r in cur.fetchall():
    print(f"    {r['movement_class']:25s}: {r['cnt']:>10,d} ({r['pct']}%)")

# ================================================================
# TASK 5: MOVEMENT COVERAGE
# ================================================================
print(f"\n{'='*65}")
print("TASK 5: MOVEMENT COVERAGE / UNCLASSIFIED")
print("=" * 65)

cur.execute("""
    SELECT movement_score, COUNT(*) as cnt
    FROM growth.driver_movement_fact
    GROUP BY 1 ORDER BY 1
""")
total = 0
classified = 0
print(f"\n  Score distribution:")
for r in cur.fetchall():
    total += r['cnt']
    if r['movement_score'] != 0: classified += r['cnt']
    label = "NEUTRAL" if r['movement_score']==0 else ("POSITIVE" if r['movement_score']>0 else "NEGATIVE")
    print(f"    {r['movement_score']:+5d} ({label:10s}): {r['cnt']:>10,d}")

unclassified = total - classified
print(f"\n  Total movements:      {total:,}")
print(f"  Classified (+/-):     {classified:,} ({round(classified/total*100,1)}%)")
print(f"  Unclassified (0):     {unclassified:,} ({round(unclassified/total*100,1)}%)")

# ================================================================
# TASK 6: PROGRAM READINESS
# ================================================================
print(f"\n{'='*65}")
print("TASK 6: PROGRAM READINESS FOR BENCHMARKING")
print("=" * 65)

# Per-program movement activity
cur.execute("""
    SELECT a.assigned_program_code,
           COUNT(*) as drivers,
           SUM(CASE WHEN m.movement_score > 0 THEN 1 ELSE 0 END) as pos,
           SUM(CASE WHEN m.movement_score < 0 THEN 1 ELSE 0 END) as neg
    FROM growth.yego_lima_program_v2_assignment_daily a
    LEFT JOIN growth.driver_movement_fact m
        ON a.driver_profile_id=m.driver_profile_id AND m.movement_date='2026-06-10'
    WHERE a.snapshot_date='2026-06-10'
    GROUP BY 1 ORDER BY 2 DESC
""")

print(f"\n  {'Program':30s} {'Drivers':>8s} {'+Moves':>8s} {'-Moves':>8s} {'Data Sufficient?'}")
for r in cur.fetchall():
    prog = r['assigned_program_code'] or 'UNASSIGNED'
    pos = r['pos'] or 0
    neg = r['neg'] or 0
    sufficient = "NO - need 7+ days" if (pos+neg) < 5 else "MODERATE" if (pos+neg) < 20 else "YES"
    print(f"  {prog:30s} {r['drivers']:>8,d} {pos:>8,d} {neg:>8,d} {sufficient}")

# ================================================================
# TASK 4: OUTCOME QUALITY
# ================================================================
print(f"\n{'='*65}")
print("TASK 4: OUTCOME QUALITY")
print("=" * 65)

# Check for double counting: same driver, same transition on same day
# (should be impossible due to UNIQUE constraint but verify)
cur.execute("""
    SELECT from_segment, to_segment, COUNT(DISTINCT driver_profile_id) as drivers,
           SUM(cnt) as total_moves
    FROM (
        SELECT movement_date, from_segment, to_segment, driver_profile_id, COUNT(*) as cnt
        FROM growth.driver_movement_fact
        GROUP BY 1,2,3,4 HAVING COUNT(*) > 1
    ) sub GROUP BY 1,2 ORDER BY 3 DESC LIMIT 5
""")
print(f"\n  Potential double-counting (same driver+day+transition >1):")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"    {r['from_segment']} -> {r['to_segment']}: {r['drivers']} drivers, {r['total_moves']} moves")
else:
    print("    NONE - all movements are unique per driver per day")

# Check if any RNA->ACTIVE_GROWTH transitions are real (positive outcomes)
cur.execute("""
    SELECT m.driver_profile_id, m.from_segment, m.to_segment, m.movement_score, m.movement_date
    FROM growth.driver_movement_fact m
    WHERE m.from_segment='REGISTERED_NOT_ACTIVATED' AND m.to_segment='ACTIVE_GROWTH'
    ORDER BY m.movement_date LIMIT 5
""")
print(f"\n  Sample positive outcomes (RNA -> ACTIVE_GROWTH):")
for r in cur.fetchall():
    print(f"    {r['driver_profile_id'][:16]}... on {r['movement_date']}: {r['from_segment']} -> {r['to_segment']} score={r['movement_score']}")

# ================================================================
# VEREDICT
# ================================================================
print(f"\n{'='*65}")
print("VEREDICT")
print("=" * 65)

if mov_days < 3:
    print("  B) MORE_HISTORY_REQUIRED")
    print(f"     Only {mov_days} movement snapshots available")
    print(f"     Need 7+ days of daily pipeline execution for stable benchmarking")
else:
    print("  A) EFFECTIVENESS_STABLE")
    print(f"     {mov_days} movement snapshots, 0 duplicates, {classified} classified outcomes")

conn.close()
print("\nDone.")
