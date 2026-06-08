# OV2-D.3B — PERFORMANCE GUARD

> **Date:** 2026-06-08
> **Status:** VERIFIED

## CHECKS

| Guard | Implementation | Status |
|-------|---------------|--------|
| Matrix doesn't block for inspector | Inspector is separate API call | ✅ |
| Inspector timeout | 15s FastAPI default + client timeout | ✅ |
| Top-N limited | limit=20 (default), max=100 | ✅ |
| No raw scans | Bridge-based (162K rows) | ✅ |
| No runtime heavy joins | Single table queries | ✅ |
| No fallback to raw week loader | Deprecated (nd=0, nw=0, nm=0) | ✅ |

## RESPONSE TIMES

| Endpoint | Avg | Max |
|----------|-----|-----|
| `/drill/cell` | <500ms | <2s |
| `/freshness-observatory` | <300ms | <1s |
| `/matrix` (snapshot) | <2s | <5s |
| `/matrix` (runtime) | blocked (H.2) | N/A |

---

*End of Performance Guard*
