# OV2-A.2 — YANGO FLEET API STAGING DESIGN

> **Fase:** OV2-A.2 — Data Ingestion & Staging Design  
> **Fecha:** 2026-06-04  
> **Dependencia:** OV2-A.1 — Source Certification Matrix  
> **Fuente:** Yango Fleet API (`https://fleet-api.yango.tech`)  
> **Propósito:** Diseñar el modelo de staging (RAW) para la ingesta de datos desde Yango Fleet API hacia Control Tower, respetando el pipeline RAW → MV → SERVING → UI

---

## 1. RESUMEN EJECUTIVO

Este documento define la capa de staging (`staging.*`) para la ingesta de datos desde Yango Fleet API hacia Control Tower. Se diseñan **cinco tablas** en el esquema `staging` que cubren:

| Tabla | Endpoint fuente | Grain | Propósito |
|-------|----------------|-------|-----------|
| `yango_api_order_raw` | POST `/v1/parks/orders/list` | order × fetch | Órdenes raw con payload completo |
| `yango_api_transaction_raw` | POST `/v2/parks/transactions/list` | transaction × fetch | Transacciones financieras raw |
| `yango_api_driver_day_raw` | Orders + Supply Hours (agregado) | driver × park × date | Métricas diarias agregadas por conductor |
| `yango_api_probe_run` | N/A (metadatos de ejecución) | probe run | Auditoría de ejecuciones de ingesta |
| `yango_api_revenue_candidate_audit` | Orders + Transactions (análisis) | field × park × date × run | Auditoría de campos de revenue descubiertos |

El diseño es **read-only** en esta fase: no se crean tablas, no se escribe código, no se insertan datos. Es un artefacto de diseño previo a la implementación.

---

## 2. ARQUITECTURA DEL PIPELINE

Todos los datos ingeridos desde Yango Fleet API deben seguir el pipeline estándar de Control Tower:

```
RAW (staging.*)  →  MV (materialized views)  →  SERVING (serving.*)  →  UI (Omniview V2)
```

### 2.1 Capas

| Capa | Esquema | Descripción | Ejemplo |
|------|---------|-------------|---------|
| **RAW** | `staging.*` | Datos crudos tal como llegan de la API. Se preserva `raw_payload` (jsonb) completo. Una fila por entidad por fetch. | `staging.yango_api_order_raw` |
| **MV** | `mv.*` | Vistas materializadas que normalizan, desduplican y unifican datos de RAW. Una fila por entidad lógica. | `mv.yango_api_order_dedup` (futuro) |
| **SERVING** | `serving.*` | Tablas de hechos optimizadas para consultas de UI. Agregadas, indexadas, con facts precalculados. | `serving.yango_api_daily_metrics` (futuro) |
| **UI** | Omniview V2 | Consume de SERVING exclusivamente. Nunca consulta RAW directamente. | Dashboard de revenue reconciliation |

### 2.2 Flujo de Datos

