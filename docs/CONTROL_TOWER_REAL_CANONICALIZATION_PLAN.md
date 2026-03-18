# Control Tower — Plan de consolidación: fuente de verdad REAL canónica

**Objetivo:** Una sola cadena canónica para REAL, eliminación controlada de legacy, señales claras en UI.  
**Regla:** Migrar → Deprecar → Borrar. Nunca borrar antes de que la canónica sostenga la pantalla.

---

## FASE 0 — Inventario de legacy a erradicar

### Matriz de erradicación legacy

| Objeto legacy | Consumidor(es) actual(es) | Pantalla/tab afectada | Reemplazo canónico disponible | ¿Apagarse ya? | Clasificación |
|---------------|---------------------------|------------------------|--------------------------------|---------------|----------------|
| **ops.mv_real_trips_monthly** | plan_real_split_service.get_real_monthly, real_repo.get_real_monthly_data, v_real_metrics_monthly (vista), v_plan_vs_real_realkey_final (si la vista toma real de aquí) | Performance > Resumen, Plan vs Real (mensual), Real vs Proyección, core/summary | Sí: agregado mensual desde real_drill_dim_fact (period_grain=month) o real_rollup_day_fact por mes | No hasta migrar consumidores | **REMOVE AFTER PARITY** |
| **ops.mv_real_trips_weekly** | phase2b_weekly_service (v_plan_vs_real_weekly), phase2c (v_plan_vs_real_weekly) | Performance > Plan vs Real (semanal) | Sí: agregado semanal desde real_drill_dim_fact (period_grain=week) | No hasta migrar | **REMOVE AFTER PARITY** |
| **ops.mv_real_trips_by_lob_month** | real_lob_service.get_real_lob_monthly_svc | Endpoints /ops/real-lob/monthly (legacy; UI usa drill PRO y v2) | Sí: real_lob v2 / drill desde cadena hourly-first | Sí: UI no depende de /real-lob/monthly | **DEPRECATE NOW** |
| **ops.mv_real_trips_by_lob_week** | real_lob_service.get_real_lob_weekly_svc | Endpoints /ops/real-lob/weekly (legacy) | Sí: idem | Sí | **DEPRECATE NOW** |
| **ops.v_real_metrics_monthly** | real_vs_projection_service.get_real_metrics, get_real_vs_projection_overview | Proyección > Real vs Proyección | Sí: vista/query desde real_drill_dim_fact mensual | No hasta migrar servicio | **REMOVE AFTER PARITY** |
| **ops.v_plan_vs_real_realkey_final** | plan_vs_real_service (monthly) | Performance > Plan vs Real (mensual) | Requiere nueva vista que una plan + real canónico (agregado mensual desde real_drill_dim_fact) | No hasta tener vista canónica | **REMOVE AFTER PARITY** |
| **ops.v_plan_vs_real_weekly** | phase2b_weekly_service | Performance > Plan vs Real (semanal) | Requiere vista que una plan semanal + real desde real_drill_dim_fact (week) | No hasta tener vista canónica | **REMOVE AFTER PARITY** |
| **plan.py refresh mv_real_trips_monthly** | POST/trigger refresh | N/A (batch) | Dejar de refrescar cuando no haya consumidores | Después de migración | **REMOVE AFTER PARITY** |

### Resumen por clasificación

- **KEEP TEMPORARILY:** Ninguno; todos los legacy tienen reemplazo o camino claro.
- **DEPRECATE NOW:** mv_real_trips_by_lob_month, mv_real_trips_by_lob_week (consumidores solo en endpoints legacy no usados por la UI principal).
- **REMOVE AFTER PARITY:** mv_real_trips_monthly, mv_real_trips_weekly, v_real_metrics_monthly, v_plan_vs_real_realkey_final, v_plan_vs_real_weekly, jobs de refresh de mv_real_trips_monthly.
- **REMOVE NOW:** Ninguno (no borrar antes de migrar y validar paridad).

---

## FASE 1 — Cadena canónica oficial

### Declaración

**Única fuente de verdad REAL para Control Tower:**

```
v_trips_real_canon_120d
  → v_real_trip_fact_v2
  → mv_real_lob_hour_v2 / mv_real_lob_day_v2
  → real_rollup_day_fact (vista sobre day_v2)
  → real_drill_dim_fact / mv_real_drill_dim_agg (day/week/month desde misma cadena)
  → week/month derivados de la misma cadena
```

