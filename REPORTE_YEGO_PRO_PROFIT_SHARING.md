# REPORTE OPERATIVO Y FINANCIERO — YEGO PRO (Park Lima)
## Análisis Últimos 30 Días | park_id: 64085dd85e124e2c808806f70d527ea8

**Fecha de generación:** 28 de mayo de 2026
**Período analizado:** 28 abril – 27 mayo 2026
**Park:** Lima, Perú | Partner: Yego | LOB: Autos Regular

---

## 1. EXECUTIVE SUMMARY

| Métrica | Valor |
|---------|-------|
| Trips completados | 13,951 |
| Trips cancelados | 13,647 (49.5% del total) |
| Conductores activos | 34 |
| Días con data | 30 |
| Revenue bruto total | S/ 142,474 |
| Ticket promedio | S/ 10.21 |
| Distancia promedio | 3.75 km |
| Duración promedio | 12.7 min |

### Hallazgo Principal

**El turno noche NO es intrínsecamente más rentable por hora que el día.** La brecha real está en:
1. **Velocidad de viaje** (noche: 10.8 min vs día: 15.5 min por trip → +44% más rápido)
2. **Trips por hora** (noche: 2.79 vs día: 2.30 trips/hora → +21%)
3. **Revenue/hora jornada** (noche: S/28.95 vs día: S/24.84 → +16.5%)

Paradoja: **El ticket es MAYOR de día** (S/10.67 vs S/9.91) pero la productividad horaria es MENOR por tráfico y tiempos muertos.

---

## 2. DATA SOURCES

| Fuente | Tabla | Uso |
|--------|-------|-----|
| **Trips** | `public.trips_2026` | Fuente primaria de viajes |
| **Drivers** | `public.drivers` | Maestro de conductores |
| **Parks** | `dim.dim_park` | Identificación del park |
| **Payment scheme** | `public.module_payment_percentages` | Escalones de pago vigentes |
| ~~Fleet Summary~~ | `public.module_ct_fleet_summary_daily` | **SIN DATA** para este park |
| ~~Connection Logs~~ | `public.connection_logs` | Solo usuarios staff, no drivers |
| ~~Supply MVs~~ | `ops.mv_supply_segments_weekly` | Disponible pero no usada (granularidad semanal insuficiente) |

---

## 3. CALIDAD Y CONFIABILIDAD

| Campo | Completitud | Nota |
|-------|-------------|------|
| fecha_inicio_viaje | 100% | Sin nulos |
| conductor_id | 100% | Sin nulos |
| fecha_finalizacion | 99.99% | Solo 2 nulos |
| distancia_km | 97.7% completados | Null en cancelados (esperado) |
| precio_yango_pro | 97.6% completados | Null en cancelados |
| efectivo | 84.2% completados | Parcial — trips tarjeta no tienen |
| tarjeta | 16.5% | Solo trips pagados con tarjeta |
| comision_servicio | 8.5% | Muy baja cobertura |
| comision_empresa_asociada | 0% | **Siempre NULL** |
| pagos_viajes_flota | 0% | **Siempre NULL o 0** |

**Limitación crítica:** No hay columna de supply hours (horas online) en la tabla de trips. La estimación de productividad/hora se calcula desde la duración del primer al último viaje del día (jornada estimada).

**Nota sobre distancia:** El campo `distancia_km` contiene valores en **metros** (avg ~3,754), no kilómetros. Se convierte a km en el análisis.

---

## 4. METODOLOGÍA

### Clasificación de Turnos
- **DÍA:** 06:00 – 17:59 (basado en `fecha_inicio_viaje`)
- **NOCHE:** 18:00 – 05:59

### Clasificación de Conductores
- **Predominante DÍA:** ≥70% de trips en horario diurno
- **Predominante NOCHE:** ≥70% de trips en horario nocturno
- **MIXTO:** Ninguno ≥70%

