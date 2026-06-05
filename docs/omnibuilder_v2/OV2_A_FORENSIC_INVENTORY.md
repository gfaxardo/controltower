# OV2-A — INVENTARIO FORENSE OMNIVIEW / OMNIBUILDER V1

> **Fase:** OV2-A — Blindaje Lógico OV2  
> **Fecha:** 2026-06-04  
> **Estado:** READ-ONLY — No modifica producción  
> **Propósito:** Inventario completo de Omniview/OmniBuilder actual para decidir KEEP/REBUILD/DROP/BACKLOG

---

## 1. FRONTEND — PÁGINAS OMNIVIEW

| Ruta | Componente | Modo | Estado |
|------|-----------|------|--------|
| `/operacion/omniview-matrix` | `BusinessSliceOmniviewMatrix` | Vs Proy (Canónico) | ACTIVO, default |
| `/operacion/omniview` | `BusinessSliceOmniview` | Evolution (Legacy) | OCULTO (`VITE_OMNIVIEW_EVOLUTION_LEGACY=true`) |
| `/operacion/business-slice` | `BusinessSliceView` | Business Slice Legacy | OCULTO |
| `/operacion/reportes` | `BusinessSliceOmniviewReports` | Reportes/Gráficos | ACTIVO |
| `/operacion/control-loop-plan-vs-real` | `ControlLoopPlanVsRealView` | Vs Proy PvR | ACTIVO |

---

## 2. FRONTEND — COMPONENTES OMNIVIEW

### Core Views (5 archivos)
| Archivo | Líneas | Rol |
|---------|--------|-----|
| `BusinessSliceOmniviewMatrix.jsx` | ~1200+ | Vista canónica principal (Vs Proy) |
| `BusinessSliceOmniview.jsx` | ~800+ | Vista legacy (Evolution) |
| `BusinessSliceOmniviewReports.jsx` | ~900+ | Reportes con ECharts |
| `BusinessSliceView.jsx` | ~400+ | Vista business slice legacy |
| `BusinessSliceOmniviewKpis.jsx` | ~100+ | Franja KPI superior |

### Matriz y Celdas (4 archivos)
| Archivo | Líneas | Rol |
|---------|--------|-----|
| `BusinessSliceOmniviewMatrixTable.jsx` | 696 | Tabla matriz principal |
| `BusinessSliceOmniviewMatrixHeader.jsx` | ~150+ | Cabecera sticky con periodos |
| `BusinessSliceOmniviewMatrixCell.jsx` | 499 | Celda individual con delta/señal/trust |
| `BusinessSliceOmniviewInspector.jsx` | ~200+ | Panel inspector de celda |

### Proyección (4 archivos)
| Archivo | Líneas | Rol |
|---------|--------|-----|
| `BusinessSliceOmniviewProjectionTable.jsx` | ~200+ | Tabla proyección |
| `BusinessSliceOmniviewProjectionCell.jsx` | ~200+ | Celda proyección |
| `OmniviewProjectionDrill.jsx` | ~300+ | Drill lateral |
| `OmniviewTopDeviations.jsx` | ~150+ | Top desviaciones |

### Subdirectorio omniview/ (24 archivos)
| Archivo | Líneas | Rol |
|---------|--------|-----|
| `omniviewMatrixUtils.js` | 1208 | Utilidades transformación matriz (DELTAS, TOTALS, árbol) |
| `projectionMatrixUtils.js` | 937 | Utilidades proyección (DELTAS, contratos, agregación) |
| `insightEngine.js` | ~300+ | Detección de insights |
| `alertingEngine.js` | ~200+ | Motor de alertas |
| `rootCauseEngine.js` | ~200+ | Motor causa raíz |
| `OmniviewCommandHeader.jsx` | ~200+ | Cabecera comando unificada |
| `OmniviewModeSelector.jsx` | ~100+ | Selector Data/Insight |
| `OmniviewFreshnessGovernanceCard.jsx` | ~150+ | Gobernanza frescura |
| `OmniviewMomentumPriorityStrip.jsx` | ~100+ | Strip momentum |
| `OmniviewMomentumDrillChart.jsx` | ~150+ | Gráfico drill momentum |
| `OperationalPriorityLayer.jsx` | ~250+ | Capa prioridad operativa |
| Otros 13 archivos | — | Constantes, temas, filtros, validación, diagnóstico |

