# DRIVER CAMPAIGN INTELLIGENCE — FASE H3.2

**Fecha:** 2026-05-26
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase:** H3.2 — Campaign Intelligence Foundation

---

## 1. QUÉ ES CAMPAIGN INTELLIGENCE

La primera base de Campaign Intelligence dentro de Drivers. Convierte insights de la Intelligence Layer en campañas accionables con universos congelados, miembros trazables y contrato API definido para consumo del CRM.

**Flujo:**
```
Intelligence Layer → Action Queues → Campaign Builder → Frozen Cohort → CRM (ejecuta) → Outcomes → Metrics
```

---

## 2. QUÉ NO ES CAMPAIGN INTELLIGENCE

- No es un CRM
- No envía mensajes (WhatsApp, SMS, email)
- No automatiza comunicación
- No es un sistema de marketing
- No reemplaza al call center
- No hace scoring probabilístico
- No hace IA

---

## 3. RELACIÓN CON CRM

- **Drivers define:** Universo, segmentación, prioridad, cohortes congeladas
- **CRM ejecuta:** Comunicación, contacto, seguimiento
- **Drivers recibe:** Outcomes vía API de ingest
- **Drivers mide:** Efectividad de campaña (H3.4)

El CRM consume `GET /drivers/campaigns/{id}/members` y envía outcomes a `POST /drivers/campaigns/{id}/outcomes`.

---

## 4. CAMPAIGN OBJECT

### ops.driver_campaigns

| Campo | Tipo | Descripción |
|-------|------|-------------|
| campaign_id | UUID | PK |
| campaign_name | TEXT | Nombre operativo |
| campaign_type | VARCHAR(30) | RECOVERY, REACTIVATION, LOYALTY, etc. |
| campaign_objective | TEXT | Objetivo de la campaña |
| source_queue_types | TEXT[] | Queues fuente (AT_RISK, CHURNED, etc.) |
| cohort_definition_json | JSONB | Definición completa del cohorte |
| country, city, park_id | TEXT | Scope geográfico |
| lifecycle_stage | TEXT | Filtro de lifecycle |
| priority_filter | TEXT | Filtro de prioridad |
| target_count | INTEGER | Total de miembros |
| with_phone_count | INTEGER | Miembros con teléfono |
| without_phone_count | INTEGER | Miembros sin teléfono |
| campaign_status | VARCHAR(20) | DRAFT → READY_FOR_CRM → SENT_TO_CRM → IN_EXECUTION → COMPLETED/CANCELLED |
| crm_sync_status | VARCHAR(20) | NOT_SYNCED → READY → SYNCED → PARTIAL → FAILED |

### ops.driver_campaign_members

| Campo | Tipo | Descripción |
|-------|------|-------------|
| campaign_member_id | UUID | PK |
| campaign_id | UUID | FK a campaigns |
| driver_id | TEXT | Driver identity |
| *_snapshot | TEXT | Valores congelados al crear campaña |
| crm_status | VARCHAR(20) | PENDING → CONTACTED → NO_RESPONSE → BAD_PHONE → RETURNED |
| latest_outcome | TEXT | Último outcome recibido |
| outcome_at | TIMESTAMPTZ | Timestamp del outcome |

---

## 5. MEMBER SNAPSHOTS

Todos los campos de identity, lifecycle y priority se congelan al crear la campaña. Esto garantiza trazabilidad: el estado del driver en el momento de la campaña queda registrado, incluso si los datos fuente cambian después.

No se duplican tablas de identity como fuente viva. Los snapshots son históricos.

---

## 6. API CONTRACT CRM

### GET /drivers/campaigns/{id}/members

**Parámetros:**
- `only_with_phone=true` (default) — solo contactables
- `limit=200` (max 500)
- `offset=0`

**Response por miembro:**
```json
{
  "campaign_id": "...",
  "campaign_member_id": "...",
  "driver_id": "...",
  "driver_name": "Carlos Pérez",
  "phone": "+57 300...",
  "country": "Colombia",
  "city": "Bogotá",
  "park_id": "...",
  "queue_type": "AT_RISK_DRIVERS",
  "lifecycle_stage": "AT_RISK",
  "priority": "HIGH",
  "reason": "No trips in last 12 days...",
  "evidence": {"trips_7d": 0, "trips_30d": 45},
  "recommended_action": "Contactar antes de churn..."
}
```

### POST /drivers/campaigns/{id}/outcomes

**Body:**
```json
{
  "campaign_member_id": "...",
  "driver_id": "...",
  "crm_status": "CONTACTED|NO_RESPONSE|BAD_PHONE|PROMISED_RETURN|RETURNED|IRRECOVERABLE|OTHER",
  "outcome_note": "Driver contacted, will return next week",
  "outcome_at": "2026-05-26T14:30:00Z"
}
```

---

## 7. OUTCOME INGEST

El endpoint de outcomes actualiza `crm_status` y `latest_outcome` en `driver_campaign_members`. También actualiza `crm_sync_status` en la campaña (NOT_SYNCED → PARTIAL).

No mide lift ni efectividad todavía. Eso será H3.4 Campaign Effectiveness.

---

## 8. DATA QUALITY RULES

No se puede crear una campaña si:
- `estimated_total = 0` (no hay drivers en el universo)
- `freshness blocked` (fuentes de datos con gaps bloqueantes)
- `identity blocked`

Se genera WARNING (pero permite crear) si:
- `with_phone_count < 30%` del total
- `freshness warning` (fuentes stale)

---

## 9. ENDPOINTS

| Método | Ruta | Propósito |
|--------|------|-----------|
| POST | `/drivers/campaigns/preview` | Previsualizar cohorte sin persistir |
| POST | `/drivers/campaigns` | Crear campaña con miembros congelados |
| GET | `/drivers/campaigns` | Listar campañas con filtros |
| GET | `/drivers/campaigns/{id}` | Detalle de campaña + resumen miembros |
| GET | `/drivers/campaigns/{id}/members` | Miembros para CRM (API contract) |
| POST | `/drivers/campaigns/{id}/outcomes` | Ingest de outcomes desde CRM |
| GET | `/drivers/campaigns/{id}/summary` | Resumen agregado de campaña |

---

## 10. GO/NO-GO

### GO para H3.3 CRM Bridge:
- [X] Campaign definitions funcionales
- [X] Preview desde queues accionables
- [X] Miembros congelados con snapshots
- [X] API contract definido para CRM
- [X] Outcome ingest operativo
- [X] Backend compile + Frontend build PASS

### H3.3 podrá:
1. Implementar CRM Bridge con sincronización bidireccional
2. Automatizar el flujo SENT_TO_CRM → IN_EXECUTION
3. Sincronizar estados de miembros entre Drivers y CRM

---

## 11. PRÓXIMO PASO: H3.3 CRM BRIDGE

H3.3 convertirá el placeholder CRM Bridge en un puente real que:
- Envíe campañas al CRM (push de miembros)
- Reciba actualizaciones de estado del CRM (webhook o poll)
- Sincronice estados bidireccionalmente
- Maneje reintentos y errores de sincronización

---

**FIN DEL DOCUMENTO H3.2**
