import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
init_db_pool()
conn=get_db().__enter__()
cur=conn.cursor()
cur.execute("SELECT condicion, COUNT(*) as cnt FROM public.trips_2026 GROUP BY condicion ORDER BY cnt DESC LIMIT 10")
rows=cur.fetchall()
print(f"{len(rows)} distinct conditions (showing top 10):")
for r in rows:
    try:
        print(f"  '{r[0][:50]}' -> {r[1]:,}")
    except:
        print(f"  (unprintable) -> {r[1]:,}")
# Try without condition filter
cur.execute("SELECT COUNT(*) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01'")
print(f"\nAll April: {cur.fetchone()[0]:,}")
cur.execute("SELECT COUNT(DISTINCT conductor_id) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01'")
print(f"Unique drivers April: {cur.fetchone()[0]:,}")
