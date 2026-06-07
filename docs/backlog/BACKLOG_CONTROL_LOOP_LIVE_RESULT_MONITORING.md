# BACKLOG — Control Loop Live Result Monitoring

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** LG-INFRA-R1.2

---

## NEED

Today the 5-min live monitoring loop maintains Yango API freshness but does NOT track what happened to drivers that were contacted. Result signals (did the driver return to operate? did they complete more trips?) are not monitored in real-time.

---

## RESULT SIGNAL TABLE (Future)

```sql
CREATE TABLE growth.yego_lima_action_result_signal (
    signal_id           uuid PRIMARY KEY,
    action_date         date NOT NULL,
    driver_profile_id   text NOT NULL,
    queue_id            uuid,
    campaign_id_external text,
    action_channel      text,
    action_sent_at      timestamptz,
    observed_at         timestamptz NOT NULL DEFAULT now(),
    first_trip_after_action_at timestamptz,
    trips_after_action  integer DEFAULT 0,
    supply_hours_after_action numeric(10,2) DEFAULT 0,
    earnings_after_action numeric(12,2) DEFAULT 0,
    reactivation_detected boolean DEFAULT false,
    source_system       text NOT NULL DEFAULT 'YANGO_API_LIVE',
    source_loaded_at    timestamptz NOT NULL DEFAULT now()
);
```

---

## LIVE MONITORING TICK (Future)

Every 5 minutes:

1. Query Yango API for recent orders by contacted drivers
2. Compare against action_sent_at timestamps
3. Update result signals:
   - `first_trip_after_action_at` if first trip detected
   - `trips_after_action` counter
   - `supply_hours_after_action` cumulative
   - `reactivation_detected` flag

---

## NOT IMPLEMENTED (Yet)

- This is formal Impact/Attribution territory
- Blocked until R3.x (Impact + Attribution foundational)
- The table schema is documented for future use
- The live monitoring loop is designed to accommodate this when ready

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| Yango API (orders lookup by driver) | EXISTS |
| LoopControl result sync (campaign → driver mapping) | BACKLOG |
| Impact measurement (causal analysis) | BACKLOG |
| Attribution (channel/program attribution) | BACKLOG |

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Control Loop Live Result Monitoring
Registered: 2026-06-06
Phase: LG-INFRA-R1.2
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post R3.1 + Result Sync + Impact Foundation
```
