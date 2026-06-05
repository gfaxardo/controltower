# OV2-B.0 — YANGO FLEET API RAW LANDING LAYER

> **Fase:** OV2-B.0 — Raw Landing  
> **Fecha:** 2026-06-05  
> **Schema:** `raw_yango`  
> **Propósito:** Crear la primera capa paralela para ingestar datos de Yango Fleet API como fuente candidata futura de Omniview V2, sin reemplazar `trips_2025`/`trips_2026`

---

## 1. OBJETIVO

Crear la primera capa paralela (`raw_yango` schema) para ingestar datos de Yango Fleet API como fuente candidata futura de Omniview V2, sin reemplazar `trips_2025`/`trips_2026`.

El propósito exclusivo de esta fase es el **raw landing**: persistir payloads JSON completos tal como los devuelve la API, con hashing para deduplicación y trazabilidad completa de cada ingesta. No se construyen materialized views, serving facts, ni componentes de UI.

---

## 2. ALCANCE

| Incluido | Excluido |
|----------|----------|
| Raw tables en schema `raw_yango` | Materialized views |
| Pipeline de ingesta incremental diaria | Serving facts |
| Deduplicación por hash de payload | UI / dashboards OV2 |
| Registro de credenciales (sin keys en DB) | Reemplazo de `trips_2025`/`trips_2026` |
| Auditoría de errores de ingesta | Agregaciones para reporting |
| Script de reconciliación vs CT | Promoción a canonical |

**Esta fase es puramente RAW TABLES.**

---

## 3. ENDPOINTS INCLUIDOS INICIALMENTE

| Endpoint | Método | Grain | Paginación | Tabla destino |
|----------|--------|-------|------------|---------------|
| `/v1/parks/orders/list` | POST | order | Cursor-based (`next_cursor`) | `raw_yango.orders_raw` |
| `/v2/parks/transactions/list` | POST | transaction | Cursor-based (`next_cursor`) | `raw_yango.transactions_raw` |
| `/v1/parks/driver-profiles/list` | POST | driver_profile | Offset-based (`limit`/`offset`/`total`) | `raw_yango.driver_profiles_raw` |

---

## 4. ENDPOINTS EXCLUIDOS (POR AHORA)

| Endpoint | Razón de exclusión |
|----------|---------------------|
| Cars creation/update (write endpoints) | Write endpoints — no aplican a raw landing read-only |
| Car-bindings | Write endpoint |
| Driver-profiles creation (write endpoints) | Write endpoint |
| `/v2/parks/contractors/supply-hours` | Per-driver, demasiado costoso a escala (>1 HTTP call por conductor por día) |
| `/v1/parks/contractors/blocked-balance` | Per-driver, no necesario para fase raw landing |

---

## 5. MODELO DE DATOS RAW

### 5.1 Schema: `raw_yango`

Schema dedicado para todos los artefactos de ingesta raw de Yango Fleet API. Independiente de `ops`, `public`, `staging`, y `growth`.

### 5.2 `raw_yango.api_park_credentials_registry`

Registro de credenciales por park. Las API keys **nunca** se almacenan en base de datos — solo se referencia la variable de entorno que las contiene.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `credential_id` | `TEXT NOT NULL UNIQUE` | Identificador único de credencial |
| `park_id` | `TEXT NOT NULL` | Park ID de Yango Fleet API |
| `country` | `TEXT` | País del park |
| `city` | `TEXT` | Ciudad del park |
| `fleet_name` | `TEXT` | Nombre descriptivo de la flota |
| `env_var_name` | `TEXT NOT NULL` | Nombre de la variable en `.env` (NUNCA el valor) |
| `api_base_url` | `TEXT NOT NULL` | URL base de la API |
| `is_active` | `BOOLEAN NOT NULL DEFAULT true` | Si el park está activo para ingesta |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Fecha de creación del registro |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Fecha de última actualización |
| `notes` | `TEXT` | Notas adicionales |

### 5.3 `raw_yango.api_ingestion_run`

