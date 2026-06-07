# OV2 LINEAGE AUDIT — DICTAMEN FINAL GO / NO GO

**Generated:** 2026-06-06  
**Phase:** Control Foundation — Omniview P0 Recovery (ACTIVE)  
**Audit Type:** Static Lineage Analysis (No Live DB)  
**Scope:** Full V1 vs V2 source comparison, KPI reconciliation, serving architecture

---

## 1. RESUMEN EJECUTIVO

Omniview V2 es una refactorizacion arquitectonica significativa que introduce un contrato de API moderno (MatrixResponse, Shell, snapshot serving) pero **hereda el mismo sustrato de datos que Omniview V1**. La arquitectura de serving de V2 es superior (lineage tracking, warnings explicitos, snapshot pre-computado), pero los datos subyacentes son identicos a los de V1.

**Veredicto preliminar: NO GO hasta resolver las dependencias compartidas con V1.**

---

## 2. RESPUESTAS A LAS 7 PREGUNTAS DEL DICTAMEN

### 2.1 ¿V2 hereda fuentes defectuosas de V1?

**SI, de forma significativa.**

V2 (`CT_TRIPS_2026`) lee de las **mismas tres tablas de hechos** que V1:

| Tabla | V1 | V2 | Riesgo |
|-------|----|----|--------|
| `ops.real_business_slice_day_fact` | Si | Si | Cualquier corrupcion en datos diarios afecta a ambos |
| `ops.real_business_slice_week_fact` | Si | Si | Idem |
| `ops.real_business_slice_month_fact` | Si | Si | Idem |

**Consecuencias:**
- Si `revenue_yego_final` no esta poblado, V2 muestra NULL (V1 muestra fallback)
- Si hay gaps de datos en las fact tables, ambos sistemas muestran gaps
- Si el refresh de fact tables falla, ambos sistemas quedan con datos stale
- Si hay bugs en la logica de agregacion de fact tables, ambos sistemas los heredan

### 2.2 ¿V2 corrige solo performance o tambien confiabilidad?

**Principalmente performance y transparencia. Confiabilidad de datos: PARCIAL.**

Mejoras de V2 sobre V1:

| Aspecto | V1 | V2 | Mejora |
|---------|----|----|--------|
| **API response** | Raw rows, frontend pivots (4072-line component) | MatrixResponse contract (columns/rows/cells) | Performance + mantenibilidad |
| **Lineage tracking** | Implicito (leer codigo) | Explicito por KPI (origin_table, origin_field, aggregation) | Confiabilidad + trazabilidad |
| **Revenue visibility** | `COALESCE(_final, _net)` — fallback silencioso | `_final` directo — NULL explicito | Confiabilidad (no oculta problemas) |
| **Warnings** | Endpoint separado de freshness | Embebidos en cada response | Transparencia |
| **canonical_ready** | No expuesto | Booleano explicito en cada response | Confiabilidad operativa |
| **Snapshot serving** | No tiene (lecturas directas) | `ops.omniview_v2_serving_snapshot` | Performance + aislamiento de carga |
| **Multi-source** | Solo CT | CT + Yango (shadow) | Flexibilidad (shadow mode) |

**Lo que V2 NO corrige:**
- Errores en los datos de las fact tables subyacentes
- Bugs en la logica de refresh del pipeline de datos
- Problemas de calidad de `revenue_yego_final` (solo los hace visibles, no los arregla)
- Plan vs Real (no esta implementado en V2, es un gap funcional)

### 2.3 ¿Que problemas de V1 pueden persistir en V2?

| Problema V1 | ¿Persiste en V2? | Mecanismo | Severidad |
|-------------|-----------------|-----------|-----------|
| Datos incorrectos en fact tables | **SI** | Misma tabla, mismo dato | CRITICAL |
| `revenue_yego_final` no poblado | **SI** (pero visible como NULL) | V2 no usa COALESCE — muestra NULL en vez de fallback | HIGH |
| Gaps de fechas en fact tables | **SI** | Misma tabla | HIGH |
| Fallos de refresh jobs | **SI** | Mismo pipeline de refresh | CRITICAL |
| `active_drivers` no-aditivo sumado incorrectamente | **SI** | Ambos usan SUM en la fact table | MEDIUM |
| MVs legacy stale | **NO** | V2 no depende de esas MVs | — |
| Plan vs Real bugs de calculo | **NO** | V2 no implementa Plan vs Real | — |
| DROP+CASCADE en driver lifecycle MVs | **NO** | V2 no toca esas MVs | — |
| Revenue fallback silencioso | **NO** | V2 no usa COALESCE | — |
| Frontend recalculo de KPIs | **NO** | V2 backend es source of truth | — |

