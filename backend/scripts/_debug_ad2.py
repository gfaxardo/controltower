import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool;from psycopg2.extras import RealDictCursor;from datetime import date
init_db_pool();conn=get_db().__enter__();cur=conn.cursor(cursor_factory=RealDictCursor)

# Test 1: hardcoded with country and slice
cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND country='peru' AND city='lima' AND business_slice_name='Auto regular'")
print("T1 (hardcoded string):", cur.fetchone()['sum'])

# Test 2: parameterized date
cur.execute("SELECT SUM(active_drivers) AS ad FROM ops.real_business_slice_month_fact WHERE month = %(ms)s AND country = 'peru' AND city = 'lima' AND business_slice_name = 'Auto regular'", {"ms": date(2026,4,1)})
print("T2 (date param):", cur.fetchone()['ad'])

# Test 3: parameterized string
cur.execute("SELECT SUM(active_drivers) AS ad FROM ops.real_business_slice_month_fact WHERE month = %(ms)s AND country = 'peru' AND city = 'lima' AND business_slice_name = 'Auto regular'", {"ms": "2026-04-01"})
print("T3 (string param):", cur.fetchone()['ad'])

# Test 4: positional params
cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month = %s AND country = %s AND city = %s AND business_slice_name = %s", (date(2026,4,1), 'peru', 'lima', 'Auto regular'))
print("T4 (positional date):", cur.fetchone()['sum'])