**Regla de gobierno:** **NEW REAL CONSUMERS MUST USE CANONICAL HOURLY-FIRST ONLY.** No añadir nuevos consumidores a legacy. Ver `docs/REAL_CANONICAL_CHAIN.md` y `docs/CONTROL_TOWER_REAL_GOVERNANCE_STATUS.md`.

### Política de nuevos consumidores (bloqueo de legacy)

- Cualquier **nueva** pantalla, endpoint o servicio que necesite datos REAL debe usar **solo** la cadena canónica (hourly-first): `real_drill_dim_fact`, `real_rollup_day_fact`, `mv_real_lob_day_v2`, `mv_real_lob_hour_v2`, o APIs que lean de ellos (p. ej. `GET /ops/real/monthly?source=canonical` cuando la paridad esté cerrada).
- **Checklist antes de desarrollar:** ¿Necesito datos REAL? → Sí → ¿Existe endpoint/servicio canónico para este grano? → Usar solo ese. No crear nuevos consumidores de `mv_real_trips_monthly`, `mv_real_trips_weekly`, `v_real_metrics_monthly` ni vistas plan-vs-real que lean de ellas.

### Documentación y comentarios

- Este documento declara la cadena en `docs/`.
- Comentarios en código: `plan_real_split_service`, `real_repo`, `real_vs_projection_service` indican "LEGACY: prefer canonical_real_monthly_service cuando USE_CANONICAL_REAL_MONTHLY".
- Contrato: la API de real mensual/semanal debe poder servirse desde agregados sobre `real_drill_dim_fact` (period_grain=month/week) con el mismo contrato de respuesta.

---

## FASE 2 — Migración de consumidores críticos

### Orden de migración

1. **Performance > Resumen**  
   - Dejar de leer `ops.mv_real_trips_monthly`.  
   - Leer desde **canonical real monthly** (agregado desde `ops.real_drill_dim_fact` con period_grain='month').  
   - Contrato: mismo formato de respuesta (period, trips_real_completed, revenue_real_yego, active_drivers_real, etc.).  
   - Revenue canónico = margin_total (mismo concepto que revenue_real_yego).

2. **Performance > Plan vs Real (mensual — implementado)**  
   - **Real canónica:** desde **ops.v_trips_real_canon** (misma fuente que `mv_real_monthly_canonical_hist`), sin 120d.  
   - Vistas: `ops.v_real_universe_by_park_realkey_canon` (agregado por country, city, park_id, real_tipo_servicio, period_date; revenue = SUM(ABS(comision_empresa_asociada))) y `ops.v_plan_vs_real_realkey_canonical` (FULL OUTER JOIN plan + real canónica; mismo contrato que legacy).  
   - **Switch:** `GET /ops/plan-vs-real/monthly?source=canonical` y `GET /ops/plan-vs-real/alerts?source=canonical` leen la vista canónica; sin parámetro = legacy.  
   - Contrato: idéntico (country, city, park_id, park_name, real_tipo_servicio, period_date, trips_plan, trips_real, revenue_plan, revenue_real, etc.).  
   - Validación: `scripts/validate_plan_vs_real_parity.py` (paridad legacy vs canónico por month+country).  
   - Semanal: sin cambios; sigue legacy.

3. **Proyección > Real vs Proyección**  
   - Dejar de usar `ops.v_real_metrics_monthly` (que lee mv_real_trips_monthly).  
   - Leer métricas reales mensuales desde agregado canónico (real_drill_dim_fact month) con mismo contrato que v_real_metrics_monthly.

### Fuente canónica mensual definitiva para Resumen (cierre técnico 2025-03)

**Preguntas respondidas con evidencia:**

