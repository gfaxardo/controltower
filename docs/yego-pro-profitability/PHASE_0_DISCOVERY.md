# PHASE 0 — DISCOVERY REPORT
## Yego Pro Profitability Intelligence
### Park: Lima, Perú | park_id: `64085dd85e124e2c808806f70d527ea8`
### Fecha: 28 mayo 2026

---

## 1. RESUMEN EJECUTIVO

El discovery confirma que **72% de los inputs financieros** ya tienen fuente real en base de datos.
La fuente más valiosa es `public.module_weekly_billing`, que contiene costos reales de combustible,
mantenimiento, horas trabajadas, pagos a conductores y utilidad/pérdida por viaje.

**GO / NO-GO para Fase 1 Backend: GO CONDICIONAL**

Condiciones:
1. Asegurar carga semanal automatizada de `module_weekly_billing` (actualmente solo 1 semana disponible)
2. Aceptar que ~28% de inputs serán configurables (supuestos)
3. El módulo operará inicialmente solo para park Lima (64085dd8...)

---

## 2. INVENTARIO DE FUENTES DE DATOS

### 2.1 Fuentes CONFIRMADAS con Data Real

| # | Tabla | Schema | Granularidad | Periodo Disponible | Freshness | Join Key | Confiabilidad |
|---|-------|--------|--------------|-------------------|-----------|----------|---------------|
| 1 | `trips_2026` | public | viaje individual | Ene 2026 – presente | Real-time (ingesta Yango) | park_id, conductor_id | ⭐⭐⭐⭐⭐ |
| 2 | `trips_2025` | public | viaje individual | Todo 2025 | Histórico cerrado | park_id, conductor_id | ⭐⭐⭐⭐⭐ |
| 3 | `module_weekly_billing` | public | conductor-semana | 1 semana (18-24 may 2026) | Semanal manual | driver_id | ⭐⭐⭐⭐⭐ |
| 4 | `module_weekly_income` | public | conductor-semana | ~8 semanas | Semanal | driver_id | ⭐⭐⭐⭐ |
| 5 | `drivers` | public | maestro (vigente) | Actual | On-change | driver_id, park_id | ⭐⭐⭐⭐⭐ |
| 6 | `module_payment_percentages` | public | config vigente | Desde may 2024 | On-change | park-level | ⭐⭐⭐⭐ |
| 7 | `module_miauto_cronograma` | public | config | Vigente | On-change | country, cronograma_id | ⭐⭐⭐⭐ |
| 8 | `module_miauto_cronograma_vehiculo` | public | vehículo | Vigente | On-change | cronograma_id | ⭐⭐⭐⭐ |
| 9 | `module_miauto_cronograma_rule` | public | regla bonos/cuotas | Vigente | On-change | cronograma_id | ⭐⭐⭐⭐ |
| 10 | `dim_park` | dim | dimensión park | Siempre | Estática | park_id | ⭐⭐⭐⭐⭐ |
| 11 | `v_geo_park` | dim | vista geo parks | Siempre | Derivada dim_park | park_id | ⭐⭐⭐⭐ |
| 12 | `yego_commission_proxy_config` | ops | config comisión | Vigente | On-change | country | ⭐⭐⭐ |
| 13 | `mv_supply_segments_weekly` | ops | supply semanal | Varias semanas | Refresh MV | park_id | ⭐⭐⭐ |

### 2.2 Fuentes VACÍAS para este Park

| Tabla | Schema | Razón de Vacío | Impacto |
|-------|--------|---------------|---------|
| `summary_daily` | public | 0 registros para park_id | No se puede obtener tasa de aceptación |
| `module_ct_fleet_summary_daily` | public | Drivers del park no matchean (supply hours) | CRÍTICO: no hay horas online reales |
| `module_miauto_cuota_semanal` | public | Programa no activo aún para este park | Cuota real cobrada no disponible |
| `module_miauto_otros_gastos` | public | 0 registros | Otros gastos no registrados |
| `module_ct_cabinet_payments` | public | 0 para este park | Sin data de pagos cabinet |

### 2.3 Fuentes INEXISTENTES (no hay tabla en BD)

| Concepto Necesario | Impacto | Alternativa |
|-------------------|---------|-------------|
| Horas online/conectado (sessions) | CRÍTICO | Usar `horas_trabajo` de billing como proxy |
| Seguro vehículo | MEDIO | Input configurable |
| GPS tracking cost | BAJO | Probablemente incluido en cuota |
| Combustible en litros | BAJO | Solo existe gasto en soles |
| Multas/peajes | BAJO | No disponible |
| Accidentes/siniestros | BAJO | No disponible |
| Lavados | BAJO | No disponible |
| Depreciación contable | MEDIO | Derivable: valor / (cuotas × 4.33) |
| Zonas/rutas geocodificadas | BAJO | Solo texto en `direccion` |

