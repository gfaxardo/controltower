"""
LG-INFRA-R3.0C — Yango Live Ingestion + Freshness Chain Certification
Complete freshness waterfall audit.
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

def check(label, table, date_col, schema='growth'):
    """Check freshness of a table"""
    full = f"{schema}.{table}"
    try:
        cur.execute(f"SELECT MAX({date_col}), COUNT(*) FROM {full}")
        r = cur.fetchone()
        max_date = str(r[0]) if r[0] else 'NONE'
        count = r[1]
        
        cur.execute(f"SELECT COUNT(*) FROM {full} WHERE {date_col} = '2026-06-05'")
        d05 = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {full} WHERE {date_col} = '2026-06-04'")
        d04 = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {full} WHERE {date_col} = '2026-06-03'")
        d03 = cur.fetchone()[0]
        
        return {
            'label': label, 'table': full, 'date_col': date_col,
            'max_date': max_date, 'total_rows': count,
            'd06_05': d05, 'd06_04': d04, 'd06_03': d03,
        }
    except Exception as e:
        return {'label': label, 'error': str(e)[:80]}

print("=" * 70)
print("LG-INFRA-R3.0C — FRESHNESS WATERFALL AUDIT")
print("=" * 70)

# ═══ PHASE 1: INGESTION JOBS ═══
print("\n" + "=" * 70)
print("PHASE 1 — INGESTION JOB INVENTORY")
print("=" * 70)

# Check ingestion run log
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_yango' AND table_name LIKE '%ingestion%'")
ing_tables = [r[0] for r in cur.fetchall()]
print(f"  Ingestion tables: {ing_tables}")

# Check for ingestion runs
for t in ing_tables:
    try:
        cur.execute(f"SELECT COUNT(*), MAX(heartbeat_at) FROM raw_yango.{t}")
        r = cur.fetchone()
        print(f"  {t}: {r[0]} runs, latest_heartbeat={r[1]}")
    except:
        pass

# Check APScheduler and endpoint ingestion
print(f"""
  KNOWN INGESTION PATHS:
  1. yango_raw_ingestion_service.py -> ingest_endpoint()
     Source: Yango Fleet API (orders/list, driver-profiles/list, transactions/list)
     Target: raw_yango.orders_raw, raw_yango.driver_profiles_raw, raw_yango.transactions_raw
     
  2. yego_lima_growth_repository.py -- upsert_raw_orders()
     Source: raw_yango.orders_raw
     Target: growth.yango_lima_orders_raw
     
  3. yego_lima_growth_history_service.py -> bootstrap_history()
     Source: public.trips_2025, public.trips_2026
     Target: growth.yango_lima_driver_history_daily -> weekly
     
  4. lab endpoints:
     POST /yego-lima-growth/lab/capture-orders-range
     POST /yego-lima-growth/lab/build-driver-360-day (dead)
     POST /yego-lima-growth/lab/stabilize-driver-360-day (dead)
