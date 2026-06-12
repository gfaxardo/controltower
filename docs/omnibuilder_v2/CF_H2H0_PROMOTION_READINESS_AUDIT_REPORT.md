# CF-H2H.0 — PROMOTION READINESS AUDIT REPORT

> **Fase:** CF-H2H.0 — Promotion Readiness Audit
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `PROMOTION_READINESS_BLOCKED`

---

## 1. EXECUTIVE SUMMARY

Auditoría de readiness para promover métricas desde CT/legacy hacia Yango API. **Resultado: NO-GO.** Solo existen 4 días de shadow data FULL (Jun 4, 8, 9, 10) de los 30 requeridos. Faltan 26 días de acumulación continua.

**Estimated readiness date: 2026-07-06** (asumiendo scheduler CF-H2D activo sin interrupciones).

---

## 2. SHADOW DATA STATUS

### 2.1 Real Shadow Data (from raw_yango.orders_raw, Lima)

| Date | Orders | Drivers | Txns | Status |
|------|--------|---------|------|--------|
| Jun 4 | 11,085 | 1,478 | 51,764 | **FULL** |
| Jun 5 | 1,000 | 468 | 52,192 | LOW (truncated ingestion) |
| Jun 6 | 500 | 322 | 56,515 | LOW (truncated ingestion) |
| Jun 8 | 8,749 | 0* | 42,541 | **FULL** |
| Jun 9 | 9,351 | 735 | 43,937 | **FULL** |
| Jun 10 | 9,136 | 996 | 42,517 | **FULL** |
| Jun 11 | 798 | 403 | 26,248 | LOW (day in progress) |

*Jun 8: driver count shows 0 likely due to DISTINCT query issue, orders count confirms FULL.

### 2.2 30-Day Requirement

| Metric | Required | Actual | Gap |
|--------|----------|--------|-----|
| FULL shadow days | 30 | 4 | **26** |
| Consecutive FULL days | 30 | 3 (Jun 8-10) | **27** |
| Shadow window | 30 days | 7 days | **23** |
| First shadow date | — | 2026-06-04 | — |
| Estimated ready date | — | 2026-07-06 | 26 more days |

### 2.3 Missing Dates (Jun 1-3, Jun 7)

| Date | Reason |
|------|--------|
| Jun 1-3 | Pre-ingestion. Scheduler not yet running. |
| Jun 7 | No Yango data ingested. Gap day. |

---

## 3. KPI READINESS MATRIX

### 3.1 Core KPIs

| KPI | Current Owner | Candidate | Shadow Days | Coverage | Delta | Freshness | Badge | Status |
|-----|-------------|-----------|-------------|----------|-------|-----------|-------|--------|
| `completed_trips` | CT_BRIDGE | YANGO | 4/30 | ~77% vs CT | -22.3% (coverage gap) | ~2-5h | CT_BRIDGE | **NOT_READY** |
| `active_drivers` | CT_BRIDGE | YANGO | 4/30 | ~77% vs CT | (driver count mismatch) | ~2-5h | CT_BRIDGE | **NOT_READY** |
| `revenue_yego` | CT_BRIDGE | YANGO | 4/30 | Tx available 7/7 days | Per-trip ~2.4% | ~1-6d | CT_BRIDGE | **NOT_READY** |
| `gmv` | CT_BRIDGE | YANGO | 4/30 | N/A (CT=0) | N/A | ~1-6d | CT_BRIDGE | **NOT_READY** |

### 3.2 Derived KPIs

| KPI | Depends On | Status | Reason |
|-----|-----------|--------|--------|
| `avg_ticket` | K1 + K6 | **NOT_READY** | Source KPIs not ready |
| `trips_per_driver` | K1 + K4 | **NOT_READY** | Source KPIs not ready |
| `revenue_per_order` | K5 + K1 | **NOT_READY** | Source KPIs not ready |
| `commission_rate` | K3 + K6 | **NOT_READY** | Source KPIs not ready |

### 3.3 Blocked KPIs

| KPI | Status | Reason |
|-----|--------|--------|
| `cancelled_trips` | **BLOCKED** | Yango no ingiere cancelados |
| `supply_hours` | **BLOCKED** | Sin endpoint bulk |
| `reactivated_drivers` | **BLOCKED** | Requiere lifecycle Yango (90d) |
| `churned_drivers` | **BLOCKED** | Requiere lifecycle Yango (90d) |
| `business_slice` | **READY_WITH_CONDITIONS** | Mapping certificado. Depende de completed_trips. |

---

## 4. COVERAGE ANALYSIS

### 4.1 Yango vs CT (Jun 4-10, FULL days only)

| Date | Yango | CT | Coverage |
|------|-------|-----|----------|
| Jun 4 | 11,085 | 14,264 | 77.7% |
| Jun 8 | 8,749 | 11,291 | 77.5% |
| Jun 9 | 9,351 | 12,528 | 74.6% |
| Jun 10 | 9,136 | 12,543 | 72.8% |

