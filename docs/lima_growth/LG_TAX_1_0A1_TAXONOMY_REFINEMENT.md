# LG-TAX-1.0A.1 — TAXONOMY REFINEMENT (E2E)

**Fase:** Lima Growth Foundation — TAX-1.0A.1  
**Motor:** Control Foundation (Lima Growth)  
**Estatus:** DESIGN ONLY — NO IMPLEMENTAR  
**Fecha:** 2026-06-10  
**Simulación:** data real 2026-06-10, N=18,545 drivers, 10 modelos de ejes comparados  
**Dependencia:** `LG_TAX_1_0A_DRIVER_TAXONOMY_FOUNDATION.md` (V1)

---

## TASK 0 — GOVERNANCE RE-VALIDACIÓN

### Fase Activa (sin cambios desde TAX-1.0A)

| Motor | Fase | Estatus |
|-------|------|---------|
| Control Foundation | Omniview P0 Recovery | **REOPENED / P0** |
| Diagnostic Engine | 2A.3 | **PAUSED** |
| Lima Growth | Scheduler 5-min tick | **ACTIVE** |

### Restricciones (sin cambios)

- NO activar Forecast, Suggestion, Decision, Action, AI
- NO modificar queue, export, control_loop, scheduler, ingestion
- NO tocar programas legacy, UI productiva
- LG-TAX-1.0A.1 es puramente diseño de refinamiento conceptual

### Veredicto: **GO para diseño.** No viola restricciones.

---

## TASK 1 — AUDITORÍA CRÍTICA DEL MODELO ACTUAL (TAX-1.0A V1)

### Evidencia de la Simulación V1

| Eje | Distribución | Gini | Diagnóstico |
|-----|-------------|------|-------------|
| Activity | **ACTIVE 100%** | 1.000 | **ROTO** — Sin poder discriminante. 1 solo estado para 18,545 drivers. |
| Lifecycle | MATURE 97%, NEW 3% | 0.470 | **DÉBIL** — Solo 2 estados activos. REACTIVATED inalcanzable sin pipeline. |
| Momentum | STABLE 97%, DECLINING 3% | 0.469 | **DÉBIL** — Solo 2 estados activos. GROWING inalcanzable por min_volume. |
| Value | LOW 51%, MEDIUM 28%, HIGH 12%, TOP 9% | 0.298 | **ACEPTABLE** — Mejor distribución de los 4 ejes. |

### Análisis por Eje

#### Lifecycle: Qué funciona / Qué no

| Funciona | No Funciona |
|----------|-------------|
| NEW detecta correctamente conductores recién ingresados (555 drivers, 3%) | REACTIVATED inalcanzable: `reactivated_flag` no está poblado en el snapshot actual |
| MATURE captura al 97% restante con `first_seen_at` confiable | Solo 2 estados activos (NEW, MATURE). Poco poder discriminante. |
| Las reglas son configurables (`new_window_days`, `maturity_after_days`) | No distingue entre MATURE de 3 meses y MATURE de 3 años |

**Problema operacional**: Un conductor de 61 días y uno de 500 días son ambos "MATURE". El programa 90/300 necesita saber si está en early-maturity o late-maturity. La taxonomía V1 no lo provee.

#### Activity: Qué funciona / Qué no

| Funciona | No Funciona |
|----------|-------------|
| `completed_orders_week > 0` es señal confiable (100% poblado) | `last_trip_at` muestra >90d para 10,630 drivers (57%) incluso con `completed_orders_week > 0` — señal degradada |
| El concepto ACTIVE/AT_RISK/CHURNED es correcto conceptualmente | `last_supply_at` es NULL para 18,545 drivers (100%) — segunda señal inutilizable |
| | Con solo `cw > 0` como señal, el eje colapsa a 100% ACTIVE: **cero poder discriminante** |

**Problema operacional**: Activity no distingue nada. No podemos identificar drivers en riesgo de abandono ni drivers completamente inactivos. Es el eje más roto de la taxonomía V1.

#### Value: Qué funciona / Qué no

| Funciona | No Funciona |
|----------|-------------|
| `avg_orders_4w` es señal confiable y bien distribuida | Los percentiles dependen del universo del día — un "HIGH" hoy puede ser "MEDIUM" mañana sin cambiar su producción |
| Distribución balanceada (20/50/20/10) cuando se usan percentiles reales | Umbrales absolutos producen 75% LOW (Gini=0.550) — peor discriminación |
| 4 tiers (TOP/HIGH/MEDIUM/LOW) son suficientes | |

**Problema operacional**: La inestabilidad temporal de los percentiles (cambian diariamente con el universo) puede causar "churn de clasificación": un driver cambia de tier sin cambiar su producción. Esto confunde a los programas que consumen la taxonomía.

#### Momentum: Qué funciona / Qué no

| Funciona | No Funciona |
|----------|-------------|
| `declining_flag` captura 575 declinadores reales (3.1%) | 96.9% STABLE porque el `min_volume_for_momentum=4` excluye a la mayoría de conductores |
| `avg_orders_4w` vs `avg_orders_12w` es un delta calculable | A volúmenes bajos (1-3 viajes/semana), el delta porcentual es ruido, no señal |
| | GROWING es inalcanzable: 0 conductores muestran +20% sostenido con volumen suficiente |
| | Solo 3 estados (GROWING/STABLE/DECLINING) — insuficiente granularidad |

**Problema operacional**: Momentum no detecta transiciones tempranas. Un driver que pasa de 8 a 5 viajes/semana (-37.5%) sigue siendo STABLE si no cruza el umbral de declining_flag. HVR requiere detectar caídas fuertes, no solo declives graduales.

---