```
┌──────────────────────────────────────────────────────────────────────┐
│                        YANGO FLEET API                               │
│                                                                      │
│  POST /v1/parks/orders/list         POST /v2/parks/transactions/list │
│  GET /v2/parks/contractors/supply-hours                              │
│  GET /v1/parks/driver-profiles/list                                  │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    RAW LAYER (staging.*)                              │
│                                                                      │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐   │
│  │ yango_api_order_raw      │  │ yango_api_transaction_raw       │   │
│  │ (order × fetch)          │  │ (transaction × fetch)           │   │
│  └────────────┬─────────────┘  └───────────────┬─────────────────┘   │
│               │                                │                     │
│               └────────────┬───────────────────┘                     │
│                            │                                         │
│                            ▼                                         │
│               ┌──────────────────────────┐                           │
│               │ yango_api_driver_day_raw │  ◄── Aggregation layer    │
│               │ (driver × park × date)   │                           │
│               └────────────┬─────────────┘                           │
│                            │                                         │
│  ┌──────────────────────────┐  ┌─────────────────────────────────┐   │
│  │ yango_api_probe_run      │  │ yango_api_revenue_candidate     │   │
│  │ (audit de ejecuciones)   │  │ _audit (audit de revenue)       │   │
│  └──────────────────────────┘  └─────────────────────────────────┘   │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    MV LAYER (mv.*) — FUTURO                          │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ mv.yango_api_order_dedup       (order × 1, latest fetch)       │  │
│  │ mv.yango_api_transaction_dedup (transaction × 1, latest fetch) │  │
│  │ mv.yango_api_driver_day_dedup  (driver × park × date × 1)      │  │
│  │ mv.yango_api_revenue_summary   (park × date, aggregated)       │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  SERVING LAYER (serving.*) — FUTURO                  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ serving.yango_daily_metrics       (park × date, pre-aggregated) │  │
│  │ serving.yango_revenue_facts       (revenue facts for UI)       │  │
│  │ serving.yango_reconciliation_log  (API vs CT deltas)           │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────┬──────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   UI LAYER — Omniview V2                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Revenue Reconciliation Dashboard                                │  │
│  │ Driver Activity vs Revenue View                                 │  │
│  │ API Freshness & Trust Sensor                                    │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.3 Notas sobre el Flujo

- **`driver_day_raw`** es una tabla de agregación que se alimenta de `order_raw` (para trips y revenue) y de `supply-hours` (para supply_seconds). Es el punto de consolidación diario.
- **`probe_run`** registra cada ejecución del pipeline. Todas las filas en RAW referencian el `run_id` vía `fetch_run_id` o `compute_run_id`.
- **`revenue_candidate_audit`** es una tabla de análisis que se alimenta del discovery de campos de revenue durante probes. No es operacional, es de auditoría.

---

## 3. DISEÑO DE TABLAS

### 3.1 `staging.yango_api_order_raw`

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Almacenar órdenes raw desde `POST /v1/parks/orders/list` |
| **Grain** | Una fila por order por fetch (idempotente vía `order_id + fetched_at`) |
| **Clave lógica** | `(order_id, park_id, fetched_at_date)` |
| **Endpoint fuente** | `POST /v1/parks/orders/list` |
| **Volumen estimado** | ~300-800 órdenes/día por park (Lima); crece con más parks |

#### Columnas

| Columna | Tipo | Constraints | Descripción |
|---------|------|-------------|-------------|
| `id` | `bigserial` | `NOT NULL` | Surrogate PK autoincremental |
| `order_id` | `text` | `NOT NULL` | Order ID de la API (`id`) |
| `park_id` | `text` | `NOT NULL` | Park ID de Yango |
| `order_status` | `text` | | Estado: `complete`, `cancelled`, etc. |
| `price` | `numeric(12,2)` | | `price.final_cost` convertido desde string |
| `payment_method` | `text` | | Método de pago |
| `category` | `text` | | Categoría de vehículo (economy, comfort, etc.) |
| `driver_profile_id` | `text` | | ID del conductor (`driver_profile.id`) |
| `car_id` | `text` | | ID del vehículo (`car.id`) |
| `booked_at` | `timestamptz` | | Timestamp de booking |
| `ended_at` | `timestamptz` | | Timestamp de finalización del viaje |
| `created_at` | `timestamptz` | | Timestamp de creación de la orden en Yango |
| `mileage` | `numeric(8,2)` | | Kilometraje del viaje |
| `provider` | `text` | | Proveedor (ej. `yango`) |
| `raw_payload_hash` | `text` | | SHA-256 del `raw_payload` completo para dedup |
| `raw_payload` | `jsonb` | | Payload JSON completo de la respuesta de API |
| `fetched_at` | `timestamptz` | `NOT NULL DEFAULT now()` | Timestamp de cuándo se obtuvo de la API |
| `fetched_at_date` | `date` | `NOT NULL` | Derivado de `fetched_at` para particionamiento |
| `endpoint` | `text` | | Endpoint llamado: `/v1/parks/orders/list` |
| `schema_version` | `text` | | Versión del schema al momento de la ingesta (ej. `2026-06-04`) |
| `fetch_run_id` | `text` | | FK lógica a `yango_api_probe_run.run_id` |

#### Índices sugeridos

```sql
-- Clave lógica compuesta
CREATE UNIQUE INDEX idx_yango_order_raw_lookup
  ON staging.yango_api_order_raw (order_id, park_id, fetched_at_date);

-- Búsqueda por fecha de fetch
CREATE INDEX idx_yango_order_raw_fetched_at
  ON staging.yango_api_order_raw (fetched_at);

-- Búsqueda por driver + fecha
CREATE INDEX idx_yango_order_raw_driver_date
  ON staging.yango_api_order_raw (driver_profile_id, booked_at);

-- Dedup hash
CREATE INDEX idx_yango_order_raw_hash
  ON staging.yango_api_order_raw (raw_payload_hash);

-- FK lógica a probe_run
CREATE INDEX idx_yango_order_raw_run_id
  ON staging.yango_api_order_raw (fetch_run_id);
