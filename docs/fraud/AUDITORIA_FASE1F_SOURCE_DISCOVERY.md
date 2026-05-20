# AUDITORIA FASE 1F — SOURCE DISCOVERY ANTIFRAUDE

Fecha: 2026-05-19 23:15

## Schemas detectados

- `bi`
- `canon`
- `closer`
- `dim`
- `observational`
- `ops`
- `pg_temp_1`
- `pg_temp_10`
- `pg_temp_100`
- `pg_temp_102`
- `pg_temp_11`
- `pg_temp_12`
- `pg_temp_13`
- `pg_temp_14`
- `pg_temp_15`
- `pg_temp_16`
- `pg_temp_17`
- `pg_temp_18`
- `pg_temp_19`
- `pg_temp_20`
- `pg_temp_21`
- `pg_temp_22`
- `pg_temp_23`
- `pg_temp_24`
- `pg_temp_25`
- `pg_temp_26`
- `pg_temp_27`
- `pg_temp_28`
- `pg_temp_29`
- `pg_temp_3`
- `pg_temp_30`
- `pg_temp_31`
- `pg_temp_32`
- `pg_temp_33`
- `pg_temp_34`
- `pg_temp_35`
- `pg_temp_36`
- `pg_temp_37`
- `pg_temp_38`
- `pg_temp_39`
- `pg_temp_4`
- `pg_temp_40`
- `pg_temp_41`
- `pg_temp_42`
- `pg_temp_43`
- `pg_temp_44`
- `pg_temp_45`
- `pg_temp_46`
- `pg_temp_47`
- `pg_temp_48`
- `pg_temp_49`
- `pg_temp_5`
- `pg_temp_50`
- `pg_temp_51`
- `pg_temp_52`
- `pg_temp_53`
- `pg_temp_54`
- `pg_temp_55`
- `pg_temp_56`
- `pg_temp_57`
- `pg_temp_58`
- `pg_temp_59`
- `pg_temp_6`
- `pg_temp_60`
- `pg_temp_61`
- `pg_temp_62`
- `pg_temp_63`
- `pg_temp_64`
- `pg_temp_65`
- `pg_temp_66`
- `pg_temp_67`
- `pg_temp_68`
- `pg_temp_69`
- `pg_temp_7`
- `pg_temp_70`
- `pg_temp_71`
- `pg_temp_72`
- `pg_temp_73`
- `pg_temp_74`
- `pg_temp_75`
- `pg_temp_76`
- `pg_temp_77`
- `pg_temp_78`
- `pg_temp_79`
- `pg_temp_8`
- `pg_temp_81`
- `pg_temp_82`
- `pg_temp_83`
- `pg_temp_87`
- `pg_temp_88`
- `pg_temp_89`
- `pg_temp_9`
- `pg_temp_90`
- `pg_temp_92`
- `pg_temp_93`
- `pg_temp_95`
- `pg_temp_96`
- `pg_temp_98`
- `pg_toast`
- `pg_toast_temp_1`
- `pg_toast_temp_10`
- `pg_toast_temp_100`
- `pg_toast_temp_102`
- `pg_toast_temp_11`
- `pg_toast_temp_12`
- `pg_toast_temp_13`
- `pg_toast_temp_14`
- `pg_toast_temp_15`
- `pg_toast_temp_16`
- `pg_toast_temp_17`
- `pg_toast_temp_18`
- `pg_toast_temp_19`
- `pg_toast_temp_20`
- `pg_toast_temp_21`
- `pg_toast_temp_22`
- `pg_toast_temp_23`
- `pg_toast_temp_24`
- `pg_toast_temp_25`
- `pg_toast_temp_26`
- `pg_toast_temp_27`
- `pg_toast_temp_28`
- `pg_toast_temp_29`
- `pg_toast_temp_3`
- `pg_toast_temp_30`
- `pg_toast_temp_31`
- `pg_toast_temp_32`
- `pg_toast_temp_33`
- `pg_toast_temp_34`
- `pg_toast_temp_35`
- `pg_toast_temp_36`
- `pg_toast_temp_37`
- `pg_toast_temp_38`
- `pg_toast_temp_39`
- `pg_toast_temp_4`
- `pg_toast_temp_40`
- `pg_toast_temp_41`
- `pg_toast_temp_42`
- `pg_toast_temp_43`
- `pg_toast_temp_44`
- `pg_toast_temp_45`
- `pg_toast_temp_46`
- `pg_toast_temp_47`
- `pg_toast_temp_48`
- `pg_toast_temp_49`
- `pg_toast_temp_5`
- `pg_toast_temp_50`
- `pg_toast_temp_51`
- `pg_toast_temp_52`
- `pg_toast_temp_53`
- `pg_toast_temp_54`
- `pg_toast_temp_55`
- `pg_toast_temp_56`
- `pg_toast_temp_57`
- `pg_toast_temp_58`
- `pg_toast_temp_59`
- `pg_toast_temp_6`
- `pg_toast_temp_60`
- `pg_toast_temp_61`
- `pg_toast_temp_62`
- `pg_toast_temp_63`
- `pg_toast_temp_64`
- `pg_toast_temp_65`
- `pg_toast_temp_66`
- `pg_toast_temp_67`
- `pg_toast_temp_68`
- `pg_toast_temp_69`
- `pg_toast_temp_7`
- `pg_toast_temp_70`
- `pg_toast_temp_71`
- `pg_toast_temp_72`
- `pg_toast_temp_73`
- `pg_toast_temp_74`
- `pg_toast_temp_75`
- `pg_toast_temp_76`
- `pg_toast_temp_77`
- `pg_toast_temp_78`
- `pg_toast_temp_79`
- `pg_toast_temp_8`
- `pg_toast_temp_81`
- `pg_toast_temp_82`
- `pg_toast_temp_83`
- `pg_toast_temp_87`
- `pg_toast_temp_88`
- `pg_toast_temp_89`
- `pg_toast_temp_9`
- `pg_toast_temp_90`
- `pg_toast_temp_92`
- `pg_toast_temp_93`
- `pg_toast_temp_95`
- `pg_toast_temp_96`
- `pg_toast_temp_98`
- `plan`
- `public`
- `staging`
- `tournament_fixture`
- `yego_integral`

