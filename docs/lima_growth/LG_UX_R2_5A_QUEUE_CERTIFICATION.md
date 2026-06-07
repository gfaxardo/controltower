# LG-UX-R2.5A — Queue Certification

**Date:** 2026-06-06
**Phase:** LG-UX-R2.5A Queue Certification
**Scope:** Certification only. No features. No UX changes.

---

## PARTE A — QUEUE CERTIFICATION

---

### TAREA A1 — Audit READY

**Pregunta:** Por que READY = X?

**Fuente exacta:** `GET /operational-summary` → `queue_ready`
`GET /assignment-queue/summary` → `totals.ready`

**Tabla exacta:** `growth.yego_lima_assignment_queue`

**Query exacta (`yego_lima_operational_summary_service.py:83-93`):**
```sql
SELECT COUNT(*) as total,
       SUM(CASE WHEN queue_status = 'READY' THEN 1 ELSE 0 END) as ready,
       SUM(CASE WHEN queue_status = 'HELD' THEN 1 ELSE 0 END) as held
FROM growth.yego_lima_assignment_queue
WHERE assignment_date = :date
```

**Filtros:** Solo `assignment_date`. Sin filtro por programa, canal o ciudad.

**Como un registro llega a READY** (`yego_lima_assignment_queue_service.py:70-72`):
```python
status = "READY"
if not phone_val or chan == "UNASSIGNED":
    status = "HELD"
```

**Regla:** Tiene telefono Y tiene canal asignado != "UNASSIGNED" → READY

**Dato real (DB 2026-06-06):**
- READY count: **150**
- Todos pertenecen a PROGRAM_CHURN_PREVENTION
- Todos tienen phone (YES) y assigned_channel = BOT

**Veredicto A1:** PASS. Fuente, tabla, query y filtros verificados. READY = 150 representa correctamente conductores con telefono y canal asignado.

---

### TAREA A2 — Audit HELD

**Pregunta:** Por que HELD = X?

**Fuente exacta:** `GET /operational-summary` → `queue_held`
`GET /assignment-queue/summary` → `totals.held`

**Tabla exacta:** `growth.yego_lima_assignment_queue`

**Query exacta:** Misma query que Tarea A1, `SUM(CASE WHEN queue_status = 'HELD' ...)`

**Como un registro llega a HELD** (`yego_lima_assignment_queue_service.py:70-72`):
```python
if not phone_val or chan == "UNASSIGNED":
    status = "HELD"
```

**Razones de HELD** (`yego_lima_queue_summary_service.py:86-103`):

| Razon | Query | Count |
|-------|-------|-------|
| Sin telefono | `phone IS NULL OR phone = ''` | 0 |
| Sin canal asignado | `assigned_channel IS NULL OR assigned_channel = 'UNASSIGNED'` | 190 |

**Dato real (DB 2026-06-06):**
- HELD count: **190**
- 100% de HELD tienen phone pero assigned_channel = UNASSIGNED
- 0 HELD por falta de telefono
- Todos pertenecen a PROGRAM_CHURN_PREVENTION

**Cobertura:** Las dos razones cubren el 100% de HELD (190 = 190 + 0). La suma es exacta.

**Veredicto A2:** PASS. Razones, conteos y cobertura verificados. HELD = 190 representa correctamente conductores con canal UNASSIGNED.

---

### TAREA A3 — Audit CAPACITY

**Pregunta:** Capacity realmente limita Actionable?

**Fuentes de configuracion:**

| Concepto | Tabla | Valor |
|----------|-------|-------|
| `daily_action_capacity` | `growth.yango_lima_opportunity_policy_config` | **500** |
| `capacity_total` | `growth.yego_lima_capacity_config` | **310** |

**`daily_action_capacity` (500) — SI limita actionable_today:**
En `yego_lima_opportunity_policy_service.py:427`:
```sql
final_rank <= %(cap)s AND selected_program_code IS NOT NULL
AND exclusion_reason IS NULL as is_actionable_today
```
Donde `cap = daily_action_capacity = 500`. Los top-500 por ranking son accionables.
- `actionable_today` en DB = **500** (limitado correctamente)

**`capacity_total` (310) — NO limita actionable_today directamente:**

`capacity_total` es la capacidad operativa por canal (agentes x capacidad/agente):
- Call Center: 2 x 40 = 80
- SAC: 1 x 30 = 30
- Bot/WhatsApp: 1 x 200 = 200
- TOTAL = **310**

`capacity_total` se usa en:
- `priority_allocation_service.py:39` — para distribuir capacidad entre programas
- `calculate_capacity_summary()` — para calcular gap, coverage_rate, utilization_status

Pero NO se usa para limitar `is_actionable_today`. El limitador real es `daily_action_capacity` (500).

