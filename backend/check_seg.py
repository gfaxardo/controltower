from app.db.connection import get_db
c = get_db().__enter__().cursor()
c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='ops' AND table_name='driver_weekly_segment_fact' ORDER BY ordinal_position")
print([r[0] for r in c.fetchall()])
c.execute("SELECT * FROM ops.driver_weekly_segment_fact LIMIT 2")
rows = [dict(zip([d[0] for d in c.description], r)) for r in c.fetchall()]
print(rows)