## Fuentes de viajes

| Tabla | Filas | driver_id | fecha | estado | pago | monto | pickup | distancia |
|---|---|---|---|---|---|---|---|---|
| `ops.plan_trips_monthly` | 3144 | no | SI | no | no | no | no | no |
| `public.module_leads_trips` | 0 | SI | SI | no | no | no | no | no |
| `public.trips_2025` | 47952972 | no | SI | SI | no | no | no | no |
| `public.trips_2026` | 16380226 | no | SI | SI | no | no | no | no |
| `public.trips_2026_old` | 0 | no | SI | SI | no | no | no | no |
| `public.trips_all` | 50315456 | no | SI | SI | no | no | no | no |
| `public.trips_driver_total` | 54066 | SI | no | no | no | SI | no | no |
| `public.trips_tracking` | 11477 | no | SI | no | no | no | no | no |
| `public.trips_tracking_2025` | 8395 | no | SI | no | no | no | no | no |
| `ops.mv_real_trips_by_lob_month` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_by_lob_week` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_monthly` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_monthly_old` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_monthly_old_margin` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_monthly_old_signed` | None | no | no | no | no | no | no | no |
| `ops.mv_real_trips_weekly` | None | no | no | no | no | no | no | no |

## Columnas detalladas — Tablas de viajes

### `ops.plan_trips_monthly` (3144 filas)

- `id` (bigint)
- `plan_version` (text)
- `country` (text)
- `city` (text)
- `park_id` (text)
- `lob_base` (text)
- `segment` (text)
- `month` (date)
- `projected_trips` (integer)
- `projected_drivers` (integer)
- `projected_ticket` (numeric)
- `projected_trips_per_driver` (numeric)
- `created_at` (timestamp with time zone)
- `city_norm` (text)
- `plan_city_resolved_norm` (text)
- `projected_revenue` (numeric)

### `public.module_leads_trips` (0 filas)

- `id` (integer)
- `driver_id` (integer)
- `trip_date` (timestamp without time zone)
- `trip_count` (integer)
- `post_reactivation` (boolean)
- `created_at` (timestamp without time zone)

### `public.trips_2025` (47952972 filas)

- `id` (character varying)
- `condicion` (character varying)
- `codigo_pedido` (character varying)
- `conductor_id` (character varying)
- `conductor_nombre` (character varying)
- `vehiculo_placa` (character varying)
- `vehiculo_modelo` (character varying)
- `fecha_inicio_viaje` (timestamp without time zone)
- `fecha_finalizacion` (timestamp without time zone)
- `motivo_cancelacion` (text)
- `direccion` (text)
- `tipo_servicio` (character varying)
- `distancia_km` (numeric)
- `precio_yango_pro` (numeric)
- `efectivo` (numeric)
- `tarjeta` (numeric)
- `pago_corporativo` (numeric)
- `propina` (numeric)
- `promocion` (numeric)
- `bonificaciones` (numeric)
- `comision_servicio` (numeric)
- `comision_empresa_asociada` (numeric)
- `otros_pagos` (numeric)
- `pagos_viajes_flota` (numeric)
- `park_id` (character varying)

### `public.trips_2026` (16380226 filas)

- `id` (character varying)
- `condicion` (character varying)
- `codigo_pedido` (character varying)
- `conductor_id` (character varying)
- `conductor_nombre` (character varying)
- `vehiculo_placa` (character varying)
- `vehiculo_modelo` (character varying)
- `fecha_inicio_viaje` (timestamp without time zone)
- `fecha_finalizacion` (timestamp without time zone)
- `motivo_cancelacion` (text)
- `direccion` (text)
- `tipo_servicio` (character varying)
- `distancia_km` (numeric)
- `precio_yango_pro` (numeric)
- `efectivo` (numeric)
- `tarjeta` (numeric)
- `pago_corporativo` (numeric)
- `propina` (numeric)
- `promocion` (numeric)
- `bonificaciones` (numeric)
- `comision_servicio` (numeric)
- `comision_empresa_asociada` (numeric)
- `otros_pagos` (numeric)
- `pagos_viajes_flota` (numeric)
- `park_id` (character varying)

### `public.trips_2026_old` (0 filas)

- `id` (character varying)
- `condicion` (character varying)
- `codigo_pedido` (character varying)
- `conductor_id` (character varying)
- `conductor_nombre` (character varying)
- `vehiculo_placa` (character varying)
- `vehiculo_modelo` (character varying)
- `fecha_inicio_viaje` (timestamp without time zone)
- `fecha_finalizacion` (timestamp without time zone)
- `motivo_cancelacion` (text)
- `direccion` (text)
- `tipo_servicio` (character varying)
- `distancia_km` (numeric)
- `precio_yango_pro` (numeric)
- `efectivo` (numeric)
- `tarjeta` (numeric)
- `pago_corporativo` (numeric)
- `propina` (numeric)
- `promocion` (numeric)
- `bonificaciones` (numeric)
- `comision_servicio` (numeric)
- `comision_empresa_asociada` (numeric)
- `otros_pagos` (numeric)
- `pagos_viajes_flota` (numeric)
- `park_id` (character varying)

### `public.trips_all` (50315456 filas)

- `id` (character varying)
- `condicion` (character varying)
- `codigo_pedido` (character varying)
- `conductor_id` (character varying)
- `conductor_nombre` (character varying)
- `vehiculo_placa` (character varying)
- `vehiculo_modelo` (character varying)
- `fecha_inicio_viaje` (timestamp without time zone)
- `fecha_finalizacion` (timestamp without time zone)
- `motivo_cancelacion` (text)
- `direccion` (text)
- `tipo_servicio` (character varying)
- `distancia_km` (numeric)
- `precio_yango_pro` (numeric)
- `efectivo` (numeric)
- `tarjeta` (numeric)
- `pago_corporativo` (numeric)
- `propina` (numeric)
- `promocion` (numeric)
- `bonificaciones` (numeric)
- `comision_servicio` (numeric)
- `comision_empresa_asociada` (numeric)
- `otros_pagos` (numeric)
- `pagos_viajes_flota` (numeric)
- `park_id` (character varying)

### `public.trips_driver_total` (54066 filas)

- `driver_id` (character varying)
- `name_driver` (character varying)
- `park_id` (character varying)
- `trips_total_2025` (bigint)
- `trips_total_2026` (bigint)
- `total` (bigint)

### `public.trips_tracking` (11477 filas)

- `id` (integer)
- `park_id` (character varying)
- `park_nombre` (character varying)
- `park_ciudad` (character varying)
- `ano` (integer)
- `mes` (integer)
- `dia` (integer)
- `procesado` (boolean)
- `registros_insertados` (integer)
- `registros_duplicados` (integer)
- `tiene_datos` (boolean)
- `error` (text)
- `fecha_proceso` (timestamp without time zone)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.trips_tracking_2025` (8395 filas)

