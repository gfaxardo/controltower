# OV2-C.8 — FALLBACK RETIREMENT REPORT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Fallback Retirement
> **Overall Status:** **PASS — FALLBACK RETIRED (DEBUG-ONLY)**

---

## 1. EXECUTIVE SUMMARY

The temporary `shellToMatrixResponse.js` adapter is now **disabled by default**. The Shadow UI depends exclusively on the real `/ops/omniview-v2/matrix` endpoint. Fallback is only available via explicit environment flag `VITE_OV2_ALLOW_MATRIX_FALLBACK=true` for local debugging.

---

## 2. GOVERNANCE

| Rule | Status |
|------|--------|
| Control Foundation | Active |
| No V1 touched | PASS |
| No serving productivo changed | PASS |
| YANGO_API_RAW canonical_ready=false | PASS |
| All additive | PASS |

---

## 3. DECISION

**Fallback: RETIRED → DEBUG-ONLY**

| Aspect | Before | After |
|--------|--------|-------|
| Default behavior on /matrix error | Silent fallback to shell adapter | Error state in UI with retry |
| Fallback activation | Automatic | Only when `VITE_OV2_ALLOW_MATRIX_FALLBACK=true` |
| User awareness | None (degraded data invisible) | Error message + source/grain/date context |
| Adapter file | Active import | Conditional import (still in codebase) |

---

## 4. FILES MODIFIED

| File | Change |
|------|--------|
| `hooks/useOmniviewV2Matrix.js` | Fallback gated by env flag. Error exposed when disabled. |
| `OmniviewV2ShadowPage.jsx` | Matrix error state with context + retry. Removed silent shellToMatrixResponse default. |
| `OV2_C8_FALLBACK_USAGE_AUDIT.md` | Created |
| `OV2_C8_FALLBACK_ENVIRONMENT_FLAG.md` | Created |
| `OV2_C8_FALLBACK_RETIREMENT_REPORT.md` | This file |

---

## 5. QA SCENARIOS

| # | Scenario | Expected Result |
|---|----------|----------------|
| 1 | CT day happy path | Matrix renders. No fallback. No error. |
| 2 | CT week happy path | Matrix renders. No fallback. |
| 3 | CT month happy path | Matrix renders. No fallback. |
| 4 | Yango day happy path | Matrix renders. No fallback. |
| 5 | Yango week unsupported | Empty matrix with GRAIN_NOT_SUPPORTED. No error state. |
| 6 | Invalid source | Empty matrix with UNKNOWN_SOURCE. No error state. |
| 7 | Flag=true + /matrix error | Fallback activates. Banner visible. |

---

## 6. BUILD QA

| Check | Result |
|-------|--------|
| Build | PASS |
| Forbidden patterns | 0 |
| Hardcoded hex | 0 |
| V1 intact | All chunks present |

---

## 7. RISKS

| Risk | Status |
|------|--------|
| Adapter code still in codebase | LOW — gated by env flag, documented for removal after 30 days |
| /matrix errors now visible to users | ACCEPTABLE — transparency over silent degradation |

---

## 8. DECISION

**GO for OV2-C.9**

All conditions met:
- Fallback disabled by default
- /matrix mandatory in happy path
- Real errors visible in UI
- No silent data substitution
- Build PASS
- V1 intact