Registro de cada ejecución de ingesta, con métricas de rendimiento.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `run_id` | `TEXT NOT NULL UNIQUE` | Identificador único de la ejecución |
| `endpoint_group` | `TEXT NOT NULL` | `orders`, `transactions`, `driver_profiles`, `all` |
| `park_id` | `TEXT NOT NULL` | Park ingerido |
| `date_from` | `DATE NOT NULL` | Fecha inicio de la ventana |
| `date_to` | `DATE NOT NULL` | Fecha fin de la ventana |
| `status` | `TEXT NOT NULL DEFAULT 'running'` | `running`, `completed`, `failed`, `partial` |
| `started_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de inicio |
| `finished_at` | `TIMESTAMPTZ` | Timestamp de finalización |
| `records_fetched` | `INTEGER DEFAULT 0` | Total de registros devueltos por la API |
| `records_inserted` | `INTEGER DEFAULT 0` | Registros nuevos insertados |
| `records_updated` | `INTEGER DEFAULT 0` | Registros cuyo payload cambió |
| `record_skips` | `INTEGER DEFAULT 0` | Registros duplicados ignorados |
| `error_count` | `INTEGER DEFAULT 0` | Total de errores durante la ejecución |
| `warning_count` | `INTEGER DEFAULT 0` | Total de warnings |
| `max_concurrency` | `INTEGER DEFAULT 3` | Concurrencia máxima usada |
| `source` | `TEXT DEFAULT 'yango_fleet_api'` | Fuente de datos |
| `script_version` | `TEXT` | Versión del script de ingesta |
| `notes` | `TEXT` | Notas adicionales |

**Índice:** `ON (park_id, date_from)`

### 5.4 `raw_yango.orders_raw`

Payloads completos del endpoint `/v1/parks/orders/list`.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `park_id` | `TEXT NOT NULL` | Park ID |
| `order_id` | `TEXT NOT NULL` | Order ID de Yango |
| `order_short_id` | `INTEGER` | Short order ID |
| `order_status` | `TEXT` | Estado de la orden |
| `order_created_at` | `TIMESTAMPTZ` | Timestamp de creación |
| `order_booked_at` | `TIMESTAMPTZ` | Timestamp de booking |
| `order_ended_at` | `TIMESTAMPTZ` | Timestamp de finalización |
| `driver_profile_id` | `TEXT` | Driver ID |
| `car_id` | `TEXT` | Vehicle ID |
| `category` | `TEXT` | Categoría de servicio |
| `payment_method` | `TEXT` | Método de pago |
| `provider` | `TEXT` | Proveedor |
| `price` | `NUMERIC` | Precio (GMV) |
| `mileage` | `NUMERIC` | Kilometraje |
| `currency_code` | `TEXT DEFAULT 'PEN'` | Código de moneda |
| `raw_payload` | `JSONB NOT NULL` | Payload JSON completo de la API |
| `raw_payload_hash` | `TEXT NOT NULL` | Hash SHA-256 del payload para deduplicación |
| `api_fetched_at` | `TIMESTAMPTZ NOT NULL` | Timestamp de cuando se obtuvo de la API |
| `api_run_id` | `TEXT` | FK lógica a `api_ingestion_run.run_id` |
| `source_endpoint` | `TEXT` | Endpoint de origen |
| `schema_version` | `TEXT` | Versión del schema de respuesta |
| `inserted_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de inserción en DB |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de última actualización |

**UNIQUE:** `uq_yango_orders_raw (park_id, order_id, raw_payload_hash)`

**Índices:**
- `ix_yango_orders_park_date (park_id, api_fetched_at)`
- `ix_yango_orders_driver (driver_profile_id)`
- `ix_yango_orders_run (api_run_id)`

### 5.5 `raw_yango.transactions_raw`

