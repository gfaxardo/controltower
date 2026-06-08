# OV2-D.3B — FRESHNESS + RUNTIME BADGES

> **Date:** 2026-06-08
> **Status:** ENDPOINT READY — BADGE CONTRACT DEFINED

## ENDPOINT

```
GET /ops/omniview-v2/freshness-observatory
```

## BADGE MAPPING

| Layer | freshness_status | Badge |
|-------|-----------------|-------|
| real_day_fact | FRESH | 🟢 REAL day D-1 |
| real_week_fact | FRESH | 🟢 REAL week current |
| real_month_fact | FRESH | 🟢 REAL month current |
| driver_bridge | FRESH | 🟢 BRIDGE D-1 |
| snapshot | STALE | 🟡 SNAPSHOT D-3 |

## RUNTIME BADGE

| Check | Source | Badge |
|-------|--------|-------|
| Backend hash = source hash | `/backend-identity` | 🟢 RUNTIME MATCH |
| Last advancement | `refresh_advancement_log` | 🟢 ADVANCED today |

## UI PLACEMENT

Badges go in the matrix header bar (next to mode/kpi selectors). Non-blocking — matrix renders even if observatory endpoint fails.

---

*End of Freshness Badges*
