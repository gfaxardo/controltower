#!/usr/bin/env python3
"""Test endpoint V2 con modo D-1_CLOSED."""
import sys
sys.path.insert(0, '.')
from app.services.refresh_service import get_combined_refresh_status
import json

result = get_combined_refresh_status('mv_real_trips_monthly')
print(json.dumps(result, indent=2, default=str))

# Validación
print('\n=== VALIDACIÓN D-1_CLOSED ===')
data = result['data']
print(f"target_date_mode: {data.get('target_date_mode')}")
print(f"target_date: {data.get('target_date')}")
print(f"row_count_target_date: {data.get('row_count_target_date')}")
print(f"avg_last_7_closed_days: {data.get('avg_last_7_closed_days')}")
print(f"volume_ratio: {data.get('volume_ratio')}")
print(f"data_quality_status: {data.get('data_quality_status')}")
print(f"data_status: {data.get('data_status')}")
print(f"overall_status: {result.get('overall_status')}")

# Verificar que ya no compara contra hoy parcial
print('\n=== CHECK ===')
print(f"data_status es 'fresh'? {data.get('data_status') == 'fresh'} (debe ser fresh si hay datos de ayer)")
print(f"minutes_since_last_refresh >= 0? {result['refresh']['minutes_since_last_refresh'] >= 0 if result['refresh']['minutes_since_last_refresh'] else 'N/A'}")
