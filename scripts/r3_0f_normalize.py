"""R3.0F — Normalize existing raw_yango data into growth.yango_lima_orders_raw"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2, json
from datetime import datetime
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=settings.DB_PORT or 5432,
    dbname=settings.DB_NAME or 'yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

# Check raw data date range
print("1. Raw data date range:")
cur.execute("SELECT COUNT(*), MIN(api_fetched_at), MAX(api_fetched_at) FROM raw_yango.orders_raw")
r = cur.fetchone()
print(f"   raw_yango.orders_raw: {r[0]} rows, {r[1]} to {r[2]}")

# Try extracting orders from raw_yango JSON blobs
# The raw table stores JSON in raw_payload column
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='raw_yango' AND table_name='orders_raw' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(f"   Columns: {cols}")

# Check a sample raw record
cur.execute("SELECT * FROM raw_yango.orders_raw LIMIT 1")
sample = cur.fetchone()
if sample:
    for i, col in enumerate(cols):
        val = str(sample[i])[:100] if sample[i] else 'NULL'
        print(f"   {col}: {val}")

# Now try to count orders per date from raw_payload
print("\n2. Extracting orders by date from raw JSON...")
cur.execute("""
    SELECT 
        (raw_payload->>'ended_at')::date as order_date,
        COUNT(*) as n
    FROM raw_yango.orders_raw
    WHERE raw_payload IS NOT NULL
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 15
""")
rows = cur.fetchall()
if rows:
    for r in rows:
        print(f"   {r[0]}: {r[1]} orders")
else:
    print("   No date data in raw_payload. Trying alternate approach...")
    # Try by api_fetched_at
    cur.execute("""
        SELECT DATE(api_fetched_at) as d, COUNT(*)
        FROM raw_yango.orders_raw
        GROUP BY d ORDER BY d DESC LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"   fetched_at {r[0]}: {r[1]}")

# Attempt normalization using the repository function
print("\n3. Attempting normalization via upsert_raw_orders...")
try:
    from app.repositories.yego_lima_growth_repository import upsert_raw_orders
    
    # Get raw orders as list of dicts
    cur.execute("""
        SELECT order_id, park_id, driver_profile_id, price, ended_at, status, raw_payload
        FROM raw_yango.orders_raw
        WHERE raw_payload IS NOT NULL
        ORDER BY api_fetched_at DESC
        LIMIT 500
    """)
    raw_orders = []
    for r in cur.fetchall():
        try:
            payload = r[6] if isinstance(r[6], dict) else {}
            ended = payload.get('ended_at') or str(r[4]) if r[4] else None
            if ended:
                raw_orders.append({
                    'order_id': r[0] or payload.get('order_id', ''),
                    'park_id': r[1] or payload.get('park_id', ''),
                    'driver_profile_id': r[2] or payload.get('driver_profile_id', ''),
                    'price': r[3] or payload.get('price', {}).get('final_cost', 0) if isinstance(payload.get('price'), dict) else 0,
                    'ended_at': ended,
                    'status': r[5] or payload.get('order_status', payload.get('status', 'complete')),
                    'raw_payload': payload,
                })
        except:
            pass
    
    print(f"   Prepared {len(raw_orders)} orders for normalization")
    if raw_orders:
        ins, upd, min_e, max_e = upsert_raw_orders(raw_orders)
        print(f"   Normalized: inserted={ins}, updated={upd}, min_date={min_e}, max_date={max_e}")
    else:
        print("   No orders to normalize")
except Exception as e:
    print(f"   Normalization failed: {e}")

# Final check
print("\n4. Post-normalization check:")
cur.execute("SELECT COUNT(*), MIN(ended_at), MAX(ended_at) FROM growth.yango_lima_orders_raw")
r = cur.fetchone()
print(f"   growth.yango_lima_orders_raw: {r[0]} rows, {r[1]} to {r[2]}")
cur.execute("SELECT DATE(ended_at) as d, COUNT(*) FROM growth.yango_lima_orders_raw GROUP BY d ORDER BY d DESC LIMIT 10")
for r in cur.fetchall():
    print(f"   {r[0]}: {r[1]} orders")

cur.close()
conn.close()
print("\nDone.")