```

---

### 3.2 `staging.yango_api_transaction_raw`

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Almacenar transacciones raw desde `POST /v2/parks/transactions/list` |
| **Grain** | Una fila por transaction por fetch |
| **Clave lógica** | `(transaction_id, park_id, fetched_at_date)` |
| **Endpoint fuente** | `POST /v2/parks/transactions/list` |
| **Volumen estimado** | Variable; típicamente 2-5 transacciones por order completada |

#### Columnas

| Columna | Tipo | Constraints | Descripción |
|---------|------|-------------|-------------|
| `id` | `bigserial` | `NOT NULL` | Surrogate PK autoincremental |
| `transaction_id` | `text` | `NOT NULL` | Transaction ID de la API |
| `park_id` | `text` | `NOT NULL` | Park ID de Yango |
| `category_id` | `text` | | ID de la categoría de transacción |
| `category_name` | `text` | | Nombre descriptivo de la categoría |
| `category_group_id` | `text` | | Grupo: `partner_rides`, `platform_fees`, `partner_fees`, etc. |
| `amount` | `numeric(12,2)` | | Monto convertido desde string |
| `currency_code` | `text` | | Código de moneda (ej. `PEN`, `USD`) |
| `description` | `text` | | Descripción textual de la transacción |
| `driver_profile_id` | `text` | | ID del conductor |
| `order_id` | `text` | | FK lógica a `yango_api_order_raw.order_id` |
| `event_at` | `timestamptz` | | Timestamp del evento de la transacción |
| `created_by_identity` | `text` | | Origen: `dispatcher`, `fleet-api`, `platform`, `tech-support` |
| `is_affecting_driver_balance` | `boolean` | | Indica si la transacción afecta el balance del conductor |
| `raw_payload_hash` | `text` | | SHA-256 del `raw_payload` completo para dedup |
| `raw_payload` | `jsonb` | | Payload JSON completo de la respuesta de API |
| `fetched_at` | `timestamptz` | `NOT NULL DEFAULT now()` | Timestamp de cuándo se obtuvo de la API |
| `fetched_at_date` | `date` | `NOT NULL` | Derivado de `fetched_at` para particionamiento |
| `endpoint` | `text` | | Endpoint llamado: `/v2/parks/transactions/list` |
| `schema_version` | `text` | | Versión del schema al momento de la ingesta |
| `fetch_run_id` | `text` | | FK lógica a `yango_api_probe_run.run_id` |

#### Índices sugeridos

```sql
CREATE UNIQUE INDEX idx_yango_transaction_raw_lookup
  ON staging.yango_api_transaction_raw (transaction_id, park_id, fetched_at_date);

CREATE INDEX idx_yango_transaction_raw_order_id
  ON staging.yango_api_transaction_raw (order_id);

CREATE INDEX idx_yango_transaction_raw_driver_date
  ON staging.yango_api_transaction_raw (driver_profile_id, event_at);

CREATE INDEX idx_yango_transaction_raw_category
  ON staging.yango_api_transaction_raw (category_name, category_group_id);

CREATE INDEX idx_yango_transaction_raw_hash
  ON staging.yango_api_transaction_raw (raw_payload_hash);

CREATE INDEX idx_yango_transaction_raw_run_id
  ON staging.yango_api_transaction_raw (fetch_run_id);
```

#### Notas sobre Transaction Categories

Las categorías de transacción son críticas para el análisis de revenue:

| `category_group_id` | Significado | Relevancia para revenue |
|---------------------|-------------|--------------------------|
| `partner_rides` | Ingresos por viajes | **Revenue primario** — GMV de viajes |
| `platform_fees` | Comisiones de plataforma | **Revenue neto** — lo que Yango retiene |
| `partner_fees` | Comisiones del partner (flota) | **Revenue del partner** — margen de la flota |
| `adjustments` | Ajustes y correcciones | **Revenue ajustado** — puede ser positivo o negativo |
| `tips` | Propinas | Revenue auxiliar, típicamente del conductor |
| `other` | Otros conceptos | Revisar caso por caso |

El mapeo de `category_group_id` a conceptos de revenue debe definirse en la fase de implementación del MV layer.

---

### 3.3 `staging.yango_api_driver_day_raw`

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Métricas diarias agregadas por conductor derivadas de orders + supply-hours |
| **Grain** | `(driver_profile_id, park_id, date)` |
| **Clave lógica** | `(driver_profile_id, park_id, date)` |
| **Fuentes** | `yango_api_order_raw` + API supply-hours + API driver-profiles |
| **Volumen estimado** | ~50-200 conductores activos/día por park |

#### Columnas

| Columna | Tipo | Constraints | Descripción |
|---------|------|-------------|-------------|
| `id` | `bigserial` | `NOT NULL` | Surrogate PK autoincremental |
| `driver_profile_id` | `text` | `NOT NULL` | ID del conductor |
| `park_id` | `text` | `NOT NULL` | Park ID de Yango |
| `date` | `date` | `NOT NULL` | Día de actividad (derivado de `booked_at` o `ended_at`) |
| `trips_completed` | `integer` | `DEFAULT 0` | Cantidad de órdenes con `status = 'complete'` |
| `revenue_gmv` | `numeric(12,2)` | | Suma de `price.final_cost` de órdenes completadas |
| `supply_seconds` | `integer` | | Segundos de supply (`supply_duration_seconds` desde API) |
| `supply_hours` | `numeric(6,2)` | | `supply_seconds / 3600.0` derivado |
| `is_working` | `boolean` | | `true` si `work_status = 'working'` |
| `work_status` | `text` | | `working`, `not_working`, etc. desde driver-profiles |
| `fetched_at` | `timestamptz` | `DEFAULT now()` | Timestamp de la agregación |
| `source_endpoints` | `text[]` | | Endpoints que contribuyeron: `{'/v1/parks/orders/list', '/v2/parks/contractors/supply-hours'}` |
| `compute_run_id` | `text` | | FK lógica a `yango_api_probe_run.run_id` |

#### Índices sugeridos

```sql
CREATE UNIQUE INDEX idx_yango_driver_day_lookup
  ON staging.yango_api_driver_day_raw (driver_profile_id, park_id, date);

