# AUDITORIA FASE 1F-5 — TRIPS SCHEMA DISCOVERY

**Fecha**: 2026-05-20  
**Fuente**: `public.trips_2026` (information_schema.columns)

## Columnas encontradas (25 columnas)

| Columna | Tipo | Uso FRAUD |
|---|---|---|
| id | varchar | ID alternativo de viaje |
| condicion | varchar | **Estado**: 'Completado' / 'Cancelado' |
| codigo_pedido | varchar | **source_trip_id** principal |
| conductor_id | varchar | **driver_id** |
| conductor_nombre | varchar | Nombre (no usado directamente) |
| vehiculo_placa | varchar | Placa (no usado directamente) |
| vehiculo_modelo | varchar | Modelo (no usado directamente) |
| fecha_inicio_viaje | timestamp | **trip_datetime** |
| fecha_finalizacion | timestamp | **duration derivable**: end - start |
| motivo_cancelacion | text | Motivo cancelacion |
| direccion | text | **ROUTE TEXT**: origen → destino |
| tipo_servicio | varchar | **lob / service_type** |
| distancia_km | numeric | **distance** |
| precio_yango_pro | numeric | **amount** |
| efectivo | numeric | cash component |
| tarjeta | numeric | card component |
| pago_corporativo | numeric | corporate payment |
| propina | numeric | tip |
| promocion | numeric | promotion |
| bonificaciones | numeric | bonuses |
| comision_servicio | numeric | service commission |
| comision_empresa_asociada | numeric | partner commission |
| otros_pagos | numeric | other payments |
| pagos_viajes_flota | numeric | fleet payments |
| park_id | varchar | **park_id** |

## Columnas CRÍTICAS encontradas

| Capacidad | Columna | Estado |
|---|---|---|
| driver_id | conductor_id | OK |
| park_id | park_id | OK |
| trip_datetime | fecha_inicio_viaje | OK |
| trip_status | condicion | OK |
| payment_method | tarjeta/efectivo (derivado) | OK |
| amount | precio_yango_pro | OK |
| distance | distancia_km | OK |
| duration | fecha_finalizacion - fecha_inicio_viaje (derivado) | OK |
| route_text | direccion (origen -> destino) | OK |
| service_type | tipo_servicio | OK |

## Columnas FALTANTES

| Capacidad | Estado |
|---|---|
| pickup_lat | NO existe |
| pickup_lng | NO existe |
| dropoff_lat | NO existe |
| dropoff_lng | NO existe |
| city directo | NO existe (usar park_id) |
| country directo | NO existe |

## Análisis de ruta (direccion)

- 200/200 samples usan `->` como separador.
- 4/200 también contienen ` - ` (dentro de direcciones).
- Formato: `Origen, numero, distrito -> Destino, numero, distrito`
- Ruteo textual 100% presente.
- Parseable deterministicamente.

## Fuentes recomendadas

| Dato | Columna |
|---|---|
| trip_datetime | **fecha_inicio_viaje** (timestamp) |
| amount | **precio_yango_pro** (numeric) |
| payment_method | Derivado: tarjeta > 0 → 'card', efectivo > 0 → 'cash' |
| route_text | **direccion** (origen -> destino) |
| distance | **distancia_km** (numeric) |
| duration | **fecha_finalizacion - fecha_inicio_viaje** (derivado en segundos) |
| service_type | **tipo_servicio** |

## Decisión

**GO**. Condición mínima satisfecha:
- driver_id existe (conductor_id)
- fecha existe (fecha_inicio_viaje)
- estado existe (condicion)
- ruta existe en direccion con separador `->`
- distance existe (distancia_km)
- duration derivable (fecha_finalizacion - fecha_inicio_viaje)

NO se requiere geocodificación externa.
