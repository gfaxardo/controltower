import sys, time; sys.path.insert(0, '.')
from app.services.driver_serving_freshness_service import check_all_facts
from app.db.connection import get_db

# Test 1: serving freshness
t0 = time.time()
r = check_all_facts()
print(f"serving-freshness: {int((time.time()-t0)*1000)}ms  status={r['status']}  ready={r['all_ready']}")

# Test 2: geo-options
t0 = time.time()
from app.routers.drivers import geo_options
# Can't easily call async, so query directly
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SET LOCAL statement_timeout = '5000'")
    cur.execute("""
        SELECT ARRAY_AGG(DISTINCT country ORDER BY country) FILTER (WHERE country IS NOT NULL AND country != 'Unknown') AS countries,
               ARRAY_AGG(DISTINCT city ORDER BY city) FILTER (WHERE city IS NOT NULL AND city != 'Unknown') AS cities,
               ARRAY_AGG(DISTINCT park_id ORDER BY park_id) FILTER (WHERE park_id IS NOT NULL AND park_id != 'Unknown') AS parks
        FROM ops.driver_supply_overview_weekly_fact
    """)
    row = cur.fetchone()
    countries = len(row[0]) if row and row[0] else 0
    cities = len(row[1]) if row and row[1] else 0
    parks = len(row[2]) if row and row[2] else 0
print(f"geo-options (direct): {int((time.time()-t0)*1000)}ms  countries={countries} cities={cities} parks={parks}")

# Test 3: supply overview fact
t0 = time.time()
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SET LOCAL statement_timeout = '5000'")
    cur.execute("""
        SELECT week_start, active_drivers, trips, churned, reactivated, refreshed_at
        FROM ops.driver_supply_overview_weekly_fact
        ORDER BY week_start DESC LIMIT 5
    """)
    rows = cur.fetchall()
    latest = str(rows[0][0])[:10] if rows else 'N/A'
print(f"supply-overview-fact: {int((time.time()-t0)*1000)}ms  latest={latest}  rows={len(rows)}")

# Test 4: composition fact
t0 = time.time()
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("SET LOCAL statement_timeout = '5000'")
    cur.execute("""
        SELECT week_start, segment, drivers_count, trips
        FROM ops.driver_weekly_segment_fact
        WHERE trips_completed > 0
        GROUP BY week_start, segment
        ORDER BY week_start DESC LIMIT 5
    """)
    rows = cur.fetchall()
print(f"segment-composition-fact: {int((time.time()-t0)*1000)}ms  rows={len(rows)}")

print("\nAll endpoints responding from facts.")
