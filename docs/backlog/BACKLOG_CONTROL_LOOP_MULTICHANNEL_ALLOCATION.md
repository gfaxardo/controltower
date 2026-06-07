# BACKLOG — Control Loop Multichannel Allocation

**Date:** 2026-06-06
**Phase:** BACKLOG (NO IMPLEMENTAR)
**Registry:** LG-UX-R2.8B — Parte B

---

## VISION

Ampliar la asignacion operativa mas alla de Call Center humano.

```
Segmento -> Accion -> Canal -> Oferta/Mensaje -> Batch/Campana -> Resultado -> Medicion
```

El sistema debe asignar cada conductor al canal optimo segun segmento, prioridad, capacidad, costo, frecuencia y potencial.

---

## CANALES FUTUROS

| Canal | Tipo | Estado Actual | Requiere |
|-------|------|:---:|----------|
| Call Center (humano) | Operativo | IMPLEMENTADO | LoopControl |
| SAC (atencion especializada) | Operativo | IMPLEMENTADO | LoopControl |
| Bot / WhatsApp | Masivo automatizado | IMPLEMENTADO | LoopControl |
| Llamada automatica / IVR | Masivo automatizado | NO IMPLEMENTADO | Integracion voice |
| SMS | Masivo | NO IMPLEMENTADO | Proveedor SMS |
| Meta / Facebook paid campaign | Paid media | NO IMPLEMENTADO | Ads API |
| Remarketing | Paid media | NO IMPLEMENTADO | Pixel/audience |
| Push / App notification | Masivo | NO IMPLEMENTADO | App integration |
| Scout / Presencial | Field ops | NO IMPLEMENTADO | Field app |
| Email | Masivo | NO IMPLEMENTADO | Email provider |
| Holdout / No contactar | Control group | NO IMPLEMENTADO | A/B split logic |

---

## VARIABLES DE ASIGNACION

| Variable | Descripcion | Estado Actual |
|----------|-------------|:---:|
| Capacidad diaria por canal | Cuantos contactos puede manejar cada canal | IMPLEMENTADO (capacity_config) |
| Costo por contacto | Cuanto cuesta cada intento por canal | NO IMPLEMENTADO |
| Presupuesto diario | Cuanto presupuesto hay disponible | NO IMPLEMENTADO |
| Frecuencia maxima por conductor | Cuantos contactos en ventana N | NO IMPLEMENTADO |
| Ventana de enfriamiento | Tiempo minimo entre contactos | NO IMPLEMENTADO |
| Prioridad por segmento | Que segmento merece capacidad primero | IMPLEMENTADO (priority_allocation) |
| Canal permitido/bloqueado | Que canales NO usar para este segmento | PARCIAL (preference order) |
| Holdout % | Porcentaje que no recibe contacto | NO IMPLEMENTADO |

---

## SEGMENTOS INICIALES

| Segmento | Caracteristicas | Canal sugerido |
|----------|----------------|----------------|
| Nuevos sin primer viaje | 0 trips, onboarding | WhatsApp + Push |
| Recien dormidos (7-14d) | 1-2 semanas sin viaje | BOT / WhatsApp |
| Degradandose (14-30d) | Bajando frecuencia | Call Center |
| Churned (30+d) | Sin actividad > 30d | Call Center |
| Alto valor dormido | High value, inactivo | Call Center (humano) |
| Activos en riesgo | Baja productividad | BOT / WhatsApp |
| Baja productividad | Muchas horas, pocos viajes | BOT / WhatsApp |
| Sin contacto reciente | No contactado en ventana | Cualquier canal |
| Alta oportunidad por cohorte | Definido por programa | Segun programa |

---

## OUTPUTS FUTUROS

| Output | Descripcion | Requiere |
|--------|-------------|----------|
| Lista por canal | Drivers asignados a cada canal | Channel Allocation |
| Lote de campana | Batch exportable por canal | LoopControl + SMS/Email/Ads |
| Estado de contacto | Contactado, respondio, ignorado | Result Sync |
| Resultado | Viajes posteriores, retencion | Impact Measurement |
| Uplift vs holdout | Diferencia contactados vs no contactados | Holdout logic + Impact |
| Costo por reactivado | Inversion / conductores que volvieron | Cost tracking + Impact |
| Costo por viaje incremental | Inversion / viajes adicionales | Cost tracking + Impact |
| ROI por canal | Retorno de inversion por canal | Cost + Impact |

---

## CONEXION CON ARQUITECTURA EXISTENTE

```
Programs (STATIC_REGISTRY)
  |
  v
Program Eligibility (daily build)
  |
  v
Opportunity Prioritization (scoring + ranking)
  |
  v
Multichannel Allocation (segmento -> canal -> batch)
  |
  v
Queue / Campaign Batch (por canal)
  |
  v
Export (por canal: LoopControl, SMS, Email, Ads)
  |
  v
Result Sync (por canal: respuestas, outcomes)
  |
  v
Impact Measurement (uplift, ROI por canal)
```

**Reglas de integracion:**

1. Queue no debe ser solo Call Center. Debe evolucionar a Execution Queue multicanal.
2. Cada canal debe tener su propio schema de export (no solo LoopControl).
3. Control Loop no debe ejecutar sin medicion.
4. Impact/Attribution siguen bloqueados hasta tener Result Sync confiable.
5. La capacidad se configura por canal (ya existe). Debe agregarse costo y presupuesto.

---

## RIESGOS DE MONSTRUO

| Riesgo | Mitigacion |
|--------|------------|
| Agregar canales sin medicion | No activar canal sin result sync primero |
| Automatizar sin control | Todo export requiere boton humano (DRAFT) |
| Over-contact (spam) | Frecuencia maxima + ventana de enfriamiento obligatorias |
| Complejidad prematura | Empezar con 1 canal masivo (BOT), medir, luego expandir |
| Asumir Attribution listo | Attribution sigue en BACKLOG. Medir sin atribuir primero. |

---

## SECUENCIA RECOMENDADA

1. **Medir lo que ya existe** — LoopControl (Call Center + SAC + BOT) con Result Sync
2. **Agregar un canal masivo** — SMS o Email con proveedor simple
3. **Agregar holdout** — 5-10% de cada segmento sin contacto
4. **Agregar costo** — Costo por contacto por canal
5. **Agregar frecuencia** — Max intentos por conductor por ventana
6. **Agregar presupuesto** — Limite diario por canal en $
7. **Agregar ROI** — Costo / impacto por canal
8. **Agregar canales adicionales** — Meta, Push, Email, Scout

---

## GOVERNANCE

No abrir Impact.
No abrir Attribution.
No abrir Forecast.
No abrir AI.
No abrir Action Engine.
No abrir Program Builder.

Este backlog pertenece a **Control Foundation Hardening / Execution Queue Evolution**.

---

## FIRMA

```
BACKLOG REGISTRY ENTRY
Control Loop Multichannel Allocation
Registered: 2026-06-06
Phase: LG-UX-R2.8B — Parte B
Status: BACKLOG — NO IMPLEMENTAR
Next review: Post Result Sync + Attribution foundation
```
