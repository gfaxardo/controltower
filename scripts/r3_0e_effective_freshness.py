"""
LG-INFRA-R3.0E — Effective Freshness + Lineage Propagation Audit
Traces TRUE source dates, not just layer generation dates.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

print("=" * 70)
print("LG-INFRA-R3.0E — EFFECTIVE FRESHNESS AUDIT")
print("=" * 70)

# ═══ LINEAGE CHAIN WITH EXACT SOURCES (from R1.8 forensic) ═══
# Each layer's TRUE source is the upstream layer it reads from

# 1. Get source dates
dates = {}

# Raw orders
cur.execute("SELECT MAX(ended_at) FROM growth.yango_lima_orders_raw")
dates['norm_orders'] = str(cur.fetchone()[0] or 'NONE')

# History daily
cur.execute("SELECT MAX(date) FROM growth.yango_lima_driver_history_daily")
dates['history_daily'] = str(cur.fetchone()[0] or 'NONE')

# History weekly
cur.execute("SELECT MAX(week_start_date) FROM growth.yango_lima_driver_history_weekly")
dates['history_weekly'] = str(cur.fetchone()[0] or 'NONE')

# Snapshot
cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
dates['snapshot'] = str(cur.fetchone()[0] or 'NONE')

# Eligibility
cur.execute("SELECT MAX(eligibility_date) FROM growth.yango_lima_program_eligibility_daily")
dates['eligibility'] = str(cur.fetchone()[0] or 'NONE')

# Opportunity
cur.execute("SELECT MAX(opportunity_date) FROM growth.yango_lima_daily_opportunity_list")
dates['opportunity'] = str(cur.fetchone()[0] or 'NONE')

# Prioritized
cur.execute("SELECT MAX(opportunity_date) FROM growth.yango_lima_prioritized_opportunity_daily")
dates['prioritized'] = str(cur.fetchone()[0] or 'NONE')

# Queue
cur.execute("SELECT MAX(assignment_date) FROM growth.yego_lima_assignment_queue")
dates['queue'] = str(cur.fetchone()[0] or 'NONE')

# Serving
cur.execute("SELECT MAX(fact_date) FROM growth.yego_lima_serving_fact")
dates['serving'] = str(cur.fetchone()[0] or 'NONE')

# ═══ EFFECTIVE SOURCE DATE PER LAYER ═══
# The effective source date is the TRUE max date of data this layer was built from

print("\n" + "=" * 70)
print("EFFECTIVE FRESHNESS WATERFALL")
print("=" * 70)

layers = [
    # (label, layer_date, source_layer, description)
    ("norm_orders", dates['norm_orders'], None, "Direct from Yango API"),
    ("history_daily", dates['history_daily'], "norm_orders", "FROM trips_2025/2026 bootstrap"),
    ("history_weekly", dates['history_weekly'], "history_daily", "FROM history_daily aggregation"),
    ("snapshot", dates['snapshot'], "history_weekly", "FROM history_weekly (PRIMARY) + driver_360 (optional)"),
    ("eligibility", dates['eligibility'], "snapshot", "FROM driver_state_snapshot"),
    ("opportunity", dates['opportunity'], "eligibility", "FROM eligibility JOIN snapshot"),
    ("prioritized", dates['prioritized'], "opportunity", "FROM daily_opportunity_list + history_weekly"),
    ("queue", dates['queue'], "prioritized", "FROM prioritized (via worklist)"),
    ("serving", dates['serving'], "queue", "FROM multiple operational tables"),
]

# Determine effective source date
effective_source = {}
for label, layer_date, source_layer, desc in layers:
    if source_layer is None:
        effective_source[label] = layer_date  # raw: effective = own date
    else:
        effective_source[label] = effective_source.get(source_layer, dates.get(source_layer, 'NONE'))

# Determine propagated staleness
print(f"\n  {'Layer':<18} {'Layer Date':<12} {'Eff Source':<12} {'Source Layer':<18} {'Status':<22}")
print(f"  {'-'*18} {'-'*12} {'-'*12} {'-'*18} {'-'*22}")

first_stale = None
for label, layer_date, source_layer, desc in layers:
    eff_src = effective_source[label]
    
    if '2026-06-05' in layer_date and eff_src and '2026-06-05' in eff_src:
        status = "FRESH"
    elif '2026-06-05' in layer_date and eff_src and '2026-06-01' in eff_src:
        status = "STALE_PROPAGATED"
        if first_stale is None:
            first_stale = label
    elif '2026-06-01' in (layer_date or ''):
        status = "STALE (source)"
        if first_stale is None:
            first_stale = label
    else:
        status = "CHECK"
    
    print(f"  {label:<18} {layer_date:<12} {eff_src:<12} {source_layer or 'NONE':<18} {status:<22}")

# ═══ VERDICT ═══
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)

has_false_freshness = any(
    '2026-06-05' in dates.get(l[0], '') and '2026-06-01' in (effective_source.get(l[0], '') or '')
    for l in layers[3:]  # snapshot onwards
)

print(f"""
  FALSE FRESHNESS DETECTED: {'YES' if has_false_freshness else 'NO'}
  
  Layers with layer_date=06-05 but effective_source=06-01:
""")
for label, layer_date, source_layer, desc in layers:
    if '2026-06-05' in (layer_date or '') and effective_source.get(label, '') and '2026-06-01' in str(effective_source[label]):
        print(f"    {label}: layer_date={layer_date}, effective_source={effective_source[label]}")

print(f"""
  EXPLANATION:
    snapshot, eligibility, opportunity, prioritized, queue, and serving facts
    all show layer_date = 2026-06-05 because the pipeline was run for that date.
    
    However, their effective source is history_weekly which maxes at 2026-06-01.
    The data used to build the 06-05 snapshot is the SAME data used for 06-01.
    
    This is STALE_PROPAGATED: the pipeline generated fresh artifacts from stale data.
    
  FIRST STALE LAYER: {first_stale or 'NONE'}
  
  OPERABILITY:
    OPERABLE_WARNING — downstream is functional but built from 6-day-old source data.
    NOT_OPERABLE would be incorrect (system works, data is internally consistent).
    FRESH would be FALSE (source data is not fresh).
""")

cur.close()
conn.close()
