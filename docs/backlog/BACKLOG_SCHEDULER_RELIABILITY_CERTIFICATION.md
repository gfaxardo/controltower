# BACKLOG — Scheduler Reliability Certification

**Date:** 2026-06-07
**Phase:** BACKLOG (HARDENING TRACKING)
**Registry:** LG-INFRA-R1.6

---

## OBJECTIVE

Certificar que el scheduler de Lima Growth:
- Corre de forma repetida y confiable cada 5 minutos
- Registra cada tick con trazabilidad completa
- Detecta y reporta fallos
- No degrada el sistema en caso de error
- Mantiene los contratos de live monitoring

---

## DEPENDENCIES

| Dependency | Status |
|-----------|:---:|
| Scheduler status table | EXISTS |
| run_live_monitoring() | EXISTS (R1.5 hardened) |
| catch_up_on_startup() | EXISTS (R1.5) |
| Intraday signal builder | EXISTS (R1.3) |
| Driver list history | EXISTS (R1.5) |

---

## TICK LOG TABLE (Proposed)

```sql
CREATE TABLE growth.yego_lima_scheduler_tick_log (
    tick_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz,
    duration_ms     integer,
    tick_status     text NOT NULL DEFAULT 'STARTED',
    catch_up_attempted boolean DEFAULT false,
    signals_built   integer DEFAULT 0,
    history_snapshot_rows integer DEFAULT 0,
    governance_checked boolean DEFAULT false,
    error_message   text,
    remediation     text
);
```

---

## RELIABILITY METRICS

| Metric | Target |
|--------|--------|
| Tick interval | 5 minutes |
| Tick duration | < 30 seconds |
| Success rate | > 95% |
| Error recovery | Auto-retry next tick |
| Tick log retention | 30 days |

---

## STATUS: PENDING CERTIFICATION

Actual certification evidence lives in:
`docs/lima_growth/LG_INFRA_R1_6_MIDNIGHT_ROLLOVER_SCHEDULER_RELIABILITY_CERTIFICATION.md`

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Scheduler Reliability Certification
Registered: 2026-06-07
Phase: LG-INFRA-R1.6
Status: PENDING CERTIFICATION
```
