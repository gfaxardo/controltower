# LG-UX-R2.4 — Programs As First-Class Citizens

**Date:** 2026-06-05
**Phase:** LG-UX-R2.4 Programs Operationalization

---

## 1. Program Operational Contract

```json
{
  "program_code": "PROGRAM_CHURN_PREVENTION",
  "program_name": "Churn Prevention",
  "eligible_total": 7816,
  "prioritized_total": 2060,
  "actionable_today": 180,
  "queued_total": 150,
  "exported_total": 135,
  "exported_campaigns_count": 7,
  "last_run_at": "2026-06-02",
  "status": "READY",
  "freshness": { "status": "FRESH", "age_minutes": 120, ... },
  "explainability": { "title": "Elegibles", "reason": "...", ... },
  "blockers": [],
  "remediation": [],
  "source": "STATIC_REGISTRY"
}
```

## 2. Operational Statuses

| Status | Condition | Meaning |
|--------|-----------|---------|
| READY | eligible > 0 AND actionable > 0 | Program has drivers ready for action |
| ACTIVE | eligible > 0 but no actionable | Program has eligible drivers but none made the capacity cut |
| EMPTY | eligible = 0 | No drivers eligible for this program |
| STALE | freshness = STALE | Source data is outdated |
| UNKNOWN | freshness = UNKNOWN or no data | Cannot determine status |
| BLOCKED | explicit blocker | Dependency missing or critical issue |

## 3. Fields Per Program

| Field | Source | Notes |
|-------|--------|-------|
| eligible_total | `program_eligibility_daily` | COUNT BY program_code |
| prioritized_total | `prioritized_opportunity_daily` | COUNT BY selected_program_code |
| actionable_today | `prioritized_opportunity_daily` | WHERE is_actionable_today=true |
| queued_total | `assignment_queue` | COUNT BY program_code |
| exported_total | `loopcontrol_campaign_export` | SUM(contacts_inserted) BY program_code |
| exported_campaigns_count | `loopcontrol_campaign_export` | COUNT BY program_code |
| last_run_at | eligibility_date | Date of last eligibility build |
| status | computed | Based on rules above |
| freshness | `compute_freshness()` | From eligibility_date |
| explainability | `explain_kpi()` | Deterministic explanation |
| blockers | computed | STALE, UNKNOWN, or NO_ELIGIBLE |
| remediation | computed | Action to resolve blockers |

## 4. Fields with null/remediation

| Field | Status | Remediation |
|-------|--------|-------------|
| exported_campaigns_count | 0 if no exports | Not an error — means no campaigns exported yet for this program |
| blockers | [] if no issues | Normal state |
| remediation | [] if no issues | Normal state |

## 5. What Was NOT Implemented

- **Program Builder** — programs are still STATIC_REGISTRY (4 programs hardcoded)
- **Program editing** — no UI to create/modify programs
- **Eligibility rule editing** — criteria are hardcoded in policy service
- **Export attribution inference** — export data comes directly from `loopcontrol_campaign_export.program_code`, no inference
- **Queue attribution** — comes directly from `assignment_queue.program_code`

## 6. Files

| File | Change |
|------|--------|
| `backend/app/services/yego_lima_program_eligibility_service.py` | Enriched with status, freshness, explainability, blockers, remediation, program_name mapping |
| `frontend/.../sections/ProgramsSection.jsx` | Rewritten — operational cards with status badges, freshness, explainability tooltip, blockers/remediation alerts |

## 7. Programs Detected: **4**

- PROGRAM_HIGH_VALUE_RECOVERY → High Value Recovery
- PROGRAM_CHURN_PREVENTION → Churn Prevention
- PROGRAM_14_90 → 14/90
- PROGRAM_ACTIVE_GROWTH → Active Growth

## 8. Build

- Backend: compile OK
- Frontend: build PASS (36.87 kB, gzip 9.06 kB)

## 9. GO / NO-GO for R2.5 Queue Operationalization

**GO** — Programs are now visible as operational units with full pipeline metrics, status, freshness, and explainability. Each program card shows its complete pipeline (eligible → prioritized → actionable → queued → exported) with blockers and remediation when needed.
