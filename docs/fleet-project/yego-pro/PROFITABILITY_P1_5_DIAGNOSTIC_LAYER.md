# Profitability P1.5 — Diagnostic Layer

## Objetivo

Agregar una capa diagnostica deterministica a Profitability que explique **por que** se gana o pierde dinero por conductor, vehiculo, turno y portafolio.

**NO es IA. NO genera recomendaciones. NO ejecuta acciones. NO cambia pagos reales. NO persiste escenarios.**

## Modelo Diagnostico

Cada diagnostico devuelve:

| Campo | Tipo | Descripcion |
|---|---|---|
| entity_type | string | driver / vehicle / shift / portfolio |
| entity_id | string | ID de la entidad |
| status | enum | PROFITABLE / RISKY / LOSS / UNKNOWN |
| main_driver | string | Causa principal detectada |
| secondary_drivers | list | Causas secundarias |
| impact_amount | float | Impacto economico estimado (S/) |
| severity | enum | HIGH / MEDIUM / LOW |
| confidence | enum | REAL / ESTIMATED / LEGACY |
| explanation | string | Explicacion en texto |
| evidence | object | Datos de soporte |

## Endpoints

### GET /fleet-project/yego-pro/profitability/diagnostics/drivers

Diagnostica por conductor usando billing semanal + shifts + closes.

**KPIs por conductor:**
- revenue, trips, km, ticket_avg
- estimated_cost, estimated_payout, estimated_margin
- revenue_per_trip, cost_per_trip, margin_per_trip

**Causas deterministas:**
- LOW_TRIPS: viajes < 50% del promedio o < 10 absolutos
- LOW_TICKET: ticket < 80% del promedio del parque
- HIGH_KM_PER_TRIP: km/viaje > 130% del promedio
- HIGH_COST_PER_TRIP: costo/viaje > 85% del revenue/viaje
- HIGH_PAYOUT_RATIO: payout % > 50%
- LOW_MARGIN: margen % < 5%
- MISSING_CLOSE: sin cierres diarios registrados
- MISSING_PLATE: sin placa asignada

**Clasificacion:**
- Rentable: profit > 0, sin causas
- Recuperable: profit < 0, pocas causas
- Critico: profit < -50 o 3+ causas con perdida
- No evaluable: sin datos suficientes

### GET /fleet-project/yego-pro/profitability/diagnostics/vehicles

Diagnostica por vehiculo (placa) usando shifts agrupados.

**KPIs por vehiculo:**
- revenue, trips, active_days, revenue_per_day, trips_per_day
- estimated_margin (usando margin % del parque como proxy)
- utilization_proxy, drivers_count, missing_plate_flag

**Causas:**
- LOW_UTILIZATION: < 3 dias activos / 7
- LOW_REVENUE_PER_DAY: < S/ 50/dia
- LOW_TRIPS_PER_DAY: < 5 viajes/dia
- MANY_DRIVERS_LOW_CONTROL: > 3 conductores distintos
- NEGATIVE_MARGIN: margen estimado < 0
- FIXED_COST_NOT_COVERED: revenue < S/ 350 (cuota semanal estimada)

**Clasificacion:**
- Rentable, Recuperable, Critico, Sin trazabilidad suficiente

### GET /fleet-project/yego-pro/profitability/diagnostics/shifts

Diagnostica dia vs noche.

**KPIs por turno:**
- revenue, trips, ticket_avg, margin, revenue_per_trip
- trips_per_day, estimated_margin, gap_day_vs_night_pct

**Responde:**
- Es dia realmente peor que noche?
- Diferencia: leve (<10%), moderada (10-30%), fuerte (>30%)
- Incentivo necesario para igualar
- Payout maximo que soporta dia
- Payout maximo que soporta noche

### GET /fleet-project/yego-pro/profitability/diagnostics/portfolio

Agregacion a nivel portafolio.

