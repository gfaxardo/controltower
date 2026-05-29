# Yego Pro Profitability P2.4 -- Data Hardening Report

## Date: 2026-05-28
## Park: 64085dd85e124e2c808806f70d527ea8 (Lima)

---

## Resumen Ejecutivo

P2.4 endurecio la capa de datos de Profitability incorporando 3 fuentes nativas que antes eran parciales o no usadas: module_calculated_shifts, module_driver_closes, y module_weekly_billing. Se crearon 4 nuevos materialized views y se actualizo el backend service con coverage metrics, warnings, y source-of-truth mapping.

---

## 1. Fuentes incorporadas

### module_calculated_shifts (PRODUCCION diaria)
- **1,026 filas** de shifts nativos (driver, fecha, turno, produccion, comisiones)
- **Rango:** 2026-04-23 a 2026-05-27 (26 dias)
- **Antes:** No usado por ningun backend code. Shifts eran derivados de timestamps de trips.
- **Ahora:** Source of truth para produccion diaria, tipo de turno nativo, revenue por shift, duracion.
- **MV:** `ops.mv_yego_pro_shift_daily`
- **Limitacion:** Placa disponible en solo 45.3% de registros.

### module_driver_closes (LIQUIDACION conductor)
- **349 filas** de cierres diarios (30 drivers, 17 dias)
- **Rango:** 2026-05-11 a 2026-05-27
- **Antes:** Documentado pero nunca usado en backend.
- **Ahora:** Source of truth para payout diario, split de combustible (GNV vs gasolina), settlement cash/yape, validacion km via odometro.
- **MV:** `ops.mv_yego_pro_driver_close_week`
- **Limitacion:** Solo 14.9% de conductores registrados tienen cierres.

### module_weekly_billing (FINANCIERO semanal)
- **26 filas** de billing (26 drivers, 1 semana)
- **Rango:** 2026-05-18 a 2026-05-24
- **Ya era source of truth.** No cambio.
- **MV nueva:** `ops.mv_yego_pro_weekly_financial_truth` (consolidado a nivel park con cost breakdown y billing_status).
- **Limitacion:** Solo 1 semana. Se necesitan 4+ para tendencias.

---

## 2. Materialized Views creadas

| MV | Rows | Date Range | Fuente |
|----|------|------------|--------|
| `ops.mv_yego_pro_shift_daily` | 1,026 | 2026-04-23 -> 2026-05-27 | module_calculated_shifts |
| `ops.mv_yego_pro_driver_close_week` | 75 | 2026-05-11 -> 2026-05-25 | module_driver_closes |
| `ops.mv_yego_pro_weekly_financial_truth` | 1 | 2026-05-18 -> 2026-05-18 | module_weekly_billing |
| `ops.mv_yego_pro_source_coverage` | 1 | N/A (coverage metrics) | Multi-source |

Todas las MVs se refrescaron correctamente. La validacion muestra 8 MVs con status=OK.

---

## 3. Source of Truth por capa

| Capa | Fuente principal | KPIs clave | Confianza |
|------|-----------------|------------|-----------|
| **PRODUCCION** | module_calculated_shifts | trips, revenue, shift_type, placa, duracion | HIGH (MEDIUM para placa) |
| **LIQUIDACION** | module_driver_closes | payout diario, GNV/gasolina, liquidacion cash/yape, km odometro | MEDIUM |
| **FINANCIERO** | module_weekly_billing | revenue, costos, payout, utilidad, margen | HIGH |

---

## 4. Coverage & Warnings

### Coverage actual
| Metrica | Valor | Estado |
|---------|-------|--------|
| Billing weeks | 1 | **PARTIAL** (necesita 4+) |
| Shift days | 26 | HEALTHY |
| Trip days | 147 | HEALTHY |
| Plate coverage (shifts) | 45.3% | **BAJO 50%** |
| Close driver coverage | 14.9% | **BAJO 80%** |
| Financial history | PARTIAL | Unica semana |
| Operational history | HEALTHY | 26 dias de shifts |

### Warnings activos
1. **BILLING_1_WEEK** (HIGH): Solo 1 semana de billing. Imposible hacer tendencias.
2. **PLATE_COVERAGE** (MEDIUM): 45.3% de shifts tienen placa. Asignacion vehiculo-conductor incompleta.
3. **CLOSE_COVERAGE** (MEDIUM): 14.9% de drivers tienen cierres. Liquidacion diaria limitada.

---

