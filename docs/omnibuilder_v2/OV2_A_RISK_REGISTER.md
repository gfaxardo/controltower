# OV2-A — RISK REGISTER (REGISTRO DE RIESGOS)

> **Fase:** OV2-A — Blindaje Lógico OV2  
> **Fecha:** 2026-06-04  
> **Severidad:** CRITICAL > HIGH > MEDIUM > LOW

---

## 1. RIESGOS CRÍTICOS (P0 — Bloquean GO real)

### R-C1: Revenue Proxy Fallback Silencioso
| Campo | Valor |
|-------|-------|
| **ID** | R-C1 |
| **Severidad** | CRITICAL |
| **Área** | Revenue |
| **Descripción** | `revenue_yego_net` usa `COALESCE(revenue_yego_real, revenue_yego_proxy)`. Cuando `comision_empresa_asociada` es NULL o 0, el sistema aplica proxy `ticket * 3%` (default commission). El usuario NO sabe cuándo está viendo revenue real vs proxy. |
| **Ubicación** | `business_slice_service.py`, `revenue_quality_service.py` |
| **Impacto** | Decisiones operativas basadas en revenue proxy sin saberlo. Falsos GO. |
| **Mitigación OV2-B** | Exponer `revenue_source` (real/proxy/missing) en la celda. Umbral WARNING >80% proxy, BLOCKED >95%. |

### R-C2: Dual Column Revenue (revenue_yego_final vs revenue_yego_net)
| Campo | Valor |
|-------|-------|
| **ID** | R-C2 |
| **Severidad** | CRITICAL |
| **Área** | Revenue |
| **Descripción** | Existen DOS columnas de revenue: `revenue_yego_final` (con COALESCE + ABS) y `revenue_yego_net` (ABS de comision_empresa_asociada). La UI muestra `revenue_yego_net` pero la proyección usa `COALESCE(revenue_yego_final, revenue_yego_net)`. Confusión de cuál es la fuente canónica. |
| **Ubicación** | `business_slice_service.py`, `serving.omniview_projection_daily_fact` |
| **Impacto** | Inconsistencia cross-métrica. Revenue en Evolution ≠ Revenue en Vs Proy. |
| **Mitigación OV2-B** | Canonizar UNA sola columna `revenue_yego` con `revenue_source` flag. Eliminar dualidad. |

### R-C3: Mega-Servicio de Proyección (3210 líneas)
| Campo | Valor |
|-------|-------|
| **ID** | R-C3 |
| **Severidad** | CRITICAL |
| **Área** | Proyección |
| **Descripción** | `projection_expected_progress_service.py` tiene 3210 líneas. Orquestra plan+real+serving+seasonality+YTD+pacing+trends+gap_decomposition. Single point of failure. Imposible de auditar completamente. |
| **Ubicación** | `backend/app/services/projection_expected_progress_service.py` |
| **Impacto** | Si falla, toda la vista Vs Proy queda ciega. Debug extremadamente lento. |
| **Mitigación OV2-B** | Dividir en: `projection_fact_builder`, `projection_query_service`, `seasonality_curve_engine` (ya separado). |

### R-C4: Evolution View Muestra Revenue Incompleto
| Campo | Valor |
|-------|-------|
| **ID** | R-C4 |
| **Severidad** | CRITICAL |
| **Área** | UI / Revenue |
| **Descripción** | Evolution view (legacy) muestra celdas de Revenue vacías o incompletas. Usa endpoint `/ops/business-slice/omniview` que lee de `V_RESOLVED` (FORBIDDEN_SERVING_SOURCE). Usuarios que acceden a Evolution ven datos falsos. |
| **Ubicación** | `BusinessSliceOmniview.jsx`, `/ops/business-slice/omniview` endpoint |
| **Impacto** | Falsos negativos: usuario cree que no hay revenue cuando sí hay. |
| **Mitigación OV2-A** | Ocultar Evolution completamente. Eliminar toggle de UI. OV2-B: remover código. |

