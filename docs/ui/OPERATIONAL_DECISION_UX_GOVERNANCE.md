# OPERATIONAL DECISION UX GOVERNANCE

**Date**: 2026-05-25
**Motor**: Control Foundation + Diagnostic Engine Temprano
**CANONICAL SOURCE**: This document

---

## 1. DEFINITION

### What Decision UX IS
A **visual prioritization layer** that helps operators detect, compare, and prioritize operational issues faster.

It provides:
- Centralized severity classification
- Deterministic attention routing
- Compact visual indicators
- Structured prioritization without AI

### What Decision UX is NOT
- Decision Engine (that's backlog motor #6)
- Suggestion Engine (that's backlog motor #5)
- AI Copilot (that's backlog motor #8)
- Action automation system
- Recommendation generator
- Predictive system

## 2. CANONICAL SEVERITIES

Only these 6 severities exist. No custom severities.

| Severity | Meaning | Threshold |
|----------|---------|-----------|
| `blocked` | Operation impossible. Trust/freshness/comparison blocked. | trust_status=blocked OR comparison=missing_plan OR confidence<10 |
| `critical` | Severe deviation. Immediate attention required. | gap>30% OR unit_alert=true OR attainment<50% |
| `elevated` | Significant deviation. Review needed soon. | gap>15% OR confidence<40 OR freshness=stale |
| `warning` | Minor deviation. Monitor. | gap>5% OR comparison=plan_without_real OR meets_oro=false |
| `normal` | Within tolerance. No action needed. | signal=green OR comparison=matched |
| `unknown` | Insufficient signal. Cannot evaluate. | No data available |

---

## 3. THRESHOLDS

Centralized in `frontend/src/utils/operationalDecisionSeverity.js` → `DECISION_THRESHOLDS`.

```js
DECISION_THRESHOLDS = {
  gap_critical: 30,    // >30% gap → critical
  gap_elevated: 15,    // >15% gap → elevated
  gap_warning:  5,     // >5%  gap → warning

  confidence_blocked: 10,   // <10  → blocked
  confidence_critical: 25,  // <25  → critical
  confidence_warning:  50,  // <50  → warning

  attainment_blocked:  30,  // <30% attainment → blocked
  attainment_critical: 50,  // <50% attainment → critical
  attainment_elevated: 75,  // <75% attainment → elevated
  attainment_warning:  95,  // <95% attainment → warning
}
```

---

## 4. ATTENTION ROUTING RULES

1. **Order**: blocked → critical → elevated → warning → normal → unknown
2. **Stability**: Items with same severity maintain original order (stable sort)
3. **Filtering**: Views can show only blocked+critical+elevated for "attention mode"
4. **Summary**: `getAttentionSummary()` returns counts per severity

---

## 5. SIGNAL NORMALIZATION

### Mapping from existing signals

```
FROM                    → TO (canonical)
─────────────────────────────────────────
trust_status="blocked"  → blocked
decision_mode="BLOCKED" → blocked
comparison_status="missing_plan" → blocked
freshness="critical"    → blocked
confidence < 10         → blocked
attainment < 30%        → blocked

gap > 30%               → critical
unit_alert=true         → critical
severity="P0"/"P1"      → critical
attainment < 50%        → critical

gap > 15%               → elevated
severity="P2"/"high"    → elevated
freshness="stale"       → elevated
confidence < 25         → critical (priority overrides elevated)
attainment < 75%        → elevated

gap > 5%                → warning
severity="P3"/"low"     → warning
comparison="plan_without_real" → warning
meets_oro=false         → warning
data_complete=false     → warning
has_any_targets=false   → warning
attainment < 95%        → warning
```

---

## 6. VISUAL PRIORITIZATION RULES

### Anomaly Emphasis

1. **Only exceptions break visual pattern.** If everything is highlighted, nothing is.
2. Blocked + Critical use red tones (`ct-badge--bad`, dot: `#dc2626`, `#ef4444`)
3. Elevated + Warning use amber tones (`ct-badge--warn`, dot: `#f59e0b`, `#fbbf24`)
4. Normal uses green tones (`ct-badge--ok`, dot: `#22c55e`)
5. Unknown uses neutral tones (`ct-badge--neutral`, dot: `#d6d3d0`)

### Badge vs Dot

- `DecisionSeverityBadge compact={true}` → dot only (6px circle). Use in dense tables, lists.
- `DecisionSeverityBadge showLabel` → badge with text. Use in panel headers, summaries.

---

## 7. PERMITTED TEXTS

### ALLOWED
- "Blocked by freshness"
- "Blocked by trust"
- "Critical plan deviation"
- "Critical unit alert"
- "Elevated operational risk"
- "Elevated deviation"
- "Warning — review required"
- "Warning — data incomplete"
- "Within tolerance"
- "Insufficient signal"
- "No data available"

### PROHIBITED
- "Haz X" / "Do X"
- "Llama a..." / "Call..."
- "Ejecuta campaña" / "Run campaign"
- "Sube bonos" / "Increase bonuses"
- "Recomendamos..." / "We recommend..."
- "La IA sugiere..." / "AI suggests..."
- "Deberías..." / "You should..."
- "La mejor acción es..." / "The best action is..."

---

## 8. COMPONENT GOVERNANCE

### Reusable (use in any view)
| Component | File | Use |
|-----------|------|-----|
| `DecisionSeverityBadge` | `components/operational/DecisionSeverityBadge.jsx` | Severity indicator (dot or badge) |
| `DecisionPriorityStrip` | `components/operational/DecisionPriorityStrip.jsx` | Severity summary strip |
| `DecisionAttentionList` | `components/operational/DecisionAttentionList.jsx` | Sorted/reordered list |
| `DecisionAttentionHeader` | `components/operational/DecisionAttentionHeader.jsx` | Section header with attention summary |
| `DecisionSignalTooltip` | `components/operational/DecisionSignalTooltip.jsx` | Explanatory tooltip |

### Core utilities
| Utility | File | Use |
|---------|------|-----|
| Severity contract | `utils/operationalDecisionSeverity.js` | All severity logic, thresholds |
| Attention routing | `utils/operationalAttentionRouting.js` | Sorting, partitioning, summarization |

---

## 9. ENFORCEMENT

### PR Review Checklist
- [ ] New severity? Reject — only 6 canonical severities allowed
- [ ] New threshold? Reject — thresholds centralized in DECISION_THRESHOLDS
- [ ] "Recomendamos" or similar text? Reject — prohibited texts
- [ ] New API call for severity? Reject — reads existing data only
- [ ] Sorting every render without memo? Reject — performance issue
- [ ] Signal normalization duplicated? Reject — use normalizeDecisionSignal()

---

## 10. LIMITS BEFORE SUGGESTION ENGINE

This Decision UX layer **ends at prioritization**.

The Suggestion Engine (Motor #5, backlog) would add:
- Recommended actions per severity
- Automated response proposals
- Priority escalation workflows
- Contextual action links

DO NOT cross into Suggestion Engine territory.
Severity is observation. Suggestion is prescription.
We observe. We do not prescribe.
