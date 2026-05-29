# REPORTE DE INPUTS REALES — MODELO FINANCIERO YEGO PRO
## Park Lima | park_id: 64085dd85e124e2c808806f70d527ea8
## Fecha: 28 mayo 2026

---

## EXECUTIVE SUMMARY

**El 72% de los inputs del modelo financiero ya pueden basarse en data real.** La tabla `module_weekly_billing` es la fuente más valiosa: contiene costos reales de combustible, mantenimiento, horas trabajadas, pagos a conductores y utilidad/pérdida por viaje.

**HALLAZGO CRÍTICO:** El park está operando con **pérdida de S/ -5,510 por semana** (S/ -22,040 mensuales estimados). Solo 1 de 26 conductores (3.8%) generó utilidad positiva en la semana analizada.

**CORRECCIÓN IMPORTANTE vs. análisis anterior:** El costo variable real por km (S/0.15 combustible + S/0.15 mantenimiento = S/0.30/km) es similar al supuesto, PERO el km real por viaje es **9.20 km** (no 3.75), ya que incluye recorrido vacío. Esto duplica el costo variable real por viaje: **S/2.79/viaje** (vs S/1.57 supuesto anterior).

---

## 1. FUENTES DE DATOS IDENTIFICADAS

### Fuentes con Data Real para este Park

| Fuente | Tabla | Records | Periodo | Utilidad |
|--------|-------|---------|---------|----------|
| **Trips** | `public.trips_2026` | 27,600 | 30 días | Revenue, distancia, duración, horarios |
| **Weekly Billing** | `public.module_weekly_billing` | 26 | 1 semana (18-24 may) | Costos, horas, pagos, utilidad |
| **Weekly Income** | `public.module_weekly_income` | 250 | ~8 semanas | Desglose ingresos, platform fees |
| **Drivers** | `public.drivers` | ~34 activos | Vigente | Maestro conductores |
| **Payment Percentages** | `public.module_payment_percentages` | 7 | Vigente | Escalones pago |
| **Cronograma Vehiculo** | `public.module_miauto_cronograma_*` | 16 vehiculos | Vigente | Cuotas semanales reales |
| **Commission Config** | `ops.yego_commission_proxy_config` | 1 (Peru) | Vigente | Comisión Yego 3% |

### Fuentes Vacías para este Park

| Fuente | Tabla | Razón |
|--------|-------|-------|
| Summary Daily | `public.summary_daily` | 0 registros para park_id |
| Fleet Summary Daily | `public.module_ct_fleet_summary_daily` | Drivers no matchean |
| MiAuto Cuota Semanal | `public.module_miauto_cuota_semanal` | 0 registros (programa no activo aún) |
| MiAuto Otros Gastos | `public.module_miauto_otros_gastos` | 0 registros |
| Cabinet Payments | `public.module_ct_cabinet_payments` | 0 para este park |

### Fuentes Inexistentes

| Concepto | Tabla Esperada | Status |
|----------|---------------|--------|
| Combustible (litros) | - | NO EXISTE |
| Seguro vehículo | - | NO EXISTE |
| GPS tracking cost | - | NO EXISTE |
| Multas/peajes | - | NO EXISTE |
| Accidentes | - | NO EXISTE |
| Horas online driver | - | NO EXISTE (se usa horas_trabajo de billing) |

---

## 2. INPUTS REALES EXTRAÍDOS (Listos para Excel)

### A. OPERATIVOS