Payloads completos del endpoint `/v2/parks/transactions/list`.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `park_id` | `TEXT NOT NULL` | Park ID |
| `transaction_id` | `TEXT NOT NULL` | Transaction ID |
| `event_at` | `TIMESTAMPTZ` | Timestamp del evento |
| `category_id` | `TEXT` | ID de categoría |
| `category_name` | `TEXT` | Nombre de categoría |
| `group_id` | `TEXT` | ID de grupo de categoría |
| `amount` | `NUMERIC` | Monto de la transacción |
| `currency_code` | `TEXT DEFAULT 'PEN'` | Código de moneda |
| `description` | `TEXT` | Descripción |
| `driver_profile_id` | `TEXT` | Driver ID |
| `order_id` | `TEXT` | Order ID vinculado |
| `created_by_identity` | `TEXT` | Identidad que creó la transacción |
| `raw_payload` | `JSONB NOT NULL` | Payload JSON completo de la API |
| `raw_payload_hash` | `TEXT NOT NULL` | Hash SHA-256 del payload para deduplicación |
| `api_fetched_at` | `TIMESTAMPTZ NOT NULL` | Timestamp de cuando se obtuvo de la API |
| `api_run_id` | `TEXT` | FK lógica a `api_ingestion_run.run_id` |
| `source_endpoint` | `TEXT` | Endpoint de origen |
| `schema_version` | `TEXT` | Versión del schema de respuesta |
| `inserted_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de inserción en DB |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de última actualización |

**UNIQUE:** `uq_yango_txn_raw (park_id, transaction_id, raw_payload_hash)`

**Índices:**
- `ix_yango_txn_park_date (park_id, api_fetched_at)`
- `ix_yango_txn_category (category_name)`
- `ix_yango_txn_group (group_id)`
- `ix_yango_txn_order (order_id)`
- `ix_yango_txn_driver (driver_profile_id)`
- `ix_yango_txn_run (api_run_id)`

### 5.6 `raw_yango.driver_profiles_raw`

Payloads completos del endpoint `/v1/parks/driver-profiles/list`.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `park_id` | `TEXT NOT NULL` | Park ID |
| `driver_profile_id` | `TEXT NOT NULL` | Driver profile ID |
| `work_status` | `TEXT` | Estado de trabajo (`working` / `not_working`) |
| `car_id` | `TEXT` | Vehicle ID asignado |
| `car_category` | `TEXT` | Categoría del vehículo |
| `has_contract_issue` | `BOOLEAN` | Flag de problema de contrato |
| `raw_payload` | `JSONB NOT NULL` | Payload JSON completo de la API |
| `raw_payload_hash` | `TEXT NOT NULL` | Hash SHA-256 del payload para deduplicación |
| `api_fetched_at` | `TIMESTAMPTZ NOT NULL` | Timestamp de cuando se obtuvo de la API |
| `api_run_id` | `TEXT` | FK lógica a `api_ingestion_run.run_id` |
| `source_endpoint` | `TEXT` | Endpoint de origen |
| `schema_version` | `TEXT` | Versión del schema de respuesta |
| `inserted_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de inserción en DB |
| `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp de última actualización |

**UNIQUE:** `uq_yango_drivers_raw (park_id, driver_profile_id, raw_payload_hash)`

**Índices:**
- `ix_yango_drivers_park (park_id)`
- `ix_yango_drivers_work_status (work_status)`

### 5.7 `raw_yango.ingestion_errors`

Registro de cada error de llamada a la API.

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `run_id` | `TEXT` | FK lógica a `api_ingestion_run.run_id` |
| `park_id` | `TEXT NOT NULL` | Park ID |
| `endpoint_group` | `TEXT` | Grupo de endpoint |
| `endpoint_url_sanitized` | `TEXT` | URL del endpoint (sin credenciales) |
| `request_params_json` | `JSONB` | Parámetros de la request |
| `status_code` | `INTEGER` | HTTP status code |
| `error_type` | `TEXT` | Tipo de error |
| `error_message_sanitized` | `TEXT` | Mensaje de error (sin credenciales) |
| `retry_count` | `INTEGER DEFAULT 0` | Número de reintentos |
| `occurred_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Timestamp del error |

**Índice:** `ix_yango_errors_run (run_id)`

---

## 6. MODELO DE CREDENCIALES POR PARK

### 6.1 Principio de seguridad

- Las credenciales se almacenan en `.env` y **nunca** en la base de datos.
- `raw_yango.api_park_credentials_registry` referencia el nombre de la variable de entorno (`env_var_name`), no el valor.
- El código de ingesta lee `env_var_name` del registry, luego obtiene el valor real desde `os.environ`.

