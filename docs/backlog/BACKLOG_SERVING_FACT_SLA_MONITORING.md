# BACKLOG — Serving Fact SLA Monitoring

**Date:** 2026-06-07
**Phase:** BACKLOG (HARDENING)
**Registry:** LG-INFRA-R1.6

---

## OBJECTIVE

Monitorear que los 8 serving facts cumplan SLA:
- Generación diaria exitosa
- Latencia de lectura < 1s
- Sin MISSING sin remediation
- Sin runtime fallback automático

---

## SLA CONTRACT

| Fact Type | Max Latency | Max Staleness | Fallback |
|-----------|:----------:|:------------:|----------|
| operational_summary | 1s | 24h | MISSING_SERVING_FACT |
| today_action_plan | 1s | 24h | MISSING_SERVING_FACT |
| programs_summary | 1s | 24h | MISSING_SERVING_FACT |
| driver_state_summary | 1s | 24h | MISSING_SERVING_FACT |
| queue_summary | 1s | 24h | MISSING_SERVING_FACT |
| allocation_trace | 1s | 24h | MISSING_SERVING_FACT |
| program_capacity_policy | 1s | 24h | MISSING_SERVING_FACT |
| refresh_status | 1s | 24h | MISSING_SERVING_FACT |

---

## MONITORING METRICS

| Metric | Description |
|--------|-------------|
| facts_generated | Count of facts generated per refresh run |
| facts_missing | Count of facts missing for latest date |
| read_latency_p50 | 50th percentile read latency |
| read_latency_p99 | 99th percentile read latency |
| staleness_hours | Hours since last generation |

---

## PROPOSED MONITORING

- `growth.yego_lima_serving_fact_sla_log` table
- Auto-check on each refresh
- Alert if facts MISSING > 0
- Alert if latency > 2s

---

## STATUS: BACKLOG

Do not implement until serving fact infrastructure stabilized.

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Serving Fact SLA Monitoring
Registered: 2026-06-07
Phase: LG-INFRA-R1.6
Status: BACKLOG — PENDING
```
