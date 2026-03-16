# Memo técnico final — Módulo REAL (Control Tower)

## 1. Definición canónica de margen_total

- **Semántica negocio:** Margen mostrado al usuario en **signo positivo** (margen favorable).
- **Origen en fact:** `v_real_trip_fact_v2.margin_total = comision_empresa_asociada` (signo contable, puede ser negativo).
- **Capa canónica (drill):** En `populate_real_drill_from_hourly_chain` se escribe en `real_drill_dim_fact`:  
  `margin_total = ABS(SUM(margin_total))` desde `mv_real_lob_day_v2` / `mv_real_lob_week_v3`.
- **Servicio:** `real_lob_drill_pro_service` normaliza a positivo en lectura (para filas legacy con signo negativo):  
  `ad["margen_total"] = abs(float(ad["margen_total"]))` en `agg_detail` y en children.
- **Rollup diario:** `real_rollup_day_fact` (vista desde day_v2) ya expone `margin_total_pos = ABS(SUM(margin_total))`.

## 2. Definición canónica de margen_trip

- **Fórmula:** `margen_trip = margen_total / viajes` (solo cuando viajes > 0), con la misma semántica de signo que margen_total.
- **En populate:** `margin_per_trip = ABS(SUM(margin_total)) / SUM(completed_trips)` cuando hay completados.
- **En servicio:** Se normaliza igual que margen_total (abs en lectura).

## 3. Definición de WoW / MoM

- **Cálculo:** Sobre métricas **ya normalizadas** (positivo):  
  `delta_pct = (current - previous) / previous * 100`, `trend = "up" | "down" | "flat"` según current vs previous.
- **Aplicado a:** viajes, margen_total, margen_trip, km_prom, pct_b2b, **cancelaciones**.
- **Fuente:** Siempre desde `real_drill_dim_fact` agregado por (country, period_start); periodo anterior = `period_start - 7d` (WoW) o mes anterior (MoM).

## 4. Definición de cancelaciones

- **Fuente:** `mv_real_lob_day_v2` y `mv_real_lob_week_v3` tienen `cancelled_trips` (y `requested_trips`, `completed_trips`).
- **Drill:** Columna `ops.real_drill_dim_fact.cancelled_trips` (migración 103); poblada por `populate_real_drill_from_hourly_chain` con `SUM(cancelled_trips)`.
- **API:** Por fila: `cancelaciones`, `cancelaciones_prev`, `cancelaciones_delta_pct`, `cancelaciones_trend`. En KPIs: `cancelaciones` (total).
- **UI:** Columnas "Cancel." y WoW % en el drill y en children.

## 5. Ruta oficial hourly-first

1. **Refresh cadena:** `scripts.refresh_hourly_first_chain` → hour_v2 → day_v2 → week_v3 → month_v3.
2. **Rollup diario:** Sin paso; `real_rollup_day_fact` es vista sobre day_v2 (101).
3. **Drill:** `scripts.populate_real_drill_from_hourly_chain` (tras refresh), con `--days 120 --weeks 18` por defecto.
4. **Pipeline orquestado:** `scripts.run_pipeline_refresh_and_audit` ejecuta lo anterior; **no** ejecuta `backfill_real_lob_mvs`.

## 6. Guardrails anti-regresión

- **Doble inserción:** `backfill_real_lob_mvs` por defecto **no** escribe en `real_drill_dim_fact`; requiere `--allow-write-drill`. Rollup es vista, no se inserta.
- **Auditoría:** `scripts.audit_real_margin_and_coverage` comprueba cobertura reciente, signo de margen, duplicidad por grain, presencia de cancelaciones en day_v2 y en drill.
- **Documentación:** `docs/REAL_PIPELINE_OFFICIAL_AND_GUARDRAILS.md` y `docs/REAL_MODULE_FASE0_SCAN_AND_DIAGNOSIS.md`.

## 7. Archivos modificados / creados (resumen)

| Área | Archivo | Cambio |
|------|---------|--------|
| FASE 0 | docs/REAL_MODULE_FASE0_SCAN_AND_DIAGNOSIS.md | Creado: mapa técnico y diagnóstico |
| FASE 1 | backend/scripts/audit_real_margin_and_coverage.py | Creado: auditoría margen, cobertura, duplicidad, cancelaciones |
| FASE 2 | backend/scripts/populate_real_drill_from_hourly_chain.py | ABS(margin_total) y ABS(margin_per_trip) en todos los INSERT |
| FASE 2 | backend/app/services/real_lob_drill_pro_service.py | Normalización abs() en agg_detail y children; WoW sobre margen positivo |
| FASE 3 | docs/REAL_PIPELINE_OFFICIAL_AND_GUARDRAILS.md | Creado: ruta oficial y guardrails |
| FASE 3 | backend/scripts/backfill_real_lob_mvs.py | --allow-write-drill; skip drill por defecto; skip_rollup=True |
| FASE 4 | backend/alembic/versions/103_real_drill_dim_fact_cancelled_trips.py | Columna cancelled_trips en real_drill_dim_fact |
| FASE 4 | populate_real_drill_from_hourly_chain.py | INSERT de cancelled_trips desde day_v2/week_v3 |
| FASE 4 | real_lob_drill_pro_service.py | cancelaciones en agg_detail, row, KPIs, _add_row_comparative, _add_child_comparative; fallback si columna no existe |
| FASE 5 | frontend/src/components/RealLOBDrillView.jsx | Columnas Cancel. y WoW %; colSpan 15 en subrows |
| FASE 6 | docs/REAL_MODULE_MEMO_FINAL_ARQUITECTURA.md | Este memo |

## 8. Validación recomendada

1. Ejecutar migración 103: `alembic upgrade head`.
2. Ejecutar `populate_real_drill_from_hourly_chain` (o pipeline completo) para repoblar drill con margen en positivo y cancelaciones.
3. Ejecutar `audit_real_margin_and_coverage`: comprobar 0 duplicados, margen no negativo en periodos recientes, cancelaciones presentes en day_v2 y en drill.
4. En UI: comprobar que en semanas recientes se ven margen_total y margen_trip, que el WoW de margen es coherente (positivo = mejora) y que Cancel. y WoW cancelaciones se muestran en el drill.

---

**Fin del memo.** Arquitectura funcional del módulo REAL unificada: margen en positivo, WoW coherente, cancelaciones integradas, una sola ruta de inserción para el drill y guardrails documentados.
