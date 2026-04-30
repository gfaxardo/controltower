import requests
import json

url = 'http://localhost:8002/diagnostics/join-keys'

# Test weekly with explicit business_slice
params = {
    "grain": "weekly",
    "plan_version": "ruta27_v2026_01_17",
    "country": "peru",
    "city": "lima",
    "business_slice": "delivery",
    "year": 2026,
    "month": 1
}

print(f"Request params: {params}")

r = requests.get(url, params=params, timeout=90)
data = r.json()

print("\n=== WEEKLY JOIN DIAGNOSTICS ===")
print(f"Status: {data.get('status')}")
print(f"Plan keys: {data.get('plan_keys')}")
print(f"Real keys: {data.get('real_keys')}")
print(f"Intersection: {data.get('intersection')}")
print(f"Intersection rate: {data.get('intersection_rate_pct')}%")
print(f"Filters: {data.get('filters')}")

print("\n=== PLAN ONLY SAMPLE (first 10) ===")
for k in data.get('plan_only_sample', [])[:10]:
    print(f"  {k}")

print("\n=== REAL ONLY SAMPLE (first 10) ===")
for k in data.get('real_only_sample', [])[:10]:
    print(f"  {k}")

# Compare specific keys
print("\n=== COMPARISON ===")
plan_only = data.get('plan_only_sample', [])
real_only = data.get('real_only_sample', [])

if plan_only and real_only:
    p = plan_only[0]
    r = real_only[0]
    print(f"Plan key example:  period={p[0]}, country={p[1]}, city={p[2]}, bsn={p[3]}")
    print(f"Real key example:  period={r[0]}, country={r[1]}, city={r[2]}, bsn={r[3]}")

    # Check if periods would match
    print(f"\nPeriod match check:")
    print(f"  Plan period: {p[0]}")
    print(f"  Real period: {r[0]}")
    print(f"  Match: {p[0] == r[0]}")
