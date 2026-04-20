# FASE — Control & Decision Engine (Omniview Proyección)

Documentación de cierre operativo: validación, confianza, anomalías, explicabilidad y acción sugerida, sobre la base del **Projection Integrity Engine** ya desplegado.

## Qué quedó resuelto técnicamente (resumen)

- Derivación weekly/daily desde plan mensual, REAL-FIRST, conservación post-derivación, smoothing α.
- `projection_confidence` por fila (`high` | `medium` | `low`) según `trips_completed_fallback_level` y magnitud del ajuste de conservación en trips.
- `projection_anomaly` por fila cuando la celda aparece en el chequeo de volatilidad (ratio vs media de la tajada en el mes).
- Campos `{kpi}_conservation_adjustment_applied` / `{kpi}_conservation_adjustment_value` cuando se corrige la última semana/día.
- Endpoint `GET /plan/projection-integrity-audit` ampliado: weekly + daily, `temporal_alignment_issues`, `conservation_issues`, `weekly_volatility_issues`, `daily_volatility_issues`, `unreasonable_week_share`, `unreasonable_day_share`, `fallback_global_overuse`, severidades `info` | `warning` | `critical`.
- Script `backend/scripts/validate_projection_operational_integrity.py` para evidencia tabular CSV + consola.
- Front: `buildProjectionMatrix` propaga confianza/anomalía/ajuste; celda con punto ámbar (confianza baja o anomalía); drill con bloque “Confianza de proyección” y ajuste de conservación; `alertingEngine` añade `trust_notes`; panel de prioridades muestra badge “Baja conf.” cuando aplica.
- API `getProjectionIntegrityAudit` en `frontend/src/services/api.js`.

## Cómo se calcula `projection_confidence`

Referencias: `trips_completed_fallback_level`, `trips_completed_conservation_adjustment_value`, `trips_completed_projected_total`.

- **high**: `fallback_level <= 2` y porcentaje de ajuste sobre el plan shard de trips `&lt; 5%`.
- **medium**: `fallback_level <= 4` y ajuste `&lt; 15%`.
- **low**: resto (fallback amplio o ajuste de conservación grande).

## Cómo se detectan anomalías

- **Semanal**: en `_validate_weekly_output`, ratio `week_plan_trip / media_slice > 1.5` → lista de anomalías; cada fila afectada recibe `projection_anomaly = true`.
- **Diario**: `_validate_daily_output` con la misma lógica sobre `trips_completed_projected_total` por día en la tajada/mes.

## Conservación monthly → weekly → daily

1. Motor estacional + smoothing reparten el plan mensual en shares semanales/diarios.
2. `_reconcile_weekly_conservation` / `_reconcile_daily_conservation` fuerzan suma = plan mensual por tajada ajustando la **última** celda si el drift supera tolerancia (`PROJECTION_CONSERVATION_TOLERANCE_PCT` y drift absoluto).
3. Los ajustes quedan registrados en `{kpi}_conservation_adjustment_*`.

## Cómo se explica una cifra (drill)

- **Detalle curva**: método (`curve_method`), confianza de curva (`curve_confidence`), nivel de fallback, ratio esperado.
- **Ajuste conservación**: valor aplicado en el último período si hubo corrección.
- **Confianza de proyección**: síntesis operativa (alto/medio/bajo) y marca de anomalía de volatilidad.

## Cómo se traduce desviación a acción sugerida

- Reglas existentes en `alertingEngine.js` (`mapToAction`, `computePriorityScore`, `classifyAlert`).
- **Nuevas notas** (`trust_notes` en el payload de alerta): baja confianza de proyección y/o anomalía de curva, mostradas bajo “Acción sugerida” en el drill.

## Validación operativa (evidencia)

Ejecutar (con BD y `plan_version` real):

```bash
cd backend
python scripts/validate_projection_operational_integrity.py --plan-version TU_VERSION --year 2026 --month 1
```

Salida: CSV en `backend/scripts/outputs/projection_operational_integrity_<version>_<Y>_<MM>.csv`.

**Regla de cierre:** el script devuelve código distinto de 0 si hay menos de 6 combinaciones ciudad/tajada con datos entre los objetivos por defecto (Lima/auto regular, delivery, cargo; Cali auto/delivery; Barranquilla/auto regular). Sustituir nombres de tajada si en datos reales usan otro slug (ej. `auto_taxi`).

_Evidencia numérica concreta depende del entorno; adjuntar el CSV generado en staging/producción al cerrar la fase._

## Checklist de cierre (local / producción)

- [ ] Correr script de validación y archivar CSV.
- [ ] Revisar `GET /plan/projection-integrity-audit` para el mes de corte.
- [ ] Verificar S1 / cruce de año: `year_end_weeks_included` en meta de proyección y filas sin `missing_plan` indebido.
- [ ] Tras subir nueva `plan_version` mensual, confirmar que weekly/daily cambian sin pasos manuales (misma versión en UI).
- [ ] Confirmar que celdas con `projection_confidence` baja o `projection_anomaly` son visibles (punto ámbar / drill).

## Veredicto y riesgos residuales

- **Cerrado:** contrato de datos (confianza, anomalía, ajuste conservación), auditoría ampliada, UI mínima de confianza, notas en acción sugerida, script de validación.
- **Riesgo:** confianza es heurística (fallback + % ajuste); no sustituye revisión humana en decisiones críticas.
- **Pendiente para productivo pleno:** ejecutar validación sobre **datos reales** de producción y archivar evidencia; ajustar umbrales de share (0.10–0.40 semanal, 0.02–0.25 diario) si el negocio lo requiere.