1. **¿La canónica mensual actual depende demasiado de la ventana 120d?** **Sí.** Toda la cadena (v_trips_real_canon_120d → v_real_trip_fact_v2 → mv_real_lob_* → real_drill_dim_fact) está limitada por 120d. No existe hoy una vista/tabla canónica mensual con 2025 completo sin esa dependencia.
2. **¿Existe ya una fuente canónica mensual mejor que v_real_trip_fact_v2 para 2025 completo?** **No.** La única agregación mensual canónica es `real_drill_dim_fact` (poblada desde `mv_real_lob_month_v3`), que tiene la misma limitación 120d. Para año completo histórico se sigue usando legacy hasta extender la cadena.
3. **¿Puede derivarse mensualmente desde mv_real_lob_day_v2, real_rollup_day_fact, real_drill_dim_fact, month_v3 sin perder consistencia?** **Sí, dentro de la ventana.** `real_drill_dim_fact` (month) se puebla desde `mv_real_lob_month_v3`; day_v2 y month_v3 comparten la misma cadena. Fuera de 120d no hay datos en esas fuentes.
4. **Mejor fuente canónica mensual para trips, revenue/margin, drivers core:**
   - **Trips y revenue/margin:** `ops.real_drill_dim_fact` (period_grain = 'month', breakdown = 'lob'). Una sola fuente, mismo grano, consistente con drill.
   - **Drivers core:** `ops.v_real_trip_fact_v2` con `COUNT(DISTINCT conductor_id)` (is_completed, año, país). No usar segmentación.

**Conclusión (antes de canónica histórica):** trips/revenue desde real_drill_dim_fact (month, lob) y drivers core desde v_real_trip_fact_v2; cobertura limitada a 120d.

**Canónica mensual histórica (post 107):** Para Resumen con año completo se usa **ops.mv_real_monthly_canonical_hist**, alimentada desde **v_trips_real_canon** (sin 120d). Una sola MV con trips, margin_total y active_drivers_core por (month_start, country). Refresco: `scripts/refresh_real_monthly_canonical_hist.py`. El servicio `canonical_real_monthly_service` lee solo de esta MV; ya no depende de 120d para el histórico mensual.

### Estado de implementación (post ejecución paridad 2025-03-17)

- **Resumen:** **Vuelto a legacy.** Tras corrección mínima (filtro país PE/CO y conductores desde vista de segmentación), PE y CO ya devuelven filas canónicas; conductores pueden seguir en 0 si la vista hace timeout o el batch de segmentación no ha poblado la fact. Oct/nov dependen de la ventana de `populate_real_drill_from_hourly_chain`. Paridad sigue MAJOR_DIFF; Resumen se mantiene en legacy. Ver **docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md** (sección 17).
- **Plan vs Real:** Sigue en legacy. Siguiente migración solo cuando Fase 1 esté cerrada.
- **Real vs Proyección:** Sigue en legacy; marcada en UI como **source_incomplete**. No tratada como completa.

---

## FASE 3 — Paridad y validación antes de borrar

### Comparación pre/post

Para cada consumidor migrado, validar paridad entre:

- **Cadena vieja:** mv_real_trips_monthly / mv_real_trips_weekly (o vistas que las usan).
- **Cadena canónica:** Agregado desde real_drill_dim_fact (month/week).

Métricas a comparar:

- Viajes (trips_real_completed vs SUM(trips)).
- Revenue (revenue_real_yego vs SUM(margin_total)).
- Conductores (active_drivers_real vs SUM(active_drivers)).
- Plan vs Real: mismos gaps y alertas dentro de umbral.

### Umbrales de tolerancia

- Diferencias de redondeo: aceptable.
- Diferencias > 1% en viajes o revenue en periodos cerrados: investigar antes de eliminar legacy.
- Si no hay paridad suficiente: NO borrar; documentar gap; dejar objeto como DEPRECATED pero vivo.

---

## FASE 4 — Desactivación controlada de legacy

Una vez migrados consumidores y validada paridad:

1. Quitar rutas internas que sigan apuntando a legacy (o redirigir a canonical).
2. Dejar comentarios/documentación de deprecación en vistas y servicios.
3. Impedir nuevos usos: documentar "DEPRECATED – use canonical only".
4. Aislar scripts de refresh legacy (no ejecutar o ejecutar solo en mantenimiento).
5. Si todo está validado: eliminar refresh jobs legacy, endpoints huérfanos y vistas/tablas legacy innecesarias.

**Importante:** No borrar nada que aún tenga consumidores activos.

---

## FASE 5 — Señales visibles en UI

### Estados posibles por feature/pantalla

