
# FASE 2C — RECOVERABILITY INTELLIGENCE
## ARQUITECTURA & SCORING DESIGN

---

## 1. OBJETIVO

Determinar, mediante sistema **determinístico auditado**, si un conductor que muestra deterioro —o que ya churnó— es recuperable, cuánto esfuerzo requeriría, y si justifica intervención operacional (SAC, lealtad, incentivos).

**No construye recomendaciones.** No automatiza acciones. No usa ML. Solo produce un score explicable y un estado de recoverability que alimentará capas futuras.

---

## 2. PROBLEMA OPERACIONAL QUE RESUELVE

### Situación actual

Las capas existentes ya saben:

| Capa | Qué responde |
|------|-------------|
| 2A.1 Lifecycle | ¿Cuántos drivers hay? ¿En qué estado de ciclo de vida están? |
| 2A.2 Benchmarking | ¿Cuánto difieren TOP_PERFORMER de DECLINING/AT_RISK? |
| 2A.3 Pattern Diagnosis | ¿Por qué difieren? ¿Qué patrones operativos los separan? |
| 2B Operational Intelligence | ¿Cómo operan? ¿Qué arquetipo son? ¿Tienen señales pre-churn? |

Pero **nadie responde todavía**:

> **¿Vale la pena intervenir este conductor?**
>
> ¿Va a volver solo? ¿Va a seguir degradándose pase lo que pase? ¿Una llamada del equipo de lealtad cambiaría algo? ¿Estamos gastando esfuerzo en casos perdidos mientras ignoramos conductores recuperables?

### Lo que 2C resuelve

2C traduce las señales diagnósticas acumuladas en **un juicio operacional determinístico** sobre recoverability. Cierra la brecha entre "sabemos que se está yendo" y "sabemos si podemos hacer algo al respecto".

---

## 3. ARQUITECTURA CONCEPTUAL

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FASE 2C — Recoverability Intelligence              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐    ┌──────────────────────────────────┐    │
│  │ CAPAS PRECEDENTES   │    │                                  │    │
│  │                     │    │  RECOVERABILITY SCORING ENGINE    │    │
│  │ 2A.1 Lifecycle ────┼────▶  • Historical Consistency          │    │
│  │ 2A.2 Benchmarking ─┼────▶  • Degradation Velocity            │    │
│  │ 2A.3 Patterns ─────┼────▶  • Recency                         │    │
│  │ 2B Op. Intel. ─────┼────▶  • Archetype Compatibility         │    │
│  │                     │    │  • Efficiency Legacy               │    │
│  └─────────────────────┘    │  • Modifiers & Penalties           │    │
│                              │                                    │    │
│                              │  SCORE: 0 ───────────────── 100    │    │
│                              │    │       │        │        │     │    │
│                              │  NON_REC  HARD   LOW    RECOV   │    │
│                              │           TO_REC  RECOV  HIGHLY  │    │
│                              └────────────┬─────────────────────┘    │
│                                           │                         │
│  ┌────────────────────────────────────────┼──────────────────────┐  │
│  │ EXPLAINABILITY LAYER                  │                       │  │
│  │  • Score decomposition por dimensión   │                       │  │
│  │  • Trace: qué señal → qué puntaje     │                       │  │
│  │  • Razón operacional del estado       │                       │  │
│  │  • Limitaciones y caveats             │                       │  │
│  └────────────────────────────────────────┼──────────────────────┘  │
│                                           │                         │
│  ┌────────────────────────────────────────┼──────────────────────┐  │
│  │ OUTPUTS                                │                       │  │
│  │  • recoverability_state               │                       │  │
│  │  • recoverability_score (0-100)       │                       │  │
│  │  • score_breakdown (5 componentes)    │                       │  │
│  │  • explainability_text               │                       │  │
│  │  • intervention_urgency              │                       │  │
│  │  • risk_flags                        │                       │  │
│  └───────────────────────────────────────┴───────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Principio rector

> **Determinístico, trazable, sin caja negra.**

Cada punto del score tiene una razón explícita. No hay pesos aprendidos. No hay embeddings. No hay random forest. Si un operador pregunta "¿por qué este conductor es HIGHLY_RECOVERABLE?", la respuesta es una lista de hechos, no una predicción opaca.

---

## 4. RECOVERABILITY STATES

### 4.1 Catálogo de Estados

Se definen **5 estados**, ordenados de mayor a menor probabilidad de recuperación operacional:

| # | Estado | Rango Score | Significado operacional |
|---|--------|------------|------------------------|
| 1 | **HIGHLY_RECOVERABLE** | 80–100 | Recuperación altamente probable con intervención ligera o incluso espontánea. |
| 2 | **RECOVERABLE** | 60–79 | Buen candidato para intervención estándar. Requiere acción pero con expectativa razonable de retorno. |
| 3 | **LOW_RECOVERABLE** | 40–59 | Señales mixtas. Recuperación incierta. Intervención posible pero con riesgo de esfuerzo desperdiciado. |
| 4 | **HARD_TO_RECOVER** | 20–39 | Degradación severa o prolongada. Baja probabilidad. Solo justificable si el conductor es estratégico. |
| 5 | **NON_RECOVERABLE** | 0–19 | Churn consolidado sin señales de retorno. Intervención probablemente fútil. |

### 4.2 Justificación del Diseño

**¿Por qué 5 estados y no 3 o 7?**

- **3 estados** (p.ej. RECOVERABLE, UNCERTAIN, NON_RECOVERABLE): demasiado grueso. No permite granularidad suficiente para priorización SAC.
- **7 estados**: demasiado fino para la precisión de las señales actuales. Las métricas disponibles no soportan 7 niveles de discriminación.
- **5 estados**: equilibrio. Suficiente granularidad para diferenciar estrategias de intervención sin granularidad falsa.

**¿Por qué estos nombres?**