---

## 3. DETALLE DE COLUMNAS POR FUENTE CLAVE

### 3.1 `public.trips_2026` (y trips_2025)

| Columna | Tipo | Uso para Profitability | Completitud |
|---------|------|----------------------|-------------|
| park_id | text | Filtro principal del park | 100% |
| conductor_id | text | Join con drivers, segmentación | 100% |
| fecha_inicio_viaje | timestamp | Fecha/hora del viaje, turnos | 100% |
| fecha_finalizacion | timestamp | Duración calculada | 99.99% |
| condicion | text | Filtro: 'Completado' vs cancelados | 100% |
| precio_yango_pro | numeric | Revenue bruto (total cobrado al pasajero) | 97.6% (solo completados) |
| distancia_km | numeric | Distancia con pasajero (**NOTA: campo en METROS**) | 97.7% |
| efectivo | numeric | Monto pagado en efectivo | 84.2% |
| tarjeta | numeric | Monto pagado con tarjeta | 16.5% |
| tipo_servicio | text | Línea de negocio | ~100% |
| direccion | text | Ruta texto (origen → destino) | ~100% |
| comision_servicio | numeric | Comisión de servicio | 8.5% |
| comision_empresa_asociada | numeric | **SIEMPRE NULL** — no usable | 0% |
| pagos_viajes_flota | numeric | **SIEMPRE NULL o 0** — no usable | 0% |
| codigo_pedido | text | ID único del viaje | 100% |

### 3.2 `public.module_weekly_billing`

| Columna | Tipo | Uso | Confiabilidad |
|---------|------|-----|---------------|
| driver_id | text | Join con drivers | 100% |
| fecha_inicio | date | Inicio de la semana | 100% |
| fecha_fin | date | Fin de la semana | 100% |
| total_viajes | int | Viajes completados en la semana | ALTA |
| horas_trabajo | numeric | Horas trabajadas (proxy de supply hours) | ALTA |
| monto_total_producido | numeric | Revenue bruto generado | ALTA |
| comision_app | numeric | Comisión plataforma (Yango/InDrive) | ALTA |
| monto_neto | numeric | Revenue neto post-comisión | ALTA |
| km_recorrido | numeric | KM totales (incluye vacío) | ALTA |
| gasto_combustible | numeric | Gasto combustible en S/ | ALTA |
| gasto_mantenimiento | numeric | Gasto mantenimiento en S/ | ALTA |
| porcentaje_pago | numeric | % pago conductor aplicado | ALTA |
| pago_total | numeric | Pago total al conductor | ALTA |
| utilidad | numeric | Resultado neto (puede ser negativo) | ALTA |
| bono_yango | numeric | Bono/incentivo de plataforma | ALTA |
| bono_adic_viajes | numeric | Bono adicional por volumen | ALTA |

### 3.3 `public.module_weekly_income`

| Columna | Tipo | Uso |
|---------|------|-----|
| driver_id | text | Join con drivers |
| fecha_inicio | date | Inicio semana |
| price_yango_pro | numeric | Precio bruto Yango Pro |
| platform_fees | numeric | Fees de plataforma (negativo) |
| bonificacion | numeric | Bonificaciones recibidas |
| cash_collected | numeric | Efectivo cobrado |
| non_cash_payment | numeric | Pagos no-efectivo |

### 3.4 `public.drivers`

| Columna | Tipo | Uso |
|---------|------|-----|
| driver_id | text (PK) | Identificador único |
| park_id | text | **Clave de relación park → driver** |
| nombre | text | Nombre del conductor |
| estado | text | Estado (activo/inactivo) |

### 3.5 `public.module_payment_percentages`

| Columna | Tipo | Uso |
|---------|------|-----|
| min_validated_trips | int | Umbral mínimo de viajes/semana |
| percentage | numeric | % de pago para el conductor |
| valid_from | date | Fecha de vigencia |

### 3.6 `public.module_miauto_cronograma_rule`

| Columna | Tipo | Uso |
|---------|------|-----|
| cronograma_id | int | FK al cronograma |
| orden | int | Orden del escalón |
| viajes | int | Mínimo de viajes para bono |
| bono_auto | numeric | Descuento en cuota por trips |
| cuotas_por_vehiculo | numeric | Cuota semanal base |

---