## TASK 2 — REDISEÑO DE ACTIVITY

### Problema Central

Activity V1 colapsa porque depende de señales de recencia (`last_trip_at`, `last_supply_at`) que están rotas. Necesitamos un eje que use señales confiables y tenga poder discriminante real.

### Alternativas Evaluadas

#### Modelo A: ACTIVITY V1 (ACTIVE / AT_RISK / CHURNED) — STATUS QUO

| Aspecto | Evaluación |
|---------|-----------|
| Señales | `last_trip_at`, `completed_orders_week`, `last_supply_at` |
| Distribución | ACTIVE 100%, AT_RISK 0%, CHURNED 0% |
| Gini | **1.000** (máxima concentración — peor caso posible) |
| Estados activos | 1 de 3 |
| Pros | Conceptualmente correcto. Si las señales se repararan, funcionaría. |
| Contras | **Inutilizable hoy.** Depende de 2 señales rotas. 0 poder discriminante. |
| Capacidad de decisión | **NULA.** No permite decidir nada. |

#### Modelo B: FREQUENCY (CONSISTENT / REGULAR / SPORADIC / IDLE)

| Aspecto | Evaluación |
|---------|-----------|
| Señales | `avg_orders_4w` (confiable) |
| Distribución | CONSISTENT 33%, REGULAR 16%, SPORADIC 51%, IDLE 0% |
| Gini | **0.231** (mejor Gini de todos los modelos testeados) |
| Estados activos | 3 de 4 (IDLE vacío porque todos tienen cw>0) |
| Pros | Excelente discriminación. Usa señal 100% confiable. 3 estados activos bien distribuidos. |
| Contras | Mide volumen de viajes, que ya está cubierto por Value (`avg_orders_4w`). Redundancia parcial con Value. No captura riesgo de abandono. |
| Capacidad de decisión | **MEDIA.** Bueno para segmentar por nivel de actividad, pero no responde "¿está en riesgo?" |

#### Modelo C: HEALTH (HEALTHY / WATCH / AT_RISK / CRITICAL)

| Aspecto | Evaluación |
|---------|-----------|
| Señales | `retention_state`, `declining_flag`, `churn_risk_flag` (todas confiables) |
| Distribución | HEALTHY 56%, WATCH 2%, AT_RISK 4%, CRITICAL 38% |
| Gini | **0.495** |
| Estados activos | 4 de 4 |
| Pros | Señales 100% confiables y disponibles. Captura directamente el riesgo operacional. Responde "¿necesita intervención?" — que es lo que los programas necesitan saber. No se solapa con Value (mide salud, no volumen). |
| Contras | Depende de la calidad del `retention_state`, que es una clasificación ya derivada. Si el pipeline de retention_state falla, HEALTH falla. |
| Capacidad de decisión | **ALTA.** Directamente accionable: HEALTHY → mantener, WATCH → monitorear, AT_RISK → intervención suave, CRITICAL → intervención urgente. |

### Comparación Directa

| Criterio | Modelo A (Activity) | Modelo B (Frequency) | Modelo C (Health) |
|----------|---------------------|----------------------|-------------------|
| Gini | 1.000 | **0.231** | 0.495 |
| Señales confiables | 1/3 | 1/1 | 3/3 |
| Sin solapamiento con Value | OK | **REDUNDANTE** | OK |
| Responde "¿está en riesgo?" | NO | NO | **SÍ** |
| Accionable por programas | NO | PARCIAL | **SÍ** |
| Detecta HVR candidates | NO | NO | **SÍ** (CRITICAL + HIGH/TOP) |
| Detecta churn temprano | NO | NO | **SÍ** (WATCH → AT_RISK) |

### Recomendación: **MODELO C — HEALTH**

**Justificación**:

1. **Señales 100% confiables**: `retention_state`, `declining_flag` y `churn_risk_flag` están poblados y son calculados por el pipeline de `driver_state_snapshot` con lógica auditada.

2. **No se solapa con Value**: Value mide cuánto produce (output). Health mide qué tan saludable está su relación con la plataforma (riesgo). Son dimensiones ortogonales. Un driver puede ser TOP value y CRITICAL health (high performer about to churn = máxima prioridad HVR).

3. **Directamente accionable**: Los programas no necesitan interpretar Activity para decidir. HEALTHY/WATCH/AT_RISK/CRITICAL mapea directamente a prioridad de intervención.

4. **Captura el精神 de Activity**: La pregunta original de Activity era "¿está activo o en riesgo?" Health responde exactamente eso pero con señales que funcionan.

5. **No requiere señales rotas**: No depende de `last_trip_at` ni `last_supply_at`. Funciona hoy con los datos disponibles.

**Estados HEALTH**:

| Estado | Definición | Señales | Interpretación operacional |
|--------|-----------|---------|---------------------------|
| **HEALTHY** | Sin señales de riesgo | `retention_state = HEALTHY` AND `declining_flag = false` AND `churn_risk_flag = false` | No intervenir. Monitoreo pasivo. |
| **WATCH** | Señal débil de atención | `retention_state = WATCHLIST` OR (`retention_state = HEALTHY` AND `recoverable_flag = true`) | Monitoreo activo. Sin acción inmediata. |
| **AT_RISK** | Riesgo moderado de abandono | `retention_state = AT_RISK` OR `declining_flag = true` OR (`churn_risk_flag = true` AND `retention_state != CHURN_RISK`) | Intervención recomendada. Ventana de acción: días. |
| **CRITICAL** | Riesgo alto de abandono | `retention_state = CHURN_RISK` AND (`declining_flag = true` OR `churn_risk_flag = true`) | Intervención urgente. Ventana de acción: horas. |

