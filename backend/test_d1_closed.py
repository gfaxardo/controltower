#!/usr/bin/env python3
"""Test endpoint V2 con modo D-1_CLOSED."""
import sys
from datetime import date, timedelta

sys.path.insert(0, ".")
from app.services.refresh_service import get_combined_refresh_status
import json

result = get_combined_refresh_status("mv_real_trips_monthly")
print(json.dumps(result, indent=2, default=str))

print("\n=== VALIDACIÓN D-1_CLOSED ===")
data = result["data"]
allowed_keys = {
    "source_table",
    "source_column",
    "target_date",
    "target_date_mode",
    "row_count_target_date",
    "avg_last_7_closed_days",
    "volume_ratio",
    "data_quality_status",
    "data_status",
}
forbidden = {"row_count_today_so_far", "avg_last_7_days_so_far", "minutes_since_last_data", "status"}
assert set(data.keys()) == allowed_keys, f"Claves data inesperadas: {data.keys()}"
assert not forbidden.intersection(data.keys())
assert data.get("data_status") is not None
assert data.get("target_date_mode") == "D-1_CLOSED"

yesterday = (date.today() - timedelta(days=1)).isoformat()
assert str(data.get("target_date") or "").startswith(yesterday), (
    f"target_date debe ser ayer ({yesterday}), fue {data.get('target_date')}"
)

print(f"target_date_mode: {data.get('target_date_mode')}")
print(f"target_date: {data.get('target_date')}")
print(f"row_count_target_date: {data.get('row_count_target_date')}")
print(f"avg_last_7_closed_days: {data.get('avg_last_7_closed_days')}")
print(f"volume_ratio: {data.get('volume_ratio')}")
print(f"data_quality_status: {data.get('data_quality_status')}")
print(f"data_status: {data.get('data_status')}")
print(f"overall_status: {result.get('overall_status')}")

print("\n=== CHECK ===")
print(f"Bloque data sin intradía: OK")
