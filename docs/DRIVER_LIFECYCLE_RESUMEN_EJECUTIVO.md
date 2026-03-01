# Driver Lifecycle — Resumen ejecutivo (blindaje y cohortes)

## Qué se blindó

1. **Consistencia matemática**  
   - Regla: **Σ KPI por park = KPI global** (activations, active_drivers, churn_flow, reactivated).  
   - SQL de validación automática (`driver_lifecycle_consistency_validation.sql`): si hay diff se muestra semana y diferencia; no avanzar a siguientes fases hasta corregir.

2. **Asignación de park única y oficial**  
   - Eliminada la lógica de “primer trip” (MIN(park_id)).  
   - **park_dominante_semana** = park_id con **mayor** número de viajes completados en la semana por (driver, week). Desempate: **menor** park_id (determinístico).  
   - Toda la lógica vive en **una sola MV**: `ops.mv_driver_weekly_stats`. No se duplica en otras MVs.

3. **Una sola fuente para KPIs semanales**  
   - `ops.mv_driver_lifecycle_weekly_kpis` se calcula solo desde `mv_driver_weekly_stats` (active_drivers, churn_flow, reactivated) y activations desde base vía join por week_start.  
   - Sin lógicas alternativas ni recálculos duplicados.

## Qué se mejoró

1. **Performance y escalabilidad (FASE 4)**  
   - Índices en `trips_all` sobre columnas reales: `conductor_id`, `COALESCE(fecha_finalizacion, fecha_inicio_viaje)`, `condicion`, `fecha_inicio_viaje`, y opcionalmente (conductor_id, week, park_id).  
   - `ANALYZE public.trips_all` y `ANALYZE public.drivers`.  
   - Medir duración del refresh antes y después de índices para evidenciar reducción o estabilidad del tiempo.

2. **Validaciones ejecutables**  
   - Consistencia: A, B, C, D (cuatro bloques SQL).  
   - Cohortes: cohort_size = activations por semana, retention ≤ 1, ningún driver fuera de su cohort_week.

## Nuevas capacidades estratégicas

1. **Cohortes por park**  
   - **ops.mv_driver_cohorts_weekly:** cohort_week, park_id (dominante en semana de activación), driver_key, active_w1, active_w4, active_w8, active_w12.  
   - **ops.mv_driver_cohort_kpis:** agregado por (cohort_week, park_id): cohort_size, retention_w1, retention_w4, retention_w8, retention_w12.  
   - Permite análisis de retención por cohorte y por park (W1/W4/W8/W12) y comparar parques.

2. **Trazabilidad hasta driver_key**  
   - Toda métrica (activations, active, churned, reactivated, FT/PT, cohort) se puede bajar a lista de driver_key usando las MVs y vistas definidas.

3. **Operación y refresh**  
   - Orden de refresh documentado; función con timeout 60 min y lock_timeout 60 s; opción CONCURRENTLY y fallback nonc.  
   - Script `refresh_driver_lifecycle` + validaciones post-refresh (parks distintos, top 5, total activations).

## Evidencias esperadas

- **Consistencia:** Ejecutar los 4 bloques de `driver_lifecycle_consistency_validation.sql` y comprobar que no devuelven filas (o documentar y corregir las excepciones).  
- **Refresh:** Medir duración del refresh antes y después de crear índices y ANALYZE; documentar en runbook o doc de operación.  
- **Cohortes:** Ejecutar `driver_lifecycle_cohort_validation.sql` y verificar 0 filas en las comprobaciones de fallo.

## Orden de despliegue recomendado

1. Ejecutar **validación de consistencia** (FASE 1); si hay diffs, investigar y corregir antes de seguir.  
2. Aplicar **driver_lifecycle_hardening_v2.sql** (FASE 2–3): nueva definición de weekly_stats y weekly_kpis.  
3. Refrescar MVs; volver a ejecutar validación de consistencia.  
4. Crear **índices** (FASE 4) en ventana de bajo uso; ejecutar ANALYZE.  
5. Medir tiempo de refresh.  
6. Aplicar **driver_lifecycle_cohorts.sql** (FASE 5); luego **driver_lifecycle_refresh_with_cohorts.sql** para incluir cohort MVs en la función de refresh.  
7. Ejecutar **driver_lifecycle_cohort_validation.sql** (FASE 6).