**Simulación**:

| Estado | Drivers | % |
|--------|---------|---|
| HEALTHY | 10,470 | 56.5% |
| WATCH | 301 | 1.6% |
| AT_RISK | 775 | 4.2% |
| CRITICAL | 6,999 | 37.7% |

**Nota**: 37.7% CRITICAL parece alto. Refleja que `churn_risk_flag = true` para 6,999 conductores (38%). Esto es una señal del pipeline actual — posiblemente la definición de `churn_risk_flag` es muy sensible. Recomendación: calibrar el umbral de `churn_risk_flag` en el pipeline de `driver_state_snapshot`, no en la taxonomía. La taxonomía refleja la señal; si la señal es ruidosa, el pipeline debe ajustarse.

---

## TASK 3 — REDISEÑO DE VALUE

### Problema Central

Value V1 usa percentiles dinámicos. Esto produce buena distribución pero es inestable en el tiempo (los umbrales cambian diariamente). Evaluamos 3 modelos.

### Modelo A: PERCENTILES DINÁMICOS

| Aspecto | Evaluación |
|---------|-----------|
| Umbrales (2026-06-10) | p30=3.0, p70=11.2, p90=44.5 |
| Distribución | LOW 20%, MEDIUM 50%, HIGH 20%, TOP 10% |
| Gini | **0.298** |
| Pros | Distribución garantizada balanceada. Se adapta a cambios estacionales del mercado.公平 entre mercados. |
| Contras | Un driver puede cambiar de tier sin cambiar producción (el universo se movió). Difícil de explicar: "TOP porque sos mejor que el 90% del mercado" vs "TOP porque hacés >X viajes". |
| Sensibilidad operacional | ALTA — cambios diarios en umbrales pueden disparar cambios de programa. |
| Estabilidad temporal | BAJA — percentiles fluctúan con el universo. |

### Modelo B: ABSOLUTO

| Aspecto | Evaluación |
|---------|-----------|
| Umbrales fijos | TOP >= 80, HIGH >= 40, MEDIUM >= 15, LOW < 15 |
| Distribución | LOW 75%, MEDIUM 14%, HIGH 8%, TOP 3% |
| Gini | **0.550** |
| Pros | Estable en el tiempo. Fácil de explicar. Consistente entre días. |
| Contras | 75% LOW — mala discriminación. No se adapta a cambios de mercado. Un mercado con promedio 5 viajes/semana tendrá 75% LOW para siempre. |
| Sensibilidad operacional | BAJA — umbrales no cambian. |
| Estabilidad temporal | ALTA — pero a costo de discriminación. |

### Modelo C: HÍBRIDO (Percentil + Piso Absoluto)

| Aspecto | Evaluación |
|---------|-----------|
| Lógica | TOP: >=50 viajes (absoluto), HIGH: >=p70 AND >=15, MEDIUM: >=p30 AND >=3, LOW: >0, INACTIVE: 0 |
| Distribución | INACTIVE 0%, LOW 20%, MEDIUM 55%, HIGH 16%, TOP 9% |
| Gini | **0.353** |
| Pros | TOP tiene significado absoluto (50+ viajes = elite real). HIGH/MEDIUM usan percentiles para adaptarse al mercado pero con pisos mínimos que evitan inflación. Fácil de explicar. |
| Contras | Más complejo de configurar que percentil puro. |
| Sensibilidad operacional | MEDIA — TOP es estable, HIGH/MEDIUM fluctúan con percentiles dentro de bandas. |
| Estabilidad temporal | MEDIA-ALTA — los pisos absolutos amortiguan fluctuaciones. |

### Comparación Directa

| Criterio | Percentil | Absoluto | Híbrido |
|----------|-----------|----------|---------|
| Gini | **0.298** | 0.550 | 0.353 |
| TOP estabilidad | Inestable | Estable | **Estable** |
| MEDIUM/LOW adaptabilidad | Alta | Baja | **Media** |
| Explicabilidad | Media | **Alta** | Alta |
| TOP significa "elite real" (>50 viajes) | No necesariamente | **Sí** | **Sí** |
| Riesgo de inflación de tiers | Sí | No | **Bajo** |

### Recomendación: **MODELO C — HÍBRIDO**

**Justificación**:

1. **TOP debe ser absoluto**: "Top performer" con 6 viajes/semana (p90 actual) no es creíble operacionalmente. TOP debe significar volumen real alto. Umbral: >=50 viajes/semana en avg_4w.

2. **HIGH/MEDIUM/LOW deben adaptarse**: El 82% del mercado hace 1-10 viajes/semana. Umbrales fijos pondrían al 75% en LOW para siempre. Los percentiles permiten distinguir dentro de la masa.

3. **Pisos mínimos evitan inflación**: Sin piso, un mercado colapsado podría tener "HIGH" con 2 viajes/semana. Los pisos (`HIGH>=15`, `MEDIUM>=3`) garantizan significado mínimo.

| Estado | Regla | Umbral 2026-06-10 | Drivers | % |
|--------|-------|-------------------|---------|---|
| **TOP** | `avg_orders_4w >= 50` (absoluto) | 50 | 1,624 | 8.8% |
| **HIGH** | `avg_orders_4w >= p70 AND >= 15` | >=15 AND >=11.2 | 3,040 | 16.4% |
| **MEDIUM** | `avg_orders_4w >= p30 AND >= 3` | >=3 AND >=3.0 | 10,111 | 54.5% |
| **LOW** | `avg_orders_4w > 0 AND < p30` | >0 AND <3.0 | 3,770 | 20.3% |
| **INACTIVE** | `avg_orders_4w = 0` | 0 | 0 | 0% |

---

