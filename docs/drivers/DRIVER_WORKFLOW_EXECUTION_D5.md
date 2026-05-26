# DRIVER WORKFLOW & EXECUTION LOOP — FASE D5

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Control Foundation
**Sub-fase Drivers:** D5 — Workflow & Operational Execution

---

## 1. GOVERNANCE CHECK

- **ACTIVE:** Control Foundation 1H.4 — D5 compatible
- **NO AI Copilot, NO Decision Engine, NO automatizaciones**
- **GO**

---

## 2. WORKFLOW STATE MACHINE

### Estados (7 activos + BLOCKED)

| Estado | Definición | Significado operacional |
|--------|-----------|------------------------|
| **UNASSIGNED** | Nadie lo ha tomado | En cola, esperando owner |
| **ASSIGNED** | Owner asignado | Listo para trabajar |
| **IN_PROGRESS** | Trabajo iniciado | En proceso de contacto |
| **CONTACTED** | Driver contactado | Esperando respuesta/resultado |
| **NO_RESPONSE** | Sin respuesta | Requiere follow-up |
| **RECOVERED** | Recuperado/reactivado | Caso exitoso |
| **CLOSED** | Cerrado (cualquier outcome) | Finalizado |
| **BLOCKED** | Bloqueado (phone inválido, data stale) | Requiere remediation |

### Transiciones permitidas

```
UNASSIGNED → ASSIGNED, BLOCKED
ASSIGNED   → IN_PROGRESS, UNASSIGNED, BLOCKED, CLOSED
IN_PROGRESS→ CONTACTED, NO_RESPONSE, RECOVERED, CLOSED, BLOCKED, ASSIGNED
CONTACTED  → IN_PROGRESS, RECOVERED, NO_RESPONSE, CLOSED
NO_RESPONSE→ IN_PROGRESS, CLOSED, BLOCKED
RECOVERED  → CLOSED, IN_PROGRESS
CLOSED     → (terminal)
BLOCKED    → ASSIGNED, CLOSED
```

---

## 3. TABLES

### ops.driver_supply_workflow
- `workflow_id` UUID PK
- `queue_type` — tipo de cola
- `driver_id` — FK a drivers
- `workflow_status` — estado actual
- `assigned_owner`, `assigned_at`
- `last_action_at`, `latest_action_type`, `latest_action_note`, `latest_action_result`
- `latest_contact_channel`, `resolution_reason`, `resolution_outcome`
- UNIQUE(driver_id, queue_type) — un workflow por driver-queue

### ops.driver_supply_action_log
- `action_id` UUID PK
- `workflow_id` FK
- `driver_id`
- `action_type` — CALL_ATTEMPT, WHATSAPP_SENT, DRIVER_CONTACTED, FOLLOW_UP, DRIVER_RECOVERED, NO_RESPONSE, INVALID_PHONE, CLOSED_CASE, ASSIGNED, NOTE
- `action_note`, `action_result`, `action_channel`
- `action_actor` — quién ejecutó
- `previous_status`, `new_status` — audit trail
- `created_at`

---

## 4. ENDPOINTS

| Método | Ruta | Propósito |
|--------|------|-----------|
| POST | `/drivers/workflow/assign` | Asignar owner a workflow |
| POST | `/drivers/workflow/action` | Registrar acción en log |
| POST | `/drivers/workflow/status` | Cambiar estado con validación de transición |
| GET | `/drivers/workflow` | Listar workflows (filtros: owner, status, queue, driver) |
| GET | `/drivers/workflow/{id}` | Detalle workflow + history |
| GET | `/drivers/workflow-metrics` | Métricas de accountability |

---

## 5. ACCOUNTABILITY METRICS

- Total workflows
- Por estado (UNASSIGNED, ASSIGNED, IN_PROGRESS, CONTACTED, NO_RESPONSE, RECOVERED, CLOSED, BLOCKED)
- Por owner (top 20)
- Owners activos count

---

## 6. UX PRINCIPLES

1. **Quick actions en la tabla** — sin modales, sin navegación extra
2. **Buttons contextuales** — según estado actual del workflow
3. **Owner filter** — input de texto simple
4. **Workflow status badge** — visible en cada fila
5. **Auditability** — cada acción guarda actor + timestamp + previous/new status

### Quick actions por estado
- UNASSIGNED → [Assign]
- ASSIGNED/IN_PROGRESS → [Contacted] [No Resp]
- CONTACTED/NO_RESPONSE → [Recover]
- Cualquiera → [Close]

---

## 7. QUÉ NO PERTENECE TODAVÍA

- Email/SMS automáticos (Reachability Engine)
- Workflows multi-step rule-based (Decision Engine)
- SLA tracking (Forecast Engine)
- AI-assisted prioritization (AI Copilot)
- Bulk operations
- Templates de mensajes
- Reportes avanzados de ejecución

---

## 8. GO / NO-GO

### GO
- 8 estados workflow con transiciones validadas
- 2 tablas (workflow + action_log) con audit trail completo
- 6 endpoints CRUD + métricas
- Quick actions integrados en Action Queues
- 0 queries rotas, 0 tabs ocultas

### D5 completa el loop operacional humano
D1→D5 forma un sistema completo:
- Governance (D1)
- Identity + Phone (D2)
- Activity + Lifecycle (D3)
- Actionable Queues (D4)
- Workflow Execution (D5)

---

## 9. ARCHIVOS

| Archivo | Tipo |
|---------|------|
| `backend/app/services/driver_workflow_service.py` | NUEVO — State machine, CRUD, métricas |
| `backend/app/routers/drivers.py` | MOD — +6 endpoints workflow |
| `frontend/src/components/driver/DriverActionableLists.jsx` | MOD — Quick actions + workflow badges |
| `docs/drivers/DRIVER_WORKFLOW_EXECUTION_D5.md` | NUEVO |
