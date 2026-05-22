# Fase 2A.2 — Driver Behavior Benchmarking Layer

## 1. Objetivo

Comparar el comportamiento operativo de conductores top performers vs conductores en declive o en riesgo. Diagnosticar patrones operativos diferenciadores: qué hacen mejor los que ganan más, qué cambia en los que se degradan, qué señales aparecen antes de la fuga.

**No genera recomendaciones.** Solo diagnóstico comparativo y benchmarking.

---

## 2. Problema operacional que resuelve

Antes de poder recomendar acciones, el negocio necesita entender **qué diferencia a un conductor exitoso de uno que se está yendo**. Sin esto, cualquier recomendación es ciega.

Este layer proporciona:
- Identificación de señales tempranas de degradación
- Comparación cuantificable entre grupos de conductores
- Distribuciones por hora, día, ciudad, park, LOB
- Base factual para el futuro Suggestion Engine (Fase 4)

---

## 3. Inputs

### Fuente primaria
- **`ops.driver_daily_activity_fact`** (pre-agregada, optimizada) — fuente canónica
- Fallback: `public.trips_2026` solo si fact table no existe o está vacía

### NOTA SOBRE 2A.1.1
`ops.driver_daily_activity_fact` fue creada por Fase 2A.1.1. En la versión inicial de 2A.2 se reportó erróneamente como inexistente por falta de verificación directa contra PostgreSQL. El FIX de alineación (Fase 2A.2-FIX) corrigió esto con verificación directa contra la DB.

---

## 4. KPIs disponibles

| KPI | Fuente | Columna | Estado |
|-----|--------|---------|--------|
| total_trips | trips_2026 | COUNT(*) | Disponible |
| active_days | trips_2026 | COUNT(DISTINCT fecha) | Disponible |
| total_revenue | trips_2026 | comision_empresa_asociada | Disponible |
| avg_ticket | trips_2026 | precio_yango_pro | Disponible |
| avg_trips_per_driver | Calculado | GROUP BY | Disponible |
| trips_per_active_day | Calculado | trips / active_days | Disponible |
| consistency_score | Calculado | active_days / period_days | Disponible |
| peak_hour_share | trips_2026 | EXTRACT(HOUR) | Disponible |
| weekend_share | trips_2026 | EXTRACT(DOW) | Disponible |
| avg_distance_km | trips_2026 | distancia_km | Disponible |
| avg_duration_sec | trips_2026 | fecha_fin - fecha_ini | Disponible |
| city_distribution | dim.dim_park | city | Disponible |
| park_distribution | trips_2026 | park_id | Disponible |
| lob_distribution | trips_2026 | tipo_servicio | Disponible |

---

## 5. KPIs no disponibles (backlog)

| KPI | Razón |
|-----|-------|
| online_hours | Columna no existe en trips_2026 ni en MVs |
| zone | Columna no existe |
| acceptance_rate | Columna no existe |
| cancellation_rate | Existe condicion='Cancelado' pero no se calcula por ahora |

---

## 6. Definición TOP_PERFORMER

Determinístico, parametrizable:

1. Se ordenan todos los conductores activos por `rolling_{period_days}_trips` descendente
2. Se toma el percentil 80 (índice `int(n * 0.20) - 1`)
3. Si el threshold es 0 (datos insuficientes), se usa `max(1, top_trips[0] // 2)`
4. TOP_PERFORMER = trips >= threshold AND active_days >= period_days * 0.3
5. Excluye DORMANT y CHURNED

Parametrizable por:
- `country` (filtro opcional)
- `city` (filtro opcional)
- `period_days` (default 28)

---

## 7. Grupos comparados

| Grupo | Criterio de clasificación |
|-------|--------------------------|
| TOP_PERFORMER | Percentil 80+ de viajes, días activos suficientes |
| STABLE | Actividad consistente sin tendencia marcada |
| GROWING | Incremento >25% vs ventana anterior |
| DECLINING | Decremento >25% vs ventana anterior |
| AT_RISK | Decremento >40% o ≤3 viajes y ≤3 días activos |
| DORMANT | 14-29 días sin actividad |
| CHURNED | 30+ días sin actividad |
| REACTIVATED | (Backlog: requiere detección de retorno post-churn) |

---

## 8. Endpoints API

Prefijo: `/driver-behavior`

### GET /driver-behavior/summary
Resumen general con conteos por grupo, métricas disponibles/faltantes, fuente de datos.

### GET /driver-behavior/group-benchmarks
Tabla completa de KPIs por grupo lifecycle.

### GET /driver-behavior/top-vs-risk
Comparación directa TOP_PERFORMER vs DECLINING vs AT_RISK con gaps e interpretaciones diagnósticas.

### GET /driver-behavior/distributions
Distribución por dimensión (city, park, lob, day_of_week, hour), opcionalmente filtrada por grupo.

---

## 9. Vista frontend

**Ruta:** `/drivers/behavior-benchmarking`
**Componente:** `DriverBehaviorBenchmarkingDashboard.jsx`
**Tab:** Drivers → Benchmarking

Incluye:
- Filtros: country, city, period_days
- KPI cards: total, top performers, declining, at risk
- Tabla de group benchmarks
- Tabla Top vs Risk con interpretaciones
- Distribuciones con selector de dimensión y grupo
- Banner de limitaciones (métricas faltantes)

