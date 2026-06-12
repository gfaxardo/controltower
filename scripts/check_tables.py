"""Check actual table names and row counts"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

DATES = ['2026-06-03', '2026-06-04', '2026-06-05']

# Find relevant tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'growth' AND table_name LIKE '%opportun%' ORDER BY table_name")
print('Opportunity tables:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'growth' AND table_name LIKE '%serving%' ORDER BY table_name")
print('Serving fact tables:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'growth' AND table_name LIKE '%eligible%' ORDER BY table_name")
print('Eligible tables:', [r[0] for r in cur.fetchall()])

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'growth' AND table_name LIKE '%driver_360%' ORDER BY table_name")
print('Driver 360 tables:', [r[0] for r in cur.fetchall()])

# Check all growth tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'growth' ORDER BY table_name")
all_tables = [r[0] for r in cur.fetchall()]
print(f'\nAll growth tables ({len(all_tables)}):')
for t in all_tables:
    print(f'  {t}')

print()

# Try each opportunity-related table for row counts
for table in all_tables:
    if 'opportun' in table or 'priorit' in table:
        for d in DATES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM growth.{table} WHERE opportunity_date = %(d)s", {"d": d})
                cnt = cur.fetchone()[0]
                print(f"  {table} @ {d}: {cnt} rows")
            except Exception as e:
                print(f"  {table} @ {d}: ERROR - {str(e)[:80]}")

# Check serving facts
print()
for table in all_tables:
    if 'serving' in table or 'fact' in table:
        for d in DATES:
            try:
                cur.execute(f"SELECT COUNT(*) FROM growth.{table} WHERE fact_date = %(d)s", {"d": d})
                cnt = cur.fetchone()[0]
                print(f"  {table} @ {d}: {cnt} fact rows")
            except Exception as e:
                try:
                    cur.execute(f"SELECT COUNT(*) FROM growth.{table} WHERE operational_data_date = %(d)s", {"d": d})
                    cnt = cur.fetchone()[0]
                    print(f"  {table} @ {d}: {cnt} rows (operational_data_date)")
                except:
                    pass

cur.close()
conn.close()
print("\nDone.")
