# UI Legacy Endpoint Scan — Action Engine & Top Driver Behavior (Phase 13)

**Project:** YEGO Control Tower  
**Date:** 2026-03-11

---

## Scope

Confirm that **Action Engine** and **Top Driver Behavior** use **only** the allowed `/ops/*` endpoints. Reject usage of `/controltower/*`, legacy behavior-alerts paths used by the wrong module, or old MVs.

---

## Action Engine — Endpoints Used

| Required | Endpoint | Used by frontend |
|----------|----------|-------------------|
| ✓ | `/ops/action-engine/summary` | Yes — `getActionEngineSummary()` in api.js → ActionEngineView |
| ✓ | `/ops/action-engine/cohorts` | Yes — `getActionEngineCohorts()` |
| ✓ | `/ops/action-engine/cohort-detail` | Yes — `getActionEngineCohortDetail()` |
| ✓ | `/ops/action-engine/recommendations` | Yes — `getActionEngineRecommendations()` |
| ✓ | `/ops/action-engine/export` | Yes — `getActionEngineExportUrl()` |

**No legacy endpoints detected.** Action Engine uses only the five endpoints above via `api.js`. No references to `/controltower/*` in the frontend.

---

## Top Driver Behavior — Endpoints Used

| Required | Endpoint | Used by frontend |
|----------|----------|-------------------|
| ✓ | `/ops/top-driver-behavior/summary` | Yes — `getTopDriverBehaviorSummary()` |
| ✓ | `/ops/top-driver-behavior/benchmarks` | Yes — `getTopDriverBehaviorBenchmarks()` |
| ✓ | `/ops/top-driver-behavior/patterns` | Yes — `getTopDriverBehaviorPatterns()` |
| ✓ | `/ops/top-driver-behavior/playbook-insights` | Yes — `getTopDriverBehaviorPlaybookInsights()` |
| ✓ | `/ops/top-driver-behavior/export` | Yes — `getTopDriverBehaviorExportUrl()` |

**No legacy endpoints detected.** Top Driver Behavior uses only the five endpoints above.

---

## Behavioral Alerts (separate module)

The **Behavioral Alerts** tab is a distinct module and correctly uses:

- `/ops/behavior-alerts/summary`
- `/ops/behavior-alerts/insight`
- `/ops/behavior-alerts/drivers`
- `/ops/behavior-alerts/driver-detail`
- `/ops/behavior-alerts/export`

These are **not** legacy; they are the intended paths for the Behavioral Alerts feature.

---

## Legacy / Rejected Paths

| Path | Status |
|------|--------|
| `/controltower/*` | Not used by any scanned component. Backend has a `controltower` router; frontend does not call it. |
| Legacy endpoints | No references found in frontend to deprecated or alternate action-engine/behavior-alerts URLs. |

---

## Conclusion

- **Action Engine:** Uses only `/ops/action-engine/*` (summary, cohorts, cohort-detail, recommendations, export).
- **Top Driver Behavior:** Uses only `/ops/top-driver-behavior/*` (summary, benchmarks, patterns, playbook-insights, export).
- **No automatic removal** was performed; no legacy usage was found to remove.
