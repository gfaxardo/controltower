"""Kill active heavy queries and check temp file status on PostgreSQL server."""
import psycopg2
import sys
sys.path.insert(0, ".")
from app.settings import settings

conn = psycopg2.connect(
    host=settings.DB_HOST, port=settings.DB_PORT,
    database=settings.DB_NAME, user=settings.DB_USER,
    password=settings.DB_PASSWORD
)
conn.autocommit = True
cur = conn.cursor()

print("=" * 80)
print("1) ACTIVE QUERIES (long-running, > 5s)")
print("=" * 80)
cur.execute("""
    SELECT pid, state, now() - query_start AS duration,
           LEFT(query, 120) AS query_preview,
           wait_event_type, wait_event
    FROM pg_stat_activity
    WHERE datname = current_database()
      AND state != 'idle'
      AND pid != pg_backend_pid()
      AND now() - query_start > interval '5 seconds'
    ORDER BY query_start
""")
active = cur.fetchall()
if not active:
    print("  No hay queries activas de larga duración.")
else:
    for r in active:
        print(f"  PID={r[0]} state={r[1]} duration={r[2]}")
        print(f"    wait={r[4]}/{r[5]}")
        print(f"    query: {r[3]}")
        print()

print("\n" + "=" * 80)
print("2) KILLING LONG-RUNNING QUERIES (> 30s, except this session)")
print("=" * 80)
cur.execute("""
    SELECT pid, LEFT(query, 100) AS q, now() - query_start AS dur
    FROM pg_stat_activity
    WHERE datname = current_database()
      AND state = 'active'
      AND pid != pg_backend_pid()
      AND now() - query_start > interval '30 seconds'
""")
to_kill = cur.fetchall()
if not to_kill:
    print("  No hay queries para matar.")
else:
    for r in to_kill:
        pid, q, dur = r
        print(f"  Killing PID={pid} (running {dur}): {q}")
        cur.execute("SELECT pg_terminate_backend(%s)", (pid,))
        result = cur.fetchone()
        print(f"    -> terminated: {result[0]}")

print("\n" + "=" * 80)
print("3) TEMP FILES STATUS")
print("=" * 80)
cur.execute("""
    SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes
    FROM pg_stat_database WHERE datname = current_database()
""")
r = cur.fetchone()
print(f"  temp_files: {r[1]}, temp_bytes acumulados: {r[2]}")

print("\n" + "=" * 80)
print("4) RESET TEMP STATS (pg_stat_reset)")
print("=" * 80)
try:
    cur.execute("SELECT pg_stat_reset()")
    print("  Stats reset OK. Los contadores de temp_files/temp_bytes vuelven a 0.")
except Exception as e:
    print(f"  No se pudo resetear stats (requiere permisos): {e}")

print("\n" + "=" * 80)
print("5) IDLE CONNECTIONS (potential temp file holders)")
print("=" * 80)
cur.execute("""
    SELECT pid, state, now() - state_change AS idle_since,
           LEFT(query, 80) AS last_query
    FROM pg_stat_activity
    WHERE datname = current_database()
      AND state LIKE 'idle%%'
      AND pid != pg_backend_pid()
    ORDER BY state_change
""")
idle = cur.fetchall()
if not idle:
    print("  No hay conexiones idle.")
else:
    for r in idle:
        print(f"  PID={r[0]} state={r[1]} idle_since={r[2]}: {r[3]}")

print("\n" + "=" * 80)
print("6) CURRENT DATABASE SIZE (after cleanup)")
print("=" * 80)
cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
print(f"  Database size: {cur.fetchone()[0]}")

cur.close()
conn.close()
print("\nDone.")
