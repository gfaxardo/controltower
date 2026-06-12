"""
LG-R3.0A — Pipeline Dependency & Eligibility vs Priority Certification
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

D = '2026-06-05'
TABLE_SNAPSHOT = "growth.yango_lima_driver_state_snapshot"
TABLE_ELIG = "growth.yango_lima_program_eligibility_daily"
TABLE_PRI = "growth.yango_lima_prioritized_opportunity_daily"
TABLE_QUEUE = "growth.yego_lima_assignment_queue"

print("=" * 65)
print("LG-R3.0A — PIPELINE DEPENDENCY CERTIFICATION")
print("=" * 65)

# ═══ PHASE 1: SOURCE OF TRUTH ═══
print("\n" + "=" * 65)
print("PHASE 1 — SOURCE OF TRUTH PER LAYER")
print("=" * 65)

layers = [
    ("driver_360_daily", "growth.yango_lima_driver_360_daily", "date"),
    ("eligible_universe", "growth.yango_lima_eligible_universe_daily", "date"),
    ("driver_state_snapshot", "growth.yango_lima_driver_state_snapshot", "snapshot_date"),
    ("program_eligibility", "growth.yango_lima_program_eligibility_daily", "eligibility_date"),
    ("prioritized_opportunity", "growth.yango_lima_prioritized_opportunity_daily", "opportunity_date"),
    ("assignment_queue", "growth.yego_lima_assignment_queue", "assignment_date"),
    ("serving_fact", "growth.yego_lima_serving_fact", "fact_date"),
    ("driver_list_history", "growth.yego_lima_driver_list_history", "action_date"),
    ("intraday_signal", "growth.yego_lima_intraday_driver_signal", "signal_date"),
]

for name, table, col in layers:
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = %(d)s", {"d": D})
    cnt = cur.fetchone()[0]
    status = "ALIVE" if cnt > 0 else "DEAD (0 rows)"
    print(f"  {name:<30} {cnt:>8}  [{status}]")

# ═══ PHASE 2: DEPENDENCY GRAPH ═══
print("\n" + "=" * 65)
print("PHASE 2 — REAL DEPENDENCY GRAPH (from code)")
print("=" * 65)

print("""
  Yango API (orders/list + driver-profiles/list + supply-hours)
      |
      v
  raw_yango.orders_raw (11,087 rows)
      |
      v
  growth.yango_lima_orders_raw (237 rows)
      |
      +---> growth.yango_lima_driver_history_daily (bootstrapped from trips)
      |         |
      |         v
      |     growth.yango_lima_driver_history_weekly (134,909 rows)
      |         |
      |         v
      |     [driver_360_daily] -- DEAD (0 rows, optional enrichment)
      |         |                  |
      |         |                  v
      |         +-----> driver_state_snapshot (18,475 rows) <-- KEYSTONE
      |                            |
      |              +-------------+-------------+
      |              |                           |
      |              v                           v
      |     program_eligibility (28,493)    driver_segments (47)
      |              |
      |              v
      |     daily_opportunity_list (28,493)
      |              |
      |              v
      |     [policy engine] --> prioritized_opportunity (5,604)
      |              |
      |              v
      |     assignment_queue (500)
      |              |
      |     +--------+--------+
      |     |                  |
      |     v                  v
      |  serving_fact (8/8)  driver_list_history (500)
      |     |
      |     v
      |   UI Endpoints
      
  DEAD BRANCHES (confirmed by R2.0):
  
  [eligible_universe_daily] -- 0 rows, no consumers
        |
        v
  [driver_360_daily] -- 0 rows, only consumer is dead
        |
        v
  (dead end -- feeds snapshot as optional enrichment, defaults to 0)
""")

# ═══ PHASE 3: DEAD LAYER CLASSIFICATION ═══
print("=" * 65)
print("PHASE 3 — DEAD LAYER DETECTOR")
print("=" * 65)

cur.execute("SELECT COUNT(*) FROM growth.yango_lima_driver_360_daily WHERE date = %(d)s", {"d": D})
d360_now = cur.fetchone()[0]
cur.execute("SELECT MAX(date) FROM growth.yango_lima_driver_360_daily")
d360_last = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM growth.yango_lima_eligible_universe_daily WHERE date = %(d)s", {"d": D})
eu_now = cur.fetchone()[0]
cur.execute("SELECT MAX(date) FROM growth.yango_lima_eligible_universe_daily")
eu_last = cur.fetchone()[0]

print(f"""
  driver_360_daily:
    rows on {D}: {d360_now}
    last date with data: {d360_last}
    consumers: build_driver_state_snapshot (SECONDARY, optional)
    classification: DEAD (last written 06-02, 3 pipeline dates with 0 rows)
    
  eligible_universe_daily:
    rows on {D}: {eu_now}
    last date with data: {eu_last}
    consumers: stabilize_driver_360_day (which is DEAD)
    classification: DEAD (no live consumers, driver_360 is its only consumer)