CREATE INDEX idx_yango_driver_day_date
  ON staging.yango_api_driver_day_raw (date);

CREATE INDEX idx_yango_driver_day_park_date
  ON staging.yango_api_driver_day_raw (park_id, date);

CREATE INDEX idx_yango_driver_day_working
  ON staging.yango_api_driver_day_raw (is_working, date)
  WHERE is_working = true;

CREATE INDEX idx_yango_driver_day_run_id
  ON staging.yango_api_driver_day_raw (compute_run_id);
```

#### Lógica de Agregación

`driver_day_raw` se calcula durante cada probe run:

1. **Desde `order_raw`**: Agrupar por `(driver_profile_id, park_id, DATE(booked_at))`, contar `status = 'complete'` como `trips_completed`, sumar `price` como `revenue_gmv`.
2. **Desde supply-hours API**: Obtener `supply_duration_seconds` por conductor por día (requiere llamadas per-driver; ver limitaciones en OV2-A.1 §4.2).
3. **Desde driver-profiles API**: Obtener `work_status` por conductor.
4. **Merge**: Unir los tres resultados por `(driver_profile_id, park_id, date)`.
5. **Upsert**: Insertar en `driver_day_raw` con `ON CONFLICT (driver_profile_id, park_id, date) DO UPDATE` para reflejar la última ejecución.

> **Nota de escala**: La dependencia de supply-hours per-driver es un cuello de botella conocido (ver OV2-A.1 §3.1, latencia). Para probes diarios con >100 conductores activos, considerar ventanas de tiempo acotadas o ejecución asíncrona con rate limiting.

---

### 3.4 `staging.yango_api_probe_run`

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Registrar cada ejecución del pipeline de ingesta/reconciliación |
| **Grain** | Una fila por probe run |
| **Clave lógica** | `run_id` |

#### Columnas

| Columna | Tipo | Constraints | Descripción |
|---------|------|-------------|-------------|
| `run_id` | `text` | `NOT NULL, PK` | Identificador único de la ejecución (UUID o timestamp-based) |
| `run_type` | `text` | `NOT NULL` | Tipo: `probe`, `reconciliation`, `scale_probe`, `revenue_discovery` |
| `park_id` | `text` | | Park ID objetivo; `NULL` si es multi-park |
| `date_from` | `date` | | Inicio de la ventana de datos consultada |
| `date_to` | `date` | | Fin de la ventana de datos consultada |
| `started_at` | `timestamptz` | `DEFAULT now()` | Inicio de la ejecución |
| `finished_at` | `timestamptz` | | Fin de la ejecución |
| `status` | `text` | `DEFAULT 'running'` | `running`, `completed`, `failed`, `partial` |
| `endpoints_called` | `text[]` | | Lista de endpoints invocados en esta ejecución |
| `total_api_calls` | `integer` | `DEFAULT 0` | Número total de llamadas HTTP realizadas |
| `success_count` | `integer` | `DEFAULT 0` | Llamadas exitosas (2xx) |
| `error_count` | `integer` | `DEFAULT 0` | Llamadas con error (4xx, 5xx) |
| `rate_limit_count` | `integer` | `DEFAULT 0` | Llamadas que recibieron 429 (rate limit) |
| `records_fetched` | `integer` | `DEFAULT 0` | Total de registros obtenidos en esta ejecución |
| `output_dir` | `text` | | Directorio de outputs (ej. `backend/exports/audits/growth_api/2026-06-04/`) |
| `error_message` | `text` | | Mensaje de error si `status = 'failed'` o `'partial'` |
| `dry_run` | `boolean` | `DEFAULT false` | Si fue ejecución de prueba sin escritura |

#### Índices sugeridos

```sql
CREATE INDEX idx_yango_probe_run_status
  ON staging.yango_api_probe_run (status);

