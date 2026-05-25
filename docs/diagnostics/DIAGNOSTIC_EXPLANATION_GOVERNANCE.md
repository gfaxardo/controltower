# DIAGNOSTIC EXPLANATION GOVERNANCE

**Date**: 2026-05-25
**Motor**: Diagnostic Engine (temprano)
**CANONICAL SOURCE**: This document

---

## 1. DEFINITION

### What Diagnostic Explanation IS
A **deterministic explanatory layer** that answers "why" something is critical/blocked/elevated/unknown.

It provides:
- Causal factor identification
- Dominant factor prioritization
- Structured breakdown of diagnostic signals

### What Diagnostic Explanation is NOT
- Suggestion Engine (backlog motor #5)
- Reachability (backlog motor #3)
- Forecast (backlog motor #4)
- Action automation
- AI/ML inference
- Recommender system

---

## 2. OFFICIAL DIAGNOSTIC FACTORS

### CATEGORY 1: System Integrity (blocking)

| Factor | Meaning | Triggered by |
|--------|---------|-------------|
| `freshness_degraded` | Data freshness is critically degraded | freshness_status="critical"/"atrasada" |
| `trust_degraded` | Trust layer blocked | trust_status="blocked"/"warning" |
| `missing_serving` | Serving fact layer empty | missing_serving_fact=true / fact_status="empty" |
| `blocked_comparison` | Comparison cannot be performed | comparison_status="blocked" |
| `missing_comparable` | No comparable data | comparison_status="plan_without_real" |
| `missing_plan` | No plan data available | comparison_status="missing_plan" |
| `projection_missing` | Projection not available | projection=null |
| `stale_data` | Data is stale but not blocked | freshness_status="stale"/"parcial_esperada" |
| `confidence_degraded` | Confidence score low | confidence < threshold |

### CATEGORY 2: Operational Deviation

| Factor | Meaning | Triggered by |
|--------|---------|-------------|
| `severe_gap` | Deviation above critical/elevated threshold | abs(gap) > threshold |
| `unit_alert_triggered` | Unit economics alert active | unit_alert=true |
| `attainment_gap` | Below target attainment | attainment < target |

### CATEGORY 3: Trend

| Factor | Meaning | Triggered by |
|--------|---------|-------------|
| `sustained_negative` | 3+ consecutive weeks declining | weeks_declining >= 3 |
| `weekly_deterioration` | Week-over-week decline | weeks_declining >= 1 |
| `monthly_deterioration` | Month-over-month decline | (reserved) |

### CATEGORY 4: Configuration & Data

| Factor | Meaning | Triggered by |
|--------|---------|-------------|
| `config_incomplete` | Targets not configured | has_any_targets=false |
| `data_incomplete` | Manual KPIs pending or data incomplete | data_complete=false / manual_kpis_pending > 0 |

### CATEGORY 5: Insufficient Signal

| Factor | Meaning | Triggered by |
|--------|---------|-------------|
| `insufficient_signal` | Not enough data to diagnose | reachability=DATA_MISSING / no signals at all |

---

## 3. FACTOR PRIORITY ORDER

Lower position = higher priority. First match becomes dominant factor.

1. freshness_degraded
2. missing_serving
3. trust_degraded
4. blocked_comparison
5. missing_comparable
6. missing_plan
7. projection_missing
8. severe_gap
9. unit_alert_triggered
10. sustained_negative
11. weekly_deterioration
12. monthly_deterioration
13. confidence_degraded
14. stale_data
15. config_incomplete
16. data_incomplete
17. attainment_gap
18. insufficient_signal

---

## 4. DOMINANT FACTOR RULE

1. **ALWAYS show exactly 1 dominant factor** — the highest priority match
2. **Max 2 secondary factors** — contributing but not primary
3. **NEVER show all factors simultaneously** — signal overload
4. **Normal state shows NOTHING** — no explanation needed for within-tolerance

---

## 5. EXPLANATION HIERARCHY

### Level 1: Dominant factor (always visible for non-normal)
- 1 line: "{Severity} due to {factor}. {detail}"
- Compact badge format
- Visible inline with the data being explained

### Level 2: Secondary factors (expandable)
- Max 2 contributing factors
- Shown on click/hover via tooltip or accordion

### Level 3: Raw signals (technical only)
- gap%, confidence score, specific values
- Only in tooltip/expand section, never main view

---

## 6. PROHIBITED FACTORS

These must NEVER appear in diagnostic explanations:
- "Market conditions" — external factor, not system-observable
- "Driver dissatisfaction" — speculative inference
- "Competition" — not measurable by the system
- "Algorithm issue" — too generic
- "AI detected" — no AI in diagnostics
- "Platform error" — should be a bug, not an explanation
- Any factor that implies a recommended action

---

## 7. SIGNAL-TO-NOISE GOVERNANCE

| Severity | Show Explanation? | Level |
|----------|------------------|-------|
| blocked | YES — dominant factor | Level 1+2 |
| critical | YES — dominant factor | Level 1+2 |
| elevated | YES — dominant factor | Level 1 |
| warning | Only if explicit (in panel/list view) | Level 1 |
| normal | NO | None |
| unknown | Minimal explanation only | Level 1 |

---

## 8. TEXT GOVERNANCE

### ALLOWED patterns
- "{Severity} due to {factor}. {detail}"
- "{Factor}: {detail}"
- "Blocked by {factor}"
- "Critical: {factor} detected"

### PROHIBITED patterns
- "You should..."
- "We recommend..."
- "The best action is..."
- "Contact..."
- "Escalate to..."
- "Run {process}"

---

## 9. COMPONENT GOVERNANCE

| Component | When to use |
|-----------|------------|
| `DiagnosticDominantFactor` | Inline in alert cards, table rows, data panels. 1 line. |
| `DiagnosticFactorBadge` | As a chip in compact contexts. "factor: detail" format. |
| `DiagnosticBreakdownTooltip` | Click/hover to reveal secondary factors + signals. |
| `DiagnosticExplanationCard` | Standalone panel for a full entity (e.g., in a drill-down view). |
| `DiagnosticReasonList` | In tooltips or detail panels where multiple factors matter. |

---

## 10. LIMITS BEFORE SUGGESTION ENGINE

The Diagnostic Explanation Layer ends at **explaining the current state**.

The Suggestion Engine (backlog motor #5) would add:
- "Given this state, what are the options?"
- "Which option has the highest expected impact?"
- "What actions have been taken in similar situations?"

DO NOT cross into suggestion territory.
Diagnosis explains. Suggestion prescribes.
We diagnose. We do not prescribe.
