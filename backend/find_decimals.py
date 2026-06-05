"""Find ALL Decimal values in campaign_payload."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decimal import Decimal
from app.services.yego_lima_loopcontrol_export_service import (
    build_contacts_payload, validate_loopcontrol_config
)
import json

def find_decimals(obj, path=""):
    """Recursively find all Decimal values."""
    found = []
    if isinstance(obj, Decimal):
        found.append((path, type(obj).__name__, repr(obj)))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            found.extend(find_decimals(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found.extend(find_decimals(v, f"{path}[{i}]"))
    return found

# Build contacts for CHURN_PREVENTION
print("=== Building contacts payload ===")
payload = build_contacts_payload("2026-06-02", "PROGRAM_CHURN_PREVENTION", 10)
contacts = payload.get("contacts", [])

# Build full campaign payload (same as export_campaign_draft does in DRY_RUN)
campaign_payload = {
    "name": "TEST_FIND_DECIMALS",
    "description": "Find all Decimal values",
    "dialer_mode": "predictive",
    "max_concurrent": 10,
    "max_attempts": 3,
    "ring_timeout": 30,
    "schedule_start": "09:00",
    "schedule_end": "18:00",
    "schedule_days": ["MON", "TUE", "WED", "THU", "FRI"],
    "script": "test",
    "contacts": [
        {"external_id": c["external_id"], "phone": c["phone"], "name": c["name"],
         "metadata": c["metadata"]}
        for c in contacts
    ],
}

print(f"\nTotal contacts: {len(contacts)}")
print(f"\n--- Searching for Decimals ---")
decimals = find_decimals(campaign_payload)
if decimals:
    print(f"Found {len(decimals)} Decimal fields:")
    for path, typ, val in decimals:
        print(f"  {path} = {typ}({val})")
else:
    print("No Decimals found!")

# Try json.dumps
print(f"\n--- Testing json.dumps ---")
try:
    s = json.dumps(campaign_payload)
    print(f"PASS: serialized {len(s)} bytes")
except Exception as e:
    print(f"FAIL: {e}")
