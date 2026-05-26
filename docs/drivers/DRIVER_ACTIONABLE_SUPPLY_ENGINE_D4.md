# DRIVER ACTIONABLE SUPPLY ENGINE — FASE D4

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Control Foundation (Operational Maturity Governance)
**Sub-fase Drivers:** D4 — Actionable Supply Engine

---

## 1. GOVERNANCE CHECK

- **Fase ACTIVE:** Control Foundation 1H.4 — D4 compatible
- **NO activa Diagnostic Engine** (READY NEXT)
- **NO activa AI Copilot**
- **NO scoring probabilístico** — todo determinístico
- **GO**

---

## 2. QUEUES IMPLEMENTADAS (5)

| Queue | Objetivo | Criterio Lifecycle | Acción recomendada |
|-------|----------|-------------------|-------------------|
| **REGISTERED_NO_FIRST_TRIP** | Activación | REGISTERED_NO_TRIPS | Contactar y asistir activación del primer viaje |
| **DECLINING_DRIVERS** | Retención | DECLINING o ACTIVE_LOW con 0 trips en 7d | Revisar caída operativa reciente. Contactar para retención preventiva |
| **AT_RISK_DRIVERS** | Recuperación temprana | AT_RISK (8-21d sin actividad) | Contactar antes de churn |
| **CHURNED_RECENT** | Reactivación | CHURNED_RECENT (22-60d) | Intentar reactivación. Evaluar incentivo |
| **HIGH_POTENTIAL_UNDERUTILIZED** | Incrementar supply | ACTIVE con t30 > 0 y t7 < 25% de t30 | Driver con buen historial pero baja utilización reciente |

---

## 3. PRIORITY ENGINE (DETERMINÍSTICO)

| Prioridad | Reglas |
|-----------|--------|
| **CRITICAL** | AT_RISK con phone y ≤14d sin actividad. DECLINING con 0 trips en 7d y phone. |
| **HIGH** | AT_RISK con phone. DECLINING con phone. REGISTERED sin viaje con phone. CHURNED muy reciente (≤30d) con phone. UNDERUTILIZED severo (<5 trips) con phone. |
| **MEDIUM** | Sin phone → baja un nivel. CHURNED con phone. UNDERUTILIZED con phone. REGISTERED sin phone. |
| **LOW** | Sin phone en cualquier queue no crítica. Identity confidence baja. Data quality degraded. |

### Penalizaciones
- **No phone** → prioridad baja 1 nivel
- **Stale data** → prioridad baja, marcado warning
- **Identity confidence low** → prioridad baja a LOW

---

## 4. ACTIONABILITY RULES

Cada entry devuelve:
- `action_reason` — texto explicativo basado en datos reales
- `evidence` — trips_7d, trips_30d, trips_60d, days_since, has_first_trip, has_phone
- `recommended_action` — acción concreta por queue type
- `queue_priority` — CRITICAL / HIGH / MEDIUM / LOW con `priority_reason`
- `data_quality_status` — ok / warning / error / blocked

### Trazabilidad
Toda clasificación es explicable con los campos `action_reason`, `priority_reason`, y `evidence`. No hay black box.

---

## 5. ENDPOINT CONTRACTS

### 5.1 GET /drivers/actionable-list

**Query params:** queue_type, queue_priority, lifecycle_stage, country, city, park_id, has_phone, limit, offset

**Response shape:**
```json
{
  "status": "ok",
  "summary": {
    "total_in_all_queues": 523,
    "critical": 12,
    "high": 145,
    "medium": 230,
    "low": 136,
    "by_queue": {
      "REGISTERED_NO_FIRST_TRIP": 89,
      "DECLINING_DRIVERS": 156,
      "AT_RISK_DRIVERS": 98,
      "CHURNED_RECENT": 134,
      "HIGH_POTENTIAL_UNDERUTILIZED": 46
    }
  },
  "queues": [
    {
      "queue_type": "AT_RISK_DRIVERS",
      "queue_label": "At-Risk Drivers",
      "queue_priority": "CRITICAL",
      "priority_reason": "AT_RISK with phone, last activity ≤ 14d. Critical recovery window.",
      "driver_id": "...",
      "driver_name": "Carlos Pérez",
      "phone": "+57 300...",
      "has_phone": true,
      "country": "Colombia",
      "city": "Bogotá",
      "park_id": "...",
      "park_name": "Park Centro",
      "lifecycle_stage": "AT_RISK",
      "activity_trend": "declining",
      "trips_7d": 0,
      "trips_30d": 45,
      "days_since_last_trip": 12,
      "action_reason": "No trips in last 12 days. Previously had 45 trips in last 30d.",
      "evidence": {"trips_7d": 0, "trips_30d": 45, "has_phone": true, ...},
      "recommended_action": "Contactar antes de churn. Última actividad entre 8-21 días.",
      "freshness_status": "fresh",
      "data_quality_status": "ok",
      "identity_confidence": "high",
      "assigned_owner": null,
      "queue_generated_at": "2026-05-25T..."
    }
  ],
  "total": 523,
  "limit": 100,
  "offset": 0,
  "warnings": [],
  "blocking_gaps": []
}
```

