# BEHAVIORAL PATTERN DIAGNOSIS — PRECHECK

**Date**: 2025-05-25
**Motor**: Diagnostic Engine (2A.2 → 2A.3)
**Phase**: Behavioral Pattern Diagnosis Architecture

---

## 1. ACTIVE PHASE CONFIRMATION

| Item | Value |
|---|---|
| Current Engine | Control Foundation (GO) + Diagnostic (ACTIVE 2A.3) |
| Diagnostic Layer | CLOSED (Stage 7) — severity, explanation, signal quality done |
| Behavioral Pattern Diagnosis | READY NEXT (per Closure Report §6) |
| Forecast/Suggestion/Action | PROTOTYPE ONLY |
| AI Copilot/Learning | BACKLOG |

**Check**: Behavioral Pattern Diagnosis is explicitly the NEXT block. Pre-work (severity, explanation, signal quality) is done.

---

## 2. EXISTING INFRASTRUCTURE — ALREADY BUILT

### Backend Services

| File | Lines | Purpose |
|---|---|---|
| `backend/app/services/behavioral_pattern_diagnosis_service.py` | 499 | Core diagnosis engine — 12 dimensions, group comparisons, strength classification, caching |
| `backend/app/services/driver_behavior_benchmarking_service.py` | — | Driver lifecycle classification, group benchmarks |
| `backend/app/routers/behavioral_pattern_diagnosis.py` | 111 | 4 API endpoints (summary, patterns, group-profile, decline-signals) |
| `backend/app/services/behavior_alerts_service.py` | — | Behavior alerts for deviation detection |

### 12 DIMENSIONS (already defined in service)

| # | Dimension | Category |
|---|---|---|
| 1 | `activity_volume` | Productivity |
| 2 | `consistency` | Stability |
| 3 | `productivity` | Productivity |
| 4 | `recency` | Temporal |
| 5 | `weekday_weekend` | Temporal |
| 6 | `city_mix` | Geographic |
| 7 | `park_mix` | Geographic |
| 8 | `lob_mix` | Operational |
| 9 | `revenue_efficiency` | Productivity |
| 10 | `time_efficiency` | Productivity |
| 11 | `distance_efficiency` | Productivity |
| 12 | `cancellation_behavior` | Operational Discipline |

### 8 Lifecycle Groups (already defined)

| # | Group | Description |
|---|---|---|
| 1 | `TOP_PERFORMER` | Highest-performing drivers |
| 2 | `STABLE` | Consistent, reliable performers |
| 3 | `GROWING` | Increasing activity |
| 4 | `DECLINING` | Decreasing performance |
| 5 | `AT_RISK` | At risk of churn/inactivity |
| 6 | `DORMANT` | Inactive |
| 7 | `CHURNED` | Left the platform |
| 8 | `REACTIVATED` | Returned after inactivity |

### 4 API Endpoints (already live)

| Method | Path | Purpose |
|---|---|---|
| GET | `/behavioral-patterns/summary` | Counts by strength, available dimensions |
| GET | `/behavioral-patterns/patterns` | Full pattern list with comparisons |
| GET | `/behavioral-patterns/group-profile` | Profile of a lifecycle group |
| GET | `/behavioral-patterns/decline-signals` | Signals comparing STABLE vs DECLINING/AT_RISK |

### Frontend Diagnostic Infrastructure

| File | Purpose |
|---|---|
| `utils/operationalDecisionSeverity.js` | 6 severity levels, centralized thresholds |
| `utils/operationalAttentionRouting.js` | Stable sorting, partitioning |
| `utils/diagnosticExplanationEngine.js` | 17 diagnostic factors, dominant factor |
| `components/operational/DecisionSeverityBadge.jsx` | Severity badge UI |
| `components/diagnostics/DiagnosticDominantFactor.jsx` | Dominant factor display |
| `components/diagnostics/DiagnosticFactorBadge.jsx` | Factor badge UI |

---

## 3. WHAT EXISTS vs WHAT IS NEEDED

| Feature | Exists? | Status |
|---|---|---|
| Driver lifecycle classification | ✅ | `driver_behavior_benchmarking_service.py` |
| Group comparison engine | ✅ | `_compare_groups_for_patterns()` |
| Dimension definitions (12) | ✅ | `DIMENSIONS` constant |
| Strength classification | ✅ | `_determine_strength()` |
| Decline signal detection | ✅ | `get_pattern_diagnosis_decline_signals()` |
| Diagnostic contract (JSON) | ❌ | Needs documentation |
| Behavioral signal inventory | ❌ | Needs documentation |
| Frontend integration to Omniview Matrix | ❌ | Pending — connect to existing Projection model |
| Diagnostic UI panel | PARTIAL | Components exist (SeverityBadge, DominantFactor) but not wired to Omniview |

---

## 4. RULES

### Allowed
- Diagnostic explanations (WHY)
- Group comparisons
- Deterministic thresholds
- Behavioral signal detection
- Dimension-based analysis
- Integration into existing Omniview views

### Forbidden
- "Haz esto" / "Recommend" / "Llama a"
- AI / LLM / Embeddings
- Forecast predictions
- Automated decisions
- New scoring models
- New API calls (all data from existing endpoints)
- New engines (Suggestion, Action, etc.)

---

## 5. RISKS

| Risk | Severity | Mitigation |
|---|---|---|
| 12 dimensions complex to render | LOW | Phase rollout: start with top 4 (productivity, consistency, activity_volume, cancellation) |
| Diagnosis might imply recommendations | LOW | Existing governance docs + automated text scan |
| Frontend integration into Omniview | MEDIUM | New component row inside existing panel architecture |
| DB query performance | LOW | Cache TTL already in place (300s) |

---

## 6. GO / NO-GO

| Criteria | Status |
|---|---|
| Active engine allows Diagnostic work | ✅ |
| Pre-work complete (severity, explanation, QA) | ✅ |
| Backend services already built | ✅ |
| API endpoints already live | ✅ |
| Dimensions already defined | ✅ |
| Lifecycle groups already defined | ✅ |
| No Suggestion/Forecast/AI activation | ✅ |
| Deterministic logic only | ✅ |

---

## VERDICT: **GO** — DEFINE CONTRACT AND ARCHITECTURE

Backend is ready. Frontend diagnostic components exist but need wiring to Omniview. This phase defines the contract and connection points.