### 6.2 Ejemplo de configuración

**.env:**
```
YANGO_LIMA_API_KEY=x-api-key-xxxx
YANGO_LIMA_CLIENT_ID=client-id-xxxx
YANGO_LIMA_PARK_ID=08e20910d81d42658d4334d3f6d10ac0
```

**api_park_credentials_registry:**
| credential_id | park_id | env_var_name | api_base_url | is_active |
|---------------|---------|-------------|-------------|-----------|
| `yango_lima_park` | `08e20910d81d42658d4334d3f6d10ac0` | `YANGO_LIMA` | `https://fleet-api.yango.tech` | `true` |

### 6.3 Lookup en tiempo de ingesta

1. Leer `api_park_credentials_registry` filtrando `is_active = true`
2. Para cada park, construir credenciales desde `os.environ[f"{env_var_name}_API_KEY"]`, `os.environ[f"{env_var_name}_CLIENT_ID"]`, `os.environ[f"{env_var_name}_PARK_ID"]`
3. Si alguna variable no existe → loggear warning y saltar park

---

## 7. MODELO DE EJECUCIÓN INCREMENTAL

### 7.1 Frecuencia

- Ingesta **diaria** por park por endpoint.
- Ventana típica: `date_from = ayer`, `date_to = ayer` (1 día).

### 7.2 Paginación

| Endpoint | Estrategia | Parámetros |
|----------|-----------|------------|
| Orders | Cursor-based | `cursor` + `limit` (max 500) |
| Transactions | Cursor-based | `cursor` + `limit` (max 1000) |
| Driver Profiles | Offset-based | `offset` + `limit` (max 1000) |

### 7.3 Flujo de ejecución

1. Crear registro en `api_ingestion_run` con `status = 'running'`
2. Para cada park activo:
   a. Resolver credenciales desde `env_var_name`
   b. Para cada endpoint group solicitado:
      - Paginar hasta agotar resultados
      - Insertar en tabla raw con `ON CONFLICT DO NOTHING`
      - Registrar errores en `ingestion_errors`
   c. Actualizar contadores en `api_ingestion_run`
3. Marcar `api_ingestion_run` como `completed`, `partial`, o `failed`

### 7.4 Concurrencia

- `max_concurrency = 3` por defecto (configurable).
- Rate limit guard: si se detecta 429, backoff mandatorio de 3 segundos para todas las goroutines activas.

---

## 8. MODELO DE DEDUPLICACIÓN

### 8.1 Estrategia

Cada tabla raw tiene una constraint `UNIQUE` compuesta que previene duplicados:

- `raw_yango.orders_raw`: `UNIQUE(park_id, order_id, raw_payload_hash)`
- `raw_yango.transactions_raw`: `UNIQUE(park_id, transaction_id, raw_payload_hash)`
- `raw_yango.driver_profiles_raw`: `UNIQUE(park_id, driver_profile_id, raw_payload_hash)`

### 8.2 Comportamiento

- `INSERT ... ON CONFLICT DO NOTHING` para payloads que no han cambiado.
- Si el mismo `order_id` aparece con un `raw_payload_hash` diferente → se inserta una nueva fila (el payload cambió). Esto permite trazabilidad de cambios en el tiempo.
- `records_inserted`: filas nuevas insertadas.
- `record_skips`: filas ignoradas por `ON CONFLICT DO NOTHING` (payload idéntico).

### 8.3 Hash

- `raw_payload_hash = SHA256(raw_payload::text)` calculado antes de insertar.
- Garantiza que payloads idénticos produzcan el mismo hash.

---

## 9. MODELO DE AUDITORÍA

### 9.1 `raw_yango.ingestion_errors`

Cada llamada fallida a la API se registra con:

- `run_id`: vinculado a la ejecución que la originó
- `park_id`: park que falló
- `endpoint_url_sanitized`: URL sin credenciales (nunca se persisten API keys)
- `request_params_json`: parámetros enviados
- `status_code`: código HTTP de respuesta
- `error_type`: clasificación del error (`RATE_LIMIT`, `AUTH`, `SERVER_ERROR`, `TIMEOUT`, `PARSE_ERROR`)
- `error_message_sanitized`: mensaje sin información sensible
- `retry_count`: cuántas veces se reintentó

