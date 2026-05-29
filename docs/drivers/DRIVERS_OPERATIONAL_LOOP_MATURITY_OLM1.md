# Drivers — Operational Loop Maturity (OLM1)

## 1. Operational Loop

El loop operativo de Drivers sigue 9 etapas:

```
Detection → Prioritization → Campaign Creation → CRM Export
     → Execution → Outcome Ingest → Follow-up → Effectiveness → Learning Notes
```

| Etapa | Owner | Input | Output |
|-------|-------|-------|--------|
| 1. Detection | Sistema | Serving facts | Conductores en queues accionables |
| 2. Prioritization | Sistema + Supervisor | Queues con scores | Conductores priorizados |
| 3. Campaign Creation | Supervisor | Prioridades + filtros | Campaña con universo congelado |
| 4. CRM Export | Operador | Campaña lista | Lista exportada al CRM |
| 5. Execution | CRM / Call Center | Lista de conductores | Intentos de contacto |
| 6. Outcome Ingest | Operador | Resultados del CRM | Outcomes registrados |
| 7. Follow-up | Operador + Supervisor | Outcomes clasificados | Decisiones de segundo intento |
| 8. Effectiveness | Supervisor | Viajes pre/post | Cambio observado |
| 9. Learning Notes | Supervisor | Resultados medidos | Decisión repetir/pausar/cerrar |

## 2. Estados del Loop

Campo derivado (no reemplaza campaign_status):

| Estado | Significado |
|--------|-------------|
| DETECTED | Conductores identificados en queues |
| PRIORITIZED | Priorizados por urgencia/recuperabilidad |
| CAMPAIGN_DRAFT | Campaña creada, pendiente de enviar |
| READY_FOR_CRM | Lista lista para el CRM |
| SENT_TO_CRM | Enviada, esperando ejecución |
| IN_EXECUTION | CRM ejecutando contacto |
| OUTCOMES_RECEIVED | Resultados importados |
| FOLLOW_UP_PENDING | Seguimiento necesario |
| MEASURED | Efectividad calculada |
| CLOSED | Campaña cerrada |
| NEEDS_REVIEW | Requiere revisión manual |

## 3. Next Human Action

Lógica determinística que indica qué debe hacer el humano:

| Acción | Label | Owner | Urgencia |
|--------|-------|-------|----------|
| CREATE_CAMPAIGN | Crear campaña | Supervisor | Media |
| EXPORT_TO_CRM | Exportar al CRM | Operador | Alta |
| IMPORT_OUTCOMES | Importar resultados | Operador | Alta |
| REVIEW_BAD_PHONES | Revisar teléfonos incorrectos | Data Quality | Media |
| FOLLOW_UP_SECOND_ATTEMPT | Segundo intento | Operador | Media |
| WAIT_MEASUREMENT_WINDOW | Esperar ventana medición | Sistema | Baja |
| REVIEW_EFFECTIVENESS | Revisar resultado observado | Supervisor | Media |
| CLOSE_CAMPAIGN | Cerrar campaña | Supervisor | Baja |

## 4. Follow-up Logic

Clasificación determinística post-outcomes:

| Outcome | Condición | Resultado |
|---------|-----------|-----------|
| NO_RESPONSE | attempts < 3 | FOLLOW_UP_PENDING |
| BAD_PHONE | — | DATA_QUALITY_REVIEW |
| PROMISED_RETURN | sin viajes D+7 | FOLLOW_UP_PENDING |
| RETURNED | con viajes | RECOVERED_OBSERVED |
| IRRECOVERABLE | — | CLOSED_IRRECOVERABLE |

## 5. Campaign Operating Board

Vista agrupada por etapa del loop:

- **Listas para CRM** (CAMPAIGN_DRAFT + READY_FOR_CRM)
- **En ejecución** (SENT_TO_CRM + IN_EXECUTION)
- **Esperando resultados** (OUTCOMES_RECEIVED)
- **Seguimiento pendiente** (FOLLOW_UP_PENDING)
- **Esperando medición** (campañas sin ventana cumplida)
- **Medidas** (MEASURED)
- **Necesitan revisión** (NEEDS_REVIEW)

## 6. Human Handoff

Ver: [DRIVERS_OPERATOR_HANDOFF_GUIDE.md](./DRIVERS_OPERATOR_HANDOFF_GUIDE.md)

Resumen del flujo humano:
1. Supervisor abre Operating Board
2. Identifica campañas pendientes de acción
3. Lee "Siguiente acción" para cada una
4. Ejecuta la acción (exportar, importar, revisar)
5. El loop avanza automáticamente al registrarse el cambio

## 7. Supervisor Runbook

Ver: [DRIVERS_SUPERVISOR_RUNBOOK.md](./DRIVERS_SUPERVISOR_RUNBOOK.md)

## 8. GO/NO-GO para Piloto Humano Real

### Criterios GO

- [x] Loop model implementado con 9 etapas
- [x] Estados del loop derivados automáticamente
- [x] Next human action visible en Campaign Detail
- [x] Operating Board funcional agrupando campañas
- [x] Follow-up logic clasificando outcomes
- [x] QA Checklist disponible por campaña
- [x] Docs de operador y supervisor creados
- [x] Builds exitosos (backend + frontend)
- [x] Campaign Intelligence intacto
- [x] CRM Bridge intacto
- [x] Effectiveness intacto

### Criterios NO-GO (bloqueos)

- [ ] Si no hay serving facts frescos → esperar refresh
- [ ] Si el CRM no tiene integración API → usar export manual
- [ ] Si no hay campañas creadas → crear primera campaña de prueba

### Recomendación

**GO** — El sistema está listo para que Gonzalo pruebe el flujo completo como operador humano:
1. Crear campaña desde Builder
2. Verificar Operating Board
3. Exportar al CRM
4. Simular import de outcomes
5. Revisar follow-up y effectiveness
6. Cerrar campaña

## Endpoints OLM1

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | /drivers/operational-loop/model | Modelo conceptual del loop |
| GET | /drivers/campaigns/operating-board | Board agrupado por etapa |
| GET | /drivers/campaigns/{id}/loop-status | Estado del loop + next action |
| GET | /drivers/campaigns/{id}/follow-up | Clasificación de follow-ups |
| GET | /drivers/campaigns/{id}/qa-checklist | Checklist de QA humano |