### Jornada Estimada
- Calculada como: `MAX(fecha_finalizacion) - MIN(fecha_inicio_viaje)` por conductor-día
- Filtrada: ≥3 trips/día, jornada entre 0.5h y 16h
- Revenue/hora = revenue / jornada estimada

### Revenue Bruto
- `precio_yango_pro` = total cobrado al pasajero (incluye todas las modalidades de pago)
- Composición: Efectivo (80.1%) + Tarjeta (16.5%) + Propinas (1.6%) + Bonificaciones (1.4%)

---

## 5. KPIs PRINCIPALES

### 5.1 Comparativa DÍA vs NOCHE

| KPI | DÍA | NOCHE | Δ% |
|-----|-----|-------|-----|
| Trips | 5,563 (40%) | 8,388 (60%) | -33% |
| Conductores | 31 | 32 | -3% |
| Ticket promedio | S/ 10.67 | S/ 9.91 | **+7.7%** |
| Ticket mediana | S/ 9.60 | S/ 8.70 | **+10.3%** |
| Revenue bruto | S/ 59,349 | S/ 83,125 | -29% |
| KM promedio | 3.89 km | 3.66 km | +6.3% |
| Duración promedio | 15.5 min | 10.8 min | **+44%** |
| Trips/hora viaje | 3.85 | 5.52 | **-30%** |
| Rev/hora viaje | S/ 41.09 | S/ 54.71 | **-25%** |
| Rev/hora jornada | S/ 24.84 | S/ 28.95 | **-14.2%** |
| Trips/hora jornada | 2.30 | 2.79 | -17.5% |
| Jornada mediana | 8.1 h | 3.4 h | **+138%** |
| Revenue mediana/jornada | S/ 153.30 | S/ 96.70 | **+58.5%** |
| Cancelaciones | 5,081 (47.7%) | 8,566 (50.5%) | -5% |

### 5.2 Insight Clave de Jornada

**El turno día tiene jornadas mucho más largas (8.1h vs 3.4h).** Esto significa:
- El conductor de día produce más en TOTAL por jornada (S/153 vs S/97)
- Pero genera menos por HORA (S/24.84 vs S/28.95)
- La diferencia de revenue/hora es solo **16.5%**, no el 40%+ que uno esperaría

### 5.3 Performance por Franja Horaria

| Franja | Trips | Drivers | Revenue | Ticket | KM | Min | Trips/Driver |
|--------|-------|---------|---------|--------|-----|-----|-------------|
| 02-06 (madrugada) | 2,605 | 22 | S/24,264 | S/9.35 | 3.9 | 12.1 | 118.4 |
| 06-10 (mañana) | 1,746 | 27 | S/19,439 | S/11.13 | 4.2 | 16.4 | 64.7 |
| 10-14 (media mañana) | 1,866 | 27 | S/19,151 | S/10.15 | 3.9 | 14.7 | 69.1 |
| 14-18 (tarde) | 1,921 | 25 | S/20,586 | S/10.51 | 3.6 | 15.3 | 76.8 |
| 18-22 (noche temprana) | 2,193 | 31 | S/23,366 | S/10.91 | 3.5 | 12.1 | 70.7 |
| 22-02 (noche core) | 3,556 | 26 | S/36,135 | S/10.14 | 3.6 | 9.7 | 136.8 |

**Franja más productiva por driver:** 22:00–02:00 (136.8 trips/driver en 30 días)
**Franja con mejor ticket:** 06:00–10:00 (S/11.13)
**Franja más rápida:** 22:00–02:00 (9.7 min/trip)

### 5.4 Performance por Día de Semana

| Día | Trips | Ticket | Revenue | Drivers |
|-----|-------|--------|---------|---------|
| Domingo | 1,859 | S/10.59 | S/19,684 | 23 |
| Lunes | 1,443 | S/10.34 | S/14,919 | 29 |
| Martes | 2,347 | S/9.80 | S/22,990 | 33 |
| Miércoles | 2,478 | S/9.74 | S/24,147 | 33 |
| Jueves | 1,971 | S/9.88 | S/19,475 | 30 |
| Viernes | 1,863 | S/10.25 | S/19,098 | 30 |
| Sábado | 1,990 | S/11.14 | S/22,161 | 29 |

