# OV2-A — CLASIFICACIÓN DE MÉTRICAS, ENDPOINTS Y COMPONENTES

> **Fase:** OV2-A — Blindaje Lógico OV2  
> **Fecha:** 2026-06-04  
> **Clasificación:** KEEP / REBUILD / DROP / BACKLOG

---

## RESUMEN EJECUTIVO

| Clase | Métricas | Endpoints | Componentes | Servicios | Data Sources |
|-------|----------|-----------|-------------|-----------|--------------|
| **KEEP** | 3 | 12 | 8 | 10 | 8 |
| **REBUILD** | 4 | 5 | 6 | 6 | 3 |
| **DROP** | 0 | 3 | 3 | 3 | 5 |
| **BACKLOG** | 0 | 2 | 4 | 5 | 0 |
| **TOTAL** | 7 | 22 | 21 | 24 | 16 |

---

## 1. KEEP — ESTABLE, TRAZABLE, CON FUENTE REAL CLARA

### 1.1 Métricas KEEP (3/7)

| Métrica | Justificación |
|---------|--------------|
| `trips_completed` | Aditivo puro, fact-first, cross-grain exact_sum, lineage completo. Sin fallback. |
| `revenue_yego_net` | Aunque tiene fallback proxy, la columna está precalculada en fact table. Definición canónica documentada (CF-H2). El fallback está identificado y es trazable. |
| `active_drivers` | Semi-aditivo con restricción cross-grain documentada. Sin fallback. |

### 1.2 Endpoints KEEP (12/22)

| Endpoint | Justificación |
|----------|--------------|
| `GET /ops/business-slice/monthly` | CANÓNICO — fact-first, strict_mode, source: month_fact |
| `GET /ops/business-slice/weekly` | CANÓNICO — fact-first, strict_mode, source: week_fact |
| `GET /ops/business-slice/daily` | CANÓNICO — fact-first, strict_mode, source: day_fact |
| `GET /ops/business-slice/filters` | Estable, API-driven, sin lógica de negocio |
| `GET /ops/business-slice/coverage` | Trazable, lectura de cobertura sobre facts |
| `GET /ops/business-slice/coverage-summary` | Resumen estable |
| `GET /ops/omniview/freshness` | Gobernanza documentada, trazable RAW→facts |
| `GET /ops/serving/health` | Serving governance foundation |
| `GET /ops/serving/coverage` | Serving governance foundation |
| `GET /ops/serving/failures` | Serving governance foundation |
| `GET /ops/serving/runtime-risks` | Protección runtime |
| `GET /ops/observability/lineage` | Trazabilidad auditoría |

### 1.3 Componentes Frontend KEEP (8/21)

| Componente | Justificación |
|-----------|--------------|
| `BusinessSliceOmniviewMatrix.jsx` | Vista canónica, modo Vs Proy es default, estructura estable |
| `BusinessSliceOmniviewMatrixHeader.jsx` | Cabecera sticky con periodos, sin lógica pesada |
| `BusinessSliceOmniviewMatrixCell.jsx` | Celda bien encapsulada, delta/señal/trust overlay |
| `BusinessSliceOmniviewKpis.jsx` | KPI cards simples, lectura de facts |
| `OmniviewCommandHeader.jsx` | Cabecera unificada, modo selector estable |
| `OmniviewFreshnessGovernanceCard.jsx` | Gobernanza visual de frescura, lectura directa |
| `OmniviewFilterPrimitives.jsx` | Componentes de filtro reutilizables |
| `OmniviewErrorBoundary.jsx` | Protección de runtime, sin lógica de negocio |

### 1.4 Servicios Backend KEEP (10/24)

| Servicio | Justificación |
|----------|--------------|
| `business_slice_service.py` | Núcleo canónico, serving facts REAL, fact-first |
| `business_slice_omniview_service.py` | Omniview Matrix REAL-only, ServingPolicy strict |
| `business_slice_canonical_service.py` | Canonicalización nombres, determinístico |
| `omniview_freshness_governance_service.py` | Gobernanza frescura, sin fallback, trazable |
| `omniview_matrix_integrity_service.py` | Integridad matriz, diagnóstico |
| `omniview_serving_integrity_guard.py` | Validación post-migration |
| `omniview_semantics_service.py` | Semántica métricas (canonical_metrics, signal) |
| `business_slice_real_freshness_service.py` | Frescura facts, trazable |
| `serving_governance_service.py` | DB-layer gate, ServingPolicy enforcement |
| `control_loop_business_slice_resolve.py` | Resolución LOB determinística |

