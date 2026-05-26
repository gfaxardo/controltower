# DRIVER ACTIVITY & LIFECYCLE FOUNDATION — FASE D3

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase Drivers:** D3 — Activity & Lifecycle Foundation

---

## 1. GOVERNANCE CHECK

- **Fase ACTIVE:** Control Foundation 1H.4 — compatible
- **READY NEXT:** Diagnostic Engine 2A.3 — NO activado
- **D3 es 100% Control Foundation** — no toca motores bloqueados
- **GO**

---

## 2. FUENTES DE ACTIVIDAD INSPECCIONADAS

| Fuente | driver_id | fecha | completados | city/country | volumen |
|--------|-----------|-------|-------------|--------------|---------|
| `public.trips_2025` | SI (conductor_id) | fecha_finalizacion | condicion='Completado' | via park | Histórico |
| `public.trips_2026` | SI (conductor_id) | fecha_finalizacion | condicion='Completado' | via park | Corriente |
| `public.trips_unified` | SI (conductor_id) | UNION trips_all+trips_2026 | condicion='Completado' | via park | Completo |
| `ops.driver_daily_activity_fact` | SI | activity_date | trips/completed_trips | SI (country, city, park_id) | Diario |

**Fuente canónica de actividad:** `ops.driver_daily_activity_fact`
- Grain: driver × activity_date
- Columnas: driver_id, activity_date, completed_trips, trips, country, city, park_id
- Refresh: diario (scheduler)
- Riesgo: si refresh falla, actividad se desactualiza → fallback no implementado en D3

---

## 3. DISEÑO ACTIVITY FACTS

### 3.1 Existing: ops.driver_daily_activity_fact
Ya existe. Es la fuente primaria para D3. No se creó nueva fact.

### 3.2 Diseñada: ops.driver_activity_weekly_fact (NO materializada en D3)
Sería una agregación semanal sobre `driver_daily_activity_fact`. Postergada a D4 ya que el service computa rolling windows en runtime sobre daily.

---

## 4. REGLAS ROLLING WINDOWS

Implementadas en `driver_activity_service.py`.

### Umbrales
- `DECLINE_THRESHOLD`: 30% (caída ≥ 30% WoW)
- `GROWTH_THRESHOLD`: 30% (crecimiento ≥ 30% WoW)

### Clasificación de activity_trend

| Trend | Condición |
|-------|-----------|
| **inactive** | trips_30d = 0 y no latest_trip_at O days_since > 60 |
| **declining** | trips_7d < trips_prev_7d con caída ≥ 30% |
| **growing** | trips_7d > trips_prev_7d con crecimiento ≥ 30% |
| **stable** | diferencia < 30% |
| **unknown** | datos insuficientes |

### Métricas computadas por driver
- trips_7d, trips_14d, trips_30d
- trips_prev_7d, trips_prev_14d, trips_prev_30d
- active_days_7d, active_days_30d
- latest_trip_at, days_since_last_trip
- activity_trend + trend_reason + evidence

---

## 5. LIFECYCLE STATE MACHINE

Implementada en `driver_lifecycle_service.py`. Determinística, sin scoring probabilístico.

### Estados (en orden de prioridad)

| Estado | Condición |
|--------|-----------|
| **NO_ACTIVITY_DATA** | Sin actividad ni identity suficiente |
| **REGISTERED_NO_TRIPS** | Tiene identity pero first_trip_at es null |
| **REACTIVATED** | Activo ahora (≤7d), previamente inactivo >21d |
| **CHURNED_LONG** | days_since_last_trip > 60 |
| **CHURNED_RECENT** | days_since_last_trip 22-60 |
| **AT_RISK** | days_since_last_trip 8-21, tuvo actividad previa |
| **DECLINING** | activity_trend = declining |
| **ACTIVE_LOW** | trips_30d > 0, trips_7d = 0, days_since ≤ 7 |
| **ACTIVE** | trips_7d > 0, days_since ≤ 7 |

### Cada estado devuelve
- lifecycle_stage
- lifecycle_reason (texto explicativo)
- evidence (datos que llevaron a la clasificación)
- computed_at
- data_quality_status

---

## 6. ENDPOINT CONTRACTS

### 6.1 GET /drivers/activity-summary (NUEVO)

**Query params:** driver_id, country, city, park_id, lifecycle_stage, activity_trend, limit, offset