**Días más productivos:** Martes y Miércoles (más trips, más drivers activos)
**Mejor ticket:** Sábado (S/11.14)
**Menor actividad:** Lunes

---

## 6. CONDUCTORES — DISTRIBUCIÓN Y PERCENTILES

### 6.1 Clasificación por Turno

| Turno Predominante | Conductores | Trips Totales | Avg Trips/Driver |
|-------------------|-------------|---------------|-----------------|
| DÍA | 11 (32%) | 3,395 | 309 |
| NOCHE | 17 (50%) | 6,970 | 410 |
| MIXTO | 6 (18%) | 3,586 | 598 |

### 6.2 Percentiles (30 días, 34 drivers)

| Percentil | Trips | Revenue |
|-----------|-------|---------|
| P10 | 43 | S/ 506 |
| P25 | 231 | S/ 2,253 |
| P50 (mediana) | 471 | S/ 4,748 |
| P75 | 599 | S/ 5,759 |
| P90 | 675 | S/ 7,132 |
| **Promedio** | **410** | **S/ 4,190** |
| **Std Dev** | **232** | **S/ 2,400** |

**Coef. variación:** 56% (trips), 57% (revenue) → Alta dispersión operativa

### 6.3 Consistencia Semanal

| Categoría | Conductores | Avg Trips/Sem | Avg Rev/Sem |
|-----------|-------------|---------------|-------------|
| CONSISTENTE (CV < 30%) | 9 | 127 | S/ 1,343 |
| MODERADO (CV 30-60%) | 15 | 111 | S/ 1,095 |
| INCONSISTENTE (CV > 60%) | 4 | 82 | S/ 865 |

### 6.4 Top Performers DÍA (con detalle productividad)

| Conductor | Días | Trips | Revenue | Jornada | Rev/h | Trips/h |
|-----------|------|-------|---------|---------|-------|---------|
| Jabali Baker Mahmoud | 26 | 632 | S/6,665 | 9.2h | S/27.9 | 2.7 |
| Pacco Monrroy Deivis P. | 28 | 632 | S/6,786 | 9.3h | S/26.2 | 2.5 |
| Sulca Pariona Johny | 20 | 460 | S/4,795 | 10.0h | S/24.3 | 2.3 |
| Durand Huamani Americo | 17 | 380 | S/3,764 | 8.1h | S/27.4 | 2.8 |

### 6.5 Top Performers NOCHE

| Conductor | Días | Trips | Revenue | Rev/Día |
|-----------|------|-------|---------|---------|
| Basto Parada Jose Richard | 29 | 573 | S/5,899 | S/203 |
| Palomino Gamboa Luis Adan | 22 | 573 | S/5,268 | S/239 |
| Choquehuanca Ppoccohuanca | 26 | 472 | S/4,850 | S/187 |
| Solorzano Contreras Freddy | 30 | 466 | S/4,524 | S/151 |

---

## 7. ESQUEMA DE PAGOS ACTUAL

### Escalones vigentes (desde 01-mayo-2024):

| Min Trips Validados (semanal) | % para Conductor |
|-------------------------------|-----------------|
| 90 | 30% |
| 95 | 35% |
| 100 | 40% |
| 107 | 45% |
| 117 | 50% |
| 128 | 55% |
| 140 | 60% |

---

## 8. RENTABILIDAD ESTIMADA

### 8.1 Supuestos del Modelo

> **NOTA:** Los costos siguientes son TEÓRICOS (no existen en BD). Se usan los supuestos proporcionados.

| Concepto | Valor | Fuente |
|----------|-------|--------|
| Ticket promedio real | S/ 10.21 | BD |
| KM por viaje real | 3.75 km | BD (campo en metros) |
| Combustible | S/ 0.20/km | Supuesto |
| Mantenimiento | S/ 0.15/km | Supuesto |
| Seguro/GPS mensual | S/ 300 | Supuesto |
| Cuota vehículo mensual | S/ 2,357 | Supuesto |
| Reserva desgaste | 20% sobre costos variables | Supuesto |

