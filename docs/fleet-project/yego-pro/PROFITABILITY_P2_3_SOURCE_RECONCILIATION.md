# Yego Pro Profitability P2.3 -- Source Reconciliation

## Date: 2026-05-28
## Park: 64085dd85e124e2c808806f70d527ea8 (Lima)

---

## PHASE 1 -- SCHEMA DISCOVERY

### module_weekly_billing (34 columns, 26 rows)
Grain: **driver + week** (fecha_inicio, fecha_fin)
Date range: **2026-05-18 to 2026-05-24** (1 single week)

Key columns:
| Column | Type | Purpose |
|--------|------|---------|
| driver_id | varchar(255) | FK to drivers |
| fecha_inicio / fecha_fin | date | Week boundaries |
| total_viajes | integer | Trip count |
| horas_trabajo | double | Hours worked |
| monto_total_producido | numeric | Gross revenue |
| comision_app | numeric | Platform commission |
| monto_neto | numeric | Net revenue |
| km_recorrido | numeric | Km (includes dead km) |
| gasto_combustible | numeric | Fuel cost |
| gasto_mantenimiento | numeric | Maintenance cost |
| porcentaje_pago | double | Driver payment % |
| pago_total | numeric | Total payout to driver |
| utilidad | numeric | Profit/loss |
| turno | varchar(10) | Shift type |
| estado | varchar(15) | Status |
| bono_yango / bono_adic_viajes | numeric | Bonuses |
| bonificacion / garantia / descuento | numeric | Additional financial adjustments |

### module_driver_closes (23 columns, 349 rows)
Grain: **driver + date** (driver_id, fecha)
Date range: **2026-05-11 to 2026-05-27** (17 days)
Park-filtered: 349 rows, 30 drivers

Key columns:
| Column | Type | Purpose |
|--------|------|---------|
| driver_id | varchar(255) | FK to drivers |
| fecha | date | Settlement date |
| gnv_m3 / gnv_soles | varchar/numeric | GNV fuel (volume + cost) |
| gasolina_galones / gasolina_soles | varchar/numeric | Gasoline (volume + cost) |
| liquida_efectivo | numeric | Cash settlement |
| liquida_yape | numeric | Yape (digital) settlement |
| otros_gastos | numeric | Other expenses |
| total_ingresos | numeric | Total daily income |
| total_gastos | numeric | Total daily expenses |
| resta | numeric | Daily remainder (income - expenses) |
| calculated_shift_ids | varchar(255) | References to shifts (ALL 349 rows have values) |
| odometro_inicial / odometro_final | integer | Odometer readings |
| diferencia_odometro | integer | Km driven (odometer-based) |
| placa | varchar(20) | Vehicle plate |

### module_calculated_shifts (17 columns, 1,026 rows)
**TABLE EXISTS** -- Not referenced in any backend code but present in database.
Grain: **driver + date + shift** (driver_id, fecha, hora_inicio, tipo_turno)
Date range: **2026-04-23 to 2026-05-27** (35 days)
Park-filtered: 1,026 rows

Key columns:
| Column | Type | Purpose |
|--------|------|---------|
| driver_id | varchar(255) | FK to drivers |
| fecha | date | Shift date |
| hora_inicio / hora_fin | timestamp | Actual shift start/end times |
| tipo_turno | varchar(10) | Shift type (native, not derived) |
| estado | varchar(10) | Shift status |
| duracion_minutos | integer | Shift duration |
| monto_total | double | Total amount per shift |
| produccion_total | double | Total production per shift |
| comisiones_servicio | double | Service commissions per shift |
| cantidad_viajes | integer | Trip count per shift |
| placa | varchar(20) | Vehicle plate (561 nulls = 55%) |
| es_manual | boolean | Whether manually created |
| pagado | boolean | Whether paid |

