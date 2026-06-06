# LG-UX-R2.2 — Freshness Layer

**Date:** 2026-06-05
**Phase:** LG-UX-R2.2 Freshness Layer E2E

---

## 1. Sources Evaluated

| Domain | Table | Timestamp Column | Freshness Available |
|--------|-------|-----------------|---------------------|
| driver_snapshot | `growth.yango_lima_driver_state_snapshot` | `snapshot_date` | YES |
| opportunity_engine | `growth.yango_lima_prioritized_opportunity_daily` | `generated_at` | YES |
| assignment_queue | `growth.yango_lima_assignment_queue` | NONE | UNKNOWN |
| exports | `growth.yango_lima_loopcontrol_campaign_export` | `exported_at` | YES |
| loopcontrol | `growth.yango_lima_loopcontrol_campaign_export` | `exported_at` | YES |
| capacity | `growth.yango_lima_capacity_config` | NONE | UNKNOWN |
| program_eligibility | `growth.yango_lima_program_eligibility_daily` | `eligibility_date` | YES |
| policy_config | `growth.yango_lima_opportunity_policy_config` | `updated_at` | YES |

## 2. Thresholds

| Domain | Threshold (min) | Rationale |
|--------|----------------|-----------|
| driver_snapshot | 1440 (24h) | Daily snapshot |
| opportunity_engine | 1440 (24h) | Daily generation |
| assignment_queue | 240 (4h) | Intra-day operational |
| exports | 240 (4h) | Recent exports expected |
| loopcontrol | 240 (4h) | Integration health |
| capacity | 10080 (7d) | Stable config |
| program_eligibility | 1440 (24h) | Daily generation |
| policy_config | 10080 (7d) | Stable config |

## 3. Freshness Contract

```json
{
  "status": "FRESH" | "WARNING" | "STALE" | "UNKNOWN",
  "last_refreshed_at": "2026-06-02T00:00:00+00:00",
  "age_minutes": 120.5,
  "threshold_minutes": 1440,
  "source": "growth.yango_lima_driver_state_snapshot",
  "domain": "driver_snapshot",
  "reason": "Data is 120min old (threshold: 1440min)",
  "remediation": null
}
```

## 4. Endpoints Modified

| Endpoint | Freshness Added |
|----------|----------------|
| `GET /operational-summary` | `freshness.driver_snapshot`, `freshness.opportunity_engine`, `freshness.assignment_queue`, `freshness.exports`, `freshness.policy_config` |
| `GET /driver-state/summary` | `freshness.driver_snapshot` |
| `GET /programs/summary` | `freshness.program_eligibility` |

## 5. New Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /yego-lima-growth/freshness/health` | Aggregated freshness for all 8 domains |

## 6. Endpoints Without Real Timestamps

| Domain | Status | Remediation |
|--------|--------|-------------|
| assignment_queue | UNKNOWN | Table has no timestamp columns. Add `created_at` to migration. |
| capacity | UNKNOWN | Table has no timestamp columns. Add `updated_at` to migration. |

## 7. Frontend Components

**New:** `FreshnessBadge.jsx` — compact/expanded variants with tooltip showing source, age, threshold, remediation.

**Modified:** `SharedComponents.jsx` — `SectionCard` accepts optional `freshness` prop.

**Wired into:**
- CommandCenterSection: freshness badges in Engine Health bar
- ProgramsSection: freshness badge on Driver State card
- ControlConfigSection: freshness badge on Policy card

## 8. CRITERIA

| Status | Condition |
|--------|-----------|
| FRESH | age_minutes <= threshold |
| WARNING | age_minutes > threshold AND <= threshold * 2 |
| STALE | age_minutes > threshold * 2 |
| UNKNOWN | No timestamp available |

## 9. Limitations

- 2 domains (assignment_queue, capacity) have UNKNOWN freshness — tables lack timestamp columns
- Thresholds are hardcoded in `freshness_service.py` — not DB-configurable yet
- No per-KPI freshness — aggregated at domain level
- No automated refresh trigger — freshness is observational only

## 10. Build

- Backend: Compile OK
- Frontend: Build PASS (32.80 kB gzip 8.16 kB)

## 11. GO / NO-GO for R2.3 (Explainability Layer)

**GO** — Freshness layer operational. All endpoints with timestamp data return freshness metadata. Health endpoint provides aggregated status. Frontend shows compact badges. 2 UNKNOWN domains identified with clear remediation path (add timestamp columns to assignment_queue and capacity_config).