---

## 3. FRONTEND — HOOKS / UTILIDADES

Sin hooks custom — solo React built-ins (`useState`, `useEffect`, `useMemo`, `useCallback`, `useRef`, `memo`).

Utilidades clave importadas como funciones planas:
- `computeDeltas`, `computeTotalsDeltas` — `omniviewMatrixUtils.js`
- `computeProjectionDeltas`, `computeProjectionTotalsDeltas` — `projectionMatrixUtils.js`
- `computeAlertsForMatrix` — `alertingEngine.js`
- `detectInsights`, `buildInsightCellMap` — `insightEngine.js`
- `loadPersistedState`, `persistState` — localStorage para filtros

---

## 4. FRONTEND — SERVICIOS API CONSUMIDOS

Todas las llamadas en `frontend/src/services/api.js` (1329 líneas, ~75 funciones).

| Función API | Endpoint | Usado por |
|------------|----------|-----------|
| `getBusinessSliceFilters` | `GET /ops/business-slice/filters` | Matrix, Reports |
| `getBusinessSliceMonthly` | `GET /ops/business-slice/monthly` | Matrix, Reports |
| `getBusinessSliceWeekly` | `GET /ops/business-slice/weekly` | Matrix, Reports |
| `getBusinessSliceDaily` | `GET /ops/business-slice/daily` | Matrix, Reports |
| `getBusinessSliceOmniview` | `GET /ops/business-slice/omniview` | Legacy Omniview (rollups) |
| `getBusinessSliceCoverage` | `GET /ops/business-slice/coverage` | Matrix |
| `getBusinessSliceCoverageSummary` | `GET /ops/business-slice/coverage-summary` | Matrix, Reports |
| `getOmniviewProjection` | `GET /ops/business-slice/omniview-projection` | Matrix (Vs Proy) |
| `getOmniviewFreshnessGovernance` | `GET /ops/omniview/freshness` | Matrix |
| `getBusinessSliceRealFreshness` | `GET /ops/business-slice/real-freshness` | Matrix (weekly/daily) |
| `getDataFreshnessGlobal` | `GET /ops/data-freshness/global` | Matrix banner |
| `getOmniviewMomentumDrill` | `GET /ops/business-slice/omniview-momentum-drill` | MomentumDrillChart |
| `getMatrixOperationalTrust` | `GET /ops/business-slice/matrix-operational-trust` | Matrix |
| `getServingPlanVersions` | `GET /ops/business-slice/omniview-projection/serving-plan-versions` | Matrix |
| `fetchKpiConsistencyAudit` | `GET /ops/kpi-consistency-audit` | — |
| `fetchRollupMismatchAudit` | `GET /ops/rollup-mismatch-audit` | — |
| `getOwnershipServingMonthly` | `GET /ops/ownership-serving/monthly` | Matrix (Ownership) |

---

## 5. FRONTEND — FILTROS USADOS

| Filtro | Tipo | Disponible en |
|--------|------|--------------|
| Grain | Mensual/Semanal/Diario | Matrix, Reports, Legacy |
| País | Dropdown (API-driven) | Matrix, Reports, Legacy |
| Ciudad | Dropdown (filtrado por país) | Matrix, Reports, Legacy |
| Tajada (Business Slice) | Dropdown (API-driven) | Matrix, Reports, Legacy |
| Flota | Dropdown (solo mensual) | Matrix, Reports, Legacy |
| Año | Dropdown (2025-2026) | Matrix, Reports, Legacy |
| Mes | Dropdown (Ene-Dic/Todos) | Matrix, Reports |
| Semana ISO | Info label | Matrix |
| Año completo | Toggle (weekly) | Matrix |
| Subflotas | Checkbox | Matrix, Reports, Legacy |
| Weekday focus | Día selector (daily) | Matrix |
| Sort | alpha/impact/trips/rev/drivers/tpd | Matrix |
| Density | Compact/Cómodo | Matrix |
| Zoom | 80%-130% | Matrix |
| Foco mode | Toggle | Matrix |
| Insight mode | Data/Insight | Matrix |
| Perspective | Oper/Owner | Matrix |
| Evolución/Vs Proy | Toggle (LEGACY flag) | Matrix |

