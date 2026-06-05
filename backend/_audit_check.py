from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
with get_db() as conn:
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT run_id, status, start_date, end_date, day_rows, week_rows, month_rows, started_at, finished_at FROM ops.omniview_real_slice_refresh_audit ORDER BY started_at DESC LIMIT 4")
    for r in cur.fetchall():
        print(f"{r['run_id']} {r['status']} {r['start_date']}-{r['end_date']} D={r['day_rows']} W={r['week_rows']} M={r['month_rows']} @{r['finished_at']}")
    cur.close()

    # Check if the May 1-Jun 5 refresh ran
    cur2 = conn.cursor(cursor_factory=RealDictCursor)
    cur2.execute("SELECT run_id, status FROM ops.omniview_real_slice_refresh_audit WHERE start_date = '2026-05-01' ORDER BY started_at DESC LIMIT 1")
    r2 = cur2.fetchone()
    if r2:
        print(f"\nMay 1 refresh: {r2['run_id']} {r2['status']}")
    else:
        print("\nNo May 1 refresh found")
    cur2.close()