### R-C5: CLOSED/PARTIAL/FUTURE No Visible en Cada Celda
| Campo | Valor |
|-------|-------|
| **ID** | R-C5 |
| **Severidad** | CRITICAL |
| **Área** | UI / Period Status |
| **Descripción** | El estado del período (CLOSED/PARTIAL/CURRENT/FUTURE/NO_PLAN/NO_REAL) no es claramente visible en cada celda de la matriz. Usuario no sabe si el dato que ve es de un período cerrado, parcial o futuro. |
| **Ubicación** | `BusinessSliceOmniviewMatrixCell.jsx`, `BusinessSliceOmniviewMatrixTable.jsx` |
| **Impacto** | Usuario puede tomar decisiones sobre datos parciales creyendo que son cerrados. |
| **Mitigación OV2-B** | Añadir badge de período en cada celda. Backend debe devolver `period_status` en cada row. |

### R-C6: CT_SCHEDULER_ENABLED=false en Producción
| Campo | Valor |
|-------|-------|
| **ID** | R-C6 |
| **Severidad** | CRITICAL |
| **Área** | Freshness / Refresh |
| **Descripción** | Los scheduler jobs NO corren en producción. Refreshes son manuales/CLI. Si nadie ejecuta refreshes, los serving facts se stalean y la UI muestra datos viejos sin advertir. |
| **Ubicación** | `main.py`, `serving_refresh_scheduler.py` |
| **Impacto** | Usuario ve datos staleados sin saberlo. Decisiones sobre datos viejos. |
| **Mitigación OV2-B** | Implementar freshness watchdog independiente del scheduler. UI debe mostrar `data_freshness_seconds` o `max_data_date` en banner permanente. |

---

## 2. RIESGOS ALTOS (P1 — Degradan confianza operacional)

### R-H1: Cálculos Pesados en Frontend (omniviewMatrixUtils.js + projectionMatrixUtils.js)
| Campo | Valor |
|-------|-------|
| **ID** | R-H1 |
| **Severidad** | HIGH |
| **Área** | Frontend / Performance |
| **Descripción** | `omniviewMatrixUtils.js` (1208 líneas) y `projectionMatrixUtils.js` (937 líneas) contienen lógica de negocio pesada: cómputo de deltas (DoD/WoW/MoM), totales, señales, colores, attainment, gap decomposition. Esto DEBERÍA estar precalculado en el backend. |
| **Ubicación** | `frontend/src/components/omniview/omniviewMatrixUtils.js`, `projectionMatrixUtils.js` |
| **Impacto** | UI lenta con muchos datos. Lógica de negocio duplicada frontend/backend. Riesgo de divergencia. |
| **Mitigación OV2-B** | Mover deltas al backend como serving columns. Frontend solo renderiza. |

### R-H2: Ratios Recomputed en Runtime (4 de 7 KPIs)
| Campo | Valor |
|-------|-------|
| **ID** | R-H2 |
| **Severidad** | HIGH |
| **Área** | Backend / Performance |
| **Descripción** | `avg_ticket`, `trips_per_driver`, `cancel_rate_pct`, `commission_pct` son recomputados en cada request. No están almacenados como serving columns. Cada query recalcula `SUM(revenue)/SUM(trips)`, `trips/active_drivers`, etc. |
| **Ubicación** | `business_slice_omniview_service.py`, `business_slice_service.py` |
| **Impacto** | Queries más lentas. Mayor carga en DB. Riesgo de fórmula inconsistente entre llamadas. |
| **Mitigación OV2-B** | Precalcular los 4 ratios en las fact tables (day_fact, week_fact, month_fact). |

### R-H3: Cross-Currency SUM (PEN + COP Sin Conversión)
| Campo | Valor |
|-------|-------|
| **ID** | R-H3 |
| **Severidad** | HIGH |
| **Área** | Revenue / Territory Totals |
| **Descripción** | Los totales de territorio (global/cross-country) suman PEN + COP sin conversión de moneda. El resultado es económicamente sin significado. |
| **Ubicación** | `business_slice_omniview_service.py` (totales globales) |
| **Impacto** | Revenue total global es falso. No se puede usar para reporting consolidado. |
| **Mitigación OV2-B** | No sumar cross-currency. Mostrar por país separado. O implementar conversión con tasa oficial. |

### R-H4: Plan vs Real Mezcla Fuentes Legacy + Canónicas
| Campo | Valor |
|-------|-------|
| **ID** | R-H4 |
| **Severidad** | HIGH |
| **Área** | Plan vs Real |
| **Descripción** | `plan_vs_real_service.py` mantiene DOS paths: legacy (`v_plan_vs_real_realkey_final`) y canonical (`mv_plan_vs_real_monthly_fact_canonical`). Coexisten dos MVs con mismos datos pero distinta homologación. |
| **Ubicación** | `plan_vs_real_service.py`, `ops.py` |
| **Impacto** | Confusión sobre cuál es el PvR autoritativo. Posible divergencia numérica. |
| **Mitigación OV2-B** | Eliminar legacy path. Canonical como única fuente. |