### trips_2026 (25 columns, 81,140 rows for park)
Grain: **individual trip**
Date range: **2026-01-01 to 2026-05-27** (5 months)
84 distinct drivers

---

## PHASE 2 -- GRAIN ANALYSIS

| Table | Grain | Rows | Drivers | Periods | Unique Combos | Period Type |
|-------|-------|------|---------|---------|---------------|-------------|
| module_weekly_billing | driver + week | 26 | 26 | 1 week | 26 | weekly |
| module_driver_closes | driver + date | 349 | 30 | 17 days | 349 (unique) | daily |
| module_calculated_shifts | driver + date + shift | 1,026 | ~30 | 35 days | 1,026 | shift-level |
| trips_2026 | individual trip | 81,140 | 84 | 147 days | 3,869 driver-days | timestamp |

Key: `module_calculated_shifts` has 3x more rows than `module_driver_closes` because multiple shifts per driver per day.

---

## PHASE 3 -- RECONCILIATION

### A. trips_2026 vs module_weekly_billing
- **22 weeks compared**
- **0 trip count mismatches** (threshold: >2)
- **Revenue reconciles cleanly**
- Status: **HIGH CONFIDENCE CROSS**

### B. module_driver_closes vs module_weekly_billing
- **26 BOTH** (matching driver-weeks)
- **0 BILLING_ONLY**
- **49 CLOSE_ONLY** (closes exist for weeks without billing -- weeks before 2026-05-18)
- Status: **PARTIAL COVERAGE -- billing only has 1 week, closes have 2.5 weeks**

### C. trips_2026 vs module_driver_closes
- **1,017 driver-days with trips but NO close**
- **0 driver-days with close but NO trips**
- Close coverage: **only 35.7%** (30 of 84 drivers have closes)
- Status: **SIGNIFICANT GAP -- most production days lack daily settlement**

---

## PHASE 4 -- SOURCE OF TRUTH MAP

### Production
| Metric | Source of Truth | Secondary Check | Confidence |
|--------|----------------|-----------------|------------|
| trips | trips_2026 | billing.total_viajes | HIGH |
| revenue_gross | trips_2026.precio_yango_pro | billing.monto_total_producido | HIGH |
| km | trips_2026.distancia_km | billing.km_recorrido | HIGH |
| shift (day/night) | module_calculated_shifts.tipo_turno | DERIVED from trips timestamp | HIGH |
| vehicle_active | module_calculated_shifts.placa | module_driver_closes.placa | LOW (55% null in shifts) |
| driver_active | trips_2026 (DISTINCT conductor_id) | billing (DISTINCT driver_id) | HIGH |

### Settlement
| Metric | Source of Truth | Secondary Check | Confidence |
|--------|----------------|-----------------|------------|
| payout_driver | billing.pago_total | closes.resta (daily) | HIGH |
| discounts | billing.comision_app | N/A | HIGH |
| bonos | billing.bono_yango + bono_adic_viajes | N/A | HIGH |
| advance_payments | NOT_AVAILABLE | closes.liquida_efectivo + liquida_yape | LOW |
| final_amount | billing.pago_total | closes.resta | HIGH |

### Billing (P&L)
| Metric | Source of Truth | Secondary Check | Confidence |
|--------|----------------|-----------------|------------|
| real_income | billing.monto_total_producido | trips revenue agg | HIGH |
| fuel | billing.gasto_combustible | closes.gnv_soles + gasolina_soles | HIGH |
| maintenance | billing.gasto_mantenimiento | N/A | HIGH |
| profit/loss | billing.utilidad | DERIVED (revenue - all costs) | HIGH |

---

## PHASE 5 -- OPERATIONAL FINDINGS

### FINDING 1: 24 of 26 drivers are in LOSS
Only 2 of 26 drivers were profitable in the single billing week (2026-05-18 to 2026-05-24).
Worst case: driver f1cdbbb6, profit = -S/ 427.94, payout only 10.1% of revenue.
**92% of drivers destroy value.**

