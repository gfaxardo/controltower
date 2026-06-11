"""Quick test: Yango transactions API for Lima 2026-06-10."""
import sys, os, json, time, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.settings import settings

LIMA = "08e20910d81d42658d4334d3f6d10ac0"
cid = settings.YANGO_CLIENT_ID or os.environ.get("YANGO_LIMA_CLIENT_ID", "")
key = settings.YANGO_API_KEY or os.environ.get("YANGO_LIMA_API_KEY", "")

headers = {"X-Client-ID": cid, "X-API-Key": key, "Content-Type": "application/json", "Accept-Language": "en"}

body = {
    "limit": 1000,
    "query": {
        "park": {
            "id": LIMA,
            "transaction": {
                "event_at": {
                    "from": "2026-06-10T00:00:00-05:00",
                    "to": "2026-06-10T23:59:59-05:00",
                },
            },
        },
    },
}

print("Calling transactions API...")
start = time.time()
resp = requests.post("https://fleet-api.yango.tech/v2/parks/transactions/list", headers=headers, json=body, timeout=60)
elapsed = time.time() - start

print(f"Status: {resp.status_code} ({elapsed:.1f}s)")

if resp.status_code == 200:
    data = resp.json()
    keys = list(data.keys())
    print(f"Response keys: {keys}")
    
    txns = data.get("transactions", []) or data.get("items", [])
    print(f"Transactions in page: {len(txns)}")
    
    cursor = data.get("cursor") or data.get("next_cursor")
    print(f"Cursor: {str(cursor)[:80] if cursor else 'None'}")
    
    if txns:
        t = txns[0]
        print(f"First txn: id={t.get('id')} cat={t.get('category_name')} amount={t.get('amount')} event_at={t.get('event_at')}")
        # Count categories
        cats = {}
        for tx in txns:
            cn = tx.get("category_name", "unknown")
            cats[cn] = cats.get(cn, 0) + 1
        print(f"Category distribution (first page):")
        for cn, cnt in sorted(cats.items(), key=lambda x: -x[1])[:10]:
            print(f"  {cn}: {cnt}")

elif resp.status_code == 429:
    print("RATE LIMITED")
else:
    print(f"Response: {resp.text[:500]}")
