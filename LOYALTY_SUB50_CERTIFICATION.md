# LOYALTY SUB-50 CERTIFICATION — FASE 2B

**Motor:** Control Foundation — Loyalty Sub-50 Audit  
**Fecha:** 2026-06-02  
**Modo:** Auditoria exhaustiva — NO implementar, NO corregir  
**Objetivo:** Certificar si la implementacion actual es apta para evolucionar hacia programas de intervencion operativa  

---

## PART 2 — COMPLETED ORDERS AUDIT

### 2.1 Definicion Exacta

| Atributo | Valor |
|----------|-------|
| **Nombre en DB** | `completed_orders_week` |
| **Definicion** | Numero de viajes completados por un driver en una semana |
| **Fuente** | `ops.driver_daily_activity_fact.activity_date` + `completed_trips` |
| **SQL exacto** | `SUM(completed_trips) AS completed_orders_week` |
| **Archivo:linea** | `yego_lima_loyalty_sub50_service.py:106` |
| **Grain** | Weekly — agrupa `activity_date` dentro de `[week_start-1d, week_end]` |
| **Filtros** | `activity_date >= start AND activity_date <= end AND driver_id = ANY(:drivers) AND completed_trips > 0` |
| **Agregacion** | `GROUP BY driver_id` → `SUM(completed_trips)` |
| **Ventana temporal** | `lookback_start = week_start - 1 day` a `lookback_end = week_end` (8 dias efectivos) |
| **Driver universe** | Todos los drivers en `growth.yango_lima_orders_raw` con `driver_profile_id IS NOT NULL` |

### 2.2 Coincidencia con Definicion Oficial de Control Tower

| Verificacion | Status |
|-------------|--------|
| Usa `trips_completed` (no `trips` totales)? | **PASS** — `completed_trips` de `driver_daily_activity_fact` |
| Filtra por `completed_flag`? | **PASS** — `completed_trips` ya es solo completados |
| Grain semanal es consistente? | **PASS** — `week_start` es lunes |
| Ventana cubre la semana exacta? | **WARNING** — `lookback_start = week_start - 1 day`. La ventana es de 8 dias (incluye el dia anterior al lunes). Esto infla ligeramente los conteos. |
| Coincide con definicion de viaje completado en Omniview? | **PASS** — `completed_trips` en Driver360 = misma fuente upstream |
| Driver universe es correcto? | **WARNING** — Solo drivers presentes en `yango_lima_orders_raw`. Drivers que nunca han tenido una orden en raw orders NO aparecen, aunque tengan viajes en `driver_daily_activity_fact`. |

### 2.3 Veredicto Completed Orders

**PASS (2 WARNINGS)**

| Issue | Severity | Detail |
|-------|----------|--------|
| Ventana de 8 dias | WARNING | `lookback_start = week_start - 1 day` incluye el domingo anterior. Para un lunes, la ventana es lun-dom + domingo previo = 8 dias. |
| Driver universe limitado | WARNING | Solo drivers con registros en `yango_lima_orders_raw`. Si raw orders no tiene datos recientes, el cohort queda vacio. |

---

## PART 3 — SUPPLY HOURS AUDIT

### 3.1 Definicion Exacta

| Atributo | Valor |
|----------|-------|
| **Nombre en DB** | `supply_hours_week` |
| **Definicion** | Horas de supply semanal estimadas desde timestamps de ordenes |
| **Fuente** | `growth.yango_lima_orders_raw` |
| **SQL exacto** | `SUM(EXTRACT(EPOCH FROM (COALESCE(ended_at, created_at) - created_at)) / 3600.0) AS supply_hours_raw` |
| **Archivo:linea** | `yego_lima_loyalty_sub50_service.py:119-121` |
| **Grain** | Weekly — agrupa por `driver_profile_id` dentro de la semana |
| **Filtros** | `ended_at >= start AND ended_at <= end+1d AND created_at IS NOT NULL AND ended_at IS NOT NULL AND ended_at > created_at` |
| **Agregacion** | `GROUP BY driver_profile_id` → `SUM(epoch_difference / 3600)` |