- `id` (integer)
- `park_id` (character varying)
- `park_nombre` (character varying)
- `park_ciudad` (character varying)
- `ano` (integer)
- `mes` (integer)
- `dia` (integer)
- `procesado` (boolean)
- `registros_insertados` (integer)
- `registros_duplicados` (integer)
- `tiene_datos` (boolean)
- `error` (text)
- `fecha_proceso` (timestamp without time zone)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `ops.mv_real_trips_by_lob_month` (None filas)


### `ops.mv_real_trips_by_lob_week` (None filas)


### `ops.mv_real_trips_monthly` (None filas)


### `ops.mv_real_trips_monthly_old` (None filas)


### `ops.mv_real_trips_monthly_old_margin` (None filas)


### `ops.mv_real_trips_monthly_old_signed` (None filas)


### `ops.mv_real_trips_weekly` (None filas)


## Fuentes de drivers/parks

### `canon.driver_orphan_quarantine`

- `driver_id` (character varying)
- `person_key` (uuid)
- `detected_at` (timestamp with time zone)
- `detected_reason` (USER-DEFINED)
- `creation_rule` (character varying)
- `evidence_json` (jsonb)
- `status` (USER-DEFINED)
- `resolved_at` (timestamp with time zone)
- `resolution_notes` (text)

### `canon.drivers_index`

