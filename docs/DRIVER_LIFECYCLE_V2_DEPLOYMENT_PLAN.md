# Driver Lifecycle v2 — Plan de despliegue seguro

## Ventana recomendada

- **Duración estimada:** 15–45 min (según tamaño de datos).
- **Ventana:** Bajo uso de la BD; sin jobs críticos en paralelo.
- **Rollback:** Disponible en `backend/sql/rollback/` (generado por preflight).

## Fases

### 1. Preflight (obligatorio)

- Confirmar existencia de MVs en `ops`: `mv_driver_weekly_stats`, `mv_driver_lifecycle_weekly_kpis`, `mv_driver_monthly_stats`, `mv_driver_lifecycle_monthly_kpis`.
- Guardar viewdefs con `pg_get_viewdef` en `backend/sql/rollback/`:
  - `rollback_mv_driver_weekly_stats.sql`
  - `rollback_mv_driver_lifecycle_weekly_kpis.sql`
  - `rollback_v_driver_weekly_churn_reactivation.sql` (si existe)
- Si alguna MV no existe, el script puede continuar (deploy inicial) o abortar según configuración.

### 2. Baseline de consistencia

- Ejecutar `driver_lifecycle_consistency_validation.sql` (bloques A–D).
- Guardar resultados en log; no bloquear por diffs (solo registrar baseline).

### 3. Hardening v2

- Ejecutar `driver_lifecycle_hardening_v2.sql`.
- **Impacto:** DROP de `mv_driver_weekly_stats`, `mv_driver_lifecycle_weekly_kpis`, `v_driver_weekly_churn_reactivation`; CREATE con nueva definición (park_dominante).
- Durante la ejecución las vistas no estarán disponibles.

### 4. Refresh

- Ejecutar `ops.refresh_driver_lifecycle_mvs()`.
- Medir duración.

### 5. Validación post-hardening

- Ejecutar consistency validation de nuevo.
- **Gate:** Si hay filas con diff ≠ 0 → FAIL, sugerir inspección y rollback.

### 6. Índices y ANALYZE

- Ejecutar `driver_lifecycle_indexes_and_analyze.sql` (CREATE INDEX CONCURRENTLY).
- Ejecutar ANALYZE en `trips_all` y `drivers`.
- Medir duración del refresh antes y después.

### 7. Cohortes

- Si no existen: ejecutar `driver_lifecycle_cohorts.sql`.
- Ejecutar `driver_lifecycle_refresh_with_cohorts.sql` (actualiza función de refresh).
- Ejecutar refresh de nuevo.

### 8. Validación de cohortes

- Ejecutar `driver_lifecycle_cohort_validation.sql`.
- **Gate:** Si retention > 1 o cohort_size no cuadra → FAIL.

### 9. Quality gates

- Contar parks distintos en `weekly_stats`.
- Contar % driver-weeks con `park_id` NULL.
- Si NULL% > 5%: WARNING fuerte (no fallar por defecto).

## Rollback

Si hay fallos críticos tras el hardening:

1. Restaurar MVs desde `backend/sql/rollback/`:
   - Ejecutar cada `rollback_*.sql` (CREATE MATERIALIZED VIEW con viewdef guardado).
   - Recrear índices únicos necesarios para REFRESH CONCURRENTLY.
2. Ejecutar refresh.
3. Validar consistencia de nuevo.

**Nota:** El rollback no revierte índices creados (DROP INDEX si se desea revertir).

## Script automatizado

```bash
cd backend
python -m scripts.apply_driver_lifecycle_v2
```

Exit code 0 = OK; exit code != 0 = fallo en validaciones o ejecución.
