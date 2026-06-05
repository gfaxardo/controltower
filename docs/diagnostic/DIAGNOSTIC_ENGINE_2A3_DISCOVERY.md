# DIAGNOSTIC ENGINE 2A.3 — BEHAVIORAL PATTERN DIAGNOSIS: DISCOVERY

**Motor:** Diagnostic Engine  
**Fecha:** 2026-06-03  
**Versión:** 1.0  
**Estado:** DISCOVERY — LISTO PARA IMPLEMENTACIÓN (GO)

---

## 1. GOVERNANCE PRECHECK

| Item | Value |
|------|-------|
| ACTIVE phase | Diagnostic Engine 2A.3 |
| Omniview Hardening | CLOSED (O5) |
| Control Foundation | Confiable |
| Forecast/Suggestion/Decision/Action | Bloqueados |
| Este sprint | Discovery/architecture, no feature productiva |

---

## 2. PROBLEMA DIAGNÓSTICO

**Problema**: "Explicar diferencias de comportamiento entre drivers activos, decrecientes, en riesgo y top performers usando métricas observables determinísticas."

**Preguntas que responde Diagnostic:**

| Pregunta | Fuente |
|----------|--------|
| ¿Qué cambió? | WoW delta trips, active days, segment migration |
| ¿En qué segmento? | Clasificación determinística por trips semanales |
| ¿Desde cuándo? | 4-week baseline vs current week |
| ¿Qué patrón observable lo explica? | Inactividad, caída progresiva, volatilidad, estacionalidad |
| ¿Qué tan confiable es el diagnóstico? | `confidence_level` basado en volumen de datos y consistencia |

**Preguntas que NO responde Diagnostic (pertenecen a motores posteriores):**
- ¿Qué acción tomar? → Suggestion Engine (bloqueado)
- ¿A quién llamar primero? → Decision Engine (bloqueado)
- ¿Se recuperará? → Forecast Engine (bloqueado)
- ¿Qué campaña lanzar? → Action Engine (bloqueado)

---

## 3. INPUTS CANÓNICOS

### 3.1 Fuente primaria (daily grain)

| Tabla | Grain | Columnas clave | Certificada | Owner |
|-------|-------|---------------|-------------|-------|
| `ops.driver_daily_activity_fact` | driver + day | `driver_id`, `activity_date`, `completed_trips`, `country`, `city`, `park_id` | **Sí** | Driver refresh pipeline |

**Coverage**: 90 días por defecto. Refrescable con `--days N`, `--full`, `--backfill-from`.

### 3.2 Fuentes secundarias (weekly/monthly grain)

| Tabla | Grain | Columnas clave | Certificada |
|-------|-------|---------------|-------------|
| `ops.mv_driver_weekly_stats` | driver + week | `driver_key`, `week_start`, `trips_completed_week`, `work_mode_week`, `park_id` | **Sí** |
| `ops.mv_driver_segments_weekly` | driver + week | `segment_week`, `segment_change_type`, `weeks_active_rolling_4w`, `baseline_trips_4w_avg` | **Sí** |
| `ops.driver_weekly_segment_fact` | driver + week | `trips_completed`, `segment`, `park_id`, `country`, `city` | **Sí** |
| `ops.mv_driver_lifecycle_base` | driver | `activation_ts`, `last_completed_ts`, `total_trips_completed`, `lifetime_days` | **Sí** (SOT primary) |
| `ops.v_driver_behavior_baseline_weekly` | driver + week | `trips_current_week`, `avg_trips_baseline`, `delta_pct`, `z_score_simple`, `weeks_declining_consecutively` | **Sí** |
| `ops.v_driver_behavior_alerts_weekly` | driver + week | `alert_type`, `severity` | **under_review** |
| `ops.mv_supply_segments_weekly` | park + segment + week | `drivers_count`, `trips_sum`, `segment_week` | **Sí** (SOT primary for supply) |