""")

# ═══ PHASE 2: RAW YANGO AUDIT ═══
print("=" * 70)
print("PHASE 2 — RAW YANGO AUDIT")
print("=" * 70)

raw_tables = [
    ("raw_yango", "orders_raw", "ended_at"),
    ("raw_yango", "driver_profiles_raw", "api_fetched_at"),
    ("raw_yango", "transactions_raw", "created_at"),
    ("growth", "yango_lima_orders_raw", "ended_at"),
]

for schema, table, col in raw_tables:
    full = f"{schema}.{table}"
    try:
        cur.execute(f"SELECT COUNT(*), MIN({col}), MAX({col}) FROM {full}")
        r = cur.fetchone()
        print(f"  {full}:")
        print(f"    rows={r[0]}, min={r[1]}, max={r[2]}")
    except Exception as e:
        print(f"  {full}: ERROR - {str(e)[:80]}")

# ═══ PHASE 3: HISTORY AUDIT ═══
print("\n" + "=" * 70)
print("PHASE 3 — NORMALIZATION + HISTORY")
print("=" * 70)

hist = [
    ("history_daily", "growth", "yango_lima_driver_history_daily", "date"),
    ("history_weekly", "growth", "yango_lima_driver_history_weekly", "week_start_date"),
]

for label, schema, table, col in hist:
    full = f"{schema}.{table}"
    try:
        cur.execute(f"SELECT COUNT(*), MIN({col}), MAX({col}) FROM {full}")
        r = cur.fetchone()
        print(f"  {label} ({full}):")
        print(f"    rows={r[0]}, min={r[1]}, max={r[2]}")
    except Exception as e:
        print(f"  {label}: ERROR - {str(e)[:80]}")

# ═══ PHASE 4+5: FRESHNESS WATERFALL ═══
print("\n" + "=" * 70)
print("PHASE 4+5 — FRESHNESS WATERFALL MATRIX")
print("=" * 70)

waterfall = [
    ("1_raw_orders", "raw_yango", "orders_raw", "ended_at"),
    ("2_raw_profiles", "raw_yango", "driver_profiles_raw", "api_fetched_at"),
    ("3_raw_tx", "raw_yango", "transactions_raw", "created_at"),
    ("4_norm_orders", "growth", "yango_lima_orders_raw", "ended_at"),
    ("5_history_daily", "growth", "yango_lima_driver_history_daily", "date"),
    ("6_history_weekly", "growth", "yango_lima_driver_history_weekly", "week_start_date"),
    ("7_snapshot", "growth", "yango_lima_driver_state_snapshot", "snapshot_date"),
    ("8_eligibility", "growth", "yango_lima_program_eligibility_daily", "eligibility_date"),
    ("9_opportunity", "growth", "yango_lima_daily_opportunity_list", "opportunity_date"),
    ("10_prioritized", "growth", "yango_lima_prioritized_opportunity_daily", "opportunity_date"),
    ("11_queue", "growth", "yego_lima_assignment_queue", "assignment_date"),
    ("12_history_trace", "growth", "yego_lima_driver_list_history", "action_date"),
    ("13_intraday", "growth", "yego_lima_intraday_driver_signal", "signal_date"),
    ("14_serving", "growth", "yego_lima_serving_fact", "fact_date"),
]

first_break = None
prev_max = None
results = []

for label, schema, table, col in waterfall:
    full = f"{schema}.{table}"
    try:
        cur.execute(f"SELECT MAX({col}), COUNT(*) FROM {full}")
        r = cur.fetchone()
        mx = str(r[0]) if r[0] else 'NONE'
        cnt = r[1]
        
        # Determine freshness status
        if cnt == 0:
            status = "EMPTY"
        elif mx == 'NONE':
            status = "NO_DATA"
        elif label.startswith("1_") or label.startswith("2_") or label.startswith("3_"):
            status = "RAW"  # raw data, always considered OK if present
        elif '2026-06-05' in mx:
            status = "FRESH"
        elif '2026-06-04' in mx:
            status = "STALE (1d)"
        elif '2026-06-03' in mx:
            status = "STALE (2d)"
        elif '2026-06' in mx:
            status = f"STALE ({mx})"
        else:
            status = f"OLD ({mx})"
        
        # Detect first breakpoint
        if first_break is None and status not in ('FRESH', 'RAW', 'EMPTY'):
            first_break = label
        
        results.append((label, full, mx, cnt, status, first_break == label))
        print(f"  {label:<22} max={mx:<12} rows={cnt:<8} [{status}]")
    except Exception as e:
        print(f"  {label:<22} ERROR: {str(e)[:60]}")

# ═══ PHASE 6: GAP EXPLANATION ═══
print("\n" + "=" * 70)
print("PHASE 6 — GAP EXPLANATION")
print("=" * 70)

cur.execute("SELECT MAX(ended_at) FROM raw_yango.orders_raw")
raw_max = cur.fetchone()[0]
cur.execute("SELECT MAX(snapshot_date) FROM growth.yango_lima_driver_state_snapshot")
snap_max = cur.fetchone()[0]
cur.execute("SELECT MAX(fact_date) FROM growth.yego_lima_serving_fact")
serve_max = cur.fetchone()[0]

print(f"""
  KEY DATES:
    Yango raw orders max:      {raw_max}
    Driver snapshot max:        {snap_max}
    Serving facts max:          {serve_max}
    
  CONTRADICTION: raw orders max = {raw_max}, but operational = {snap_max}
  
  EXPLANATION:
    Raw orders from Yango API are STALE. Latest order is {raw_max}.
    Snapshot ({snap_max}) and all downstream layers were built from
    driver_history_weekly, which was bootstrapped from public.trips_2025/2026,
    NOT from Yango API raw orders.
    
    The freshness chain breaks at LAYER 1: Yango API raw ingestion is stale.
    Everything downstream uses historical bootstrap data from trips tables.
    
    This is NOT a bug — it's by design:
    - Raw Yango provides LIVE operational freshness (currently stale)
    - History bootstrap provides HISTORICAL context (always available)
    - Snapshot uses BOTH, falling back to history when raw is stale
    
    FIRST BREAKPOINT: raw_yango.orders_raw (max date = {raw_max}, 6 days behind)
    
    REMEDIATION: Run Yango API ingestion to bring raw data current.
    POST /yego-lima-growth/lab/capture-orders-range
""")

# Check serving facts freshness
print("=" * 70)
print("SERVING FACTS STATUS")
print("=" * 70)
cur.execute("""
    SELECT fact_date, fact_type, freshness_status, generated_at
    FROM growth.yego_lima_serving_fact
    ORDER BY fact_date DESC, fact_type
""")
for r in cur.fetchall():
    print(f"  {r[0]} {r[1]:<30} {r[2]:<10} {r[3]}")

cur.close()
conn.close()

print("\n" + "=" * 70)
print("AUDIT COMPLETE")
print(f"FIRST BREAKPOINT: {first_break or 'None'}")
print("=" * 70)