Los nombres reflejan la decisión operacional que habilitan, no una clasificación académica:

- `HIGHLY_RECOVERABLE` → "Intervenir ya, con bajo costo"
- `RECOVERABLE` → "Intervenir con esfuerzo estándar"
- `LOW_RECOVERABLE` → "Evaluar caso por caso, posible test A/B"
- `HARD_TO_RECOVER` → "Solo si es estratégico; probablemente no"
- `NON_RECOVERABLE` → "Excluir de campañas de recuperación"

### 4.3 Significado Operacional por Estado

#### HIGHLY_RECOVERABLE (80-100)

| Atributo | Valor |
|----------|-------|
| **Significado** | Conductor con deterioro leve o reciente. Historial de consistencia. Probablemente volverá con un empujón mínimo o incluso solo. |
| **Perfil típico** | Ex-TOP_PERFORMER o STABLE con caída reciente moderada. Activo en últimos 14 días. FULLTIMER o CONSISTENT_OPERATOR. |
| **Riesgo de no intervenir** | Medio: podría degradarse más si se ignora. |
| **Riesgo de intervenir** | Bajo: probablemente agradecerá el contacto. |
| **Horizonte de recuperación** | 7–21 días. |
| **Uso futuro** | Prioridad 1 en cola SAC. Contacto ligero (notificación, incentivo simbólico). |

#### RECOVERABLE (60-79)

| Atributo | Valor |
|----------|-------|
| **Significado** | Conductor con degradación moderada pero perfil operativo que históricamente se asocia con retorno. Sin señales de abandono estructural. |
| **Perfil típico** | STABLE o DECLINING con señales EARLY_WARNING. Activo en últimos 30 días. PART_TIMER o WEEKEND_SPECIALIST. |
| **Riesgo de no intervenir** | Alto: probablemente seguirá decayendo sin acción. |
| **Riesgo de intervenir** | Moderado: requiere esfuerzo pero con expectativa razonable. |
| **Horizonte de recuperación** | 14–30 días. |
| **Uso futuro** | Prioridad 2 en cola SAC. Intervención estándar (llamada, oferta de lealtad). |

#### LOW_RECOVERABLE (40-59)

| Atributo | Valor |
|----------|-------|
| **Significado** | Señales contradictorias: algunas positivas (historial decente), otras negativas (degradación significativa, inactividad prolongada). |
| **Perfil típico** | DECLINING o AT_RISK con señales MODERATE. Activo hace 30-45 días. INCONSISTENT_OPERATOR o HIGH_VOLUME_LOW_EFFICIENCY. |
| **Riesgo de no intervenir** | Moderado: podría perderse, pero no es seguro. |
| **Riesgo de intervenir** | Alto: esfuerzo significativo con resultado incierto. |
| **Horizonte de recuperación** | 21–60 días. |
| **Uso futuro** | Prioridad 3. Solo intervenir si hay capacidad sobrante o si el conductor es estratégico (zona crítica, LOB clave). |

#### HARD_TO_RECOVER (20-39)

| Atributo | Valor |
|----------|-------|
| **Significado** | Degradación severa multi-dimensional. Larga inactividad o patrón de inconsistencia crónico. Baja probabilidad de respuesta. |
| **Perfil típico** | AT_RISK o DORMANT con señales STRONG. Inactivo 30-60 días. BURNOUT_PATTERN o INCONSISTENT_OPERATOR. |
| **Riesgo de no intervenir** | Bajo: probablemente ya estaba perdido. |
| **Riesgo de intervenir** | Muy alto: probablemente esfuerzo desperdiciado. |
| **Horizonte de recuperación** | 30–90 días (si acaso). |
| **Uso futuro** | Normalmente no intervenir. Escalar solo si es estratégico (high-value driver con historial excepcional). |

#### NON_RECOVERABLE (0-19)

| Atributo | Valor |
|----------|-------|
| **Significado** | Churn consolidado. Más de 60 días sin actividad. Sin historial de retorno previo. Sin señales de engagement residual. |
| **Perfil típico** | CHURNED con >60 días inactivo. Nunca fue consistente. Sin picos históricos destacables. |
| **Riesgo de no intervenir** | Nulo: ya es una pérdida consumada. |
| **Riesgo de intervenir** | Fútil: desperdicio garantizado. |
| **Horizonte de recuperación** | N/A. |
| **Uso futuro** | Excluir de campañas. Solo reconsiderar si aparecen señales externas de re-engagement. |

---

## 5. INPUT DIMENSIONS

### 5.1 Dimensiones Disponibles Hoy (Fase 2A + 2B)

Cada dimensión lista su fuente exacta en las capas existentes.

