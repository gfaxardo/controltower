# Growth API Source Probe — Summary

**Generated:** 2026-06-04T23:22:50.275029-05:00
**Dry Run:** True
**Date Range:** 2026-06-01 → 2026-06-03
**Park ID (masked):** 08e20910***

## 1. Connection
- Enabled: True
- Base URL: https://fleet-api.yango.tech
- Auth: X-Client-ID + X-API-Key (custom headers, NOT Bearer token)
- Timezone: America/Lima (UTC-5)

## 2. Orders Endpoint — POST /v1/parks/orders/list
- Total orders fetched: 0
- Pages fetched: 0 (max: 5)
- Has more pages: N/A
- Pagination: cursor-based (next_cursor field)
- Errors: []

## 3. Driver Profiles Endpoint — POST /v1/parks/driver-profiles/list
- Total profiles: 0
- Fetched: 0
- Work status distribution: {}
- Has car info: False
- Has account/balance: False
- Has current status: False
- Pagination: offset-based (limit/offset, total in response)

## 4. Supply Hours Endpoint — GET /v2/parks/contractors/supply-hours
- Samples attempted: 0
- Samples succeeded: 0
- Samples failed: 0
- Per-driver endpoint (one HTTP call per driver per day)
- Returns supply_duration_seconds (divide by 3600 for hours)
- Rate limit backoff: 3000ms

## 5. Grain Analysis
- Orders grain: **order** (driver_profile.id, car.id, timestamp, price, status)
- Driver profiles grain: **driver_profile** (snapshot, no historical tracking via this endpoint alone)
- Supply hours grain: **driver × day** (one call per driver per day)

## 6. Key Findings
- All available orders within range were fetched
- Supply-hours requires per-driver calls — expensive at fleet scale
- No single endpoint provides aggregated daily metrics (trips, drivers, hours, revenue) — requires client-side aggregation