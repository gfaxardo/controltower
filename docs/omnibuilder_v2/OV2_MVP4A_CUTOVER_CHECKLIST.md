# OV2-MVP.4A — CUTOVER CHECKLIST

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Cutover Checklist
> **Fecha:** 2026-06-12
> **Status:** DO NOT EXECUTE YET

---

## PRE-CUTOVER (ALL must be YES)

### Trial & Acceptance

| # | Check | Required | Status |
|---|-------|----------|--------|
| 1 | Trial completed (2 weeks) | YES | PENDING |
| 2 | Acceptance score ≥ 85 | YES | PENDING |
| 3 | V2/V1 ratio ≥ 3:1 during trial | YES | PENDING |
| 4 | Operator confidence ≥ 4/5 | YES | PENDING |
| 5 | 0 P0 frictions open | YES | PENDING |

### Data & Serving

| # | Check | Required | Status |
|---|-------|----------|--------|
| 6 | V2 data matches V1 for all P0 tasks | YES | VERIFIED |
| 7 | CT serving facts fresh (< 1 day) | YES | VERIFIED |
| 8 | Reconciliation endpoint shows MATCH for core KPIs | YES | PARTIAL |
| 9 | No serving fact corruption | YES | VERIFIED |

### Technical Readiness

| # | Check | Required | Status |
|---|-------|----------|--------|
| 10 | V1_LEGACY_MODE flag implemented | YES | NOT STARTED |
| 11 | Rollback runbook tested | YES | NOT STARTED |
| 12 | Rollback time < 5 minutes verified | YES | NOT STARTED |
| 13 | All V2 endpoints return 200 | YES | VERIFIED |
| 14 | Infra-health endpoint shows pool OK | YES | VERIFIED |

### Training

| # | Check | Required | Status |
|---|-------|----------|--------|
| 15 | Training guide distributed | YES | NOT STARTED |
| 16 | Training session completed | YES | NOT STARTED |
| 17 | All operators aware of V1 legacy banner | YES | NOT STARTED |

### Signoff

| # | Check | Required | Status |
|---|-------|----------|--------|
| 18 | Operations lead signoff | YES | PENDING |
| 19 | Engineering lead signoff | YES | PENDING |
| 20 | PMO signoff | YES | PENDING |

---

## CUTOVER DAY

### Morning (before activation)

- [ ] Verify V1 is working normally
- [ ] Verify V2 is working normally  
- [ ] Check health endpoints green
- [ ] Notify team: cutover happening today

### Activation

- [ ] Set `V1_LEGACY_MODE=true` on backend
- [ ] Rebuild frontend with `VITE_V1_LEGACY_MODE=true`
- [ ] Verify V1 shows "V1 LEGACY" banner
- [ ] Verify V2 is default route
- [ ] Verify V1 still accessible directly

### Post-Activation Monitoring

- [ ] Monitor errors for 1 hour
- [ ] Check V2/V1 ratio
- [ ] Collect operator feedback (midday)
- [ ] Resolve any P0 frictions immediately

### End of Day

- [ ] No P0 frictions
- [ ] V2/V1 ratio ≥ 5:1
- [ ] Operators report no blockers
- [ ] Decide: continue or rollback?

---

## POST-CUTOVER (Week 1)

- [ ] Daily checkpoint (sessions, frictions, blocked tasks)
- [ ] No P0 frictions after day 3
- [ ] V1 usage drops to near-zero

## POST-CUTOVER (Week 2)

- [ ] V1 usage = 0 (or verification only)
- [ ] All operators comfortable with V2
- [ ] Final acceptance score ≥ 90

## POST-CUTOVER (Month 1)

- [ ] V1 routes can be removed from nav
- [ ] V1 code can be archived
- [ ] V1 endpoints can be deprecated (30-day notice)

---

## STATUS

| Category | Done | Total | % |
|----------|------|-------|---|
| Pre-cutover | 5 | 20 | 25% |
| Cutover day | 0 | 0 | — |
| Post-cutover | 0 | 0 | — |

**Cutover is NOT ready. Trial must complete first.**
