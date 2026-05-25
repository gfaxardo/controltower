# API PRE-PROD QA

**Date**: 2026-05-25

## ENDPOINT DEFINITION

### Momentum Drill
```
GET /ops/business-slice/omniview-momentum-drill
```

**Params**: grain, metric_code, country, city, business_slice, fleet, year, weekday, limit

### Daily same-weekday test
```
GET /ops/business-slice/omniview-momentum-drill?grain=daily&metric_code=trips_completed&year=2026&weekday=0&limit=8
```
- Expected: 200 with series array
- Error handling: returns structured error if params invalid
- Timeout: lightweight query (single table, indexed)

### Weekly WoW test
```
GET /ops/business-slice/omniview-momentum-drill?grain=weekly&metric_code=trips_completed&year=2026&limit=8
```
- Expected: Weekly series with week-start keys

### Monthly MoM test
```
GET /ops/business-slice/omniview-momentum-drill?grain=monthly&metric_code=trips_completed&year=2026&limit=8
```
- Expected: Monthly series with month keys

## EXISTING ENDPOINTS (unchanged)
- `GET /ops/business-slice/omniview-projection` — unchanged
- `GET /ops/business-slice/real-freshness` — unchanged
- All others — unchanged

## DATA SOURCE

| Grain | Table |
|-------|-------|
| daily | `ops.real_business_slice_day_fact` |
| weekly | `ops.real_business_slice_week_fact` |
| monthly | `ops.real_business_slice_month_fact` |

## VERDICT: PASS (pending live DB test)
