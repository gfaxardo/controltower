import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
from psycopg2.extras import RealDictCursor
init_db_pool()
conn=get_db().__enter__()
cur=conn.cursor(cursor_factory=RealDictCursor)

# Direct query
cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND country='peru' AND city='lima' AND business_slice_name='Auto regular'")
print("AD direct:", cur.fetchone()['sum'])

# Service function
from app.services.yango_loyalty_performance_service import _fetch_lima_performance
from datetime import date
r = _fetch_lima_performance(cur, date(2026,4,1))
print("AD via service:", r['active_drivers_mtd'])
print("Full:", r)