---

## 10. Limitaciones

1. `ops.driver_daily_activity_fact` **no existe** — se usa `public.trips_2026` directamente
2. `online_hours` no disponible en ninguna fuente
3. `zone` no existe como columna
4. `acceptance` no existe como métrica
5. `REACTIVATED` no se calcula en esta fase (requiere tracking de churn previo)
6. Las distribuciones por LOB dependen de que `tipo_servicio` esté poblado
7. La query a `trips_2026` puede ser pesada para ventanas >60 días con muchos drivers
8. Los grupos se clasifican en Python (no en SQL) para mantener la lógica determinística y testeable

---

## 11. Qué NO se construyó

- NO Suggestion Engine
- NO Decision Engine
- NO acciones automáticas
- NO mensajes para conductores
- NO recomendaciones accionables
- NO scripts de llamada
- NO IA
- NO modificación de Driver Lifecycle existente
- NO modificación de Omniview Matrix
- NO modificación de Plan vs Real
- NO `ops.driver_daily_activity_fact` (no existe)

---

## 12. Backlog Fase 2A.3

- Crear `ops.driver_daily_activity_fact` si es viable
- Detección de REACTIVATED (post-churn)
- Añadir online_hours si se captura en el futuro
- Detección de cancelaciones por conductor
- Análisis de estacionalidad semanal
- Trending de KPIs en el tiempo (no solo snapshot)

---

## 13. Backlog Fase 4 — Suggestion Engine

- Traducir gaps de benchmarking en sugerencias contextuales
- Matching de conductores DECLINING con patrones de TOP_PERFORMER
- Priorización de intervenciones por impacto estimado
- Playbooks por segmento

---

## 14. Veredicto

**GO** — QA real ejecutado con 38/38 PASS. Fuente alineada a `ops.driver_daily_activity_fact`.

---

## 15. Source Alignment Fix (2A.2-FIX)

### Evidencia de fact table
- **Existe:** SI (BASE TABLE en schema `ops`)
- **Rows:** 309,649
- **Drivers:** 17,100
- **Rango de fechas:** 2026-02-20 → 2026-05-21
- **Columnas:** driver_id, activity_date, country, city, park_id, completed_trips, source_year, last_refreshed_at

### Fuente final usada por 2A.2
`ops.driver_daily_activity_fact` como fuente primaria (source_type: pre_aggregated_fact).

### Fallback policy
- Si fact table no existe → `public.trips_2026` con `source_warning` y `fallback_reason`
- Si fact table existe pero está vacía → `public.trips_2026` con `source_warning` y `fallback_reason`
- Enriquecimiento opcional desde trips_2026: `enrich_from_trips=false` por defecto

### Performance real
| Endpoint | Tiempo | Threshold |
|----------|--------|-----------|
| /driver-behavior/summary | 3.1s | <4s OK |
| /driver-behavior/group-benchmarks | 2.6s | <4s FAST |
| /driver-behavior/top-vs-risk | 2.6s | <4s FAST |
| /driver-behavior/distributions | 5.3s | <8s SLOW |
| /ops/driver-lifecycle/summary | 1.5s | FAST |
| /ops/business-slice/matrix-operational-trust | <1s | FAST |
| /ops/plan-vs-real/monthly | 2.6s | OK |

### QA real ejecutado
- **38/38 PASS**
- Endpoints: summary, group-benchmarks, top-vs-risk, distributions (x2)
- Fact table: verified in DB (exists, has data, date range valid)
- Source alignment: data_source=same, source_type=pre_aggregated_fact, no fallback, no warnings
- Groups: valid names, required fields present
- No negative values
- TOP_PERFORMER detected (1,982 of 10,067 drivers)
- Interpretations neutral (no actionable recommendations)
- Missing dimensions handled gracefully (available=false + reason)
- Lifecycle NOT BROKEN
- Omniview Matrix NOT BROKEN
- Plan vs Real NOT BROKEN
- Performance <15s

### Limitaciones
1. Revenue, avg_ticket, trip_hour, distance, duration, tipo_servicio no están en la fact table
2. Distribución LOB no disponible sin trips_2026 (expensive mode)
3. Distribución por ciudad/park tarda ~5.3s (aceptable <8s)

---

### Archivos creados/modificados

| Archivo | Acción |
|---------|--------|
| `backend/app/services/driver_behavior_benchmarking_service.py` | Creado |
| `backend/app/routers/driver_behavior_benchmarking.py` | Creado |
| `backend/app/main.py` | Modificado (import + include_router) |
| `frontend/src/services/api.js` | Modificado (4 funciones) |
| `frontend/src/components/driverBehavior/DriverBehaviorBenchmarkingDashboard.jsx` | Creado |
| `frontend/src/config/controlTowerNavigationRegistry.js` | Modificado (nueva entrada) |
| `frontend/src/App.jsx` | Modificado (import, ruta, sub-url, render) |
| `backend/scripts/validate_phase2a2_driver_behavior_benchmarking.py` | Creado |
| `docs/diagnostic_engine/FASE2A2_DRIVER_BEHAVIOR_BENCHMARKING.md` | Creado |
