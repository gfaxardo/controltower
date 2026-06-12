# LG-UI-1A — DRIVER DETAIL CONTRACT

**Date:** 2026-06-12
**Phase:** LG-UI-1A / Dashboard MVP
**Status:** CONTRACT DEFINED — Implementation deferred to LG-UI-1B

---

## NAVIGATION FLOW

```
Driver Explorer (filter/search)
    ↓  click driver_id or "Detail →" button
Driver Detail View
    ↓  click "Why?" on any attribute
Explainability View (full trace)
```

---

## DRIVER DETAIL VIEW — CONTRACT

### Route

`/lima-growth/intelligence/driver/:driver_id`

### Data Sources

| Section | Endpoint | Method |
|---------|----------|--------|
| Driver Identity | `GET /drivers/identity/{driver_id}` | EXISTS |
| Lifecycle Detail | `GET /drivers/lifecycle/{driver_id}` | EXISTS |
| Program History | `GET /yego-lima-growth/programs/drivers?driver_id=` | EXISTS |
| Movement History | `GET /yego-lima-growth/movement/driver/{driver_id}` | EXISTS |
| Diagnostic Trace | `GET /yego-lima-growth/diagnostic-trace/{driver_id}` | EXISTS |
| Segment/Taxonomy | `GET /yego-lima-growth/taxonomy/driver/{driver_id}` | EXISTS |
| Activity Summary | `GET /drivers/activity-summary?driver_id=` | EXISTS |
| Contact History | (to be created in LG-UI-1B) | TBD |

### Sections

1. **Driver Identity Card**
   - driver_id, name, phone, city, park
   - Registration date, first trip date

2. **Current Status**
   - Lifecycle stage (with explainability: why this stage?)
   - Segment (with explainability: matched rules)
   - Value tier, Momentum
   - RNA status
   - Active programs

3. **Activity Timeline**
   - Trips 7d, 30d, 90d
   - Last trip date
   - Hours online
   - Earnings trend

4. **Program History**
   - Program assignments timeline
   - Eligibility changes
   - Decision traces

5. **Movement Timeline**
   - State transitions
   - Program entries/exits
   - Trigger reasons

6. **Contact History**
   - Campaign contacts
   - LoopControl exports
   - Outcomes

---

## EXPLAINABILITY CONTRACT

Each key attribute must expose a "Why?" trigger:

| Attribute | Explainability Source | Engine |
|-----------|----------------------|--------|
| Lifecycle stage | lifecycle_reason + evidence_json in lifecycle_daily | Diagnostic |
| Segment | matched_rules + failed_rules per taxonomy layer | Taxonomy V2 |
| Program assignment | eligibility_reason + selection_reason | Program Engine |
| Movement | trigger_reason + rule_delta per transition | Movement Engine |
| RNA status | Cancelled signal validation + contactability | RNA Engine |

Explainability surface integrated in LG-UI-1A as:
- StatusBadge components with tooltip
- "Why" column in Driver Explorer (placeholder for LG-UI-1B)
- Per-row explainability summary from diagnostic traces

---

## DEFERRED TO LG-UI-1B

- Full Driver Detail view implementation
- Explainability modal/drawer with full trace
- Contact history endpoint (if not existing)
- CSV export
- Advanced heatmaps
- RNA prioritization engine
