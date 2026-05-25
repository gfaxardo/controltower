# OMNIVIEW PRE-PROD HARDENING — PRECHECK

**Date**: 2025-05-25
**Phase**: FASE FINAL PRE-PROD — Hardening & Stabilization
**Engine**: Control Foundation (GO) + Diagnostic Engine (ACTIVE 2A.3)

---

## 1. ACTIVE PHASE CONFIRMATION

| Item | Value |
|---|---|
| Active Phase | 1H.4 — Operational Maturity Governance |
| Engine | Control Foundation (GO) |
| Next Engine | Diagnostic Engine (2A.3 — READY NEXT) |
| Omniview hardening | **ALLOWED** (explicitly listed in `ai_current_phase.md`) |
| Forecast/Suggestion/Decision | PROTOTYPE ONLY — NOT ACTIVE |

**Check**: Hardening is within active phase scope.

---

## 2. CURRENT STATE INVENTORY

### What's working
| System | Status |
|---|---|
| `BusinessSliceOmniviewMatrix` | Rendering on `/operacion/omniview-matrix` |
| Evolution mode | Functional |
| Projection mode | Functional + momentum absorbed |
| Momentum Color Authority | Implemented in `ProjectionCellRender` |
| Weekday Focus | Functional on both modes |
| Momentum Priority Strip | Functional on both modes |
| Momentum Drill | Toggle in `OmniviewProjectionDrill` |
| Fullscreen | Works for matrix and drill |
| Sticky headers | Intact |
| Build | PASS (9.74s) |

### What's pending/precarious
| Item | Risk |
|---|---|
| Performance (3799-line component) | MEDIUM — many useMemos, but no explicit performance audit |
| Visual consistency between modes | LOW — same component, same utilities |
| Empty/error states | LOW — SmartEmptyState exists for both modes |
| Dead code accumulated | LOW — 2 dead files, 6 dead APIs, 1 dead import |
| Smoke marker still visible | MUST REMOVE before release |

### What's forbidden to touch
| System | Reason |
|---|---|
| ISO week logic | Core calculation |
| Freshness tracking | Serving governance |
| Trust engine | Operational decision confidence |
| Serving contract | Backend-dependent |
| Core matrix build (`buildMatrix`, `buildProjectionMatrix`) | Contract-stable |
| Root cause engine | Diagnostic integrity |

---

## 3. RISK ASSESSMENT

| Risk | Severity | Mitigation |
|---|---|---|
| Rerender cascade in large matrix (daily) | MEDIUM | Audit useMemo deps, add React.memo where missing |
| Momentum priority recalculation on every render | LOW | Already useMemo'd in OMPS |
| Visual inconsistency (color codes across modes) | LOW | Both use shared `signalColorForKpi` or `momColor` pattern |
| Broken empty state after momentum changes | LOW | Empty state logic untouched; new momentum row is conditional |
| Legacy cleanup breaking something | LOW | Only removing zero-reference dead code |
| Weekday focus wrong for edge dates | LOW | `parseDateFromPeriodKey` handles multiple formats |

---

## 4. ALLOWED CHANGES

- Remove smoke marker
- Audit and fix useMemo dependencies
- Remove dead imports (App.jsx:44 — `RealVsProjectionView`)
- Remove dead API functions from api.js (6 functions)
- Visual consistency tweaks (spacing, opacity)
- Priority strip hardening (limits, ranking)
- Toolbar cleanup (reduce noise)
- Empty state verification

---

## 5. FORBIDDEN CHANGES

- New engines
- New APIs
- Serving contract changes
- ISO week logic changes
- Freshness logic changes
- Trust engine changes
- Matrix structure changes
- Sticky/scroll changes
- New features
- Deleting evolution mode
- Killing legacy routes prematurely
- Refactors of buildMatrix or buildProjectionMatrix

---

## 6. GO / NO-GO

| Criteria | Status |
|---|---|
| Active phase allows hardening | ✅ |
| No engine activation needed | ✅ |
| All forbidden items avoided | ✅ |
| Build currently passes | ✅ |
| Matrix intact | ✅ |
| No regression risk from planned changes | ✅ (only dead code removal + visual tweaks) |

---

## VERDICT: **GO** — READY FOR HARDENING