### 8.2 Costos Calculados por Viaje

| Concepto | Cálculo | Valor/viaje |
|----------|---------|-------------|
| Combustible | 3.75 km × S/0.20 | S/ 0.75 |
| Mantenimiento | 3.75 km × S/0.15 | S/ 0.56 |
| Reserva desgaste | (0.75+0.56) × 20% | S/ 0.26 |
| **Total costo variable/viaje** | | **S/ 1.57** |

### 8.3 Costos Fijos Mensuales por Vehículo

| Concepto | Valor |
|----------|-------|
| Cuota vehículo | S/ 2,357 |
| Seguro/GPS | S/ 300 |
| **Total fijos** | **S/ 2,657** |

### 8.4 Escenario por Vehículo (30 días, conductor promedio P50)

| Métrica | Valor |
|---------|-------|
| Trips/mes (P50) | 471 |
| Revenue bruto | S/ 4,748 |
| (-) Costo variable | S/ 740 (471 × S/1.57) |
| (-) Costo fijo | S/ 2,657 |
| **= Utilidad antes de pago conductor** | **S/ 1,351** |
| (-) Pago conductor (50%, ~117 trips/sem) | S/ 2,374 |
| **= Resultado neto empresa** | **S/ -1,023 (PÉRDIDA)** |

### 8.5 Escenario Top Performer (P75)

| Métrica | Valor |
|---------|-------|
| Trips/mes | 599 |
| Revenue bruto | S/ 5,759 |
| (-) Costo variable | S/ 940 |
| (-) Costo fijo | S/ 2,657 |
| **= Utilidad antes de pago conductor** | **S/ 2,162** |
| (-) Pago conductor (55%, ~128 trips/sem) | S/ 3,167 |
| **= Resultado neto empresa** | **S/ -1,005 (PÉRDIDA)** |

### 8.6 Escenario P90

| Métrica | Valor |
|---------|-------|
| Trips/mes | 675 |
| Revenue bruto | S/ 7,132 |
| (-) Costo variable | S/ 1,060 |
| (-) Costo fijo | S/ 2,657 |
| **= Utilidad antes de pago conductor** | **S/ 3,415** |
| (-) Pago conductor (60%, 140+ trips/sem) | S/ 4,279 |
| **= Resultado neto empresa** | **S/ -864 (PÉRDIDA)** |

### 8.7 PUNTO DE EQUILIBRIO

Para que la empresa no pierda (pago conductor 40%):

| Variable | Requerido |
|----------|-----------|
| Revenue mínimo mensual/vehículo | **S/ 5,662** |
| Trips mínimos mensuales | **~554** (a S/10.21/trip) |
| Trips mínimos semanales | **~139** |

Con el esquema actual (pago 60% a 140 trips/sem):
- Revenue necesario = **S/ 8,643/mes** (inalcanzable — solo 0-2 drivers lo logran)

### 8.8 Sensibilidad al % Conductor

| % Conductor | Revenue Break-even | Trips/sem requeridos |
|-------------|-------------------|---------------------|
| 30% | S/ 3,796 | 93 |
| 35% | S/ 4,088 | 100 |
| 40% | S/ 4,428 | 109 |
| 45% | S/ 4,831 | 119 |
| 50% | S/ 5,314 | 130 |
| 55% | S/ 5,904 | 145 |
| 60% | S/ 6,643 | 163 |

---

## 9. COMPARATIVA DÍA VS NOCHE — RESPUESTAS DIRECTAS

### 9.1 ¿Qué tan inferior es realmente el turno día?

**Solo 16.5% inferior en revenue/hora jornada.** La percepción de que "día es mucho peor" es exagerada. La brecha real:
- Rev/hora: S/24.84 (día) vs S/28.95 (noche) = -14.2%
- Trips/hora: 2.30 vs 2.79 = -17.5%

