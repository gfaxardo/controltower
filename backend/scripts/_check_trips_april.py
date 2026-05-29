import sys,os
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db,init_db_pool
init_db_pool()
conn=get_db().__enter__()
cur=conn.cursor()
cur.execute("SELECT COUNT(*) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01'")
print('All April trips:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01' AND condicion = 'completed'")
print('Completed April:', cur.fetchone()[0])
cur.execute("SELECT DISTINCT condicion FROM public.trips_2026 LIMIT 20")
print('Conditions:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT COUNT(DISTINCT conductor_id) FROM public.trips_2026 WHERE fecha_inicio_viaje >= '2026-04-01' AND fecha_inicio_viaje < '2026-05-01' AND condicion = 'completed'")
print('Unique drivers April:', cur.fetchone()[0])
