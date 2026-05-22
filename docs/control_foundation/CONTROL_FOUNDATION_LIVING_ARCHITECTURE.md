# CONTROL FOUNDATION — LIVING ARCHITECTURE

**Última actualización:** 2026-05-21 (Fase 1G.2 Closure)
**Motor canónico:** Control Foundation (#1 de 9)
**Estado:** ACTIVE → CONDITIONAL GO para cierre

---

## 1. FUENTES CANÓNICAS DE REAL

### 1.1 Backbone horario (hourly-first)

```
v_real_trip_fact_v2 → mv_real_lob_hour_v2 → real_business_slice_day_fact → week_fact → month_fact
```

### 1.2 Tablas FACT (Business Slice)

| Tabla | Schema | Grain | Fuente |
|-------|--------|-------|--------|
| `real_business_slice_day_fact` | ops | daily | `v_real_trips_enriched_base` → `v_real_trips_business_slice_resolved` |
| `real_business_slice_week_fact` | ops | weekly (ISO) | ROLLUP desde `day_fact` |
| `real_business_slice_month_fact` | ops | monthly | `v_real_trips_enriched_base` → resolución incremental |

### 1.3 Vista de serving

| Vista | Propósito |
|-------|-----------|
| `v_real_business_slice_month_serving` | UNION de snapshots activos + working_fact para períodos abiertos |

### 1.4 KPIs canónicos (7 visibles en Omniview)

| KPI | Tipo | Agregación |
|-----|------|-----------|
| `trips_completed` | ADDITIVE | SUM |
| `trips_cancelled` | ADDITIVE | SUM |
| `active_drivers` | SEMI_ADDITIVE | COUNT DISTINCT |
| `avg_ticket` | RATIO | AVG ponderado |
| `revenue_yego_net` | ADDITIVE | SUM |
| `commission_pct` | RATIO | Recomputed from totals |
| `cancel_rate_pct` | RATIO | Recomputed from totals |
| `trips_per_driver` | DERIVED_RATIO | trips_completed / active_drivers |

---

## 2. FUENTES CANÓNICAS DE PLAN

| Tabla | Schema | Nota |
|-------|--------|------|
| `plan_trips_monthly` | ops | Plan cargado vía upload templates (Ruta27, simple, control_loop) |
| `v_plan_trips_monthly_latest` | ops | Vista que resuelve la última versión activa |
| `plan_versions_metadata` | plan | Metadatos de versiones (plan_version_key, display_name, created_at) |

---

## 3. GRAINS OFICIALES

| Grain | Backend field | Período | ISO-aware |
|-------|--------------|---------|-----------|
| `monthly` | `month` | Primer día del mes (YYYY-MM-01) | No |
| `weekly` | `week_start` | Lunes de semana ISO | Sí |
| `daily` | `trip_date` | Fecha calendario | No |

**Reglas:**
- `weekly` y `daily` requieren `country` (filtro obligatorio para limitar scope).
- `daily_window_days <= 120` (guardrail en Omniview).
- `weekly` → comparativo WoW (lunes vs lunes - 7 días).
- `daily` → comparativo DoW-7 (mismo día de semana anterior).

---

## 4. ENDPOINTS OFICIALES

### 4.1 Omniview Matrix (Business Slice)

| Método | Endpoint | Grain |
|--------|----------|-------|
| GET | `/ops/business-slice/monthly` | monthly |
| GET | `/ops/business-slice/weekly` | weekly |
| GET | `/ops/business-slice/daily` | daily |
| GET | `/ops/business-slice/omniview` | any (unified) |
| GET | `/ops/business-slice/filters` | metadata |
| GET | `/ops/business-slice/coverage` | cobertura |
| GET | `/ops/business-slice/coverage-summary` | resumen cobertura |
| GET | `/ops/business-slice/omniview-projection` | proyección |

### 4.2 Plan vs Real

| Método | Endpoint | Grain |
|--------|----------|-------|
| GET | `/ops/plan-vs-real/monthly` | monthly |
| GET | `/ops/plan-vs-real/alerts` | monthly (alertas) |
| GET | `/ops/plan/monthly` | monthly (Plan split) |
| GET | `/ops/real/monthly` | monthly (Real split) |
| GET | `/ops/compare/overlap-monthly` | monthly (overlap) |

### 4.3 Real LOB

| Método | Endpoint | Grain |
|--------|----------|-------|
| GET | `/ops/real-lob/monthly-v2` | monthly (canonical) |
| GET | `/ops/real-lob/weekly-v2` | weekly (canonical) |
| GET | `/ops/real-lob/v2/data` | any |
| GET | `/ops/real-lob/daily/summary` | daily |
| GET | `/ops/real-lob/daily/comparative` | daily (DoD/WoW/4w) |
| GET | `/ops/real-lob/comparatives/weekly` | weekly (WoW) |
| GET | `/ops/real-lob/comparatives/monthly` | monthly (MoM) |

### 4.4 Freshness & Data Trust

| Método | Endpoint |
|--------|----------|
| GET | `/ops/data-freshness/global` |
| GET | `/ops/data-pipeline-health` |
| GET | `/ops/business-slice/real-freshness` |
| GET | `/ops/business-slice/fact-status` |
| GET | `/ops/data-trust` |
| GET | `/ops/decision-signal` |
| GET | `/ops/decision-signal/summary` |
| GET | `/ops/business-slice/matrix-operational-trust` |

### 4.5 Plan Versioning

| Método | Endpoint |
|--------|----------|
| GET | `/plan/versions` |
| PATCH | `/plan/versions/{plan_version_key}` |
| POST | `/plan/upload_simple` |
| POST | `/plan/upload_ruta27_ui` |
| POST | `/plan/upload_control_loop_projection` |
| GET | `/plan/unmapped-summary` |
| GET | `/plan/mapping-audit` |
| GET | `/plan/reconciliation-audit` |

---

## 5. ENDPOINTS LEGACY / DEPRECATED

| Endpoint | Estado | Migración |
|----------|--------|-----------|
| `/plan/upload` | DEPRECATED | Usar `/plan/upload_simple` o `/plan/upload_ruta27_ui` |
| `/ops/real-lob/monthly` (v1) | LEGACY | Migrar a `/ops/real-lob/monthly-v2` |
| `/ops/real-lob/weekly` (v1) | LEGACY | Migrar a `/ops/real-lob/weekly-v2` |
| `/ops/real-drill/*` | LEGACY | Migrar a Real LOB v2 PRO |
| `v_plan_vs_real_realkey_final` | LEGACY | Usar `mv_plan_vs_real_monthly_fact_canonical` |

---

## 6. SERVICIOS PRINCIPALES

| Servicio | Archivo | Responsabilidad |
|----------|---------|----------------|
| Business Slice | `business_slice_service.py` | Lecturas REAL desde FACT tables |
| Business Slice Omniview | `business_slice_omniview_service.py` | Omniview canónico (REAL only) |
| Business Slice Canonical | `business_slice_canonical_service.py` | Normalización y agregación de slices |
| Plan vs Real | `plan_vs_real_service.py` | Comparación Plan vs Real mensual |
| Plan Real Split | `plan_real_split_service.py` | Split Real/Plan/Overlap |
| Data Freshness | `data_freshness_service.py` | Auditoría de frescura de datos |
| Data Trust | `data_trust_service.py` | Capa de confianza (OK/WARNING/BLOCKED) |
| Confidence Engine | `confidence_engine.py` | Scores de confianza |
| Decision Engine | `decision_engine.py` | Señales de decisión |
| Comparative Metrics | `comparative_metrics_service.py` | Comparativos WoW/MoM |
| Period Semantics | `period_semantics_service.py` | Semántica de períodos abiertos/cerrados |
| Period Closure | `period_closure_service.py` | Cierre de períodos con QA |
| Refresh Control | `refresh_control_service.py` | Guard de refresh con advisory locks |
| Serving Guardrails | `serving_guardrails.py` | Hard enforcement de fuentes |
| KPI Aggregation | `kpi_aggregation_rules.py` | Reglas de agregación cross-grain |
| KPI Consistency | `kpi_consistency.py` | Validación cross-grain |

---

## 7. REGLAS DE FRESHNESS

1. **Cutoff diario:** 1 día. Si `derived_max_date >= today - 1`, NO es "falta data".
2. **Tolerancia madrugada:** Hasta 28h de lag aceptable (data de ayer carga en madrugada).
3. **Pipeline:** `ops.data_freshness_audit` debe ejecutarse periódicamente (mínimo diario).
4. **Grupos:** `operational` (real_operational, real_lob_drill, real_lob), `analytical`, `legacy`.
5. **Datasets primarios:** `real_operational` + fallback a `real_lob_drill`, `real_lob`.

---

## 8. REGLAS DE COMPARABILIDAD

1. **Monthly:** MoM (mes civil vs mes anterior). Partial: compara período parcial equivalente.
2. **Weekly:** WoW (semana ISO vs semana ISO - 7 días). Partial: compara ventana parcial equivalente.
3. **Daily:** DoW-7 (mismo día semana anterior). Baseline options: D-1, same_weekday_previous_week, same_weekday_avg_4w.
4. **Partial periods:** Se marcan como `is_partial_equivalent` cuando hay baseline comparable del backend.
5. **Thresholds:** Multiplicadores por grain (monthly=1.0, weekly=1.3, daily=1.8) y por partial (x1.5).

---

## 9. REGLAS YTD

1. **Base:** Suma de `trips_completed` desde `real_business_slice_month_fact` para meses cerrados + datos parciales del mes actual.
2. **Validación:** `SUM(day_fact)` debe coincidir con `SUM(month_fact)` para el mismo rango (tolerancia 3%).
3. **Revenue:** El valor absoluto de month_fact debe coincidir con day_fact. Hay inversión de signo documentada (month_fact negativo, day_fact positivo) — misma magnitud.
4. **Proyección YTD:** attainment_pct, gap_to_expected calculados desde `projection_expected_progress_service`.

---

## 10. REGLAS DE PLAN VS REAL

1. **Separación estricta:** `real_business_slice_*_fact` NO contiene columnas de Plan.
2. **Fuentes:** Plan desde `ops.plan_trips_monthly` + `ops.v_plan_trips_monthly_latest`. Real desde `ops.real_business_slice_month_fact` vía serving view.
3. **Comparación:** `ops.mv_plan_vs_real_monthly_fact` y `ops.mv_plan_vs_real_monthly_fact_canonical`.
4. **Status buckets:** `matched`, `plan_only`, `real_only`, `unknown`.
5. **Canonical vs Legacy:** Preferir canonical (MV). Fallback a legacy solo si canonical no disponible.
6. **No mezclar:** Omniview Matrix es REAL ONLY. Plan vs Real tiene su propia vista dedicada.

---

## 11. QUÉ NO DEBE TOCARSE SIN NUEVA FASE

Las siguientes áreas están bajo la regla de no modificación sin autorización explícita de nueva fase:

| Área | Motor | Regla |
|------|-------|-------|
| Forecast / Predicciones | Forecast Engine (Fase 3) | No implementar |
| Sugerencias automáticas | Suggestion Engine (Fase 4) | No implementar |
| Decisiones operativas | Decision Engine (Fase 5) | No implementar |
| Ejecución de acciones | Action Engine (Fase 7) | No implementar |
| Aprendizaje de efectividad | Learning Engine (Fase 9) | No implementar |
| Refactors grandes | N/A | Solo cambios aditivos |
| Migraciones destructivas | N/A | Prohibidas |
| Mezclar Plan en Omniview | Control Foundation | Omniview es REAL ONLY |
| IA generativa en decisiones | N/A | IA asiste, no gobierna |

---

## 12. DEPENDENCIAS ENTRE MOTORES

```
Control Foundation (ACTIVE) → Diagnostic → Forecast → Suggestion → Decision → Action → Learning
                                    ↑
                              READY NEXT
```

- Solo 1 motor ACTIVE a la vez.
- Cada motor depende del anterior como prerrequisito.
- Control Foundation debe cerrarse antes de activar Diagnostic.
- El cierre de Control Foundation está en estado **CONDITIONAL GO**.

---

## 13. SCRIPTS DE QA Y VALIDACIÓN

| Script | Propósito |
|--------|-----------|
| `validate_phase1g2_control_foundation_closure.py` | Auditoría integral Fase 1G.2 (43 validaciones) |
| `validate_kpi_grain_consistency.py` | Consistencia KPI cross-grain (daily/weekly/monthly) |
| `regression_phase1g.py` | Regresión comprehensiva Fase 1G |
| `audit_control_tower.py` | Auditoría central (7 checks) |
| `certify_control_tower_go_nogo.py` | Certificación GO/NO-GO formal |

---

*Documento mantenido como arquitectura viva de Control Foundation.*
*Actualizar con cada cierre de fase o cambio arquitectónico significativo.*