### 3.3 Fuentes de identidad

| Tabla | Columnas clave |
|-------|---------------|
| `public.drivers` | `driver_id`, `full_name`, `phone`, `park_id`, `created_at`, `hire_date` |
| `public.drivers_data` | `driver_phone` |
| `dim.dim_park` | `park_id`, `park_name`, `city`, `country` |

### 3.4 Configuración

| Tabla | Uso |
|-------|-----|
| `ops.driver_segment_config` | Umbrales de segmentación (min/max trips por semana) |

---

## 4. MÉTRICAS DIAGNÓSTICAS

### 4.1 Actividad

| Métrica | Fórmula | Grain | Fuente |
|---------|---------|-------|--------|
| `trips_current_week` | SUM(completed_trips) WHERE week_start = current | weekly | `driver_daily_activity_fact` |
| `active_days_current_week` | COUNT(DISTINCT activity_date) WHERE week_start = current | weekly | `driver_daily_activity_fact` |
| `trips_per_active_day` | trips_current_week / active_days_current_week | weekly | derivada |
| `baseline_trips_4w_avg` | AVG(SUM(trips) per week) over last 4 closed weeks | weekly | `driver_daily_activity_fact` |
| `lifetime_trips` | `total_trips_completed` | driver | `mv_driver_lifecycle_base` |

### 4.2 Cambio

| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| `delta_trips_abs` | trips_current_week - baseline_trips_4w_avg | Magnitud del cambio |
| `delta_trips_pct` | delta_trips_abs / baseline_trips_4w_avg | Intensidad relativa |
| `delta_active_days` | active_days_current_week - AVG(active_days) 4w | Cambio en frecuencia |
| `weeks_declining` | Semanas consecutivas con delta < 0 | Persistencia de caída |
| `z_score_baseline` | (trips_current - avg_baseline) / stddev_baseline | Desviación estadística |

### 4.3 Riesgo

| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| `days_since_last_trip` | today - last_completed_ts | Inactividad actual |
| `inactivity_streak` | Días consecutivos sin trips | Riesgo de churn |
| `volatility_4w` | STDDEV(trips_per_week) over 4 weeks | Inestabilidad |
| `declining_streak` | Semanas consecutivas con delta < -20% | Caída sostenida |

---

## 5. SEGMENTOS DETERMINÍSTICOS

### 5.1 Clasificación por actividad actual (basada en `driver_segment_config`)

| Segmento | Regla | trips_semana |
|----------|-------|-------------|
| **DORMANT** | 0 trips, last_trip > 14d | 0 |
| **OCCASIONAL** | Actividad esporádica | 1-5 |
| **CASUAL** | Baja pero consistente | 6-15 |
| **PT** | Part-time | 16-35 |
| **FT** | Full-time | 36-60 |
| **ELITE** | Alto volumen | 61-100 |
| **LEGEND** | Top performer | 101+ |

### 5.2 Clasificación por tendencia (Diagnostic-specific)

| Segmento | Regla exacta | Fuente |
|----------|-------------|--------|
| **STABLE_ACTIVE** | z_score_baseline entre -1 y +1, trips > 0 | `mv_driver_segments_weekly` |
| **GROWING** | delta_trips_pct > +20%, trips_current > 0 | `driver_daily_activity_fact` |
| **DECLINING** | delta_trips_pct < -20%, weeks_declining >= 1 | `driver_daily_activity_fact` |
| **AT_RISK** | delta_trips_pct < -50% OR inactivity_streak >= 7d | `driver_daily_activity_fact` + `mv_driver_lifecycle_base` |
| **CHURNED_RECENT** | days_since_last_trip >= 14 AND was_active_last_4w | `mv_driver_lifecycle_base` |
| **NEW_ACTIVE** | activation_ts dentro de últimos 30d, trips > 0 | `mv_driver_lifecycle_base` |
| **REACTIVATED** | days_since_last_trip > 14, now has trips in current week | `mv_driver_lifecycle_base` |
| **TOP_PERFORMER** | ELITE o LEGEND, delta estable | `driver_segment_config` + delta |
| **LOW_SIGNAL** | baseline_trips_4w_avg < 3 (datos insuficientes) | `driver_daily_activity_fact` |