| # | Dimensión | Fuente | Tipo | Qué mide para recoverability |
|---|-----------|--------|------|------------------------------|
| **D1** | **Historical Consistency** | 2A.2 `consistency_score = active_days / period_days` | Númerico 0.0–1.0 | Predictor #1 de retorno: conductores consistentes vuelven; erráticos no. |
| **D2** | **Recent Degradation Velocity** | 2B `pre-churn signals`: trips_change_pct, active_days_change_pct, revenue_change_pct | Señal + severidad | Velocidad de caída. Degradación lenta = recuperable. Caída abrupta = pérdida estructural. |
| **D3** | **Recency** | 2A.2 `days_since_last_activity` desde `activity_date` en fact table | Días | Distancia temporal al último viaje. <14d = caliente. >60d = frío. |
| **D4** | **Archetype** | 2B `get_operational_archetypes()` | Categórico (9 valores) | Perfil operativo. FULLTIMER/CONSISTENT más recuperables que BURNOUT/INCONSISTENT. |
| **D5** | **Efficiency Legacy** | 2B `revenue_per_hour`, `revenue_per_trip`, `trips_per_hour` | Numérico | Valor histórico del conductor para la plataforma. Alta eficiencia = vale la pena recuperar. |
| **D6** | **Churn Duration** | 2A.1/2A.2 `days_since_last_activity → DORMANT (14-29d) / CHURNED (30+d)` | Días | Tiempo total fuera. Umbral psicológico: >30d las probabilidades caen drásticamente. |
| **D7** | **Volatility** | 2A.2 comparación multi-período: `trips stddev / mean` | Numérico | Inconsistencia histórica. Alta volatilidad = baja predictibilidad = difícil recuperar. |
| **D8** | **Session Quality History** | 2B `session_fact`: avg session_trips, session_revenue, session_duration | Numérico | Profundidad de engagement. Sesiones largas y productivas = conductor comprometido. |
| **D9** | **Weekend / Weekday Dependency** | 2B `weekend_share`, `peak_hour_share` | Porcentaje 0–100 | Balance operativo. Especialistas extremos (90%+ weekend) más vulnerables a shocks de demanda. |
| **D10** | **Idle Deterioration** | 2B `session_fact`: idle_ratio | Numérico 0.0–1.0 | Señal de fatiga. Idle creciente = conductor desmotivado, posible abandono estructural. |
| **D11** | **Revenue/Hour Deterioration** | 2B `rev_per_hour_change` de pre-churn signals | Porcentaje | Caída de eficiencia. Puede indicar cambio de zona, pérdida de habilidad, o desmotivación. |
| **D12** | **Historical Peak** | 2A.2 clasificación previa: fue TOP_PERFORMER / STABLE / DECLINING | Categórico | Demostró capacidad. Un ex-TOP_PERFORMER en declive es mucho más recuperable que alguien que nunca rindió. |

### 5.2 Señales Compuestas Derivables Hoy

Estas no existen como columnas pero se pueden calcular combinando capas existentes:

| # | Señal compuesta | Cálculo | Interpretación |
|---|----------------|---------|----------------|
| **C1** | **Deterioration Momentum** | trips_change_pct × active_days_change_pct (signo) | Si ambas caen → momento negativo compuesto. |
| **C2** | **Engagement Depth Ratio** | session_trips / active_days | Cuando trabaja, ¿trabaja intensamente? |
| **C3** | **Recovery Trajectory Match** | ¿El patrón de caída coincide con patrones de drivers que luego volvieron? | Requiere poblaciones de referencia de la capa 2A.3. |

### 5.3 Dimensiones NO Disponibles Hoy (Dependencia Futura)

| # | Dimensión | Qué aportaría | Qué falta | Backlog |
|---|-----------|--------------|-----------|---------|
| **F1** | **Prior Reactivation Success** | ¿Este conductor ya churnó y volvió antes? Predictor fortísimo de recoverability. | Tracking de REACTIVATED en 2A.2 (backlog existente). | 2A.2 backlog item: "Detección de REACTIVATED (post-churn)". |
| **F2** | **Incentive Responsiveness** | ¿Respondió históricamente a bonos, garantías, o campañas? | Sin datos de bonus/boost en el sistema. | 2B backlog: "Arquetipo BONUS_DEPENDENT". |
| **F3** | **Multi-Period Trend Lines** | Tendencia de largo plazo (3+ períodos), no solo primera vs segunda mitad. | 2B pre-churn solo compara 2 mitades. | 2B backlog: "Trend lines multi-período para señales pre-churn". |
| **F4** | **Seasonality Adjustment** | ¿El conductor siempre baja en esta temporada? | Sin modelo de estacionalidad. | 2B backlog: "Seasonality-adjusted archetypes". |
| **F5** | **Zone/Market Health** | ¿El mercado local tiene demanda? ¿O el conductor se fue porque no hay viajes? | Zone behavior solo da actividad por park, no demanda de mercado. | Fase futura: Market Intelligence. |
| **F6** | **Archetype Transition Matrix** | ¿De qué arquetipo viene y hacia cuál va? Trayectoria entre arquetipos. | 2B asigna arquetipo en snapshot. | 2B backlog: "Matriz de transición entre arquetipos". |
| **F7** | **Online Hours / Acceptance Rate** | ¿Está conectado pero rechazando? vs ¿ni siquiera se conecta? | Columnas no existen en los datos. | Dependencia externa: ingesta de datos de supply. |
| **F8** | **Driver Tenure** | Antigüedad total en la plataforma. Conductores antiguos pueden tener más lealtad residual. | No hay columna de fecha de alta/onboarding en los facts actuales. | Requiere datos de fleet/onboarding. |

---

## 6. DETERMINISTIC SCORING MODEL

### 6.1 Fórmula General

```
RecoverabilityScore = Σ (ComponentScore_i × Weight_i) + Modifiers
```

Rango: **0–100**

Donde:
- `ComponentScore_i` ∈ [0, 100] normalizado
- `Weight_i` ∈ [0, 1] tal que Σ weights = 1.0
- `Modifiers` ∈ [-10, +10] ajustes puntuales

### 6.2 Componentes y Pesos

| # | Componente | Peso | Rango bruto | Justificación del peso |
|---|-----------|------|------------|------------------------|
| **C1** | Historical Consistency | 25% | 0–100 | Predictor más fuerte de comportamiento futuro. La consistencia pasada es el mejor predictor de retorno. Un conductor que siempre fue consistente y decayó recientemente tiene alta probabilidad de recuperación. |
| **C2** | Degradation Severity | 25% | 0–100 | Velocidad y profundidad de la caída. Una caída lenta y reciente permite intervención. Una caída abrupta y profunda sugiere evento externo (cambio de empleo, mudanza). |
| **C3** | Recency & Churn Duration | 20% | 0–100 | Factor temporal crítico. Cada día sin actividad reduce la probabilidad de retorno. La curva no es lineal: los primeros 14 días son una meseta alta, 14-30 caída acelerada, >30 colapso. |
| **C4** | Archetype Compatibility | 15% | 0–100 | El perfil operativo determina la relación con la plataforma. FULLTIMER depende de Yego para su ingreso principal → más recuperable. WEEKEND_SPECIALIST tiene Yego como ingreso complementario → menos urgente para él volver. |
| **C5** | Efficiency Legacy | 10% | 0–100 | Mide el valor del conductor para la plataforma. No es predictivo de recuperación per se, pero es esencial para priorización: entre dos conductores igualmente recuperables, priorizar al de mayor valor histórico. |
| **C6** | Modifiers | ±10 pts | -10 a +10 | Ajustes por señales específicas no capturadas en los componentes principales. |

