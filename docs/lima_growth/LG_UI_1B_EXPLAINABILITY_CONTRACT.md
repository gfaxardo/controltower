# LG-UI-1B — EXPLAINABILITY CONTRACT

**Date:** 2026-06-12
**Phase:** LG-UI-1B / Explainability Hardening

---

## CONTRACT

```json
{
  "driver_id": "string",
  "found": true,
  "domains": {
    "lifecycle": {
      "status": "ACTIVE | AT_RISK | DECLINING | CHURNED | ...",
      "reason": "string — human-readable explanation",
      "evidence": { "trips_7d": int, "days_since_last_trip": int },
      "trips_7d": int,
      "trips_30d": int,
      "days_since_last_trip": int,
      "version": "string",
      "source_date": "2026-06-10"
    },
    "segment": {
      "operational_status": "string",
      "activity_status": "string",
      "value_tier": "top_20 | mid_60 | bottom_20",
      "momentum": "rising | stable | falling",
      "persona": "string",
      "matched_rules": { "layer": ["rule1", "rule2"] },
      "failed_rules": { "layer": ["rule3"] },
      "source_date": "2026-06-10"
    },
    "program": {
      "selected_program": "PROGRAM_ACTIVE_GROWTH | ...",
      "selection_reason": "string",
      "opportunity_score": float,
      "final_rank": int,
      "eligible_programs": ["PROGRAM_ACTIVE_GROWTH", "..."],
      "evidence": {},
      "source_date": "2026-06-10"
    },
    "movement": {
      "transition_type": "ENTERED_PROGRAM | EXITED_PROGRAM | STATE_CHANGE",
      "trigger_reason": "string",
      "rule_deltas": [{"rule": "...", "before": "FAIL", "after": "MATCH"}],
      "state_before": {},
      "state_after": {},
      "evidence": {},
      "source_date": "2026-06-05"
    },
    "rna": {
      "is_rna": true,
      "contactable": true,
      "cancelled_signal": false,
      "registration_date": "2026-01-15",
      "first_trip_date": null,
      "last_trip_date": null,
      "reason": "string — RNA explanation"
    }
  }
}
```

---

## ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/yego-lima-growth/explainability/{driver_id}` | All 5 domains aggregated |
| `GET` | `/yego-lima-growth/explainability/{driver_id}/{domain}` | Single domain |

---

## UI FORMAT (DECISION → RAZONES → EVIDENCIA → FUENTE → FECHA)

Implemented in `ExplainabilityPanel.jsx`:

1. **DECISION**: What was decided (lifecycle status, program assignment, movement type)
2. **RAZONES**: Why this decision (lifecycle_reason, selection_reason, trigger_reason)
3. **EVIDENCIA**: Supporting data (trips, rules matched/failed, scores)
4. **FUENTE**: Source table
5. **FECHA**: source_date

---

## RULES

- Zero recalculation — all data from persisted traces
- Zero inference — no AI, no guessing
- Every explanation is traceable to a source table and date
- Missing data → "No explanation available" (not silent failure)
- Partial data → show what exists, note what's missing