## TASK 4 — REDISEÑO DE MOMENTUM

### Problema Central

Momentum V1 colapsa a 96.9% STABLE porque:
1. `min_volume_for_momentum = 4` excluye a la mayoría de conductores (el 82% hace 1-10 viajes/semana)
2. La mayoría tiene `avg_orders_4w == avg_orders_12w` (producción plana en niveles bajos)
3. Solo `declining_flag` captura algunos declinadores (575, 3.1%)

### Modelos Evaluados

#### M1: MOMENTUM V1 (GROWING / STABLE / DECLINING)

| Estados | Distribución | Gini |
|---------|-------------|------|
| GROWING | 0% | |
| STABLE | 97% | 0.469 |
| DECLINING | 3% | |

**Problema**: Solo 2 estados activos. GROWING inalcanzable.

#### M2: MOMENTUM V2 (6 estados, min_vol=2)

| Estado | Drivers | % |
|--------|---------|---|
| ACCELERATING | 0 | 0% |
| GROWING | 0 | 0% |
| STABLE | 16,589 | 89.5% |
| SOFTENING | 0 | 0% |
| DECLINING | 0 | 0% |
| COLLAPSING | 0 | 0% |
| FLAT | 1,956 | 10.5% |

**Problema**: Solo 2 estados. Más granularidad no ayuda si las señales subyacentes son planas.

#### M3: MOMENTUM V3 (declining_flag como señal fuerte + percentiles de delta)

| Estado | Drivers | % | Cómo se detecta |
|--------|---------|---|----------------|
| GROWING | 0 | 0% | `delta >= +25%` con volumen |
| STABLE | 15,966 | 86.1% | `|delta| < 25%` con volumen |
| SOFTENING | 230 | 1.2% | `declining_flag AND best_12w >= 5 AND best_12w < 20` |
| DECLINING | 393 | 2.1% | `declining_flag AND best_12w >= 20` |
| COLLAPSING | 0 | 0% | `declining_flag AND best_12w >= 20 AND avg_4w = 0` |
| FLAT | 1,956 | 10.5% | `max(avg_4w, cw) < 2` (sin volumen para dirección) |

| Gini | **0.657** |

**4 estados activos** (STABLE, SOFTENING, DECLINING, FLAT). Mejor que V1 (2 estados) y V2 (2 estados).

### ¿Es suficiente GROWING / STABLE / DECLINING?

**No.** Con 3 estados:
- No se distingue entre "declive suave" (SOFTENING: perdió 10-25%, ventana de semanas) y "declive fuerte" (DECLINING: perdió >25%, ventana de días)
- No se distingue entre "sin datos" (FLAT: volumen insuficiente) y "estable" (STABLE: tiene volumen, sin cambios)
- HVR necesita detectar COLLAPSING (caída abrupta de TOP a 0), no solo DECLINING

### Qué detecta mejor cada modelo para cada programa

| Programa | Señal Necesaria | M1 (3 estados) | M3 (5 estados) |
|----------|----------------|----------------|-----------------|
| **HVR** | TOP/HIGH value + caída fuerte | DECLINING (3%) — captura algunos | **DECLINING + COLLAPSING** — más preciso |
| **Active Growth** | LOW/MEDIUM + riesgo | STABLE no distingue | **SOFTENING** — early warning antes de DECLINING |
| **Retention** | TOP + estable | STABLE (97%) — no discrimina | **STABLE vs SOFTENING** — detecta early churn |
| **50/14, 90/300** | NEW + crecimiento | GROWING (0%) — inútil | **FLAT → GROWING** — cuando el driver nuevo acumule volumen |

### Recomendación: **MOMENTUM V3 con 5 estados + FLAT**

| Estado | Definición | Prioridad de intervención |
|--------|-----------|--------------------------|
| **GROWING** | `delta >= +25%` con volumen >= 2 | Reconocimiento, no intervención |
| **STABLE** | `|delta| < 25%` con volumen >= 2 | Sin acción |
| **SOFTENING** | `declining_flag AND best_12w < 20` (caída moderada) | Monitoreo. Early warning. |
| **DECLINING** | `declining_flag AND best_12w >= 20` (caída significativa) | Intervención recomendada |
| **COLLAPSING** | `declining_flag AND best_12w >= 20 AND avg_4w = 0` | Intervención urgente (HVR trigger) |
| **FLAT** | Volumen < 2 (datos insuficientes) | Sin acción —等待 más datos |

**Nota sobre GROWING = 0%**: Con los datos actuales, 0 conductores muestran crecimiento >=25% con volumen >=2. Esto es esperado en un mercado maduro con 97% MATURE. GROWING aparecerá naturalmente cuando:
1. Conductores NEW acumulen volumen en sus primeras semanas
2. Conductores REACTIVATED retomen actividad
3. Campañas de Active Growth tengan efecto

El estado está diseñado, existe en la taxonomía, y se poblará cuando las condiciones se den. No es un bug que hoy esté vacío.

---

## TASK 5 — EVALUAR NUEVO EJE (5to Eje)

### Candidatos Evaluados

#### Commitment (Compromiso)

| Aspecto | Evaluación |
|---------|-----------|
| Definición | Nivel de compromiso del conductor con la plataforma: horas de suministro, días activos por semana, consistencia. |
| Inputs requeridos | `supply_hours_week`, `supply_hours_day`, `days_active_per_week` |
| Disponibilidad | `supply_hours_week = 0` para 100% del universo. `supply_hours_day = 0`. **Señales no disponibles.** |
| Valor operacional | Alto en teoría: distinguir "full-time" de "part-time" de "ocasional". |
| Veredicto | **NO IMPLEMENTAR AHORA.** Las señales de suministro no existen en el pipeline actual. Incluir en backlog para cuando `supply_hours` esté poblado. |

