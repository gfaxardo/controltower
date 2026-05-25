# OPERATIONAL DECISION SIGNAL AUDIT

**Date**: 2026-05-25

---

## usable_now — Listas para usar (consistentes, ya en serving facts)

### Gaps & Deviations
| Signal | Type | Source | Consistency |
|--------|------|--------|------------|
| `gap_trips` | number | Phase2B weekly DB view | Consistent |
| `gap_trips_pct` | number | Phase2B weekly DB view | Consistent |
| `gap_revenue` | number | Phase2B weekly DB view | Consistent |
| `gap_revenue_pct` | number | Phase2B weekly DB view | Consistent |
| `gap_drivers` | number | Phase2B weekly DB view | Consistent |
| `gap_unitario` | number | Phase2B weekly DB view | Consistent |
| `gap_unitario_pct` | number | Phase2B weekly DB view | Consistent |
| `gap_prod` | number | Phase2B weekly DB view | Consistent |
| `gap_pct` (canonical) | number | projection_expected_progress_service | Consistent |
| `severity_score` | number | Phase2B weekly alerts | Consistent |
| `unit_alert` | boolean | Phase2B weekly DB view | Consistent |

### Attainment & Completion
| Signal | Type | Source | Consistency |
|--------|------|--------|------------|
| `attainment_pct` | number | projection_expected_progress_service | Consistent |
| `meets_oro` | boolean | yango_loyalty_service | Consistent |
| `meets_plata` | boolean | yango_loyalty_service | Consistent |
| `data_complete` | boolean | yango_loyalty_service | Consistent |
| `has_any_targets` | boolean | yango_loyalty_service | Consistent |

### Trust & Confidence
| Signal | Type | Source | Consistency |
|--------|------|--------|------------|
| `trust_status` | string (ok/warning/blocked) | data_trust_service | Consistent |
| `confidence_score` | number (0-100) | omniview_matrix_integrity_service | Consistent |
| `decision_mode` | string (SAFE/CAUTION/BLOCKED) | omniview_matrix_integrity_service | Consistent |

### Freshness
| Signal | Type | Source | Consistency |
|--------|------|--------|------------|
| `status` (global) | string (fresca/parcial_esperada/atrasada/falta_data/sin_datos) | data-freshness/global | Consistent |
| `lag_days` | number | business_slice_real_freshness_service | Consistent |

### Comparison
| Signal | Type | Source | Consistency |
|--------|------|--------|------------|
| `comparison_status` | string (matched/missing_plan/plan_without_real) | projection_expected_progress_service | Consistent |
| `reachability` | string (ON_TRACK/SLIGHTLY_BEHIND/RECOVERABLE/HIGH_RISK/UNREACHABLE/DATA_MISSING) | yango_loyalty_service | Consistent |
| `dominant_driver` | string (UNIT/VOL) | Phase2B weekly DB view | Consistent |

---

## usable_with_mapping — Existen pero requieren normalización

| Signal | Issue | Normalization |
|--------|-------|--------------|
| `severity` (P0/P1/P2/P3) from `ops.py` | Different enum from `alert_severity`, `risk_band` | Map to canonical severity: P0→blocked, P1→critical, P2→elevated, P3→warning |
| `alert_severity` (string) from `ops.py` | Inconsistent with `max_severity` and `severity_summary` | Map to canonical severity |
| `max_severity` (EARLY_WARNING/MODERATE_DEGRADATION/STRONG_DEGRADATION) | Behavioral intelligence specific | Map to canonical: EARLY_WARNING→warning, MODERATE→elevated, STRONG→critical |
| `priority_band` (CRITICAL/HIGH/MEDIUM/LOW/WATCH) | Alerting engine specific | Map to canonical |
| `signal` (green/warning/danger/no_data) | Visual-only, per KPI | Use as input for severity |
| `risk_band` | Behavioral alerts specific | Map to canonical |
| `freshness status` (fresh/stale/critical/unknown) | Different enum from global freshness | Map: critical→blocked, stale→elevated, unknown→unknown |

---

## unavailable — No existen (NO inventar)

- nada que requiera nuevos serving facts
- nada que requiera nuevos cálculos
- nada que requiera nuevos endpoints

---

## Maps de normalización

### Severidad canónica ← fuentes existentes

```
blocked ← trust_status="blocked" | decision_mode="BLOCKED" | comparison_status="missing_plan" (without real) | freshness="critical"
critical ← gap_pct > 30% | severity="P0"/"P1" | unit_alert=true | max_severity="STRONG_DEGRADATION" | priority_band="CRITICAL"
elevated ← gap_pct > 15% | severity="P2" | max_severity="MODERATE_DEGRADATION" | priority_band="HIGH" | confidence_score < 40 | freshness="stale"
warning  ← gap_pct > 5%  | severity="P3" | max_severity="EARLY_WARNING" | priority_band="MEDIUM" | comparison_status="plan_without_real" | meets_oro=false
normal   ← gap_pct <= 5% | signal="green" | meets_oro=true | comparison_status="matched"
unknown  ← no data | comparison_status=null | reachability="DATA_MISSING" | confidence_score=null
```
