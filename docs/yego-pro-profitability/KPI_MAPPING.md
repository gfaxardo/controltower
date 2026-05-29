# KPI MAPPING — Yego Pro Profitability Intelligence
## Park: Lima | park_id: `64085dd85e124e2c808806f70d527ea8`
## Fecha: 28 mayo 2026

---

## CLASIFICACIÓN

- **REAL**: Valor directo de BD, sin transformación significativa
- **DERIVADO**: Se calcula combinando 2+ campos de BD
- **SUPUESTO**: Requiere input configurable externo
- **NO DISPONIBLE**: No existe fuente actual

---

## 1. KPIs OPERATIVOS

| # | KPI | Clasificación | Fuente/Fórmula | Granularidad Mín | Confianza |
|---|-----|--------------|----------------|-----------------|-----------|
| 1 | Trips completados | REAL | `trips_2026 WHERE condicion='Completado'` | viaje | ⭐⭐⭐⭐⭐ |
| 2 | Trips cancelados | REAL | `trips_2026 WHERE condicion<>'Completado'` | viaje | ⭐⭐⭐⭐⭐ |
| 3 | Revenue bruto | REAL | `SUM(precio_yango_pro)` de trips completados | viaje | ⭐⭐⭐⭐⭐ |
| 4 | Ticket promedio | DERIVADO | `AVG(precio_yango_pro)` completados | día | ⭐⭐⭐⭐⭐ |
| 5 | KM total (con pasajero) | REAL | `SUM(distancia_km)/1000` (**campo en metros**) | viaje | ⭐⭐⭐⭐ |
| 6 | KM total (real incl. vacío) | REAL | `SUM(km_recorrido)` de billing | semana | ⭐⭐⭐⭐⭐ |
| 7 | KM promedio por viaje (pasajero) | DERIVADO | `AVG(distancia_km)/1000` | día | ⭐⭐⭐⭐ |
| 8 | KM promedio por viaje (total) | DERIVADO | `SUM(km_recorrido)/SUM(total_viajes)` billing | semana | ⭐⭐⭐⭐⭐ |
| 9 | KM vacío por viaje | DERIVADO | `km_billing(9.20) - km_trips(3.75)` = 5.45 km | semana | ⭐⭐⭐ |
| 10 | Conductores activos | REAL | `COUNT(DISTINCT conductor_id)` trips completados | día | ⭐⭐⭐⭐⭐ |
| 11 | Vehículos activos | NO DISPONIBLE | Sin tabla de asignación vehículo→conductor | — | — |
| 12 | Supply hours (horas online) | NO DISPONIBLE | `module_ct_fleet_summary_daily` vacía para park | — | — |
| 13 | Horas trabajo (proxy supply) | REAL | `SUM(horas_trabajo)` de billing | semana | ⭐⭐⭐⭐ |
| 14 | Revenue/hora | DERIVADO | `SUM(monto_total_producido)/SUM(horas_trabajo)` billing | semana | ⭐⭐⭐⭐ |
| 15 | Trips/hora | DERIVADO | `SUM(total_viajes)/SUM(horas_trabajo)` billing | semana | ⭐⭐⭐⭐ |
| 16 | Revenue/km | DERIVADO | `SUM(precio_yango_pro)/SUM(distancia_km/1000)` trips | día | ⭐⭐⭐⭐ |
| 17 | Tasa de cancelación | DERIVADO | `cancelados / (completados + cancelados)` | día | ⭐⭐⭐⭐⭐ |
| 18 | Duración promedio viaje | DERIVADO | `AVG(fecha_finalizacion - fecha_inicio_viaje)` | viaje | ⭐⭐⭐⭐ |

---

## 2. KPIs FINANCIEROS