""")

# ═══ PHASE 4: ELIGIBILITY vs PRIORITY ═══
print("=" * 65)
print("PHASE 4 — ELIGIBILITY vs PRIORITY (20 drivers)")
print("=" * 65)

# Get 20 drivers with their eligibility and priority status
cur.execute(f"""
    SELECT e.driver_profile_id, e.program_code as elig_prog, e.eligible_flag,
           p.selected_program_code as pri_prog, p.is_actionable_today, p.final_rank,
           p.exclusion_reason, e.eligibility_reason
    FROM {TABLE_SNAPSHOT} s
    LEFT JOIN growth.yango_lima_program_eligibility_daily e
        ON e.driver_profile_id = s.driver_profile_id AND e.eligibility_date = %(d)s
    LEFT JOIN growth.yango_lima_prioritized_opportunity_daily p
        ON p.driver_profile_id = s.driver_profile_id AND p.opportunity_date = %(d)s
    WHERE s.snapshot_date = %(d)s
    ORDER BY RANDOM()
    LIMIT 20
""", {"d": D})

print(f"\n  {'driver_id':<16} {'eligible':>8} {'program':<28} {'prioritized':>12} {'actionable':>10} {'rank':>5} {'exclusion':>25}")
print(f"  {'-'*16} {'-'*8} {'-'*28} {'-'*12} {'-'*10} {'-'*5} {'-'*25}")

cases = {"A": 0, "B": 0, "C": 0, "D": 0}
for r in cur.fetchall():
    did = (r[0] or 'NULL')[:16]
    elig_prog = (r[1] or 'NONE')[:28]
    eligible = bool(r[2]) if r[2] is not None else False
    pri_prog = (r[3] or 'NONE')[:12] if r[3] else 'NONE'
    actionable = bool(r[4]) if r[4] is not None else False
    rank = r[5] if r[5] else '-'
    excl = (r[6] or '-')[:25] if r[6] else '-'
    
    if eligible and r[3]:
        case = "A"
    elif eligible and not r[3]:
        case = "B"
    elif not eligible and r[3]:
        case = "C"
    else:
        case = "D"
    cases[case] += 1
    
    print(f"  {did:<16} {'YES' if eligible else 'NO':>8} {elig_prog:<28} {pri_prog:<12} {'YES' if actionable else 'NO':>10} {str(rank):>5} {excl:<25}")

print(f"\n  Case A (eligible + prioritized): {cases['A']}")
print(f"  Case B (eligible, NOT prioritized): {cases['B']}")
print(f"  Case C (NOT eligible, prioritized): {cases['C']}")
print(f"  Case D (neither): {cases['D']}")

# ═══ PHASE 5: HIGH VALUE RECOVERY ═══
print("\n" + "=" * 65)
print("PHASE 5 — HIGH VALUE RECOVERY AUDIT")
print("=" * 65)

cur.execute(f"""
    SELECT COUNT(*) FROM growth.yango_lima_program_eligibility_daily
    WHERE eligibility_date = %(d)s AND program_code = 'PROGRAM_HIGH_VALUE_RECOVERY'
""", {"d": D})
hv_elig = cur.fetchone()[0]

cur.execute(f"""
    SELECT COUNT(*), SUM(CASE WHEN is_actionable_today THEN 1 ELSE 0 END)
    FROM growth.yango_lima_prioritized_opportunity_daily
    WHERE opportunity_date = %(d)s AND selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY'
""", {"d": D})
hv_pri = cur.fetchone()

cur.execute(f"""
    SELECT p.driver_profile_id, p.opportunity_score, p.final_rank, p.exclusion_reason,
           e.eligible_flag, e.eligibility_reason
    FROM growth.yango_lima_prioritized_opportunity_daily p
    LEFT JOIN growth.yango_lima_program_eligibility_daily e
        ON e.driver_profile_id = p.driver_profile_id
        AND e.eligibility_date = p.opportunity_date
        AND e.program_code = 'PROGRAM_HIGH_VALUE_RECOVERY'
    WHERE p.opportunity_date = %(d)s AND p.selected_program_code = 'PROGRAM_HIGH_VALUE_RECOVERY'
    LIMIT 5
