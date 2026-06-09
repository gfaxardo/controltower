"""OV2-D.3D.1 — Week auditability recertification"""
import urllib.request, urllib.parse, json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db

base = "http://localhost:8000/ops/omniview-v2/cell-audit"
metrics = ["trips", "revenue", "active_drivers", "avg_ticket", "trips_per_driver"]

print("=== FASE 1: 5 KPI Week Audit ===")
for metric in metrics:
    params = urllib.parse.urlencode({
        "period": "2026-06-01", "business_slice_name": "Auto regular",
        "grain": "week", "metric_id": metric
    })
    r = json.loads(urllib.request.urlopen(f"{base}?{params}", timeout=10).read())
    v = r.get("value", {})
    print(f"  {metric:20s} | trips={v.get('trips',0):>6,d} rev={v.get('revenue',0):>10,.0f} drv={v.get('active_drivers',0):>5,d} ticket={v.get('avg_ticket')} tpd={v.get('trips_per_driver')}")

print("\n=== FASE 2: Source Reconciliation ===")
with get_db() as conn:
    cur = conn.cursor()
    try:
        # Week fact
        cur.execute("SELECT SUM(trips_completed), SUM(active_drivers), SUM(revenue_yego_final) FROM ops.real_business_slice_week_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND week_start='2026-06-01' AND business_slice_name='Auto regular'")
        wf = cur.fetchone()
        print(f"  week_fact: trips={wf[0]:,} drivers={wf[1]:,} revenue={wf[2]:,.0f}")

        # Bridge (day-level for the week)
        cur.execute("SELECT SUM(completed_trips), COUNT(DISTINCT driver_id) FILTER (WHERE completed_trips>0) FROM ops.driver_day_slice_fact WHERE country='peru' AND city='lima' AND activity_date>='2026-06-01' AND activity_date<'2026-06-08' AND business_slice_name='Auto regular'")
        br = cur.fetchone()
        print(f"  bridge:   trips={br[0]:,} drivers={br[1]:,}")

        # Day fact revenue
        cur.execute("SELECT SUM(revenue_yego_final) FROM ops.real_business_slice_day_fact WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima' AND trip_date>='2026-06-01' AND trip_date<'2026-06-08' AND business_slice_name='Auto regular'")
        rev = cur.fetchone()
        print(f"  day_fact revenue: {rev[0]:,.0f}")
    finally:
        cur.close()

print("\n=== FASE 3: Day/Month Regression ===")
for grain, period in [("day", "2026-06-06"), ("month", "2026-06-01")]:
    params = urllib.parse.urlencode({"period": period, "business_slice_name": "Auto regular", "grain": grain, "metric_id": "trips"})
    r2 = json.loads(urllib.request.urlopen(f"{base}?{params}", timeout=10).read())
    v = r2.get("value", {})
    print(f"  {grain:5s}: trips={v.get('trips',0):,} drivers={v.get('active_drivers',0):,}")

print("\nDONE")