## 5. Backend Service hardening

### get_overview
- Agrego `source_coverage` con metricas de coverage
- Agrego `data_confidence_by_layer` (operation: HIGH, closes: MEDIUM, billing: PARTIAL, simulation: N/A)
- Agrego `financial_history_status` y `operational_history_status`

### get_shifts
- Ahora usa preferentemente `mv_yego_pro_shift_daily` (native shifts de module_calculated_shifts)
- Fallback al MV derivado si el native no existe
- Devuelve `shift_source` indicando cual se uso y nivel de confianza

### get_quality
- Agrego coverage metrics de `mv_yego_pro_source_coverage`
- Agrego array `warnings` con severidad y mensajes
- Agrego 5 nuevas MVs al check (shift_daily, close_week, financial_truth, source_coverage)
- Overall status ahora incluye WARNING si hay billing <4 semanas o plate <80%

### get_input_mapping
- Reorganizado en 3 categorias: `inputs_production`, `inputs_settlement`, `inputs_financial`
- Cada input muestra `source_table` y `role` (SOURCE_OF_TRUTH, SECONDARY_CHECK)
- Agrego `source_of_truth` declarativo por capa

---

## 6. Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `backend/sql/yego_pro_profitability_serving_views.sql` | +4 MVs nuevas (+210 lineas) |
| `backend/app/services/yego_pro_profitability_service.py` | Hardening de overview, shifts, quality, input-mapping |
| `backend/scripts/yego_pro_p2_4_validate.py` | Script de validacion read-only |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_4_DATA_HARDENING.md` | Este documento |

### Output files generados
| Archivo | Filas |
|---------|-------|
| `reports/yego_pro_p2_4_validation.csv` | 8 MVs validadas |
| `reports/yego_pro_p2_4_coverage.csv` | 30 metricas de coverage |
| `reports/yego_pro_p2_4_metric_sources.csv` | 16 KPIs mapeados |

---

## 7. Archivos NO tocados

- Drivers: NINGUNO
- Yango Loyalty: NINGUNO
- Omniview: NINGUNO
- Frontend: NINGUNO
- Migraciones: NINGUNA
- UPDATE/DELETE: NINGUNO

---

## 8. Veredicto (Phase 6)

### Q1: module_calculated_shifts incorporado?
**SI.** MV `mv_yego_pro_shift_daily` creada con 1,026 filas. Shifts native con tipo_turno, produccion, revenue. Service `get_shifts` lo usa como source primaria.

### Q2: module_driver_closes incorporado?
**SI.** MV `mv_yego_pro_driver_close_week` creada con 75 filas. Service expone settlement diario, payout, combustible split, km validated.

### Q3: module_weekly_billing sigue como financial truth?
**SI.** Sin cambios en su rol. MV `weekly_financial_truth` consolida el P&L semanal con breakdown de costos.

### Q4: Coverage conductor-vehiculo?
**45.3%** de shifts tienen placa. Mejoro respecto al 0% anterior (no habia ningun vinculo). Pero sigue bajo 80%.

### Q5: Semanas de billing?
**1 semana** (2026-05-18 a 2026-05-24). Muy insuficiente para tendencias.

### Q6: Dias de shifts?
**26 dias** (2026-04-23 a 2026-05-27). HEALTHY.

### Q7: KPIs confiables?
- **HIGH:** Produccion diaria (trips, revenue, shift_type, duracion)
- **MEDIUM:** Liquidacion diaria (payout, combustible, settlement)
- **HIGH:** Financiero semanal (revenue, costos, utilidad, margen)

### Q8: KPIs parciales?
- Payout diario: solo 14.9% de drivers
- Placa/vehiculo: solo 45.3% de shifts
- Billing historico: solo 1 semana
- Km validated: odometro confianza LOW

### Q9: Listo para prueba humana UI?
**GO.** La capa de datos ahora tiene:
- Production: module_calculated_shifts (native)
- Settlement: module_driver_closes (diario)
- Financial: module_weekly_billing (semanal)
- Coverage visible con warnings claros

### Q10: Listo para P3 Simulator?
**NO.**
- Solo 1 semana de billing -> minimo 4 necesarias
- Plate coverage 45% -> necesita >=80% para simulacion por vehiculo
- Close coverage 14.9% -> payout diario no confiable para simulacion
- **Recomendacion:** Esperar que billing acumule 4+ semanas y que el coverage de placa y cierres mejore antes de avanzar a P3.