### 5.2 GET /drivers/actionable-summary

Aggregate view with quality metadata, phone coverage, and warnings.

---

## 6. FACT DESIGN

### ops.driver_supply_actionable_fact (DISEÑADA, no materializada)

Postergada. El servicio `driver_actionable_supply_service.py` genera las queues en runtime sobre `driver_daily_activity_fact` + identity sources. Es suficiente para D4. La fact materializada se creará cuando los refresh pipelines estén estables.

---

## 7. UX PRINCIPLES

1. **Tabla operacional limpia** — 10 columnas, no 50
2. **Prioridad visible inmediatamente** — badges de color
3. **Phone indicator** — check/cross
4. **Métricas clave** — 7d, 30d, days_since
5. **Acción recomendada visible** — texto claro y directo
6. **Filtro por queue** — pills de navegación
7. **Summary cards** — totales y prioridades críticas

### Qué NO está en la tabla
- No 50 columnas
- No kanban
- No drag/drop
- No workflows de edición
- No IA ni scoring

---

## 8. DATA QUALITY DEPENDENCIES

| Dependencia | Impacto en D4 |
|-------------|---------------|
| `ops.driver_daily_activity_fact` refrescada | Si stale → todos los queues desactualizados |
| `public.drivers_data.phone` | Sin phone → contactability limitada → prioridad baja |
| `ops.v_dim_driver_resolved` (nombres) | Sin nombre → identidad es UUID |
| Identity confidence | Baja → prioridad forzada a LOW |

---

## 9. QUÉ NO PERTENECE TODAVÍA

| Capacidad | Por qué no |
|-----------|------------|
| Workflow de asignación (assigned_owner real) | Requiere modelo de usuarios + roles. D5. |
| Scoring ML de recoverability | Requiere Reachability Engine (BACKLOG). |
| Forecast de churn | Requiere Forecast Engine (BACKLOG). |
| Automatización de contacto | Requiere Action Engine (BACKLOG). |
| IA Copilot | BACKLOG. |
| Kanban / drag-drop | Prematuro sin workflow foundation. |

---

## 10. GO / NO-GO

### GO
- 5 queues operacionales implementadas
- Priority engine determinístico (4 niveles)
- 2 endpoints (`/drivers/actionable-list`, `/drivers/actionable-summary`)
- Frontend con tabla operacional, pills de queue, summary cards
- Phone indicator, priority badges, recommended actions visibles
- 0 queries rotas, 0 tabs ocultas

### D5 habilitado
Con queues + identity + activity + lifecycle funcionando, D5 puede:
1. Agregar workflow básico (assigned_owner real)
2. Filtrar por owner
3. Tracking de acciones tomadas
4. Integrar con sistema de accountability existente

---

## 11. ARCHIVOS CREADOS/MODIFICADOS

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/app/services/driver_actionable_supply_service.py` | NUEVO | 5 queues + priority engine + batch query con CTEs |
| `backend/app/routers/drivers.py` | MOD | +2 endpoints actionable |
| `frontend/src/components/driver/DriverActionableLists.jsx` | NUEVO | Tabla operacional con pills, summary cards, badges |
| `frontend/src/App.jsx` | MOD | Route + import + rendering de action queues |
| `frontend/src/config/controlTowerNavigationRegistry.js` | MOD | Entry `drivers_action_queues` |
| `frontend/src/config/operationalMaturityRegistry.js` | MOD | Entry `drivers_action_queues` (HARDENING, D4) |
| `frontend/src/components/driver/DriverOperatingHub.jsx` | MOD | Lifecycle card en action queues tab |
| `docs/drivers/DRIVER_ACTIONABLE_SUPPLY_ENGINE_D4.md` | NUEVO | Este documento |

---

**FIN DEL DOCUMENTO D4**