CREATE INDEX idx_yango_probe_run_park_date
  ON staging.yango_api_probe_run (park_id, date_from, date_to);

CREATE INDEX idx_yango_probe_run_type
  ON staging.yango_api_probe_run (run_type, started_at);

CREATE INDEX idx_yango_probe_run_started
  ON staging.yango_api_probe_run (started_at DESC);
```

#### Estados de Probe Run

```
running ──► completed
    │
    ├──► failed ──► (re-run genera nuevo run_id)
    │
    └──► partial ──► completed (re-run complementario)
```

---

### 3.5 `staging.yango_api_revenue_candidate_audit`

| Propiedad | Valor |
|-----------|-------|
| **Propósito** | Registrar campos de revenue descubiertos durante análisis de la API para trazabilidad |
| **Grain** | `(field_path, park_id, date, discovery_run_id)` |
| **Clave lógica** | `audit_id` (surrogate) |

#### Columnas

| Columna | Tipo | Constraints | Descripción |
|---------|------|-------------|-------------|
| `audit_id` | `serial` | `NOT NULL, PK` | Surrogate PK autoincremental |
| `field_path` | `text` | `NOT NULL` | JSON path al campo, ej. `orders[].price` |
| `endpoint` | `text` | | Endpoint donde se encontró el campo |
| `park_id` | `text` | | Park ID de los datos analizados |
| `date` | `date` | | Fecha de los datos analizados |
| `classification` | `text` | | Clasificación del campo: `REVENUE_YEGO_CANDIDATE`, `GMV_ONLY`, `METADATA_ONLY`, `UNKNOWN` |
| `confidence` | `text` | | Nivel de confianza: `HIGH`, `MEDIUM`, `LOW` |
| `value_sum` | `numeric(16,2)` | | Suma total del campo en la muestra |
| `value_count` | `integer` | | Cantidad de valores no-null |
| `value_avg` | `numeric(12,2)` | | Promedio del campo |
| `value_min` | `numeric(12,2)` | | Valor mínimo |
| `value_max` | `numeric(12,2)` | | Valor máximo |
| `null_count` | `integer` | | Cantidad de valores null |
| `currency_code` | `text` | | Moneda del campo si es importe |
| `delta_vs_ct_revenue` | `numeric(14,2)` | | Diferencia contra el revenue calculado por CT |
| `delta_pct` | `numeric(6,2)` | | Diferencia porcentual vs CT |
| `discovery_run_id` | `text` | | FK lógica a `yango_api_probe_run.run_id` |
| `notes` | `text` | | Notas del analista o del proceso de discovery |
| `validated_at` | `timestamptz` | | Timestamp de validación manual (si aplica) |

#### Índices sugeridos

```sql
CREATE UNIQUE INDEX idx_yango_revenue_audit_lookup
  ON staging.yango_api_revenue_candidate_audit (field_path, park_id, date, discovery_run_id);

CREATE INDEX idx_yango_revenue_audit_classification
  ON staging.yango_api_revenue_candidate_audit (classification, confidence);

CREATE INDEX idx_yango_revenue_audit_delta
  ON staging.yango_api_revenue_candidate_audit (delta_pct)
  WHERE delta_pct IS NOT NULL;

CREATE INDEX idx_yango_revenue_audit_run
  ON staging.yango_api_revenue_candidate_audit (discovery_run_id);