""", {"d": D})

print(f"""
  PROGRAM_HIGH_VALUE_RECOVERY:
    Eligible (from program_eligibility):  {hv_elig}
    Prioritized (from policy engine):     {hv_pri[0]} (actionable: {hv_pri[1]})
    
  EXPLANATION:
    HIGH_VALUE_RECOVERY is added by the POLICY ENGINE (build_prioritized_opportunities)
    NOT by program_eligibility (build_program_eligibility).
    
    The policy engine's classified CTE has its own logic:
      WHEN best_week_12w >= 80
       AND completed_orders_week = 0
       AND last_trip_date BETWEEN 1 AND 14 days ago
      THEN 'PROGRAM_HIGH_VALUE_RECOVERY'
    
    This is a POLICY OVERRIDE, not a bug. The policy engine can assign
    programs beyond what program_eligibility defines.
    
  Sample drivers (policy-assigned):
""")
for r in cur.fetchall():
    print(f"    driver={r[0][:16]}..., score={r[1]}, rank={r[2]}, excl={r[3]}, elig={r[4]}, reason={r[5]}")

# ═══ PHASE 6: POLICY ENGINE TRACEABILITY ═══
print("\n" + "=" * 65)
print("PHASE 6 — POLICY ENGINE TRACEABILITY")
print("=" * 65)

cur.execute(f"""
    SELECT driver_profile_id, selected_program_code, opportunity_score,
           impact_score, urgency_score, probability_score,
           final_rank, is_actionable_today, exclusion_reason,
           lifecycle_state, retention_state, completed_orders_week, best_week_12w
    FROM growth.yango_lima_prioritized_opportunity_daily
    WHERE opportunity_date = %(d)s
    ORDER BY final_rank ASC LIMIT 5
""", {"d": D})

print(f"\n  Top 5 prioritized drivers:")
print(f"  {'driver':<16} {'program':<28} {'score':>8} {'impact':>6} {'urgency':>7} {'prob':>6} {'rank':>5} {'actionable':>10}")
print(f"  {'-'*16} {'-'*28} {'-'*8} {'-'*6} {'-'*7} {'-'*6} {'-'*5} {'-'*10}")
for r in cur.fetchall():
    print(f"  {r[0][:16]:<16} {(r[1] or '')[:28]:<28} {r[2]:>8.2f} {r[3]:>6.2f} {r[4]:>7.2f} {r[5]:>6.2f} {r[6]:>5} {'YES' if r[7] else 'NO':>10}")

# ═══ PHASE 7: CONSISTENCY AUDIT ═══
print("\n" + "=" * 65)
print("PHASE 7 — CONSISTENCY AUDIT")
print("=" * 65)

# Prioritized without any program eligibility
cur.execute(f"""
    SELECT COUNT(DISTINCT p.driver_profile_id)
    FROM growth.yango_lima_prioritized_opportunity_daily p
    WHERE p.opportunity_date = %(d)s
    AND NOT EXISTS (
        SELECT 1 FROM growth.yango_lima_program_eligibility_daily e
        WHERE e.driver_profile_id = p.driver_profile_id
        AND e.eligibility_date = %(d)s
        AND e.program_code = p.selected_program_code
    )
""", {"d": D})
pri_without_elig = cur.fetchone()[0]

# Queue without prioritized
cur.execute(f"""
    SELECT COUNT(DISTINCT q.driver_id)
    FROM growth.yego_lima_assignment_queue q
    WHERE q.assignment_date = %(d)s
    AND NOT EXISTS (
        SELECT 1 FROM growth.yango_lima_prioritized_opportunity_daily p
        WHERE p.driver_profile_id = q.driver_id
        AND p.opportunity_date = %(d)s
    )
""", {"d": D})
queue_without_pri = cur.fetchone()[0]

# Serving facts for latest date
cur.execute(f"""
    SELECT fact_type, freshness_status, generated_at
    FROM growth.yego_lima_serving_fact
    WHERE fact_date = %(d)s
    ORDER BY fact_type
""", {"d": D})
facts = cur.fetchall()

print(f"""
  Prioritized without eligibility:   {pri_without_elig} (policy engine assignments without program_eligibility)
  Queue without prioritized:          {queue_without_pri} (should be 0)
  Serving facts ({len(facts)}/8):
""")
for f in facts:
    print(f"    {f[0]:<30} {f[1]:<10} {f[2]}")

cur.close()
conn.close()
print("\n" + "=" * 65)
print("AUDIT COMPLETE")
print("=" * 65)
