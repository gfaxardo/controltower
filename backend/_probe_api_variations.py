# -*- coding: utf-8 -*-
"""Probe Yango API with variations to diagnose 11:05 AM limitation."""
import asyncio
import sys
sys.path.insert(0, ".")

from app.settings import settings
from datetime import datetime, timedelta, timezone
import httpx

PET = timezone(timedelta(hours=-5))


def _build_headers():
    return {
        "X-Client-ID": (settings.YANGO_CLIENT_ID or "").strip(),
        "X-API-Key": (settings.YANGO_API_KEY or "").strip(),
        "Accept-Language": "en",
        "Content-Type": "application/json",
    }


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")


async def probe_variation(name, body):
    """Probe API with a single request and report first/last timestamps."""
    url = "https://fleet-api.yango.tech/v1/parks/orders/list"
    headers = _build_headers()
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(url, json=body, headers=headers)
            if resp.status_code != 200:
                print(f"  {name}: HTTP {resp.status_code}")
                return None
            data = resp.json()
            orders = data.get("orders", [])
            if not orders:
                print(f"  {name}: 0 orders returned")
                return None
            first_order = orders[0]
            last_order = orders[-1]
            first_at = first_order.get("ended_at") or first_order.get("created_at") or "?"
            last_at = last_order.get("ended_at") or last_order.get("created_at") or "?"
            cursor = data.get("cursor", "")
            print(f"  {name}: {len(orders):>4} orders, first={str(first_at)[:19]}, last={str(last_at)[:19]}, cursor={'YES' if cursor else 'NONE'}")
            return {"count": len(orders), "first_at": first_at, "last_at": last_at, "cursor": cursor}
        except Exception as e:
            print(f"  {name}: ERROR {e}")
            return None


async def main():
    park_id = (settings.YANGO_LIMA_PARK_ID or "").strip()
    if not park_id:
        print("ERROR: No park_id")
        return

    date = "2026-06-04"
    base = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=PET)
    day_start = base.replace(hour=0, minute=0, second=0)
    day_end = base.replace(hour=23, minute=59, second=59)

    # Variation 1: ended_at (current behavior)
    await probe_variation("ended_at full day", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(day_start), "to": _fmt(day_end)},"statuses":["complete"]}}}
    })

    # Variation 2: booked_at instead of ended_at
    await probe_variation("booked_at full day", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"booked_at": {"from": _fmt(day_start), "to": _fmt(day_end)},"statuses":["complete"]}}}
    })

    # Variation 3: Morning window 00:00-06:00
    morning_start = base.replace(hour=0, minute=0)
    morning_end = base.replace(hour=6, minute=0)
    await probe_variation("ended_at 00:00-06:00", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(morning_start), "to": _fmt(morning_end)},"statuses":["complete"]}}}
    })

    # Variation 4: Morning window 06:00-11:00
    mid_start = base.replace(hour=6, minute=0)
    mid_end = base.replace(hour=11, minute=0)
    await probe_variation("ended_at 06:00-11:00", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(mid_start), "to": _fmt(mid_end)},"statuses":["complete"]}}}
    })

    # Variation 5: UTC timezone
    await probe_variation("ended_at UTC full day", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": "2026-06-04T00:00:00+00:00", "to": "2026-06-04T23:59:59+00:00"},"statuses":["complete"]}}}
    })

    # Variation 6: Lima full day booked_at
    await probe_variation("booked_at Lima full", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"booked_at": {"from": _fmt(day_start), "to": _fmt(day_end)},"statuses":["complete"]}}}
    })

    # Variation 7: Previous day for comparison
    prev_base = datetime.strptime("2026-06-03", "%Y-%m-%d").replace(tzinfo=PET)
    prev_start = prev_base.replace(hour=0, minute=0)
    prev_end = prev_base.replace(hour=23, minute=59, second=59)
    await probe_variation("2026-06-03 ended_at", {
        "limit": 1,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(prev_start), "to": _fmt(prev_end)},"statuses":["complete"]}}}
    })

    # Variation 8: Count how many orders for morning window
    morning_full = await probe_variation("ended_at 00:00-12:00 count", {
        "limit": 500,
        "query": {"park": {"id": park_id, "order": {"ended_at": {"from": _fmt(morning_start), "to": _fmt(mid_end)},"statuses":["complete"]}}}
    })

    print(f"\n--- Analysis ---")
    print(f"Morning window (00-12): {'HAS DATA' if morning_full and morning_full['count'] > 0 else 'EMPTY'}")
    if morning_full and morning_full['count'] > 0:
        print(f"  First: {morning_full['first_at']}")
        print(f"  Last:  {morning_full['last_at']}")


if __name__ == "__main__":
    asyncio.run(main())