### 9.2 Trazabilidad end-to-end

```
api_ingestion_run.run_id
  → orders_raw.api_run_id
  → transactions_raw.api_run_id
  → driver_profiles_raw.api_run_id
  → ingestion_errors.run_id
```

Cada registro raw es trazable a la ejecución que lo produjo.

---

## 10. MODELO DE ERRORES

### 10.1 Política de reintentos

| Código | Clasificación | Comportamiento |
|--------|--------------|----------------|
| `429` | `RATE_LIMIT` | Backoff 3s mandatorio, reintentar hasta 2 veces |
| `401`, `403` | `AUTH` | Loggear error, **saltar park completo** (no reintentar) |
| `5xx` | `SERVER_ERROR` | Exponential backoff: 1s, 2s, 4s. Máximo 3 reintentos |
| Timeout | `TIMEOUT` | Reintentar hasta 2 veces con mismo timeout (20s default) |
| `4xx` (otros) | `CLIENT_ERROR` | Loggear error, no reintentar, continuar con siguiente página |

### 10.2 Degradación graceful

- Si un park falla con `401`/`403`, se salta y se continúa con los demás parks.
- Si un endpoint group falla completamente, se marca `status = 'partial'` en `api_ingestion_run`.
- Si todos los parks/endpoints fallan, se marca `status = 'failed'`.

---

## 11. MODELO DE RECONCILIACIÓN

### 11.1 Script

`backend/scripts/reconcile_yango_raw_vs_ct.py`

### 11.2 Fuentes comparadas

| Fuente A | Fuente B | Comparación |
|----------|----------|-------------|
| `raw_yango.orders_raw` | `ops.real_business_slice_day_fact` | Trips por día, revenue, drivers activos |
| `raw_yango.transactions_raw` | `ops.real_business_slice_day_fact` | Revenue via `partner_rides` + `platform_fees` |

### 11.3 Clasificación de resultados

| Clasificación | Condición | Significado |
|---------------|-----------|-------------|
| `MATCH` | Delta = 0% | Las fuentes coinciden exactamente |
| `MINOR_DELTA` | Delta < 5% | Variación aceptable, dentro de tolerancia |
| `MAJOR_DELTA` | Delta 5-20% | Requiere investigación, posible issue de datos |
| `CT_ONLY` | Dato existe en CT pero no en API | Trip registrado en CT que no aparece en Yango API |
| `API_ONLY` | Dato existe en API pero no en CT | Trip en Yango API que no está en `day_fact` |

### 11.4 Output

- Resultados exportados a `backend/exports/audits/yango_raw_reconciliation/`
- Reporte diario con conteo por clasificación
- Alertas automáticas si `MAJOR_DELTA > 5%` del total o `CT_ONLY > 10` trips

---

## 12. GO / NO-GO PARA OV2-B.1

### 12.1 Criterios de GO

| Criterio | Condición |
|----------|-----------|
| Migración | `alembic upgrade head` aplica limpiamente sin errores |
| Dry-run ingesta | El script de ingesta en modo `--dry-run` lista los parks, endpoints, y credenciales correctamente |
| Coverage script | `reconcile_yango_raw_vs_ct.py` ejecuta sin errores de schema |
| Safety rules | Ninguna regla de governance violada |

### 12.2 Criterios de NO-GO

| Criterio | Condición |
|----------|-----------|
| Migración fallida | `alembic upgrade head` produce error de SQL |
| Credenciales faltantes | Alguna variable de entorno requerida no existe en `.env` |
| Safety rule violada | Cualquier regla de la tabla de governance marcada como `FAIL` |
| Schema conflict | El schema `raw_yango` o alguna tabla ya existe con estructura incompatible |

### 12.3 Decisión

- **GO**: Si todos los criterios GO se cumplen y ningún NO-GO se activa → proceder a OV2-B.1 (implementación del script de ingesta).
- **NO-GO**: Si cualquier criterio NO-GO se activa → detener, documentar el bloqueo, y requerir resolución antes de continuar.

---

## 13. GOVERNANCE CHECK