### 3.2 Origen de supply_hours

**CRITICO — supply_hours es INFERIDO desde ordenes, NO desde una fuente de supply real.**

```python
# yego_lima_loyalty_sub50_service.py:119-121
SUM(
    EXTRACT(EPOCH FROM (COALESCE(ended_at, created_at) - created_at)) / 3600.0
) AS supply_hours_raw
FROM growth.yango_lima_orders_raw
```

Esta formula calcula la duracion de cada orden (`ended_at - created_at`) como proxy de horas de supply. Esto NO es una medicion de horas de trabajo del conductor. Es una inferencia desde actividad transaccional.

### 3.3 Verificacion de Fuente

| Pregunta | Respuesta |
|----------|-----------|
| Proviene de `growth.yango_lima_driver_360_daily`? | **NO** |
| Proviene de `ops.driver_daily_activity_fact`? | **NO** |
| Proviene de `public.module_ct_fleet_summary_daily`? | **NO** |
| Es inferido desde orders/trips? | **SI** — duracion de ordenes como proxy |
| La tabla tiene columna `work_time_hours`? | La tabla `yango_lima_orders_raw` NO tiene columna de horas de trabajo. Solo tiene `created_at` y `ended_at` de cada orden. |

### 3.4 Veredicto Supply Hours

**FAIL**

| Issue | Severity | Detail |
|-------|----------|--------|
| Supply hours inferido, no real | **FAIL** | `(ended_at - created_at)` de cada orden NO es supply hours real. Es duracion de orden. Un conductor puede tener muchas ordenes de 5 min con gaps largos entre ellas → `supply_hours` seria bajo aunque trabajo 10h. Inversamente, un conductor con pocas ordenes largas (ej: 1 orden de 60 min) tendria `supply_hours` alto con 1 solo viaje. |
| `trips_per_supply_hour` es enganoso | **WARNING** | Derivado de un proxy incorrecto. El ratio `completed / supply_hours` mide "viajes por hora de orden", NO "viajes por hora de trabajo". |
| Sin fuente de ground truth | **FAIL** | No hay integracion con supply real (horas de conexion, horas de trabajo, fleet summary). La nota en el codigo (linea 12) reconoce esto: "proxy hasta tener supply fact". |
| `productivity_band` usa este proxy | **WARNING** | `LOW_PRODUCTIVITY` / `HIGH_PRODUCTIVITY` se calcula sobre `trips_per_supply_hour`, que es un ratio derivado de un proxy. Las clasificaciones de productividad heredan el error del proxy. |

---

## PART 4 — DRIVER 360 AUDIT

### 4.1 Confirmacion

| Pregunta | Respuesta |
|----------|-----------|
| Usa `growth.yango_lima_driver_360_daily`? | **NO** |
| Usa `ops.driver_daily_activity_fact`? | **SI** — descrito como "Driver360" en comentarios |
| Que es `driver_daily_activity_fact`? | Fact table con metrica diaria por driver: `driver_id`, `activity_date`, `completed_trips`. Poblada por los driver serving facts builds. |

### 4.2 Impacto

| Aspecto | Impacto |
|---------|---------|
| `completed_orders_week` correcto? | **SI** — `driver_daily_activity_fact.completed_trips` es una fuente valida para viajes completados |
| `supply_hours_week` afectado? | **SI** — `driver_daily_activity_fact` no tiene supply hours. Por eso se usa `yango_lima_orders_raw` como proxy |
| La tabla `growth.yango_lima_driver_360_daily` existe? | **SI** — existe en la DB pero no es utilizada por el Sub50 engine |
| Tiene la tabla `driver_360_daily` columnas utiles? | Desconocido — no se inspecciono el schema de la tabla. El hecho de que exista y no se use sugiere una oportunidad de mejora para supply_hours |

### 4.3 Veredicto Driver 360

**WARNING**

