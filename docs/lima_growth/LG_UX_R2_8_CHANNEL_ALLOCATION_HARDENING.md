# LG-UX-R2.8 — Channel Allocation Hardening

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8 Channel Allocation Hardening
**Scope:** Eliminar el principal blocker operacional: HELD por canal no asignado.
**Rule:** NO IA. NO Program Builder. NO nuevos motores. Solo hardening.

---

## 1. CHANNEL AUDIT RESULTS

### 1.1 Canales detectados

| Canal | Agentes | Cap/Agente | Capacidad |
|-------|---------|------------|-----------|
| BOT | 1 | 200 | 200 |
| CALL_CENTER | 2 | 40 | 80 |
| SAC | 1 | 30 | 30 |
| **TOTAL** | **4** | | **310** |

### 1.2 Reglas de asignacion reales (extraidas del codigo)

Archivo: `yego_lima_channel_registry.py`

```
CALL_CENTER → SAC → BOT  (HIGH_VALUE_RECOVERY, CHURN_PREVENTION)
BOT → CALL_CENTER → SAC  (14_90, ACTIVE_GROWTH)
```

El assignment individual (worklist_service `_assign_channel`) asigna drivers a canales en orden de preferencia hasta agotar capacity.

### 1.3 Estado actual de la cola

| Canal | En Cola | READY | HELD | EXPORTED |
|-------|---------|:-----:|:----:|:--------:|
| BOT | 200 | 150 | 0 | 50 |
| CALL_CENTER | 80 | 0 | 0 | 80 |
| SAC | 30 | 0 | 0 | 30 |
| UNASSIGNED | 190 | 0 | 190 | 0 |
| **TOTAL** | **500** | **150** | **190** | **160** |

### 1.4 Por que existen HELD por canal?

**Respuesta:** La capacidad de canales (310) es menor que los accionables (500). El gap de 190 resulta en UNASSIGNED.

El macro allocation distribuye 310 entre todos los canales (100% utilizado). Cuando los canales se llenan, los drivers restantes quedan UNASSIGNED → HELD.

**Detalle:**
- PROGRAM_HIGH_VALUE_RECOVERY consume 80 en CALL_CENTER (lleno)
- PROGRAM_CHURN_PREVENTION consume 30 en SAC + 200 en BOT (ambos llenos)
- Los 190 restantes de CHURN_PREVENTION quedan sin canal

---

## 2. CHANNEL ALLOCATION CONTRACT

```json
{
  "channel_allocation_summary": {
    "total_unassigned": 190,
    "total_capacity": 310,
    "channels": [
      {
        "channel": "Bot / WhatsApp",
        "configured_capacity": 200,
        "assigned_in_queue": 200,
        "ready_in_queue": 150,
        "available_capacity": 0,
        "utilization_pct": 100.0,
        "is_full": true
      },
      {
        "channel": "Call Center",
        "configured_capacity": 80,
        "assigned_in_queue": 80,
        "ready_in_queue": 0,
        "available_capacity": 0,
        "utilization_pct": 100.0,
        "is_full": true
      },
      {
        "channel": "SAC",
        "configured_capacity": 30,
        "assigned_in_queue": 30,
        "ready_in_queue": 0,
        "available_capacity": 0,
        "utilization_pct": 100.0,
        "is_full": true
      },
      {
        "channel": "UNASSIGNED",
        "configured_capacity": 0,
        "assigned_in_queue": 190,
        "ready_in_queue": 0,
        "available_capacity": 0,
        "utilization_pct": 0,
        "is_full": false
      }
    ],
    "blockers": [
      "190 conductores sin canal asignado (UNASSIGNED)",
      "3 canales llenos (100% utilizacion)"
    ],
    "remediation": "Aumentar capacidad de canales en Configuracion o reducir daily_action_capacity"
  }
}
```

---

## 3. ASSIGNMENT RULES

### 3.1 Macro Level (Program → Channel distribution)

Servicio: `yego_lima_channel_allocation_service.py`

1. Toma la capacidad asignada a cada programa (de priority_allocation)
2. Itera los canales en orden de preferencia por programa
3. Asigna `min(remaining_program, remaining_channel)` a cada canal
4. Tracking de utilizacion por canal

### 3.2 Micro Level (Driver → Channel assignment)

Servicio: `yego_lima_opportunity_worklist_service.py:_assign_channel()`

1. Para cada driver en un programa, itera los canales por preferencia
2. Si el canal tiene capacidad (used < allocated_capacity), asigna
3. Si todos los canales estan llenos → UNASSIGNED

### 3.3 Channel Preferences

```python
PROGRAM_CHANNEL_PREFERENCE = {
    "PROGRAM_HIGH_VALUE_RECOVERY": ["CALL_CENTER", "SAC", "BOT"],
    "PROGRAM_CHURN_PREVENTION":    ["CALL_CENTER", "SAC", "BOT"],
    "PROGRAM_14_90":              ["BOT", "CALL_CENTER", "SAC"],
    "PROGRAM_ACTIVE_GROWTH":      ["BOT", "CALL_CENTER", "SAC"],
}
```

---

## 4. CHANNEL GAP ANALYSIS

| Metrica | Valor |
|---------|-------|
| Capacidad total configurada | 310 |
| Accionables hoy | 500 |
| En cola | 500 |
| Con canal asignado | 310 |
| Sin canal (UNASSIGNED) | 190 |
| Gap (accionables - capacidad) | 190 |
| Canales llenos | 3/3 (100%) |

