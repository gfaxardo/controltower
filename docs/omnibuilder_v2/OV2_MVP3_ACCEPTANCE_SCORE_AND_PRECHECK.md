# OV2-MVP.3 — ACCEPTANCE SCORE MODEL + DEPRECATION PRECHECK

> **Fase:** OV2-MVP.3 — Operational Acceptance Trial
> **Sub-document:** Score Model + Precheck
> **Fecha:** 2026-06-12

---

## 1. ACCEPTANCE SCORE FORMULA

```
Score = (Coverage × 0.30) + (Usability × 0.25) + (Reliability × 0.20) + (Performance × 0.15) + (Confidence × 0.10)
```

Range: 0-100. Deterministic. No AI.

### Coverage (30%)

```
Coverage = (PASS_tasks / TOTAL_tasks) × 100
Source: Critical Task Inventory (21 tasks)
Weight: Each task equally weighted
```

**Current: 19/21 = 90.5% (commission + ECharts pending)**

### Usability (25%)

```
Usability = 100 - (P0_frictions × 10) - (P1_frictions × 5) - (P2_frictions × 2)
Floor: 0
```

**Current: 100 (trial not started, 0 frictions)**

### Reliability (20%)

```
Reliability = 100 - (errors_per_100_sessions × 5)
Floor: 0
Source: Server-side error counts / session counts
```

**Current: To be measured during trial**

### Performance (15%)

```
Performance = 100 if avg_matrix_ms < 2000
            = 85  if avg_matrix_ms < 5000
            = 60  if avg_matrix_ms < 10000
            = 30  otherwise
```

**Current: ~750ms (estimated from backend benchmark)**

### Confidence (10%)

```
Confidence = survey_score × 20
Survey: "Confio en V2 para mis tareas diarias" (1-5 scale)
```

**Current: Pending operator survey**

---

## 2. ACCEPTANCE THRESHOLDS

| Score | Classification | Action |
|-------|---------------|--------|
| ≥ 85 | **ACCEPTED** | GO for V1 Deprecation |
| 70-84 | **CONDITIONAL** | Extend trial 1 week, fix top frictions |
| < 70 | **REJECTED** | Return to build phase |

---

## 3. DEPRECATION READINESS PRECHECK

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | All P0 tasks complete in V2 | **PASS** | 9/9 |
| 2 | V2/V1 ratio ≥ 3:1 | **PENDING** | Trial not started |
| 3 | 0 critical V1 dependencies | **PASS** | V1 dependency audit: 0 HIGH/CRITICAL |
| 4 | Acceptance score ≥ 85% | **PENDING** | Trial not started |
| 5 | ≤ 5 P0/P1 frictions | **PENDING** | Trial not started |
| 6 | V1 flag exists for quick rollback | **NOT STARTED** | `V1_LEGACY_MODE` flag to be implemented in MVP.4 |
| 7 | V2 route is production-ready | **NOT STARTED** | Currently `productionReady: false`. Needs flag flip in MVP.4 |
| 8 | Operations team trained on V2 | **NOT STARTED** | Training session needed before deprecation |
| 9 | V1 deprecation runbook exists | **NOT STARTED** | Runbook to be created in MVP.4 |
| 10 | Redirect map V1 → V2 exists | **NOT STARTED** | Route mapping to be created in MVP.4 |

---

## 4. WHAT'S MISSING FOR V1 DEPRECATION?

| # | Item | Phase |
|---|------|-------|
| 1 | Trial complete with acceptance score ≥ 85% | OV2-MVP.3 (current) |
| 2 | V1_LEGACY_MODE flag + rollback test | OV2-MVP.4 |
| 3 | productionReady: true for V2 | OV2-MVP.4 |
| 4 | V2 as default route (redirect V1) | OV2-MVP.4 |
| 5 | Deprecation runbook | OV2-MVP.4 |
| 6 | Operations training session | OV2-MVP.4 |
| 7 | 1-week dry-run with V1 hidden | OV2-MVP.4 |

---

## 5. CLASSIFICATION

**`OV2_DEPRECATION_READY_WITH_GAPS`**

Pre-check score: 3/10 criteria met (pre-trial). Expected to reach 7/10 after trial completion. Remaining 3 items (flag, training, runbook) are MVP.4 deliverables.
