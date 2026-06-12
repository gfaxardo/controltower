# OV2-MVP.4A — ROLLBACK RUNBOOK

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Rollback Runbook
> **Fecha:** 2026-06-12

---

## 1. SCENARIO CLASSIFICATION

### P0 ROLLBACK — EMERGENCY (immediate, no approval needed)

| Trigger | Action |
|---------|--------|
| V2 returns wrong data for P0 tasks (trips, revenue, drivers) | Immediate rollback |
| V2 matrix shows blank/error for all users | Immediate rollback |
| V2 endpoint returns 500 for > 5 consecutive requests | Immediate rollback |
| Data corruption detected in V2 serving path | Immediate rollback |

### P1 ROLLBACK — URGENT (same day)

| Trigger | Action |
|---------|--------|
| V2/V1 ratio drops below 1:1 after cutover | Rollback within 4h |
| > 5 P0 frictions in 1 day after cutover | Rollback within 8h |
| Acceptance score drops below 70 post-cutover | Rollback within 24h |

### P2 ROLLBACK — PLANNED (scheduled)

| Trigger | Action |
|---------|--------|
| Performance degradation (matrix > 10s) | Schedule rollback in next maintenance window |
| UX confusion causing operator slowdown | Rollback after investigation |

---

## 2. ROLLBACK PROCEDURE (P0)

```
TIME: < 5 minutes
OWNER: Backend engineer on call

Step 1: Set env var
  export V1_LEGACY_MODE=false

Step 2: Restart backend (or wait for env reload)
  systemctl restart controltower-api

Step 3: Rebuild frontend (if build-time flag)
  VITE_V1_LEGACY_MODE=false npm run build
  cp -r dist/* /var/www/controltower/

Step 4: Verify V1 accessible
  curl http://localhost:8000/ops/business-slice/monthly

Step 5: Verify V1 is default route
  Open browser → Operacion tab → should show Omniview Matrix

Step 6: Notify team
  "V1 LEGACY MODE ROLLED BACK. V1 is default. V2 is shadow. Investigating."

Step 7: Log rollback reason
  Document in friction log as P0 rollback event

Total time: < 5 minutes
```

---

## 3. ROLLBACK VERIFICATION

| Check | Method | Expected |
|-------|--------|----------|
| V1 accessible | Browser → `/operacion/omniview-matrix` | Matrix loads with data |
| V1 not showing legacy banner | Browser check | No "V1 LEGACY" banner |
| V2 still accessible | Browser → `/operacion/omniview-v2-shadow` | V2 loads (shadow mode) |
| Production data unchanged | Query day_fact | Same row counts as before |
| No 500 errors | Health endpoint | All services OK |

---

## 4. POST-ROLLBACK

1. **Investigate root cause** — what triggered the rollback?
2. **Fix the issue** — P0 within 24h, P1 within trial week
3. **Re-validate** — run acceptance score, smoke tests
4. **Re-attempt cutover** — only after fix verified
5. **Update runbook** — if new scenario discovered

---

## 5. ROLLBACK LOG

| Date | Trigger | Severity | Duration | Root Cause | Resolution |
|------|---------|----------|----------|------------|------------|
| — | — | — | — | — | — |

---

## 6. PREVENTION

| Risk | Prevention |
|------|-----------|
| Wrong data in V2 | Reconciliation endpoint (/reconciliation/park) run before cutover |
| 500 errors | Infra-health endpoint monitored |
| UX confusion | Training completed before cutover |
| Unprepared ops team | Survey confirming readiness |