---

## 6. FRONTEND — KPIs RENDERIZADOS

### Evolution Mode (7 KPIs — `omniviewMatrixUtils.js`)
| key | Label | Unidad | Display |
|-----|-------|--------|---------|
| `trips_completed` | Viajes | number | Raw |
| `revenue_yego_net` | Revenue | currency | Currency |
| `active_drivers` | Conductores | number | Raw |
| `avg_ticket` | Ticket | currency | Currency |
| `trips_per_driver` | TPD | number | Raw |
| `cancel_rate_pct` | Cancel % | ratio | % |
| `commission_pct` | Comm % | ratio | % |

### Vs Proyección Mode (3 KPIs — `projectionMatrixUtils.js`)
| key | Label |
|-----|-------|
| `trips_completed` | Viajes |
| `revenue_yego_net` | Revenue |
| `active_drivers` | Conductores |

### Coverage (Matrix + Reports)
| Métrica | Descripción |
|---------|-------------|
| `coverage_pct` | % cobertura |
| `mapped_trips` | Viajes mapeados |
| `unmapped_trips` | No mapeados |
| `total_trips` | Total viajes |

---

## 7. FRONTEND — TABLAS / MATRICES / GRILLAS

| Componente | Tipo | Estructura |
|-----------|------|-----------|
| `BusinessSliceOmniviewMatrixTable` | Matriz 2D | Cities × Lines × Periods, colapsable |
| `BusinessSliceOmniviewTable` | Árbol jerárquico | País → Ciudad → Tajada → Flota, expandible |
| `BusinessSliceOmniviewMatrixHeader` | Cabecera sticky | Columnas de periodo con badges |
| `BusinessSliceOmniviewMatrixCell` | Celda individual | Delta + señal + trust overlay |
| `BusinessSliceOmniviewProjectionTable` | Tabla proyección | Plan vs Real con attainment |

---

## 8. BACKEND — ROUTERS / ENDPOINTS OMNIVIEW

### Router: `ops.py` (3300+ líneas)

#### Business Slice (Omniview-serving)
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/business-slice/omniview-projection/serving-plan-versions` | `business_slice_serving_plan_versions` |
| GET | `/ops/business-slice/omniview-projection` | `business_slice_omniview_projection` |
| GET | `/ops/business-slice/real-freshness` | `business_slice_real_freshness_endpoint` |
| POST | `/ops/business-slice/real-refresh-omniview` | `business_slice_real_refresh_omniview_endpoint` |
| GET | `/ops/business-slice/omniview-momentum-drill` | `omniview_momentum_drill_endpoint` |

#### Omniview Freshness & Governance
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/omniview/freshness` | `omniview_freshness_governance_endpoint` |
| GET | `/ops/omniview/weekly-serving-guardrails` | `omniview_weekly_serving_guardrails_endpoint` |
| POST | `/ops/omniview/refresh` | `omniview_refresh_remediation_endpoint` |

#### Serving Governance (Fase 1H.1)
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/serving/health` | `serving_health` |
| GET | `/ops/serving/coverage` | `serving_coverage` |
| GET | `/ops/serving/failures` | `serving_failures` |
| GET | `/ops/serving/runtime-risks` | `serving_runtime_risks` |
| GET | `/ops/serving/integrity` | `serving_integrity` |

#### KPI Audits
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/kpi-consistency-audit` | `kpi_consistency_audit_endpoint` |
| GET | `/ops/rollup-mismatch-audit` | `rollup_mismatch_audit_endpoint` |

