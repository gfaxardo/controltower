# LG-UX-R2.8D — Priority Allocation Policy Correction

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8D Priority Allocation Policy Correction
**Scope:** Discovery + simulation + backlog. NO production changes.
**Rule:** NO new score. NO new engines. NO production changes.

---

## 1. PROBLEMA DESCUBIERTO

### Datos (2026-06-02)

| Metrica | Valor |
|---------|-------|
| Total actionable | 500 |
| Total capacity | 310 |
| HVR actionable | 80 |
| CP actionable | 420 |
| 14_90 actionable | 0 |
| AG actionable | 0 |
| Total unassigned | 190 |

### Distribucion actual

| Programa | Actionable | Asignado | Unmet | % Served |
|----------|:---:|:---:|:---:|:---:|
| High Value Recovery | 80 | **80** | 0 | 100% |
| Churn Prevention | 420 | **230** | 190 | 54.8% |
| 14/90 | 0 | 0 | 0 | — |
| Active Growth | 0 | 0 | 0 | — |

### Issues

1. **14/90 y AG reciben 0 siempre** si HVR y CP consumen toda la capacidad
2. **CP tiene 190 UNASSIGNED** sin remediacion — si tuviera un min_floor o CP tuviera max_cap, se podria redistribuir
3. **No hay forma de limitar** cuanto consume un programa — strict priority es inflexible
4. **No hay forma de asegurar piso** para programas de baja prioridad

---

## 2. POLITICA ACTUAL

### Hardcodes encontrados

| Hardcode | Archivo | Detalle |
|----------|---------|---------|
| PRIORITY_RANK | `yego_lima_priority_registry.py` | HVR=1, CP=2, 1490=3, AG=4 |
| allocate_capacity() | `yego_lima_priority_allocation_service.py:54` | `allocated = min(available, remaining)` — first program takes all |
| daily_action_capacity=500 | `opportunity_policy_config` | Default policy value |
| PROGRAM_BONUS | `opportunity_policy_service.py:380-384` | HVR=200, CP=100, 1490=50, AG=0 |
| channel_preferences | `yego_lima_channel_registry.py` | Hardcoded per program |

### Que es configurable hoy

- `daily_action_capacity` — via `opportunity_policy_config` table
- Capacidad por canal — via `capacity_config` table (agents × cap_per_agent)
- PRIORITY_RANK — SOLO editando el archivo Python (no via UI/DB)

### Que NO es configurable

- Min/max capacity por programa
- Target share por programa
- Program enabled/disabled
- Floor garantizado
- Cap maximo

---

## 3. ESCENARIOS SIMULADOS

### Escenario A: Actual (strict priority)
```
HVR=80 (100%), CP=230 (54.8%), 14_90=0, AG=0, Unassigned=190
```
HVR toma sus 80. CP toma el resto (230 de 420). 14_90 y AG no reciben nada.

### Escenario B: Max cap per program
```
HVR=80 (max 40%=124), CP=186 (max 60%=186), 14_90=0, AG=0, Unassigned=234
```
CP limitado a 186. 44 slots quedan sin usar (14_90 y AG no tienen actionable). **Peor que actual** para este dataset.

### Escenario C: Min floor per program
```
HVR=80 (floor=80), CP=230 (floor=50), 14_90=0 (floor=10), AG=0 (floor=10), Unassigned=190
```
Similar al actual porque los floors se satisfacen y CP consume el resto. 14_90/AG tendrian 10 cada uno si tuvieran actionable.

### Escenario D: Proportional share
```
HVR=50 (16% share), CP=260 (84% share), 14_90=0, AG=0, Unassigned=190
```
Distribucion proporcional a actionable count. HVR pierde 30 slots vs actual. CP gana 30. **Mas justo proporcionalmente.**

### Escenario E: Hybrid (priority + caps + floors)
```
HVR=80 (max 40%=124, floor=80), CP=170 (max 55%=170, floor=100), 14_90=0, AG=0, Unassigned=250
```
CP limitado a 170. 60 slots quedan sin usar. HVR sigue con 80. **Mayor unassigned pero mas controlado.**

### Comparacion

| Escenario | HVR | CP | Unassigned | Fairness |
|-----------|:---:|:---:|:---:|:---:|
| A: Current | 80 | 230 | 190 | N/A (baseline) |
| B: Max cap | 80 | 186 | 234 | CP limitado |
| C: Min floor | 80 | 230 | 190 | Similar a A |
| D: Proportional | 50 | 260 | 190 | Mas proporcional |
| E: Hybrid | 80 | 170 | 250 | Mas controlado |

---

## 4. RECOMENDACION

**Escenario E (Hybrid) como objetivo futuro**, pero NO para este dataset:

Para 2026-06-02, el escenario D (proportional) es el mas justo porque:
- CP tiene 84% de los accionables y recibe 84% de la capacidad
- HVR recibe lo proporcional (16%)
- Total unassigned no empeora (190)

El hybrid (E) es mejor cuando 14_90 y AG tengan accionables > 0 — los floors aseguran que no queden en 0.

**NO implementar todavia.** La simulacion muestra que:
- Sin 14_90/AG accionables, los cambios no mejoran el unassigned total
- El verdadero fix es aumentar capacidad (310 → 500) o reducir actionable (500 → 310)
- La policy de distribucion solo cambia QUIEN queda fuera, no CUANTOS

---

## 5. QUE NO SE IMPLEMENTO

- No se modifico la politica de asignacion en produccion
- No se cambiaron PRIORITY_RANKs
- No se agregaron caps/floors al codigo
- No se creo endpoint de policy config
- No se modifico la UI
- La simulacion es read-only, no afecta datos reales

---

## 6. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `backend/scripts/simulate_program_capacity_policy.py` | Simulador de 5 escenarios (read-only) |
| `exports/audits/lima_growth/program_capacity_policy_simulation.md` | Reporte markdown de simulacion |
| `exports/audits/lima_growth/program_capacity_policy_simulation.json` | Datos JSON de simulacion |
| `docs/lima_growth/LG_UX_R2_8D_PRIORITY_ALLOCATION_POLICY_CORRECTION.md` | Este documento |
| `docs/backlog/BACKLOG_PROGRAM_CAPACITY_POLICY.md` | Backlog de policy config |

### Modificados:
- Ninguno (solo documentacion y scripts read-only)

---

## 7. QA

| Check | Resultado |
|-------|:---------:|
| Backend compile | OK |
| Simulacion ejecutada | 5 escenarios completados |
| DB modificada | NO (read-only) |
| git status | Solo nuevos archivos |
| No nuevos motores | YES |

---

## 8. VEREDICTO

```
GO para LG-UX-R2.8E Program Capacity Policy Foundation
```

**Evidencia:**
- 5 hardcodes identificados y documentados
- 5 escenarios simulados con datos reales
- Escenario D (proportional) recomendado para situacion actual
- Escenario E (hybrid) recomendado para futuro con mas programas activos
- Backlog de policy creado con contrato, UI requirements y reglas
- NO cambios en produccion — discovery puro
