import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
init_db_pool();conn=get_db().__enter__();cur=conn.cursor()
# Check without country filter first
cur.execute("SELECT DISTINCT country FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND city='lima'")
print("Countries:", cur.fetchall())

cur.execute("SELECT business_slice_name, active_drivers FROM ops.real_business_slice_month_fact WHERE month='2026-04-01' AND city='lima' ORDER BY active_drivers DESC")
print("\nAll slices for Lima April 2026:")
for r in cur.fetchall():
    print(f"  {r[0]:<25} AD={r[1]}")
