# OV2-C.6 — FALLBACK BEHAVIOR QA

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Matrix API Certification
> **Status:** PASS

---

## 1. FALLBACK SCENARIOS

### 1.1 Invalid Source
| Aspect | Behavior |
|--------|----------|
| Cause | Source not in registry (e.g., `INVALID_SOURCE`) |
| /matrix response | HTTP 200 with UNKNOWN_SOURCE warning, empty matrix |
| Hook behavior | `getOmniviewV2Matrix()` returns response with warning |
| Fallback triggered? | **NO** — response is valid, just empty |
| Fallback banner | Not shown |
| User sees | Empty matrix with warning badge |

### 1.2 Endpoint Unavailable (network/server error)
| Aspect | Behavior |
|--------|----------|
| Cause | Backend down, 500, or network timeout |
| Hook behavior | `catch` block triggers fallback |
| Fallback triggered? | **YES** — `shellToMatrixResponse(shellData)` used |
| Fallback banner | **YES** — amber "MATRIX_FALLBACK_ACTIVE" |
| User sees | Matrix from shell adapter (single KPI, limited data) |
| Console | `[OV2] MATRIX_FALLBACK_ACTIVE` + error message |

### 1.3 Unsupported Grain (e.g., Yango week)
| Aspect | Behavior |
|--------|----------|
| Cause | Grain not supported by source |
| /matrix response | HTTP 200 with GRAIN_NOT_SUPPORTED warning, empty matrix |
| Hook behavior | Response received successfully — no error, no fallback |
| Fallback triggered? | **NO** |
| User sees | Empty matrix with warning |

---

## 2. FALLBACK ACTIVATION CHECKLIST

| # | Condition | Fallback? |
|---|-----------|-----------|
| F1 | /matrix returns valid response | NO |
| F2 | /matrix throws network error | YES |
| F3 | /matrix returns 500 | YES |
| F4 | /matrix returns empty but valid | NO |
| F5 | /matrix returns 404 | YES |
| F6 | Shell data also unavailable | Error state shown |

---

## 3. BANNER VISIBILITY

| Source | /matrix OK | /matrix FAIL |
|--------|-----------|-------------|
| CT_TRIPS_2026 | No banner | MATRIX_FALLBACK_ACTIVE + error |
| YANGO_API_RAW | SHADOW MODE banner only | SHADOW MODE + MATRIX_FALLBACK_ACTIVE |

Both banners are distinct:
- SHADOW MODE: amber, full-width, always for Yango
- MATRIX_FALLBACK_ACTIVE: amber/yellow, only when fallback active

---

## 4. ERROR RECOVERY

| Action | Behavior |
|--------|----------|
| Source switch | New request to /matrix, fallback state cleared |
| Grain switch | New request, fallback cleared |
| Period change | New request, fallback cleared |
| Page reload | Fresh start, no fallback |

Fallback state is **per-request**, not persisted.

---

## 5. VERDICT

**FALLBACK BEHAVIOR QA: PASS**

Fallback activates only on real errors. Does NOT activate on valid empty/warning responses. Banner clearly visible when active. State clears on any filter change. No white screens.
