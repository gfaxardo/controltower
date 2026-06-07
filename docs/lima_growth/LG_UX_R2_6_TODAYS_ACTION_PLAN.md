# LG-UX-R2.6 — Today's Action Plan

**Date:** 2026-06-06
**Phase:** LG-UX-R2.6 Today's Action Plan
**Scope:** Transform Command Center into an operational console.
**Rule:** NO IA. NO Forecast. NO Suggestion. Deterministic only.

---

## 1. CONTRATO — today_action_plan

```json
{
  "date": "2026-06-02",
  "freshness": { /* 5 domains */ },
  "operational_status": "READY_WITH_BLOCKERS",

  "capacity": {
    "available": 310,
    "configured": 3,
    "utilization_pct": 161.3,
    "channels": [
      {"channel": "Call Center", "agents": 2, "capacity_per_agent": 40, "channel_capacity": 80},
      {"channel": "SAC", "agents": 1, "capacity_per_agent": 30, "channel_capacity": 30},
      {"channel": "Bot / WhatsApp", "agents": 1, "capacity_per_agent": 200, "channel_capacity": 200}
    ]
  },

  "workload": {
    "ready": 150,
    "held": 190,
    "exported": 51,
    "total": 500,
    "queue_status": "READY"
  },

  "gap": {
    "available_capacity": 310,
    "missing_capacity": 190,
    "excess_capacity": 0,
    "actionable_total": 500,
    "gap_description": "Capacidad insuficiente: 190 accionables exceden la capacidad de 310"
  },

  "priorities": [
    {
      "priority_position": 1,
      "program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
      "program_name": "High Value Recovery",
      "reason": "80 accionables, 80 en cola"
    },
    {
      "priority_position": 2,
      "program_code": "PROGRAM_CHURN_PREVENTION",
      "program_name": "Churn Prevention",
      "reason": "7816 elegibles, 420 accionables, 420 en cola"
    }
  ],

  "blockers": [
    {
      "blocker": "SIN_CANAL_ASIGNADO",
      "severity": "HIGH",
      "count": 190,
      "description": "190 conductores retenidos: Sin canal asignado",
      "remediation": "Ejecutar channel allocation para asignar canales",
      "action_required": true
    },
    {
      "blocker": "CAPACITY_GAP",
      "severity": "HIGH",
      "count": 190,
      "description": "Hay 190 accionables sin capacidad operativa",
      "remediation": "Aumentar capacidad en Configuracion o ajustar daily_action_capacity",
      "action_required": true
    }
  ],

  "recommended_actions": [
    {
      "priority": 1,
      "action": "Exportar 150 conductores READY",
      "action_type": "EXPORT",
      "reason": "Hay 150 conductores listos con telefono y canal asignado esperando exportacion",
      "expected_effect": "Enviar 150 conductores a LoopControl para gestion"
    },
    {
      "priority": 2,
      "action": "Resolver 190 HELD: Sin canal asignado",
      "action_type": "RESOLVE",
      "reason": "190 conductores retenidos por 'Sin canal asignado'",
      "expected_effect": "Liberar 190 conductores a estado READY para exportacion"
    },
    {
      "priority": 3,
      "action": "Asignar canal a 190 conductores HELD",
      "action_type": "ASSIGN_CHANNEL",
      "reason": "190 conductores no tienen canal asignado",
      "expected_effect": "Habilitar 190 conductores para exportacion a LoopControl"
    },
    {
      "priority": 4,
      "action": "Priorizar Programa: High Value Recovery",
      "action_type": "PRIORITIZE",
      "reason": "Programa con mayor prioridad operativa. 80 accionables, 80 en cola",
      "expected_effect": "Gestionar 80 conductores del programa prioritario"
    },
    {
      "priority": 6,
      "action": "Capacidad ociosa: 160 slots disponibles",
      "action_type": "NOTICE",
      "reason": "Capacidad (310) > READY (150). 160 slots sin utilizar.",
      "expected_effect": "Aumentar daily_action_capacity o construir mas cola para aprovechar capacidad"
    },
    {
      "priority": 7,
      "action": "Ajustar capacidad: 190 accionables exceden la capacidad",
      "action_type": "ADJUST",
      "reason": "daily_action_capacity permite 500 accionables pero solo hay capacidad para 310",
      "expected_effect": "Reducir daily_action_capacity de 500 a 310 o aumentar capacidad"
    }
  ]
}
```

---

## 2. REGLAS DETERMINISTICAS

| # | Condicion | Accion | Tipo |
|---|-----------|--------|------|
| 1 | READY > 0 | Exportar READY | EXPORT |
| 2 | HELD > 0 | Resolver bloqueadores | RESOLVE |
| 3 | HELD por canal no asignado | Asignar canal | ASSIGN_CHANNEL |
| 4 | Programa con mayor actionable | Priorizar programa | PRIORITIZE |
| 5 | READY > Capacity | Ejecutar en multiples tandas | SCALE |
| 6 | READY < Capacity | Capacidad ociosa | NOTICE |
| — | Capacity < Actionable | Ajustar capacidad | ADJUST |

Todas las reglas son deterministicas. No AI, no scoring, no forecast.