### 2.4 ¿Que problemas quedan aislados de V1?

| Problema V1 | Estado en V2 |
|-------------|-------------|
| `ops.mv_plan_vs_real_monthly_fact` (legacy MV) | **AISLADO** — V2 no lo lee |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | **AISLADO** — V2 solo referencia readiness |
| `ops.mv_real_trips_monthly` (legacy) | **AISLADO** — V2 no lo lee |
| `ops.v_real_trips_business_slice_resolved` (forbidden) | **AISLADO** — V2 jamas lo referencia |
| `serving.omniview_projection_daily_fact` | **AISLADO** — V2 no lo usa para matrix |
| `ops.v_plan_vs_real_realkey_final` (fallback view) | **AISLADO** — V2 no lo lee |
| `public.trips_unified` (forbidden source) | **AISLADO** — V2 jamas lo referencia |
| Driver lifecycle MVs y su DROP+CASCADE | **AISLADO** — V2 no las toca |
| Legacy real LOB MVs | **AISLADO** — V2 no las lee |

### 2.5 ¿Que assets deben ser deprecados?

| Asset | Razon | Accion |
|-------|-------|--------|
| `ops.mv_plan_vs_real_monthly_fact` (legacy) | Reemplazado por `_canonical` | Deprecar + redirigir endpoints |
| `ops.mv_real_trips_monthly` | Fuente legacy, reemplazada por fact tables | Deprecar + eliminar refresh |
| `ops.v_plan_vs_real_realkey_final` | View legacy con REALKEY key (sin LOB mapping) | Deprecar cuando canonical este estable |
| `ops.v_real_trips_business_slice_resolved` | Ya marcado FORBIDDEN para serving | Eliminar referencias restantes |
| `ops.v_real_trips_enriched_base` | Ya marcado FORBIDDEN para serving | Eliminar referencias restantes |
| `ops.mv_supply_weekly` / `_monthly` | Nunca refrescados, reemplazados por views v140 | Deprecar MVs, activar views |
| `ops.v_plan_projection_control_loop` | Usado solo por control loop Plan vs Real | Evaluar si control loop sigue siendo necesario |

### 2.6 ¿Que assets deben seguir siendo canonicos?

| Asset | Razon | Estado |
|-------|-------|--------|
| `ops.real_business_slice_day_fact` | Fuente unica de verdad diaria para V1 y V2 | **CANONICO — MANTENER** |
| `ops.real_business_slice_week_fact` | Fuente unica de verdad semanal | **CANONICO — MANTENER** |
| `ops.real_business_slice_month_fact` | Fuente unica de verdad mensual | **CANONICO — MANTENER** |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | Plan vs Real con fuente real canonica | **CANONICO — MANTENER** |
| `ops.real_business_slice_month_snapshot` | Snapshot de meses cerrados | **CANONICO — MANTENER** |
| `ops.v_real_business_slice_month_serving` | View de serving que rutea snapshot/working | **CANONICO — MANTENER** |
| `serving.omniview_projection_daily_fact` | Proyeccion pre-computada | **CANONICO — MANTENER** (para V1) |
| `ops.omniview_v2_serving_snapshot` | Snapshot serving V2 | **CANONICO — MANTENER** (nuevo, exclusivo V2) |

### 2.7 ¿Se puede avanzar con V2 o primero hay que sanear upstream?

**Primero hay que sanear upstream. NO se puede avanzar con V2 a produccion operativa sin antes garantizar la calidad de las fact tables compartidas.**

**Orden de saneamiento requerido:**

```
FASE A — SANEAMIENTO UPSTREAM (PRE-V2)
  1. Auditoria de calidad de fact tables:
     - Verificar que revenue_yego_final este poblado para todos los periodos
     - Verificar que no haya gaps de fechas en day/week/month_fact
     - Verificar que los refresh jobs esten funcionando correctamente
     - Resolver cualquier rollup mismatch (monthly != SUM(daily))

  2. Revenue certification:
     - Completar poblacion de revenue_yego_final donde falte
     - Documentar diferencias revenue_yego_final vs revenue_yego_net
     - Establecer SLA de poblacion de revenue_yego_final

  3. Refresh pipeline hardening:
     - Migrar DROP+CASCADE a REFRESH CONCURRENTLY donde aplique
     - Implementar refresh_guard() en todos los scripts de refresh
     - Establecer alertas de fallo de refresh

FASE B — V2 SHADOW (PARALELO, NO BLOQUEANTE)
  1. V2 puede seguir en modo shadow (YANGO_API_RAW, endpoints /shadow)
  2. V2 puede seguir refinando contrato MatrixResponse y Shell
  3. V2 puede seguir construyendo snapshots para single-day queries

FASE C — V2 CT TRANSITION (POST-SANEAMIENTO)
  1. Una vez que fact tables esten certificadas:
     - Activar V2 CT_TRIPS_2026 como fuente operativa
     - Validar reconciliacion V1 vs V2 con queries live
     - Migrar UI de V1 a V2 progresivamente (Evolution → V2 Matrix)
  2. Implementar Plan vs Real en V2 si se necesita
  3. Deprecar endpoints V1 redundantes
```