El Sub50 engine usa `ops.driver_daily_activity_fact` como fuente de completed_trips (correcto) pero NO usa `growth.yango_lima_driver_360_daily` para supply_hours. En su lugar, infiere supply hours desde ordenes raw. Si `driver_360_daily` contiene supply hours real, la implementacion actual esta usando un proxy innecesariamente.

---

## PART 5 — META SUB-50 AUDIT

### 5.1 Ubicacion del Umbral

El umbral de **50 viajes** aparece en una sola ubicacion de codigo:

```python
# yego_lima_loyalty_sub50_service.py:66-67
def _compute_distance_to_50(completed: int) -> int:
    return max(0, 50 - completed)
```

### 5.2 Clasificacion

| Aspecto | Status |
|---------|--------|
| Hardcoded? | **SI** — literal `50` en linea 67 |
| Configurable via settings.py? | **NO** — no existe `LOYALTY_SUB50_TRIP_THRESHOLD` ni similar |
| Configurable via env? | **NO** |
| Configurable via DB? | **NO** |
| Parcialmente configurable? | **NO** |

### 5.3 Impacto

| Riesgo | Detail |
|--------|--------|
| Cambio de meta requiere deploy | Cualquier ajuste de "50" a otro valor (ej: 30, 75, 100) requiere modificar codigo y redeploy |
| No se puede A/B test | Imposible comparar sub-50 vs sub-30 sin modificar codigo |
| No se puede configurar por ciudad | Lima, Trujillo, Arequipa comparten el mismo umbral si se expandiera |
| Inconsistente con otros thresholds | `YANGO_LOW_PRODUCTIVITY_TPH_THRESHOLD` y `YANGO_HIGH_PRODUCTIVITY_TPH_THRESHOLD` SI son configurables via settings.py. El "50" rompe el patron. |

### 5.4 Veredicto Meta Sub-50

**FAIL — Hardcoded**

---

## PART 6 — SEGMENTACION OPERACIONAL AUDIT

### 6.1 Lealtad 1 — Nuevos / Reactivados (Meta: 50 viajes en 14 dias, Retencion: 90 dias)

| Aspecto | Status |
|---------|--------|
| Identifica drivers NUEVOS? | **NO EXISTE** — No hay logica para detectar nuevos drivers. `driver_daily_activity_fact` no tiene `first_trip_date`. |
| Identifica drivers REACTIVADOS? | **NO EXISTE** — No hay logica de reactivacion. Los MVs de driver segment migration (`driver_segment_migration_fact`) detectan `REACTIVATED` como movimiento entre segmentos, pero Sub50 no lo consume. |
| Ventana de 14 dias? | **NO EXISTE** — Solo hay ventana semanal (7 dias, efectivamente 8 por el lookback). No hay logica de 14 dias. |
| Retencion 90 dias? | **NO EXISTE** — No hay tracking de retencion post-meta. |
| Seguimiento de progreso hacia 50? | **PARCIAL** — `distance_to_50` mide la distancia, pero no hay historial ni tendencia. |

### 6.2 Lealtad 2 — Activos bajo meta

| Aspecto | Status |
|---------|--------|
| Identifica drivers activos bajo 50? | **PARCIAL** — El engine clasifica a todos los drivers con <50 viajes en segmentos SUB50_XX_YY. Esto cubre "activos bajo meta" implicitamente. |
| Distingue entre activo-estable y activo-decayendo? | **NO EXISTE** — No hay historial ni tendencia. Un driver que decayo de 45→20 y uno que subio de 20→45 estan en el mismo segmento SUB50_20_29 si la semana actual es 22. |
| Tiene priorizacion? | **PARCIAL** — `growth_priority` ordena por cercania a 50, pero no considera tendencia ni valor historico del driver. |

### 6.3 Lealtad 3 — Degradados / At-Risk / Churn Risk