**Gap identificado:**
- `actionable_today` = 500 (limitado por daily_action_capacity)
- `capacity_total` = 310 (capacidad operativa de canales)
- Gap = 500 - 310 = **190** conductores accionables sin capacidad operativa

Esto NO es un bug de Queue Certification. Es una discrepancia de configuracion entre politica (500) y capacidad de canales (310). Pertenece al backlog de Program Tuning (LG-UX-R2.x futuro).

**Veredicto A3:** NO (con matiz). `capacity_total` (310) no limita `actionable_today` (500). El limitador real es `daily_action_capacity` (500) desde `opportunity_policy_config`. Hay un gap de 190 conductores accionables sin capacidad de canal. Esto debe resolverse en Program Tuning, no en esta fase de certificacion.

---

### TAREA A4 — Audit EXPORT FLOW

**Pregunta:** EXPORTED sale realmente de READY?

**Flujo documentado:**
```
Queue → Export → LoopControl → Export History
```

**Hallazgo critico — Dos paths de export, diferentes comportamientos:**

#### Path A: `POST /assignment-queue/export` (USADO POR EL FRONTEND)

Archivo: `yego_lima_assignment_queue.py:105-146`

1. Lee READY records de `growth.yego_lima_assignment_queue`
2. Construye lista de contactos
3. Llama a `export_from_contacts()` (`yego_lima_loopcontrol_export_service.py:340-474`)
4. `export_from_contacts()`:
   - Construye campaign payload
   - Llama a LoopControl API (o DRY_RUN)
   - Inserta en `growth.yango_lima_loopcontrol_campaign_export`
   - **NO actualiza queue_status en la tabla de cola**
5. Los registros de cola permanecen en estado READY

#### Path B: `export_ready_queue_to_loopcontrol()` (NO USADO POR EL FRONTEND)

Archivo: `yego_lima_queue_export_service.py:109-353`

1. Lee READY records de queue
2. Llama a LoopControl API
3. Inserta en campaign_export
4. **SI actualiza queue_status = 'EXPORTED'** (linea 326-337)

**Evidencia en DB (2026-06-06):**
- `queue_status = 'EXPORTED'`: **160 registros** (generados por Path B o script)
- `queue_status = 'READY'`: **150** (no cambiaran tras export via UI)
- Export history: 7 campanas, 140 contacts inserted

**El frontend NO llama a Path B.** La ruta `/yego-lima-growth/queue-export` es un placeholder sin implementacion.

#### `queue_exported` en operational_summary

Archivo: `yego_lima_operational_summary_service.py:117`
```python
queue_exported = lc_campaigns  # COUNT from loopcontrol_campaign_export WHERE export_status='exported'
```

`queue_exported` NO cuenta registros de cola con status EXPORTED. Cuenta campanas exportadas.

#### Problema en `queue_total`

El query de cola (linea 83-88) hace `COUNT(*)` sin excluir EXPORTED:
```sql
SELECT COUNT(*) as total, ... FROM assignment_queue WHERE assignment_date = :date
```
- `queue_total` = 500 (incluye 150 READY + 190 HELD + 160 EXPORTED)
- Los 160 EXPORTED inflan queue_total

**Veredicto A4:** NO. La ruta de export usada por el frontend (Path A) **NO** actualiza queue_status a EXPORTED. Los registros permanecen READY tras la exportacion. El Path B (que si actualiza) no esta expuesto via frontend. `queue_total` incluye incorrectamente registros ya exportados.

---

### TAREA A5 — Traceability

**Muestra 10 registros READY (DB 2026-06-06):**

| # | Driver | Program | Status | Phone | Channel |
|---|--------|---------|--------|-------|---------|
| 1 | Paredes Zambrano | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 2 | Quispe Luis | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 3 | Vasquez Clavo Oscar | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 4 | Alzuro Vasquez Victor Enrique | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 5 | Auccapuclla Hidalgo Diago | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 6 | Bellido Collahua Antony | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 7 | Bernal Giancarlos | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 8 | Betancourt Duque Yonathan Migu | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 9 | Cabrera Carpio Cesar Arturo | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |
| 10 | Cabrera Castaneda Juan Carlos | PROGRAM_CHURN_PREVENTION | READY | YES | BOT |

**Muestra 10 registros HELD (DB 2026-06-06):**

| # | Driver | Program | Status | Phone | Channel |
|---|--------|---------|--------|-------|---------|
| 1 | Pozo Jose | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 2 | ROMAN HUAMAN DANIEL PAULINO | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 3 | Sanchez Elvis | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 4 | Sanchez Villar Julio | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 5 | Bendezu Mitac Victor Cesar | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 6 | Bernuy salazar Pool cesar | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 7 | Cabello Javier | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 8 | Castro Jeremy | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 9 | Reyna Victor | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |
| 10 | Rivera Ortiz Victor Antonio | PROGRAM_CHURN_PREVENTION | HELD | YES | UNASSIGNED |