### Router: `real_vs_projection.py`
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/real-vs-projection/overview` | `real_vs_projection_overview` |
| GET | `/ops/real-vs-projection/dimensions` | `real_vs_projection_dimensions` |
| GET | `/ops/real-vs-projection/mapping-coverage` | `real_vs_projection_mapping_coverage` |
| GET | `/ops/real-vs-projection/real-metrics` | `real_vs_projection_real_metrics` |
| GET | `/ops/real-vs-projection/projection-template-contract` | `real_vs_projection_template_contract` |

### Router: `observability.py`
| Método | Path | Handler |
|--------|------|---------|
| GET | `/ops/observability/overview` | `observability_overview` |
| GET | `/ops/observability/lineage` | `observability_lineage` |
| GET | `/ops/observability/freshness` | `observability_freshness` |

---

## 9. BACKEND — SERVICES OMNIVIEW

### Núcleo Canónico (KEEP candidates)
| Servicio | Líneas | Rol |
|----------|--------|-----|
| `business_slice_service.py` | 3155 | Serving facts REAL (day/week/month) — fuente canónica |
| `business_slice_omniview_service.py` | 1174 | Omniview Matrix (REAL-only, fact-first, ServingPolicy strict) |
| `business_slice_canonical_service.py` | ~200+ | Canonicalización nombres business slice |
| `omniview_freshness_governance_service.py` | 432 | Gobernanza frescura RAW→day→week→month→projection |
| `omniview_matrix_integrity_service.py` | ~200+ | Integridad matriz + trust operacional |
| `omniview_momentum_drill_service.py` | ~100+ | Drill momentum DoD/WoW/MoM |
| `omniview_semantics_service.py` | ~150+ | Semántica métricas (canonical_metrics, comparison_basis, signal) |
| `omniview_serving_integrity_guard.py` | ~100+ | Post-migration serving integrity validation |
| `omniview_playbooks.py` | ~100+ | Playbooks operacionales |

### Proyección (REBUILD candidates)
| Servicio | Líneas | Rol |
|----------|--------|-----|
| `projection_expected_progress_service.py` | 3210 | **Orquestrador proyección** — plan+real+serving+seasonality |
| `projection_integrity_service.py` | ~200+ | Estado integridad proyección |
| `projection_ytd_period_service.py` | ~200+ | Cómputo YTD |
| `projection_ytd_alerts_service.py` | ~200+ | Alertas YTD |
| `seasonality_curve_engine.py` | ~300+ | Curvas de estacionalidad |

### Inteligencia (BACKLOG candidates)
| Servicio | Líneas | Rol |
|----------|--------|-----|
| `projection_contextual_suggestion_service.py` | ~200+ | Sugerencias contextuales |
| `projection_decision_policy_engine.py` | ~200+ | Políticas decisión/manual adjustment |
| `projection_suggestion_engine_service.py` | ~300+ | Motor sugerencias proyección |
| `global_decision_intelligence_service.py` | ~200+ | Inteligencia decisión global |

### Revenue (REBUILD candidates)
| Servicio | Líneas | Rol |
|----------|--------|-----|
| `revenue_quality_service.py` | 311 | Calidad revenue (NaN, proxy, MoM drift) |
| `real_margin_quality_service.py` | ~300+ | Auditoría margen real |
| `plan_vs_real_service.py` | 516 | Plan vs Real (canonical + legacy) |
| `real_vs_projection_service.py` | 262 | Real vs Proyección (Fase 2A) |

### Control Loop (KEEP + REBUILD)
| Servicio | Líneas | Rol |
|----------|--------|-----|
| `control_loop_business_slice_resolve.py` | ~150+ | Resolución LOB→business slice |
| `control_loop_projection_parser.py` | ~200+ | Parser Excel proyección |
| `control_loop_upload_service.py` | ~200+ | Upload proyección |
| `control_loop_plan_vs_real_service.py` | ~200+ | Plan vs Real control loop |

---

## 10. BACKEND — DATA SOURCES (TABLAS / VIEWS / MVs)

### Serving Facts — Omniview CANÓNICO
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `ops.real_business_slice_month_fact` | TABLE | monthly | ACTIVO |
| `ops.real_business_slice_week_fact` | TABLE | weekly | ACTIVO |
| `ops.real_business_slice_day_fact` | TABLE | daily | ACTIVO |
| `ops.v_real_business_slice_month_serving` | VIEW | monthly | ACTIVO (snapshot redirect) |
| `ops.v_real_trips_enriched_base` | VIEW | trip | LEGACY (no serving) |

### Serving Facts — Proyección
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `serving.omniview_projection_daily_fact` | TABLE | daily/weekly | ACTIVO |

### Plan vs Real
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `ops.plan_trips_monthly` | TABLE | monthly | CANÓNICO |
| `ops.mv_plan_vs_real_monthly_fact` | MV | monthly | LEGACY |
| `ops.mv_plan_vs_real_monthly_fact_canonical` | MV | monthly | CANÓNICO |
| `ops.v_plan_vs_real_realkey_final` | VIEW | monthly | LEGACY |
| `ops.v_plan_vs_real_realkey_canonical` | VIEW | monthly | CANÓNICO |

### Real LOB
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `ops.v_real_trip_fact_v2` | VIEW | trip | ACTIVO (con revenue_source) |
| `ops.mv_real_trips_monthly` | MV | monthly | ACTIVO |
| `ops.mv_real_monthly_canonical_hist` | MV | monthly | CANÓNICO |

### Revenue
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `ops.real_margin_quality_audit` | TABLE | audit | ACTIVO |

### Governance
| Identificador | Tipo | Grain | Estado |
|--------------|------|-------|--------|
| `ops.serving_registry` | TABLE | — | ACTIVO |
| `ops.serving_refresh_log` | TABLE | — | ACTIVO |
| `ops.refresh_run_log` | TABLE | — | ACTIVO |
| `ops.period_closure_registry` | TABLE | — | ACTIVO |

### RAW Sources
| Identificador | Schema |
|--------------|--------|
| `public.trips_2025` / `public.trips_2026` | RAW |
| `public.module_weekly_billing` | RAW (Yego Pro) |
| `public.drivers` | RAW |
| `dim.dim_park` | DIM |
| `bi.ingestion_status` | META |

---

## 11. MÉTRICAS — FICHAS COMPLETAS

### M1: trips_completed
| Campo | Valor |
|-------|-------|
| **metric_id** | `trips_completed` |
| **Nombre visual** | Viajes / Trips |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` → `get_business_slice_omniview()` |
| **Repo/Query** | Directo a `ops.real_business_slice_{day,week,month}_fact` |
| **Source table** | `ops.real_business_slice_month_fact` / `_week_fact` / `_day_fact` |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet, year, month, weekday |
| **Fórmula** | `SUM(trips_completed)` sobre fact, `FILTER (WHERE completed_flag)` |
| **Plan/Real** | Solo REAL (matriz Omniview); Plan via PvR separado |
| **Fallback** | No — ServingPolicy strict_mode, fact-first |
| **Runtime pesado** | No — lectura directa de fact table |
| **Lineage posible** | Sí: RAW trips → enriched_base → day_fact → week_fact → month_fact |
| **Confianza** | ALTA — additive, serving fact, cross-grain exact_sum |