| Aspecto | Status |
|---------|--------|
| Identifica degradados? | **NO EXISTE en Sub50** — Los MVs de `driver_segment_migration_fact` y `driver_operational_priority_fact` SI tienen logica de downgrade/churn, pero no estan integrados con Sub50. |
| At-risk / Churn Risk? | **NO EXISTE en Sub50** — `driver_state` es una columna NULL placeholder. |
| Recoverability integrado? | **NO** — `recoverability_intelligence_service` existe como servicio separado (shadow mode) usando `driver_trip_behavior_daily_fact`. No hay integracion con Sub50. |

### 6.4 Matriz de Segmentacion

| Segmento | Definicion | Implementado? | Motor actual |
|----------|-----------|---------------|-------------|
| **LEALTAD 1** — Nuevos | Drivers nuevos, meta 50 viajes en 14 dias | **NO EXISTE** | — |
| **LEALTAD 1** — Reactivados | Drivers reactivados, meta 50 viajes en 14 dias | **NO EXISTE** | — |
| **LEALTAD 2** — Activos bajo meta | Drivers activos con <50 viajes/semana | **PARCIAL** | `SUB50_XX_YY` segments + `growth_priority` |
| **LEALTAD 3** — Degradados | Drivers que bajaron de segmento | **NO EXISTE en Sub50** | `driver_segment_migration_fact` (separado) |
| **LEALTAD 3** — At-Risk | Drivers con patron de declive | **NO EXISTE** | `recoverability_intelligence_service` (separado) |
| **LEALTAD 3** — Churn Risk | Drivers que dejaron de operar | **NO EXISTE en Sub50** | `driver_operational_priority_fact` (separado) |

### 6.5 Veredicto Segmentacion

**FAIL — Solo Lealtad 2 esta PARCIALMENTE implementada. Lealtad 1 y Lealtad 3 NO EXISTEN.**

---

## PART 7 — CONTROL LOOP READINESS

### 7.1 Evaluacion por Dimension

| Dimension | Sub50 Actual | Requerido para Control Loop | Gap |
|-----------|-------------|----------------------------|-----|
| `driver_id` | **SI** — `driver_profile_id` en la tabla | Identificador unico del driver | Ninguno |
| `cohorte` | **NO** — solo segmento de viajes (SUB50_XX_YY) | Clasificacion de lealtad (Nuevo/Activo/Degradado) | Faltan Lealtad 1 y 3 |
| `prioridad` | **PARCIAL** — `growth_priority` 1-5 | Scoring multi-factor (valor, urgencia, recoverabilidad) | Solo basado en cercania a 50 |
| `fecha` | **PARCIAL** — `week_start_date` | Ventana de accion (14 dias, 90 dias retencion) | Solo granularidad semanal |
| `metrica` | **SI** — `completed_orders_week`, `distance_to_50` | KPI accionable | Valores correctos pero limitados |
| `explicabilidad` | **NO** — solo numeros crudos | Razon de priorizacion, tendencia, contexto | Sin narrativa ni factores causales |

### 7.2 Clasificacion por Consumidor Futuro

| Consumidor | READY? | Razon |
|-----------|--------|-------|
| **Control Loop** | **NOT READY** | Sin cohortes de lealtad, sin ventana de 14 dias, sin tendencia, sin explicabilidad. Solo clasifica por conteo semanal. |
| **Call Center** | **NOT READY** | Sin `driver_state`, sin historial de contacto, sin telefono enmascarado en top-opportunities. `driver_profile_id_masked` es util pero insuficiente. |
| **Lealtad** | **PARTIAL** | La metrica base (completed_orders) es correcta. La priorizacion por cercania a 50 es util. Pero falta segmentacion real (nuevo vs activo vs degradado) y ventana temporal correcta. |
| **Acciones** | **NOT READY** | Sin recommended_action, sin canal preferido, sin elegibilidad. Solo prioridad numerica sin contexto operativo. |

### 7.3 Veredicto Control Loop Readiness

**NOT READY** — La implementacion actual es un prototipo de clasificacion, no un motor de intervencion. Puede servir como input a un sistema de lealtad, pero no puede consumirse directamente por Control Loop sin capas adicionales de segmentacion, contexto temporal y explicabilidad.

---

## PART 8 — GOVERNANCE AUDIT

### 8.1 Source of Truth

