"""
Phase 1/2 — DB Connection Audit + Cleanup
"""
import sys, os

# Add backend to path
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

import psycopg2
from app.settings import settings

conn_params = {
    "host": settings.DB_HOST or "localhost",
    "port": settings.DB_PORT or 5432,
    "dbname": settings.DB_NAME or "yego_integral",
    "user": settings.DB_USER or "",
    "password": settings.DB_PASSWORD or "",
    "connect_timeout": 15,
}

print("Connecting to DB...")
try:
    conn = psycopg2.connect(**conn_params)
    conn.autocommit = True
    print("Connected OK")
except Exception as e:
    print(f"CONNECTION FAILED: {e}")
    sys.exit(1)

cur = conn.cursor()

print()
print("=" * 60)
print("PHASE 1 — DB_POOL_BEFORE")
print("=" * 60)

cur.execute("""
    SELECT state, usename, application_name, client_addr,
           COUNT(*) AS connections
    FROM pg_stat_activity
    GROUP BY state, usename, application_name, client_addr
    ORDER BY connections DESC
""")
rows = cur.fetchall()
print(f"\n{'STATE':<20} {'USER':<20} {'APP':<30} {'ADDR':<20} {'COUNT':>6}")
print("-" * 100)
for r in rows:
    print(f"{str(r[0] or ''):<20} {str(r[1] or ''):<20} {str(r[2] or '')[:29]:<30} {str(r[3] or ''):<20} {r[4]:>6}")

print("\n--- TOP 30 CONNECTIONS (by state_change) ---")
cur.execute("""
    SELECT pid, usename, state, now() - state_change AS idle_for,
           LEFT(query, 200) AS query
    FROM pg_stat_activity
    ORDER BY state_change ASC
    LIMIT 30
""")
rows = cur.fetchall()
for r in rows:
    q = (r[4] or "")[:120]
    print(f"  pid={r[0]}, user={r[1]}, state={r[2]}, idle_for={r[3]}, query={q}")

cur.execute("SELECT COUNT(*) FROM pg_stat_activity")
total = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle'")
idle = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction'")
idle_tx = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'")
active = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction (aborted)'")
idle_aborted = cur.fetchone()[0]

print(f"\nTOTAL CONNECTIONS: {total}")
print(f"  idle:               {idle}")
print(f"  idle in transaction: {idle_tx}")
print(f"  idle in tx(aborted):{idle_aborted}")
print(f"  active:             {active}")

# Check max_connections setting
cur.execute("SHOW max_connections")
max_conn = cur.fetchone()[0]
print(f"\n  max_connections setting: {max_conn}")

print()
print("=" * 60)
print("PHASE 2 — SAFE CLEANUP")
print("=" * 60)

my_pid = conn.get_backend_pid()
print(f"My backend PID: {my_pid}")

# First, terminate idle connections (not ours, not active)
cur.execute("""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE state = 'idle'
      AND pid <> pg_backend_pid()
""")
idle_terminated = cur.fetchone()[0]
print(f"Terminated idle connections: {idle_terminated}")

# Then idle in transaction
cur.execute("""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE state = 'idle in transaction'
      AND pid <> pg_backend_pid()
""")
idle_tx_terminated = cur.fetchone()[0]
print(f"Terminated idle-in-transaction connections: {idle_tx_terminated}")

print()
print("=" * 60)
print("DB_POOL_AFTER")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM pg_stat_activity")
total_after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle'")
idle_after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'active'")
active_after = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM pg_stat_activity WHERE state = 'idle in transaction'")
idle_tx_after = cur.fetchone()[0]

print(f"TOTAL: {total_after} | idle: {idle_after} | idle_tx: {idle_tx_after} | active: {active_after}")

print(f"\nBefore: total={total}, idle={idle}, active={active}")
print(f"After:  total={total_after}, idle={idle_after}, active={active_after}")

# Quick test query
try:
    cur.execute("SELECT 1 AS alive")
    print("Test query: OK (alive)")
except Exception as e:
    print(f"Test query: FAILED - {e}")

cur.close()
conn.close()
print("\nConnection audit complete.")
