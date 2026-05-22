# Fase 2A.3 — Behavioral Pattern Diagnosis

## 1. Objetivo

Explicar **por qué** los grupos de conductores son diferentes. Va más allá del benchmarking comparativo (Fase 2A.2) para identificar patrones operativos diferenciales con interpretaciones diagnósticas determinísticas.

## 2. Problema operacional que resuelve

Fase 2A.2 respondió "cuánto difieren los grupos". Esto responde **"qué explica esas diferencias"**:

- Qué dimensiones operativas separan a TOP_PERFORMER de AT_RISK
- Qué señales de deterioro aparecen antes de la fuga
- Qué patrones son consistentes vs circunstanciales

## 3. Diferencia entre Benchmarking y Pattern Diagnosis

| | Benchmarking (2A.2) | Pattern Diagnosis (2A.3) |
|---|---|---|
| Output | Tabla de KPIs por grupo | Patrones explicativos |
| Pregunta | ¿Cuánto difieren? | ¿Por qué difieren? |
| Método | Agregación + clasificación | Reglas determinísticas sobre gaps |
| Ejemplo | "TOP tiene 42 viajes, AT_RISK tiene 5" | "TOP_PERFORMER presenta 740% más volumen de viajes que AT_RISK. Diferencia HIGH." |

## 4. Inputs

- `ops.driver_daily_activity_fact` — fuente primaria (via benchmarking service)
- `driver_behavior_benchmarking_service.py` — datos base de grupos
- `public.trips_2026` — solo si `enrich_from_trips=true` (default: false)

## 5. Outputs

- Patrones detectados con dimension, strength, interpretation
- Perfiles de grupo (KPIs + top cities + top parks)
- Señales de deterioro (STABLE vs DECLINING / AT_RISK)

## 6. Reglas determinísticas

### A. Activity Volume Gap
Compara `avg_trips_per_driver` entre grupos. Strength: HIGH >= 100% gap, MEDIUM >= 50%, LOW >= 25%.

### B. Active Days Gap
Compara `avg_active_days`. Mismos thresholds.

### C. Productivity Gap
Compara `trips_per_active_day`. Mismos thresholds.

### D. Consistency Gap
Compara `consistency_score`. Strength: HIGH >= 30pp, MEDIUM >= 15pp, LOW >= 5pp.

### E. Weekend Concentration
Compara `weekend_share` si existe. Mismos thresholds que consistency.

### F. Decline Signals
Compara STABLE vs DECLINING vs AT_RISK en todas las métricas, generando señales de deterioro.

## 7. Dimensiones soportadas

| Dimensión | Disponible | Fuente |
|-----------|-----------|--------|
| activity_volume | SI | avg_trips_per_driver |
| consistency | SI | avg_active_days, consistency_score |
| productivity | SI | trips_per_active_day |
| weekday_weekend | SI | weekend_share |
| city_mix | SI (group-profile) | distributions |
| park_mix | SI (group-profile) | distributions |
| revenue_efficiency | NO | requiere enrich_from_trips |
| lob_mix | NO | requiere enrich_from_trips |
| time_efficiency | NO | requiere enrich_from_trips |
| distance_efficiency | NO | requiere enrich_from_trips |
| cancellation_behavior | NO | requiere enrich_from_trips |

## 8. Métricas faltantes

revenue, avg_ticket, trip_hour, distance, duration, tipo_servicio, cancellation, online_hours, zone, acceptance

Disponibles con `enrich_from_trips=true` (default false por performance).

