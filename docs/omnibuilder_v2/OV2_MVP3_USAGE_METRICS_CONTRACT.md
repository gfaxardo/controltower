# OV2-MVP.3 — USAGE METRICS CONTRACT

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** Usage Metrics Contract
> **Fecha:** 2026-06-12

---

## PRINCIPLE

Telemetry is operational, not analytical. No invasive tracking. No PII. No analytics SDKs.

Data is collected via server-side route counting on existing endpoints. Frontend logs to browser console only in dev mode.

---

## METRICS

### 1. Session Count (V2)

```
Endpoint: GET /ops/omniview-v2/shell
Metric:   shell_requests_total
Source:   Server-side counter (in-memory dict, not DB)
```

### 2. Session Count (V1)

```
Endpoint: GET /ops/business-slice/monthly
Metric:   v1_shell_requests_total
Source:   Server-side counter
```

### 3. Grain Usage

```
Params: grain=day|week|month
Metric: grain_usage_{grain}_total
Source: Parsed from query params on /matrix endpoint
```

### 4. Filter Usage

```
Params: country, city, business_slice_name, park_id
Metric: filter_usage_{filter}_{value}_total
Source: Parsed from query params
```

### 5. Source System Usage

```
Params: source_system=CT_TRIPS_2026|YANGO_API_RAW
Metric: source_usage_{source}_total
Source: Query param on /shell or /matrix
```

### 6. Fullscreen Usage

```
Event:  Fullscreen toggle (frontend only)
Metric: fullscreen_toggle_total
Source: Browser localStorage counter
```

### 7. Route Entry Point

```
Event:  Page load
Metric: v2_route_entry_total
Source: Browser sessionStorage on first load
```

---

## IMPLEMENTATION (MINIMAL)

```python
# ops_metrics.py (in-memory, no DB writes)
metrics = {
    "v2_sessions": 0,
    "v1_sessions": 0,
    "grain": {"day": 0, "week": 0, "month": 0},
    "source": {"CT_TRIPS_2026": 0, "YANGO_API_RAW": 0},
    "filters": {},
}
```

```python
# In router:
@router.get("/metrics")
def get_metrics():
    return {
        "v2_sessions": metrics["v2_sessions"],
        "v1_sessions": metrics["v1_sessions"],
        "v2_v1_ratio": round(metrics["v2_sessions"] / max(metrics["v1_sessions"], 1), 2),
        "grain_usage": metrics["grain"],
        "source_usage": metrics["source"],
    }
```

---

## WHAT IS NOT TRACKED

- User identity (no auth check in metrics)
- IP addresses
- Browser fingerprint
- Session duration
- Click paths (single page app)
- Error details beyond count