### 5.3 Por qué pertenece a Diagnostic y no a Suggestion

Estos segmentos describen **ESTADO**, no prescriben **ACCIÓN**. Diagnostic dice "este driver está DECLINING". Suggestion dirá "para drivers DECLINING, la acción más efectiva es X". Decision dirá "entre los DECLINING, contactar primero a Y". Action ejecutará el contacto.

---

## 6. OUTPUT CONTRACT

```json
{
  "driver_id": "string",
  "country": "string",
  "city": "string",
  "park_id": "string",
  "diagnostic_segment": "STABLE_ACTIVE | GROWING | DECLINING | AT_RISK | CHURNED_RECENT | NEW_ACTIVE | REACTIVATED | TOP_PERFORMER | LOW_SIGNAL",
  "diagnostic_label": "string (human-readable, ej: 'Caída del 35% vs baseline 4 semanas')",
  "diagnostic_reason": "string (technical, ej: 'trips_current=12, baseline=18.5, z_score=-1.8')",
  "supporting_metrics": {
    "trips_current_week": "number",
    "baseline_trips_4w_avg": "number",
    "delta_trips_pct": "number",
    "active_days_current_week": "number",
    "days_since_last_trip": "number",
    "z_score_baseline": "number",
    "weeks_declining": "number"
  },
  "confidence_level": "high | medium | low",
  "freshness_status": "fresh | stale | unknown",
  "period_start": "YYYY-MM-DD",
  "period_end": "YYYY-MM-DD",
  "baseline_period": "YYYY-MM-DD..YYYY-MM-DD",
  "comparison_period": "YYYY-MM-DD",
  "trace_id": "uuid"
}
```

**NO incluye**: `recommended_action`, `priority_score`, `forecast`, `next_best_action`.

---

## 7. SERVING ARCHITECTURE

```
┌─────────────────────────────────────────────────────────┐
│                   INPUT LAYER (existing)                 │
├─────────────────────────────────────────────────────────┤
│  ops.driver_daily_activity_fact (driver+day)             │
│  ops.mv_driver_lifecycle_base (driver)                   │
│  ops.mv_driver_segments_weekly (driver+week)             │
│  ops.driver_segment_config (thresholds)                  │
│  public.drivers (identity)                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│               DIAGNOSTIC COMPUTE LAYER                   │
├─────────────────────────────────────────────────────────┤
│  driver_behavioral_pattern_diagnosis_service.py (nuevo)  │
│                                                          │
│  Funciones:                                              │
│  - classify_driver_segment(driver_id, week)              │
│  - compute_baseline_metrics(driver_id, weeks=4)          │
│  - compute_delta_metrics(driver_id, current_week)        │
│  - compute_risk_signals(driver_id)                       │
│  - diagnose_driver(driver_id) → DiagnosticOutput         │
│  - diagnose_population(filters) → [DiagnosticOutput]     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                SERVING LAYER (new)                       │
├─────────────────────────────────────────────────────────┤
│  ops.mv_driver_diagnostic_summary_weekly (MV - weekly)   │
│    - snapshot semanal del diagnóstico por driver         │
│    - columns: driver_id, week_start, segment,            │
│      baseline_trips, current_trips, delta_pct,           │
│      risk_signals, confidence, country, city, park_id    │
│                                                          │
│  ops.v_driver_diagnostic_detail (VIEW - on-demand)       │
│    - versión live del diagnóstico (sin MV)               │
│    - para debugging y ad-hoc queries                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    API LAYER (new)                       │
├─────────────────────────────────────────────────────────┤
│  GET /diagnostic/driver/{driver_id}                      │
│  GET /diagnostic/population?country=&city=&park=&segment=│
│  GET /diagnostic/summary?week=                           │
│  GET /diagnostic/segments/distribution?week=             │
│  GET /diagnostic/risk/drivers?limit=50                   │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    UI LAYER (future)                     │
├─────────────────────────────────────────────────────────┤
│  DiagnosticDashboard (ya esbozado en BehavioralPattern   │
│  DiagnosisDashboard.jsx — Fase 2A.1/2A.2 existente)      │
└─────────────────────────────────────────────────────────┘
```