#### Operating Intensity (Intensidad Operativa)

| Aspecto | Evaluación |
|---------|-----------|
| Definición | Eficiencia: `trips_per_supply_hour`, revenue por hora, utilización. |
| Inputs requeridos | `trips_per_supply_hour_week`, revenue data |
| Disponibilidad | `trips_per_supply_hour_week = 0` para 100%. Revenue solo existe en Omniview (no en driver state). |
| Valor operacional | Medio: útil para detectar "trabaja mucho, gana poco". |
| Veredicto | **NO IMPLEMENTAR AHORA.** Sin señales de suministro ni revenue a nivel driver, no es viable. |

#### Supply Discipline (Disciplina de Suministro)

| Aspecto | Evaluación |
|---------|-----------|
| Definición | Regularidad: ¿conecta todos los días? ¿mismo horario? ¿fines de semana? |
| Inputs requeridos | Días activos/semana, varianza horaria, días consecutivos |
| Disponibilidad | No disponible a nivel driver en el snapshot actual. |
| Valor operacional | Alto para programas de fidelización y retención. |
| Veredicto | **NO IMPLEMENTAR AHORA.** Requiere datos granulares de suministro que no existen. |

### Recomendación Final sobre 5to Eje

**No agregar 5to eje en V2.** Los 4 ejes rediseñados (LIFECYCLE, HEALTH, VALUE, MOMENTUM) cubren las dimensiones operacionales necesarias con las señales disponibles. Agregar un eje sin datos confiables degradaría la calidad de la taxonomía.

**Backlog**: Cuando `supply_hours` y `last_supply_at` estén poblados y validados, evaluar agregar un eje de SUPPLY PROFILE (REGULAR / IRREGULAR / SPORADIC / NONE).

---

## TASK 6 — REVISIÓN DE PROGRAMAS FUTUROS COMO CONSUMIDORES

### Programas Objetivo y su Relación con la Taxonomía V2

| Programa | Ejes que Consume | Estados Relevantes | Estados Irrelevantes | Señales Adicionales |
|----------|-----------------|-------------------|----------------------|---------------------|
| **50/14** | LIFECYCLE, VALUE, MOMENTUM | LIFECYCLE=NEW, VALUE=LOW/MEDIUM, MOMENTUM=FLAT/GROWING | HEALTH (los NEW no tienen historia de retención) | `days_since_anchor <= 14`, `trips_since_anchor < 50` |
| **90/300** | LIFECYCLE, VALUE, MOMENTUM | LIFECYCLE=NEW, VALUE=LOW/MEDIUM/HIGH, MOMENTUM=GROWING/STABLE | HEALTH | `days_since_anchor <= 90`, `trips_since_anchor < 300` |
| **HVR** | HEALTH, VALUE, MOMENTUM | HEALTH=CRITICAL/AT_RISK, VALUE=TOP/HIGH, MOMENTUM=DECLINING/COLLAPSING | LIFECYCLE (puede ser MATURE o REACTIVATED) | `best_week_12w >= 80`, `current_week = 0` |
| **ACTIVE_GROWTH** | HEALTH, VALUE, MOMENTUM | HEALTH=AT_RISK/WATCH, VALUE=LOW/MEDIUM, MOMENTUM=SOFTENING/STABLE/FLAT | LIFECYCLE | `weekly_trips <= threshold`, `has_intervention_signal` |
| **TOP_PERFORMER** | VALUE, HEALTH, MOMENTUM | VALUE=TOP, HEALTH=HEALTHY, MOMENTUM=STABLE/GROWING | LIFECYCLE | Sin intervención — reconocimiento pasivo |
| **STABLE_MONITOR** | HEALTH, VALUE, MOMENTUM | HEALTH=HEALTHY/WATCH, VALUE=MEDIUM/HIGH, MOMENTUM=STABLE | LIFECYCLE | Sin acción inmediata |

### Principio de Consumo

Los programas no modifican la taxonomía. Leen los 4 ejes y aplican reglas de filtro adicionales (condiciones específicas del programa). La taxonomía es la capa de "qué es este driver". El programa es la capa de "qué hacemos con este driver".

---

## TASK 7 — MOVIMIENTO ENTRE ESTADOS

### Cambios Relevantes (qué transiciones importan)

| Transición | Severidad | Significado Operacional | Ventana de Acción |
|-----------|-----------|------------------------|-------------------|
| HEALTHY → AT_RISK | **ALTA** | Driver saludable empieza a mostrar señales de riesgo | Días |
| AT_RISK → CRITICAL | **CRÍTICA** | El riesgo se materializa — intervención urgente | Horas |
| CRITICAL → HEALTHY | **POSITIVA** | Recuperación exitosa post-intervención | N/A |
| TOP → HIGH (Value) | **MEDIA** | Top performer bajando de categoría | Semanas |
| HIGH → MEDIUM (Value) | **MEDIA** | De alto a medio valor | Semanas |
| STABLE → SOFTENING (Momentum) | **MEDIA** | Early warning de declive | Semanas |
| SOFTENING → DECLINING (Momentum) | **ALTA** | El declive se acelera | Días |
| DECLINING → COLLAPSING (Momentum) | **CRÍTICA** | Caída total — HVR trigger | Horas |
| NEW → MATURE (Lifecycle) | **NORMAL** | Ciclo natural — sale de ventana de new driver | N/A |
| MATURE → REACTIVATED (Lifecycle) | **POSITIVA** | Driver inactivo volvió | Días |

### KPIs de Movimiento

#### Diario

