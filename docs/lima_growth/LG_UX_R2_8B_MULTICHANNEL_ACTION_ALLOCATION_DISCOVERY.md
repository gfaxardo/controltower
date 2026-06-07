# LG-UX-R2.8B — Multichannel Action Allocation Discovery

**Date:** 2026-06-06
**Phase:** LG-UX-R2.8B Multichannel Action Allocation Discovery
**Scope:** Discovery + backlog only. NO implementation.
**Rule:** NO nuevos motores. NO campañas automaticas. Solo documentacion.

---

## 1. ESTADO ACTUAL

### 1.1 Canales Implementados

| Canal | Capacidad | Asignacion | Export | Medicion |
|-------|:---------:|:----------:|:------:|:--------:|
| Call Center (agentes humanos) | 80/dia | YES | LoopControl | NO |
| SAC (atencion especializada) | 30/dia | YES | LoopControl | NO |
| Bot / WhatsApp | 200/dia | YES | LoopControl | NO |
| **TOTAL** | **310/dia** | | | |

Los 3 canales usan el mismo pipeline de LoopControl. No hay diferenciacion de script, dialer, horario, ni costo entre canales.

### 1.2 Politica Actual de Asignacion

**Orden de programas:** HIGH_VALUE_RECOVERY (#1) → CHURN_PREVENTION (#2) → 14_90 (#3) → ACTIVE_GROWTH (#4)

**Preferencia de canal por programa:**
- HIGH_VALUE_RECOVERY, CHURN_PREVENTION: CALL_CENTER → SAC → BOT
- 14_90, ACTIVE_GROWTH: BOT → CALL_CENTER → SAC

**Regla individual:** Asigna al primer canal con capacidad disponible en orden de preferencia. Si todos llenos → UNASSIGNED.

**Resultado actual (2026-06-02):**
- 310 asignados, 190 UNASSIGNED
- Los 3 canales al 100% de utilizacion

### 1.3 Lo que NO existe hoy

- No hay costo por canal
- No hay presupuesto por canal
- No hay frecuencia maxima de contacto
- No hay ventana de enfriamiento
- No hay holdout / grupo de control
- No hay diferenciacion de script por canal
- No hay medicion de resultado por canal
- No hay rebalanceo dinamico de canales
- SMS, Email, Push, IVR, Ads, Scout: NO implementados

---

## 2. GAPS ACTUALES

| Gap | Impacto | Severidad |
|-----|---------|:---------:|
| Sin frecuencia maxima | Riesgo de over-contact / spam | HIGH |
| Sin holdout/control | Imposible medir uplift real | HIGH |
| Sin costo por canal | Imposible calcular ROI | MEDIUM |
| Sin ventana de enfriamiento | Contactos repetidos sin descanso | MEDIUM |
| Sin Result Sync confiable | Sin loop cerrado de feedback | HIGH |
| Sin atribucion por canal | No se sabe que canal funciono | HIGH |
| Canales limitados a 3 | Sin alternativas masivas economicas | MEDIUM |
| UNASSIGNED no tiene remediacion automatica | 190 conductores sin atencion | MEDIUM |

---

## 3. MODELO FUTURO (NO IMPLEMENTAR)

### 3.1 Pipeline completo

```
Program Eligibility (daily)
  |
  v
Opportunity Prioritization (score + ranking + fatigue penalty)
  |
  v
Multichannel Allocation (segmento -> canal optimo)
  |
  v
Campaign Batch (por canal: LoopControl, SMS, Email, Ads, Push, Scout)
  |
  v
Export (por canal, con script, horario, dialer especificos)
  |
  v
Result Sync (respuestas, outcomes, por canal)
  |
  v
Impact Measurement (uplift vs holdout, ROI por canal)
```

### 3.2 Canales futuros

| Canal | Tipo | Costo estimado | Prioridad |
|-------|------|:---:|:---:|
| Call Center (humano) | Alta calidad, alto costo | Alto | Conductores de alto valor |
| SAC | Atencion especializada | Alto | Casos complejos |
| BOT / WhatsApp | Masivo, bajo costo | Bajo | Volumen, recordatorios |
| SMS | Masivo, bajo costo | Bajo | Reactivacion masiva |
| IVR / Llamada automatica | Masivo, medio costo | Medio | Recordatorios, encuestas |
| Email | Masivo, bajo costo | Bajo | Comunicacion masiva |
| Meta / Facebook Ads | Paid media | Variable | Adquisicion, remarketing |
| Remarketing | Paid media | Variable | Recuperacion de abandonos |
| Push / App | Masivo, cero costo marginal | Cero | Notificaciones, nudges |
| Scout / Presencial | Field ops, alto costo | Alto | Conductores incontactables |
| Holdout | Control group | N/A | Medicion de uplift |

### 3.3 Reglas de asignacion futuras

1. **Segmento** determina el pool de canales validos
2. **Priority score** (con fatigue por canal) ordena conductores
3. **Capacidad por canal** limita cuantos entran
4. **Costo por canal** + **presupuesto** limita cuanto se gasta
5. **Frecuencia maxima** evita over-contact
6. **Ventana de enfriamiento** da descanso entre contactos
7. **Holdout %** reserva grupo de control para medicion
8. **Resultado previo** (si existe) ajusta futura asignacion

---

## 4. QUE NO IMPLEMENTAR TODAVIA

- **Campañas automaticas.** Todo export debe seguir siendo DRAFT + boton humano.
- **Action Engine.** Sigue bloqueado. Decision → Action requiere AI Copilot, que requiere todos los motores previos estables.
- **Costo/ROI.** Requiere Result Sync + Attribution. Sin medicion, el costo es especulativo.
- **Canales nuevos (SMS, Email, Ads).** Requieren integracion externa. Sin Result Sync confiable primero, no hay forma de medir si funcionan.
- **Rebalanceo dinamico de canales.** Requiere que el sistema entienda que canal funciona mejor. Sin Attribution, es ciego.
- **AI optimizando canales.** Requiere datos de resultado. Sin datos, AI no tiene que optimizar.

---

## 5. RIESGOS DE MONSTRUO

| Riesgo | Como evitarlo |
|--------|--------------|
| Agregar canales sin poder medirlos | Result Sync primero, canales despues |
| Automatizar export sin boton humano | Mantener DRAFT + boton hasta Attribution |
| Spam de contactos sin control | Frecuencia maxima + enfriamiento obligatorios |
| Complejidad que nadie usa | 1 canal masivo nuevo a la vez, medir, iterar |
| Asumir que Attribution esta listo | Attribution sigue en BACKLOG. No depende de el. |
| Mezclar discovery con implementacion | Este doc es BACKLOG. No se toca codigo. |

---

## 6. SECUENCIA RECOMENDADA

```
FASE 1 (AHORA): Result Sync confiable
  - LoopControl sync funcionando
  - Respuestas y outcomes visibles

FASE 2: Frecuencia + Enfriamiento
  - Max intentos por conductor por ventana
  - Tiempo minimo entre contactos

FASE 3: Holdout
  - 5-10% sin contacto por segmento
  - Grupo de control para medicion

FASE 4: Un canal masivo nuevo
  - SMS o Email con proveedor simple
  - Costo por contacto

FASE 5: Costo + Presupuesto
  - Costo por contacto por canal
  - Limite diario en $

FASE 6: Attribution (cuando este lista)
  - Uplift vs holdout
  - ROI por canal

FASE 7: Canales adicionales
  - Meta, Push, Email, Scout
  - Segun resultados de fases anteriores
```

---

## 7. ARCHIVOS CREADOS / MODIFICADOS

### Creados:
| Archivo | Proposito |
|---------|-----------|
| `docs/backlog/BACKLOG_CONTROL_LOOP_MULTICHANNEL_ALLOCATION.md` | Backlog: canales, variables, segmentos, outputs, riesgos |
| `docs/lima_growth/LG_UX_R2_8B_MULTICHANNEL_ACTION_ALLOCATION_DISCOVERY.md` | Este documento |

### Modificados:
| Archivo | Cambio |
|---------|--------|
| `docs/backlog/BACKLOG_OPPORTUNITY_PRIORITIZATION_ENGINE.md` | +Multichannel Integration section (fatigue por canal, frecuencia multicanal, canal humano vs masivo) |

---

## 8. CANALES DETECTADOS

3 canales implementados: CALL_CENTER, SAC, BOT/WhatsApp.
8 canales adicionales identificados como backlog.
Ninguno tiene costo, frecuencia, holdout, o medicion independiente.

---

## 9. QA

| Check | Resultado |
|-------|:---------:|
| Backend compile | OK (no code changes) |
| Frontend build | PASS (no code changes) |
| Canales detectados | 3 implementados + 8 backlog |
| Gaps documentados | 8 gaps identificados |
| Backlog multicanal creado | YES |
| Opportunity Prioritization actualizado | YES |
| No nuevos motores | YES |
| No campañas automaticas | YES |

---

## 10. VEREDICTO

```
GO para LG-UX-R2.8C Opportunity Prioritization Discovery
```

**Evidencia:**
- 3 canales operativos auditados y documentados
- 11 canales futuros mapeados (3 actuales + 8 backlog)
- 8 variables de asignacion identificadas (4 implementadas, 4 faltantes)
- 9 segmentos iniciales definidos
- Conexion con arquitectura existente documentada sin ruptura
- Riesgos de monstruo identificados con mitigacion
- Secuencia recomendada de 7 fases
- Sin cambios de codigo (discovery puro)