### 6.3 Normalización por Componente

#### C1 — Historical Consistency (Peso: 25%)

**Fuente:** `consistency_score` de 2A.2 = `active_days / period_days`

| consistency_score | Puntos C1 |
|-------------------|---|
| ≥ 0.85 | 100 |
| ≥ 0.70 | 80 |
| ≥ 0.55 | 60 |
| ≥ 0.40 | 40 |
| ≥ 0.25 | 20 |
| < 0.25 | 0 |

**Justificación:** La diferencia entre 0.85 y 0.70 no es trivial: un conductor con 85% de días activos es un FULLTIMER comprometido; uno con 70% ya muestra gaps. La escala refleja esta no-linealidad.

#### C2 — Degradation Severity (Peso: 25%)

**Fuente:** `pre-churn signals` de 2B. Se considera la señal más severa detectada.

| Señal más severa | Puntos C2 |
|-----------------|---|
| Sin señales de degradación | 100 |
| EARLY_WARNING (1 señal) | 80 |
| EARLY_WARNING (2+ señales) | 65 |
| MODERATE (1 señal) | 50 |
| MODERATE (2+ señales) | 35 |
| STRONG (1 señal) | 20 |
| STRONG (2+ señales o churn detectado) | 0 |

**Regla de severidad compuesta:** Si hay múltiples señales, se toma la más severa + penalización por acumulación (-15 por cada señal adicional en el mismo nivel, hasta el piso de ese nivel).

#### C3 — Recency & Churn Duration (Peso: 20%)

**Fuente:** `days_since_last_activity` de la fact table de 2A.2.

| Días desde último viaje | Puntos C3 | Justificación |
|------------------------|-----------|---------------|
| 0–7 | 100 | Activo esta semana. Caliente. |
| 8–14 | 85 | Activo recientemente. Ventana óptima de intervención. |
| 15–21 | 65 | Borde de la zona DORMANT. Urgente. |
| 22–30 | 45 | DORMANT establecido. Todavía alcanzable. |
| 31–45 | 25 | CHURNED reciente. Probabilidad baja. |
| 46–60 | 10 | CHURNED consolidado. Muy baja probabilidad. |
| 61–90 | 5 | CHURNED profundo. Casi nula. |
| > 90 | 0 | CHURNED irreversible por esta vía. |

**Justificación de la curva no lineal:** Datos operacionales de plataformas de ridesharing muestran que la probabilidad de retorno espontáneo cae del ~60% en la primera semana al ~15% después de 30 días, y al <3% después de 90 días.

#### C4 — Archetype Compatibility (Peso: 15%)

**Fuente:** `get_operational_archetypes()` de 2B.

Mapeo de arquetipos a puntaje de recoverability:

| Archetype | Puntos C4 | Justificación |
|-----------|-----------|---------------|
| FULLTIMER | 100 | Yego es su ingreso principal. Alta motivación para volver. |
| CONSISTENT_OPERATOR | 90 | Patrón estable. Si decayó, probablemente es circunstancial. |
| HIGH_EFFICIENCY | 85 | Alto valor. Degradación puede ser por fatiga temporal. |
| PART_TIMER | 65 | Ingreso complementario. Menos dependencia, pero aún compromiso. |
| WEEKEND_SPECIALIST | 55 | Nicho específico. Vulnerable a cambios de rutina personal. |
| PEAK_HOUR_SPECIALIST | 55 | Similar a weekend: nicho vulnerable. |
| HIGH_VOLUME_LOW_EFFICIENCY | 40 | Trabaja mucho pero gana poco. Puede estar buscando alternativas. |
| INCONSISTENT_OPERATOR | 25 | Nunca fue consistente. Su ausencia puede ser su estado natural. |
| BURNOUT_PATTERN | 15 | Señal de agotamiento. Forzar recuperación puede empeorar la situación. |

**Regla para múltiples arquetipos:** Un conductor puede pertenecer a varios arquetipos. Se toma el **promedio ponderado** de los arquetipos asignados. Ejemplo: FULLTIMER (100) + HIGH_VOLUME_LOW_EFFICIENCY (40) → 70.

#### C5 — Efficiency Legacy (Peso: 10%)

**Fuente:** `revenue_per_hour` de 2B efficiency endpoint.

| Percentil de revenue/hour | Puntos C5 |
|--------------------------|-----------|
| > p75 | 100 |
| p50–p75 | 70 |
| p25–p50 | 40 |
| < p25 | 10 |
| Sin datos | 0 (N/A) |

**Justificación:** No se usa revenue absoluto (favorecería a FULLTIMERs). Se usa eficiencia por hora para medir productividad real independientemente del volumen.

#### C6 — Modifiers (±10 puntos)

Ajustes determinísticos por señales adicionales:

| Modifier | Condición | Puntos |
|----------|-----------|--------|
| **Prior TOP_PERFORMER** | Clasificado TOP_PERFORMER en período anterior (2A.2) | **+5** |
| **Prior STABLE** | Clasificado STABLE en período anterior | **+3** |
| **Prior DECLINING** | Ya estaba DECLINING en período anterior | **−5** |
| **Prior AT_RISK** | Ya estaba AT_RISK en período anterior | **−8** |
| **High Idle Deterioration** | idle_ratio > 0.5 en sesiones recientes (2B) | **−3** |
| **Session Quality Decline** | session_trips cayó >30% vs período anterior | **−3** |
| **Balanced Schedule** | 0.3 < weekend_share < 0.7 y 0.3 < peak_hour_share < 0.7 | **+2** |
| **Extreme Specialist** | weekend_share > 0.9 o peak_hour_share > 0.9 | **−2** |

