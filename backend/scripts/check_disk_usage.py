"""Check PostgreSQL disk usage: top tables, temp files, database size."""
import psycopg2
import sys
sys.path.insert(0, ".")
from app.settings import settings

conn = psycopg2.connect(
    host=settings.DB_HOST, port=settings.DB_PORT,
    database=settings.DB_NAME, user=settings.DB_USER,
    password=settings.DB_PASSWORD
)
cur = conn.cursor()

print("=" * 80)
print("DATABASE SIZE")
print("=" * 80)
cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
print(f"  {cur.fetchone()[0]}")

print("\n" + "=" * 80)
print("TOP 25 TABLES/MVs BY SIZE (including indexes)")
print("=" * 80)
cur.execute("""
    SELECT
        n.nspname || '.' || c.relname AS name,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
        pg_total_relation_size(c.oid) AS bytes,
        pg_size_pretty(pg_relation_size(c.oid)) AS data_size,
        CASE c.relkind
            WHEN 'r' THEN 'TABLE'
            WHEN 'm' THEN 'MATVIEW'
            WHEN 'p' THEN 'PARTITIONED'
            ELSE c.relkind::text
        END AS tipo,
        COALESCE(s.n_live_tup, 0) AS filas_aprox
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
    WHERE c.relkind IN ('r', 'm', 'p')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    ORDER BY pg_total_relation_size(c.oid) DESC
    LIMIT 25
""")
print(f"{'Tabla':<55} {'Total':>10} {'Data':>10} {'Tipo':<8} {'Filas':>12}")
print("-" * 100)
for r in cur.fetchall():
    print(f"{r[0]:<55} {r[1]:>10} {r[3]:>10} {r[4]:<8} {r[5]:>12}")

print("\n" + "=" * 80)
print("TEMP FILES USAGE (accumulated since last stats reset)")
print("=" * 80)
cur.execute("""
    SELECT datname, temp_files, pg_size_pretty(temp_bytes) AS temp_bytes
    FROM pg_stat_database WHERE datname = current_database()
""")
r = cur.fetchone()
if r:
    print(f"  DB: {r[0]}, temp_files: {r[1]}, temp_bytes: {r[2]}")

print("\n" + "=" * 80)
print("SCHEMA SIZES (ops, public, canon, plan, bi)")
print("=" * 80)
cur.execute("""
    SELECT
        n.nspname AS schema,
        pg_size_pretty(SUM(pg_total_relation_size(c.oid))) AS total,
        SUM(pg_total_relation_size(c.oid)) AS bytes,
        COUNT(*) AS objects
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind IN ('r', 'm', 'i', 'S')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    GROUP BY n.nspname
    ORDER BY SUM(pg_total_relation_size(c.oid)) DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:<20} {r[1]:>12}  ({r[3]} objects)")

print("\n" + "=" * 80)
print("OPS SCHEMA - ALL TABLES DETAIL")
print("=" * 80)
cur.execute("""
    SELECT
        c.relname AS name,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
        pg_total_relation_size(c.oid) AS bytes,
        CASE c.relkind
            WHEN 'r' THEN 'TABLE'
            WHEN 'm' THEN 'MATVIEW'
            WHEN 'i' THEN 'INDEX'
            ELSE c.relkind::text
        END AS tipo,
        COALESCE(s.n_live_tup, 0) AS filas
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
    WHERE n.nspname = 'ops' AND c.relkind IN ('r', 'm')
    ORDER BY pg_total_relation_size(c.oid) DESC
""")
print(f"{'Tabla':<50} {'Total':>10} {'Tipo':<8} {'Filas':>12}")
print("-" * 85)
for r in cur.fetchall():
    print(f"{r[0]:<50} {r[1]:>10} {r[3]:<8} {r[4]:>12}")

cur.close()
conn.close()
