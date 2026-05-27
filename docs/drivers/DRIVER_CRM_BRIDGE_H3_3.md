# DRIVER CRM BRIDGE & SYNC LAYER — FASE H3.3

**Fecha:** 2026-05-26
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase:** H3.3 — CRM Bridge & Sync Layer

---

## 1. FILOSOFÍA ESTRATÉGICA

Drivers es el source of truth estratégico. El CRM es el execution engine de comunicación.

Drivers NO se convierte en CRM. El CRM NO se convierte en Drivers.

```
Drivers Intelligence → Campaign Object → CRM Sync Export → CRM Execution → CRM Outcomes → Drivers Progress → Drivers Learning
```

---

## 2. DRIVERS VS CRM

| Drivers | CRM |
|---------|-----|
| Define universos y cohorts | Ejecuta outreach |
| Segmenta y prioriza | Orquesta canales (call, WhatsApp, SMS) |
| Congela miembros | Contacta drivers |
| Expone payload | Consume members API |
| Recibe outcomes | Envía resultados |
| Mide efectividad | Mide eficiencia operativa |
| **Source of truth estratégico** | **Execution engine táctico** |

---

## 3. SYNC LIFECYCLE

```
DRAFT → READY_FOR_CRM → EXPORTING → EXPORTED → (CRM executions) → IMPORTING_OUTCOMES → COMPLETED / PARTIAL
```

- **EXPORTING:** Drivers genera payload CRM-ready y registra sync_started
- **EXPORTED:** Payload disponible. CRM puede consumir members API
- **IMPORTING_OUTCOMES:** CRM envía resultados vía POST outcomes
- **COMPLETED:** Todos los outcomes procesados sin errores
- **PARTIAL:** Algunos outcomes fallaron (miembros no encontrados, datos inválidos)

---

## 4. EXPORT PAYLOAD CONTRACT

```
GET /drivers/campaigns/{id}/crm-export
```

Response:
```json
{
  "sync_id": "...",
  "campaign": { "campaign_id", "campaign_name", "campaign_type", "objective", "country", "city" },
  "members": [
    {
      "campaign_member_id", "driver_id", "driver_name", "phone",
      "country", "city", "park_id",
      "queue_type", "lifecycle_stage", "priority",
      "reason", "recommended_action"
    }
  ],
  "metadata": { "generated_at", "total_members", "with_phone" }
}
```

---

## 5. IMPORT OUTCOMES CONTRACT

```
POST /drivers/campaigns/{id}/crm-sync/outcomes
```

Body:
```json
{
  "crm_system_name": "...",
  "crm_campaign_reference": "...",
  "outcomes": [
    {
      "campaign_member_id": "...",
      "driver_id": "...",
      "execution_status": "CONTACTED|RECOVERED|NO_RESPONSE|BAD_PHONE|...",
      "outcome": "...",
      "attempt_number": 1,
      "contacted_at": "2026-05-26T14:30:00Z",
      "executed_by": "...",
      "notes": "..."
    }
  ]
}
```

Partial success: outcomes inválidos o miembros no encontrados se registran como warnings. No bloquean el batch.

---

## 6. SYNC STATUSES

| Status | Descripción |
|--------|-------------|
| PENDING | Campaña lista, no sync iniciado |
| READY | Campaña marcada para CRM |
| EXPORTING | Generando payload |
| EXPORTED | Payload disponible |
| IMPORTING_OUTCOMES | Recibiendo resultados del CRM |
| COMPLETED | Sync completo sin errores |
| PARTIAL | Sync completo con algunos errores |
| FAILED | Sync fallido (requiere retry) |

---

## 7. GRACEFUL DEGRADATION

Si el CRM falla o no está disponible:
- Las campañas siguen existiendo en DRAFT/READY
- Las Action Queues siguen operativas
- Los workflows siguen operativos
- El Pilot Workboard sigue funcional
- Supply Overview sigue funcional
- Se muestra warning en CRM Bridge UI
- El operador puede reintentar export cuando el CRM vuelva

**Principio:** CRM failure != Drivers failure.

---

## 8. AUDITABILITY

Cada sync registra:
- **Sync record** (`ops.driver_campaign_sync`): sync_id, campaign_id, direction, status, counts, timestamps, actor
- **Sync log** (`ops.driver_campaign_sync_log`): evento individual, member_id, status, message, timestamp

Cada outcome actualiza:
- **Member execution_status**: estado de ejecución actual
- **Member attempts_count**: número de intentos de contacto
- **Member latest_contact_at**: última fecha de contacto
- **Member executed_by**: quién ejecutó el contacto

---

## 9. QUÉ NO PERTENECE AQUÍ

- Automatización de envío a CRM (el operador exporta manualmente)
- Integración con CRM específico (el bridge es agnóstico)
- Webhook entrante automático (POST manual o vía polling del CRM)
- Multi-canal orchestration
- Templates de mensajes
- Scheduling de campañas
- A/B testing de mensajes

---

## 10. TABLAS CREADAS

| Tabla | Schema | Propósito |
|-------|--------|-----------|
| `ops.driver_campaign_sync` | Sync tracking: dirección, status, counts, timestamps, actor |
| `ops.driver_campaign_sync_log` | Event log: export_started, export_completed, outcome_ingested, outcome_skipped |

Columnas agregadas a `ops.driver_campaign_members`:
| Columna | Tipo | Propósito |
|---------|------|-----------|
| execution_status | VARCHAR(30) | NOT_CONTACTED → CONTACTED → RECOVERED... |
| attempts_count | INTEGER | Número de intentos de contacto |
| latest_contact_at | TIMESTAMPTZ | Última fecha de contacto |
| executed_by | VARCHAR(128) | Quién ejecutó el contacto |

---

## 11. GO/NO-GO

### GO para H3.4 Campaign Effectiveness:
- [X] CRM bridge operativo con export/import
- [X] Sync tracking y auditability
- [X] Execution status tracking en members
- [X] Campaign progress computado
- [X] Graceful degradation implementado
- [X] Backend compile + Frontend build PASS

### H3.4 podrá:
1. Medir lift de campañas vs baseline
2. Comparar efectividad entre campañas
3. Calcular ROI por campaña
4. Identificar patrones de recovery por queue_type

---

**FIN DEL DOCUMENTO H3.3**
