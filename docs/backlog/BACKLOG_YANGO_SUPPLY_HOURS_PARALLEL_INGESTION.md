# BACKLOG — Yango Supply Hours Parallel Ingestion

**Date:** 2026-06-07
**Phase:** BACKLOG (PENDING)
**Registry:** LG-INFRA-R1.4

---

## OBJECTIVE

Actualizar `supply_hours` desde Yango API (`GET /v2/parks/contractors/supply-hours`) con procesamiento paralelo controlado, sin bloquear el loop de monitoreo de 5 minutos.

---

## PROBLEM

Hoy la API de supply-hours es el cuello de botella para frescura intradía:
- Cada driver requiere una llamada API individual (~1.5s con rate-limit)
- 5000 drivers activos tomarían ~2 horas secuencialmente
- No es viable reconstruir supply_hours en el loop de 5 minutos

---

## CONTRACT

| Dato | Frecuencia | Método |
|------|-----------|--------|
| orders / activity | Cada 5 minutos | Ingestión API batch (existente) |
| supply_hours | Paralelo por lotes, rate-limited | NUEVO servicio separado |
| driver profiles | Diario (daily closed pipeline) | Existente |

---

## ARQUITECTURA PROPUESTA

```
                        ┌──────────────────────┐
                        │  Scheduler Principal  │
                        │  (5-min loop)          │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
              orders/activity  heartbeat    supply_hours
              (cada 5 min)    (cada 5 min)   (batch paralelo)
                                                   │
                                        ┌──────────┴──────────┐
                                        │ Supply Hours Worker  │
                                        │ (thread separado)     │
                                        └─────────────────────┘
```

---

## PRIORIDAD DE PROCESAMIENTO

1. **Conductores accionados hoy** (tienen queue entry EXPORTED)
2. **HOT-tier drivers** (mayor actividad reciente)
3. **Drivers activos recientes** (con órdenes en últimas 24h)
4. **Resto por batch** (WARM, COLD, DORMANT en background)

---

## CAMPOS REQUERIDOS

Nueva columna en `growth.yango_lima_driver_360_daily`:

```sql
ALTER TABLE growth.yango_lima_driver_360_daily
    ADD COLUMN last_supply_hours_fetch_at TIMESTAMPTZ,
    ADD COLUMN supply_hours_freshness_status TEXT DEFAULT 'UNKNOWN',
    ADD COLUMN supply_hours_source TEXT DEFAULT 'YANGO_API_LIVE',
    ADD COLUMN supply_hours_partial_reason TEXT,
    ADD COLUMN supply_hours_batch_id UUID,
    ADD COLUMN supply_hours_retry_count INTEGER DEFAULT 0;
```

---

## RESTRICCIONES

- NO full scan secuencial de miles de drivers
- NO romper scheduler principal (corre en thread separado)
- NO bloquear Today Action Plan
- NO usar trips_2025/trips_2026 como fallback live
- Status = PARTIAL si no termina todos los tiers
- Freshness propia para supply_hours (separada de orders)
- Rate-limit: máximo N solicitudes concurrentes (configurable, default 3)

---

## ENDPOINTS PROPUESTOS

| Method | Path | Description |
|--------|------|-------------|
| POST | `/yego-lima-growth/lab/run-supply-batch` | Ejecutar batch de supply (existente, extender) |
| GET | `/yego-lima-growth/lab/supply-freshness-status` | Estado actual de frescura supply_hours |

---

## DEPENDENCIAS

| Dependencia | Status |
|------------|:---:|
| Yango API `get_supply_hours()` | EXISTS |
| driver_360_daily table | EXISTS |
| Hot-tier driver classification | EXISTS (eligible_universe) |
| Parallel execution framework | PENDING (threading/asyncio) |

---

## ESTIMACIÓN

| Item | Esfuerzo |
|------|---------|
| Parallel worker service | 3-4 horas |
| Rate-limit controller | 1 hora |
| Freshness tracking columns | 1 hora |
| Endpoint integration | 1 hora |
| Testing | 2 horas |
| **Total** | **~8 horas** |

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Yango Supply Hours Parallel Ingestion
Registered: 2026-06-07
Phase: LG-INFRA-R1.4
Status: BACKLOG — PENDING
Priority: MEDIUM (needed for full intraday freshness)
Blocked by: None (can be implemented standalone)
Next review: Post scheduler stabilization
```