| # | KPI | Clasificación | Fuente/Fórmula | Granularidad Mín | Confianza |
|---|-----|--------------|----------------|-----------------|-----------|
| 19 | Combustible real (S/) | REAL | `SUM(gasto_combustible)` billing | semana | ⭐⭐⭐⭐⭐ |
| 20 | Combustible/km | DERIVADO | `gasto_combustible / km_recorrido` billing | semana | ⭐⭐⭐⭐⭐ |
| 21 | Combustible/viaje | DERIVADO | `gasto_combustible / total_viajes` billing | semana | ⭐⭐⭐⭐⭐ |
| 22 | Mantenimiento real (S/) | REAL | `SUM(gasto_mantenimiento)` billing | semana | ⭐⭐⭐⭐⭐ |
| 23 | Mantenimiento/km | DERIVADO | `gasto_mantenimiento / km_recorrido` billing | semana | ⭐⭐⭐⭐⭐ |
| 24 | Mantenimiento/viaje | DERIVADO | `gasto_mantenimiento / total_viajes` billing | semana | ⭐⭐⭐⭐⭐ |
| 25 | Pago conductor (S/) | REAL | `SUM(pago_total)` billing | semana | ⭐⭐⭐⭐⭐ |
| 26 | % pago conductor real | REAL | `AVG(porcentaje_pago)` billing | conductor-semana | ⭐⭐⭐⭐⭐ |
| 27 | Comisión plataforma (S/) | REAL | `SUM(comision_app)` billing | semana | ⭐⭐⭐⭐⭐ |
| 28 | Comisión plataforma (%) | DERIVADO | `comision_app / monto_total_producido` | semana | ⭐⭐⭐⭐⭐ |
| 29 | Comisión Yego (%) | REAL | `ops.yego_commission_proxy_config` (3%) | config | ⭐⭐⭐ |
| 30 | Costo fijo vehículo (cuota/sem) | REAL | `module_miauto_cronograma_rule.cuotas_por_vehiculo` | config | ⭐⭐⭐⭐ |
| 31 | Seguro/GPS mensual | SUPUESTO | No existe en BD — input configurable | config | ⭐ |
| 32 | Cuota mensual equivalente | DERIVADO | `cuota_semanal × 4.33` | mes | ⭐⭐⭐⭐ |
| 33 | Bono Yango (incentivo plataforma) | REAL | `SUM(bono_yango)` billing | semana | ⭐⭐⭐⭐⭐ |
| 34 | Bono adicional viajes | REAL | `SUM(bono_adic_viajes)` billing | semana | ⭐⭐⭐⭐⭐ |
| 35 | Bono reducción cuota (por trips) | REAL | `module_miauto_cronograma_rule.bono_auto` | config | ⭐⭐⭐⭐ |
| 36 | Utilidad operativa (por viaje) | REAL | `utilidad / total_viajes` billing | conductor-semana | ⭐⭐⭐⭐⭐ |
| 37 | Utilidad operativa (semanal flota) | REAL | `SUM(utilidad)` billing | semana | ⭐⭐⭐⭐⭐ |
| 38 | Utilidad neta (post cuota) | DERIVADO | `utilidad - cuota_vehiculo` (billing ya incluye) | semana | ⭐⭐⭐⭐ |
| 39 | Margen bruto/viaje | DERIVADO | `ticket - costo_variable` | semana | ⭐⭐⭐⭐ |
| 40 | Margen neto/viaje | REAL | `utilidad / total_viajes` billing | semana | ⭐⭐⭐⭐⭐ |
| 41 | Pérdida semanal | REAL | `SUM(utilidad) WHERE utilidad < 0` | semana | ⭐⭐⭐⭐⭐ |
| 42 | Break-even trips/semana | DERIVADO | Observado: 172+ trips/sem (solo 1 driver rentable) | semana | ⭐⭐⭐⭐ |
| 43 | % drivers con utilidad positiva | DERIVADO | `drivers con utilidad > 0 / total drivers` | semana | ⭐⭐⭐⭐⭐ |

---

## 3. KPIs DE SEGMENTACIÓN

| # | KPI | Clasificación | Fuente/Fórmula | Segmento |
|---|-----|--------------|----------------|----------|
| 44 | Revenue DÍA (06:00–17:59) | DERIVADO | trips filtrado por EXTRACT(HOUR) | turno |
| 45 | Revenue NOCHE (18:00–05:59) | DERIVADO | trips filtrado por EXTRACT(HOUR) | turno |
| 46 | Trips/hora DÍA | DERIVADO | trips día / jornada estimada día | turno |
| 47 | Trips/hora NOCHE | DERIVADO | trips noche / jornada estimada noche | turno |
| 48 | Revenue/hora DÍA | DERIVADO | revenue día / jornada estimada | turno |
| 49 | Revenue/hora NOCHE | DERIVADO | revenue noche / jornada estimada | turno |
| 50 | Ticket promedio DÍA | DERIVADO | AVG(precio_yango_pro) horario día | turno |
| 51 | Ticket promedio NOCHE | DERIVADO | AVG(precio_yango_pro) horario noche | turno |
| 52 | Trips por conductor | DERIVADO | COUNT(*) GROUP BY conductor_id | conductor |
| 53 | Revenue por conductor | DERIVADO | SUM(precio_yango_pro) GROUP BY conductor_id | conductor |
| 54 | Utilidad por conductor | REAL | `utilidad` de billing por driver_id | conductor |
| 55 | % pago por conductor | REAL | `porcentaje_pago` de billing | conductor |
| 56 | Horas por conductor | REAL | `horas_trabajo` de billing | conductor |
| 57 | Trips por semana | DERIVADO | COUNT(*) por iso_week | semana |
| 58 | Revenue por día semana | DERIVADO | SUM GROUP BY DOW | día |
| 59 | Trips por hora del día | DERIVADO | COUNT GROUP BY EXTRACT(HOUR) | hora |
| 60 | Revenue por franja horaria | DERIVADO | SUM GROUP BY franja 4h | franja |