| Estado | Significado | Ejemplo de etiqueta |
|--------|-------------|----------------------|
| **CANONICAL** | Fuente canónica hourly-first | "Fuente canónica" |
| **MIGRATING** | En proceso de migración a canónica | "Migrando a fuente canónica" |
| **DATA_IN_PROGRESS** | Datos en proceso de poblado | "Datos en proceso de poblado" |
| **DATA_MISSING** | Falta data para el periodo | "Sin datos para este periodo" |
| **SOURCE_INCOMPLETE** | Fuente incompleta o limitada | "Vista temporalmente limitada" |

### Dónde aplicar

- Resumen (KPICards / ExecutiveSnapshotView).
- Real (diario) – ya canónica; badge "Fuente canónica".
- Plan vs Real (mensual y semanal).
- Real vs Proyección.
- Cards relacionadas y tablas donde aplique.

### Regla

El usuario no debe confundir: un cero real vs dato no poblado vs feature no migrada. Siempre que haya ambigüedad, mostrar el estado de la fuente.

---

## FASE 6 — Fallbacks visibles y no engañosos

Si una característica no puede cargar (falta migración o data):

- Mostrar estado visible en UI (badge o mensaje).
- No colgar la pantalla; no spinner infinito.
- No mostrar números falsos; no ocultar el problema.
- Comportamiento: fallback controlado, mensaje corto, navegación intacta.

---

## FASE 7 — Gobierno y observabilidad

### Contenido

- Qué pantallas están en canónica.
- Cuáles en migración.
- Cuáles dependen de data faltante.
- Freshness por pantalla / fuente.
- Última fecha/hora poblada por fuente.

### Dónde vive

- Documentación: este plan y CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md.
- Endpoint diagnóstico: `GET /ops/real-source-status` (implementado) devuelve por pantalla/feature: source_status (canonical | legacy | migrating), freshness_max_date, message.

---

## FASE 8 — Validación final

### Checklist

1. Pantallas 100% en canónica: Real (diario), Operación > Drill; Resumen/Plan vs Real/Real vs Proyección cuando migración y paridad estén cerradas.
2. Legacy deprecated: mv_real_trips_by_lob_*; resto según matriz.
3. Legacy eliminado: solo después de paridad y cero consumidores.
4. Señales en UI: presentes en Resumen, Plan vs Real, Real vs Proyección, Real (diario).
5. Sin errores 500 por eliminación prematura.
6. Sin spinner infinito; fallbacks claros.
7. Usuario puede entender qué falta y por qué.

---

## Entregables obligatorios

### 1. Documento

- **docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md** (este archivo).  
- Incluye: inventario legacy, cadena canónica oficial, consumidores migrados, objetos deprecated, objetos eliminados, plan de borrado final.

### 2. Lista exacta de archivos modificados

Ver sección "Archivos modificados" al final del plan.

### 3. Checklist visual de señales UI (post paridad real)

| Pantalla / Área | Estado actual | Badge / señal |
|-----------------|----------------|----------------|
| Performance > Resumen | **Migrating** (legacy activo) | "Legacy (paridad canónica pendiente)" (ámbar) |
| Performance > Real (diario) | Canonical | "Fuente canónica" |
| Performance > Plan vs Real | Migrating | "Migrando a fuente canónica" (ámbar/azul) |
| Proyección > Real vs Proyección | **source_incomplete** | "Vista temporalmente limitada" (rojo) |
| Operación > Drill | Canonical | "Fuente canónica" |
| Cards/tablas con real | Según fuente | DataStateBadge con estado |

### 4. Veredicto final

**Veredicto Fase 1:** **PHASE1_CANONICALIZATION_CLOSED** (canónica mensual histórica 2025-03)

- Canónica mensual histórica: `ops.mv_real_monthly_canonical_hist` (fuente `v_trips_real_canon`, sin 120d). Migración 107+108, refresh con `scripts/refresh_real_monthly_canonical_hist.py`.
- Paridad: **Global MATCH**, **CO MINOR_DIFF**, PE MAJOR_DIFF (residual: origen legacy PE). Cobertura 2025: 12/12 meses trips, revenue, drivers core.
- **Resumen** usa canónica (KPICards → getRealMonthlySplitCanonical; real-source-status: performance_resumen = canonical, resumen_uses_canonical = True). Legacy listo para deprecación cuando se migren Plan vs Real y Real vs Proyección.
- Siguiente paso: Fase 2 — migrar Plan vs Real a real desde `mv_real_monthly_canonical_hist` (o agregado compatible) y validar paridad.

