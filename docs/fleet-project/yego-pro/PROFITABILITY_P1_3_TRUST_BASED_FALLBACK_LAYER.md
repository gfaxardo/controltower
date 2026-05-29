# Profitability P1.3 — Trust-Based Fallback Layer

## Objetivo

Profitability no bloquea Drivers, Vehicles, Shifts ni Waterfall solo porque falten cierres completos.
Muestra informacion usando la mejor fuente disponible, con etiqueta clara de confianza:

| Nivel | Significado |
|-------|-------------|
| REAL | Dato verificado desde fuente financiera cerrada |
| ESTIMATED | Calculado con produccion real + supuestos de costos |
| LEGACY | Basado en defaults historicos |
| NOT_AVAILABLE | No se puede calcular con la data actual |

## Jerarquia de fuentes

### Produccion
1. `module_calculated_shifts` = REAL_OPERATIONAL
2. `trips_2026` = FALLBACK_OPERATIONAL

### Pagos/Liquidacion
1. `module_driver_closes` = REAL_SETTLEMENT
2. `assumptions/config` = ESTIMATED

### Financiero
1. `module_weekly_billing` = REAL_FINANCIAL
2. `module_calculated_shifts + assumptions` = ESTIMATED_FINANCIAL
3. `legacy_defaults` = LEGACY_MODEL

## Supuestos de costos (cuando no hay cierre)

| Parametro | Valor | Fuente |
|-----------|-------|--------|
| Combustible/viaje | S/ 3.50 | Promedio historico |
| Mantenimiento/viaje | S/ 1.20 | Promedio historico |
| Comision plataforma | 25% | Contrato |
| Payout conductor default | 45% | Esquema base |
| Costo fijo diario | S/ 15.00 | Legacy model |

## Cambios implementados

### Backend

**`backend/app/services/yego_pro_profitability_service.py`**:
- Constantes `SOURCE_PRIORITY` y `COST_ASSUMPTIONS`
- `get_drivers`: fallback a `module_calculated_shifts` cuando MV_DRIVER esta vacio
- `get_vehicles`: fallback a agrupacion por placa desde shifts
- `get_shifts`: agrega `estimated_margin` basado en supuestos
- `get_waterfall`: nuevo endpoint P&L con confianza por linea
- `get_quality`: agrega `trust_layer_summary` con REAL/ESTIMATED/LEGACY/NOT_AVAILABLE
- `_build_trust_layer_summary`: genera resumen de confianza y upgrade path

**`backend/app/routers/yego_pro_profitability.py`**:
- Nuevo endpoint `GET /fleet-project/yego-pro/profitability/waterfall`

### Frontend

**`frontend/src/components/YegoProProfitabilityPage.jsx`**:
- `ConfidenceBadge`: componente para mostrar nivel de confianza
- `TrustWarningBanner`: banner de advertencia cuando datos son parciales
- `TrustLayerSection`: panel en Data Quality mostrando que es real vs estimado
- `DataTable`: columna de confianza cuando hay datos estimados
- `WaterfallPanel`: badges de confianza por linea
- `TabularPanel`: muestra warnings y confianza general
- `extractRows`: ahora reconoce `drivers`, `vehicles`, `shifts`, `weeks`, `days`
- Labels para nuevos niveles de confianza (REAL_OPERATIONAL, ESTIMATED_FINANCIAL, LEGACY, etc.)

**`frontend/src/services/api.js`**:
- `getYegoProProfitabilityWaterfall`: nuevo call al endpoint waterfall

## Comportamiento por tab

| Tab | Sin billing | Con billing |
|-----|-------------|-------------|
| Drivers | Muestra estimacion desde shifts + supuestos | Muestra datos reales de billing |
| Vehicles | Agrupa por placa con costos estimados | Fleet config + datos reales |
| Shifts | Produccion real + margen estimado | Produccion real + margen estimado |
| Waterfall | P&L parcial con lineas estimadas | P&L completo real |
| Data Quality | Trust Layer: que es real y que falta | Trust Layer: todo real |

## Reglas de fallback

1. Si falta una fuente GOLD, no bloquear. Usar siguiente fuente y mostrar confianza.
2. NO mostrar vacio si hay produccion.
3. Cada dato tiene confidence.
4. Mensajes humanos en vez de "No hay datos disponibles".

## QA Validado

- `python -m compileall backend/app` — OK
- `cd frontend && npm run build` — OK
- No se tocan modulos fuera del scope (Drivers, Yango Loyalty, Omniview, WorkOS)
- Cambios aditivos, sin breaking changes al contrato API existente

## Fecha

2026-05-29