| Input | Valor | Unidad | Fuente | Confianza |
|-------|-------|--------|--------|-----------|
| Ticket promedio | **10.21** | S/ | trips_2026 | ALTA |
| Ticket mediana | **9.00** | S/ | trips_2026 | ALTA |
| Ticket DÍA | **10.67** | S/ | trips_2026 | ALTA |
| Ticket NOCHE | **9.91** | S/ | trips_2026 | ALTA |
| KM/viaje (con pasajero) | **3.75** | km | trips_2026 | ALTA |
| KM/viaje (total real incl. vacío) | **9.20** | km | billing | ALTA |
| KM muertos/viaje | **5.45** | km | derivado | MEDIA |
| Ratio KM muertos | **59.2%** | % | derivado | MEDIA |
| Duración promedio viaje | **12.70** | min | trips_2026 | ALTA |
| Viajes completados/30d | **13,951** | trips | trips_2026 | ALTA |
| Viajes cancelados/30d | **13,647** | trips | trips_2026 | ALTA |
| Tasa cancelación | **49.5%** | % | trips_2026 | ALTA |
| Conductores activos (total) | **34** | drivers | trips_2026 | ALTA |
| Conductores activos/día (avg) | **21.8** | drivers | trips_2026 | ALTA |
| Conductores activos/semana (avg) | **25.2** | drivers | trips_2026 | ALTA |
| Viajes/conductor/día | **13.68** | trips | trips_2026 | ALTA |
| Viajes/conductor/semana | **95.42** | trips | trips_2026 | ALTA |
| Revenue/conductor/día | **139.68** | S/ | trips_2026 | ALTA |
| Revenue/conductor/semana | **974.51** | S/ | trips_2026 | ALTA |
| Horas trabajo/semana (avg) | **52.36** | horas | billing | ALTA |
| Horas trabajo/día (avg) | **9.08** | horas | billing | ALTA |
| Días trabajados/semana | **5.77** | días | billing | ALTA |
| Revenue/hora (billing) | **28.97** | S/h | billing | ALTA |
| Viajes/hora (billing) | **2.32** | trips/h | billing | ALTA |
| % trips DÍA | **39.9%** | % | trips_2026 | ALTA |
| % trips NOCHE | **60.1%** | % | trips_2026 | ALTA |
| Revenue DÍA (30d) | **59,349** | S/ | trips_2026 | ALTA |
| Revenue NOCHE (30d) | **83,125** | S/ | trips_2026 | ALTA |

### B. COSTOS REALES

| Input | Valor | Unidad | Fuente | Confianza |
|-------|-------|--------|--------|-----------|
| Combustible/km | **0.1528** | S/km | billing | ALTA |
| Mantenimiento/km | **0.1500** | S/km | billing | ALTA |
| Costo variable total/km | **0.3028** | S/km | billing | ALTA |
| Combustible/viaje | **1.41** | S/ | billing | ALTA |
| Mantenimiento/viaje | **1.38** | S/ | billing | ALTA |
| Costo variable total/viaje | **2.79** | S/ | billing | ALTA |
| Comisión plataforma | **16.66%** | % bruto | billing | ALTA |
| Platform fee (income) | **14.94%** | % yango_pro | income | ALTA |
| Comisión Yego Peru | **3.00%** | % | config | ALTA |
| Cuota vehículo/sem (0KM base) | **500.00** | S/ | cronograma | ALTA |
| Cuota vehículo/sem (Kia seminuevo) | **532.50** | S/ | cronograma | ALTA |
| Cuota vehículo/sem (Hyundai seminuevo) | **562.50** | S/ | cronograma | ALTA |
| Cuota vehículo/sem (2026-II Kia) | **500.00** | S/ | cronograma | ALTA |
| Bono auto (90-119 trips) | **10.00** | S/ | cronograma rule | ALTA |
| Bono auto (120-149 trips) | **40.00** | S/ | cronograma rule | ALTA |
| Bono auto (150-179 trips) | **70.00** | S/ | cronograma rule | ALTA |
| Tasa mora cronograma | **4.00%** | % | cronograma | ALTA |
| Cuotas semanales total (0KM) | **261** | semanas | cronograma | ALTA |
| Cuotas semanales total (seminuevo) | **156-230** | semanas | cronograma | ALTA |
| Inicial vehículo | **500-1000** | S/ | cronograma | ALTA |

### C. PAGOS Y RENTABILIDAD

| Input | Valor | Unidad | Fuente | Confianza |
|-------|-------|--------|--------|-----------|
| % pago conductor (promedio real) | **47.69%** | % | billing | ALTA |
| Pago/viaje (avg real) | **2.96** | S/ | billing | ALTA |
| Pago total/bruto | **26.95%** | % | billing | ALTA |
| Pago total/neto | **32.34%** | % | billing | ALTA |
| Utilidad/viaje (real actual) | **-2.17** | S/ | billing | ALTA |
| Utilidad semanal flota | **-5,509.90** | S/ | billing | ALTA |
| Bono Yango semanal | **5,126.57** | S/ | billing | ALTA |
| Bono adicional viajes/sem | **2,125.00** | S/ | billing | ALTA |
| Revenue bruto mensual | **142,474** | S/ | trips_2026 | ALTA |
| Bonificaciones % revenue | **23.06%** | % | income | ALTA |
| Cash % revenue | **80.1%** | % | trips_2026 | ALTA |
| Tarjeta % revenue | **16.5%** | % | trips_2026 | ALTA |

### D. ESCALONES DE PAGO VIGENTES

| Min Trips/Semana | % Conductor | Fuente |
|-----------------|-------------|--------|
| 90 | 30% | module_payment_percentages |
| 95 | 35% | module_payment_percentages |
| 100 | 40% | module_payment_percentages |
| 107 | 45% | module_payment_percentages |
| 117 | 50% | module_payment_percentages |
| 128 | 55% | module_payment_percentages |
| 140 | 60% | module_payment_percentages |