### 9.2 ¿Por qué es peor?

| Factor | Impacto | Evidencia |
|--------|---------|-----------|
| **Tráfico** | ALTO | Duración 15.5 min vs 10.8 min (+44%) |
| Menos ticket | INVERSO | Ticket DÍA es mayor (+7.7%) |
| Menos horas efectivas | NO | Jornadas DÍA son más largas (8.1h vs 3.4h) |
| Menos viajes/hora | MODERADO | 2.30 vs 2.79 (-17.5%) |
| Menos demanda | PARCIAL | 40% vs 60% de trips totales |

**CONCLUSIÓN: El problema es TRÁFICO, no demanda ni ticket.**

### 9.3 ¿Cuál es la brecha REAL?

- Por hora: S/4.11/hora menos (16.5%)
- Por jornada completa (8h): S/32.9 menos
- Por mes (25 jornadas): ~S/822 menos en revenue antes de costos

### 9.4 ¿Qué incentivo mínimo equilibraría?

Para compensar S/4.11/hora de diferencia al conductor (asumiendo 50% para él):
- **Bono mínimo sugerido: S/2.05/hora adicional en turno día**
- O equivalente: **+S/0.90 por viaje completado en horario 06-18**

### 9.5 ¿Qué perfiles producen bien de día?

Los top performers de día tienen estos patrones:
1. **Jornadas largas** (9-10 horas continuas)
2. **Alta constancia** (26-28 días/mes)
3. **Arranque temprano** (comenzando 6-7am)
4. **Ticket superior** (S/10.55-10.73 vs promedio S/10.21)
5. **No se dispersan a noche** (90%+ en horario diurno)

### 9.6 ¿Qué horario es más rentable?

- **MEJOR revenue/driver:** 22:00-02:00 (136.8 trips/driver/mes)
- **MEJOR ticket:** 06:00-10:00 (S/11.13 promedio)
- **MEJOR combinación:** 18:00-22:00 (buen ticket S/10.91 + 31 drivers activos)

### 9.7 ¿Dónde se destruye rentabilidad?

1. **Conductores P10-P25** (trips < 231/mes): Nunca cubren costos fijos
2. **Inconsistentes** (CV > 60%): Solo 82 trips/sem promedio
3. **Lunes** (menor actividad: 1,443 trips con 29 drivers)
4. **Franja 06-10 de día** (64.7 trips/driver vs 136.8 de noche) → tráfico pesado destruye productividad

---

## 10. PROPUESTAS DE MODELO DE COMPENSACIÓN

### Modelo A: Porcentaje Puro (actual mejorado)

| Trips/semana | % Actual | % Propuesto | Δ |
|--------------|----------|-------------|---|
| 90 | 30% | 30% | = |
| 95 | 35% | 33% | -2% |
| 100 | 40% | 36% | -4% |
| 107 | 45% | 40% | -5% |
| 117 | 50% | 44% | -6% |
| 128 | 55% | 48% | -7% |
| 140 | 60% | 52% | -8% |

**Impacto empresa:** Reduce pérdida ~S/800-1,000/vehículo/mes
**Impacto conductor:** Pierde 8-13% de ingreso en los escalones altos
**Riesgo:** Fuga de conductores top

### Modelo B: Fijo + Variable

| Componente | Valor |
|-----------|-------|
| Fijo semanal (garantía) | S/ 250 |
| Variable por trip completado | S/ 2.50 |
| Bono productividad (>130 trips/sem) | S/ 100 |

**Simulación conductor promedio (P50, 117 trips/sem):**
- Ingreso: S/250 + (117 × S/2.50) = S/542.50/semana = **S/2,170/mes**
- vs actual (50%): 117 × S/10.21 × 50% = S/597/sem = S/2,388/mes

**Impacto empresa (P50):**
- Revenue: S/4,748 - Costos S/3,397 - Pago conductor S/2,170 = **S/-819** (mejor que -S/1,023)

### Modelo C: Multiplicador por Turno Día

