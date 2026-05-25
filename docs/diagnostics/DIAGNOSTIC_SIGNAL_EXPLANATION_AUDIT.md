# DIAGNOSTIC SIGNAL EXPLANATION AUDIT

**Date**: 2026-05-25
**Phase**: Stage 5 — Diagnostic Explanation Layer

---

## reusable_now — Señales explicativas ya existentes y consistentes

### Trust & Confidence (Matrix)
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| `trust_status` | data_trust_service | string (ok/warning/blocked) | WHY blocked: "Trust layer blocked" |
| `confidence.score` | omniview_matrix_integrity_service | number (0-100) | "Confidence degraded to {score}" |
| `confidence.coverage` | trust integrity | number | "Coverage: {value}" |
| `confidence.freshness` | trust integrity | number | "Freshness: {value}" |
| `confidence.consistency` | trust integrity | number | "Consistency: {value}" |
| `hard_cap.code` | trust integrity | string | "Penalized by {code}" |
| `hard_cap.reason` | trust integrity | string | Reason text |

### Freshness
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| Global `status` | data-freshness/global | string | "Data freshness: {status}" |
| `lag_days` | freshness service | number | "Lag: {lag_days}d" |
| `derived_max_date` | pipeline health | date | "Data up to: {date}" |
| `data_freshness.status` | matrix freshness | string | "Freshness: {status}" |

### Comparison & Plan
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| `comparison_status` | projection_expected_progress | string (matched/missing_plan/plan_without_real) | "Missing plan data" / "No real data to compare" |
| `dominant_driver` | Phase2B weekly | string (UNIT/VOL) | "Driven by {driver}" |
| `efecto_volumen` | Phase2B weekly | number | "Volume effect: {currency}" |
| `efecto_unitario` | Phase2B weekly | number | "Unit effect: {currency}" |

### Gaps & Deviations (Weekly)
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| `gap_revenue_pct` | Phase2B weekly | number | "Revenue gap: {pct}%" |
| `gap_trips_pct` | Phase2B weekly | number | "Trips gap: {pct}%" |
| `gap_unitario_pct` | Phase2B weekly | number | "Unit gap: {pct}%" |
| `unit_alert` | Phase2B weekly | boolean | "Unit alert triggered" |
| `why` (alert explanation) | Phase2B weekly | string | Free text explanation |

### Loyalty
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| `data_complete` | yango_loyalty_service | boolean | "Incomplete data for scoring" |
| `manual_kpis_pending` | loyalty service | number | "{n} KPIs pending manual entry" |
| `has_any_targets` | loyalty service | boolean | "No targets configured" |
| `reachability` | loyalty service | string | "Reachability: {status}" |

### Serving & Coverage
| Signal | Source | Format | Explanation Value |
|--------|--------|--------|-------------------|
| `coverage_pct` | matrix integrity | number | "Coverage: {pct}%" |
| `unmapped_trips` | matrix integrity | number | "{n} unmapped trips" |
| `fact_layer.status` | matrix meta | string | "Fact layer empty/serving failure" |

---

## reusable_with_mapping — Existen pero requieren normalización

| Signal | Current Format | Normalized |
|--------|---------------|-----------|
| `severity` (P0/P1/P2/P3) | Backend enum, inconsistent across services | → diagnostic factor based on threshold |
| `alert_severity` | String, varies by alert source | → canonical severity → diagnostic factor |
| `why` (alert text) | Free text from backend | → Can be used as-is in breakdown |
| `playbook.recommended_action` | Matrix executive | → **PROHIBITED for diagnostic layer** (this crosses into Suggestion) |
| `playbook.operational_meaning` | Matrix executive | → Acceptable as explanation, not as recommendation |
| `executive.main_issue.description` | Matrix executive | → Reusable as explanation text |

---

## unavailable — No existen (NO inventar)

- Causalidad compleja (multi-variable correlation)
- Market/external factor inference
- Driver behavior attribution
- Algorithmic root cause (beyond what's in `why` text)
- Predictive diagnostic (forecast of degradation)
