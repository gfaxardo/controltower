# OV2-C.8 — FALLBACK ENVIRONMENT FLAG

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Fallback Retirement

---

## 1. FLAG: VITE_OV2_ALLOW_MATRIX_FALLBACK

| Attribute | Value |
|-----------|-------|
| Variable | `VITE_OV2_ALLOW_MATRIX_FALLBACK` |
| Default | `false` |
| Type | boolean string (`"true"` or anything else = false) |
| Scope | Build-time (Vite env) |
| Used in | `hooks/useOmniviewV2Matrix.js` |

---

## 2. BEHAVIOR

### When `false` (DEFAULT — production, CI, most dev)

| /matrix status | UI behavior |
|---------------|-------------|
| Success | Matrix renders with real data |
| Error | Matrix zone shows error state with: error code, source, grain, date range, retry button |
| Empty (valid) | MatrixEmptyState shown |

Product Shell sections remain visible even if matrix fails. Only the matrix zone shows the error.

### When `true` (DEBUG ONLY)

| /matrix status | UI behavior |
|---------------|-------------|
| Success | Matrix renders with real data |
| Error | **Fallback activates:** shell→MatrixResponse conversion. Banner: "MATRIX_FALLBACK_ACTIVE — DEBUG ONLY" |
| Empty (valid) | MatrixEmptyState shown |

---

## 3. HOW TO ENABLE

Create `.env.local` in `frontend/`:

```bash
VITE_OV2_ALLOW_MATRIX_FALLBACK=true
```

Restart dev server after changing.

---

## 4. HOW TO VERIFY

### In browser console:
```
// When fallback is active and enabled:
[OV2] MATRIX_FALLBACK_ACTIVE — DEBUG ONLY { reason: "...", count: 1, timestamp: "..." }

// When fallback would be needed but is disabled:
// Matrix zone shows error state. No console warning.
```

### In UI:
- **Amber banner visible:** "MATRIX_FALLBACK_ACTIVE" → fallback is ON
- **No amber banner, matrix shows error:** fallback is OFF → working correctly
- **No amber banner, matrix shows data:** happy path → /matrix is working

---

## 5. PRODUCTION RULES

| Rule | Enforcement |
|------|------------|
| `VITE_OV2_ALLOW_MATRIX_FALLBACK` must NOT be `true` in production | Env file not deployed |
| Build-time flag only | Cannot be toggled at runtime |
| No localStorage override | Not implemented (would violate "no localStorage without versioning") |

---

## 6. RETIREMENT COMPLETE WHEN

- [x] Fallback disabled by default
- [x] /matrix errors visible in UI
- [x] Debug flag documented
- [ ] 0 fallback activations in production for 30 days → can delete shellToMatrixResponse.js