### Refresh strategy

| Componente | Estrategia |
|-----------|-----------|
| `mv_driver_diagnostic_summary_weekly` | REFRESH MATERIALIZED VIEW CONCURRENTLY, semanal (lunes 03:00) |
| `driver_behavioral_pattern_diagnosis_service.py` | Compute on-demand (APScheduler + cache 5min) |
| Freshness | `MAX(week_start)` en serving fact, expuesto en `/diagnostic/health` |

---

## 8. GO / NO-GO

### GO para implementación

| Criterio | Estado |
|----------|--------|
| Fuentes certificadas | **Sí** — `driver_daily_activity_fact`, `mv_driver_lifecycle_base`, `mv_driver_segments_weekly` |
| Métricas definidas | **Sí** — 15 métricas determinísticas |
| Segmentos definidos | **Sí** — 9 segmentos con reglas exactas |
| Output contract definido | **Sí** — 15 campos, sin recommendation |
| Arquitectura serving definida | **Sí** — 1 MV, 1 view, 5 endpoints |
| No dependencia de IA | **Sí** — 100% determinístico |
| No runtime pesado UI | **Sí** — compute en backend, cache en MV |

### NO-GO triggers

| Condición | Estado |
|-----------|--------|
| Fuentes no gobernadas | Ninguna — todas certificadas |
| Métricas ambiguas | Ninguna — fórmulas exactas |
| Umbrales sin trazabilidad | Config en `driver_segment_config` |
| Mezcla con Suggestion | Separación clara en output contract |
| Falta de serving architecture | Completa (Sección 7) |

---

## 9. BACKLOG

### Fase 2A.3 — Implementación (este sprint)

| ID | Tarea |
|----|-------|
| D1 | Crear `driver_behavioral_pattern_diagnosis_service.py` |
| D2 | Crear `ops.mv_driver_diagnostic_summary_weekly` |
| D3 | Crear `ops.v_driver_diagnostic_detail` |
| D4 | Crear router `/diagnostic/*` con 5 endpoints |
| D5 | Crear `refresh_driver_diagnostic_summary.py` |
| D6 | Crear QA script `audit_driver_diagnostic.py` |
| D7 | Tests unitarios para clasificación + métricas |

### Fase 2A.4 — UI (futuro)

| ID | Tarea |
|----|-------|
| U1 | Diagnostic Dashboard (ya esbozado) |
| U2 | Driver detail card |
| U3 | Population distribution chart |

---

## 10. VEREDICTO

### GO — Discovery completo, listo para implementación controlada.

**Evidencia**: 11 inputs canónicos, 15 métricas, 9 segmentos determinísticos, output contract, serving architecture, GO/NO-GO criteria definidos.

**Próximo paso**: DIAGNOSTIC ENGINE 2A.3 — IMPLEMENTATION. Crear servicio, MV, endpoints, y QA script según arquitectura definida.

---

## 11. PRÓXIMO PROMPT RECOMENDADO

**Diagnostic Engine 2A.3 — Implementation Sprint**: Crear `driver_behavioral_pattern_diagnosis_service.py` con las 4 funciones de diagnóstico, crear `ops.mv_driver_diagnostic_summary_weekly`, crear router `/diagnostic/*`, crear script de refresh, QA, y tests. Sin IA, sin Forecast, sin Suggestion.

---

**END OF DISCOVERY**