- `driver_id` (character varying)
- `park_id` (character varying)
- `phone_norm` (character varying)
- `license_norm` (character varying)
- `plate_norm` (character varying)
- `full_name_norm` (character varying)
- `hire_date` (date)
- `snapshot_date` (date)
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)
- `brand_norm` (character varying)
- `model_norm` (character varying)

### `dim.dim_geo_park`

- `park_id` (text)
- `park_name` (text)
- `city` (text)
- `country` (text)
- `is_active` (boolean)
- `updated_at` (timestamp with time zone)

### `dim.dim_park`

- `park_id` (character varying)
- `park_name` (text)
- `city` (text)
- `country` (text)
- `partner` (text)
- `default_line_of_business` (text)
- `has_multiple_lines` (boolean)
- `active` (boolean)
- `notes` (text)

### `ops.driver_name_aliases`

- `driver_id` (text)
- `alias_name_key` (text)
- `created_at` (timestamp without time zone)

### `ops.driver_segment_config`

- `id` (integer)
- `segment_code` (text)
- `segment_name` (text)
- `min_trips_week` (integer)
- `max_trips_week` (integer)
- `ordering` (integer)
- `is_active` (boolean)
- `effective_from` (date)
- `effective_to` (date)
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)

### `ops.park_country_fallback`

- `park_id` (text)
- `country` (text)
- `created_at` (timestamp with time zone)

### `ops.real_drill_service_by_park`

- `country` (text)
- `period_grain` (text)
- `period_start` (date)
- `segment` (text)
- `park_id` (text)
- `city` (text)
- `tipo_servicio_norm` (text)
- `trips` (bigint)
- `margin_total` (numeric)
- `margin_per_trip` (numeric)
- `km_avg` (numeric)
- `b2b_trips` (bigint)
- `b2b_share` (numeric)
- `last_trip_ts` (timestamp with time zone)

### `ops.stg_park_territory`

- `park_id` (text)
- `country` (text)
- `city` (text)
- `loaded_at` (timestamp with time zone)
- `loaded_by` (text)
- `default_line_of_business` (text)

### `public.conductores_cancelaciones`

- `id` (text)
- `nombre_completo` (text)
- `licencia_de_conducir` (text)
- `numero_de_placa_del_vehiculo` (text)
- `motivo_de_la_cancelacion` (text)
- `numero_de_telefono` (text)
- `fecha_de_inicio_del_viaje` (timestamp without time zone)
- `id_flota` (text)
- `nombre_flota` (text)

### `public.driver_active_list`

- `id` (bigint)
- `driver_id` (character varying)
- `park_id` (character varying)
- `trips` (integer)
- `month` (integer)
- `year` (integer)
- `category` (character varying)
- `count_orders_completed` (integer)
- `count_orders_all` (integer)
- `count_orders_accepted` (integer)
- `count_orders_cancelled_by_client` (integer)
- `count_orders_cancelled_by_driver` (integer)
- `count_orders_platform` (integer)
- `sum_price_cash` (numeric)
- `sum_price_cashless` (numeric)
- `sum_price_other_gas` (numeric)
- `sum_price_park_commission` (numeric)
- `sum_price_platform_commission` (numeric)
- `sum_work_time_seconds` (bigint)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.drivers`

- `driver_id` (character varying)
- `park_id` (character varying)
- `first_name` (character varying)
- `last_name` (character varying)
- `middle_name` (character varying)
- `full_name` (character varying)
- `phone` (character varying)
- `rating` (double precision)
- `work_status` (character varying)
- `hire_date` (date)
- `fire_date` (date)
- `is_selfemployed` (boolean)
- `car_id` (character varying)
- `car_brand` (character varying)
- `car_model` (character varying)
- `car_color` (character varying)
- `car_number` (character varying)
- `car_callsign` (character varying)
- `car_normalized_number` (character varying)
- `license_number` (character varying)
- `license_country` (character varying)
- `license_expiration_date` (date)
- `license_issue_date` (date)
- `license_normalized_number` (character varying)
- `account_balance` (numeric)
- `account_balance_limit` (numeric)
- `account_id` (character varying)
- `current_status` (character varying)
- `status_updated_at` (date)
- `account_type` (character varying)
- `account_number` (character varying)
- `recipient_name` (character varying)
- `document_type` (character varying)
- `document_number` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `id` (bigint)
- `active` (boolean)
- `works_terms` (character varying)

### `public.drivers_data`

- `driver_id` (character varying)
- `park_id` (character varying)
- `first_name` (character varying)
- `last_name` (character varying)
- `middle_name` (character varying)
- `full_name` (character varying)
- `phone` (character varying)
- `rating` (numeric)
- `work_status` (character varying)
- `hire_date` (date)
- `fire_date` (date)
- `is_selfemployed` (boolean)
- `car_id` (character varying)
- `car_brand` (character varying)
- `car_model` (character varying)
- `car_color` (character varying)
- `car_number` (character varying)
- `car_callsign` (character varying)
- `car_normalized_number` (character varying)
- `license_number` (character varying)
- `license_country` (character varying)
- `license_expiration_date` (date)
- `license_issue_date` (date)
- `license_normalized_number` (character varying)
- `account_balance` (numeric)
- `account_balance_limit` (numeric)
- `account_id` (character varying)
- `current_status` (character varying)
- `status_updated_at` (timestamp without time zone)
- `account_type` (character varying)
- `account_number` (character varying)
- `recipient_name` (character varying)
- `document_type` (character varying)
- `document_number` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.fraud_drivers`