## 9. Endpoints

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/behavioral-patterns/summary` | Resumen: patrones detectados, dimensiones, modo |
| GET | `/behavioral-patterns/patterns` | Lista de patrones (filtrable por dimension, strength) |
| GET | `/behavioral-patterns/group-profile` | Perfil completo de un grupo (KPIs + distribuciones) |
| GET | `/behavioral-patterns/decline-signals` | Señales de deterioro STABLE vs DECLINING/AT_RISK |

## 10. Vista frontend

**Ruta:** `/drivers/behavioral-patterns` (Drivers → Patrones)
**Componente:** `BehavioralPatternDiagnosisDashboard.jsx`

- KPI cards: patrones totales, HIGH/MEDIUM/LOW
- Tabla de patrones detectados con fuerza e interpretación
- Perfil de grupo con selector
- Tabla de señales de deterioro
- Banner de limitaciones

## 11. Limitaciones

1. Solo detecta patrones basados en métricas disponibles en la fact table
2. Revenue, hour, distance requieren `enrich_from_trips=true` (costoso)
3. Las interpretaciones son correlacionales, no causales
4. No analiza estacionalidad ni tendencias de largo plazo
5. La fuerza de los patrones depende de thresholds determinísticos fijos

## 12. Qué NO se construyó

- NO Suggestion Engine
- NO Decision Engine
- NO recomendaciones automáticas
- NO acciones para conductores
- NO scripts de llamada
- NO IA
- NO causal inference
- NO modificación de layers existentes

## 13. Backlog

### Fase 3
- Análisis de tendencias temporales (no solo snapshot)
- Patrones de seasonality
- Correlación entre métricas

### Fase 4 (Suggestion Engine)
- Traducir patrones en sugerencias contextuales
- Matching de conductores con patrones de éxito
- Priorización por impacto estimado

## 14. Performance Hardening 2A.3.1

### Problema inicial
Fase 2A.3 cerró con CONDITIONAL GO por lentitud:
- summary: 5.9s
- group-profile: 11.9s
- patterns: 2.8s
- decline-signals: 2.8s

### Causa raíz
1. **Llamadas duplicadas a `get_behavior_benchmarking_groups()`**: Cada endpoint hacía su propio fetch+classify de drivers (~3s cada uno)
2. **group-profile llamaba a `get_behavior_benchmarking_distributions()` 2x** (city + park), cada una re-ejecutando el fetch+classify
3. **Cálculos de patrones idénticos** entre summary y patterns

### Cambios realizados
1. **Cache compartido TTL (300s)**: `_get_full_benchmark_data()` ejecuta el fetch+classify UNA vez y lo comparte entre todas las funciones
2. **Queries directas al fact table** para top_cities/top_parks en vez de llamar a distributions (que re-clasificaba todo)
3. **Reutilización de `_build_group_benchmarks`** desde la capa de benchmarking para evitar recomputar grupos
4. **Eliminación de `get_behavior_benchmarking_distributions`** del group-profile

### Performance antes/después

| Endpoint | Antes | Ahora (cold) | Ahora (warm) |
|----------|-------|-------------|-------------|
| summary | 5.9s | 4.5s | 0.0s |
| patterns | 2.8s | 0.0s | 0.0s |
| group-profile | 11.9s | 2.2s | 1.3s |
| decline-signals | 2.8s | 0.0s | 0.0s |

### Cache
- TTL: 300s (5 minutos)
- Key: (country, city, period_days, enrich_from_trips)
- Expiración automática de entradas > 2x TTL
- Cache operacional, no fuente de verdad

### Riesgos remanentes
1. Group-profile warm todavía gasta 1.3s (queries directas a fact table)
2. Sin cache entre diferentes parámetros (country/city distintos = cache miss)
3. Cache en memoria no sobrevive a reinicio del servidor

### Veredicto
**GO** — group-profile de 11.9s a 2.2s (-81%). Todos los endpoints bajo 5s en frío, instantáneos en cálido.

## 15. Veredicto

**GO** — Performance hardening exitoso.

---

### Archivos creados/modificados

| Archivo | Acción |
|---------|--------|
| `backend/app/services/behavioral_pattern_diagnosis_service.py` | CREADO |
| `backend/app/routers/behavioral_pattern_diagnosis.py` | CREADO |
| `backend/app/main.py` | MODIFICADO (+import, +include_router) |
| `frontend/src/services/api.js` | MODIFICADO (+4 funciones) |
| `frontend/src/components/behavioralPatterns/BehavioralPatternDiagnosisDashboard.jsx` | CREADO |
| `frontend/src/config/controlTowerNavigationRegistry.js` | MODIFICADO (+1 entry) |
| `frontend/src/App.jsx` | MODIFICADO (+import, ruta, sub-url, render) |
| `backend/scripts/validate_phase2a3_behavioral_pattern_diagnosis.py` | CREADO |
| `docs/diagnostic_engine/FASE2A3_BEHAVIORAL_PATTERN_DIAGNOSIS.md` | CREADO |