### 6.4 Score → State Mapping

| Score Range | State |
|-------------|-------|
| 80 – 100 | `HIGHLY_RECOVERABLE` |
| 60 – 79 | `RECOVERABLE` |
| 40 – 59 | `LOW_RECOVERABLE` |
| 20 – 39 | `HARD_TO_RECOVER` |
| 0 – 19 | `NON_RECOVERABLE` |

### 6.5 Ejemplo de Cálculo

**Driver X (ID: 1842)**

| Componente | Valor | Puntos | Peso | Contribución |
|-----------|-------|--------|------|-------------|
| C1 Consistency | consistency_score = 0.88 | 100 | 0.25 | 25.0 |
| C2 Degradation | EARLY_WARNING (1 señal: trips -18%) | 80 | 0.25 | 20.0 |
| C3 Recency | Último viaje: hace 5 días | 100 | 0.20 | 20.0 |
| C4 Archetype | FULLTIMER | 100 | 0.15 | 15.0 |
| C5 Efficiency | revenue/hour en p68 | 70 | 0.10 | 7.0 |
| | | | **Subtotal** | **87.0** |
| C6 Modifiers | Prior TOP_PERFORMER (+5), Balanced Schedule (+2) | +7 | — | +7.0 |
| | | | **Total** | **94.0** |

**Estado:** `HIGHLY_RECOVERABLE`

---

## 7. EXPLAINABILITY LAYER

### 7.1 Principio

> Todo score debe poder descomponerse en sus partes y cada parte debe tener una razón operacional explícita.

No se permite "el modelo dice que...". Se requiere "este conductor es recoverable porque...".

### 7.2 Estructura de Explainability

Cada evaluación de recoverability producirá:

```json
{
  "driver_id": "1842",
  "recoverability_state": "HIGHLY_RECOVERABLE",
  "recoverability_score": 94.0,
  "score_breakdown": {
    "historical_consistency": {
      "score": 100,
      "weight": 0.25,
      "contribution": 25.0,
      "evidence": "consistency_score = 0.88 (activo 25 de 28 días)",
      "source": "driver_behavior_benchmarking.consistency_score"
    },
    "degradation_severity": {
      "score": 80,
      "weight": 0.25,
      "contribution": 20.0,
      "evidence": "EARLY_WARNING: trips_change = -18% (umbral -15%). 1 señal detectada.",
      "source": "operational_intelligence.pre_churn_signals"
    },
    "recency": {
      "score": 100,
      "weight": 0.20,
      "contribution": 20.0,
      "evidence": "Último viaje: hace 5 días (2026-05-16)",
      "source": "driver_daily_activity_fact.activity_date"
    },
    "archetype_compatibility": {
      "score": 100,
      "weight": 0.15,
      "contribution": 15.0,
      "evidence": "FULLTIMER: active_days >= 5, total_trips >= 40",
      "source": "operational_intelligence.archetypes"
    },
    "efficiency_legacy": {
      "score": 70,
      "weight": 0.10,
      "contribution": 7.0,
      "evidence": "revenue_per_hour = 18.50 (p68, mediana población = 15.20)",
      "source": "operational_intelligence.efficiency"
    },
    "modifiers": [
      {
        "modifier": "Prior TOP_PERFORMER",
        "points": "+5",
        "evidence": "Clasificado TOP_PERFORMER en período 2026-04-23 a 2026-05-20"
      },
      {
        "modifier": "Balanced Schedule",
        "points": "+2",
        "evidence": "weekend_share = 0.45, peak_hour_share = 0.52"
      }
    ]
  },
  "explainability_text": "Driver altamente recuperable. Consistencia histórica excepcional (88% días activos). Degradación reciente leve (-18% viajes, etapa temprana). Activo hace solo 5 días. Perfil FULLTIMER con alta dependencia de la plataforma. Eficiencia histórica por encima del promedio. Fue TOP_PERFORMER en el período anterior. Alta probabilidad de recuperación con intervención ligera.",
  "intervention_urgency": "HIGH",
  "risk_flags": [],
  "data_freshness": {
    "computed_at": "2026-05-21T10:30:00Z",
    "data_window_end": "2026-05-20",
    "sources_used": ["ops.driver_daily_activity_fact", "ops.driver_trip_behavior_fact", "ops.driver_session_fact"]
  }
}
```

### 7.3 Trace

Cada campo del breakdown incluye:
- **evidence:** El hecho concreto que sustenta el puntaje. No interpretaciones.
- **source:** La capa exacta de donde proviene el dato.
- **contribution:** Cuánto aporta al score total (para que el operador vea qué pesa más).

### 7.4 Explainability Text

Texto generado deterministicamente, no por LLM. Template:

```
Driver {state_nombre}. {frase_consistency}. {frase_degradation}. {frase_recency}. {frase_archetype}. {frase_efficiency}. {frase_modifiers}. {frase_verdict}.
```

Donde cada `frase_*` se elige de un catálogo determinístico según el valor del componente. Ejemplo para consistency:

| consistency_score | Frase |
|-------------------|-------|
| > 0.85 | "Consistencia histórica excepcional (XX% días activos)." |
| 0.70–0.85 | "Buena consistencia histórica (XX% días activos)." |
| 0.55–0.70 | "Consistencia histórica moderada (XX% días activos)." |
| 0.40–0.55 | "Consistencia histórica baja (XX% días activos)." |
| < 0.40 | "Consistencia histórica muy baja (XX% días activos)." |