| Concepto | Valor |
|----------|-------|
| Base: igual al actual | |
| Multiplicador trips 06:00-12:00 | ×1.20 (cada trip día cuenta como 1.2) |
| Multiplicador trips 12:00-18:00 | ×1.10 |

**Efecto:** Un conductor que hace 100 trips en día (80 en 6-12, 20 en 12-18) =
80×1.2 + 20×1.1 = 96 + 22 = 118 trips virtuales → obtiene 50% en lugar de 40%

### Modelo D: Revenue/Hora con Garantía

| Componente | Valor |
|-----------|-------|
| Garantía mínima/hora conectado | S/ 8.00 |
| + 35% del revenue generado | |
| Cap máximo: 55% del revenue | |

**Simulación día (8h, S/24.84 rev/h = S/198.72/día):**
- Garantía: 8 × S/8 = S/64
- 35% revenue: S/198.72 × 35% = S/69.55
- Pago = MAX(S/64, S/69.55) = S/69.55 → 35% efectivo

**Simulación noche (3.4h, S/28.95 rev/h = S/98.43):**
- Garantía: 3.4 × S/8 = S/27.20
- 35% revenue: S/98.43 × 35% = S/34.45
- Pago = S/34.45 → 35% efectivo

### Modelo E: Escalonado por Revenue/Hora (Anti-Ocio)

| Revenue/hora generado | % para conductor |
|-----------------------|-----------------|
| < S/15/hora | 25% |
| S/15-20/hora | 35% |
| S/20-25/hora | 42% |
| S/25-30/hora | 48% |
| > S/30/hora | 55% |

**Incentiva productividad y penaliza tiempos muertos.**

### Modelo F: Esquema Híbrido (RECOMENDADO)

| Componente | Valor | Razón |
|-----------|-------|-------|
| Base fija semanal | S/ 200 | Seguridad mínima |
| Variable por trip | S/ 2.00 | Incentivo volume |
| Bono turno día (06-18) | +S/ 0.80/trip | Compensar brecha |
| Bono consistencia (≥6 días/sem) | S/ 80/semana | Reducir ausentismo |
| Bono productividad (>3 trips/hora) | +S/ 0.50/trip extra | Anti-ocio |
| Cap máximo | 52% del revenue | Protección empresa |

**Simulación conductor DÍA consistente (25 días, ~23 trips/día = 138/sem):**
- Base: S/200
- Variable: 138 × S/2.00 = S/276
- Bono día: 138 × S/0.80 = S/110.40
- Bono consistencia: S/80
- Total semanal: **S/666.40** = S/2,666/mes
- vs actual (55%): 138 × S/10.21 × 55% = **S/775/sem** = S/3,100/mes
- **Ahorro empresa: S/434/mes por driver**

**Simulación conductor NOCHE productivo (25 días, ~28 trips/día = 168/sem):**
- Base: S/200
- Variable: 168 × S/2.00 = S/336
- Bono día: S/0
- Bono consistencia: S/80
- Total semanal: **S/616** = S/2,464/mes
- vs actual (60%): 168 × S/10.21 × 60% = **S/1,029/sem** = S/4,116/mes
- **Ahorro empresa: S/1,652/mes pero RIESGO ALTO de fuga**

---

## 11. RIESGOS

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Fuga de top drivers noche si se reduce % | ALTA | CRÍTICO | Transición gradual, negociación individual |
| Baja cobertura día persiste | MEDIA | ALTO | Modelo F con bono día explícito |
| Gaming del sistema (conectar sin aceptar) | MEDIA | MEDIO | Modelo E (anti-ocio por rev/hora) |
| Conductores inconsistentes no mejoran | ALTA | MEDIO | Mínimo de días/semana obligatorio |
| Datos insuficientes de supply hours | ALTA | MEDIO | Implementar tracking de horas online |

---

## 12. RECOMENDACIONES ACCIONABLES