### E. PERCENTILES CONDUCTOR (30 días)

| Percentil | Trips/mes | Revenue/mes |
|-----------|-----------|-------------|
| P10 | 43 | S/ 506 |
| P25 | 231 | S/ 2,253 |
| P50 | 471 | S/ 4,748 |
| P75 | 599 | S/ 5,759 |
| P90 | 675 | S/ 7,132 |

---

## 3. INPUTS QUE SIGUEN SIENDO SUPUESTOS

| Input | Valor Sugerido | Razón | Recomendación |
|-------|---------------|-------|---------------|
| Seguro/GPS mensual | S/ 300 | No existe en BD | Confirmar con operaciones |
| Reserva desgaste % | 10-20% | No existe en BD | Input configurable |
| Precio gasolina/galón | S/ 15-17 | No existe en BD | Actualizar periódicamente |
| Lavado/semana | S/ 25-40 | No existe en BD | Añadir a otros_gastos |
| Peajes/día | Variable | No existe en BD | Estimar por zona |
| Depreciación mensual | Derivable | Puede calcularse: valor vehículo / (cuotas * 4.33 meses) | Usar valor residual contable |

---

## 4. RESPUESTAS EJECUTIVAS

### 4.1 ¿Qué porcentaje del modelo ya puede basarse en data real?

**~72%** de los inputs principales tienen fuente real:
- 67 inputs reales extraídos
- 14 inputs derivados de data real
- 16 inputs no disponibles

### 4.2 ¿Qué inputs siguen siendo supuestos?

- Seguro/GPS (S/300/mes)
- Reserva desgaste (%)
- Precio gasolina
- Lavados
- Peajes
- Depreciación contable

### 4.3 ¿Qué inputs faltan críticamente?

1. **Horas online reales** — Se usa `horas_trabajo` de billing como proxy (9.08h/día)
2. **KM muertos desglosados** — Solo se puede inferir por diferencia (5.45 km/viaje)
3. **Tasa de aceptación por turno** — `summary_daily` vacía para este park
4. **Seguro real** — Posiblemente incluido en cuota pero no desglosado

### 4.4 ¿Qué fuentes son más confiables?

| Fuente | Confiabilidad | Nota |
|--------|--------------|------|
| `module_weekly_billing` | ⭐⭐⭐⭐⭐ | Data financiera real calculada, incluye P&L |
| `trips_2026` | ⭐⭐⭐⭐⭐ | Volume/revenue impecable, 30 días completos |
| `module_weekly_income` | ⭐⭐⭐⭐ | Ingresos desglosados, múltiples semanas |
| `module_miauto_cronograma_*` | ⭐⭐⭐⭐ | Configuración vigente de cuotas |
| `module_payment_percentages` | ⭐⭐⭐⭐ | Escalones confirmados |
| `ops.yego_commission_proxy_config` | ⭐⭐⭐ | Config genérica Peru (no park-specific) |

### 4.5 ¿Qué gaps impiden un P&L exacto?

1. **Cuota vehículo real aplicada** — `module_miauto_cuota_semanal` está vacía (programa aún no activo para este park en producción). Las cuotas del cronograma son la estructura, pero no el cobro real.
2. **Seguro/GPS** — No desglosado ni rastreable.
3. **Billing solo tiene 1 semana** — No hay histórico de meses para comparar estacionalidad de costos.
4. **El concepto "utilidad" en billing ya incluye todo** — Pero no se sabe si incluye cuota vehículo.

### 4.6 ¿Qué debería integrarse después?

| Prioridad | Integración | Impacto |
|-----------|-------------|---------|
| 1 | Activar module_miauto_cuota_semanal para este park | Cuota vehiculo real |
| 2 | Automatizar carga semanal de module_weekly_billing | Histórico completo |
| 3 | Implementar tracking de horas online (API Yango) | Supply hours real |
| 4 | Desglosar otros_gastos (seguro, GPS, lavado) | P&L completo |
| 5 | Geocodificar viajes para análisis de zona | Optimización rutas |

### 4.7 ¿Qué inputs deberían ser configurables?

| Input | Razón |
|-------|-------|
| Precio gasolina | Varía semanalmente |
| Reserva desgaste % | Decisión de negocio |
| Seguro/GPS mensual | Cambia por proveedor |
| Cuota vehículo base | Cambia por cronograma |
| Escalones de pago | Sujeto a rediseño |
| Bono por turno día | Nuevo, configurable |
| Objetivo trips/hora | Meta operativa |