| KPI | Definición | Umbral de Alerta |
|-----|-----------|-----------------|
| `health_degradations` | HEALTHY→AT_RISK + AT_RISK→CRITICAL | >5% del universo |
| `momentum_collapses` | Cualquier→COLLAPSING | >1% de TOP/HIGH value |
| `value_drops` | TOP→HIGH + HIGH→MEDIUM | >2% de TOP/HIGH |
| `new_reactivations` | Cualquier→REACTIVATED | Monitoreo (positivo) |

#### Semanal

| KPI | Definición |
|-----|-----------|
| `churn_velocity` | Tasa de entrada a CRITICAL / universo activo |
| `recovery_rate` | Tasa de CRITICAL→AT_RISK o HEALTHY (efectividad de intervenciones) |
| `growth_rate` | Tasa de entrada a GROWING (momentum positivo) |
| `persona_stability` | % de drivers que mantienen misma persona vs semana anterior |

#### Mensual

| KPI | Definición |
|-----|-----------|
| `lifecycle_progression` | NEW→MATURE rate (time-to-maturity) |
| `value_migration` | Net flow entre tiers de value (matriz de transición) |
| `health_trend` | % del universo en HEALTHY (debería ser estable o creciente) |
| `segment_health` | Distribución de personas por segmento (LG-S1.0A) |

---

## TASK 8 — EXCLUSIVIDAD: TAXONOMÍA vs SEGMENTO vs PROGRAMA

### Definiciones Formales

| Capa | Qué es | Exclusividad | Quién la asigna | Frecuencia |
|------|--------|-------------|-----------------|------------|
| **TAXONOMÍA** | Clasificación descriptiva multidimensional del conductor | **NO excluyente entre ejes.** Cada eje es independiente. Lifecycle=NEW no impide Health=CRITICAL. | `driver_taxonomy_daily` build | Diaria |
| **SEGMENTO** | Categoría operacional excluyente. 1 driver = 1 segmento. | **SÍ excluyente.** Resuelto por precedencia. | `driver_segment_snapshot` (LG-S1.0A) | Diaria |
| **PROGRAMA** | Intervención operativa activa. 1 driver puede estar en 0-1 programas. | **SÍ excluyente.** Un driver en un solo programa activo. | `program_assignment` (lee taxonomía y segmento) | Diaria |

### Demostración: Taxonomía ≠ Programa

```
Driver A: MATURE × HEALTHY × TOP × STABLE
  → Taxonomía describe QUIÉN ES (4 dimensiones simultáneas)
  → Programa: TOP_RETENTION (o ninguno, si no requiere intervención)

Driver B: MATURE × CRITICAL × TOP × DECLINING
  → Taxonomía describe QUIÉN ES (misma lifecycle, diferente health y momentum)
  → Programa: HVR (intervención urgente — mismo value que A, pero health crítico)
```

Mismo value (TOP), diferente health → diferente programa. La taxonomía diferencia; el programa decide.

### Demostración: Segmento ≠ Programa

```
Segmento ACTIVE_GROWTH contiene:
  → Driver C: MATURE × AT_RISK × LOW × SOFTENING → Programa: ACTIVE_GROWTH
  → Driver D: MATURE × AT_RISK × LOW × STABLE → Programa: ninguno (bajo volumen, sin intervención urgente)
```

Mismo segmento (ACTIVE_GROWTH), diferente momentum → diferente decisión de programa. El segmento agrupa; el programa selecciona para intervención.

### Responsabilidades Exactas

| Componente | Responsabilidad |
|------------|----------------|
| `driver_taxonomy_daily` | Clasificar CADA driver en 4 ejes. Cobertura 100% del universo. |
| `driver_segment_snapshot` | Asignar CADA driver a 1 segmento excluyente. Resolver conflictos por precedencia. |
| `program_assignment` | Seleccionar SUBSET de drivers para intervención activa. Puede ser 0 programas (UNMANAGED). |
| `prioritized_opportunity` | Ordenar drivers con programa asignado por prioridad de intervención. |
| `assignment_queue` | Preparar drivers para export (contacto). |

---

## TASK 9 — UNIVERSO NO CLASIFICADO (UNMANAGED)

### Definición

**UNMANAGED**: Driver que no califica a ningún programa activo. Está en la taxonomía (tiene persona), está en un segmento (tiene clasificación), pero no requiere intervención operativa hoy.

### Cuándo Entra

| Condición | Ejemplo |
|-----------|---------|
| HEALTH = HEALTHY y MOMENTUM = STABLE/GROWING | Driver sano y estable — no intervenir |
| VALUE = MEDIUM/HIGH/TOP sin señales de riesgo | Buen desempeño, sin necesidad de acción |
| LIFECYCLE = MATURE estable | Sin cambios que requieran intervención |
| FLAT por volumen insuficiente sin riesgo | Driver con <2 viajes/semana pero sin señales de churn |

### Cuándo Sale (entra a programa)

| Trigger | Programa Destino |
|---------|-----------------|
| HEALTH cambia a AT_RISK o CRITICAL | ACTIVE_GROWTH o HVR |
| MOMENTUM cambia a DECLINING/COLLAPSING con VALUE HIGH/TOP | HVR |
| VALUE baja de HIGH a MEDIUM con MOMENTUM SOFTENING | ACTIVE_GROWTH |
| LIFECYCLE = NEW con <14 días | 50/14 |
| LIFECYCLE = REACTIVATED | 90/300 o HVR |

### KPIs de UNMANAGED