---

## 5. QUEUE INTEGRATION

### Execution Queue ahora muestra:

- **UNASSIGNED como KPI visible:** Separado de HELD en el header de KPIs
- **ACTIVE count:** Total de registros activos (READY + HELD, sin EXPORTED)
- **Channel Utilization table:** Nueva seccion con capacidad, asignados, disponibles, utilizacion por canal
- **Canales llenos marcados:** Visualmente con "(lleno)" y color rojo

### Cambios en queue_summary_service:

- `totals.unassigned` — conductores sin canal
- `totals.active_total` — total activo (excluye EXPORTED)
- `channel_utilization[]` — capacidad, asignados, READY, disponible, utilizacion por canal
- `hold_reasons` remediation actualizada: "Capacidad de canales agotada"

---

## 6. TODAY ACTION PLAN INTEGRATION

### Capacity block mejorado:

Cada canal ahora incluye:
- `assigned_in_queue` — cuantos conductores usan este canal en la cola
- `ready_in_queue` — cuantos READY hay en este canal
- `available_capacity` — cuantos slots quedan disponibles
- `utilization_pct` — % de utilizacion
- `is_full` — flag de canal lleno

### Blockers mejorados:

- **CHANNEL_FULL blockers:** Detecta canales al 100% de utilizacion
- **Remediacion especifica por canal:** "Aumentar capacidad del canal 'X' en Configuracion"

---

## 7. CONTROL CONFIG INTEGRATION

La tabla de capacidad ahora muestra:
- **En Cola:** Cuantos conductores estan asignados a cada canal en la cola
- **Disp:** Capacidad disponible por canal
- **Barra de utilizacion:** Visual (verde < 80%, amarillo 80-100%, rojo = 100%)
- **Marcador "lleno":** Cuando el canal esta al 100%

---

## 8. EXPLAINABILITY

### Por que este conductor esta UNASSIGNED?

**Respuesta:** Todos los canales configurados (BOT=200, CALL_CENTER=80, SAC=30) estan llenos. La capacidad total (310) es menor que los accionables (500). 190 conductores no pueden ser asignados.

### Por que este canal esta lleno?

**Respuesta:** La capacidad configurada para este canal ha sido completamente ocupada por conductores de los programas con prioridad mas alta. Los programas compiten por capacidad limitada.

### Por que este canal tiene capacidad disponible?

**Respuesta:** No se han asignado suficientes conductores a este canal. Puede deberse a que los programas que prefieren este canal tienen menos accionables que la capacidad del canal, o a que canales de mayor preferencia absorbieron la demanda.

---

## 9. LIMITACIONES

- La asignacion de canales es estatica (no se recalcula al editar capacidad sin rebuild de cola)
- No hay rebalanceo automatico de canales
- Los canales se asignan en orden de preferencia; no hay load balancing
- UNASSIGNED solo se resuelve con mas capacidad o rebuild de cola
- No hay explicacion por driver individual de por que quedo UNASSIGNED (requiere Program Tuning)

---

## 10. ARCHIVOS CREADOS / MODIFICADOS

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `backend/app/services/yego_lima_queue_summary_service.py` | +unassigned, +active_total, +channel_utilization, remediation actualizada |
| `backend/app/services/yego_lima_today_action_plan_service.py` | +channel_details con utilization, +CHANNEL_FULL blockers |
| `frontend/src/pages/lima-growth-v2/sections/ExecutionQueueSection.jsx` | KPI UNASSIGNED + ACTIVE, Channel Utilization table |
| `frontend/src/pages/lima-growth-v2/sections/ControlConfigSection.jsx` | +En Cola, +Disp, +barras de utilizacion por canal |

### Creado:
| Archivo | Proposito |
|---------|-----------|
| `docs/lima_growth/LG_UX_R2_8_CHANNEL_ALLOCATION_HARDENING.md` | Este documento |

---

## 11. QA

| Check | Resultado |
|-------|:---------:|
| Backend compile | OK |
| Frontend build | PASS |
| UNASSIGNED visible en Queue | YES (KPI + Channel Utilization) |
| Capacity por canal con utilizacion | YES (Control Config) |
| Today Action Plan usa blockers reales | YES (CHANNEL_FULL + CAPACITY_GAP) |
| Explainability visible | YES (remediation actualizada) |
| No nuevos motores | YES |
| No AI | YES |
| No Program Builder | YES |

---

## 12. VEREDICTO

```
GO para R3.1 Program Registry Foundation
```

**Evidencia:**
- UNASSIGNED ahora visible como estado operacional explicito
- 3 canales detectados con capacidad y utilizacion documentadas
- 190 conductores UNASSIGNED explicados en contexto de capacidad
- Reglas de asignacion extraidas y documentadas (macro + micro)
- Channel Utilization integrado en Queue y Config
- Today Action Plan detecta canales llenos como blockers
- Backend compile OK, Frontend build PASS

---

## 13. WHAT REMAINS BLOCKED

| Motor | Status | Razon |
|-------|:------:|-------|
| Program Builder | BLOCKED | Requiere Impact + Movement + Attribution |
| Impact | BLOCKED | Hasta R3.x completion |
| Movement | BLOCKED | Hasta R3.x completion |
| Attribution | BLOCKED | Hasta R3.x completion |
| Forecast | BLOCKED | Control Foundation no cerrado |
| AI | BLOCKED | Motores deterministicos primero |