## 4. MAPEO DEL PARK

### 4.1 Identificación

| Atributo | Valor |
|----------|-------|
| park_id | `64085dd85e124e2c808806f70d527ea8` |
| Park Name | Yego Lima |
| City | Lima |
| Country | Peru |
| LOB | Autos Regular |
| Schema | dim.dim_park |

### 4.2 Vehículos Asociados

- Fuente: `module_miauto_cronograma_vehiculo` (16 vehículos configurados)
- Modelos: Kia (0KM y seminuevo), Hyundai (seminuevo)
- Cuotas semanales: S/ 500 – S/ 562.50
- Total cuotas: 156–261 semanas según modelo
- **No hay tabla de asignación vehículo→conductor explícita**

### 4.3 Conductores Asociados

| Métrica | Valor | Fuente |
|---------|-------|--------|
| Total en tabla `drivers` con park_id | ~34 | public.drivers |
| Activos últimos 30d (con viajes) | 34 | trips_2026 |
| Promedio activos/día | 21.8 | trips_2026 |
| En billing (última semana) | 26 | module_weekly_billing |
| Compartidos con otros parks | **Por validar** | Requiere query cruzada |

### 4.4 Cómo Aparece el Park en Cada Fuente

| Fuente | Método de Filtro | Directo/Indirecto |
|--------|-----------------|-------------------|
| trips_2026 | `WHERE park_id = '64085dd8...'` | **DIRECTO** |
| trips_2025 | `WHERE park_id = '64085dd8...'` | **DIRECTO** |
| drivers | `WHERE park_id = '64085dd8...'` | **DIRECTO** |
| module_weekly_billing | `WHERE driver_id IN (SELECT driver_id FROM drivers WHERE park_id = ...)` | **VÍA DRIVER** |
| module_weekly_income | VÍA DRIVER (misma lógica) | **VÍA DRIVER** |
| module_ct_fleet_summary_daily | Drivers no matchean → **NO DISPONIBLE** | N/A |
| summary_daily | 0 registros para park_id | **NO DISPONIBLE** |
| dim.dim_park | `WHERE park_id = '64085dd8...'` | **DIRECTO** |

### 4.5 Periodos Disponibles

| Granularidad | Disponible | Fuente |
|-------------|-----------|--------|
| Días | 30 días continuos confirmados (abr-may 2026) | trips_2026 |
| Semanas | 1 semana financiera (18-24 may); ~8 semanas income | billing / income |
| Meses | Derivable de trips (ene 2026 – presente) | trips_2026 |
| Histórico 2025 | Año completo | trips_2025 |

### 4.6 Riesgos de Mapeo

| Riesgo | Severidad | Detalle |
|--------|-----------|---------|
| Drivers compartidos entre parks | MEDIA | Requiere validación: `SELECT driver_id, COUNT(DISTINCT park_id) FROM drivers GROUP BY 1 HAVING COUNT(*) > 1` |
| Billing solo 1 semana | ALTA | No se puede calcular tendencia ni estacionalidad de costos |
| Fleet summary vacía | ALTA | Sin supply hours reales; solo proxy de billing |
| Vehículos sin asignación explícita | MEDIA | No hay tabla vehicle_assignment; solo cronograma de pagos |
| park_id podría cambiar | BAJA | El park_id es estable en el sistema |

---

## 5. ARQUITECTURA DE DATOS PROPUESTA