```

#### Clasificaciones de Revenue

| Clasificación | Criterio | Acción |
|---------------|----------|--------|
| `REVENUE_YEGO_CANDIDATE` | Campo numérico que correlaciona con revenue de CT (>0.8) y tiene sentido de negocio | Candidato a integrar en MV de revenue |
| `GMV_ONLY` | Representa GMV (Gross Merchandise Value) pero no revenue neto | Usar como sanity check, no como fuente primaria |
| `METADATA_ONLY` | Campo no financiero (IDs, timestamps, strings) | Ignorar para revenue |
| `UNKNOWN` | Campo numérico sin correlación clara con métricas conocidas | Requiere análisis manual; revisar en próxima iteración |
| `DUPLICATE_CT` | Campo que replica exactamente un valor ya existente en CT | Redundante; no integrar |

---

## 4. PRINCIPIOS DE DISEÑO

### 4.1 Idempotencia

Todas las inserciones en tablas RAW deben ser idempotentes. El mecanismo principal es:

- **`ON CONFLICT DO NOTHING`**: Para inserciones donde no se desea actualizar registros existentes (ej. re-runs de probe sobre la misma ventana).
- **`ON CONFLICT ... DO UPDATE`**: Para `driver_day_raw` donde cada nueva ejecución debe reflejar los datos más recientes de la agregación.

La clave lógica compuesta garantiza que un mismo registro no se duplique incluso si el probe se ejecuta múltiples veces.

```sql
-- Ejemplo para order_raw
INSERT INTO staging.yango_api_order_raw (order_id, park_id, ...)
VALUES (...)
ON CONFLICT (order_id, park_id, fetched_at_date) DO NOTHING;

-- Ejemplo para driver_day_raw (agregación — siempre reflejar último cómputo)
INSERT INTO staging.yango_api_driver_day_raw (driver_profile_id, park_id, date, ...)
VALUES (...)
ON CONFLICT (driver_profile_id, park_id, date) DO UPDATE SET
  trips_completed = EXCLUDED.trips_completed,
  revenue_gmv = EXCLUDED.revenue_gmv,
  fetched_at = EXCLUDED.fetched_at,
  compute_run_id = EXCLUDED.compute_run_id;
```

### 4.2 Preservación del Payload Raw

- **`raw_payload` (jsonb)**: Cada fila en `order_raw` y `transaction_raw` preserva el payload JSON completo retornado por la API. Esto permite:
  - Auditoría forense ante discrepancias
  - Re-procesamiento sin re-consultar la API
  - Evolución del schema sin pérdida de datos históricos
  - Debugging de transformaciones en MV layer

- **Costo de almacenamiento**: ~2-5 KB por fila. Para 10,000 órdenes/mes: ~20-50 MB/mes. Aceptable.

### 4.3 Deduplicación por Hash

- **`raw_payload_hash`**: SHA-256 del `raw_payload` completo. Permite detectar si un payload idéntico ya fue procesado sin necesidad de comparar el JSON completo.
- **Uso**: Antes de insertar, verificar si `raw_payload_hash` ya existe para el mismo `order_id` + `park_id`. Si existe, skip (el contenido no cambió).
- **Limitación**: Si la API retorna el mismo dato con timestamps internos diferentes (ej. `updated_at`), el hash será diferente aunque los datos de negocio sean idénticos. Para esos casos, se debe implementar un hash semántico (solo campos de negocio) en el MV layer.

### 4.4 Seguridad de Secretos

- **Nunca loggear `raw_payload`** a consola, archivos de log, o outputs de error.
- **Credenciales siempre enmascaradas**: `X-API-Key`, `X-Client-ID`, y cualquier header sensible deben ser reemplazados por `***MASKED***` en logs y en `error_message` de `probe_run`.
- **`schema_version` y `endpoint`**: Tags que permiten rastrear qué versión del schema se usó para cada fila, facilitando migraciones y detección de breaking changes en la API.
- **`.env` como única fuente de credenciales**: Nunca hardcodear credenciales en código ni en tablas.

### 4.5 Evolución del Schema

- **`schema_version`**: Cada fila en RAW registra la versión del schema al momento de la ingesta (ej. `2026-06-04`). Cuando la API de Yango evolucione:
  - Filas existentes conservan su `schema_version` original y su `raw_payload` intacto.
  - Nuevas filas se ingieren con la nueva `schema_version`.
  - Las vistas en MV layer pueden adaptarse para leer múltiples versiones de schema.
  - Se puede realizar backfill de `raw_payload` desde versiones antiguas si es necesario.

- **Estrategia de migración**:
  1. Detectar cambio de schema (probe detecta campos nuevos/eliminados).
  2. Actualizar `schema_version` en la configuración de ingesta.
  3. Crear nueva versión de MV si el cambio es incompatible.
  4. Mantener retrocompatibilidad en SERVING layer para la UI.

### 4.6 Estrategia de Particionamiento (Futuro)

Para escala (múltiples parks, largos períodos de retención):

- **Particionar por `park_id` + `fetched_at_date`** (o `date` en `driver_day_raw`).
- Esto permite:
  - Purgar datos antiguos por park sin bloquear la tabla completa.
  - Consultas eficientes por park + rango de fechas.
  - Particionamiento independiente por park para multi-tenancy.

```sql
-- Ejemplo conceptual (no ejecutar en esta fase)
CREATE TABLE staging.yango_api_order_raw (
  ...
) PARTITION BY LIST (park_id);