---

## Gobierno operativo (aplicado)

- **Estado por pantalla:** Ver `docs/CONTROL_TOWER_REAL_GOVERNANCE_STATUS.md`. Todas las pantallas REAL relevantes tienen badge (canonical / migrating / source_incomplete / under_review).
- **Navegación:** Real vs Proyección, Alertas de conducta y Fuga de flota están bajo tab "En revisión"; no se eliminan, se exponen con aviso. Riesgo principal solo Desviación por ventanas y Acciones recomendadas.
- **Política:** NEW REAL CONSUMERS MUST USE CANONICAL HOURLY-FIRST ONLY. Documentado en `REAL_CANONICAL_CHAIN.md` y en este plan.

---

## Archivos modificados (lista) — incluye Fase 1 y gobernanza

- `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` (este plan).
- `docs/REAL_CANONICAL_CHAIN.md` (declaración oficial de la cadena).
- `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md` (informe Fase 1; cierre técnico 2025-03: sección 18, veredicto PHASE1_PARTIAL_PARITY_PENDING).
- `docs/REAL_DRIVER_GOVERNANCE.md` (modelo drivers core vs segmentados, grano por vista).
- `backend/scripts/validate_real_monthly_coverage.py` (validación cobertura temporal canónica).
- `backend/app/services/canonical_real_monthly_service.py` (lee mv_real_monthly_canonical_hist; sin 120d).
- `backend/alembic/versions/107_real_monthly_canonical_hist_mv.py` (MV canónica mensual histórica).
- `backend/scripts/refresh_real_monthly_canonical_hist.py` (refresco de la MV).
- `backend/scripts/outputs/parity_global_2025.csv`, `parity_PE_2025.csv`, `parity_CO_2025.csv` (evidencia de paridad).
- `backend/app/services/canonical_real_monthly_service.py` (servicio canónico; comentario seguridad breakdown=lob).
- `backend/app/settings.py` (USE_CANONICAL_REAL_MONTHLY; control real vía source=canonical en endpoint).
- `backend/app/services/plan_real_split_service.py` (get_real_monthly siempre legacy; canónica solo vía endpoint).
- `backend/app/routers/ops.py` (GET /ops/real/monthly con param source=canonical; GET /ops/real-source-status).
- `backend/scripts/validate_real_monthly_parity.py` (script paridad legacy vs canónico).
- `frontend/src/components/DataStateBadge.jsx` (estados canonical, migrating, legacy, data_in_progress, data_missing, source_incomplete).
- `frontend/src/components/ExecutiveSnapshotView.jsx` (badge según getRealSourceStatus).
- `frontend/src/components/KPICards.jsx` (Resumen vuelto a getRealMonthlySplit legacy tras MAJOR_DIFF).
- `frontend/src/components/PlanVsRealView.jsx` (badge migrating).
- `frontend/src/components/RealVsProjectionView.jsx` (badge source_incomplete).
- `frontend/src/components/RealOperationalView.jsx` (badge "Fuente canónica").
- `frontend/src/components/RealLOBDrillView.jsx` (badge canonical drill y diario).
- `frontend/src/constants/sourceStatus.js` (labels y clases por estado; source_incomplete en rojo).
- `frontend/src/services/api.js` (getRealMonthlySplitCanonical, getRealSourceStatus).
- **Gobernanza:** `docs/CONTROL_TOWER_REAL_GOVERNANCE_STATUS.md` (nuevo). `frontend/src/constants/sourceStatus.js` (under_review; migrating=ámbar). `frontend/src/components/DataStateBadge.jsx` (under_review). `frontend/src/App.jsx` (tab En revisión; Proyección quitada de main nav; Risk sin Alertas/Fuga en principal). `frontend/src/components/BehavioralAlertsView.jsx`, `FleetLeakageView.jsx` (badge under_review + mensaje fallback). `frontend/src/components/RealVsProjectionView.jsx` (mensaje fallback source_incomplete). `backend/app/routers/ops.py` (real-source-status: risk_behavioral_alerts, risk_fleet_leakage under_review). `docs/REAL_CANONICAL_CHAIN.md`, `docs/CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md` (política nuevos consumidores).

---

*Plan de consolidación. Eliminación de legacy en 3 pasos: migrar → deprecar → borrar.*
