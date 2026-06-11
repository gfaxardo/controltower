"""Direct Yango API debug call."""
import sys, os, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.settings import settings
from datetime import datetime, timedelta, timezone

PET = timezone(timedelta(hours=-5))

cid = settings.YANGO_CLIENT_ID or os.environ.get("YANGO_LIMA_CLIENT_ID", "")
key = settings.YANGO_API_KEY or os.environ.get("YANGO_LIMA_API_KEY", "")

body = {
    "limit": 500,
    "query": {
        "park": {
            "id": "08e20910d81d42658d4334d3f6d10ac0",
            "order": {
                "ended_at": {
                    "from": "2026-06-10T00:00:00-05:00",
                    "to": "2026-06-10T23:59:59-05:00",
                },
                "statuses": ["complete"],
            },
        }
    },
}

headers = {
    "X-Client-ID": cid,
    "X-API-Key": key,
    "Content-Type": "application/json",
    "Accept-Language": "en",
}

print("Sending request...")
print(f"  from: {body['query']['park']['order']['ended_at']['from']}")
print(f"  to:   {body['query']['park']['order']['ended_at']['to']}")
print(f"  limit: {body['limit']}")
print(f"  statuses: {body['query']['park']['order']['statuses']}")

resp = requests.post(
    "https://fleet-api.yango.tech/v1/parks/orders/list",
    headers=headers,
    json=body,
    timeout=60,
)
print(f"Status: {resp.status_code}")

data = resp.json()
orders = data.get("orders", [])
print(f"Orders in this page: {len(orders)}")
print(f"Response keys: {sorted(data.keys())}")
nc = data.get("cursor")
print(f"cursor: {str(nc)[:80] if nc else 'None'}")
print(f"has next_cursor key: {'next_cursor' in data}")

if orders:
    first = orders[0]
    last = orders[-1]
    print(f"First order ID: {first.get('id')}")
    print(f"First order ended_at: {first.get('ended_at')}")
    print(f"First order status: {first.get('status')}")
    print(f"Last order ended_at: {last.get('ended_at')}")
    print(f"Sample price: {first.get('price')} (type={type(first.get('price')).__name__})")

    driver = first.get("driver_profile", {})
    car = first.get("car", {})
    print(f"Driver: id={driver.get('id')}")
    print(f"Car: id={car.get('id')}")
    print(f"Category: {first.get('category')}")
    print(f"Payment method: {first.get('payment_method')}")
    print(f"Provider: {first.get('provider')}")

# Test second page with cursor
if nc:
    print("\nFetching second page with cursor...")
    body["cursor"] = nc
    resp2 = requests.post(
        "https://fleet-api.yango.tech/v1/parks/orders/list",
        headers=headers,
        json=body,
        timeout=60,
    )
    data2 = resp2.json()
    orders2 = data2.get("orders", [])
    print(f"Second page: {len(orders2)} orders, status={resp2.status_code}")
    nc2 = data2.get("next_cursor")
    print(f"Second next_cursor: {nc2}")
    if orders2:
        print(f"Second page first ended_at: {orders2[0].get('ended_at')}")
        print(f"Second page last ended_at: {orders2[-1].get('ended_at')}")