### M2: revenue_yego_net
| Campo | Valor |
|-------|-------|
| **metric_id** | `revenue_yego_net` |
| **Nombre visual** | Revenue / Rev. |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | `ops.real_business_slice_month_fact` (revenue_yego_final) |
| **Source table** | `ops.real_business_slice_month_fact` |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet, year, month |
| **Fórmula** | `SUM(ABS(NULLIF(comision_empresa_asociada, 0)))` con proxy fallback |
| **Plan/Real** | Solo REAL |
| **Fallback** | **SÍ** — `COALESCE(revenue_yego_real, revenue_yego_proxy)`; proxy = ticket * 3% default |
| **Runtime pesado** | No — precalculado en fact table |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA-ALTA — proxy fallback activo, dual column (revenue_yego_final vs _net) |

### M3: active_drivers
| Campo | Valor |
|-------|-------|
| **metric_id** | `active_drivers` |
| **Nombre visual** | Conductores / Active Drivers |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | `ops.real_business_slice_{day,week,month}_fact` |
| **Source table** | Fact tables |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet, year, month |
| **Fórmula** | `COUNT(DISTINCT driver_uuid)` — SEMI_ADDITIVE |
| **Plan/Real** | Solo REAL |
| **Fallback** | No |
| **Runtime pesado** | No |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA — semi-aditivo, no comparable cross-grain directamente |

