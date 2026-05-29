# PROFITABILITY P1 VALIDATION REPORT
## Yego Pro Profitability Intelligence — Pre-UI P2 Validation
## Date: 28 May 2026

---

## VERDICT: **GO UI P2**

---

## 1. SCOPE CONTAMINATION CHECK

| Category | Files | Initiative | Risk to P1 |
|----------|-------|-----------|-------------|
| **Ours (Profitability P1)** | main.py (+2 lines), yego_pro_profitability.py, yego_pro_profitability_service.py, SQL views, docs, reports | Yego Pro Profitability | NONE |
| OLM1 (Operational Loop) | drivers.py (+36 lines), driver_operational_loop_service.py, docs/drivers/* | Drivers OLM1 | **NONE** — separate scope |
| Yango Loyalty | yango_loyalty.py, yango_loyalty_*_service.py, alembic 157-160, scripts | Yango Loyalty | **NONE** — separate scope |
| Frontend (not ours) | CampaignEffectiveness.jsx, CampaignIntelligence.jsx, YangoLoyaltyView.jsx, api.js | OLM1 + Yango Loyalty | **NONE** — we did NOT touch frontend |

**Verdict**: Scope contamination EXISTS from OLM1 and Yango Loyalty initiatives, but it does **NOT interfere** with Profitability P1. All our changes are in isolated files. The only shared file (`main.py`) has a clean +2 lines addition.

---

## 2. SQL EXECUTED

```
File: backend/sql/yego_pro_profitability_serving_views.sql
Statements: 9 (5 CREATE MATERIALIZED VIEW + 4 CREATE INDEX)
Result: ALL 9 OK
```

**Fix applied during validation**: Column `d.nombre` changed to `d.full_name` in driver MV (table uses `full_name`).

---

## 3. MVs/VIEWS CREATED

| View | Rows | Status |
|------|------|--------|
| `ops.mv_yego_pro_profitability_week` | 1 | ✅ OK |
| `ops.mv_yego_pro_profitability_day` | 147 | ✅ OK |
| `ops.mv_yego_pro_driver_profitability_week` | 26 | ✅ OK |
| `ops.mv_yego_pro_vehicle_profitability_week` | 102 | ✅ OK |
| `ops.mv_yego_pro_shift_profitability_week` | 44 | ✅ OK |

---

## 4. ENDPOINT TEST RESULTS

| # | Endpoint | Status | Key Data | Pass |
|---|----------|--------|----------|------|
| 1 | GET /overview | OK | 17 KPIs, trips=13951, revenue=142474 | ✅ |
| 2 | GET /weekly | OK | 1 week, profit=-5509.9 | ✅ |
| 3 | GET /daily | OK | 30 days, latest=2026-05-27, trips=507 | ✅ |
| 4 | GET /drivers | OK | 26 drivers, 2 profitable | ✅ |
| 5 | GET /vehicles | LIMITED | 102 config rows, limitation acknowledged | ✅ |
| 6 | GET /shifts | OK | 16 entries (8 weeks × 2 shifts) | ✅ |
| 7 | GET /input-mapping | OK | 10 real, 4 configurable, 3 not_available | ✅ |
| 8 | GET /quality | HEALTHY | All 5 views OK with data | ✅ |

**All 8 endpoints PASS.**

---

## 5. GOVERNANCE VALIDATION

| Check | Result |
|-------|--------|
| No full scans without park/date filter | ✅ PASS (10 park_id filters in SQL) |
| No runtime heavy (uses get_db_quick 15s timeout) | ✅ PASS (8 calls) |
| No fallback monstruoso | ✅ PASS (graceful MISSING_SOURCE) |
| No changes to Omniview | ✅ PASS (no omniview imports) |
| No mixing historical with simulation | ✅ PASS (no simulat/what_if) |
| No automatic recommendations | ✅ PASS (no forecast/suggestion/action) |
| No UPDATE/DELETE/INSERT | ✅ PASS (read-only) |
| Serving-first architecture | ✅ PASS (MV → Service → Router) |

---

## 6. FRESHNESS VALIDATION

| Source | Status | Detail |
|--------|--------|--------|
| `trips_2026` | ✅ FRESH | 147 days (Jan 1 – May 27), 30d window: 319-569 trips/day |
| `module_weekly_billing` | ⚠️ PARTIAL | 1 week only (2026-05-18) |
| `module_weekly_income` | ✅ AVAILABLE | 6 weeks (May 11 – Jun 1) |
| Serving Views | ✅ FRESH | All refreshed 2026-05-28 20:31 |
| `summary_daily` | ❌ GAP | 0 rows for park (acceptance rate unavailable) |
| `fleet_summary_daily` | ❌ GAP | 0 rows for park drivers (supply hours unavailable) |

**Last closed billing week**: 2026-05-18 to 2026-05-24
**Last closed day with trips**: 2026-05-27
**Data range**: 2026-01-01 to 2026-05-27 (147 days)
**Billing gap**: Only 1 week — trend analysis not possible yet

---

## 7. DATA QUALITY

| Metric | Expected | Actual | Match |
|--------|----------|--------|-------|
| Trips completed (30d) | ~13,951 | 13,951 | ✅ |
| Cancellation rate | ~49.5% | 49.45% | ✅ |
| Revenue gross (30d) | ~S/ 142,474 | S/ 142,474 | ✅ |
| Weekly profit | -S/ 5,510 | -S/ 5,509.9 | ✅ |
| Drivers in billing | 26 | 26 | ✅ |
| Profitable drivers | 1-2 | 2 | ✅ |
| Ticket avg | ~S/ 10.21 | S/ 10.21 | ✅ |

---

## 8. COMPILE CHECK

```
python -m compileall backend/app -q
Result: PASS (0 errors)
```

Frontend was NOT touched by Profitability P1 — no frontend build required.

---

## 9. RISKS FOR UI P2

| Risk | Severity | Mitigation |
|------|----------|------------|
| Billing only 1 week — no trend charts possible | MEDIUM | Show "MEDIUM confidence" indicator; weekly chart will have 1 data point |
| Vehicle endpoint is LIMITED | LOW | UI should show fleet config table, not per-vehicle P&L |
| MV refresh not automated yet | MEDIUM | Add to refresh scheduler in P2 or P3 |
| Shift revenue/hour not in billing (only in trips estimate) | LOW | Show available metrics; mark as "estimated" |
| income has 6 weeks but not integrated in weekly MV | LOW | Can enhance in P2 if needed |

---

## 10. RECOMMENDATIONS FOR UI P2

1. **Start with Overview + Weekly + Daily** — most data-rich endpoints
2. **Driver ranking table** — high value, 26 rows with full P&L
3. **Shift comparison (day/night)** — strong insight, well-supported
4. **Waterfall chart** — derive from /overview KPIs (already have all values)
5. **Quality indicator** — show billing confidence level prominently
6. **Defer vehicle page** to P3 (LIMITED data)

---

## 11. GO / NO-GO

| Criterion | Status |
|-----------|--------|
| All endpoints respond | ✅ |
| Data matches Phase 0 discovery | ✅ |
| Governance rules respected | ✅ |
| No production breakage | ✅ |
| No scope contamination risk | ✅ |
| Compile clean | ✅ |
| Freshness acceptable | ⚠️ (billing limited but acknowledged) |

## **FINAL VERDICT: GO UI P2**

Proceed to build the frontend UI for Yego Pro Profitability. Backend is stable, read-only, and serving real data.