```
┌─────────────────────────────────────────────────────────────────────┐
│                    YEGO PRO PROFITABILITY MODULE                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  FUENTES PRIMARIAS                  CAPA DE AGREGACIÓN               │
│  ─────────────────                  ────────────────────              │
│                                                                       │
│  trips_2026 ──────────┐                                              │
│  trips_2025 ──────────┤     ┌──────────────────────────────┐        │
│                        ├────►│  profitability_weekly_fact    │        │
│  module_weekly_billing─┤     │  (conductor × semana)         │        │
│  module_weekly_income ─┤     └──────────────┬───────────────┘        │
│                        │                    │                         │
│  drivers ─────────────┤     ┌──────────────▼───────────────┐        │
│  payment_percentages ──┤     │  profitability_vehicle_fact   │        │
│  cronograma_rule ──────┘     │  (vehículo × semana)          │        │
│                              └──────────────┬───────────────┘        │
│  INPUTS CONFIGURABLES                       │                         │
│  ────────────────────                       ▼                         │
│  seguro_gps_mensual ──┐     ┌──────────────────────────────┐        │
│  reserva_desgaste ────┤     │  profitability_park_summary   │        │
│  precio_gasolina ─────┘     │  (park × semana/mes)           │        │
│                              └──────────────────────────────┘        │
│                                                                       │
│  ENDPOINTS                                                            │
│  ─────────                                                            │
│  /profitability/overview                                              │
│  /profitability/weekly-closed                                         │
│  /profitability/last-closed-day                                       │
│  /profitability/driver                                                │
│  /profitability/vehicle                                               │
│  /profitability/shift                                                 │
│  /profitability/waterfall                                             │
│  /profitability/inputs                                                │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. RIESGOS DE DATA

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| 1 | Billing tiene solo 1 semana | ALTA | CRÍTICO | Automatizar carga semanal; indicar "low confidence" si < 4 semanas |
| 2 | Sin supply hours reales | ALTA | ALTO | Usar horas_trabajo de billing; marcar como "proxy" |
| 3 | Fleet summary vacía para park | CONFIRMADO | ALTO | No depender de ella; usar billing como fuente de productividad |
| 4 | KM en trips está en metros, no km | CONFIRMADO | MEDIO | Dividir por 1000 en todo cálculo |
| 5 | comision_empresa_asociada siempre NULL | CONFIRMADO | MEDIO | Usar comision_app de billing (16.7%) |
| 6 | Discrepancia KM trips vs billing | CONFIRMADO | ALTO | trips: 3.75km (solo pasajero); billing: 9.20km (total). Usar billing para costos |
| 7 | 8 drivers en trips sin billing | MEDIA | MEDIO | Posiblemente nuevos; billing cubrirá en semanas siguientes |
| 8 | Cancelaciones 49.5% | CONFIRMADO | ALTO | Afecta productividad real; incluir en métricas |
| 9 | Sin tabla de asignación vehículo→conductor | CONFIRMADO | MEDIO | Solo se puede analizar por conductor, no por vehículo individual |

---

## 7. RECOMENDACIÓN TÉCNICA

### Para Fase 1 Backend:

1. **Crear servicio `profitability_service.py`** que:
   - Lea trips_2026 filtrado por park_id
   - Lea module_weekly_billing vía drivers del park
   - Lea module_weekly_income vía drivers del park
   - Lea configuración de cronograma y escalones
   - Acepte inputs configurables (seguro, reserva, etc.)

2. **Crear tabla de configuración** `profitability_config`:
   - park_id, config_key, config_value, updated_at
   - Para inputs que no vienen de BD (seguro, GPS, etc.)

3. **Crear MVs de agregación** (opcionales, para performance):
   - `ops.mv_profitability_weekly_driver` (conductor × semana)
   - `ops.mv_profitability_weekly_park` (park × semana)

4. **NO crear tabla de hechos nueva** todavía — usar queries directas en Fase 1 y materializar en Fase 2 solo si el performance lo requiere.

### Stack Tecnológico:
- Backend: Python + FastAPI (existente)
- DB: PostgreSQL (existente, schema `public` + `ops`)
- Conexión: psycopg2 pool (existente en `app/db/connection.py`)
- Pattern: Service layer → Router → API (pattern existente)

---

## 8. GO / NO-GO

| Criterio | Status | Nota |
|----------|--------|------|
| Fuente de trips disponible | ✅ GO | trips_2026 con park_id directo |
| Fuente financiera disponible | ⚠️ PARCIAL | Billing solo 1 semana; income 8 semanas |
| Revenue calculable | ✅ GO | precio_yango_pro disponible al 97.6% |
| Costos variables calculables | ✅ GO | Billing tiene combustible + mantenimiento |
| Pago conductor calculable | ✅ GO | Billing tiene porcentaje y pago real |
| Cuota vehículo calculable | ⚠️ PARCIAL | Cronograma existe; cobro real no |
| Supply hours | ⚠️ PROXY | horas_trabajo de billing; no hay online hours |
| Segmentación día/noche | ✅ GO | fecha_inicio_viaje disponible |
| Segmentación por conductor | ✅ GO | conductor_id disponible |
| Segmentación por vehículo | ❌ NO GO | Sin asignación vehículo→conductor |
| Histórico suficiente | ⚠️ PARCIAL | Trips: sí; Billing: solo 1 semana |

### VEREDICTO: **GO CONDICIONAL**

Proceder con Fase 1 Backend con las siguientes limitaciones aceptadas:
1. Profitability por **vehículo individual** no es posible (se reportará por conductor)
2. Costos serán **mezcla de reales + configurables**
3. KPI de supply hours será **proxy** (horas_trabajo de billing)
4. Se requiere **automatizar carga semanal** de billing para histórico
