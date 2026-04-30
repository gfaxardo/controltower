import requests
import json

url = 'http://localhost:8002/diagnostics/join-keys'

# Test weekly first
params = {
    "grain": "weekly",
    "plan_version": "ruta27_v2026_01_17",
    "country": "peru",
    "city": "lima",
    "business_slice": "delivery",
    "year": 2026,
    "month": 1
}

r = requests.get(url, params=params, timeout=90)
data = r.json()

print("=== WEEKLY JOIN DIAGNOSTICS ===")
print(f"Status: {data.get('status')}")
print(f"Plan keys: {data.get('plan_keys')}")
print(f"Real keys: {data.get('real_keys')}")
print(f"Intersection: {data.get('intersection')}")
print(f"Intersection rate: {data.get('intersection_rate_pct')}%")

print("\n=== PLAN ONLY SAMPLE (first 5) ===")
for k in data.get('plan_only_sample', [])[:5]:
    print(f"  {k}")

print("\n=== REAL ONLY SAMPLE (first 5) ===")
for k in data.get('real_only_sample', [])[:5]:
    print(f"  {k}")

# Now test daily
params["grain"] = "daily"
r = requests.get(url, params=params, timeout=90)
data = r.json()

print("\n\n=== DAILY JOIN DIAGNOSTICS ===")
print(f"Status: {data.get('status')}")
print(f"Plan keys: {data.get('plan_keys')}")
print(f"Real keys: {data.get('real_keys')}")
print(f"Intersection: {data.get('intersection')}")
print(f"Intersection rate: {data.get('intersection_rate_pct')}%")

print("\n=== PLAN ONLY SAMPLE (first 5) ===")
for k in data.get('plan_only_sample', [])[:5]:
    print(f"  {k}")

print("\n=== REAL ONLY SAMPLE (first 5) ===")
for k in data.get('real_only_sample', [])[:5]:
    print(f"  {k}")