### R-H5: MVs No Refrescadas — Supply Weekly/Monthly Stale
| Campo | Valor |
|-------|-------|
| **ID** | R-H5 |
| **Severidad** | HIGH |
| **Área** | Supply / Freshness |
| **Descripción** | `mv_supply_weekly` y `mv_supply_monthly` NO se refrescan en el pipeline principal. Documentado como G7 en `OMNIVIEW_CANONICAL_REGISTRY.md:756`. Potencialmente permanentemente stale. |
| **Ubicación** | `ops.mv_supply_weekly`, `ops.mv_supply_monthly` |
| **Impacto** | Datos de supply en UI potencialmente obsoletos. |
| **Mitigación OV2-B** | Incluir en pipeline de refresh o migrar a serving facts gobernados. |

### R-H6: Daily/Weekly Facts Sin Serving Views
| Campo | Valor |
|-------|-------|
| **ID** | R-H6 |
| **Severidad** | HIGH |
| **Área** | Serving Governance |
| **Descripción** | Solo `month_fact` tiene serving view (`v_real_business_slice_month_serving`). `day_fact` y `week_fact` son leídos directamente, sin capa de serving view que pueda implementar snapshot/rollback/redirect. |
| **Ubicación** | `ops.real_business_slice_day_fact`, `ops.real_business_slice_week_fact` |
| **Impacto** | Sin capacidad de serving view rollback para daily/weekly. Menor gobernanza. |
| **Mitigación OV2-B** | Crear `v_real_business_slice_day_serving` y `v_real_business_slice_week_serving`. |

---

## 3. RIESGOS MEDIOS (P2 — Degradan calidad pero no bloquean)

### R-M1: Dependencias Circulares en Proyección
| Campo | Valor |
|-------|-------|
| **ID** | R-M1 |
| **Severidad** | MEDIUM |
| **Área** | Proyección |
| **Descripción** | `projection_expected_progress_service.py` llama a `business_slice_service.py` para obtener facts, y `business_slice_omniview_service.py` llama a `projection_expected_progress_service.py` para obtener proyección. Posible ciclo de imports/lógica. |
| **Ubicación** | Servicios de proyección y business slice |
| **Impacto** | Riesgo de recursión o double-counting en queries. |
| **Mitigación OV2-B** | Separar claramente: serving facts (fuente) → projection builder (transforma) → projection query (lee). Unidireccional. |

### R-M2: Lógica de Alertas Duplicada Frontend/Backend
| Campo | Valor |
|-------|-------|
| **ID** | R-M2 |
| **Severidad** | MEDIUM |
| **Área** | Alertas |
| **Descripción** | `alertingEngine.js` (frontend) y `projection_ytd_alerts_service.py` (backend) contienen lógica de alertas. Posible divergencia en thresholds o señales. |
| **Ubicación** | Frontend `omniview/alertingEngine.js`, Backend `projection_ytd_alerts_service.py` |
| **Impacto** | Usuario ve alerta en UI que no coincide con backend. |
| **Mitigación OV2-B** | Backend como fuente única de alertas. Frontend solo renderiza. |

### R-M3: Inspector de Celda No Trazable a Source
| Campo | Valor |
|-------|-------|
| **ID** | R-M3 |
| **Severidad** | MEDIUM |
| **Área** | UI / Trazabilidad |
| **Descripción** | `BusinessSliceOmniviewInspector.jsx` muestra detalles de celda pero no expone la fuente SQL/view/tabla que generó el dato. Usuario no sabe si el dato viene de fact, serving view, o proxy. |
| **Ubicación** | `BusinessSliceOmniviewInspector.jsx` |
| **Impacto** | Usuario no puede verificar trazabilidad del dato. |
| **Mitigación OV2-B** | Añadir `source_table`, `source_type`, `refreshed_at`, `data_date` en el inspector. |