### Inmediatas (0-2 semanas)
1. **Implementar tracking de horas online** — Sin esto, no se puede medir productividad real
2. **Segmentar conductores**: Los 4 inconsistentes deben tener conversación o ser reemplazados
3. **Establecer mínimo operativo**: <90 trips/semana = sin derecho a porcentaje

### Corto plazo (2-4 semanas)
4. **Pilotear Modelo F** con 5-6 conductores voluntarios de día
5. **Reducir tope máximo**: De 60% a 52% para nuevos (abuelo para existentes por 60 días)
6. **Bono por cobertura lunes**: S/1.00 extra/trip los lunes (día con menor actividad)

### Medio plazo (1-3 meses)
7. **Migrar a modelo híbrido completo** una vez validado el piloto
8. **Implementar scoring conductor** basado en: consistencia + trips/hora + cancelaciones
9. **Indexar cuota vehículo al revenue**: Si revenue < S/4,000/mes → evaluar retirar vehículo

### Estructural
10. **Dato de supply hours es CRÍTICO** — Sin él, cualquier modelo basado en productividad/hora es estimación
11. **Considerar si 34 conductores es excesivo** para la demanda actual: 13,951 trips / 34 = 410 trips promedio; con 28 conductores activos podrían cubrirse ~498/cada uno

---

## 13. MÉTRICAS NO DISPONIBLES

| Métrica | Razón | Impacto |
|---------|-------|---------|
| Horas online/conectado | No existe tabla de sessions para drivers | CRÍTICO |
| Tasa de aceptación real | `module_ct_fleet_summary_daily` vacía para este park | ALTO |
| Costo combustible real | No registrado en BD | MEDIO |
| Costo mantenimiento real | No registrado en BD | MEDIO |
| KM muertos (sin pasajero) | Solo se registra KM del viaje | ALTO |
| Revenue neto post-comisión plataforma | comision_empresa_asociada siempre NULL | ALTO |
| Zonas/rutas por viaje | Solo dirección texto, no geocodificado | BAJO |

---

## 14. SQLs RELEVANTES

### SQL 1: Trips completados últimos 30 días
```sql
SELECT *
FROM public.trips_2026
WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
  AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
  AND condicion = 'Completado'
```

### SQL 2: Clasificación de turnos por conductor
```sql
WITH trips_hora AS (
  SELECT conductor_id,
    EXTRACT(HOUR FROM fecha_inicio_viaje) as hora,
    COUNT(*) as trips
  FROM public.trips_2026
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
    AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
    AND condicion = 'Completado'
  GROUP BY conductor_id, EXTRACT(HOUR FROM fecha_inicio_viaje)
),
driver_turno AS (
  SELECT conductor_id,
    SUM(CASE WHEN hora >= 6 AND hora < 18 THEN trips ELSE 0 END) as trips_dia,
    SUM(CASE WHEN hora >= 18 OR hora < 6 THEN trips ELSE 0 END) as trips_noche,
    SUM(trips) as trips_total
  FROM trips_hora
  GROUP BY conductor_id
)
SELECT *,
  CASE
    WHEN trips_dia::float / NULLIF(trips_total, 0) >= 0.7 THEN 'DIA'
    WHEN trips_noche::float / NULLIF(trips_total, 0) >= 0.7 THEN 'NOCHE'
    ELSE 'MIXTO'
  END as turno_predominante
FROM driver_turno
```

### SQL 3: Métricas por turno
```sql
SELECT
  CASE WHEN EXTRACT(HOUR FROM fecha_inicio_viaje) >= 6
            AND EXTRACT(HOUR FROM fecha_inicio_viaje) < 18 THEN 'DIA'
       ELSE 'NOCHE' END as turno,
  COUNT(*) as trips,
  COUNT(DISTINCT conductor_id) as conductores,
  AVG(precio_yango_pro) as ticket_promedio,
  SUM(precio_yango_pro) as revenue_bruto,
  AVG(distancia_km)/1000 as km_promedio,
  AVG(EXTRACT(EPOCH FROM (fecha_finalizacion - fecha_inicio_viaje))/60) as duracion_min,
  PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY precio_yango_pro) as ticket_mediana
FROM public.trips_2026
WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
  AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
  AND condicion = 'Completado'
GROUP BY 1
```