### 1.5 Data Sources KEEP (8/16)

| Data Source | Justificación |
|-------------|--------------|
| `ops.real_business_slice_month_fact` | CANÓNICO — serving fact mensual |
| `ops.real_business_slice_week_fact` | CANÓNICO — serving fact semanal |
| `ops.real_business_slice_day_fact` | CANÓNICO — serving fact diario |
| `ops.v_real_business_slice_month_serving` | CANÓNICO — vista serving con snapshot redirect |
| `ops.plan_trips_monthly` | CANÓNICO — plan mensual |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | CANÓNICO — PvR canonical |
| `ops.serving_registry` | GOVERNANCE — registro central |
| `ops.period_closure_registry` | GOVERNANCE — protección closed periods |

---

## 2. REBUILD — ÚTIL, PERO CON LÓGICA CONFUSA / RUNTIME PESADO / FUENTE DUDOSA

### 2.1 Métricas REBUILD (4/7)

| Métrica | Problema | Acción |
|---------|----------|--------|
| `avg_ticket` | Ratio recomputado en runtime. Debería ser serving column precalculada en fact table. | Precalcular `avg_ticket` en fact tables (day/week/month). Eliminar recomputación. |
| `trips_per_driver` | Derivado de active_drivers semi-aditivo. No control cross-grain. | Precalcular en fact tables o definir serving view dedicada. |
| `cancel_rate_pct` | Ratio recomputado. No almacenado. | Precalcular `cancel_rate_pct` en fact tables. |
| `commission_pct` | Ratio con doble dependencia (revenue proxy + total_fare). | Precalcular en fact tables. Auditoría de source de total_fare. |

### 2.2 Endpoints REBUILD (5/22)

| Endpoint | Problema | Acción |
|----------|----------|--------|
| `GET /ops/business-slice/omniview-projection` | Proyección usa `projection_expected_progress_service.py` (3210 líneas) con curva de estacionalidad compleja y fallbacks. | Simplificar pipeline: plan → seasonality_curve → projection_fact. Eliminar recomputación runtime. |
| `GET /ops/business-slice/omniview-momentum-drill` | Cálculos DoD/WoW/MoM on-the-fly. | Precalcular deltas en fact tables o serving views. |
| `GET /ops/omniview/weekly-serving-guardrails` | Lógica de guardrails acoplada a weekly serving. | Unificar con serving governance general. |
| `GET /ops/business-slice/real-freshness` | OK en estructura, pero depende de refresh job que NO corre en producción (`CT_SCHEDULER_ENABLED=false`). | Migrar a modelo pull-on-demand o CLI explícito con tracing. |
| `GET /ops/observability/freshness` | OK pero acoplado a serving registry que no cubre day_fact/week_fact. | Expandir coverage de freshness a todos los facts. |

### 2.3 Componentes Frontend REBUILD (6/21)

| Componente | Problema | Acción |
|-----------|----------|--------|
| `BusinessSliceOmniviewMatrixTable.jsx` (696 líneas) | Mezcla lógica de rendering con cálculos de delta y color. Acoplado a `omniviewMatrixUtils.js` (1208 líneas). | Separar rendering de lógica. Mover deltas al backend (serving columns). |
| `BusinessSliceOmniviewProjectionTable.jsx` | Depende de `projectionMatrixUtils.js` (937 líneas) con cálculos pesados en frontend. | Mover attainment/gap/signal al backend. |
| `OmniviewProjectionDrill.jsx` | Drill pesado, múltiples llamadas API. | Simplificar a single endpoint con datos precalculados. |
| `OmniviewTopDeviations.jsx` | Cálculo de desviaciones en frontend. | Mover al backend. |
| `BusinessSliceOmniviewReports.jsx` | Mezcla datos de múltiples endpoints. Filtros complejos. | Simplificar pipeline de datos. |
| `OperationalPriorityLayer.jsx` | Decision scores calculados en frontend. Motor de decisión es BACKLOG. | Mover a backend cuando Decision Engine se active. Por ahora, simplificar a diagnóstico. |