### FINDING 2: Cost structure
- Payout to drivers: **27.0%** of revenue
- Fuel: **11.3%** of revenue
- Maintenance: **11.1%** of revenue
- Remaining ~50% goes to platform commission, bonuses, and other costs
**Payout is the largest controllable cost but at 27% is NOT the dominant factor. The combination of all costs exceeds revenue.**

### FINDING 3: Close coverage is only 35.7%
Only 30 of 84 park drivers have daily closes. 1,017 driver-days have production but no settlement record.
**This means daily P&L tracking is incomplete for 64% of drivers.**

### FINDING 4: Daily closes show positive remainder
All 349 daily closes show income > expenses (avg remainder S/ 132.00).
But billing shows loss. This suggests the daily close captures only operational cash flow (fuel, yape), not the full cost structure (commission, maintenance, quotas).

### FINDING 5: module_calculated_shifts is UNTAPPED
1,026 shift records exist with native shift types, production totals, trip counts, and vehicle plates. This table is **not used by any backend code**. It could replace the derived DAY/NIGHT calculation from trip timestamps with actual operational shift data.

---

## PHASE 6 -- OUTPUT FILES

| File | Rows | Content |
|------|------|---------|
| `reports/yego_pro_source_inventory.csv` | 4 | Schema inventory of all 4 tables |
| `reports/yego_pro_table_grains.csv` | 3 | Grain analysis per table |
| `reports/yego_pro_reconciliation_summary.csv` | 119 | Cross-table reconciliation details |
| `reports/yego_pro_metric_source_of_truth.csv` | 17 | Metric-to-source mapping |
| `reports/yego_pro_data_gaps.csv` | 2 | Identified data gaps |

---

## PHASE 7 -- VERDICT

### Q1: Which table should govern daily production?
**trips_2026** -- Atomic trip-level data. Highest granularity. 81,140 rows, 5 months.

### Q2: Which table should govern driver payments?
**module_weekly_billing.pago_total** -- Official weekly payout. module_driver_closes has daily settlement but 35.7% coverage.

### Q3: Which table should govern weekly profitability?
**module_weekly_billing.utilidad** -- Complete P&L per driver per week. Only 1 week available.

### Q4: Which crosses are reliable?
**trips_2026 <-> module_weekly_billing** -- Trip counts and revenue reconcile at weekly grain with 0 mismatches.

### Q5: Which crosses are unreliable?
**module_driver_closes <-> module_weekly_billing** -- Different grains (daily vs weekly), different semantics (operational cash flow vs full billing), 35.7% coverage.

### Q6: What is revelatory for operations?
- **module_calculated_shifts** is untapped gold: shift-level production with native tipo_turno, durations, vehicle plates
- **module_driver_closes** has dual fuel types (GNV + gasoline), odometer readings for km validation, and daily cash flow splits
- **92% of drivers are in loss** in the single billing week

### Q7: What should be incorporated before the simulator?
1. **Ingest module_calculated_shifts** into serving layer for native shift profitability (not derived from timestamps)
2. **Validate km**: odometer (closes.diferencia_odometro) vs km_recorrido (billing) vs distancia_km (trips)
3. **Split fuel costs**: GNV vs gasoline from closes for cost modeling accuracy
4. **Increase billing coverage**: Only 1 week exists. Need at least 4 weeks for trends.

### Q8: Ready for P3 Scenario Engine?
**CONDITIONAL GO.**
- Serving facts are solid for module_weekly_billing
- Vehicle assignment is PARTIALLY available via module_calculated_shifts.placa (55% coverage) and module_driver_closes.placa
- module_driver_closes is untapped
- Need at least 4 billing weeks for meaningful simulation
- Recommend: ingest module_calculated_shifts + wait for more billing weeks before P3

---

## Script
`backend/scripts/yego_pro_source_reconciliation.py` (read-only, no data modifications)