- `id` (integer)
- `contractor_id` (character varying)
- `first_name` (character varying)
- `last_name` (character varying)
- `normalized_number` (character varying)
- `created_date` (date)
- `count_completed` (integer)
- `phone` (character varying)
- `balance` (numeric)
- `has_account` (boolean)
- `account_type` (character varying)
- `account_number` (character varying)
- `recipient_name` (character varying)
- `document_type` (character varying)
- `document_number` (character varying)
- `payout_unlinked` (boolean)
- `payout_unlinked_at` (timestamp without time zone)
- `created_at` (timestamp without time zone)

### `public.module_ct_cabinet_drivers`

- `id` (integer)
- `driver_id` (character varying)
- `driver_nombre` (character varying)
- `driver_apellido` (character varying)
- `driver_placa` (character varying)
- `driver_phone` (character varying)
- `park_name` (character varying)
- `park_id` (character varying)
- `status` (character varying)
- `last_active_date` (character varying)
- `segment` (character varying)
- `stage` (character varying)
- `license` (character varying)
- `viajes_0_7` (boolean)
- `viajes_8_14` (boolean)
- `orders` (integer)
- `conexion` (character varying)
- `hire_date` (character varying)
- `origen` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_ct_scout_drivers`

- `id` (integer)
- `scout_id` (integer)
- `scout_name` (character varying)
- `driver_name` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_driver_closes`

- `id` (bigint)
- `driver_id` (character varying)
- `fecha` (date)
- `user_id` (bigint)
- `gnv_m3` (character varying)
- `gnv_soles` (numeric)
- `gasolina_galones` (character varying)
- `gasolina_soles` (numeric)
- `liquida_efectivo` (numeric)
- `liquida_yape` (numeric)
- `otros_gastos` (numeric)
- `otros_gastos_descripcion` (text)
- `total_ingresos` (numeric)
- `total_gastos` (numeric)
- `resta` (numeric)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `user_id_modificado` (bigint)
- `calculated_shift_ids` (character varying)
- `odometro_inicial` (integer)
- `odometro_final` (integer)
- `diferencia_odometro` (integer)
- `placa` (character varying)

### `public.module_leads_drivers`

- `id` (integer)
- `first_name` (character varying)
- `last_name` (character varying)
- `license_number` (character varying)
- `phone_number` (character varying)
- `contact_notes` (text)
- `reactivation_status` (character varying)
- `agent_id` (integer)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `campaign_id` (integer)
- `is_archived` (boolean)
- `assigned_to` (integer)
- `assigned_at` (timestamp without time zone)
- `status_category` (character varying)
- `status_detail` (character varying)
- `closed_at` (timestamp without time zone)
- `last_status_change_at` (timestamp without time zone)
- `activation_stage` (character varying)
- `activation_status_reason` (text)
- `activation_last_check_at` (timestamp without time zone)
- `activation_owner_bot_id` (integer)
- `registration_status` (character varying)
- `trip_count` (integer)
- `debt_amount` (numeric)
- `yego_partner_confirmed` (boolean)
- `inbox_id` (integer)
- `deleted_by_user_id` (integer)
- `is_deleted` (boolean)
- `deleted_at` (timestamp without time zone)

### `public.module_rapidin_drivers`

- `id` (uuid)
- `dni` (character varying)
- `country` (character varying)
- `first_name` (character varying)
- `last_name` (character varying)
- `phone` (character varying)
- `email` (character varying)
- `yego_premium` (boolean)
- `cycle` (integer)
- `credit_line` (numeric)
- `completed_trips` (integer)
- `acceptance_rate` (numeric)
- `active` (boolean)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `external_driver_id` (character varying)
- `park_id` (character varying)
- `license` (character varying)

### `public.parks`

- `id` (character varying)
- `name` (character varying)
- `city` (character varying)
- `created_at` (timestamp without time zone)

### `public.scout_liq_cutoff_driver_lines`