### 2.4 Servicios Backend REBUILD (6/24)

| Servicio | Problema | Acción |
|----------|----------|--------|
| `projection_expected_progress_service.py` (3210 líneas) | **MEGA-SERVICIO** — orquestra plan+real+serving+seasonality+YTD+pacing+trends. Demasiada responsabilidad. Curve confidence, fallback_level, projection_anomaly flags complejos. | Dividir en: `projection_fact_builder.py` (construcción), `projection_query_service.py` (lectura), `seasonality_curve_engine.py` (curvas, ya separado). Simplificar flags. |
| `revenue_quality_service.py` (311 líneas) | Umbrales proxy (80%/95%) hardcodeados. No expone `revenue_yego_final` vs `revenue_yego_net` dual-column audit. | Mover umbrales a config. Añadir audit de dual-column. |
| `plan_vs_real_service.py` (516 líneas) | Mantiene legacy view (`v_plan_vs_real_realkey_final`) junto a canonical. | Deprecar legacy path. Simplificar a solo canonical. |
| `real_vs_projection_service.py` (262 líneas) | Acoplado a `projection_upload_staging` y `projection_dimension_mapping`. | Migrar a projection serving fact como fuente única. |
| `seasonality_curve_engine.py` | Lógica de curva compleja. Poca trazabilidad de qué curva se usó para cada proyección. | Añadir `curve_method` y `curve_confidence` tracing en el serving fact. |
| `control_loop_plan_vs_real_service.py` | Duplica lógica de `plan_vs_real_service.py` con variantes. | Unificar en un solo Plan vs Real service canónico. |

### 2.5 Data Sources REBUILD (3/16)

| Data Source | Problema | Acción |
|-------------|----------|--------|
| `serving.omniview_projection_daily_fact` | Columnas de attainment/gap/confidence complejas. Mezcla daily y weekly en misma tabla. | Separar daily_projection_fact y weekly_projection_fact. Simplificar columnas de confidence. |
| `ops.mv_plan_vs_real_monthly_fact` (LEGACY) | Coexiste con `_canonical`. Confusión de cuál usar. | Eliminar legacy, renombrar canonical como default. |
| `ops.v_plan_vs_real_realkey_final` (LEGACY) | Sin homologación LOB. Confunde. | Drop (mover a DROP). |

---

## 3. DROP — DEPRECADO, DUPLICADO, CONFUSO O FALSOS DATOS

### 3.1 Componentes DROP (3/21)

| Componente | Razón |
|-----------|--------|
| `BusinessSliceOmniview.jsx` | **Evolution view.** Ya oculto (`VITE_OMNIVIEW_EVOLUTION_LEGACY=true`). Confunde usuarios. Revenue aparece incompleto en esta vista. Eliminar de UI productiva. |
| `BusinessSliceView.jsx` | **Business Slice legacy.** Ya oculto. Reemplazado por Matrix. Drop. |
| `BusinessSliceOmniviewTable.jsx` | **Tabla jerárquica legacy.** Solo usada por Evolution view. Drop. |

### 3.2 Endpoints DROP (3/22)

| Endpoint | Razón |
|----------|--------|
| `GET /ops/business-slice/omniview` | **Legacy rollup endpoint.** Usa `V_RESOLVED` como fuente (prohibida en strict_mode). Ya no es ruta principal de UI. Drop. |
| `GET /ops/real-lob/monthly` (v1) | Reemplazado por `/monthly-v2`. Drop. |
| `GET /ops/real-lob/weekly` (v1) | Reemplazado por `/weekly-v2`. Drop. |

### 3.3 Servicios DROP (3/24)

| Servicio | Razón |
|----------|--------|
| `real_lob_service.py` (v1) | Reemplazado por `real_lob_service_v2.py`. Drop. |
| `real_lob_filters_service.py` (v1) | Reemplazado por v2. Drop. |
| Proyección suggestion/decision services en modo actual | `projection_suggestion_engine_service.py`, `projection_decision_policy_engine.py`, `projection_contextual_suggestion_service.py` — lógica de sugerencia/decisión prematura, mezclada con serving. Mover a BACKLOG o reescribir cuando esos motores se activen. |