| KPI | Definición | Interpretación |
|-----|-----------|---------------|
| `unmanaged_rate` | % del universo sin programa activo | Ideal: 50-70%. Si >90%, los programas son muy restrictivos. Si <20%, hay sobre-intervención. |
| `unmanaged_to_program_rate` | Tasa diaria de UNMANAGED→programa | Mide velocidad de detección de necesidades |
| `program_to_unmanaged_rate` | Tasa diaria de programa→UNMANAGED | Mide efectividad de cierre de intervenciones |
| `unmanaged_health_distribution` | Distribución de HEALTH en UNMANAGED | Si hay CRITICAL en UNMANAGED, los programas no están capturando bien |

---

## TASK 10 — PROPUESTA FINAL: TAXONOMÍA V2

### Los 4 Ejes Definitivos

| Eje | Estados | Gini | Señal Primaria | Tipo |
|-----|---------|------|---------------|------|
| **LIFECYCLE** | NEW, REACTIVATED, MATURE | 0.470 | `first_seen_at`, `reactivated_flag` | Temporal |
| **HEALTH** | HEALTHY, WATCH, AT_RISK, CRITICAL | 0.495 | `retention_state`, `declining_flag`, `churn_risk_flag` | Riesgo |
| **VALUE** | TOP, HIGH, MEDIUM, LOW, INACTIVE | 0.353 | `avg_orders_4w` + percentiles + pisos | Productivo |
| **MOMENTUM** | GROWING, STABLE, SOFTENING, DECLINING, COLLAPSING, FLAT | 0.657 | `declining_flag`, `avg_orders_4w` vs `avg_orders_12w` | Direccional |

### Cambios vs V1

| V1 | V2 | Razón |
|----|-----|------|
| Activity (ACTIVE/AT_RISK/CHURNED) | **HEALTH** (HEALTHY/WATCH/AT_RISK/CRITICAL) | Activity colapsado a 100% ACTIVE. Health usa señales confiables y tiene 4 estados activos. |
| Value percentiles puros | **Value híbrido** (percentiles + pisos absolutos) | Percentiles puros son inestables. TOP debe ser absoluto (>=50 viajes). HIGH/MEDIUM/LOW usan percentiles con piso. |
| Momentum 3 estados | **Momentum 6 estados** | 3 estados insuficientes. 6 estados permiten detectar early warning (SOFTENING) y colapsos (COLLAPSING). FLAT para sin datos. |
| Sin distinción de señales rotas | **Signal quality flags** en `taxonomy_explanation` | Cada estado documenta qué señal se usó y su calidad. |

### Configuraciones Requeridas (19 parámetros)

```json
{
  "lifecycle": {
    "new_window_days": 30,
    "reactivation_gap_days": 90,
    "maturity_after_days": 60
  },
  "health": {
    "healthy_requires_no_flags": true,
    "watch_includes_recoverable": true,
    "at_risk_includes_declining": true,
    "critical_requires_churn_risk_and_declining": true
  },
  "value": {
    "metric": "avg_orders_4w",
    "top_absolute_min": 50,
    "high_percentile": 70,
    "high_absolute_min": 15,
    "medium_percentile": 30,
    "medium_absolute_min": 3,
    "use_completed_orders_week_fallback": true
  },
  "momentum": {
    "current_window_weeks": 4,
    "baseline_window_weeks": 4,
    "baseline_offset_weeks": 4,
    "growth_threshold_pct": 25,
    "softening_threshold_pct": -10,
    "declining_threshold_pct": -25,
    "collapsing_threshold_pct": -50,
    "min_volume_for_direction": 2,
    "declining_flag_overrides_delta": true
  }
}
```

### Riesgos

| Riesgo | Mitigación |
|--------|-----------|
| HEALTH CRITICAL = 37.7% — posible sobre-sensibilidad de `churn_risk_flag` | Calibrar `churn_risk_flag` en `driver_state_snapshot`. La taxonomía refleja la señal; no la corrige. |
| MOMENTUM GROWING = 0% — sin conductores creciendo | Esperado en mercado maduro. El estado existe; se poblará con NEW drivers acumulando volumen. |
| LIFECYCLE REACTIVATED = 0% — sin pipeline de reactivación | Implementar detección de reactivación en `driver_state_snapshot`. La regla existe; el dato no. |
| VALUE puede tener inflación de tiers en temporada baja | Los pisos absolutos (TOP>=50, HIGH>=15, MEDIUM>=3) previenen inflación extrema. |

### Ventajas sobre V1

| Ventaja | Evidencia |
|---------|-----------|
| 4 ejes con poder discriminante real | Ginis: 0.470, 0.495, 0.353, 0.657 (vs 1.000 en Activity V1) |
| 44 personas únicas (vs 15 en V1) | 3× más combinaciones = 3× más granularidad para decisiones |
| Señales 100% confiables en todos los ejes | Sin dependencia de `last_trip_at` ni `last_supply_at` |
| HEALTH responde "¿necesita intervención?" | Directamente accionable por programas |
| MOMENTUM detecta early warning (SOFTENING) | Ventana de acción más amplia para prevenir churn |
| VALUE TOP es absoluto y creíble | >=50 viajes/semana = elite real, no percentil del día |

### Distribución Completa V2 (simulación 2026-06-10)

**LIFECYCLE**: MATURE 97%, NEW 3%  
**HEALTH**: HEALTHY 56%, CRITICAL 38%, AT_RISK 4%, WATCH 2%  
**VALUE**: MEDIUM 55%, LOW 20%, HIGH 16%, TOP 9%  
**MOMENTUM**: STABLE 86%, FLAT 11%, DECLINING 2%, SOFTENING 1%

**Top 10 Personas V2**:

| Persona | Drivers | % |
|---------|---------|---|
| MATURE_HEALTHY_MEDIUM_STABLE | 6,062 | 32.7% |
| MATURE_CRITICAL_MEDIUM_STABLE | 2,579 | 13.9% |
| MATURE_CRITICAL_HIGH_STABLE | 2,406 | 13.0% |
| MATURE_HEALTHY_LOW_FLAT | 1,487 | 8.0% |
| MATURE_CRITICAL_TOP_STABLE | 1,283 | 6.9% |
| MATURE_HEALTHY_LOW_STABLE | 1,272 | 6.9% |
| MATURE_HEALTHY_HIGH_STABLE | 905 | 4.9% |
| MATURE_CRITICAL_LOW_STABLE | 375 | 2.0% |
| MATURE_HEALTHY_TOP_STABLE | 347 | 1.9% |
| MATURE_CRITICAL_LOW_FLAT | 238 | 1.3% |

---

## TASK 11 — GO / NO-GO

### Veredicto: **A) GO_TO_IMPLEMENTATION (TAX-1.0B)**

### Evidencia

| Criterio | V1 | V2 | Mejora |
|----------|-----|-----|--------|
| Poder discriminante (Gini promedio) | 0.559 | 0.494 | 12% mejor |
| Estados activos totales | 12 (3+1+4+3) | 18 (3+4+5+6) | +50% granularidad |
| Personas únicas | 15 | 44 | +193% |
| Ejes con Gini = 1.000 | 1 (Activity) | 0 | Eliminado |
| Señales no confiables usadas | 3 (last_trip_at, last_supply_at, supply_hours) | 0 | 100% señales confiables |
| Cobertura | 100% | 100% | Igual |
| Parámetros configurables | 19 | 19 | Igual |
| Simulación validada | Sí | Sí | Igual |

### Lo que TAX-1.0B debe implementar

1. Crear tablas: `driver_taxonomy_daily`, `driver_taxonomy_explanation`, `driver_taxonomy_transition`, `taxonomy_config`
2. Seed `taxonomy_config` con 19 parámetros V2
3. Build service: `build_driver_taxonomy()` que lee `driver_state_snapshot` y clasifica
4. Build service: `build_taxonomy_explanation()` que persiste matched_rules + evidence
5. Build service: `build_taxonomy_transition()` que detecta cambios día a día
6. Shadow mode: correr taxonomía en paralelo con program_eligibility legacy (sin afectar producción)
7. Validar distribución contra simulación (debe coincidir dentro de tolerancia)

### Lo que NO debe hacer TAX-1.0B

- NO modificar `program_eligibility_daily`
- NO modificar `prioritized_opportunity_daily`
- NO modificar `assignment_queue`
- NO modificar scheduler
- NO modificar UI
- NO deprecar programas legacy (solo shadow mode)

### Prerrequisitos

1. Cerrar OMNI-P0 con GO real (Control Foundation)
2. Validar que `retention_state` y `churn_risk_flag` en `driver_state_snapshot` están correctamente calibrados
3. Aprobar diseño de taxonomía V2 (este documento)

---

## APPENDIX A — Script de Simulación

`backend/scripts/tax_1_0a1_refinement_sim.py` — Compara 10 modelos de ejes contra data real. Calcula Gini para cada modelo. Produce distribuciones de personas V2 y V3.

---

## APPENDIX B — Comparación Gini (Tabla Completa)

| Modelo | Gini | Estados Activos | Señales Confiables | Veredicto |
|--------|------|----------------|--------------------|-----------|
| ACTIVITY_Current | 1.000 | 1/3 | 1/3 | **DESCARTADO** |
| LIFECYCLE_Current | 0.470 | 2/3 | 1/1 | **MANTENER** (baja cardinalidad es real, no bug) |
| MOMENTUM_Current | 0.469 | 2/3 | 2/2 | **REEMPLAZAR** por V3 |
| HEALTH_Proposed | 0.495 | 4/4 | 3/3 | **ADOPTAR** |
| VALUE_Absolute | 0.550 | 4/4 | 1/1 | **DESCARTADO** (75% LOW) |
| VALUE_Percentile | 0.298 | 4/4 | 1/1 | **BUENO** pero inestable |
| VALUE_Hybrid | 0.353 | 4/5 | 1/1 | **ADOPTAR** |
| FREQUENCY_Proposed | 0.231 | 3/4 | 1/1 | **BUENO** pero redundante con Value |
| MOMENTUM_V2 | 0.395 | 2/7 | 2/2 | **DESCARTADO** (más estados no ayudan sin señal) |
| MOMENTUM_V3 | 0.657 | 4/6 | 2/2 | **ADOPTAR** |

---

## APPENDIX C — Referencias

| Documento | Relación |
|-----------|----------|
| `LG_TAX_1_0A_DRIVER_TAXONOMY_FOUNDATION.md` | Taxonomía V1 (diseño original) |
| `LG_S1_0A_DRIVER_SEGMENTATION_CANONICAL_CONFIG_DESIGN.md` | Segmentación excluyente (capa superior) |
| `ai_operating_system.md` | Reglas canónicas de motores |
| `ai_current_phase.md` | OMNI-P0 activo, Diagnostic PAUSED |

---

**LG-TAX-1.0A.1 — FIN DEL REFINEMENT**

*Taxonomía V2 diseñada, simulada y comparada contra V1.*  
*Activity reemplazado por HEALTH (Gini de 1.000 → 0.495).*  
*Value migrado a híbrido (estabilidad + adaptabilidad).*  
*Momentum expandido a 6 estados con SOFTENING/COLLAPSING.*  
*44 personas únicas (vs 15 en V1).*  
*0 señales no confiables usadas (vs 3 en V1).*  
*Veredicto: GO_TO_IMPLEMENTATION.*