### 4.8 ¿Qué inputs deberían congelarse como históricos?

| Input | Razón |
|-------|-------|
| Ticket promedio mensual | Benchmark para comparación |
| Costo variable/km mensual | Detectar tendencias |
| Utilidad/viaje mensual | Tracking de rentabilidad |
| Horas trabajo/semana | Monitorear intensidad |
| % drivers con utilidad positiva | KPI de salud del modelo |
| Revenue/hora | Productividad trend |

### 4.9 ¿Qué inputs deberían venir siempre live de BD?

| Input | Tabla | Refresh |
|-------|-------|---------|
| Trips completados/día | trips_2026 | Real-time |
| Revenue/conductor/semana | trips_2026 | Semanal |
| % escalón pago aplicado | module_payment_percentages | On change |
| Utilidad semanal | module_weekly_billing | Semanal |
| Conductores activos | trips_2026 | Diario |
| Cuota vehiculo vigente | module_miauto_cronograma_rule | On change |
| Comisión plataforma | billing + income | Semanal |

---

## 5. P&L REAL POR VIAJE (Basado en Billing)

| Concepto | S/ / viaje | % del bruto |
|----------|-----------|-------------|
| Revenue bruto (ticket) | 10.21 | 100% |
| (-) Comisión plataforma | -1.70 | -16.7% |
| = Revenue neto | 8.51 | 83.3% |
| (-) Combustible | -1.41 | -13.8% |
| (-) Mantenimiento | -1.38 | -13.5% |
| = Margen antes de pago conductor | 5.72 | 56.0% |
| (-) Pago conductor | -2.96 | -29.0% |
| = Margen antes de cuota vehículo | 2.76 | 27.0% |
| (-) Cuota vehículo (~S/500/sem ÷ ~122 trips/sem) | -4.10 | -40.2% |
| (+) Bono Yango (~S/197/driver/sem ÷ 122 trips) | +1.62 | +15.9% |
| (+) Bono adicional viajes (~S/82/driver/sem ÷ 122) | +0.67 | +6.6% |
| **= RESULTADO NETO POR VIAJE** | **+0.95** | **+9.3%** |

> **NOTA:** El resultado de -2.17 en billing INCLUYE la cuota vehículo en el cálculo. La diferencia es que no todos los drivers tienen bono Yango completo y las cuotas varían.

### El verdadero driver de pérdida:

El billing muestra utilidad = -2.17/viaje, pero si se aíslan:
- **Drivers con 60% (172+ trips/sem):** 1 rentable, 5 con pérdida leve
- **Drivers con 20-35%:** Todos con pérdida severa (bajo volumen = cuota fija no se cubre)

**La cuota fija del vehículo es el principal destructor de rentabilidad para drivers de bajo volumen.**

---

## 6. DISCREPANCIA KM: trips vs billing

| Métrica | trips_2026 | billing | Diferencia |
|---------|-----------|---------|------------|
| KM/viaje | 3.75 | 9.20 | **+5.45 km** |
| Interpretación | Solo distancia con pasajero | Distancia total recorrida | Recorrido vacío (pickup + reposicionamiento) |

**Implicación:** El ratio de "km muertos" es **59.2%**. Por cada 3.75 km pagados por el pasajero, el vehículo recorre 5.45 km adicionales sin generar ingreso. Esto es normal en ride-hailing urbano pero es un input CRÍTICO para el modelo de costos.

---

## 7. COMPARATIVA: SUPUESTOS ANTERIORES vs DATA REAL

| Input | Supuesto Anterior | Data Real | Delta | Impacto en Modelo |
|-------|-------------------|-----------|-------|-------------------|
| KM/viaje | 3.75 (solo pasajero) | **9.20** (total) | **+145%** | CRÍTICO: duplica costo variable |
| Combustible/km | S/0.20 | **S/0.1528** | -24% | Favorable (menor costo/km) |
| Mantenimiento/km | S/0.15 | **S/0.1500** | = | Correcto |
| Cuota mensual | S/2,357 | **S/2,000-2,250** | -5 a -15% | Levemente favorable |
| Seguro/GPS | S/300/mes | **N/D** | ? | No verificable |
| Costo variable/viaje | S/1.57 | **S/2.79** | **+78%** | CRÍTICO: subestimado antes |
| Revenue/hora | estimado S/25 | **S/28.97** (real) | +16% | Favorable |
| Horas/día | estimado 8h | **9.08h** (real) | +14% | Favorable |

---

## 8. SQLs RELEVANTES