### 3.4 Data Sources DROP (5/16)

| Data Source | Razón |
|-------------|--------|
| `ops.v_real_trips_business_slice_resolved` | Solo reconciliación. Marcado como FORBIDDEN_SERVING_SOURCE. |
| `ops.v_real_trips_enriched_base` | Solo build pipeline. Marcado como FORBIDDEN_SERVING_SOURCE. |
| `ops.v_plan_vs_real_realkey_final` | Legacy sin LOB homologation. Reemplazado por `_canonical`. |
| `ops.v_plan_business_slice_join_stub` | Stub temporal. Ya no necesario. |
| `ops.v_business_slice_unmatched_trips` | Coverage debugging. No serving. Mantener solo para diagnóstico offline. |

---

## 4. BACKLOG — VALIOSO, PERO PREMATURO PARA LA FASE ACTUAL

### 4.1 Componentes BACKLOG (4/21)

| Componente | Razón |
|-----------|--------|
| `BusinessSliceInsightsPanel.jsx` | Insights requieren Suggestion Engine (BLOQUEADO). |
| `BusinessSliceInsightSettings.jsx` | Config insights prematura. |
| `OmniviewPriorityPanel.jsx` | Prioridades operativas requieren Decision Engine (BLOQUEADO). |
| `OmniviewProjectionDrill.jsx` | Drill avanzado requiere Forecast Engine (BLOQUEADO) para ser preciso. Versión actual es diagnóstico básico. |

### 4.2 Endpoints BACKLOG (2/22)

| Endpoint | Razón |
|----------|--------|
| `GET /ops/decision-readiness` | Decision Engine está BLOQUEADO. |
| `GET /ops/decision-signal` | Decision Engine está BLOQUEADO. |

### 4.3 Servicios BACKLOG (5/24)

| Servicio | Razón |
|----------|--------|
| `projection_suggestion_engine_service.py` | Suggestion Engine BLOQUEADO |
| `projection_decision_policy_engine.py` | Decision Engine BLOQUEADO |
| `projection_contextual_suggestion_service.py` | Suggestion Engine BLOQUEADO |
| `global_decision_intelligence_service.py` | Decision Engine BLOQUEADO |
| `projection_ytd_alerts_service.py` | YTD alerts requieren Forecast para ser accionables |

---

## 5. MATRIZ DE DECISIÓN

```
                    KEEP        REBUILD     DROP        BACKLOG
─────────────────────────────────────────────────────────────────
MÉTRICAS (7)        trips        avg_ticket   —           —
                    revenue      tpd
                    drivers      cancel_pct
                                 commission

ENDPOINTS (22)      12           5            3           2

COMPONENTES (21)    8            6            3           4

SERVICIOS (24)      10           6            3           5

DATA SOURCES (16)   8            3            5           0
─────────────────────────────────────────────────────────────────
TOTAL (90)          41 (46%)    24 (27%)    14 (16%)    11 (12%)
```

---

## 6. ACCIONES PRIORITARIAS POR CLASE

### KEEP → Proteger
- No modificar lógica
- Mantener ServingPolicy strict_mode
- Monitorear frescura
- Documentar contratos API

### REBUILD → Planificar OV2-B
1. Precalcular ratios (avg_ticket, tpd, cancel_rate_pct, commission_pct) en fact tables
2. Dividir `projection_expected_progress_service.py` en 3 servicios
3. Mover deltas/cálculos pesados de frontend a backend
4. Unificar Plan vs Real en un solo servicio canónico
5. Separar `serving.omniview_projection_daily_fact` en daily/weekly
6. Eliminar dual-column revenue_yego_final vs revenue_yego_net

### DROP → Ejecutar en OV2-A o planificar OV2-C
1. Eliminar endpoint `/ops/business-slice/omniview` (legacy rollup)
2. Eliminar componentes Evolution (ya ocultos, remover código)
3. Eliminar data sources legacy
4. Eliminar servicios V1 reemplazados

### BACKLOG → No tocar hasta fase correspondiente
1. Mantener código existente pero no expandir
2. Marcar con flag `BACKLOG` en código
3. No exponer en UI productiva
