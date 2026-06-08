# OV2-F.2 — UI HEALTH CONTRACT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** CONTRACT DEFINED — NOT IMPLEMENTED

---

## 1. PURPOSE

Define the data contract for future UI health components that surface refresh chain staleness to users. No UI builds — this is a contract-only document.

---

## 2. HEALTH BADGE CONTRACT

```json
{
  "health_badge": {
    "overall": "FRESH|STALE|DEGRADED|UNKNOWN",
    "summary": "Data as of 2026-06-06 (D-1)",
    "color": "green|yellow|red|gray",
    "updated_at": "2026-06-07T04:00:00Z"
  }
}
```

| Status | Color | Condition |
|--------|-------|-----------|
| FRESH | Green | All layers within threshold |
| DEGRADED | Yellow | 1-2 layers stale but UI still functional |
| STALE | Red | Critical layer stale, UI shows old data |
| UNKNOWN | Gray | Cannot determine (DB down) |

---

## 3. FRESHNESS BADGE CONTRACT

```json
{
  "freshness_badge": {
    "layer": "DAY_FACT",
    "max_date": "2026-06-06",
    "gap_days": 1,
    "status": "FRESH|STALE|MISSING",
    "message": "Daily data up to June 6 (D-1)"
  }
}
```

---

## 4. REFRESH EXPLANATION DRAWER CONTRACT

```json
{
  "refresh_drawer": {
    "layers": [
      {
        "layer": "DAY_FACT",
        "last_success": "2026-06-07T04:00:00Z",
        "last_failure": null,
        "freshness_gap_days": 1,
        "status": "FRESH",
        "error_code": null,
        "error_message": null,
        "remediation": "Auto-refreshed at 04:00 UTC"
      }
    ],
    "waterfall_broken": false,
    "stale_layers_count": 0,
    "certification_result": "GO (9/10)"
  }
}
```

---

## 5. API ENDPOINT

Recommended endpoint (not implemented — backlog):

```
GET /ops/omniview-v2/refresh-health
```

Response: The `refresh_drawer` contract above.

---

## 6. BACKLOG

| # | Item | Priority |
|---|------|----------|
| 1 | Implement `GET /ops/omniview-v2/refresh-health` endpoint | P2 |
| 2 | Add Health Badge to CommandHeader | P3 |
| 3 | Add Freshness Badge per-layer in UI | P3 |
| 4 | Add Refresh Explanation Drawer (click badge → expand) | P3 |

---

*End of UI Health Contract*
