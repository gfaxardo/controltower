# OV2-G.1 — V1/V2 ISOLATION AUDIT

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE

---

## 1. SHARED OBJECTS

| Object | Classification | Rationale |
|--------|---------------|-----------|
| `real_business_slice_day_fact` | **SAFE_SHARED** | Single writer (bridge), both V1/V2 read |
| `real_business_slice_week_fact` | **SAFE_SHARED** | Single writer (bridge), both V1/V2 read |
| `real_business_slice_month_fact` | **SAFE_SHARED** | Single writer (bridge), both V1/V2 read |
| `driver_day_slice_fact` | **SAFE_SHARED** | Single writer, V2 uses for drill, V1 reads indirectly |
| `plan_trips_monthly` | **SAFE_SHARED** | Plan source, read-only for serving |

## 2. ISOLATED OBJECTS

| Object | Classification | Rationale |
|--------|---------------|-----------|
| V1 routers | **SAFE_ISOLATED** | No cross-dependency with V2 |
| V2 routers | **SAFE_ISOLATED** | No cross-dependency with V1 |
| V1 MV views | **SAFE_ISOLATED** | Not used by V2 |
| V2 snapshots | **SAFE_ISOLATED** | V2 only |
| V2 inspector/drill | **SAFE_ISOLATED** | V2 only |

## 3. CROSS-DEPENDENCY CHECK

| Check | Finding |
|-------|---------|
| V1 imports V2 code? | ❌ No |
| V2 imports V1 code? | ❌ No |
| V1 uses V2 endpoints? | ❌ No |
| V2 uses V1 endpoints? | ❌ No |
| Shared scheduler jobs? | ❌ No (V2 cascade, V1 separate) |
| Shared DB tables? | ✅ Yes (REAL facts — intentional) |

## 4. DANGEROUS SHARED

| Object | Risk | Mitigation |
|--------|------|------------|
| `week_fact` | If writer broken, BOTH V1/V2 show stale data | Single writer governance + observatory |

## 5. VERDICT

**SAFE_SHARED** — Shared objects are limited to REAL facts (intentional). V1 and V2 are otherwise isolated. Single-writer governance prevents conflicts.

---

*End of V1/V2 Isolation Audit*