| Pregunta | Status | Detail |
|----------|--------|--------|
| Esta registrado en `source_of_truth_registry.py`? | **FAIL** | No hay entrada para `loyalty_sub50`, `driver_sub50`, ni `growth.yango_lima_loyalty_sub50_weekly`. |
| El dominio tiene primary source declarado? | **FAIL** | No existe el dominio. |
| Tiene `source_mode` definido? | **FAIL** | Sin registro → sin modo (canonical/migrating/legacy). |

### 8.2 Metric Definition

| Pregunta | Status | Detail |
|----------|--------|--------|
| `completed_orders_week` tiene definicion documentada? | **FAIL** | Solo en el SQL inline. No en `kpi_semantics.py` ni en metric definition sets. |
| `supply_hours_week` tiene definicion documentada? | **FAIL** | Idem. Nota: "proxy hasta tener supply fact" en comentario de codigo. |
| `distance_to_50` tiene definicion documentada? | **WARNING** | Trivial (`50 - completed`), pero no documentada fuera del codigo. |
| Definicion de "viaje completado" es consistente? | **PASS** | Usa `completed_trips` de `driver_daily_activity_fact`, misma fuente que el resto del sistema. |
| Definicion de "supply hours" es consistente? | **FAIL** | El sistema tiene multiples definiciones de supply_hours: `module_ct_fleet_summary_daily` (loyalty performance), `yango_lima_orders_raw` proxy (sub50), manual KPI (yango loyalty). No hay una unica fuente canonica. |

### 8.3 Grain Consistency

| Pregunta | Status | Detail |
|----------|--------|--------|
| Grain semanal es consistente? | **WARNING** | La ventana es `[week_start-1d, week_end]` = 8 dias. Las otras metricas semanales del sistema usan `[week_start, week_start+6d]` = 7 dias. |
| Grain esta alineado con Omniview? | **WARNING** | Omniview usa ISO weeks. Sub50 usa week_start manual (parametro del endpoint). No hay validacion de que sea lunes. |
| Rollup daily→weekly validado? | **PASS** | `SUM(completed_trips)` desde `driver_daily_activity_fact` → aditivo puro. |

### 8.4 Freshness

| Pregunta | Status | Detail |
|----------|--------|--------|
| Hay freshness tracking? | **FAIL** | No hay `last_calculated_at` expuesto en los endpoints de lectura. No hay freshness status. |
| Hay alerta de datos stale? | **FAIL** | Si `yango_lima_orders_raw` no tiene datos recientes, el cohort queda vacio sin advertencia. |
| Hay refresh automatico? | **FAIL** | `build_loyalty_sub50` es manual (POST). No hay scheduler. |
| Dependencia de datos externos? | **FAIL** | Depende de `yango_lima_orders_raw` poblado via Yango API (que esta detras de `YANGO_API_ENABLED`). Si la API esta disabled, todo el pipeline muere. |

### 8.5 Traceability

| Pregunta | Status | Detail |
|----------|--------|--------|
| Se puede trazar un valor hasta su fuente? | **PARTIAL** | `completed_orders_week` → `driver_daily_activity_fact` → upstream. `supply_hours_week` → `yango_lima_orders_raw` → Yango API. Trazable pero no documentado formalmente. |
| Hay audit trail de cambios? | **FAIL** | No hay tabla de auditoria. UPSERT sobreescribe sin historial. |
| Columna `source` en la tabla? | **PASS** | `source = 'loyalty_sub50'` hardcoded en el UPSERT. Al menos identifica el origen del row. |

### 8.6 Configurabilidad