### R-M4: Filtros Persistidos en localStorage Sin Versión
| Campo | Valor |
|-------|-------|
| **ID** | R-M4 |
| **Severidad** | MEDIUM |
| **Área** | UI / Estado |
| **Descripción** | Filtros de Omniview se persisten en localStorage sin versionado. Si la estructura de filtros cambia, el estado guardado puede causar errores silenciosos o filtros rotos. |
| **Ubicación** | `omniviewMatrixUtils.js` → `loadPersistedState()` / `persistState()` |
| **Impacto** | UI rota después de deploy sin explicación. |
| **Mitigación OV2-B** | Versionar estado persistido. Validar schema al cargar. |

### R-M5: Playwright Screenshots No Capturan Semántica Operacional
| Campo | Valor |
|-------|-------|
| **ID** | R-M5 |
| **Severidad** | MEDIUM |
| **Área** | Certificación / Testing |
| **Descripción** | OMNI-GOV-001 usó DOM token validation (15/15 PASS) pero no detectó que Revenue estaba vacío en Evolution. La validación visual no captura semántica operacional. |
| **Ubicación** | `OMNIVIEW_HARDENING_CLOSURE.md`, Playwright tests |
| **Impacto** | Falsos GO. Cierre de fase sin validación real. |
| **Mitigación OV2-B** | Certificación semántica V2: validar valores numéricos, no solo presencia de elementos DOM. |

---

## 4. RIESGOS BAJOS (P3 — Mejora continua)

### R-L1: insightEngine.js Sin Tests
### R-L2: Sin Documentación de API para Endpoints Omniview
### R-L3: Cobertura de serving registry incompleta (faltan day_fact, week_fact)
### R-L4: Código muerto (evolution toggle, legacy components aún en bundle)

---

## 5. RESUMEN DE RIESGOS

| ID | Severidad | Área | Mitigable en OV2-A | Bloquea GO? |
|----|-----------|------|---------------------|-------------|
| R-C1 | CRITICAL | Revenue Proxy Fallback | No (requiere OV2-B) | SÍ |
| R-C2 | CRITICAL | Dual Column Revenue | No (requiere OV2-B) | SÍ |
| R-C3 | CRITICAL | Mega-Servicio Proyección | No (requiere OV2-B) | SÍ |
| R-C4 | CRITICAL | Evolution Revenue Incompleto | **SÍ** (ocultar toggle) | SÍ |
| R-C5 | CRITICAL | Period Status No Visible | No (requiere OV2-B) | SÍ |
| R-C6 | CRITICAL | Scheduler Disabled | Parcial (watchdog) | SÍ |
| R-H1 | HIGH | Cálculos Frontend Pesados | No (requiere OV2-B) | No |
| R-H2 | HIGH | Ratios Recomputed | No (requiere OV2-B) | No |
| R-H3 | HIGH | Cross-Currency SUM | No (requiere OV2-B) | No |
| R-H4 | HIGH | PvR Legacy + Canonical | No (requiere OV2-B) | No |
| R-H5 | HIGH | Supply MVs Stale | No (requiere OV2-B) | No |
| R-H6 | HIGH | Daily/Weekly Sin Serving View | No (requiere OV2-B) | No |
| R-M1 | MEDIUM | Deps Circulares Proyección | No (requiere OV2-B) | No |
| R-M2 | MEDIUM | Alertas Duplicadas | No (requiere OV2-B) | No |
| R-M3 | MEDIUM | Inspector Sin Trazabilidad | No (requiere OV2-B) | No |
| R-M4 | MEDIUM | localStorage Sin Versión | No (requiere OV2-B) | No |
| R-M5 | MEDIUM | Certificación Solo DOM | **SÍ** (definir V2) | No |

---

## 6. CAUSAS RAÍZ DE ROLLBACK SILENCIOSO

Identificadas del OMNI-P0 False GO (2026-06-03):

1. **Validación por tokens DOM, no por semántica operacional** → Pass visual no detectó Revenue vacío
2. **Evolution como vista default** → Usuarios veían vista incorrecta
3. **Dualidad revenue_yego_final vs revenue_yego_net** → Inconsistencia cross-métrica
4. **Scheduler disabled en producción** → Facts no se refrescaban, datos stale
5. **No hay `max_data_date` visible en UI** → Usuario no sabía antigüedad del dato
6. **CLOSED/PARTIAL no visible** → Usuario asumía datos cerrados
7. **Alertas coexisten con Trust OK** → Falsos positivos/negativos sin explicación