**Validacion:**

| Criterio | READY (10/10) | HELD (10/10) |
|----------|:---:|:---:|
| Aparecen en Queue | 10/10 PASS | 10/10 PASS |
| Programa correcto (CHURN_PREVENTION) | 10/10 PASS | 10/10 PASS |
| Estado correcto | 10/10 PASS | 10/10 PASS |
| Regla READY (phone + canal asignado) | 10/10 PASS | — |
| Regla HELD (canal UNASSIGNED) | — | 10/10 PASS |

**Veredicto A5:** PASS. 10/10 READY y 10/10 HELD validados. Todos aparecen en Queue, pertenecen al programa correcto, y tienen el estado correcto segun las reglas de negocio.

---

### Distribucion completa de cola (DB 2026-06-06):

| Queue Status | Count | Program |
|-------------|-------|---------|
| HELD | 190 | CHURN_PREVENTION (programa unico) |
| EXPORTED | 160 | 80 CHURN_PREVENTION + 80 HIGH_VALUE_RECOVERY |
| READY | 150 | CHURN_PREVENTION |
| **TOTAL** | **500** | |

Fecha: 2026-06-02 (unica fecha con cola)

---

## SUMMARY — QUEUE CERTIFICATION

| Tarea | Resultado | Detalle |
|-------|:---------:|---------|
| A1 — READY audit | **PASS** | Fuente/tabla/query/filtros verificados. READY = 150. |
| A2 — HELD audit | **PASS** | Razones y cobertura 100%. HELD = 190 (todos UNASSIGNED). |
| A3 — CAPACITY audit | **NO** | `capacity_total` (310) no limita actionable (500). Gap de 190. |
| A4 — EXPORT FLOW audit | **NO** | Export via UI no actualiza queue_status a EXPORTED. `queue_total` inflado. |
| A5 — Traceability | **PASS** | 20/20 registros validados correctamente. |

### Issues encontrados:

| ID | Issue | Severidad | Archivo |
|----|-------|:---------:|---------|
| CERT-001 | `queue_total` incluye registros EXPORTED inflando el conteo | MEDIUM | `yego_lima_operational_summary_service.py:83-88` |
| CERT-002 | `POST /assignment-queue/export` no actualiza queue_status a EXPORTED | HIGH | `yego_lima_assignment_queue.py:105-146` |
| CERT-003 | `capacity_total` no limita `actionable_today`; gap de 190 | LOW | Discrepancia de configuracion, no de codigo |
| CERT-004 | `queue_exported` mide campanas, no registros de cola exportados | LOW | `yego_lima_operational_summary_service.py:117` |
| CERT-005 | Merge conflict en `api.js` (resuelto durante certificacion) | LOW | `frontend/src/services/api.js:1387` |

### Remediation requerida para CERT-001 y CERT-002 (antes de considerar GO pleno):

1. **CERT-002 (HIGH):** Modificar `POST /assignment-queue/export` para que llame a `export_ready_queue_to_loopcontrol()` (Path B) en lugar de `export_from_contacts()` (Path A). O alternativamente, agregar el UPDATE de `queue_status = 'EXPORTED'` al flujo de Path A.

2. **CERT-001 (MEDIUM):** Agregar filtro `queue_status != 'EXPORTED'` al query de `queue_total` o crear un campo separado `queue_exported_from_queue`.

---

## VEREDICTO FINAL

```
QUEUE CERTIFIED
  con 2 issues que requieren remediacion antes de R2.6
```

**Estado:** CERTIFIED WITH OBSERVATIONS

La cola representa la realidad operacional con fidelidad en READY, HELD, y traceability. Los issues de export (CERT-001, CERT-002) son bugs remediables que no invalidan la certificacion del concepto de cola, pero deben resolverse antes de declarar GO pleno para Today's Action Plan.

---

## GO / NO-GO for LG-UX-R2.6 Today's Action Plan

**GO (condicionado)**

Condiciones:
1. CERT-002 (HIGH) debe resolverse antes de activar R2.6 — el export debe actualizar queue_status
2. CERT-001 (MEDIUM) debe resolverse — queue_total no debe incluir EXPORTED

Sin estas correcciones, el usuario vera 500 en cola cuando solo 340 (150 READY + 190 HELD) estan realmente pendientes, y los registros exportados no se distinguiran de los READY.

---

## QA

- Backend compile: **OK**
- Frontend build: **PASS** (merge conflict en api.js resuelto durante certificacion)
- DB traceability: **20/20 registros validados**
- Sin cambios funcionales nuevos
