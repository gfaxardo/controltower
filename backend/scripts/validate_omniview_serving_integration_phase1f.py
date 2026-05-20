"""Fase 1F — Validate Omniview serving integration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import init_db_pool, _get_connection_params
init_db_pool()
import psycopg2

print("=" * 60)
print("FASE 1F — OMNIVIEW SERVING INTEGRATION VALIDATION")
print("=" * 60)

c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()

# 1) Verify FACT_MONTHLY redirect
from app.services.business_slice_service import FACT_MONTHLY, FACT_MONTHLY_RAW
print(f"\n1. FACT_MONTHLY = {FACT_MONTHLY}")
print(f"   FACT_MONTHLY_RAW = {FACT_MONTHLY_RAW}")
assert FACT_MONTHLY == "ops.v_real_business_slice_month_serving"
print("   Redirect confirmed: PASS")

# 2) April data via serving view
cur.execute(f"SELECT COALESCE(SUM(trips_completed),0) FROM {FACT_MONTHLY} WHERE month = '2026-04-01'")
april_serving = cur.fetchone()[0]
cur.execute(f"SELECT COALESCE(SUM(trips_completed),0) FROM {FACT_MONTHLY_RAW} WHERE month = '2026-04-01'")
april_raw = cur.fetchone()[0]
print(f"\n2. April: serving={april_serving} raw={april_raw} match={april_serving==april_raw}")
assert april_serving == april_raw

# 3) May data via serving view
cur.execute(f"SELECT COALESCE(SUM(trips_completed),0) FROM {FACT_MONTHLY} WHERE month = '2026-05-01'")
may_serving = cur.fetchone()[0]
cur.execute(f"SELECT COALESCE(SUM(trips_completed),0) FROM {FACT_MONTHLY_RAW} WHERE month = '2026-05-01'")
may_raw = cur.fetchone()[0]
print(f"\n3. May: serving={may_serving} raw={may_raw} match={may_serving==may_raw}")
assert may_serving == may_raw

# 4) Serving source metadata for April
cur.execute(f"""
    SELECT DISTINCT serving_source, data_status 
    FROM {FACT_MONTHLY} WHERE month = '2026-04-01'
""")
r = cur.fetchone()
print(f"\n4. April metadata: source={r[0]} status={r[1]}")
assert r[0] == 'snapshot'
assert r[1] == 'locked_snapshot'
print("   PASS")

# 5) Serving source metadata for May
cur.execute(f"""
    SELECT DISTINCT serving_source, data_status 
    FROM {FACT_MONTHLY} WHERE month = '2026-05-01'
""")
r = cur.fetchone()
print(f"\n5. May metadata: source={r[0]} status={r[1]}")
assert r[0] == 'working_fact'
print("   PASS")

# 6) Bogota
cur.execute(f"""
    SELECT business_slice_name, SUM(trips_completed) 
    FROM {FACT_MONTHLY} WHERE month = '2026-05-01' 
    AND LOWER(COALESCE(city,'')) = 'bogota'
    GROUP BY 1 ORDER BY 2 DESC
""")
bg = {str(r[0]): int(r[1]) for r in cur.fetchall()}
print(f"\n6. Bogota: {bg}")
assert bg.get("Carga") == 2801
assert bg.get("Delivery moto") == 188
print("   PASS")

# 7) Barranquilla
cur.execute(f"""
    SELECT business_slice_name, SUM(trips_completed) 
    FROM {FACT_MONTHLY} WHERE month = '2026-05-01' 
    AND LOWER(COALESCE(city,'')) = 'barranquilla'
    GROUP BY 1 ORDER BY 2 DESC
""")
bq = {str(r[0]): int(r[1]) for r in cur.fetchall()}
print(f"\n7. Barranquilla: {bq}")
assert bq.get("Taxi Moto") == 12483
assert bq.get("Auto regular") == 9764
print("   PASS")

# 8) Omniview service importable
from app.services.business_slice_omniview_service import get_business_slice_omniview
print("\n8. Omniview service importable: PASS")

# 9) Endpoints importable
from app.routers.ops_refresh import router
print("9. Endpoints importable: PASS")

# 10) No regression in refresh path (raw still used for writes)
from app.services.business_slice_incremental_load import FACT_MONTH as BS_FACT_MONTH
print(f"\n10. Incremental load FACT_MONTH = {BS_FACT_MONTH}")
assert BS_FACT_MONTH == "ops.real_business_slice_month_fact"
print("    Refresh path unchanged: PASS")

cur.close(); c.close()

print("\n" + "=" * 60)
print("ALL TESTS PASSED — FASE 1F GO")
print("=" * 60)
