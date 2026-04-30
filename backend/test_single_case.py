import requests
import json

url = 'http://localhost:8002/diagnostics/join-keys'

# Solo caso 3: weekly Peru Lima Delivery
params = {
    "grain": "weekly",
    "plan_version": "ruta27_v2026_01_17",
    "country": "peru",
    "city": "lima",
    "business_slice": "delivery",
    "year": 2026,
    "month": 1
}

print(f"Testing: Peru/Lima/Delivery/weekly/2026")
print(f"Params: {params}")

try:
    r = requests.get(url, params=params, timeout=90)
    data = r.json()

    print(f"\nStatus: {data.get('status')}")
    print(f"Plan keys: {data.get('plan_keys')}")
    print(f"Real keys: {data.get('real_keys')}")
    print(f"Intersection: {data.get('intersection')}")
    print(f"Plan only: {data.get('plan_only')}")
    print(f"Real only: {data.get('real_only')}")
    print(f"Rate: {data.get('intersection_rate_pct')}%")
    print(f"Filters: {data.get('filters')}")

    print("\nPlan only sample (first 5):")
    for k in data.get('plan_only_sample', [])[:5]:
        print(f"  {k}")

    print("\nReal only sample (first 5):")
    for k in data.get('real_only_sample', [])[:5]:
        print(f"  {k}")

    print("\nBy cause:", data.get('by_cause'))

except Exception as e:
    print(f"Error: {e}")
