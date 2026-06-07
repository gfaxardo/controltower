# OV2-C.4 — ERROR STATE QA

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Shadow UI Hardening
> **Status:** PASS

---

## 1. ERROR SCENARIOS

### 1.1 Backend Unavailable
| Aspect | Behavior |
|--------|----------|
| Cause | API server down or unreachable |
| Component | `OmniviewV2ShadowPage.jsx` error branch |
| Visual | Error message + Retry button |
| Crash? | No — caught by error state in page component |
| White screen? | No — renders error UI with header |
| Retry | Button calls `refetch()` |

### 1.2 Invalid Source
| Aspect | Behavior |
|--------|----------|
| Cause | `source_system` parameter not in registry |
| Component | Backend returns UNKNOWN_SOURCE warning |
| Visual | Error state if shell fails; warning badge if partial |
| Crash? | No |

### 1.3 Period Without Data
| Aspect | Behavior |
|--------|----------|
| Cause | Date range with no records in source |
| Component | `MatrixShell` receives `row_count=0` |
| Visual | `MatrixEmptyState` with "No data available" message |
| Crash? | No |
| User guidance | "Try adjusting the period or grain selector." |

### 1.4 Yango Without Data
| Aspect | Behavior |
|--------|----------|
| Cause | YANGO_API_RAW has no data for selected period |
| Component | Shell returns warnings, matrix shows empty |
| Visual | WARNING badges, empty matrix |
| Safety banner | Still visible ("SHADOW MODE") |

### 1.5 Unsupported Grain
| Aspect | Behavior |
|--------|----------|
| Cause | Grain not supported by selected source (e.g., week for Yango) |
| Component | Backend returns GRAIN_NOT_SUPPORTED warning |
| Visual | Warning in alert strip, matrix may be empty |
| Crash? | No |

---

## 2. EDGE STATE CHECKS

| # | State | Verified? |
|---|-------|-----------|
| E1 | No source selected | N/A — dropdown always has a value |
| E2 | No period selected | Handled — defaults to today |
| E3 | Compare mode with missing source | N/A — compare not yet wired to UI |
| E4 | Rapid filter changes | AbortController cancels previous request |
| E5 | Browser back/forward | React Router handles navigation |

---

## 3. COMPONENT ERROR BOUNDARIES

| Component | Protection |
|-----------|-----------|
| OmniviewV2ShadowPage | Try/catch in hook + error state in component |
| OmniviewV2MatrixSandbox | Wraps in OmniviewErrorBoundary (App.jsx) |
| MatrixShell | Defensive checks: `!matrixData || !matrixData.metadata || row_count === 0` → EmptyState |
| MatrixCell | Defensive: `!cell` → muted empty cell |

---

## 4. LOADING STATES

| State | Visual |
|-------|--------|
| Initial load | MatrixSkeleton (10 rows × 7 cols) |
| Source switch | Old data visible until new data arrives (no flash) |
| Error | Error message + Retry button |
| Empty | MatrixEmptyState with guidance text |

---

## 5. VERDICT

**ERROR STATE QA: PASS** — No white screens. All error/empty/loading states handled. Defensive checks on all data-dependent components.