---

## 4. RESUMEN DE DISPONIBILIDAD

| Categoría | Total KPIs | REAL | DERIVADO | SUPUESTO | NO DISPONIBLE |
|-----------|-----------|------|----------|----------|---------------|
| Operativos | 18 | 7 | 9 | 0 | 2 |
| Financieros | 25 | 13 | 10 | 1 | 1 |
| Segmentación | 17 | 4 | 13 | 0 | 0 |
| **TOTAL** | **60** | **24 (40%)** | **32 (53%)** | **1 (2%)** | **3 (5%)** |

---

## 5. KPIs NO DISPONIBLES — DETALLE

| KPI | Razón | Alternativa | Prioridad de Solución |
|-----|-------|-------------|----------------------|
| Vehículos activos | Sin asignación vehículo→conductor en BD | Derivar de cronograma (16 vehículos configurados) | MEDIA |
| Supply hours (online) | fleet_summary_daily vacía para park | Proxy: horas_trabajo de billing | ALTA |
| Seguro/GPS real | No existe tabla | Input configurable (S/300/mes sugerido) | BAJA |

---

## 6. VALORES DE REFERENCIA (BENCHMARK — Últimos 30 Días)

| KPI | Valor Actual | Unidad |
|-----|-------------|--------|
| Trips completados/30d | 13,951 | trips |
| Revenue bruto/30d | S/ 142,474 | S/ |
| Ticket promedio | S/ 10.21 | S/ |
| KM/viaje (pasajero) | 3.75 | km |
| KM/viaje (total real) | 9.20 | km |
| Conductores activos | 34 | drivers |
| Horas trabajo/sem promedio | 52.36 | horas |
| Revenue/hora | S/ 28.97 | S/h |
| Trips/hora | 2.32 | trips/h |
| Combustible/km | S/ 0.1528 | S/km |
| Mantenimiento/km | S/ 0.1500 | S/km |
| Comisión plataforma | 16.66% | % |
| Pago conductor (avg) | 47.69% | % |
| Utilidad/viaje | -S/ 2.17 | S/ |
| Utilidad semanal flota | -S/ 5,510 | S/ |
| Break-even trips/sem | 172+ | trips |
| % drivers rentables | 3.8% | % |

---

## 7. FÓRMULAS CLAVE

### Utilidad Operativa por Conductor-Semana
```
utilidad = monto_neto - gasto_combustible - gasto_mantenimiento - pago_total - cuota_vehiculo + bono_yango + bono_adic_viajes
```

### Margen por Viaje
```
margen_viaje = ticket_promedio - comision_plataforma - combustible/viaje - mantenimiento/viaje - pago_conductor/viaje - cuota/viaje + bonos/viaje
```

### Revenue/Hora
```
rev_hora = monto_total_producido / horas_trabajo  (billing)
```
O estimado:
```
rev_hora_estimada = revenue_jornada / (MAX(fin) - MIN(inicio))  (trips)
```

### Break-even Semanal
```
break_even_trips = costos_fijos_semanales / (ticket * (1 - pct_conductor) - costo_variable_viaje)
```

### Waterfall P&L por Viaje
```
Revenue bruto (ticket):                    S/ 10.21 (100%)
(-) Comisión plataforma:                   -S/  1.70 (-16.7%)
= Revenue neto:                             S/  8.51 (83.3%)
(-) Combustible:                           -S/  1.41 (-13.8%)
(-) Mantenimiento:                         -S/  1.38 (-13.5%)
= Margen antes de pago conductor:           S/  5.72 (56.0%)
(-) Pago conductor:                        -S/  2.96 (-29.0%)
= Margen antes de cuota vehículo:           S/  2.76 (27.0%)
(-) Cuota vehículo:                        -S/  4.10 (-40.2%)
(+) Bono Yango:                            +S/  1.62 (+15.9%)
(+) Bono adicional:                        +S/  0.67 (+6.6%)
= RESULTADO NETO POR VIAJE:                S/  0.95 (+9.3%)
```
> NOTA: El billing muestra -S/2.17 porque no todos los drivers reciben bonos completos.