---

## 3. PRIORIDADES

Las prioridades se calculan con score = (actionable × 3) + (queued × 2) + eligible. Se ordenan por:
1. Programas con actionable > 0 (is_priority = true) primero
2. Por priority_rank ascendente

Top 3 visible en el Action Plan.

---

## 4. BLOCKERS

Los blockers se detectan de:
- `hold_reasons` del queue_summary (HELD por telefono o canal)
- CAPACITY_GAP: cuando actionable_today > capacity_total
- PROGRAM_NOT_QUEUED: cuando un programa tiene accionables pero cero en cola

Cada blocker incluye severidad, conteo, descripcion, y remediacion.

---

## 5. OPERATIONAL STATUSES

| Status | Significado |
|--------|-------------|
| QUEUE_NOT_BUILT | Cola no construida — accion inmediata requerida |
| QUEUE_EMPTY | Cola vacia — verificar accionables |
| READY_TO_EXPORT | Todo listo — exportar |
| READY_WITH_BLOCKERS | Hay READY pero tambien HELD — resolver primero |
| ALL_HELD | Todo retenido — resolver blockers |
| ALL_EXPORTED | Todo procesado — dia completo |
| IDLE | Sin cambios |

---

## 6. LIMITACIONES

- NO tiene en cuenta Impact/ROI (bloqueado hasta R2.7+)
- NO predice resultados de las acciones
- NO recomienda canales especificos para asignar
- NO programa automaticamente las acciones
- NO integra con LoopControl para exportacion automatica
- Las acciones son sugerencias, no comandos automaticos
- Export via UI no actualiza queue_status (CERT-002 pendiente)

---

## 7. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/yego_lima_today_action_plan_service.py` | Servicio — consume servicios existentes, genera plan de accion |
| `backend/app/routers/yego_lima_today_action_plan.py` | Router — GET /yego-lima-growth/today-action-plan |
| `frontend/src/pages/lima-growth-v2/sections/TodayActionPlanSection.jsx` | Frontend — reemplaza Command Center |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/main.py` | Import + registro del router today_action_plan |
| `backend/app/services/yego_lima_queue_summary_service.py` | Fix: `yango` → `yego` en referencias a assignment_queue |
| `frontend/src/pages/LimaGrowthDashboardV2.jsx` | Reemplaza CommandCenterSection con TodayActionPlanSection |
| `frontend/src/pages/lima-growth-v2/hooks/useLimaGrowthData.js` | Agrega fetch de today-action-plan |
| `frontend/src/services/api.js` | Agrega getLimaGrowthTodayActionPlan() |

---

## 8. ENDPOINT

```
GET /yego-lima-growth/today-action-plan?date=YYYY-MM-DD
```

Response: `today_action_plan` contract (ver seccion 1).

---

## 9. EVIDENCIA FRONTEND

El Command Center ha sido reemplazado por "Today's Action Plan" como vista default:

- **Bloque 1:** Today Status — Capacity, READY, HELD, Exported, Gap + pipeline
- **Bloque 2:** Top Priorities — 3 programas prioritarios con razon
- **Bloque 3:** Blockers — bloqueadores activos con severidad y remediacion
- **Bloque 4:** Today Actions — lista ordenada de acciones con iconos, razon, y efecto esperado
- **Bloque 5:** Operational Health — freshness + health de Queue, Capacity, Export, Programs

El sidebar cambia: "Command Center" → "Today's Action Plan"

---

## 10. QA OPERACIONAL

**Pregunta:** Puede un supervisor iniciar el dia sin abrir otra pantalla?

**Respuesta:** SI (con condiciones)

**Justificacion:**

La pantalla Today's Action Plan responde "QUE HACEMOS HOY":

1. Muestra el estado operacional de un vistazo
2. Lista las acciones prioritarias en orden
3. Identifica bloqueadores con remediacion explicita
4. Muestra que programas requieren atencion
5. Indica si la cola fue construida o no
6. Expone capacidad vs demanda
7. Cada accion explica POR QUE existe y QUE EFECTO tendra

**Condiciones para que sea realmente autonomo:**
- La cola debe estar construida (si no, redirige a Execution Queue)
- CERT-002 (export no actualiza queue_status) debe resolverse para que READY/EXPORTED sean confiables
- Capacity config debe estar actualizada

---

## 11. BACKEND COMPILE

**OK**

## 12. FRONTEND BUILD

**PASS** (LimaGrowthDashboardV2: 42.17 kB, gzip 10.52 kB)

---

## 13. VEREDICTO

```
GO para LG-UX-R2.7 UX Operational Certification
```

**Evidencia:**
- Endpoint today-action-plan funcional con datos reales
- 6 acciones recomendadas generadas deterministicamente
- 2 blockers detectados (SIN_CANAL_ASIGNADO + CAPACITY_GAP)
- 2 prioridades identificadas (High Value Recovery + Churn Prevention)
- Frontend reemplaza Command Center con consola operativa
- Backend compile OK, Frontend build PASS
- Sin IA, sin forecast, sin nuevos motores
- Bug fix en queue_summary_service (yango → yego table references)