---

## 3. CRITERIOS GO / NO GO — EVALUACION

### Criterios GO

| Criterio | Estado | Evidencia |
|----------|--------|-----------|
| Cada KPI tiene lineage completo | **GO** | V2 tiene `origin_table`, `origin_field`, `aggregation` por cada KPI en source_registry y en cada response |
| Cada endpoint tiene source map | **GO** | Todos los endpoints V2 tienen traceability documentada (ver OV2_LINEAGE_MAP.md section 6) |
| V1 vs V2 tiene comparacion documentada | **GO** | OV1_VS_OV2_SOURCE_COMPARISON.md completo |
| Runtime fallback identificado y controlado | **GO** | `allow_runtime` flag gated, snapshot-first architecture documentada |
| Snapshot V2 tiene upstream conocido | **GO** | Snapshot se construye desde las mismas fact tables, traceable |
| No hay source desconocida | **GO** | Todas las sources estan en el source_registry |

### Criterios NO GO

| Criterio | Estado | Evidencia |
|----------|--------|-----------|
| V2 usa fuentes V1 defectuosas sin saneamiento | **NO GO** | V2 lee de las mismas fact tables que V1; no hay evidencia de saneamiento completado |
| V2 recalcula runtime sin trazabilidad | **GO** (mitigado) | Runtime solo con `allow_runtime=true`; lineage tracking embebido en response |
| Hay KPIs sin source map | **GO** | Todos los 9 KPIs CT + 5 KPIs Yango tienen source map |
| Hay diferencias sin explicacion | **PARCIAL** | Revenue (COALESCE vs direct) esta explicada y documentada; reconciliacion live pendiente |
| Hay fallback silencioso | **GO** | V2 no tiene COALESCE silencioso; revenue NULL es explicito; snapshot fallback es visible (SERVING_SNAPSHOT_MISSING warning) |
| Hay MV o serving fact sin refresh/freshness claro | **PARCIAL** | Fact tables tienen refresh orquestado; snapshot V2 tiene refresh script; raw_yango MVs tienen refresh script; pero no hay alertas automaticas de staleness para V2 snapshot |

---

## 4. DICTAMEN FINAL

### VEREDICTO: NO GO (CONDICIONAL)

**Omniview V2 NO esta listo para reemplazar a Omniview V1 como vista operativa.**

**Razones del NO GO:**

1. **Dependencia de datos no saneada (CRITICAL):** V2 lee de las mismas fact tables que V1. Cualquier problema de calidad de datos en esas tablas se hereda. El saneamiento de `revenue_yego_final`, gaps de fechas, y rollup mismatches debe completarse antes de que V2 pueda ser considerado operativo.

2. **Revenue gap potencial (HIGH):** La diferencia entre `COALESCE(revenue_yego_final, revenue_yego_net)` (V1) y `revenue_yego_final` directo (V2) puede causar que V2 muestre NULL o 0 donde V1 muestra datos. Esto debe ser cuantificado y comunicado antes de la transicion.

3. **Plan vs Real no implementado (MEDIUM):** V2 no tiene calculo de Plan vs Real. Si este KPI es operacionalmente necesario, V2 no puede reemplazar a V1 sin esta funcionalidad.

4. **Snapshot staleness sin alertas (MEDIUM):** El snapshot `ops.omniview_v2_serving_snapshot` puede quedar stale sin deteccion automatica. La arquitectura de snapshot es correcta pero falta governance de freshness.

5. **Reconciliacion live no ejecutada (MEDIUM):** La reconciliacion de valores entre V1 y V2 requiere queries contra la base de datos real. El analisis estatico predice igualdad para la mayoria de KPIs (misma tabla, misma columna) pero esto debe ser verificado.

### LO QUE SI ESTA LISTO