- `id` (integer)
- `cutoff_run_id` (integer)
- `scout_id` (integer)
- `driver_id` (character varying)
- `hire_date` (date)
- `origin` (character varying)
- `trips_7d` (integer)
- `trips_14d` (integer)
- `is_converted_5trips_7d` (boolean)
- `eligible` (boolean)
- `blocked_reason` (text)
- `already_paid` (boolean)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `trips_0_7_count` (integer)
- `trips_8_14_count` (integer)
- `trips_0_14_count` (integer)
- `total_orders` (integer)
- `legacy_viajes_0_7_flag` (boolean)
- `legacy_viajes_8_14_flag` (boolean)
- `source_quality_status` (character varying)
- `source_warning` (text)
- `line_status` (character varying)
- `payment_rule` (character varying)
- `activated_flag` (boolean)
- `is_converted_5trips_14d` (boolean)
- `driver_lifecycle_status` (character varying)
- `payment_status` (character varying)
- `payout_eligible_flag` (boolean)
- `calculated_amount` (numeric)

### `public.scout_liq_driver_assignments`

- `id` (integer)
- `driver_id` (character varying)
- `scout_id` (integer)
- `origin` (character varying)
- `assigned_at` (timestamp without time zone)
- `hire_date` (date)
- `notes` (text)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `status` (character varying)
- `source_hire_date_raw` (character varying)
- `source_origin` (character varying)
- `assigned_by` (character varying)
- `source_file` (character varying)
- `source_sheet` (character varying)
- `source_row` (integer)
- `import_batch_id` (integer)
- `license_raw` (character varying)

### `public.trips_driver_total`

- `driver_id` (character varying)
- `name_driver` (character varying)
- `park_id` (character varying)
- `trips_total_2025` (bigint)
- `trips_total_2026` (bigint)
- `total` (bigint)

## Fuentes de pago/saldo/bono/banco

### `ops.partner_payment_rules`

- `id` (integer)
- `origin_tag` (character varying)
- `window_days` (integer)
- `milestone_trips` (integer)
- `amount` (numeric)
- `currency` (character varying)
- `valid_from` (date)
- `valid_to` (date)
- `is_active` (boolean)
- `notes` (text)
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)

### `ops.scout_liquidation_ledger`

- `id` (bigint)
- `payment_item_key` (text)
- `scout_id` (integer)
- `person_key` (uuid)
- `driver_id` (text)
- `lead_origin` (text)
- `milestone_type` (text)
- `milestone_value` (integer)
- `rule_id` (integer)
- `payable_date` (date)
- `achieved_date` (date)
- `amount` (numeric)
- `currency` (text)
- `paid_at` (timestamp with time zone)
- `paid_by` (text)
- `payment_ref` (text)
- `notes` (text)
- `created_at` (timestamp with time zone)

### `ops.scout_payment_rules`

- `id` (integer)
- `origin_tag` (character varying)
- `window_days` (integer)
- `milestone_trips` (integer)
- `amount` (numeric)
- `currency` (character varying)
- `valid_from` (date)
- `valid_to` (date)
- `is_active` (boolean)
- `notes` (text)
- `created_at` (timestamp with time zone)
- `updated_at` (timestamp with time zone)
- `milestone_type` (text)
- `milestone_value` (integer)

### `ops.yango_payment_status_ledger`

- `id` (bigint)
- `snapshot_at` (timestamp with time zone)
- `source_table` (text)
- `source_pk` (text)
- `pay_date` (date)
- `pay_time` (time without time zone)
- `raw_driver_name` (text)
- `driver_name_normalized` (text)
- `milestone_type` (text)
- `milestone_value` (integer)
- `is_paid` (boolean)
- `paid_flag_source` (text)
- `driver_id` (text)
- `person_key` (uuid)
- `match_rule` (text)
- `match_confidence` (text)
- `payment_key` (text)
- `state_hash` (text)
- `created_at` (timestamp with time zone)

### `public.module_bonus_thresholds`

- `id` (bigint)
- `min_trips` (integer)
- `bonus_amount` (numeric)
- `effective_from` (date)
- `updated_by` (bigint)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_ct_cabinet_payments`

- `id` (integer)
- `date` (date)
- `time` (time without time zone)
- `scout_id` (integer)
- `driver` (character varying)
- `trip_1` (boolean)
- `trip_5` (boolean)
- `trip_25` (boolean)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)
- `driver_id` (character varying)
- `person_key` (uuid)

### `public.module_payment_percentages`

- `id` (bigint)
- `min_validated_trips` (integer)
- `percentage` (double precision)
- `effective_from` (date)
- `updated_by` (bigint)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_rapidin_auto_payment_log`

- `id` (uuid)
- `loan_id` (uuid)
- `installment_id` (uuid)
- `driver_id` (uuid)
- `external_driver_id` (character varying)
- `driver_first_name` (character varying)
- `driver_last_name` (character varying)
- `flota` (character varying)
- `amount_to_charge` (numeric)
- `amount_charged` (numeric)
- `installment_number` (integer)
- `status` (character varying)
- `reason` (text)
- `balance_at_attempt` (numeric)
- `payment_id` (uuid)
- `created_at` (timestamp without time zone)

