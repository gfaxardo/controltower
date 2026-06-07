# OV2-C.8 — FALLBACK USAGE AUDIT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Fallback Retirement
> **Decision:** **REMOVE** — converted to debug-only via env flag

---

## 1. FILES AUDITED

| File | Role |
|------|------|
| `adapters/shellToMatrixResponse.js` | TEMPORARY adapter — converts Shell API response to MatrixResponse |
| `hooks/useOmniviewV2Matrix.js` | Matrix data hook — tries /matrix, falls back to shell adapter |
| `OmniviewV2ShadowPage.jsx` | Main shadow page — consumes matrix data |
| `services/api.js` | API client — getOmniviewV2Matrix() |

---

## 2. WHEN FALLBACK ACTIVATES

| Scenario | Before (OV2-C.5/C.6) | After (OV2-C.8) |
|----------|----------------------|-----------------|
| /matrix works | No fallback | No fallback |
| /matrix network error | **Silent fallback** to shell adapter | Error shown in UI. No fallback (default). |
| /matrix 500 | **Silent fallback** to shell adapter | Error shown in UI. No fallback (default). |
| Invalid source | Valid empty response — no fallback | Same |
| Unsupported grain | Valid empty response — no fallback | Same |

**Key change:** Silent fallback → visible error. User knows /matrix is broken.

---

## 3. WHAT ERRORS WERE BEING HIDDEN

The silent fallback was hiding:
- Network connectivity issues to /matrix endpoint
- Backend 500 errors
- Schema mismatches between Shell and Matrix contracts
- Missing data: shell adapter shows limited KPI data while /matrix would show richer data

---

## 4. RISKS OF KEEPING ACTIVE FALLBACK

| Risk | Severity |
|------|----------|
| Users see degraded data without knowing | HIGH |
| /matrix failures go undetected | HIGH |
| Two code paths produce different cell structures | MEDIUM |
| Adapter must be maintained alongside real endpoint | LOW |

---

## 5. DECISION

| Option | Chosen? |
|--------|---------|
| REMOVE completely | NO — kept for debug |
| KEEP_DEBUG_ONLY | **YES** — only active when `VITE_OV2_ALLOW_MATRIX_FALLBACK=true` |
| KEEP_TEMPORARY | NO |

The adapter remains in the codebase for local debugging but is **disabled by default** in all environments including production.

---

## 6. DEBUG ACTIVATION

```bash
# .env.local (development only)
VITE_OV2_ALLOW_MATRIX_FALLBACK=true
```

When enabled:
- Failed /matrix requests fall back to shell adapter
- Amber banner: "MATRIX_FALLBACK_ACTIVE — DEBUG ONLY"
- Console: `[OV2] MATRIX_FALLBACK_ACTIVE`

When disabled (default):
- Failed /matrix requests show error state with retry button
- No fallback
- Error clearly visible in UI