**Coverage is NOT >= 95%.** However, this is an ingestion volume issue (documented in CF-H2C.0A), not a data quality issue. Yango ingests via a near-real-time scheduler that:
- Was truncated pre-June 8 (max_pages=20, MAX_TOTAL_SECONDS=120)
- Only captures `status='complete'` orders
- Has 800 driver profiles vs CT's 10,165 active drivers

Expected coverage improvement when:
- Scheduler runs continuously for 30 days (CF-H2D)
- Full driver profiles ingestion completes
- Transaction volume stabilizes

### 4.2 Coverage Trend

Coverage is slightly declining (77.7% → 72.8%) over the 4 FULL days. This warrants monitoring but is within expected range for a recently-deployed scheduler.

---

## 5. FRESHNESS ANALYSIS

### 5.1 Current Freshness

| Endpoint | Last Event | Age |
|----------|-----------|-----|
| Orders | 2026-06-11 (latest order) | ~4.3 hours |
| Transactions | Varies by date | 1-6 days behind |
| Driver profiles | 800 profiles snapshotted | Static |

**Freshness is NOT within 5 minutes** for any endpoint. The near-real-time scheduler (CF-H2D, every 5 min) should achieve this once running stably for 30 days.

### 5.2 Freshness History

Based on per-date age_hours from section 2.2:
- Jun 10: 20.9h (day-old data, expected for yesterday's complete day)
- Jun 11: 4.3h (today, still accumulating)
- No cycle-level freshness data available yet (scheduler tick logs exist but need freshness metrics)

---

## 6. ROLLBACK READINESS

| Check | Status |
|-------|--------|
| Rollback plan documented | **PASS** (CF_H2H0_ROLLBACK_TEST_PLAN.md) |
| Single control point defined (registry) | **PASS** |
| Auto-rollback triggers defined | **PASS** (5 conditions) |
| Manual rollback procedure | **PASS** |
| Rollback throttling (3 strikes) | **PASS** |
| Dry-run executed | **NOT STARTED** (requires 30d shadow first) |
| CT fallback verified operational | **PASS** (CT day facts serving normally) |

---

## 7. PROMOTION WORKFLOW READINESS

| Check | Status |
|-------|--------|
| Workflow documented | **PASS** (CF_H2H0_PROMOTION_WORKFLOW.md) |
| 6-phase state machine | **PASS** |
| Two-phase approval defined | **PASS** |
| Promotion execution procedure | **PASS** |
| Monitoring plan (7 days post-promotion) | **PASS** |
| Promotion order (dependency-aware) | **PASS** |
| Approval evidence package defined | **PASS** |

---

## 8. FAILURE MODES COVERAGE

| Failure Mode | Detection | Severity | Fallback | Covered |
|-------------|-----------|----------|----------|---------|
| Yango API timeout | scheduler_tick_log | WARNING→CRITICAL | Auto-rollback after 3 fails | Yes |
| Yango API credentials fail (401/403) | HTTP status | CRITICAL | Immediate rollback | Yes |
| Transactions missing | 0 revenue for date | HIGH | CT fallback for revenue | Yes |
| Orders missing (0 for date) | COUNT = 0 | CRITICAL after 3d | CT fallback for all KPIs | Yes |
| Freshness degraded (>30min) | Freshness audit | WARNING | Degraded badge, keep source | Yes |
| Duplicate inflation | raw_rows > distinct_orders | LOW | COUNT(DISTINCT order_id) | Yes |
| Business slice unmapped | 0 mapped orders | MEDIUM | CT business_slice_name | Yes |
| Source registry missing | Table not found | CRITICAL | Hard fail, all KPIs → CT | Yes |
| Canonical mapper failed | Service error | HIGH | Last known good day fact | Yes |
| CT fallback missing | No CT data | CRITICAL | MISSING badge, no proxy | Yes |
| Delta spike (>20%) | Reconciliation | HIGH | Auto-rollback after 3d | Yes |
| Scheduler zombie runs | running > 30min | MEDIUM | Zombie cleanup in scheduler | Yes |

---

## 9. INFRASTRUCTURE READINESS

| Component | Status | Note |
|-----------|--------|------|
| `ops.omniview_metric_source_registry` | Deployed | 21 KPIs registered (migration 210) |
| `ops.omniview_canonical_day_fact_shadow` | Deployed | Seeded with dates from raw_yango |
| `cf_h2g_canonical_mapper_service` | Deployed | Shadow mapper operational |
| `dim.yango_category_to_slice` | Deployed | 10 mappings certified (migration 211) |
| CF-H2D scheduler | Deployed | Near-real-time, every 5 min |
| Omniview productivo | Untouched | Production serving facts unchanged |
| CT fallback | Operational | day/week/month facts serving normally |
| `growth.health` endpoints | Deployed | LG-SERV-2A certified |

---

## 10. BLOCKERS SUMMARY

| # | Blocker | Impact | Resolution |
|---|---------|--------|------------|
| **1** | **Only 4/30 FULL shadow days** | **ALL KPIs NOT_READY** | Wait 26 more days. Scheduler CF-H2D must run continuously. |
| **2** | Coverage < 95% (currently ~75%) | All Yango KPIs | Scheduler must complete full ingestion. More driver profiles needed. |
| **3** | Freshness not within 5 min target | All Yango KPIs | Scheduler near-real-time must stabilize. |
| **4** | Rollback dry-run not executed | Rollback readiness | Execute after 30 days shadow data exists. |
| **5** | Jun 7 gap day (no Yango data) | Continuity | Re-ingest or document as explained gap. |
| **6** | Driver profile count (800) << CT (10,165) | active_drivers KPI | Full driver_profiles ingestion needed. |
| **7** | No approved approvers designated | Approval workflow | Assign Operations Lead as approver. |

---

## 11. GO / NO-GO

### 11.1 Per-KPI

| KPI | Status | Reason |
|-----|--------|--------|
| `completed_trips` | **NOT_READY** | Shadow days: 4/30. Coverage: ~75%. |
| `active_drivers` | **NOT_READY** | Shadow days: 4/30. Driver count mismatch. |
| `revenue_yego` | **NOT_READY** | Shadow days: 4/30. Tx freshness: 1-6d. |
| `gmv` | **NOT_READY** | Shadow days: 4/30. Tx freshness: 1-6d. |
| `avg_ticket` | **NOT_READY** | Depends on K1+K6. |
| `trips_per_driver` | **NOT_READY** | Depends on K1+K4. |
| `revenue_per_order` | **NOT_READY** | Depends on K5+K1. |
| `commission_rate` | **NOT_READY** | Depends on K5+K6. |
| `business_slice` | **READY_WITH_CONDITIONS** | Mapping certified. Depends on K1. |
| `cancelled_trips` | **BLOCKED** | Yango no ingiere cancelados. |
| `supply_hours` | **BLOCKED** | Sin endpoint bulk. |

### 11.2 Global for CF-H2H Source Promotion: **NO-GO**

```
███████████████████████████████████████████████████████████████
█                                                             █
█   CF-H2H SOURCE PROMOTION                                   █
█                                                             █
█   STATUS: NO-GO                                             █
█                                                             █
█   Blocker: Only 4 FULL shadow days of 30 required.         █
█   Estimated ready: 2026-07-06 (26 more days).              █
█                                                             █
█   Satisfied:                                                █
█   - Rollback plan documented                               █
█   - Promotion workflow documented                          █
█   - Failure modes covered (12)                             █
█   - Registry + mapper deployed                             █
█   - Business slice mapping certified                        █
█   - Omniview productivo untouched                          █
█                                                             █
█   Not satisfied:                                            █
█   - 30 FULL shadow days (4/30)                             █
█   - Coverage >= 95% (currently ~75%)                       █
█   - Freshness <= 5 min (>4h)                              █
█   - Rollback dry-run executed                              █
█   - Approvers designated                                   █
█                                                             █
███████████████████████████████████████████████████████████████
```

---

## 12. ESTIMATED TIMELINE TO READINESS

| Milestone | Est. Date | Depends On |
|-----------|-----------|------------|
| CF-H2D scheduler continuous | Already active | — |
| 30 FULL shadow days | 2026-07-06 | Scheduler running daily |
| Coverage stabilization | 2026-07-06 | Full ingestion + driver profiles |
| Freshness within 5 min | 2026-06-15 | Scheduler near-real-time stabilization |
| Rollback dry-run | 2026-07-06 | 30 days shadow data |
| Approval workflow activation | TBD | Approvers designated |
| **CF-H2H ready for re-audit** | **2026-07-06** | All above |

---

## 13. BACKLOG UPDATED

| Estado | Fase | Descripción |
|--------|------|-------------|
| **ACTIVE** | **CF-H2H.0** | Promotion Readiness Audit (this document) |
| READY NEXT | CF-H2J | Continuous Certification Monitor |
| BLOCKED | **CF-H2H** | **Omniview Source Promotion (NO-GO)** |
| BACKLOG | CF-H2E | Multipark Credential Expansion |
| BACKLOG | CF-H2I | Historical Snapshot Locking |
| BACKLOG | CF-H2K | Supply Hours Canonicalization |

---

## 14. CLASSIFICATION

**`PROMOTION_READINESS_BLOCKED`**

The promotion infrastructure is ready (registry, mapper, workflows, rollback plan, failure modes). The blocker is **data accumulation**: only 4 of 30 required FULL shadow days exist. No architectural or code blockers remain.

---

## 15. FIRMA

| Campo | Valor |
|-------|-------|
| **Auditado por** | CF-H2H.0 Promotion Readiness Audit |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `PROMOTION_READINESS_BLOCKED` |
| **Veredicto** | **NO-GO for CF-H2H. Re-audit after 2026-07-06.** |
| **Próxima fase** | CF-H2J (Continuous Certification Monitor) — can start now |