### `public.module_rapidin_payment_installments`

- `id` (uuid)
- `payment_id` (uuid)
- `installment_id` (uuid)
- `applied_amount` (numeric)
- `created_at` (timestamp without time zone)

### `public.module_rapidin_payment_vouchers`

- `id` (uuid)
- `loan_id` (uuid)
- `driver_id` (uuid)
- `amount` (numeric)
- `payment_date` (date)
- `file_name` (character varying)
- `file_path` (character varying)
- `observations` (text)
- `status` (character varying)
- `reviewed_by` (uuid)
- `reviewed_at` (timestamp without time zone)
- `rejection_reason` (text)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_rapidin_payments`

- `id` (uuid)
- `loan_id` (uuid)
- `amount` (numeric)
- `payment_date` (date)
- `payment_method` (character varying)
- `observations` (text)
- `registered_by` (uuid)
- `created_at` (timestamp without time zone)
- `voucher_id` (uuid)

### `public.module_rrhh_payroll_details`

- `id` (text)
- `payroll_id` (text)
- `user_id` (text)
- `base_salary` (double precision)
- `overtime_pay` (double precision)
- `bonuses` (double precision)
- `gross_salary` (double precision)
- `afp_deduction` (double precision)
- `onp_deduction` (double precision)
- `tax_deduction` (double precision)
- `other_deductions` (double precision)
- `essalud_contribution` (double precision)
- `net_salary` (double precision)
- `worked_days` (integer)
- `notes` (text)
- `created_at` (timestamp without time zone)

### `public.module_rrhh_payrolls`

- `id` (text)
- `month` (integer)
- `year` (integer)
- `status` (text)
- `notes` (text)
- `processed_at` (timestamp without time zone)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.module_rrhh_vacation_balances`

- `id` (text)
- `user_id` (text)
- `year` (integer)
- `earned_days` (double precision)
- `used_days` (double precision)
- `pending_days` (double precision)
- `available_days` (double precision)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.payment_details`

- `id` (integer)
- `driver_id` (character varying)
- `park_id` (character varying)
- `bank_name` (character varying)
- `account_number` (character varying)
- `account_type` (character varying)
- `recipient_name` (character varying)
- `document_type` (character varying)
- `document_number` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.scout_liq_manual_payments`