### SQL 4: Jornada estimada por conductor-día
```sql
WITH driver_day AS (
  SELECT conductor_id, DATE(fecha_inicio_viaje) as fecha,
    CASE WHEN EXTRACT(HOUR FROM fecha_inicio_viaje) >= 6
              AND EXTRACT(HOUR FROM fecha_inicio_viaje) < 18 THEN 'DIA'
         ELSE 'NOCHE' END as turno,
    COUNT(*) as trips,
    SUM(precio_yango_pro) as revenue,
    EXTRACT(EPOCH FROM (MAX(fecha_finalizacion) - MIN(fecha_inicio_viaje)))/3600 as jornada_horas
  FROM public.trips_2026
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
    AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
    AND condicion = 'Completado'
    AND fecha_finalizacion IS NOT NULL
    AND fecha_finalizacion > fecha_inicio_viaje
  GROUP BY 1, 2, 3
  HAVING COUNT(*) >= 3
)
SELECT turno,
  AVG(trips) as avg_trips_jornada,
  AVG(revenue) as avg_rev_jornada,
  AVG(jornada_horas) as avg_jornada_horas,
  AVG(revenue / NULLIF(jornada_horas, 0)) as rev_per_hora_jornada
FROM driver_day
WHERE jornada_horas > 0.5 AND jornada_horas < 16
GROUP BY turno
```

### SQL 5: Performance horaria
```sql
SELECT
  EXTRACT(HOUR FROM fecha_inicio_viaje) as hora,
  COUNT(*) as trips,
  COUNT(DISTINCT conductor_id) as conductores,
  AVG(precio_yango_pro) as ticket_promedio,
  SUM(precio_yango_pro) as revenue
FROM public.trips_2026
WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
  AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
  AND condicion = 'Completado'
GROUP BY 1
ORDER BY 1
```

### SQL 6: Percentiles por conductor
```sql
WITH driver_stats AS (
  SELECT conductor_id,
    COUNT(*) as trips,
    SUM(precio_yango_pro) as revenue,
    COUNT(DISTINCT DATE(fecha_inicio_viaje)) as dias_activos
  FROM public.trips_2026
  WHERE park_id = '64085dd85e124e2c808806f70d527ea8'
    AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days'
    AND condicion = 'Completado'
  GROUP BY conductor_id
)
SELECT
  PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY trips) as p10_trips,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY trips) as p25_trips,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY trips) as p50_trips,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY trips) as p75_trips,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY trips) as p90_trips,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY revenue) as p50_revenue,
  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY revenue) as p90_revenue
FROM driver_stats
```

---

## APÉNDICE: LIMITACIONES DEL ANÁLISIS

1. **Sin horas online reales** — La productividad/hora es estimada desde el span del primer al último viaje. No incluye tiempo ocioso antes/después ni entre viajes sin data.
2. **Costos son 100% supuestos** — No hay registro de combustible, mantenimiento ni costos reales en la BD.
3. **El campo `distancia_km` está en metros** — Se corrigió dividiendo por 1000.
4. **`comision_empresa_asociada` siempre NULL** — No se puede calcular el revenue neto real de la empresa desde la plataforma.
5. **`module_ct_fleet_summary_daily` vacía para este park** — Los drivers de este park no aparecen en la tabla de fleet summary.
6. **Solo 34 conductores** — Sample pequeño; conclusiones estadísticas deben interpretarse con cautela.
7. **No hay data de KM muertos** (deadhead) — Solo se conoce la distancia del viaje, no la recorrida sin pasajero.
8. **Timezone asumida: América/Lima (UTC-5)** — Las horas en BD parecen estar en hora local.
9. **Rate de cancelación alto (49.5%)** — Puede indicar problemas de asignación o cobertura que impactan productividad medida.