| Regla | Estado |
|-------|--------|
| No modifica Omniview V1 | PASS |
| No modifica UI productiva | PASS |
| No reemplaza fuentes actuales (`trips_2025`/`trips_2026`) | PASS |
| Read-only sobre tablas existentes | PASS |
| Schema independiente (`raw_yango`) | PASS |
| Sin inserción en tablas productivas | PASS |
| Sin modificar serving facts | PASS |
| Credenciales nunca en DB (solo referencia a `.env`) | PASS |
| Errores logueados sin información sensible | PASS |
| Deduplicación por hash (idempotente) | PASS |
| Downgrade limpio (todas las tablas tienen DROP) | PASS |
| Sin dependencia circular con otros schemas | PASS |

---

## 14. DIAGRAMA DE ARQUITECTURA

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YANGO FLEET API                              │
│                   https://fleet-api.yango.tech                       │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐  │
│  │ /v1/parks/       │  │ /v2/parks/       │  │ /v1/parks/        │  │
│  │ orders/list      │  │ transactions/    │  │ driver-profiles/  │  │
│  │                  │  │ list             │  │ list              │  │
│  │ Cursor pag.      │  │ Cursor pag.      │  │ Offset pag.       │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬──────────┘  │
│           │                     │                     │              │
└───────────┼─────────────────────┼─────────────────────┼──────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE (OV2-B.1)                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  api_park_credentials_registry  ←  .env (keys NUNCA en DB)  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Paginación  │  Deduplicación          │  Errores → retry/backoff  │
│  Concurrency │  SHA256(raw_payload)    │  Errores → ingestion_errors│
│              │  ON CONFLICT DO NOTHING │                            │
└─────────────────────────────────────────────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     raw_yango SCHEMA (OV2-B.0)                       │
│                                                                     │
│  ┌────────────────┐  ┌───────────────────┐  ┌────────────────────┐  │
│  │ orders_raw      │  │ transactions_raw  │  │ driver_profiles_   │  │
│  │                 │  │                   │  │ raw                │  │
│  │ UNIQUE(park_id, │  │ UNIQUE(park_id,   │  │                    │  │
│  │  order_id,      │  │  transaction_id,  │  │ UNIQUE(park_id,    │  │
│  │  payload_hash)  │  │  payload_hash)    │  │  driver_profile_id,│  │
│  │                 │  │                   │  │  payload_hash)     │  │
│  └────────┬────────┘  └────────┬──────────┘  └─────────┬──────────┘  │
│           │                    │                        │             │
│  ┌────────┴────────────────────┴────────────────────────┴────────┐  │
│  │                  api_ingestion_run                              │  │
│  │  (run_id, park_id, date_range, status, metrics)                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  ingestion_errors                               │  │
│  │  (run_id, park_id, endpoint, status_code, error, retry_count)  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
            │
            │ (FUTURO: OV2-B.2+)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 FUTURE: MATERIALIZED VIEWS (PENDIENTE)               │
│                                                                     │
│  raw_yango → staging MV (daily aggregates, deduplicated)            │
│            → reconciliation views (API vs CT day_fact)              │
└─────────────────────────────────────────────────────────────────────┘
            │
            │ (FUTURO: OV2-C)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 FUTURE: SERVING FACTS (PENDIENTE)                    │
│                                                                     │
│  MV → serving facts (API-sourced business metrics)                  │
│     → confidence flags                                             │
│     → trust sensors                                                 │
└─────────────────────────────────────────────────────────────────────┘
            │
            │ (FUTURO: OV2-D)
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 FUTURE: UI OV2 (PENDIENTE)                           │
│                                                                     │
│  serving facts → Omniview V2 UI                                    │
│                → Yango-sourced indicators                           │
│                → Reconciliation dashboard                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 15. FIRMA

| Campo | Valor |
|-------|-------|
| **Diseñado por** | OV2-B.0 Raw Landing Architecture |
| **Fecha** | 2026-06-05 |
| **Próxima fase** | OV2-B.1 — Ingestion Pipeline Implementation |
| **Estado** | `PENDIENTE_IMPLEMENTACION` (migration + script de ingesta) |
