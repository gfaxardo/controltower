"""Normalize raw_yango -> growth orders"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.chdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
import psycopg2
from app.settings import settings

conn = psycopg2.connect(host=settings.DB_HOST or 'localhost', port=5432,
    dbname='yego_integral', user=settings.DB_USER or '',
    password=settings.DB_PASSWORD or '', connect_timeout=15)
conn.autocommit = True
cur = conn.cursor()

print("BEFORE:")
cur.execute("SELECT COUNT(*), MIN(ended_at), MAX(ended_at) FROM growth.yango_lima_orders_raw")
r = cur.fetchone()
print(f"  growth.orders_raw: {r[0]} rows, {r[1]} to {r[2]}")

print("\nNORMALIZING (raw_yango -> growth)...")
cur.execute("""
    INSERT INTO growth.yango_lima_orders_raw 
    (order_id, status, ended_at, price, driver_profile_id, car_id, category, payment_method, raw_payload, last_fetched_at)
    SELECT order_id, order_status, order_ended_at, price, driver_profile_id, car_id, category, payment_method, raw_payload, api_fetched_at
    FROM raw_yango.orders_raw
    WHERE order_ended_at > '2026-06-01'
    ON CONFLICT (order_id) DO NOTHING
""")
print(f"  Inserted: {cur.rowcount}")

print("\nAFTER:")
cur.execute("SELECT COUNT(*), MIN(ended_at), MAX(ended_at) FROM growth.yango_lima_orders_raw")
r = cur.fetchone()
print(f"  growth.orders_raw: {r[0]} rows, {r[1]} to {r[2]}")

cur.execute("SELECT DATE(ended_at) as d, COUNT(*) FROM growth.yango_lima_orders_raw GROUP BY d ORDER BY d")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]} orders")

cur.close()
conn.close()
print("\nNormalization done!")