---

## 8. RIESGOS OPERACIONALES

### 8.1 Riesgos de Clasificación

| # | Riesgo | Descripción | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| **R1** | **Falsos positivos** | Clasificar como RECOVERABLE a un conductor que no va a volver. | Desperdicio de recursos SAC. Fatiga del equipo de lealtad. | El score es probabilístico en espíritu, no certeza. Documentar tasa esperada de error. No garantizar resultados. |
| **R2** | **Falsos negativos** | Clasificar como NON_RECOVERABLE a un conductor que habría vuelto con intervención. | Pérdida de revenue recuperable. | Los modifiers (Prior TOP_PERFORMER, etc.) actúan como red de seguridad. Permitir overrides manuales en capas futuras. |
| **R3** | **Tautología operacional** | El score penaliza lo mismo que pretende predecir. Ej: "como no está activo → NON_RECOVERABLE → no lo intervenimos → sigue inactivo". | Profecía autocumplida. | Separar dimensiones de estado (qué pasó) de dimensiones de potencial (qué podría pasar). La recency pesa 20%, no 50%. |
| **R4** | **Data staleness** | Si los facts no están frescos, el score se calcula sobre datos viejos y clasifica mal. | Decisiones basadas en realidad desactualizada. | Incluir `data_freshness` en el output. No calcular score si los facts tienen >48h de antigüedad sin refresh. |

### 8.2 Riesgos de Sesgo Operacional

| # | Riesgo | Descripción | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| **R5** | **Bias hacia FULLTIMERs** | Los pesos actuales favorecen a FULLTIMERs/CONSISTENT_OPERATORs. Conductores PART_TIMER o WEEKEND_SPECIALIST pueden ser igualmente valiosos y recuperables pero el score los penaliza. | Sub-inversión en segmentos que podrían ser leales. | C4 (archetype) pesa solo 15%. Los modifiers compensan parcialmente. En fase futura, calibrar pesos por segmento. |
| **R6** | **Starvation de LOW_RECOVERABLE** | Si el presupuesto SAC se agota en HIGHLY_RECOVERABLE y RECOVERABLE, los LOW_RECOVERABLE nunca reciben intervención → nunca sabremos si el score funciona para ellos. | Sesgo de confirmación: solo validamos donde ya creemos que funciona. | Recomendar test A/B con pequeño % de LOW_RECOVERABLE para calibration continua. |
| **R7** | **Sacrificio del long-tail valioso** | Conductores de nicho (ej. weekend high-value, peak-hour en zona premium) pueden aparecer como HARD_TO_RECOVER por baja frecuencia, pero son estratégicos para cobertura horaria/zona. | Pérdida de cobertura en horas/zonas críticas. | Futuro: dimensión de "criticidad operacional" que module el score (fuera del alcance de 2C). |
| **R8** | **Castigo a casual drivers** | Conductores que siempre fueron esporádicos (ej. una vez cada 15 días) son clasificados como INCONSISTENT_OPERATOR → LOW_RECOVERABLE aunque su comportamiento sea perfectamente normal para su segmento. | Falsa alarma. Intervención innecesaria. | El score debe compararse contra la baseline del segmento, no contra la población general. Esto requiere segmentación previa (futuro). |

### 8.3 Riesgos de Proceso

| # | Riesgo | Descripción | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| **R9** | **Over-prioritization de recuperación** | Si 2C se vuelve el foco principal, se descuida la retención de conductores activos (STABLE, GROWING) que son la base del revenue actual. | Paradoja: gastamos en recuperar al 5% mientras perdemos al 95%. | 2C es capa diagnóstica, no motor de decisión. La priorización final la hará el Decision Engine (Fase 4/5). |
| **R10** | **Intervention paradox** | Si intervenimos masivamente sobre HIGHLY_RECOVERABLE, alteramos su comportamiento y el score pierde calibración. | El modelo se vuelve menos preciso con el tiempo. | Recalibración periódica de thresholds. Comparar tasas de retorno real vs esperadas. |
| **R11** | **Score gaming** | Si operadores SAC aprenden los thresholds, pueden sesgar sus decisiones para favorecer ciertos resultados. | Distorsión de métricas de efectividad. | Rotación de thresholds leves. Auditoría de decisiones vs scores. |

---

## 9. DEPENDENCIAS

### 9.1 Dependencias Internas (Capas Existentes)

```
FASE 2C depende de:
├── 2A.1 Driver Lifecycle ──────────► días desde último viaje, estado DORMANT/CHURNED
├── 2A.2 Driver Behavior Benchmarking ► consistency_score, clasificación previa, TOP_PERFORMER
├── 2A.3 Behavioral Pattern Diagnosis ─► gaps y patrones (uso indirecto, validación cruzada)
└── 2B Operational Behavioral Intelligence ► pre-churn signals, archetypes, efficiency, sessions
```

**Regla de fallback:** Si una capa dependiente no está disponible, el componente correspondiente del score se calcula con datos degradados (ej. consistency sin 2A.2 → desde trips raw) o se marca como `unavailable` y el peso se redistribuye proporcionalmente entre los componentes disponibles.

### 9.2 Dependencias de Datos

| Dependencia | Tipo | Estado | Riesgo si falta |
|-------------|------|--------|-----------------|
| `ops.driver_daily_activity_fact` | TABLE | Existente (309K rows) | Sin esta tabla no hay consistency ni recency fiables. |
| `ops.driver_trip_behavior_fact` | VIEW | Existente | Sin efficiency legacy ni degradation velocity precisos. |
| `ops.driver_session_fact` | MVIEW | Existente (refresh manual) | Sin session quality ni idle deterioration. |
| `ops.driver_zone_behavior_fact` | VIEW | Existente | Sin datos de zona. Componente no usado directamente en 2C v1. |
| `public.trips_2026` | TABLE | Existente (64M+ rows) | Fallback para métricas no cubiertas por facts. |
| `ops.v_real_trips_enriched_base` | VIEW | Existente | Fuente del trip_behavior_fact. |