**Response:**
```json
{
  "total": 100,
  "limit": 100,
  "offset": 0,
  "drivers": [
    {
      "driver_id": "...",
      "driver_name": "Carlos Pérez",
      "phone": "+57 300...",
      "country": "Colombia",
      "city": "Bogotá",
      "park_id": "...",
      "park_name": "Park Centro",
      "trips_7d": 45,
      "trips_14d": 90,
      "trips_30d": 195,
      "trips_prev_7d": 50,
      "trips_prev_30d": 210,
      "active_days_7d": 6,
      "active_days_30d": 22,
      "latest_trip_at": "2026-05-24",
      "days_since_last_trip": 1,
      "activity_trend": "stable",
      "trend_reason": "Trips stable: 50→45.",
      "evidence": {...},
      "data_quality_status": "ok",
      "refreshed_at": "2026-05-25T..."
    }
  ]
}
```

### 6.2 GET /drivers/lifecycle-summary (NUEVO)

**Query params:** country, city, park_id

**Response:**
```json
{
  "status": "ok",
  "summary": [
    {
      "lifecycle_stage": "ACTIVE",
      "drivers_count": 1234,
      "with_phone_count": 0,
      "without_phone_count": 1234,
      "avg_trips_30d": 45.2
    }
  ],
  "quality": {
    "identity_coverage": 94.5,
    "phone_coverage": 62.3,
    "activity_coverage": 87.1,
    "freshness_status": "ok"
  },
  "warnings": [],
  "blocking_gaps": []
}
```

### 6.3 GET /drivers/lifecycle/{driver_id} (NUEVO)

Single driver lifecycle classification with full identity + activity context.

---

## 7. DATA QUALITY / FRESHNESS DEPENDENCY

| Dependencia | Estado D3 |
|-------------|-----------|
| `ops.driver_daily_activity_fact` refrescada | Crítica — si stale, toda la clasificación se desactualiza |
| `public.drivers_data.phone` | Deseable — sin phone, contactability es limitada |
| `ops.v_dim_driver_resolved` (nombres) | Deseable — sin nombre, identidad es solo UUID |
| `ops.mv_driver_lifecycle_base` (first_trip) | Deseable — sin first_trip, algunos estados se degradan a NO_ACTIVITY_DATA |

---

## 8. QUÉ QUEDA BLOQUEADO PARA D4

| Capacidad | Estado | Bloqueante |
|-----------|--------|------------|
| Listas accionables P0 (nuevos sin viaje, sin contacto, declining, etc.) | **LISTO** — datos disponibles vía activity-summary + lifecycle-summary | Ninguno |
| `serving.driver_supply_actionable_fact` | **Pendiente** — requiere agregar action_reason + recommended_action | Crear en D4 |

D4 puede avanzar. Los datos de actividad y lifecycle ya están disponibles y son determinísticos.

---

## 9. GO / NO-GO

### GO para D4
- Activity metrics funcionan con rolling windows 7/14/30d
- Lifecycle state machine clasifica 9 estados determinísticos
- Endpoints `/drivers/activity-summary` y `/drivers/lifecycle-summary` operativos
- Frontend muestra Lifecycle Distribution card en Supply + Lifecycle
- Phone coverage medible vía lifecycle-summary quality
- 0 queries productivas rotas
- 0 tabs ocultas/modificadas

### D4 habilitado
Con activity + lifecycle + identity funcionando, D4 puede crear:
1. Listas accionables reales (P0: nuevos sin viaje, sin contacto, declining)
2. `driver_supply_actionable_fact` con action_reason + recommended_action
3. Workflow básico de asignación

---

## 10. REMEDIATION PLAN

| Paso | Acción | Prioridad |
|------|--------|-----------|
| 1 | Monitorear refresh de `driver_daily_activity_fact` (freshness < 24h) | P0 |
| 2 | Validar phone coverage en producción (lifecycle-summary.quality.phone_coverage) | P0 |
| 3 | Crear `serving.driver_activity_weekly_fact` para evitar runtime queries en D4 | P1 |
| 4 | Agregar filtro `country`/`city`/`park_id` en lifecycle-summary si no filtra bien | P1 |
| 5 | Integrar phone coverage en DataFoundation card | P2 |

---

## 11. ARCHIVOS CREADOS/MODIFICADOS

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/app/services/driver_activity_service.py` | NUEVO | Rolling windows 7/14/30d, trend classification, batch search |
| `backend/app/services/driver_lifecycle_service.py` | NUEVO | State machine 9 estados, bulk summary, single driver classification |
| `backend/app/routers/drivers.py` | MOD | +3 endpoints: activity-summary, lifecycle-summary, lifecycle/{id} |
| `frontend/src/components/driver/DriverLifecycleSummary.jsx` | NUEVO | Lifecycle distribution card con barras + quality metadata |
| `frontend/src/components/driver/DriverOperatingHub.jsx` | MOD | Integración de lifecycle card en Supply + Lifecycle |
| `docs/drivers/DRIVER_ACTIVITY_LIFECYCLE_FOUNDATION_D3.md` | NUEVO | Este documento |

---

**FIN DEL DOCUMENTO D3**
