import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
init_db_pool();conn=get_db().__enter__();cur=conn.cursor()
cur.execute("SELECT DISTINCT business_slice_name, active_drivers FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND country='peru' AND city='lima' ORDER BY active_drivers DESC")
for r in cur.fetchall():
    print(repr(r[0]), r[1])