CREATE TABLE staging.yango_api_order_raw_park_08e20910
  PARTITION OF staging.yango_api_order_raw
  FOR VALUES IN ('08e20910d81d42658d4334d3f6d10ac0');
```

---

## 5. RELACIONES ENTRE TABLAS

```
┌────────────────────────────┐
│  yango_api_probe_run       │
│  (run_id) ──── PK          │
└────────┬───────────────────┘
         │
         │ fetch_run_id / compute_run_id / discovery_run_id
         │
    ┌────┴──────────────────────────────────────────┐
    │                                                │
    ▼                                                ▼
┌────────────────────────────┐  ┌─────────────────────────────────┐
│  yango_api_order_raw       │  │  yango_api_revenue_candidate    │
│  (fetch_run_id ── FK)     │  │  _audit (discovery_run_id ── FK)│
└────────┬───────────────────┘  └─────────────────────────────────┘
         │
         │ order_id
         │
         ▼
┌────────────────────────────┐
│  yango_api_transaction_raw │
│  (order_id ── FK lógica)   │
└────────────────────────────┘

┌────────────────────────────┐         ┌────────────────────────────┐
│  yango_api_order_raw       │         │  supply-hours API          │
│  (driver_profile_id, date) │         │  (driver_profile_id, date) │
└────────┬───────────────────┘         └────────┬───────────────────┘
         │                                      │
         └──────────────┬───────────────────────┘
                        │ (aggregation JOIN)
                        ▼
           ┌────────────────────────────┐
           │  yango_api_driver_day_raw  │
           │  (compute_run_id ── FK)    │
           └────────────────────────────┘
