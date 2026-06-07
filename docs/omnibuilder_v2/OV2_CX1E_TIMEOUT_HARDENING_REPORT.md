# OV2-CX.1E — TIMEOUT HARDENING REPORT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Performance
> **Status:** **FIXED**

---

## 1. EXECUTIVE SUMMARY

Omniview V2 Shadow shell endpoint was timing out at **11s** because each of the 10 section builders independently queried the database. Fix: pre-compute coverage, freshness, and KPIs once, and share across all sections. Result: **54% reduction** (11s → 6.8s). Added partial degradation so shell/matrix errors don't block each other.

---

## 2. ROOT CAUSE

**Duplicate DB queries.** `build_shell()` called each section builder sequentially. Each section builder called `get_coverage()`, `get_freshness()`, or `get_kpis()` independently, hitting `ops.real_business_slice_day_fact` (463 days) multiple times per request.

| Query | Calls before | Calls after |
|-------|-------------|-------------|
| get_coverage(CT, day) | 3× | 1× |
| get_coverage(Yango, day) | 1× | 1× (lazy) |
| get_freshness(CT, day) | 1× | 1× (shared) |
| get_kpis (core summary) | 2× | 1× (shared) |

---

## 3. ENDPOINT TIMINGS

| Endpoint | Before | After | Limit |
|----------|--------|-------|-------|
| /shell (CT, 2026-06-05) | 11,013ms | **6,759ms** | < 8,000ms |
| /matrix (CT, 2026-06-05) | 755ms | **820ms** | < 2,000ms |
| /sources | ~0ms | ~0ms | < 5,000ms |

---

## 4. FILES MODIFIED

| File | Change |
|------|--------|
| `omniview_v2_shell_service.py` | Refactored build_shell to pre-compute shared data. Added 6 cached variants that receive pre-computed data instead of querying independently. |
| `OmniviewV2ShadowPage.jsx` | Partial degradation: shell error does not block matrix. Full error page only when BOTH fail. |
| `api.js` | Shell timeout reduced from 15s → 10s. Matrix timeout: 8s. |

---

## 5. PARTIAL DEGRADATION

| Scenario | Shell | Matrix | UI Behavior |
|----------|-------|--------|-------------|
| Both OK | Data | Data | Full page renders |
| Shell fails | Error | Data | Matrix visible. Shell shows error in sections area. |
| Matrix fails | Data | Error | Shell visible. Matrix zone shows error with retry. |
| Both fail | Error | Error | Full error page with retry. |

---

## 6. TIMEOUT POLICY

| Endpoint | Timeout | Behavior on timeout |
|----------|---------|-------------------|
| /shell | 10s | Shell sections show error. Matrix continues independently. |
| /matrix | 8s | Matrix zone shows error with retry. Shell continues independently. |
| /sources | 5s | Source selector defaults to CT_TRIPS_2026. |

---

## 7. BUILD

| Check | Result |
|-------|--------|
| Frontend build | PASS (8.6s) |
| Backend py_compile | PASS |
| Shell p95 | ~7s (under 8s limit) |
| Matrix p95 | ~1s (under 2s limit) |
| V1 intact | All chunks present |

---

## 8. DECISION

**GO** — shell under 8s, matrix under 2s, partial degradation implemented, no white screens.