| Parametro | Configurable? | Ubicacion |
|-----------|--------------|-----------|
| Umbral de 50 viajes | **FAIL** — Hardcoded | `yego_lima_loyalty_sub50_service.py:67` |
| Segmentos (40-49, 30-39, ...) | **FAIL** — Hardcoded | `yego_lima_loyalty_sub50_service.py:30-36` |
| Prioridades de segmento | **FAIL** — Hardcoded | `yego_lima_loyalty_sub50_service.py:38-44` |
| Productivity LOW threshold (0.5) | **PASS** — settings | `settings.py:341 YANGO_LOW_PRODUCTIVITY_TPH_THRESHOLD` |
| Productivity HIGH threshold (2.0) | **PASS** — settings | `settings.py:347 YANGO_HIGH_PRODUCTIVITY_TPH_THRESHOLD` |
| Ventana temporal (7 dias) | **FAIL** — Hardcoded | `yego_lima_loyalty_sub50_service.py:88-89` |
| Driver universe source | **FAIL** — Hardcoded | `yego_lima_loyalty_sub50_service.py:79-84` (siempre `yango_lima_orders_raw`) |
| Tabla destino | **FAIL** — Hardcoded | `growth.yango_lima_loyalty_sub50_weekly` en todos los SQL strings |

**Score de configurabilidad: 2/8 parametros configurables (25%).**

### 8.7 Dependencia de Proxies

| Metrica | Fuente real | Proxy usado | Riesgo |
|---------|-----------|------------|--------|
| `completed_orders_week` | `driver_daily_activity_fact` | — | **BAJO** |
| `supply_hours_week` | No existe | `yango_lima_orders_raw` (duracion de ordenes) | **ALTO** |
| `trips_per_supply_hour_week` | — | Derivado de proxy de supply | **ALTO** |
| `productivity_band` | — | Derivado de proxy de supply | **ALTO** |

### 8.8 Governance Scorecard

| Dimension | Status |
|-----------|--------|
| Source of Truth | **FAIL** |
| Metric Definition | **FAIL** |
| Grain Consistency | **WARNING** |
| Freshness | **FAIL** |
| Traceability | **PARTIAL** |
| Configurabilidad | **FAIL** |
| Dependencia de Proxies | **FAIL** |

**Governance Score: 0 PASS, 1 PARTIAL, 1 WARNING, 5 FAIL**

---

## PART 9 — RESULTADO EJECUTIVO

### A. Que sirve hoy

1. **Clasificacion semanal de drivers por volumen** — `build_loyalty_sub50()` identifica correctamente drivers con menos de 50 viajes y los segmenta por bandas (40-49, 30-39, ...). La logica de `SUM(completed_trips)` es correcta.
2. **Priorizacion basica** — `growth_priority` ordena por cercania a 50. Util para identificar quick-wins.
3. **Persistencia** — Los resultados se guardan en `growth.yango_lima_loyalty_sub50_weekly` con UPSERT por semana+driver_id.
4. **Top-opportunities** — `get_top_opportunities()` expone drivers priorizados con IDs enmascarados. Util para consumo manual.
5. **Supply-opportunities** — `get_supply_opportunities()` identifica drivers con alto supply y bajos viajes (ineficiencia).

### B. Que esta mal

1. **Supply hours es un proxy incorrecto** — `(ended_at - created_at)` de ordenes NO es horas de trabajo. Un driver con 10 viajes de 5 min = 50 min de "supply". En realidad trabajo 8h. `trips_per_supply_hour` y `productivity_band` heredan este error.
2. **Ventana temporal incorrecta** — 8 dias en vez de 7 (lookback incluye el dia anterior al lunes). Y no existe la ventana de 14 dias requerida para Lealtad 1.
3. **Meta 50 hardcoded** — Imposible ajustar sin deploy. Rompe el patron de configuracion del sistema.
4. **Sin segmentacion de lealtad** — No distingue nuevos, reactivados, activos, degradados. Solo clasifica por conteo de viajes.
5. **Sin retencion** — No hay tracking post-meta (90 dias). No se sabe si un driver que llego a 50 se mantiene.
6. **Sin tendencia** — Un driver en `SUB50_20_29` puede estar subiendo o bajando. La clasificacion es puntual, no historica.
7. **Sin scheduler** — Build manual. Sin refresh automatico, los datos se vuelven obsoletos.
8. **Sin UI** — Los endpoints existen pero no hay frontend. Imposible que operaciones los use.