**Responde:**
- Utilidad total estimada (drivers y vehiculos)
- % drivers en perdida, % vehiculos en perdida
- Top 5 perdidas, Top 5 ganancias
- Concentracion de perdida (top 3)
- Impacto hipotetico de retirar bottom 5 vehiculos
- Impacto hipotetico de retirar bottom 5 conductores
- Root causes agregados con conteo, impacto y severidad

## Reglas Deterministicas

Todas las clasificaciones usan umbrales fijos definidos en `DIAG_DRIVER_THRESHOLDS` y `DIAG_VEHICLE_THRESHOLDS`. No hay modelo estadistico, ML ni IA.

Los umbrales se comparan contra promedios calculados del mismo parque en el mismo periodo. Son relativos al contexto operativo actual.

## KPIs Usados

| KPI | Fuente | Tipo |
|---|---|---|
| revenue | module_weekly_billing / module_calculated_shifts | REAL |
| trips | module_weekly_billing / module_calculated_shifts | REAL |
| km | module_weekly_billing | REAL |
| fuel_cost | module_weekly_billing | REAL |
| maintenance_cost | module_weekly_billing | REAL |
| driver_payment | module_weekly_billing | REAL |
| profit | module_weekly_billing | REAL |
| margin_pct | module_weekly_billing (derivado) | DERIVED |
| close_days | module_driver_closes | REAL |
| plate_coverage | module_calculated_shifts | REAL |
| vehicle_margin | Estimado (margin % parque x revenue placa) | ESTIMATED |

## Limitaciones

1. **Margen por vehiculo es ESTIMADO**: no hay asignacion vehiculo-conductor completa. Se usa el margen % del parque aplicado al revenue por placa.
2. **Cobertura de placa parcial**: ~55% de shifts tienen placa. Vehiculos sin placa no aparecen.
3. **Cobertura de cierres parcial**: ~36% de drivers tienen cierres. Drivers sin cierre se marcan como ESTIMATED.
4. **Costo fijo vehicular es un default** (S/ 350/semana). No se obtiene de la BD.
5. **Solo 1 semana de billing disponible**. Los diagnosticos reflejan esa semana, no tendencias.
6. **No hay persistencia**. Los diagnosticos se calculan en tiempo real en cada request.

## Que NO hace

- NO usa IA ni modelos predictivos
- NO genera recomendaciones automaticas
- NO ejecuta acciones
- NO cambia pagos reales
- NO persiste escenarios
- NO toca otros modulos (Drivers, Yango Loyalty, Omniview, WorkOS)
- NO crea migraciones ni vistas SQL nuevas

## Frontend

Tab "Diagnostics" con subtabs:
1. **Portfolio**: resumen ejecutivo, top 5 perdidas/ganancias, concentracion, impacto hipotetico
2. **Drivers**: tabla con estado, clasificacion, causa, severidad, confianza, KPIs + explicaciones
3. **Vehicles**: tabla con estado, clasificacion, margen estimado, causa, severidad + explicaciones
4. **Shifts**: comparacion dia/noche con KPIs, brecha, incentivo, payout maximo
5. **Root Causes**: tabla agregada de causas con conteo, impacto e intensidad

## Archivos Modificados

| Archivo | Cambio |
|---|---|
| backend/app/services/yego_pro_profitability_service.py | +4 funciones diagnosticas |
| backend/app/routers/yego_pro_profitability.py | +4 endpoints GET |
| frontend/src/services/api.js | +4 funciones API |
| frontend/src/components/YegoProProfitabilityPage.jsx | +Tab Diagnostics con 5 subtabs |

## GO/NO-GO para P1.6

**GO si:**
- Diagnostics carga correctamente en todos los subtabs
- No hay NaN, undefined, loading infinito
- Simulator, Waterfall, Data Quality siguen funcionando
- Los endpoints diagnostics responden < 20s
- El modelo diagnostico clasifica correctamente casos conocidos

**NO-GO si:**
- Diagnostics no carga o muestra errores persistentes
- Afecta tabs existentes
- Los endpoints tardan > 30s consistentemente
- Los clasificadores producen resultados contradictores con la realidad conocida