### M4: avg_ticket
| Campo | Valor |
|-------|-------|
| **metric_id** | `avg_ticket` |
| **Nombre visual** | Ticket / Avg Ticket |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | Fact tables |
| **Source table** | Fact tables |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet |
| **Fórmula** | `SUM(revenue) / SUM(trips)` — NON_ADDITIVE_RATIO |
| **Plan/Real** | Solo REAL |
| **Fallback** | No directo, hereda fallback de revenue |
| **Runtime pesado** | **SÍ** — recomputado en cada query de ratio |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA — ratio recomputado, sensibilidad a fallback revenue |

### M5: trips_per_driver
| Campo | Valor |
|-------|-------|
| **metric_id** | `trips_per_driver` |
| **Nombre visual** | TPD / Trips per Driver |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | Fact tables |
| **Source table** | Fact tables |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet |
| **Fórmula** | `trips_completed / active_drivers` — DERIVED_RATIO |
| **Plan/Real** | Solo REAL |
| **Fallback** | No directo |
| **Runtime pesado** | **SÍ** — recomputado cada vez |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA — derivado; ruido de active_drivers semi-aditivo |

### M6: cancel_rate_pct
| Campo | Valor |
|-------|-------|
| **metric_id** | `cancel_rate_pct` |
| **Nombre visual** | Cancel % |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | Fact tables |
| **Source table** | Fact tables |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet |
| **Fórmula** | `SUM(trips_cancelled) / (SUM(trips_completed) + SUM(trips_cancelled))` |
| **Plan/Real** | Solo REAL |
| **Fallback** | No |
| **Runtime pesado** | **SÍ** — recomputado |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA — ratio recomputado |

### M7: commission_pct
| Campo | Valor |
|-------|-------|
| **metric_id** | `commission_pct` |
| **Nombre visual** | Comm % |
| **Endpoint** | `GET /ops/business-slice/{monthly,weekly,daily}` |
| **Service** | `business_slice_omniview_service.py` |
| **Repo/Query** | Fact tables |
| **Source table** | Fact tables |
| **Grain** | day / week / month |
| **Filtros** | country, city, business_slice, fleet |
| **Fórmula** | `SUM(revenue) / SUM(total_fare)` — NON_ADDITIVE_RATIO |
| **Plan/Real** | Solo REAL |
| **Fallback** | Hereda fallback revenue |
| **Runtime pesado** | **SÍ** — recomputado |
| **Lineage posible** | Sí |
| **Confianza** | MEDIA-BAJA — doble dependencia proxy revenue + ratio |

---

## 12. SCHEDULER / REFRESH

| Job | Schedule | Función |
|-----|----------|---------|
| `serving_fact_daily_refresh` | Daily 05:00 UTC | Daily+weekly+monthly serving facts |
| `omniview_business_slice_real_refresh` | Configurable | day/week/month facts (2 meses) |
| `omniview_real_data_watchdog` | Cada N minutos | Freshness monitoring |

**Nota crítica:** `CT_SCHEDULER_ENABLED=false` en producción. Refreshes son manual/CLI.

---

## 13. SQL FILES RELEVANTES (55+ archivos)

- `phase1g3_omniview_projection_serving_layer.sql` — Serving table projection (125 líneas)
- `phase1h1_serving_governance.sql` — Serving governance (70 líneas)
- `paso2_homologacion_lob_e2e.sql` — LOB homologation
- `paso3_plan_canon_and_plan_vs_real.sql` — Plan canonical + PvR
- `driver_lifecycle_build.sql` — Driver lifecycle
- `driver_serving_facts_build.sql` — Driver serving facts
- `yego_pro_profitability_serving_views.sql` — 8 MVs Yego Pro (428 líneas)
- Rollbacks en `backend/sql/rollback/`

---

**Total inventariado:**
- **Frontend:** 7 páginas, 53+ componentes top-level, 24 sub-componentes omniview/, 17 funciones API, 18 filtros, 7 KPIs, 4 tablas/matrices
- **Backend:** 25 endpoints Omniview, 22 servicios Omniview, 30+ data sources, 8 métricas con ficha completa
- **DB:** 3 serving facts, 1 proyección fact, 4 PvR views, 15+ serving registry entries, 3 scheduler jobs
- **SQL:** 55+ archivos SQL, 6 rollback scripts
- **Docs:** 22 root-level .md, 8 docs/architecture, 4 docs/control_foundation