### C. Riesgos de negocio

| Riesgo | Severidad | Descripcion |
|--------|-----------|-------------|
| Decisiones basadas en supply_hours erroneo | **HIGH** | Priorizar drivers por `trips_per_supply_hour` o `productivity_band` es peligroso. Un driver eficiente puede aparecer como LOW_PRODUCTIVITY si tiene ordenes cortas. |
| Cohort vacio por falta de ingestion | **HIGH** | Si `capture-orders-range` no se ejecuto, `yango_lima_orders_raw` no tiene datos → `build_loyalty_sub50` devuelve cohort vacio. Sin alerta. |
| Confianza en datos no certificados | **MEDIUM** | Si un stakeholder toma decisiones basadas en estos endpoints sin entender los proxies, las decisiones seran incorrectas. |
| Escalamiento sin gobernanza | **MEDIUM** | Sin SOT registry, sin metric definitions, sin freshness tracking. Agregar mas endpoints sin gobernanza multiplica la deuda tecnica. |

### D. Riesgos de escalamiento

| Riesgo | Severidad | Descripcion |
|--------|-----------|-------------|
| Hardcoded values explosion | **HIGH** | Si se agregan mas ciudades (Trujillo, Arequipa), cada una necesitaria su propio umbral, ventana, y segmentos. Con valores hardcoded, esto se vuelve inmantenible. |
| Sin indice de crecimiento | **HIGH** | No hay forma de medir si Sub50 esta funcionando: sin baseline, sin conversion rate, sin retention rate. |
| Driver universe no escalable | **MEDIUM** | `yango_lima_orders_raw` es el universo de drivers. Si no tiene datos para una ciudad nueva, el cohort esta vacio. |

### E. Que debe refactorizarse

| Componente | Accion | Prioridad |
|-----------|--------|-----------|
| `supply_hours_week` | Reemplazar con fuente real de supply (Driver360, fleet summary, o work_time de billing) | **P0** |
| Meta 50 | Mover a settings.py (configurable por ciudad) | **P0** |
| Ventana temporal | Corregir a 7 dias exactos; agregar ventana de 14 dias para Lealtad 1 | **P0** |
| Segmentacion | Agregar `driver_state`: NEW, REACTIVATED, ACTIVE_BELOW_50, AT_RISK, DEGRADED, CHURNED | **P1** |
| Tendencias | Agregar `last_week_completed`, `trend_direction`, `trend_magnitude` | **P1** |
| Scheduler | APScheduler job semanal para `build_loyalty_sub50` | **P1** |
| Governance | Registrar en `source_of_truth_registry.py`, `kpi_semantics.py`, metric definition sets | **P1** |
| Freshness | Agregar `last_calculated_at` a endpoints de lectura; alerta si datos stale > 7 dias | **P1** |
| Explicabilidad | Agregar `priority_reason`, `suggested_action`, `suggested_channel` | **P2** |
| UI | Frontend basico con tabla de drivers Sub50 y filtros | **P2** |
| Retencion | Tracking de 90 dias post-meta: `reached_50_date`, `active_at_day_30/60/90` | **P2** |
| Audit trail | Tabla de historial (no UPSERT ciego) o `valid_from`/`valid_to` en la tabla actual | **P2** |

### F. Que puede quedarse igual

1. **`ops.driver_daily_activity_fact` como fuente de completed_trips** — Correcta y alineada con el resto del sistema.
2. **`growth.yango_lima_loyalty_sub50_weekly` como tabla de destino** — Estructura adecuada. Solo requiere columnas adicionales para tendencia y estado.
3. **`get_top_opportunities()` y `get_supply_opportunities()`** — Logica de consulta correcta. Solo los datos subyacentes necesitan mejora.
4. **Enmascaramiento de driver_id** — `_mask_driver_id()` es adecuado para exposicion en API.
5. **Productivity bands configurables** — `YANGO_LOW_PRODUCTIVITY_TPH_THRESHOLD` y `YANGO_HIGH_PRODUCTIVITY_TPH_THRESHOLD` en settings.py es el patron correcto.

