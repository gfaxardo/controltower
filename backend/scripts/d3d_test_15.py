import urllib.request, urllib.parse, json

base = "http://localhost:8000/ops/omniview-v2/cell-audit"
grains = {"day": "2026-06-06", "week": "2026-06-01", "month": "2026-06-01"}
metrics = ["trips", "revenue", "active_drivers", "avg_ticket", "trips_per_driver"]

print("Cell Audit — 5 KPIs × 3 Grains")
print("=" * 70)
for grain, period in grains.items():
    for metric in metrics:
        params = urllib.parse.urlencode({
            "period": period, "business_slice_name": "Auto regular",
            "grain": grain, "metric_id": metric
        })
        url = f"{base}?{params}"
        try:
            r = json.loads(urllib.request.urlopen(url, timeout=10).read())
            v = r.get("value", {})
            print(f"  {metric:20s} / {grain:5s} | trips={v.get('trips',0):>6,d} rev={v.get('revenue',0):>10,.0f} drv={v.get('active_drivers',0):>5,d} ticket={v.get('avg_ticket')} tpd={v.get('trips_per_driver')}")
        except Exception as e:
            print(f"  {metric:20s} / {grain:5s} | FAIL: {str(e)[:60]}")