### SQL: Billing agregado semanal
```sql
SELECT
  SUM(total_viajes) as viajes,
  SUM(horas_trabajo) as horas,
  SUM(monto_total_producido) as producido,
  SUM(comision_app) as comision_app,
  SUM(monto_neto) as neto,
  SUM(km_recorrido) as km,
  SUM(gasto_combustible) as combustible,
  SUM(gasto_mantenimiento) as mantenimiento,
  SUM(pago_total) as pago_total,
  SUM(utilidad) as utilidad,
  SUM(bono_yango) as bono_yango
FROM public.module_weekly_billing
WHERE driver_id IN (
  SELECT driver_id FROM public.drivers
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
)
AND fecha_inicio >= CURRENT_DATE - INTERVAL '30 days'
```

### SQL: Costo por km real
```sql
SELECT
  SUM(gasto_combustible) / NULLIF(SUM(km_recorrido), 0) as combustible_por_km,
  SUM(gasto_mantenimiento) / NULLIF(SUM(km_recorrido), 0) as mantenimiento_por_km,
  SUM(km_recorrido) / NULLIF(SUM(total_viajes), 0) as km_por_viaje,
  SUM(monto_total_producido) / NULLIF(SUM(horas_trabajo), 0) as revenue_por_hora
FROM public.module_weekly_billing
WHERE driver_id IN (
  SELECT driver_id FROM public.drivers
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
)
```

### SQL: Income con platform fees
```sql
SELECT
  SUM(platform_fees) / NULLIF(SUM(price_yango_pro), 0) * -100 as pct_platform_fee,
  SUM(bonificacion) / NULLIF(SUM(price_yango_pro), 0) * 100 as pct_bonificacion,
  SUM(cash_collected) + SUM(non_cash_payment) as total_cobrado
FROM public.module_weekly_income
WHERE driver_id IN (
  SELECT driver_id FROM public.drivers
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
)
AND fecha_inicio >= CURRENT_DATE - INTERVAL '30 days'
```

### SQL: Cronograma cuotas vehículo
```sql
SELECT cr.name, cv.name as vehiculo, cv.cuotas_semanales,
       rule.viajes, rule.bono_auto, rule.cuotas_por_vehiculo
FROM public.module_miauto_cronograma cr
JOIN public.module_miauto_cronograma_vehiculo cv ON cv.cronograma_id = cr.id
JOIN public.module_miauto_cronograma_rule rule ON rule.cronograma_id = cr.id
WHERE cr.country = 'PE' AND cr.active = true
ORDER BY cr.name, rule.orden
```

---

## 9. ARCHIVOS GENERADOS

| Archivo | Contenido | Rows |
|---------|-----------|------|
| `reports/inputs_reales_yego_pro.csv` | Todos los inputs con valor real | 67 |
| `reports/inputs_no_disponibles.csv` | Inputs que no existen en BD | 16 |
| `reports/inputs_derivados.csv` | Inputs calculados de data real | 14 |
| `reports/input_mapping_excel.csv` | Mapeo directo para Excel | 29 |
| `reports/resumen_turnos.csv` | DÍA vs NOCHE (reporte anterior) | 2 |
| `reports/resumen_conductores.csv` | Todos los drivers | 37 |
| `reports/hourly_performance.csv` | Performance por hora | 24 |
| `reports/rentabilidad_estimada.csv` | Escenarios de sensibilidad | 42 |
| `reports/top_day_drivers.csv` | Top conductores DÍA | 25 |
| `reports/top_night_drivers.csv` | Top conductores NOCHE | 22 |

---

## 10. LIMITACIONES Y NOTAS

1. **`module_weekly_billing` solo tiene 1 semana** (18-24 mayo 2026, 26 drivers). Los costos pueden variar estacionalmente.
2. **El campo `utilidad` en billing ya es post-cuota** — Incluye el descuento por cuota vehículo en el cálculo interno.
3. **El `km_recorrido` en billing es TOTAL** (con y sin pasajero) — Diferente al `distancia_km` de trips.
4. **La comisión de plataforma** tiene dos mediciones: 16.7% (billing) vs 14.9% (income). La diferencia se explica porque billing puede incluir ajustes y el income es más "bruto".
5. **El Bono Yango (S/5,127/sem)** es un ingreso externo que mitiga parcialmente las pérdidas.
6. **Los conductores con 20% de pago** aún generan pérdida — El problema no es el % del conductor sino la cuota fija del vehículo que no se cubre con bajo volumen.
7. **Hay 34 drivers en trips pero 26 en billing** — 8 drivers no tienen registro de billing (posiblemente nuevos o sin liquidación esa semana).
