# OV2-C.6 — FALLBACK RETIREMENT PLAN

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix API Certification
> **Status:** PLAN DEFINED

---

## 1. WHY shellToMatrixResponse.js EXISTS

The adapter `frontend/src/pages/omniview-v2-shadow/adapters/shellToMatrixResponse.js` was created in OV2-C.3C because:
- The `/ops/omniview-v2/matrix` endpoint did not exist yet
- The ShadowPage needed a MatrixResponse to render MatrixShell
- The Shell API (`/ops/omniview-v2/shell`) returns section-based data, not matrix cells
- A temporary bridge was needed to convert shell KPIs into matrix cells

---

## 2. CURRENT STATE

| Component | Status |
|-----------|--------|
| /ops/omniview-v2/matrix endpoint | **ACTIVE** — CT day, Yango day supported |
| shellToMatrixResponse.js | **ACTIVE** — fallback only, not used in happy path |
| useOmniviewV2Matrix hook | **ACTIVE** — tries /matrix first, falls back on error |
| Fallback banner | **ACTIVE** — visible when fallback used |

---

## 3. RETIREMENT CONDITIONS

`shellToMatrixResponse.js` can be **removed** when ALL of these are true:

| # | Condition | Current |
|---|-----------|---------|
| 1 | /matrix supports CT_TRIPS_2026 day/week/month | day ✅, week/month ❌ |
| 2 | /matrix supports YANGO_API_RAW day | ✅ |
| 3 | Unsupported grains return empty MatrixResponse with GRAIN_NOT_SUPPORTED | ✅ |
| 4 | 0 fallback activations in QA for ≥5 cycles | Pending |
| 5 | Shadow UI stable (no errors) for ≥5 days | Pending |
| 6 | All frontend matrix views consume /matrix directly | ShadowPage only |
| 7 | Sandbox uses real /matrix (or mock data intentionally) | Mock only |

---

## 4. PROPOSED RETIREMENT PHASE

**Target:** OV2-C.8 (Stabilization & Production Readiness)

**Timeline:**
- OV2-C.6: Add fallback telemetry, document plan (CURRENT)
- OV2-C.7: Add multi-metric support to /matrix
- OV2-C.8: Remove shellToMatrixResponse.js after conditions met

---

## 5. RISKS OF KEEPING IT

| Risk | Severity | Description |
|------|----------|-------------|
| Silent degradation | MEDIUM | If /matrix fails, users see limited shell data without knowing quality differs |
| Maintenance burden | LOW | Adapter must be updated when CellContract changes |
| False sense of stability | MEDIUM | Fallback hides /matrix failures from user awareness |
| Divergent data paths | MEDIUM | Two code paths produce different cell structures |

---

## 6. DETECTION IN PRODUCTION

### Frontend telemetry (added in OV2-C.6):
```javascript
let fallbackActivationCount = 0;
// Incremented each time useOmniviewV2Matrix activates fallback
console.warn("[OV2] MATRIX_FALLBACK_ACTIVE", { reason, count: fallbackActivationCount });
```

### Monitoring:
- **Console filter:** `[OV2] MATRIX_FALLBACK_ACTIVE`
- **UI indicator:** Amber banner "MATRIX_FALLBACK_ACTIVE"
- **Metric:** `fallbackActivationCount` — if >0 in production, investigate /matrix health

---

## 7. RETIREMENT CHECKLIST

- [ ] All retirement conditions met
- [ ] `shellToMatrixResponse.js` deleted
- [ ] `useOmniviewV2Matrix.js` removes fallback import
- [ ] `OmniviewV2ShadowPage.jsx` removes `shellToMatrixResponse` import
- [ ] Fallback banner removed from ShadowPage
- [ ] Build passes
- [ ] V1 unaffected
- [ ] QA cycle passes with 0 errors

---

## 8. SIGN-OFF

| Role | Decision |
|------|----------|
| Retirement plan approved | YES |
| Deferred to OV2-C.8 | YES |
| Telemetry active | YES |