```

> **Nota**: Las FKs son lógicas (no declarativas como constraints en DB). Se implementan vía joins en el MV layer y se validan en el pipeline de ingesta.

---

## 6. CHECKLIST DE IMPLEMENTACIÓN

> **Estado:** Ningún ítem está completado. Este documento es puramente de diseño.

| # | Tarea | Dependencia | Estado |
|---|-------|-------------|--------|
| 1 | Aprobación de governance para crear tablas `staging.*` | Este documento | [ ] Pendiente |
| 2 | Crear migraciones (`backend/alembic/versions/`) para las 5 tablas | #1 | [ ] Pendiente |
| 3 | Implementar repository layer (`backend/repositories/yango_api_staging.py`) | #2 | [ ] Pendiente |
| 4 | Implementar loader service (`backend/services/yango_api_loader.py`) | #3 | [ ] Pendiente |
| 5 | Implementar lógica de dedup vía hash + ON CONFLICT | #4 | [ ] Pendiente |
| 6 | Integrar con probe run audit (`yango_api_probe_run`) | #4, #5 | [ ] Pendiente |
| 7 | Implementar agregación `driver_day_raw` desde orders + supply-hours | #4 | [ ] Pendiente |
| 8 | Implementar discovery de revenue candidates y auditoría | #4 | [ ] Pendiente |
| 9 | Configurar scheduler para probes periódicos (Airflow/cron) | #6 | [ ] Pendiente |
| 10 | Crear MV layer (`mv.yango_api_*`) para dedup y normalización | #4 | [ ] Pendiente |
| 11 | Crear SERVING layer (`serving.yango_*`) para UI | #10 | [ ] Pendiente |
| 12 | Integrar con Omniview V2 UI (revenue reconciliation dashboard) | #11 | [ ] Pendiente |
| 13 | Pruebas de escala con datos reales (>30 días, múltiples parks) | #7, #8 | [ ] Pendiente |
| 14 | Documentar mapeo `category_group_id` → conceptos de revenue CT | #8 | [ ] Pendiente |
| 15 | Implementar particionamiento si el volumen lo requiere | #13 | [ ] Pendiente |

---

## 7. GOVERNANCE

### 7.1 Reglas de Control Tower

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| No modifica Omniview V1 | `PASS` | Diseño de tablas nuevas en `staging.*`; sin alterar esquemas existentes |
| No modifica UI productiva | `PASS` | Las tablas RAW no son consultadas por ninguna UI; solo SERVING alimenta UI |
| No reemplaza fuentes actuales | `PASS` | Las tablas `staging.*` son adicionales; `trips_2026` sigue siendo fuente canónica |
| Read-only / design | `PASS` | Este documento no crea tablas, no ejecuta DDL, no inserta datos |
| Control Foundation scope | `PASS` | Diseño acotado a la ingesta de Yango Fleet API para Omniview V2 |
| Credenciales enmascaradas | `PASS` | No se exponen credenciales en este documento ni en el diseño de tablas |
| Sin inserción en tablas productivas | `PASS` | Las tablas diseñadas son `staging.*` (RAW); no se tocan `serving.*` ni `mv.*` existentes |
| RAW → MV → SERVING → UI | `PASS` | Pipeline documentado en §2; cada capa tiene propósito definido |
| Sin writes en esta fase | `PASS` | Documento de diseño; implementación en fases posteriores (OV2-B/OV2-C) |

### 7.2 Supuestos y Restricciones

| Item | Descripción |
|------|-------------|
| **Parks soportados** | Inicialmente solo Lima (`08e20910d81d42658d4334d3f6d10ac0`); escalable a multi-park |
| **Endpoint de transacciones** | `POST /v2/parks/transactions/list` — asume disponibilidad y estructura de response según documentación de Yango |
| **Rate limiting** | Respetar rate limits de la API (429 → backoff). `probe_run` registra `rate_limit_count` |
| **Supply-hours per-driver** | Limitación conocida (OV2-A.1 §4.2); considerar caché o ejecución asíncrona |
| **Retención de RAW** | 90 días por defecto en `staging.*`; configurable por park. MV y SERVING tienen retención mayor |
| **Idioma de datos** | Los datos de Yango vienen en inglés/ruso; no se traducen en RAW; la traducción ocurre en SERVING si es necesario |

---

## 8. RIESGOS TÉCNICOS

| ID | Riesgo | Severidad | Mitigación |
|----|--------|-----------|------------|
| R-A2-1 | API `/v2/parks/transactions/list` no disponible o cambia de schema | `HIGH` | Validar disponibilidad en probe inicial; `schema_version` permite tracking de cambios |
| R-A2-2 | `raw_payload` ocupa demasiado storage a largo plazo | `MEDIUM` | Política de retención (90 días en RAW); compresión nativa de jsonb en PostgreSQL |
| R-A2-3 | Hash-based dedup falla con timestamps internos cambiantes | `MEDIUM` | Implementar hash semántico en MV layer (solo campos de negocio) |
| R-A2-4 | Agregación `driver_day_raw` lenta con supply-hours per-driver | `HIGH` | Paralelizar llamadas con rate limiting; evaluar caché de 24h |
| R-A2-5 | Discrepancia revenue API vs CT > tolerancia aceptable | `HIGH` | No activar alarmas automáticas hasta validar mapeo; `revenue_candidate_audit` captura deltas para análisis |
| R-A2-6 | Multi-park escala mal sin particionamiento | `LOW` (corto plazo) | Particionamiento diseñado en §4.6; activar cuando se agregue un segundo park |

---

## 9. FIRMA

| Campo | Valor |
|-------|-------|
| **Diseñado por** | OV2-A.2 Yango API Staging Design |
| **Fecha** | 2026-06-04 |
| **Próxima revisión** | Al iniciar OV2-B (implementación de tablas RAW) |
| **Estado** | `DESIGN` — pendiente de aprobación de governance |
| **Depende de** | OV2-A.1 Source Certification Matrix (clasificación de la API como fuente válida) |
| **Precede a** | OV2-B.1 — Implementación de staging tables + loader service |

---

## APÉNDICE A: Resumen de Endpoints Mapeados

| Endpoint Yango | Método | Tabla RAW | Campos clave |
|----------------|--------|-----------|--------------|
| `/v1/parks/orders/list` | `POST` | `yango_api_order_raw` | `order_id`, `price.final_cost`, `driver_profile.id`, `status`, `booked_at`, `ended_at` |
| `/v2/parks/transactions/list` | `POST` | `yango_api_transaction_raw` | `transaction_id`, `category_group_id`, `amount`, `order_id`, `is_affecting_driver_balance` |
| `/v2/parks/contractors/supply-hours` | `GET` | `yango_api_driver_day_raw` (vía agregación) | `supply_duration_seconds` |
| `/v1/parks/driver-profiles/list` | `POST` | `yango_api_driver_day_raw` (vía agregación) | `work_status`, `driver_profile.id` |

## APÉNDICE B: Nomenclatura de Tablas

| Prefijo | Significado | Ejemplo |
|---------|-------------|---------|
| `yango_api_` | Datos provenientes de Yango Fleet API | `yango_api_order_raw` |
| `_raw` | Tabla en capa RAW (staging) | `yango_api_order_raw` |
| `_dedup` | Vista/tabla desduplicada en MV | `yango_api_order_dedup` (futuro) |
| `_audit` | Tabla de auditoría/trazabilidad | `yango_api_revenue_candidate_audit` |
| `_probe_run` | Registro de ejecución de pipeline | `yango_api_probe_run` |
