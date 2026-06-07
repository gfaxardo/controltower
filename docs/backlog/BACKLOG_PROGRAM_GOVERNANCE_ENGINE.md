# BACKLOG — Program Governance Engine

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** Part of LG-UX-R2.5A Queue Certification — Parte B

---

## VISION

Los programas NO seran permanentemente STATIC_REGISTRY.

Evolucion aprobada:

```
STATIC_REGISTRY
    |
    v
PROGRAM_REGISTRY
    |
    v
PROGRAM_VERSIONING
    |
    v
PROGRAM_TUNING
    |
    v
PROGRAM_BUILDER
    |
    v
DYNAMIC_PROGRAM_ENGINE
```

---

## ESTADO ACTUAL (2026-06-06)

Los programas son STATIC_REGISTRY:
- Definidos en `backend/app/config/yego_lima_priority_registry.py`
- 4 programas hardcodeados:
  1. PROGRAM_HIGH_VALUE_RECOVERY
  2. PROGRAM_CHURN_PREVENTION
  3. PROGRAM_14_90
  4. PROGRAM_ACTIVE_GROWTH
- Sin versioning, sin audit trail, sin UI de edicion
- Las eligibility rules estan hardcodeadas en `opportunity_policy_service.py`
- La priority allocation usa PRIORITY_RANK hardcodeado
- El channel allocation es determinista pero no configurable via UI

---

## REQUISITOS FUTUROS

### 1. Program Auditability

Cada programa debe tener:
- `program_code` — identificador unico
- `program_name` — nombre para display
- `definition` — proposito operacional del programa
- `owner` — responsable del programa
- `version` — version actual (v1, v2, v3...)
- `rules` — reglas de elegibilidad, priorizacion, exclusion
- `created_at` — fecha de creacion
- `modified_at` — fecha de ultima modificacion
- `modified_by` — quien modifico
- `status` — ACTIVE, INACTIVE, DRAFT, ARCHIVED

### 2. Program Tuning

Modificar parametros operacionales con preview de impacto:
- `thresholds` — valores de corte para eligibility (ej: min_orders_7d)
- `windows` — ventanas temporales (ej: 7d, 14d, 30d, 90d)
- `segments` — segmentos target (ej: lifecycle_state, performance_state)
- `channels` — canales habilitados por programa

**Impact Preview requerido:**
```
Current Universe: 18,475
    |
    v  (aplicar cambios de threshold)
Projected Universe: 14,200
    |
    v  (aplicar elegibilidad)
Projected Eligible: 8,900
    |
    v  (aplicar priorizacion)
Projected Actionable: 420
```

### 3. Program Versioning

Historial de cambios auditable:
```
v1 (2026-05-15) — Version inicial, threshold = 5 orders
v2 (2026-06-01) — Ajuste threshold a 3 orders, +segmento HIGH_VALUE
v3 (2026-06-15) — Nuevo canal BOT habilitado
```

Cada version guarda snapshot completo de reglas. Rollback posible.

### 4. Dynamic Cohorts

Los programas guardan reglas, NO listas de conductores.

El Scheduler recalcula diariamente:
```
Universo (driver_state_snapshot)
    |
    v  (aplicar reglas de elegibilidad del programa)
Elegibles
    |
    v  (aplicar scoring + ranking)
Prioritized
    |
    v  (aplicar daily_action_capacity)
Actionable
```

Las reglas se evaluan contra el state snapshot actual. Sin listas estaticas.

### 5. Driver Explainability

Responder preguntas operacionales:
- "Why is this driver in this program?"
- "Why is this driver excluded?"
- "What rule did they pass/fail?"

Ejemplo:
```
Driver: Juan Perez (ID: ABC123)
Program: CHURN_PREVENTION
Status: ELIGIBLE
Rules passed:
  - lifecycle_state = AT_RISK (current: AT_RISK)  PASS
  - completed_orders_7d < 5 (current: 3)          PASS
  - supply_hours_7d > 10 (current: 15)            PASS
Rules failed: none
```

### 6. Impact Preview

Antes de guardar cambios a un programa:
```
Mostrar:
  Current Universe:  18,475
  Projected Universe: 16,800  (-1,675, -9.1%)
  Projected Eligible:   7,200  (-616, -7.9%)
  Projected Actionable:   380  (-40, -9.5%)
```

Con breakdown por:
- Conductores que ENTRAN al programa
- Conductores que SALEN del programa
- Impacto en otros programas (cannibalizacion)

### 7. Program Builder

**BLOQUEADO.** No habilitar antes de:

- R2.7 — Impact Tracking (medir que paso despues de la accion)
- Movement — entender trayectoria de conductores entre programas
- Attribution — atribuir cambios de estado a acciones especificas

Sin estos pilares, el Program Builder seria "editar a ciegas".

### 8. Governance Rule

**Ninguna implementacion futura puede asumir que STATIC_REGISTRY es el estado final del producto.**

Todo codigo nuevo que toque programas debe:
- Leer de un Program Registry (no de constantes hardcodeadas)
- Soportar versioning (campo `program_version` en tablas de hechos)
- Mantener audit trail (quien cambio que y cuando)
- No hardcodear program_code en queries (usar parametros)

---

## DEPENDENCIAS

| Dependencia | Estado | Bloquea |
|-------------|--------|---------|
| Program Registry (DB table) | NO IMPLEMENTADO | Program Auditability |
| Program Versioning (DB table) | NO IMPLEMENTADO | Versioning, Tuning |
| Impact Tracking (IF-1) | BACKLOG | Program Builder |
| Movement (AT-1) | BACKLOG | Driver Explainability |
| Attribution (AT-2) | BACKLOG | Impact Preview |
| Channel Allocation (LG-2.4) | IMPLEMENTADO | — |
| Priority Allocation (LG-2.3) | IMPLEMENTADO | — |

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Program Governance Engine
Registered: 2026-06-06
Phase: LG-UX-R2.5A — Parte B
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post R2.7 (Impact + Movement + Attribution)
```

---

## QA

- Documento creado: `docs/backlog/BACKLOG_PROGRAM_GOVERNANCE_ENGINE.md`
- Sin cambios funcionales nuevos
- Sin implementacion