- `id` (integer)
- `cutoff_run_id` (integer)
- `scout_id` (integer)
- `supervisor_id` (integer)
- `driver_id` (character varying)
- `driver_license_raw` (character varying)
- `payment_scheme_id` (integer)
- `payment_rule` (character varying)
- `amount` (numeric)
- `currency` (character varying)
- `reason` (text)
- `status` (character varying)
- `approved_by` (character varying)
- `approved_at` (timestamp without time zone)
- `paid_history_id` (integer)
- `created_by` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.scout_liq_scout_bonuses`

- `id` (integer)
- `cutoff_run_id` (integer)
- `scout_id` (integer)
- `bonus_type` (character varying)
- `amount` (numeric)
- `currency` (character varying)
- `reason` (text)
- `status` (character varying)
- `approved_by` (character varying)
- `approved_at` (timestamp without time zone)
- `paid_history_id` (integer)
- `created_by` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

### `public.scout_payment_config`

- `id` (bigint)
- `milestone_type` (integer)
- `amount_scout` (numeric)
- `payment_days` (integer)
- `is_active` (boolean)
- `created_at` (timestamp without time zone)
- `last_updated` (timestamp without time zone)
- `min_registrations_required` (integer)
- `min_connection_seconds` (integer)

### `public.scout_payment_instances`

- `id` (bigint)
- `scout_id` (character varying)
- `driver_id` (character varying)
- `milestone_type` (integer)
- `milestone_instance_id` (bigint)
- `amount` (numeric)
- `registration_date` (date)
- `milestone_fulfillment_date` (timestamp without time zone)
- `eligibility_verified` (boolean)
- `eligibility_reason` (text)
- `status` (character varying)
- `payment_id` (bigint)
- `created_at` (timestamp without time zone)
- `last_updated` (timestamp without time zone)

### `public.scout_payments`

- `id` (bigint)
- `scout_id` (character varying)
- `payment_period_start` (date)
- `payment_period_end` (date)
- `total_amount` (numeric)
- `transactions_count` (integer)
- `status` (character varying)
- `paid_at` (timestamp without time zone)
- `created_at` (timestamp without time zone)
- `last_updated` (timestamp without time zone)
- `instance_ids` (jsonb)

### `public.yango_payment_config`

- `id` (bigint)
- `milestone_type` (integer)
- `amount_yango` (numeric)
- `period_days` (integer)
- `is_active` (boolean)
- `created_at` (timestamp without time zone)
- `last_updated` (timestamp without time zone)

## Muestras de datos

### `public.trips_2026`

```json
{
  "id": "3719df6e8fd41e78bb775685ee6a3030",
  "condicion": "Cancelado",
  "codigo_pedido": "16526595",
  "conductor_id": "fbf13558221f422e898a1720f5332c7e",
  "conductor_nombre": "Herrera Ponce Carlos Christiam",
  "vehiculo_placa": "0d9676d799a3444fa2b1a987bde9a599",
  "vehiculo_modelo": "Kia Rio АРМ524",
  "fecha_inicio_viaje": "2026-04-26 02:56:44",
  "fecha_finalizacion": "2026-04-26 02:52:45",
  "motivo_cancelacion": "Viaje cancelado por el cliente",
  "direccion": "Avenida Alameda de la Molina Vieja, 221, Distrital La Molina -> Calle los Eucaliptos, 337, Distrital San Isidro",
  "tipo_servicio": "Económico",
  "distancia_km": "None",
  "precio_yango_pro": "None",
  "efectivo": "None",
  "tarjeta": "None",
  "pago_corporativo": "None",
  "propina": "None",
  "promocion": "None",
  "bonificaciones": "None",
  "comision_servicio": "None",
  "comision_empresa_asociada": "None",
  "otros_pagos": "None",
  "pagos_viajes_flota": "None",
  "park_id": "08e20910d81d42658d4334d3f6d10ac0"
}
```

### `public.trips_2025`

```json
{
  "id": "ce8078dc9a75c30398edd6877a1a04ba",
  "condicion": "Cancelado",
  "codigo_pedido": "25993453",
  "conductor_id": "15c35a39c0254649b3a696aa6544080e",
  "conductor_nombre": "Aguirre John",
  "vehiculo_placa": "f1194a300ea17521cb29c0f5b09d3795",
  "vehiculo_modelo": "Nissan March НЕМ582",
  "fecha_inicio_viaje": "2025-04-29 20:41:20",
  "fecha_finalizacion": "2025-04-29 20:38:13",
  "motivo_cancelacion": "El conducto rechazó la solicitud de viaje",
  "direccion": "Carrera 40, 41-91, Municipio de Santiago de Cali, Comuna 16, Antonio Nariño -> Autocentro Capri, Avenida Alfonso Bonilla Aragon, Municipio de Santiago de Cali",
  "tipo_servicio": "Económico",
  "distancia_km": "None",
  "precio_yango_pro": "None",
  "efectivo": "None",
  "tarjeta": "None",
  "pago_corporativo": "None",
  "propina": "None",
  "promocion": "None",
  "bonificaciones": "None",
  "comision_servicio": "None",
  "comision_empresa_asociada": "None",
  "otros_pagos": "None",
  "pagos_viajes_flota": "None",
  "park_id": "05b1c831e66f41a9a87f5f3fa0a186ae"
}
```

### `public.trips_all`

```json
{
  "id": "b03b1bb623d325e2bee51d876c0b7cfb",
  "condicion": "Cancelado",
  "codigo_pedido": "27705",
  "conductor_id": "512a6cc639c542e5ae6d7313b98bd4ae",
  "conductor_nombre": "Niño Garcia Andres Felipe",
  "vehiculo_placa": "eda415a8aa1406106558f6b8f4f0d5e8",
  "vehiculo_modelo": "Bajaj Moto VЕУ60F",
  "fecha_inicio_viaje": "2025-01-31 23:12:58",
  "fecha_finalizacion": "2025-01-31 23:05:09",
  "motivo_cancelacion": "El conducto rechazó la solicitud de viaje",
  "direccion": "Filo, Cabecera del llano, Bucaramanga, Colombia -> Santa Coloma, Cra. 28a, 193110, Floridablanca, Colombia",
  "tipo_servicio": "Standard",
  "distancia_km": "None",
  "precio_yango_pro": "None",
  "efectivo": "None",
  "tarjeta": "None",
  "pago_corporativo": "None",
  "propina": "None",
  "promocion": "None",
  "bonificaciones": "None",
  "comision_servicio": "None",
  "comision_empresa_asociada": "None",
  "otros_pagos": "None",
  "pagos_viajes_flota": "None",
  "park_id": "96f5a1e493b6484e88d7fc2e3bb8cbdb"
}
```

## Fuente canónica recomendada para MVP

**NO-GO: No se encontro fuente con driver_id + fecha + estado.**

## Capacidades disponibles

- payment_method: no
- amount: SI
- pickup lat/lng: no
- distance/duration: no
- bonus source: SI
- balance source: SI
- bank source: SI

## Limitaciones

- Sin fuente de saldo/PLAC confirmada en tablas base
- Sin fuente de cuenta bancaria confirmada en tablas base
- Sin fuente directa de bonos/referidos en tablas base

## Decision

**GO** — existe al menos una fuente con driver_id + fecha + estado.
