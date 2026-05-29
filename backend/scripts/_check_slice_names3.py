import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
init_db_pool();conn=get_db().__enter__();cur=conn.cursor()

cur.execute("SELECT business_slice_name, active_drivers, length(business_slice_name) as len, encode(business_slice_name::bytea,'hex') as hex FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND city='lima' ORDER BY active_drivers DESC")
for r in cur.fetchall():
    print(f"name='{r[0]}'  len={r[2]}  hex={r[3][:40]}  AD={r[1]}")

# Test equality
cur.execute("SELECT SUM(active_drivers) FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND city='lima' AND business_slice_name LIKE 'Auto%'")
print("\nLIKE Auto%:", cur.fetchone()[0])
