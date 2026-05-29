# YEGO PRO PROFITABILITY — P1 FOUNDATION
## Control Foundation Serving Layer (Read-Only)
## Park: Lima | park_id: `64085dd85e124e2c808806f70d527ea8`
## Date: 28 May 2026

---

## 1. GOVERNANCE VALIDATION

| Check | Result |
|-------|--------|
| Active Phase | Control Foundation 1H.4 |
| Engine | Control Foundation (serving layer) |
| Forbidden Engines | Forecast/Suggestion/Decision/Action — NOT USED |
| Architecture | Serving-first: MV → Service → Router → API |
| Runtime Protection | get_db_quick with 15s timeout |
| Fallback | Graceful: missing_source + remediation |

---

## 2. COMPONENTS CREATED

### SQL Serving Views
`backend/sql/yego_pro_profitability_serving_views.sql`

| View | Source | Granularity | Purpose |
|------|--------|-------------|---------|
| `ops.mv_yego_pro_profitability_week` | module_weekly_billing | park × week | Park-level P&L |
| `ops.mv_yego_pro_profitability_day` | trips_2026 | park × day | Daily operations |
| `ops.mv_yego_pro_driver_profitability_week` | billing + drivers | driver × week | Driver P&L |
| `ops.mv_yego_pro_vehicle_profitability_week` | cronograma | config | Fleet quota structure |
| `ops.mv_yego_pro_shift_profitability_week` | trips_2026 | shift × week | Day/Night analysis |

### Backend Service
`backend/app/services/yego_pro_profitability_service.py`

Functions:
- `get_overview()` — 30d trips + last billing week
- `get_weekly()` — Weekly P&L series
- `get_daily()` — Daily operational metrics
- `get_drivers()` — Driver-level profitability
- `get_vehicles()` — Fleet configuration (limited)
- `get_shifts()` — Day/Night shift breakdown
- `get_input_mapping()` — All inputs with classification
- `get_quality()` — Data health check

### Router
`backend/app/routers/yego_pro_profitability.py`

Prefix: `/fleet-project/yego-pro/profitability`

### Registration
Added to `backend/app/main.py` (import + include_router)

---

## 3. ENDPOINTS

| Method | Path | Source | Description |
|--------|------|--------|-------------|
| GET | `/fleet-project/yego-pro/profitability/overview` | trips + billing | Overview KPIs |
| GET | `/fleet-project/yego-pro/profitability/weekly` | billing | Weekly P&L series |
| GET | `/fleet-project/yego-pro/profitability/daily` | trips | Daily operations |
| GET | `/fleet-project/yego-pro/profitability/drivers` | billing | Driver profitability |
| GET | `/fleet-project/yego-pro/profitability/vehicles` | cronograma | Fleet config |
| GET | `/fleet-project/yego-pro/profitability/shifts` | trips | Day/Night shifts |
| GET | `/fleet-project/yego-pro/profitability/input-mapping` | multiple | Input classification |
| GET | `/fleet-project/yego-pro/profitability/quality` | meta | Data health |

---

## 4. METRIC METADATA CONTRACT

Every KPI returned includes:
```json
{
  "value": 10.21,
  "source": "trips_2026",
  "metric_type": "REAL | DERIVED | ASSUMPTION | NOT_AVAILABLE",
  "confidence": "HIGH | MEDIUM | LOW",
  "notes": ""
}
```

---

## 5. GRACEFUL FAILURE PATTERN

If a serving view is missing:
```json
{
  "status": "MISSING_SOURCE",
  "missing_view": "ops.mv_yego_pro_profitability_week",
  "remediation": "Run yego_pro_profitability_serving_views.sql",
  "message": "Serving view does not exist. Create it first."
}
```

No UI freeze. No heavy runtime fallback. No monster queries.

---

## 6. DEPLOYMENT STEPS

1. Run SQL script to create serving views:
   ```bash
   psql -d yego_integral -f backend/sql/yego_pro_profitability_serving_views.sql
   ```

2. Backend is ready (service + router already registered in main.py)

3. Refresh views periodically:
   ```sql
   REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yego_pro_profitability_week;
   REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yego_pro_profitability_day;
   REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yego_pro_driver_profitability_week;
   REFRESH MATERIALIZED VIEW ops.mv_yego_pro_vehicle_profitability_week;
   REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_yego_pro_shift_profitability_week;
   ```

---

## 7. LIMITATIONS ACCEPTED

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Billing: only 1 week available | Cannot show trends | `data_confidence: MEDIUM` indicator |
| No supply hours | Cannot show true online hours | Proxy: horas_trabajo from billing |
| No vehicle assignment | Cannot report per-vehicle P&L | Show fleet config only |
| fleet_summary_daily empty | No acceptance rate | Marked as NOT_AVAILABLE |
| KM in trips is in meters | Conversion needed | Dividing by 1000 in all views |

---

## 8. NOT IMPLEMENTED (Deferred)

| Feature | Phase | Reason |
|---------|-------|--------|
| Waterfall chart endpoint | P2 | Requires UI component |
| Simulator/what-if | P3+ | Forecast Engine territory |
| Recommendations | P3+ | Suggestion Engine territory |
| Auto-refresh scheduler | P2 | Need operational stability first |
| Input update (PUT) | P2 | Requires config table migration |
| Trend analysis | P2 | Need 4+ weeks billing |

---

## 9. FILES CREATED/MODIFIED

| File | Action |
|------|--------|
| `backend/sql/yego_pro_profitability_serving_views.sql` | NEW |
| `backend/app/services/yego_pro_profitability_service.py` | NEW |
| `backend/app/routers/yego_pro_profitability.py` | NEW |
| `backend/app/main.py` | MODIFIED (import + router registration) |
| `docs/fleet-project/yego-pro/PROFITABILITY_P1_FOUNDATION.md` | NEW |
| `docs/fleet-project/yego-pro/PROFITABILITY_DATA_CONTRACT.md` | NEW |
| `reports/yego_pro_profitability_p1_validation.csv` | NEW |
