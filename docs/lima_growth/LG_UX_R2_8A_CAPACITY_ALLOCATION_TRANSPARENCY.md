# LG-UX-R2.8A — Capacity Allocation Transparency

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8A Capacity Allocation Transparency + Prioritization Backlog
**Scope:** Make capacity allocation flow transparent. Register prioritization backlog.

---

## PARTE A — ALLOCATION TRACE

### 1. Current Allocation Rules

#### Macro Level (LG-2.3 Priority Allocation)

Programas reciben capacidad en orden de prioridad:

| Rank | Programa | Accionables | Recibio | Unmet |
|:----:|----------|:-----------:|:-------:|:-----:|
| 1 | High Value Recovery | 80 | 80 | 0 |
| 2 | Churn Prevention | 420 | 230 | 190 |
| 3 | 14/90 | 0 | 0 | 0 |
| 4 | Active Growth | 0 | 0 | 0 |

#### Micro Level (LG-2.4 Channel Allocation)

Cada programa distribuye su capacidad entre canales por preferencia:

| Programa | Preferencia Canal |
|----------|-------------------|
| High Value Recovery | CALL_CENTER → SAC → BOT |
| Churn Prevention | CALL_CENTER → SAC → BOT |
| 14/90 | BOT → CALL_CENTER → SAC |
| Active Growth | BOT → CALL_CENTER → SAC |

#### Individual Assignment (LG-2.5A Worklist)

Cada driver recibe el primer canal con capacidad disponible en orden de preferencia. Cuando todos los canales estan llenos → UNASSIGNED.

### 2. Current Allocation Trace

```
Step 1: High Value Recovery → Call Center: 80 asignados (capacidad restante: 0)
Step 2: Churn Prevention → SAC: 30 asignados (capacidad restante: 0)
Step 3: Churn Prevention → Bot/WhatsApp: 200 asignados (capacidad restante: 0)
Step 4: Churn Prevention → 190 RECHAZADOS (capacidad total agotada: 310 para 500 accionables)
Step 5: 14/90 → 0 asignados (capacidad agotada por programas de mayor prioridad)
Step 6: Active Growth → 0 asignados (capacidad agotada por programas de mayor prioridad)
```

### 3. Channel Consumption

| Canal | Capacidad | Asignado | Utilizacion | Llenado por |
|-------|:---------:|:--------:|:-----------:|-------------|
| Call Center | 80 | 80 | 100% | High Value Recovery (+80) |
| SAC | 30 | 30 | 100% | Churn Prevention (+30) |
| Bot/WhatsApp | 200 | 200 | 100% | Churn Prevention (+200) |

### 4. Program Consumption

| Programa | Accionables | Asignados | Sin Canal | % Cap | Razon |
|----------|:-----------:|:---------:|:---------:|:-----:|-------|
| High Value Recovery | 80 | 80 | 0 | 25.8% | Asignacion completa |
| Churn Prevention | 420 | 230 | 190 | 74.2% | 190 sin asignar: capacidad insuficiente |
| 14/90 | 0 | 0 | 0 | 0% | Sin accionables |
| Active Growth | 0 | 0 | 0 | 0% | Sin accionables |

### 5. UNASSIGNED Pressure

190 conductores sin canal. Todos de Churn Prevention.

**Razon:** La capacidad total (310) es insuficiente para 500 accionables. High Value Recovery (prioridad 1) consume 80 del Call Center. Churn Prevention (prioridad 2) recibe el resto (230 de 420). Los 190 restantes no tienen canal disponible.

**Que cambiaria para incluirlos:**
- Aumentar capacidad en canales llenos: Call Center, SAC, Bot / WhatsApp
- Reducir daily_action_capacity de 500 a 310
- Aumentar capacidad total en al menos 190 para cubrir el gap

### 6. Endpoint

```
GET /yego-lima-growth/capacity/allocation-trace?date=YYYY-MM-DD
```

Response: `allocation_trace` contract (ver seccion 2).

### 7. UI Integration

La seccion "Capacity Allocation Trace" en Control Config muestra:

1. **Resumen:** Accionables, Capacidad, Asignados, Sin Canal
2. **Consumo por Programa:** tabla con actionable, assigned, unassigned, % capacidad
3. **Consumo por Canal:** tabla con capacidad, asignado, utilizacion, llenado por programas
4. **Orden de Asignacion:** step-by-step con quien recibio y quien fue rechazado
5. **Explicacion:** por que quedaron UNASSIGNED
6. **Remediacion:** que cambiaria para incluirlos

### 8. Limitations

- Trace es agregado, no por conductor individual
- No muestra que conductor especifico quedo fuera ni por que
- No rebalancea canales automaticamente
- No sugiere cuanto aumentar cada canal
- La asignacion de canales es estatica (no se recalcula al editar sin rebuild)

---

## PARTE B — BACKLOG: OPPORTUNITY PRIORITIZATION ENGINE

Documentado en: `docs/backlog/BACKLOG_OPPORTUNITY_PRIORITIZATION_ENGINE.md`

Registra:
- Vision: mejores conductores primero cuando capacidad < demanda
- Priority Score formula: opportunity_score - fatigue_penalty
- Componentes propuestos con pesos sugeridos
- Fatigue Penalty por intentos sin respuesta
- UI requirements: trazabilidad por conductor
- Configurability futura
- Dependencias (Result Sync, Attribution)

**Status: BACKLOG — NO IMPLEMENTAR**

---

## ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/app/services/yego_lima_allocation_trace_service.py` | Allocation trace service |
| `backend/app/routers/yego_lima_allocation_trace.py` | Endpoint `/capacity/allocation-trace` |
| `docs/lima_growth/LG_UX_R2_8A_CAPACITY_ALLOCATION_TRANSPARENCY.md` | Este documento |
| `docs/backlog/BACKLOG_OPPORTUNITY_PRIORITIZATION_ENGINE.md` | Prioritization backlog |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/main.py` | +allocation_trace router import + registration |
| `frontend/src/services/api.js` | +getLimaGrowthAllocationTrace |
| `frontend/src/pages/lima-growth-v2/hooks/useLimaGrowthData.js` | +allocationTrace fetch |
| `frontend/src/pages/lima-growth-v2/sections/ControlConfigSection.jsx` | +AllocationTracePanel |

---

## QA

| Check | Resultado |
|-------|:---------:|
| Backend compile | OK |
| Frontend build | PASS |
| Endpoint /capacity/allocation-trace | Funcional (4 steps, 4 programs, 3 channels) |
| UI muestra allocation trace | YES (Control Config) |
| Explicacion de UNASSIGNED visible | YES |
| Backlog Opportunity Prioritization creado | YES |
| No nuevos motores | YES |
| No AI | YES |
| No reglas de asignacion modificadas | YES |

---

## VEREDICTO

```
GO para LG-UX-R2.8B Opportunity Prioritization Hardening
```

**Evidencia:**
- Allocation trace transparente: quien consume capacidad, quien queda fuera
- 500 accionables, 310 capacidad, 190 UNASSIGNED explicados
- 4 programas con consumo documentado
- 3 canales con utilizacion y programa que los lleno
- Backlog de priorizacion registrado
- UI muestra el trace completo con explicacion y remediacion