### 9.3 Dependencias de Backlog Existente

| Backlog Item | Capa origen | Impacto en 2C si se completa |
|-------------|------------|------------------------------|
| REACTIVATED tracking | 2A.2 | Añadir dimensión F1: Prior Reactivation Success. Peso estimado: +10% al score actual. |
| BONUS_DEPENDENT archetype | 2B | Añadir archetype con scoring propio. |
| Trend lines multi-período | 2B | Mejorar C2 (Degradation Severity) con velocidad en vez de snapshot. |
| Seasonality-adjusted archetypes | 2B | Evitar falsos positivos por bajadas estacionales. |
| Archetype transition matrix | 2B | Añadir dimensión de trayectoria (¿está mejorando o empeorando?). |

---

## 10. QUÉ NO SE IMPLEMENTARÁ EN 2C

| Ítem | Razón |
|------|-------|
| **Modelos ML** | El diseño es determinístico. ML requeriría datos etiquetados de intervenciones previas que no existen. |
| **IA generativa** | La explainability es por templates, no LLM. |
| **Acciones automáticas** | 2C es solo diagnóstico. Las acciones son de fases futuras (Action Engine, Orchestrator). |
| **Endpoints API** | Se diseñan en este documento pero se implementan en la fase de construcción. |
| **Frontend / Dashboard** | Ídem. |
| **Integración con SAC/CRM** | Depende de sistemas externos. 2C solo produce el score y estado. |
| **Prioritización automática de cola SAC** | Lo hará el Decision Engine (Fase 4+). |
| **Cálculo de incentivos óptimos** | Requiere datos de elasticidad que no existen. |
| **Forecast de recuperación** | El Forecast Engine es una capa separada futura. |
| **Reachability (canales de contacto)** | El Reachability Engine es una capa separada futura. |
| **Scripts de llamada SAC** | El Suggestion Engine los generará en el futuro. |
| **Calibración automática de thresholds** | Los thresholds son fijos en esta fase. Recalibración manual periódica. |

---

## 11. QUÉ REQUIERE MADUREZ FUTURA

### 11.1 Señales que mejorarían el score sustancialmente

| Señal | Impacto estimado | Bloqueante |
|-------|-----------------|------------|
| Prior reactivation success (F1) | **Alto**: unos +10 puntos de precisión | Backlog 2A.2 |
| Incentive responsiveness (F2) | **Medio**: permitiría segmentar por canal de intervención | Sin datos |
| Multi-period trends (F3) | **Medio**: mejoraría C2 | Backlog 2B |
| Seasonality adjustment (F4) | **Alto**: evitaría ~15% de falsos positivos en conductores estacionales | Backlog 2B |
| Driver tenure (F8) | **Medio**: aportaría contexto de lealtad | Sin datos |

### 11.2 Umbrales que requerirán recalibración

Los thresholds actuales (ej. 85% consistency → 100 puntos) se calibraron conceptualmente. Una vez en producción, deberán recalibrarse contra datos reales de intervención:

1. **Tasa de retorno real vs score:** ¿Los HIGHLY_RECOVERABLE realmente vuelven más?
2. **Curva de recency real:** ¿La probabilidad de retorno cae como asumimos?
3. **Pesos de componentes:** ¿Consistency realmente es 2.5× más predictivo que efficiency?

---

## 12. FUTURE CONNECTIONS (ROADMAP POSTERIOR)

### 12.1 Cómo 2C Conecta con Capas Futuras

```
                              ┌──────────────────────────┐
                              │   FASE 2C: RECOVERABILITY │
                              │   INTELLIGENCE             │
                              │                            │
                              │   • recoverability_state   │
                              │   • recoverability_score   │
                              │   • score_breakdown        │
                              │   • explainability_text    │
                              └──────────┬─────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ▼                              ▼                              ▼
┌──────────────────┐    ┌──────────────────────────┐    ┌──────────────────────┐
│ REACHABILITY     │    │ FORECAST ENGINE           │    │ SUGGESTION ENGINE    │
│ ENGINE (Futuro)  │    │ (Futuro)                  │    │ (Fase 4)             │
│                  │    │                            │    │                      │
│ ¿Por qué canal   │    │ ¿Cuánto revenue             │    │ ¿Qué acción          │
│ contactamos a    │    │ recuperaríamos si           │    │ sugerimos para       │
│ este conductor?  │    │ intervenimos?               │    │ este conductor?      │
│                  │    │                            │    │                      │
│ Input: state     │    │ Input: score + breakdown   │    │ Input: score +       │
│ + score para     │    │ para modelar escenarios    │    │ archetype + patterns │
│ priorizar canal  │    │ de recuperación            │    │ para playbook        │
└────────┬─────────┘    └─────────────┬──────────────┘    └──────────┬───────────┘
         │                           │                              │
         └───────────────────────────┼──────────────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │ DECISION ENGINE (Fase 4+/5)      │
                    │                                  │
                    │ Priorización cross-driver:       │
                    │ ¿A cuáles intervenimos primero?  │
                    │ ¿Con qué presupuesto?            │
                    │ ¿Qué ROI esperamos?              │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌──────────┐  ┌──────────┐  ┌──────────────┐
             │ SAC      │  │ LEALTAD  │  │ INCENTIVOS   │
             │ Queue    │  │ Queue    │  │ Queue        │
             └──────────┘  └──────────┘  └──────────────┘
```

### 12.2 Integración con SAC Prioritization

Cuando el Suggestion Engine esté operativo (Fase 4), 2C le proporcionará:

- **Priority score:** derivado de recoverability_score × strategic_value (futuro).
- **Segmentación:** RECOVERABLE vs HARD_TO_RECOVER para decidir tono y oferta.
- **Contexto:** explainability_text como briefing para el agente SAC.