- **Arquitectura de serving V2:** El diseno de MatrixResponse, Shell, snapshot serving, source registry, lineage tracking es arquitectonicamente superior a V1.
- **Modo shadow (Yango):** V2 puede operar en modo shadow con `YANGO_API_RAW` sin afectar a V1.
- **Contratos de API:** Los contratos `OmniviewV2MatrixResponse`, `OmniviewV2ShellResponse` estan bien definidos.
- **Endpoints de shadow/reconciliation:** `/ops/omniview-v2-shadow/*` son utiles para monitoreo y comparacion.
- **Lineage documentation:** Este audit proporciona el lineage completo requerido para governance.

### PATH TO GO

```
SEMANA 1-2: SANEAMIENTO UPSTREAM
  □ Ejecutar queries de reconciliacion live (OV1_VS_OV2_KPI_RECONCILIATION.md Section 5)
  □ Cuantificar revenue gap (revenue_yego_final NULL vs revenue_yego_net)
  □ Verificar refresh pipeline health para fact tables
  □ Resolver cualquier rollup mismatch (monthly vs SUM daily)
  □ Completar revenue_yego_final donde falte

SEMANA 2-3: V2 HARDENING
  □ Implementar alertas de snapshot staleness
  □ Implementar Plan vs Real en V2 (o documentar como gap aceptado)
  □ Agregar freshness metadata al snapshot (expires_at enforcement)
  □ Testing end-to-end: V1 vs V2 para un mes completo

SEMANA 3-4: GO DECISION
  □ Re-ejecutar reconciliacion live con datos saneados
  □ Confirmar 0 gaps de revenue_yego_final
  □ Confirmar trips, drivers, ticket, TPD identicos V1 vs V2
  □ Obtener sign-off de usuario operativo
  □ EMITIR GO — iniciar migracion UI de V1 a V2
```

---

## 5. FINDINGS CLAVE DEL AUDIT

| # | Finding | Severity | Accion |
|---|---------|----------|--------|
| F1 | V2 y V1 comparten las mismas fact tables (day/week/month) | CRITICAL | Sanear fact tables antes de promover V2 |
| F2 | V2 no usa COALESCE para revenue — muestra NULL donde V1 muestra fallback | HIGH | Cuantificar gap, poblar revenue_yego_final |
| F3 | V2 no tiene Plan vs Real operativo | MEDIUM | Implementar o documentar como gap |
| F4 | Snapshot V2 sin alertas de staleness | MEDIUM | Agregar freshness governance al snapshot |
| F5 | V1 y V2 comparten el mismo pipeline de refresh | HIGH | Hardening del pipeline (advisory locks, alertas) |
| F6 | V2 source_registry tiene lineage tracking nativo | POSITIVE | Mantener y extender |
| F7 | V2 shell tiene 10 secciones operativas pre-construidas | POSITIVE | Util para operational awareness |
| F8 | Yango shadow source tiene canonical_ready=false | POSITIVE | Correctamente gated, no riesgo operativo |
| F9 | 5 raw_yango MVs exclusivas de V2 (no shared risk) | POSITIVE | Bien aisladas del ecosistema V1 |
| F10 | V2 MatrixResponse contrato es backend-native (no frontend pivot) | POSITIVE | Reduce bugs de UI, mejora performance |

---

## 6. GOVERNANCE COMPLIANCE CHECK

| Regla del AI Operating System | V2 Cumple? |
|-------------------------------|------------|
| RAW → MV → SERVING FACTS → UI | **SI** — fact tables → snapshot (serving) → UI |
| No heavy runtime para UI publica | **SI** — snapshot-first, runtime gated |
| No mezclar motores | **SI** — solo Control Foundation |
| Serving-first architecture | **SI** — snapshot pre-computado es serving-first |
| Runtime fallback protection | **SI** — `allow_runtime` flag explicito, default OFF |
| Deterministic logic first | **SI** — no AI en V2 |
| 1 ACTIVE + 1 READY NEXT | **SI** — OMNI-P0 ACTIVE, Diagnostic PAUSED |

---

## 7. NEXT STEPS

1. **INMEDIATO:** Ejecutar reconciliacion live (queries en OV1_VS_OV2_KPI_RECONCILIATION.md Section 5)
2. **INMEDIATO:** Cuantificar revenue_yego_final gaps
3. **CORTO PLAZO:** Hardening del refresh pipeline de fact tables
4. **CORTO PLAZO:** Agregar snapshot freshness alerts
5. **MEDIO PLAZO:** Implementar Plan vs Real en V2 o documentar como gap aceptado
6. **MEDIO PLAZO:** Una vez saneado upstream, iniciar migracion progresiva V1 → V2

---

*Este dictamen se basa en analisis estatico de codigo. La reconciliacion live contra la base de datos es REQUERIDA para el GO final.*
