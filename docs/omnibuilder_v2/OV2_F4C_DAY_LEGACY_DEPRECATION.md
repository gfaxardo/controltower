# OV2-F.4C — DAY LEGACY DEPRECATION

> **Date:** 2026-06-08
> **Status:** DEPRECATED

## DEPRECATED FUNCTIONS

| Function | File | Replacement |
|----------|------|-------------|
| `load_business_slice_day_for_month()` | `business_slice_incremental_load.py:1695` | `rebuild_day_from_bridge.py` |
| `load_business_slice_week_for_month()` | `business_slice_incremental_load.py:1794` | `rebuild_week_from_day_and_bridge.py` |
| `load_business_slice_month()` | `business_slice_incremental_load.py:1552` | `rebuild_month_from_day_and_bridge.py` |

## PERMITTED USE

Only for manual backfill with explicit flags:
```bash
python -m scripts.refresh_omniview_real_slice_incremental --allow-legacy-weekly-dangerous
```

## BLOCKED USE

- Cannot be called from scheduler
- Cannot be called from HTTP endpoints
- Cannot be called from cascade

## PROTECTION

- Removed from scheduler imports (F.4C)
- DEPRECATED markers in source code
- Cascade orchestrator uses only bridge-based scripts