### 12.3 Integración con Loyalty Prioritization

- **HIGHLY_RECOVERABLE** → campañas de re-engagement ligeras (push notification, email).
- **RECOVERABLE** → ofertas de lealtad condicionadas (ej. "completa 10 viajes esta semana y desbloquea X").
- **LOW_RECOVERABLE** → test A/B con incentivos para medir elasticidad.

---

## 13. OUTPUTS FORMALES DE 2C

### 13.1 Estructura de Output por Conductor

```json
{
  "driver_id": "string",
  "recoverability_state": "HIGHLY_RECOVERABLE | RECOVERABLE | LOW_RECOVERABLE | HARD_TO_RECOVER | NON_RECOVERABLE",
  "recoverability_score": "float (0.0–100.0)",
  "score_breakdown": {
    "historical_consistency": { "score": "float", "weight": "float", "contribution": "float", "evidence": "string", "source": "string" },
    "degradation_severity": { "...": "..." },
    "recency": { "...": "..." },
    "archetype_compatibility": { "...": "..." },
    "efficiency_legacy": { "...": "..." },
    "modifiers": [ { "modifier": "string", "points": "string", "evidence": "string" } ]
  },
  "explainability_text": "string (generado por template determinístico)",
  "intervention_urgency": "HIGH | MEDIUM | LOW | NONE",
  "risk_flags": ["string (ej. 'seasonal_pattern_suspected', 'data_stale')"],
  "data_freshness": {
    "computed_at": "ISO8601",
    "data_window_end": "date",
    "sources_used": ["string"],
    "sources_unavailable": ["string"]
  }
}
```

### 13.2 Outputs Agregados (Futuro Endpoint)

| Output | Descripción |
|--------|------------|
| **Distribución de estados** | Cuántos drivers en cada estado de recoverability. |
| **Score promedio por país/ciudad** | ¿Hay mercados con peor recoverability estructural? |
| **Drivers en riesgo de degradación de estado** | HIGHLY_RECOVERABLE que bajarán a RECOVERABLE si no se interviene en N días. |
| **Matriz de transición** | ¿Cuántos pasan de RECOVERABLE → HARD_TO_RECOVER cada semana? |

---

## 14. VEREDICT

### Estado del diseño

**COMPLETO.** La arquitectura conceptual de Recoverability Intelligence está diseñada.

### Resumen de Entregables de Diseño

| # | Entregable | Estado |
|---|-----------|--------|
| 1 | 5 Recoverability States definidos | Diseñado |
| 2 | 12 Input Dimensions (8 disponibles, 4 futuro) | Diseñado |
| 3 | Deterministic Scoring Model (6 componentes, pesos, normalización) | Diseñado |
| 4 | Explainability Layer (breakdown + template text + trace) | Diseñado |
| 5 | 11 Riesgos Operacionales identificados con mitigación | Diseñado |
| 6 | Dependencias internas, de datos, y de backlog mapeadas | Diseñado |
| 7 | Future Connections con Reachability, Forecast, Suggestion, Decision, SAC, Loyalty | Diseñado |
| 8 | Outputs formales definidos | Diseñado |
| 9 | Lista explícita de qué NO se implementa en 2C | Diseñado |

### Recomendación

**AVANZAR a implementación de Fase 2C.**

Razones:

1. **Todas las dependencias de datos existen.** No se requiere crear nuevos facts, tablas, ni pipelines. 2C consume exclusivamente señales ya producidas por 2A.1, 2A.2, 2A.3 y 2B.
2. **El score es determinístico.** No hay riesgo de deriva de modelo, sobreajuste, ni opacidad. Se puede implementar como una función pura de Python que toma datos de los servicios existentes y devuelve el score.
3. **La explainability es total.** Cada punto del score tiene trazabilidad a una métrica concreta de una capa existente.
4. **El riesgo de construir 2C ahora es bajo.** Si los thresholds necesitan ajuste, se modifican constantes. Si una dimensión resulta no predictiva, se baja su peso. Nada de esto requiere re-entrenar ni re-arquitecturar.
5. **El valor incremental es alto.** Por primera vez, el sistema podrá responder "¿vale la pena intervenir este conductor?" — la pregunta que conecta el diagnóstico con la acción.

### Riesgo principal de avanzar ahora

La calibración de thresholds y pesos es conceptual, no empírica. Una vez que exista la capacidad de medir tasas de retorno reales post-intervención (esto requiere que el Action Engine esté operativo), será necesario **recalibrar**. Pero esperar a tener datos de intervención para diseñar el score sería un bloqueo circular: necesitamos el score para priorizar intervenciones, y necesitamos intervenciones para calibrar el score.

**Estrategia recomendada:** Implementar 2C con los thresholds de diseño. Usarlo en modo "shadow" inicialmente (calcular scores sin accionar). Recalibrar cuando haya datos de intervención real.

---

## 15. ARCHIVOS DE ESTA FASE (Futuro)

| Archivo | Propósito |
|---------|-----------|
| `backend/app/services/recoverability_intelligence_service.py` | Lógica del scoring engine |
| `backend/app/routers/recoverability_intelligence.py` | Endpoints API |
| `backend/app/main.py` | Wiring del router |
| `frontend/src/services/api.js` | Funciones de API |
| `frontend/src/components/recoverability/RecoverabilityIntelligenceDashboard.jsx` | Dashboard |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Entrada de navegación |
| `frontend/src/App.jsx` | Ruta y render |
| `backend/scripts/validate_phase2c_recoverability_intelligence.py` | QA Script |
| `docs/diagnostic_engine/FASE2C_RECOVERABILITY_INTELLIGENCE_ARCHITECTURE.md` | Este documento |

---

*Documento de arquitectura — Fase 2C. No implementar todavía.*
*Fecha: 2026-05-21*
