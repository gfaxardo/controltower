# FRAUD DATA CONTRACT — FASE 1F

## Principio rector
El modulo antifraude no inventa columnas. Si una columna no existe en la fuente, se informa como null y se documenta. Las únicas escrituras permitidas son en el esquema `fraud`.

---

## fraud_normalized_trip (contrato de lectura, no es tabla)

| Campo | Tipo | Fuente trips_2026 | Fallback |
|---|---|---|---|
| source_table | TEXT | `'trips_2026'` | Fijo |
| source_trip_id | TEXT | `codigo_pedido` | `id` |
| driver_id | TEXT | `conductor_id` | null |
| park_id | TEXT | `park_id` | null |
| trip_datetime | TIMESTAMPTZ | `fecha_inicio_viaje` | null |
| trip_status | TEXT | `condicion` | null |
| is_completed | BOOLEAN | `condicion = 'Completado'` | false |
| payment_method | TEXT | `'card' IF tarjeta>0 ELSE 'cash'` | null |
| amount | NUMERIC | `precio_yango_pro` | null |
| distance | NUMERIC | `distancia_km` | null |
| duration | NUMERIC | No existe | null |
| pickup_lat | NUMERIC | No existe | null |
| pickup_lng | NUMERIC | No existe | null |
| pickup_address | TEXT | `direccion` | null |
| pickup_cluster_key | TEXT | Normalizado de direccion | null |
| dropoff_lat | NUMERIC | No existe | null |
| dropoff_lng | NUMERIC | No existe | null |
| dropoff_address | TEXT | No existe | null |
| city | TEXT | No existe directo | null (usar park_id) |
| country | TEXT | No existe directo | null |
| lob | TEXT | `tipo_servicio` | null |
| segment | TEXT | No existe directo | null |
| route_text | TEXT | direccion | null |
| origin_text | TEXT | Parseado de direccion | null |
| destination_text | TEXT | Parseado de direccion | null |
| origin_norm | TEXT | origin_text normalizado | null |
| destination_norm | TEXT | destination_text normalizado | null |
| origin_cluster_key | TEXT | pickup_lat,lng > origin_norm > pickup_address | null |
| destination_cluster_key | TEXT | dropoff_lat,lng > destination_norm | null |
| route_signature | TEXT | origin_norm -> destination_norm | null |
| reverse_route_signature | TEXT | destination_norm -> origin_norm | null |
| route_parse_quality | TEXT | ok / partial / failed | null |
| duration_seconds | NUMERIC | fecha_finalizacion - fecha_inicio_viaje | null |

---

## fraud_driver_trust (tabla: fraud.driver_trust_snapshot)

| Campo | Tipo | Descripcion |
|---|---|---|
| driver_id | TEXT | `conductor_id` normalizado |
| park_id | TEXT | Del viaje mas reciente |
| total_completed_trips | BIGINT | COUNT viajes completados |
| completed_trips_7d | BIGINT | Ultimos 7 dias |
| completed_trips_30d | BIGINT | Ultimos 30 dias |
| first_completed_trip_at | TIMESTAMPTZ | Primer viaje completado |
| last_completed_trip_at | TIMESTAMPTZ | Ultimo viaje completado |
| trust_tier | TEXT | trusted / new_or_unproven / restricted / unknown |
| trust_reason | JSONB | Motivo de la clasificacion |

---

## fraud_driver_risk (tabla: fraud.driver_risk_snapshot)

| Campo | Tipo | Descripcion |
|---|---|---|
| driver_id | TEXT | |
| park_id | TEXT | |
| risk_score | NUMERIC | 0-100+ |
| severity | TEXT | low / medium / high / critical |
| triggered_rules | JSONB | Lista de reglas que dispararon |
| suspicious_trip_count | BIGINT | Viajes marcados |
| completed_trip_count | BIGINT | Total completados |
| recommended_action | TEXT | Accion sugerida |
| action_reason | JSONB | Evidencia |

---

## Capacidades reales detectadas

| Capacidad | Disponible | Fuente |
|---|---|---|
| payment_method | SI (derivado) | tarjeta/efectivo en trips_2026 |
| amount | SI | precio_yango_pro |
| pickup lat/lng | NO | Sin columnas GPS en trips_2026 |
| pickup address | SI | direccion en trips_2026 |
| distance | SI | distancia_km en trips_2026 |
| duration | NO | Sin columna de duracion |
| bonus source | SI (indirecto) | module_bonus_thresholds, ops.scout_liquidation_ledger |
| balance source | NO | Sin fuente de saldo/PLAC en tablas base |
| bank source | SI | public.payment_details (bank_name, account_number) |