### G. Plan de correccion priorizado

#### P0 — Bloqueantes para cualquier uso operativo

| ID | Accion | Archivos |
|----|--------|----------|
| P0.1 | Reemplazar `supply_hours_week` con fuente real | `yego_lima_loyalty_sub50_service.py:119-131` |
| P0.2 | Mover umbral 50 a `settings.py` (con default 50, configurable por ciudad) | `settings.py`, `yego_lima_loyalty_sub50_service.py:67` |
| P0.3 | Corregir ventana temporal a 7 dias exactos | `yego_lima_loyalty_sub50_service.py:90-91` |
| P0.4 | Agregar validacion de lunes para `week_start_date` | `yego_lima_loyalty_sub50_service.py:88` |

#### P1 — Necesarios para Control Loop / Call Center

| ID | Accion | Archivos |
|----|--------|----------|
| P1.1 | Agregar columna `driver_state` con valores: NEW, REACTIVATED, ACTIVE_BELOW_50, AT_RISK, DEGRADED, CHURNED | `162_yego_lima_loyalty_sub50_weekly.py`, service |
| P1.2 | Agregar ventana de 14 dias para Lealtad 1 | Service + migration |
| P1.3 | Agregar columnas de tendencia: `last_week_completed`, `trend_direction` | Migration + service |
| P1.4 | Scheduler semanal para build automatico | `serving_refresh_scheduler.py` o nuevo scheduler |
| P1.5 | Governance: SOT registry, metric definitions, freshness | `source_of_truth_registry.py`, `kpi_semantics.py`, service |

#### P2 — Diferenciadores para produccion

| ID | Accion | Archivos |
|----|--------|----------|
| P2.1 | Explicabilidad: `priority_reason`, `suggested_action` | Service + migration |
| P2.2 | Frontend Sub50 basico | Nuevo componente React |
| P2.3 | Retencion 30/60/90 dias post-meta | Service + migration |
| P2.4 | Audit trail (historial en vez de UPSERT ciego) | Migration |

---

## GLOBAL CERTIFICATION SUMMARY

| Parte | Metrica | Veredicto |
|-------|---------|-----------|
| PART 2 | Completed Orders | **PASS** (2 WARNINGS) |
| PART 3 | Supply Hours | **FAIL** — Inferido de ordenes, no real |
| PART 4 | Driver 360 | **WARNING** — No usa `driver_360_daily` |
| PART 5 | Meta Sub-50 | **FAIL** — Hardcoded |
| PART 6 | Segmentacion Operacional | **FAIL** — Solo Lealtad 2 parcial |
| PART 7 | Control Loop Readiness | **NOT READY** |
| PART 8 | Governance | **0 PASS / 1 PARTIAL / 1 WARNING / 5 FAIL** |

### Veredicto Final

**LOYALTY SUB-50: NOT CERTIFIED FOR PRODUCTION**

La implementacion actual es un prototipo funcional de laboratorio (Fase 2B) que clasifica drivers por volumen semanal. No esta lista para evolucionar hacia programas de intervencion operativa por 3 razones fundamentales:

1. **Supply hours es falso** — La metrica mas importante para productividad se calcula desde un proxy que no mide horas de trabajo. Cualquier decision basada en `trips_per_supply_hour` o `productivity_band` es potencialmente incorrecta.

2. **Sin segmentacion de lealtad** — No distingue entre un driver nuevo que necesita alcanzar 50 viajes (Lealtad 1), un driver activo que bajo de 60 a 40 (Lealtad 3), o un driver estable en 30 (Lealtad 2). Sin esta distincion, el sistema no puede recomendar intervenciones diferenciadas.

3. **Sin gobernanza** — Meta hardcoded, sin SOT registry, sin metric definitions, sin freshness tracking, sin scheduler. Cualquier expansion (mas ciudades, mas umbrales, mas segmentos) multiplica la deuda tecnica.

**Para que Sub50 sea apto para Control Loop, se requiere completar P0 y P1 del plan de correccion.**
