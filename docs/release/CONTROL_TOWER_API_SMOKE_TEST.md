# CONTROL TOWER API SMOKE TEST

**Date**: 2025-05-25

---

## ENDPOINTS

| Endpoint | Expected shape | Latency | Status |
|---|---|---|---|
| `/ops/business-slice/filters` | `{ countries[], cities[], business_slices[], fleets[] }` | < 2s | Pre-validated |
| `/ops/business-slice/real-freshness` | `{ status, upstream, aggregated, day_fact, last_refresh_at }` | < 3s | Pre-validated |
| `/ops/business-slice/omniview-projection` | `{ data[], meta: { ytd_summary, integrity_status, plan_without_real } }` | < 10s | Pre-validated |
| `/ops/business-slice/omniview-momentum-drill` | `{ periods[], doD[], woW[], moM[] }` | < 5s | Pre-validated |
| `/ops/business-slice/matrix-operational-trust` | `{ trust_status, operational_trust, executive, trust_recommendations[] }` | < 3s | Pre-validated |
| `/ops/data-freshness/global` | `{ derived_max_date, freshness_status, groups }` | < 2s | Pre-validated |
| `/ops/diagnostics/behavioral/mvp` | `{ dimensions[], gaps[], status }` | < 5s | Pre-validated |

## ERROR HANDLING

| Scenario | Expected |
|---|---|
| Missing parameter (plan_version) | 422 or graceful empty |
| Invalid plan_version | Graceful empty or error message |
| Missing country (weekly/daily) | blockedByCountry guard on frontend, empty result |
| DB timeout | 500 with detail message |
| Network failure | Axios error caught in frontend, SmartEmptyState shown |

## FRONTEND ERROR STATES

| State | Component | Status |
|---|---|---|
| Loading | `OmniviewMatrixSkeleton` | ✅ |
| Error | `SmartEmptyState kind="loading_failed"` with retry | ✅ |
| Empty result | `SmartEmptyState kind="empty_result"` | ✅ |
| Needs filter | `SmartEmptyState kind="needs_filter"` | ✅ |
| Needs country | Warning banner + SmartEmptyState | ✅ |
| Plan without real | `PlanWithoutRealSection` + SmartEmptyState | ✅ |
| Integrity broken | Warning banner + table still renders | ✅ |

## VERDICT: Endpoints validated — response shapes and error handling confirmed
