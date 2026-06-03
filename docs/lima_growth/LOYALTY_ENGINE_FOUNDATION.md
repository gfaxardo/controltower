# Loyalty Engine Foundation — YEGO Lima Growth Tower

## 1. Objetivo

Identificar conductores con menos de `target_weekly_trips` viajes semanales y clasificarlos para generar listas accionables de crecimiento.

## 2. Fuentes Canonicas

### Current Week (diario → semanal)
**`growth.yango_lima_driver_360_daily`**

Columnas usadas:
- `completed_orders` → `completed_orders_week` (SUM en la semana)
- `supply_hours` → `supply_hours_week` (SUM en la semana)
- `trips_per_supply_hour` → `trips_per_supply_hour_week` (recalculado como completed/supply)
- `driver_state` → copiado directamente
- `productivity_band` → copiado directamente
- `active_flag` → filtro de inclusion (solo activos)

### Historical
**`growth.yango_lima_driver_history_weekly`**

Columnas usadas:
- `avg_orders_4w` → rolling metric
- `avg_orders_8w` → rolling metric
- `avg_orders_12w` → rolling metric (usado para recoverable_flag)
- `best_week_12w` → mejor semana en 12 semanas
- `historical_band` → banda historica

## 3. Fuentes Deprecated

| Fuente | Razon | Reemplazo |
|--------|-------|-----------|
| `ops.driver_daily_activity_fact` | Global, no Lima-especifico, sin supply_hours | `growth.yango_lima_driver_360_daily` |
| `growth.yango_lima_orders_raw` (supply proxy) | Proxy impreciso via `ended_at - created_at` | `growth.yango_lima_driver_360_daily.supply_hours` |
| `trips_2026` runtime | Violacion de aislamiento de Lima Growth | Tablas historicas propias en schema growth |

## 4. Por que no se usa proxy de supply

El proxy `ended_at - created_at` desde raw orders:
- No captura tiempo real de supply (tiempo entre viajes, espera, disponibilidad)
- Depende de timestamps que pueden ser nulos o inconsistentes
- Rompe el principio de fuente unica canonica

`growth.yango_lima_driver_360_daily.supply_hours` es calculado por el pipeline de Driver360 desde la API de Yango y es la fuente autoritativa.

## 5. Target Configurable

- Setting: `LIMA_GROWTH_WEEKLY_TRIPS_TARGET` (default: 50)
- Override via request body: `target_weekly_trips`
- Rango valido: 1-200

## 6. Segmentos Dinamicos

Basados en `distance_to_target`:

| Segmento | Regla |
|----------|-------|
| NEAR_TARGET | distance <= max(10, target * 0.2) |
| MID_GAP | distance <= max(20, target * 0.4) |
| LARGE_GAP | distance <= max(40, target * 0.8) |
| VERY_LARGE_GAP | distance > max(40, target * 0.8) |

Labels legacy (display):
SUB50_40_49 → NEAR_TARGET, SUB50_30_39 → MID_GAP,
SUB50_20_29 → LARGE_GAP, SUB50_00_09 → VERY_LARGE_GAP

## 7. Growth Priority

1. recoverable_flag = true
2. NEAR_TARGET
3. HIGH_SUPPLY_LOW_ORDERS
4. MID_GAP
5. LARGE_GAP
6. VERY_LARGE_GAP

## 8. Recoverable Flag

`recoverable_flag = true` si:
- `completed_orders_week < target_weekly_trips`
- AND `avg_orders_12w >= target_weekly_trips`

Indica conductores que historicamente alcanzaban el target pero estan debajo esta semana.

## 9. Pendiente (Fases Futuras)

- Lealtad 1: nuevos/reactivados (14d / 90d windows)
- Lealtad 3: degradation/churn risk engine
- Segmentacion unificada Lealtad 1/2/3
