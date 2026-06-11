# CF-H2B — YANGO OMNIVIEW RAW LANDING FOUNDATION

> **Fase:** CF-H2B — Yango Omniview Raw Landing Foundation
> **Motor:** Control Foundation
> **Clasificación:** CF_H2B_RAW_LANDING_ARCHITECTURE_READY
> **Fecha:** 2026-06-11
> **Propósito:** Diseñar la migración progresiva de Omniview V2 hacia Yango API como fuente maestra operacional desde 2026-06-01, cubriendo todas las métricas que Omniview necesita o podría necesitar.

---

## 1. EXECUTIVE SUMMARY

Omniview V2 consume actualmente 8 KPIs desde `ops.real_business_slice_*_fact`, alimentados por `public.trips_unified` (CT bridge). Yango Fleet API ya ha sido validada como fuente operacional live para Lima Growth Engine y certificada como `CERTIFIED_REVENUE_AUDIT` para revenue.

Este documento define la arquitectura para **migrar progresivamente Omniview V2 hacia Yango API como fuente maestra** desde 2026-06-01, métrica por métrica, sin romper el pipeline actual ni abrir Diagnostic Engine.

**Principio rector:**
```
NUNCA consultar Yango API en runtime desde UI.
Yango API → RAW → NORMALIZED → SERVING FACTS → UI.
```

**Estrategia de migración:**
- No big-bang. Promoción progresiva por métrica.
- Cada métrica tiene su propio threshold de certificación y `source_badge`.
- Revenue se promueve primero (más validado). Trips/drivers después.
- CT bridge permanece como fallback y fuente pre-corte.
- Omniview V2 recibe datos vía serving facts con `source_badge` trazable.

---

## 2. GOVERNANCE VALIDATION

### 2.1 Reglas de Engine

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| Motor = Control Foundation | **PASS** | CF-H2B pertenece a Control Foundation. |
| No mezclar engines | **PASS** | Sin Diagnostic/Forecast/Suggestion/Decision/Action. |
| Serving-first architecture | **PASS** | RAW → NORMALIZED → SERVING FACTS → UI. Nada en runtime. |
| Deterministic logic first | **PASS** | Todas las métricas son agregaciones SQL determinísticas. |
| Máximo 1 ACTIVE + 1 READY NEXT | **PASS** | OMNI-P0 ACTIVE, CF-H2B READY NEXT. |
| Diagnostic PAUSED | **PASS** | No se activa. |

### 2.2 Reglas de Omniview V2

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| OV2 cerrado (commit 2ab32e9) | **PASS** | OV2_CLOSE_5_RELEASE_COMMITTED |
| No modificar serving facts existentes | **PASS** | Se crean nuevos serving facts en paralelo. |
| No modificar UI productiva | **PASS** | Solo backend. |
| No tocar V1 | **PASS** | V1 intacto. |
| Snapshot-first serving | **PASS** | Nuevos serving facts alimentan snapshots. |

### 2.3 Governance Verdict

**GO for CF-H2B Architecture Design.**

---

## 3. YANGO API ENDPOINT AUDIT — COMPLETE INVENTORY

### 3.1 Clasificación por Utilidad para Omniview

| # | Endpoint | Método | Paginación | Utilidad Omniview | Clasificación |
|---|----------|--------|------------|-------------------|---------------|
| 1 | `/v2/parks/transactions/list` | POST | Cursor, max 1000 | **REVENUE + GMV + COMMISSION** | `CANONICAL_CANDIDATE` |
| 2 | `/v1/parks/orders/list` | POST | Cursor, max 500 | **TRIPS + DRIVERS + GMV + CANCEL** | `CANONICAL_CANDIDATE` |
| 3 | `/v1/parks/driver-profiles/list` | POST | Offset, max 1000 | **DRIVER UNIVERSE + STATE** | `CANONICAL_CANDIDATE` |
| 4 | `/v2/parks/transactions/categories/list` | POST | Sin paginación | **TAXONOMY** | `REFERENCE` |
| 5 | `/v2/parks/orders/transactions/list` | POST | Por order_ids | **PER-ORDER FINANCIALS** | `RECONCILIATION` |
| 6 | `/v2/parks/contractors/supply-hours` | GET | Per-driver | **SUPPLY HOURS** | `CANDIDATE_LIMITED` |
| 7 | `/v1/parks/cars/list` | POST | Offset | **FLEET INVENTORY** | `DIMENSIONAL` |
| 8 | `/v1/parks/contractors/blocked-balance` | GET | Per-driver | **DRIVER BALANCE** | `RECONCILIATION` |
| 9 | `/v1/parks/driver-work-rules` | GET | Sin paginación | **WORK RULES** | `DIMENSIONAL` |
| 10-24 | Resto | Varios | Varios | Write/Not useful | `EXCLUDED` |

### 3.2 Priorización para Raw Landing

| Prioridad | Endpoint | Razón |
|-----------|----------|-------|
| **P0** | `POST /v2/parks/transactions/list` | Revenue canónico. Ya ingerido. |
| **P0** | `POST /v1/parks/orders/list` | Trips, drivers, GMV, cancel rate. Ya ingerido. |
| **P1** | `POST /v1/parks/driver-profiles/list` | Driver universe. Ya ingerido. |
| **P1** | `POST /v2/parks/transactions/categories/list` | Taxonomy. NO almacenado aún. |
| **P2** | `POST /v1/parks/cars/list` | Fleet inventory. NO implementado. |
| **P2** | `POST /v2/parks/orders/transactions/list` | Per-order reconciliation. NO implementado. |
| **P3** | `GET /v2/parks/contractors/supply-hours` | Supply hours. Per-driver bottleneck. Uso limitado. |

### 3.3 Campos Disponibles por Endpoint (Resumen)

#### Orders (`POST /v1/parks/orders/list`)

| Campo API | Tipo | Omniview KPI |
|-----------|------|-------------|
| `id` | string | order_id (join key) |
| `short_id` | integer | referencia |
| `status` | string (`complete`/`cancelled`) | trips_completed, cancel_rate_pct |
| `created_at` | ISO datetime | timestamps |
| `booked_at` | ISO datetime | timestamps |
| `ended_at` | ISO datetime | source_date |
| `provider` | string | dimensional |
| `category` | string | business_slice mapping |
| `payment_method` | string | dimensional |
| `driver_profile.id` | string | active_drivers (unique count) |
| `car.id` | string | fleet |
| `price` | string (fixed-point) | GMV, avg_ticket |
| `mileage` | number | referencia |
| `cancellation_description` | string | cancel reason |
| `amenities`, `events`, `route_points`, `address_from` | objects/arrays | solo raw_payload |

#### Transactions (`POST /v2/parks/transactions/list`)

| Campo API | Tipo | Omniview KPI |
|-----------|------|-------------|
| `id` | string | transaction_id |
| `event_at` | ISO datetime | source_date |
| `category_name` | string | revenue_yango, platform_fee, GMV |
| `amount` | string (fixed-point) | revenue_yango (ABS), GMV (SUM) |
| `currency_code` | string | currency |
| `order_id` | string | join con orders |
| `driver_profile_id` | string | driver attribution |
| `description` | string | referencia |

#### Driver Profiles (`POST /v1/parks/driver-profiles/list`)

| Campo API | Tipo | Omniview KPI |
|-----------|------|-------------|
| `driver_profile.id` | string | driver_id |
| `driver_profile.work_status` | string | driver state |
| `driver_profile.first_name` / `last_name` | string | identity |
| `current_status.status` | string | online/offline/busy |
| `car.id` | string | vehicle binding |
| `car.category` | string | vehicle category |
| `account.balance` | string | driver balance |
| `account.currency` | string | currency |

---

## 4. RAW PAYLOAD STORAGE — QUÉ GUARDAR

### 4.1 Principio

**Todo payload de API se guarda completo en `raw_payload` JSONB.** Esto permite:
- Replay futuro sin re-consultar API
- Auditoría de cambios de schema de API
- Extracción de campos no anticipados
- Reconciliación forense

### 4.2 Tablas Raw Existentes (CONFIRMADAS)

| Tabla | Endpoint | Estado | Migración |
|-------|----------|--------|-----------|
| `raw_yango.orders_raw` | `POST /v1/parks/orders/list` | **ACTIVA** | 181 |
| `raw_yango.transactions_raw` | `POST /v2/parks/transactions/list` | **ACTIVA** | 181 |
| `raw_yango.driver_profiles_raw` | `POST /v1/parks/driver-profiles/list` | **ACTIVA** | 181 |

### 4.3 Tablas Raw Nuevas Propuestas

| Tabla | Endpoint | Justificación |
|-------|----------|---------------|
| `raw_yango.transaction_categories_ref` | `POST /v2/parks/transactions/categories/list` | Sin esto, `category_id` y `group_id` en transactions_raw no tienen taxonomía persistente. Hoy se consulta solo en discovery scripts. |
| `raw_yango.cars_raw` | `POST /v1/parks/cars/list` | Fleet inventory. Útil para dimensional enrichment de orders. Baja prioridad. |
| `raw_yango.supply_hours_raw` | `GET /v2/parks/contractors/supply-hours` | Si se implementa bulk ingestion futura. Por ahora, per-driver = no viable. |

### 4.4 `raw_yango.transaction_categories_ref`

```sql
CREATE TABLE raw_yango.transaction_categories_ref (
    id                  SERIAL PRIMARY KEY,
    park_id             TEXT NOT NULL,
    category_id         TEXT NOT NULL,
    category_name       TEXT NOT NULL,
    group_id            TEXT,
    group_name          TEXT,
    is_affecting_driver_balance BOOLEAN,
    raw_payload         JSONB NOT NULL,
    api_fetched_at      TIMESTAMPTZ NOT NULL,
    inserted_at         TIMESTAMPTZ DEFAULT now(),
    UNIQUE (park_id, category_id)
);
```

**Frecuencia de refresh:** Semanal o ante detección de `category_id` desconocido en transactions_raw.

### 4.5 Campos Faltantes en Tablas Existentes

| Tabla | Campo API | Acción |
|-------|-----------|--------|
| `orders_raw` | `amenities`, `events`, `route_points`, `address_from`, `type`, `driver_work_rule`, `cancellation_description`, `park_details` | Ya en `raw_payload` JSONB. No necesitan columna dedicada. |
| `transactions_raw` | `event_id` | Agregar columna `event_id TEXT` si se requiere para reconciliación. |
| `transactions_raw` | `created_by` (full object) | Ya se extrae `created_by_identity`. Resto en `raw_payload`. |
| `driver_profiles_raw` | `current_status`, `account.balance`, `phone` | Ya en `raw_payload` JSONB. Evaluar flattening si se usan frecuentemente. |

---

## 5. NORMALIZED FACTS — DISEÑO COMPLETO

### 5.1 Arquitectura de Capas

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RAW LAYER (raw_yango)                            │
│                                                                          │
│  orders_raw  │  transactions_raw  │  driver_profiles_raw                 │
│  cars_raw    │  transaction_categories_ref                               │
│  (supply_hours_raw — futuro)                                             │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼ DAILY REFRESH
┌─────────────────────────────────────────────────────────────────────────┐
│                   NORMALIZED LAYER (raw_yango MVs)                       │
│                                                                          │
│  mv_orders_day          → trips, drivers, cancel rate, GMV               │
│  mv_transactions_day    → transactions by category                       │
│  mv_revenue_day          → revenue, platform fees, GMV by payment type   │
│  mv_driver_profiles_snapshot → latest driver state                       │
│  mv_source_coverage_day → coverage per park+day+endpoint                 │
│  mv_driver_activity_day  → [NUEVA] supply/activity si está disponible    │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼ DAILY REFRESH
┌─────────────────────────────────────────────────────────────────────────┐
│                  CANONICAL FACTS (ops)                                    │
│                                                                          │
│  ops.yango_orders_day_fact        → canonical trips/drivers/cancel/GMV   │
│  ops.yango_revenue_day_fact       → canonical revenue/fees               │
│  ops.yango_driver_day_fact        → [NUEVA] driver state/activity        │
│  ops.yango_coverage_day_log       → promotion eligibility per metric     │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼ DAILY REFRESH
┌─────────────────────────────────────────────────────────────────────────┐
│                  SERVING LAYER (ops)                                      │
│                                                                          │
│  ops.omniview_v2_source_canonical_fact  ← unificado con source_badge     │
│  ops.omniview_v2_serving_snapshot       ← ya existe, se amplía           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         UI LAYER                                          │
│                                                                          │
│  Omniview V2 / Vs Proy  ← source_badge visible por celda                 │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 `raw_yango.mv_orders_day` (EXISTENTE — Migración 187/188)

```sql
-- Columnas actuales: park_id, order_date, orders_total, orders_completed,
-- orders_cancelled, unique_drivers, unique_cars, first_order_at, last_order_at,
-- api_records, refreshed_at

-- Propuesta de extensión (nueva migración):
-- Agregar: gmv_total, gmv_cash, gmv_card, orders_by_payment_method,
-- orders_by_category, unique_drivers_working, orders_per_driver_avg
```

### 5.3 `raw_yango.mv_revenue_day` (EXISTENTE — Migración 187→188→190)

Ya tiene las columnas necesarias para revenue canónico:
- `revenue_partner_fee_amount` → YEGO revenue
- `platform_fee_amount` → Yango commission
- `gmv_cash_amount`, `gmv_card_amount` → GMV
- `revenue_per_order`, `revenue_per_partner_fee_txn`
- `revenue_source`, `revenue_confidence`

### 5.4 `raw_yango.mv_driver_activity_day` (NUEVA)

```sql
CREATE MATERIALIZED VIEW raw_yango.mv_driver_activity_day AS
SELECT
    d.park_id,
    d.api_fetched_at::date AS snapshot_date,
    COUNT(*) AS total_profiles,
    COUNT(*) FILTER (WHERE d.work_status = 'working') AS drivers_working,
    COUNT(*) FILTER (WHERE d.work_status = 'not_working') AS drivers_not_working,
    COUNT(*) FILTER (WHERE d.has_contract_issue = true) AS drivers_contract_issue,
    COUNT(DISTINCT d.car_id) AS unique_cars_assigned,
    now() AS refreshed_at
FROM raw_yango.driver_profiles_raw d
WHERE d.api_fetched_at = (
    SELECT MAX(api_fetched_at) FROM raw_yango.driver_profiles_raw
    WHERE park_id = d.park_id
)
GROUP BY d.park_id, d.api_fetched_at::date;
```

### 5.5 `ops.yango_orders_day_fact` (NUEVA — Canonical Orders)

```sql
CREATE TABLE ops.yango_orders_day_fact (
    id                      BIGSERIAL PRIMARY KEY,
    source_date             DATE NOT NULL,
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,

    -- Core orders
    orders_total            INT DEFAULT 0,
    orders_completed        INT DEFAULT 0,
    orders_cancelled        INT DEFAULT 0,
    cancel_rate_pct         NUMERIC,

    -- Drivers
    unique_drivers          INT DEFAULT 0,
    orders_per_driver_avg   NUMERIC,

    -- GMV (from orders price, not transactions)
    gmv_total               NUMERIC,
    avg_ticket_gmv          NUMERIC,

    -- Fleet
    unique_cars             INT DEFAULT 0,

    -- Dimensions (from raw_payload or order fields)
    orders_by_payment_method JSONB DEFAULT '{}',
    orders_by_category       JSONB DEFAULT '{}',

    -- Audit
    source_endpoint         TEXT DEFAULT 'orders/list',
    coverage_pct            NUMERIC,              -- vs CT bridge
    refreshed_at            TIMESTAMPTZ DEFAULT now(),

    UNIQUE (source_date, park_id)
);
```

### 5.6 `ops.yango_revenue_day_fact` (NUEVA — Canonical Revenue)

Equivalente a `ops.revenue_canonical_day_fact` del diseño CF-H2A, renombrado para consistencia:

```sql
CREATE TABLE ops.yango_revenue_day_fact (
    id                      BIGSERIAL PRIMARY KEY,
    source_date             DATE NOT NULL,
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,

    -- Revenue YEGO
    revenue_yango           NUMERIC,               -- SUM(ABS(Partner fee for trip))
    revenue_currency        TEXT DEFAULT 'PEN',
    revenue_order_count     INT,                   -- orders con Partner fee

    -- Platform fees (Yango commission)
    platform_fee_amount     NUMERIC,               -- Service fee for trip
    platform_fee_vat_amount NUMERIC,               -- Service fee, VAT

    -- GMV (from transactions)
    gmv_cash_amount         NUMERIC,
    gmv_card_amount         NUMERIC,
    gmv_total               NUMERIC,

    -- Derived
    revenue_per_order       NUMERIC,
    take_rate_yego          NUMERIC,               -- revenue_yango / gmv_total
    take_rate_yango         NUMERIC,               -- platform_fee / gmv_total

    -- Other transaction categories
    promo_compensation      NUMERIC,
    adjustments_amount      NUMERIC,
    refunds_amount          NUMERIC,

    -- Audit
    source_endpoint         TEXT DEFAULT 'transactions/list',
    transactions_total      INT,
    linked_orders           INT,
    coverage_pct            NUMERIC,
    refreshed_at            TIMESTAMPTZ DEFAULT now(),

    UNIQUE (source_date, park_id)
);
```

### 5.7 `ops.yango_driver_day_fact` (NUEVA — Driver State)

```sql
CREATE TABLE ops.yango_driver_day_fact (
    id                      BIGSERIAL PRIMARY KEY,
    source_date             DATE NOT NULL,
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,

    -- Driver universe
    drivers_total           INT DEFAULT 0,
    drivers_working         INT DEFAULT 0,
    drivers_not_working     INT DEFAULT 0,
    drivers_contract_issue  INT DEFAULT 0,

    -- Activity (derived from orders)
    drivers_with_orders     INT DEFAULT 0,
    drivers_without_orders  INT DEFAULT 0,

    -- Fleet
    cars_assigned           INT DEFAULT 0,

    -- Supply (si está disponible)
    supply_hours_total      NUMERIC,
    supply_hours_avg        NUMERIC,

    -- Audit
    source_endpoint         TEXT DEFAULT 'driver-profiles/list',
    coverage_pct            NUMERIC,
    refreshed_at            TIMESTAMPTZ DEFAULT now(),

    UNIQUE (source_date, park_id)
);
```

### 5.8 `ops.omniview_v2_source_canonical_fact` (NUEVA — Unified Serving Fact)

**Esta es la tabla que Omniview V2 leerá.** Unifica todas las fuentes (Yango API + CT bridge) con `source_badge` por métrica.

```sql
CREATE TABLE ops.omniview_v2_source_canonical_fact (
    id                      BIGSERIAL PRIMARY KEY,
    source_date             DATE NOT NULL,
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,
    business_slice_name     TEXT,                   -- mapeado desde dim.dim_business_slice_mapping
    fleet_display_name      TEXT,

    -- ================================================================
    -- MÉTRICAS CON SOURCE BADGE INDIVIDUAL
    -- ================================================================

    -- Orders / Trips
    trips_completed         BIGINT,
    trips_source_badge      TEXT,                   -- 'YANGO_API' | 'CT_BRIDGE' | 'MISSING'
    trips_coverage_pct      NUMERIC,

    trips_cancelled         BIGINT,
    cancel_rate_pct         NUMERIC,
    cancel_source_badge     TEXT,

    -- Revenue
    revenue_total           NUMERIC,
    revenue_source_badge    TEXT,                   -- 'YANGO_API' | 'CT_BRIDGE' | 'MISSING'
    revenue_coverage_pct    NUMERIC,

    -- Drivers
    active_drivers          BIGINT,
    drivers_source_badge    TEXT,                   -- 'YANGO_API' | 'CT_BRIDGE' | 'MISSING'
    drivers_coverage_pct    NUMERIC,

    -- Derived
    avg_ticket              NUMERIC,
    trips_per_driver        NUMERIC,
    revenue_per_order       NUMERIC,

    -- GMV & Platform
    gmv_total               NUMERIC,
    gmv_source_badge        TEXT,
    platform_fee_total      NUMERIC,
    platform_fee_source_badge TEXT,
    commission_pct          NUMERIC,

    -- Supply (baja prioridad)
    supply_hours            NUMERIC,
    supply_source_badge     TEXT DEFAULT 'MISSING',

    -- ================================================================
    -- AUDIT
    -- ================================================================
    yango_ingestion_run_id  TEXT,
    ct_refreshed_at         TIMESTAMPTZ,
    yango_refreshed_at      TIMESTAMPTZ,
    mapped_at               TIMESTAMPTZ DEFAULT now(),
    overall_coverage_status TEXT,                   -- 'CERTIFIED' | 'PARTIAL' | 'PENDING'

    UNIQUE (source_date, park_id, business_slice_name)
);

CREATE INDEX ix_ov2scf_date ON ops.omniview_v2_source_canonical_fact (source_date);
CREATE INDEX ix_ov2scf_park ON ops.omniview_v2_source_canonical_fact (park_id);
CREATE INDEX ix_ov2scf_slice ON ops.omniview_v2_source_canonical_fact (business_slice_name);
```

### 5.9 Relación entre Tablas

```
Yango API                          CT Bridge
    │                                   │
    ▼                                   ▼
raw_yango.*                      public.trips_unified
    │                                   │
    ▼                                   ▼
raw_yango.mv_*                   ops.real_business_slice_*_fact
(orders, revenue, drivers)       (day, week, month)
    │                                   │
    └───────────────┬───────────────────┘
                    ▼
    ops.omniview_v2_source_canonical_fact
    (source_badge por métrica)
                    │
                    ▼
    ops.omniview_v2_serving_snapshot
    (JSONB pre-computado para UI)
                    │
                    ▼
           Omniview V2 UI
```

---

## 6. INCREMENTAL INGESTION DESIGN

### 6.1 Watermarks por Park + Endpoint

Cada park+endpoint mantiene su propio watermark de última ingesta exitosa.

```sql
CREATE TABLE raw_yango.ingestion_watermark (
    id                  SERIAL PRIMARY KEY,
    park_id             TEXT NOT NULL,
    endpoint_group      TEXT NOT NULL,              -- 'orders' | 'transactions' | 'driver_profiles'
    last_source_date    DATE,                       -- última fecha ingerida exitosamente
    last_run_id         TEXT,
    last_completed_at   TIMESTAMPTZ,
    records_total       BIGINT DEFAULT 0,
    consecutive_failures INT DEFAULT 0,
    status              TEXT DEFAULT 'active',      -- 'active' | 'paused' | 'failed'
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (park_id, endpoint_group)
);
```

### 6.2 Flujo de Ingesta Diaria

```
1. SCHEDULER dispara ingesta diaria (cron o 5-min tick)
2. Para cada park activo en api_park_credentials_registry:
   a. Leer watermark: last_source_date
   b. Determinar ventana: [last_source_date + 1, today - 1]
   c. Si ventana vacía → skip (ya está al día)
   d. Si ventana > 7 días → modo catch-up (rate-limited)
3. Para cada endpoint_group [orders, transactions, driver_profiles]:
   a. Crear api_ingestion_run (status='running')
   b. Paginar hasta agotar cursor/offset
   c. INSERT ... ON CONFLICT DO NOTHING
   d. Guardar api_ingestion_page_checkpoint por página
   e. Al completar: actualizar watermark.last_source_date
   f. Marcar run como 'completed'
4. Refresh de materialized views (raw_yango.mv_*)
5. Poblar canonical facts (ops.yango_*_day_fact)
6. Poblar unified serving fact (ops.omniview_v2_source_canonical_fact)
7. Regenerar serving snapshot (ops.omniview_v2_serving_snapshot)
```

### 6.3 Ventanas de Ingesta

| Escenario | Ventana | Frecuencia | Rate Limit |
|-----------|---------|------------|------------|
| **Normal (diario)** | yesterday → yesterday | Diario, post-midnight | Normal |
| **Catch-up (< 7 días)** | last_watermark → yesterday | Bajo demanda | Normal |
| **Catch-up (7-30 días)** | last_watermark → yesterday | Programado, baja prioridad | 50% velocidad |
| **Historical backfill (> 30 días)** | Definido por CF-H2H | Manual, batch | 25% velocidad |

### 6.4 Concurrencia Multipark

| Configuración | Valor | Notas |
|---------------|-------|-------|
| Parks concurrentes | Máximo 3 workers | Un worker por park |
| Endpoints concurrentes (mismo park) | Orders ∥ Transactions | Driver profiles secuencial después |
| Páginas (mismo endpoint) | Secuencial | Cursor pagination no permite paralelismo |
| Rate limit guard global | Backoff 3s para todos los workers si 429 | Thread-safe via threading.Event |

### 6.5 Resiliencia

| Mecanismo | Implementación |
|-----------|---------------|
| **Idempotencia** | `ON CONFLICT (park_id, order_id/transaction_id/driver_profile_id, raw_payload_hash) DO NOTHING` |
| **Resume** | `api_ingestion_page_checkpoint` guarda cursor + página por run. Si falla, next run retoma. |
| **Watermark** | `ingestion_watermark` solo avanza si run.status = 'completed'. Si 'partial', se reintenta. |
| **Credenciales inválidas** | Pausar park en watermark (status='failed'). No reintentar. Alerta. |
| **Timeout** | Reintentar 2x. Si persiste, marcar run 'partial'. |

---

## 7. RECONCILIATION DESIGN (Yango API vs CT Bridge)

### 7.1 Métricas Comparables

| Métrica | Yango API | CT Bridge | Join Key |
|---------|-----------|-----------|----------|
| Orders completed | `orders_completed` (mv_orders_day) | `trips_completed` (day_fact) | source_date + park |
| Active drivers | `unique_drivers` (mv_orders_day) | `COUNT DISTINCT driver_id` (driver_day_slice_fact) | source_date + park |
| Revenue | `revenue_partner_fee_amount` (mv_revenue_day) | `revenue_yego_final` (day_fact) | source_date + park |
| GMV | `gmv_cash + gmv_card` (mv_revenue_day) | `gmv_passenger_paid` (day_fact) | source_date + park |
| Cancel rate | `orders_cancelled / orders_total` | `cancel_rate_pct` (day_fact) | source_date + park |
| Avg ticket | `gmv_total / orders_completed` | `avg_ticket` (day_fact) | source_date + park |

### 7.2 Dimensiones de Reconciliación

| Dimensión | Cómo se compara | Dificultad |
|-----------|----------------|------------|
| **Day** | Directa: source_date = trip_date | Baja |
| **Park** | Directa: park_id = park_id | Baja |
| **Business Slice** | Indirecta: requiere mapeo order.category → business_slice_name | **Alta** |
| **City** | Directa: city from park registry | Baja |
| **Country** | Directa: country from park registry | Baja |

### 7.3 Problema del Business Slice Mapping

Yango API no tiene concepto de "business_slice_name". Las órdenes tienen `category` (ej. "auto_regular", "taxi") y los drivers tienen `work_rule`. El mapeo a business slices de CT requiere:

```
Opción A: Mapeo estático category → business_slice_name
  "auto" → "Auto regular"
  "taxi" → "Auto regular"
  "delivery" → "Delivery"
  etc.

Opción B: Mapeo vía driver_work_rule → business_slice
  Requiere tabla de referencia: dim_yango_work_rule → business_slice_name

Opción C: Mapeo vía CT bridge (híbrido)
  Usar CT para generar mapping order_id → business_slice_name
  Luego aplicar a orders_raw.order_id
```

**Recomendación:** Opción A para fase inicial (simple, estática). Opción B si se requiere precisión (requiere work rule taxonomy). Opción C para validación cruzada.

### 7.4 Clasificación de Resultados

| Clasificación | Condición | Significado |
|---------------|-----------|-------------|
| `MATCH` | Delta < 1% | Fuentes equivalentes |
| `MINOR_DELTA` | Delta 1-5% | Variación aceptable |
| `MAJOR_DELTA` | Delta 5-20% | Requiere investigación |
| `CRITICAL_DELTA` | Delta > 20% | Bloquea promoción |
| `YANGO_ONLY` | Dato en Yango, no en CT | Gap de CT bridge |
| `CT_ONLY` | Dato en CT, no en Yango | Gap de Yango API |
| `MISSING_BOTH` | Sin dato en ninguna fuente | Park/día sin cobertura |

### 7.5 Frecuencia de Reconciliación

| Tipo | Frecuencia | Trigger |
|------|------------|---------|
| **Diaria** | Cada ingesta | Automático post-refresh de serving facts |
| **Semanal** | Lunes | Reporte agregado de 7 días |
| **Mensual** | Día 1 del mes | Reporte de cobertura y certificación |
| **Ad-hoc** | Manual | Para investigar anomalías |

---

## 8. PROMOTION RULES — POR MÉTRICA

Cada métrica tiene su propio criterio de promoción de CT_BRIDGE a YANGO_API. **No hay big-bang. La promoción es independiente por métrica.**

### 8.1 Thresholds por Métrica

| Métrica | Cobertura mínima | Delta máximo diario | Delta máximo agregado (30d) | Días consecutivos requeridos |
|---------|-----------------|---------------------|---------------------------|---------------------------|
| **Revenue** | ≥ 99% | ≤ 5% | ≤ 3% | 30 |
| **Trips/Orders** | ≥ 99% | ≤ 2% | ≤ 1% | 30 |
| **Active Drivers** | ≥ 95% | ≤ 10% | ≤ 5% | 30 |
| **Cancel Rate** | ≥ 99% | ≤ 2% | ≤ 1% | 14 |
| **GMV** | ≥ 99% | ≤ 5% | ≤ 3% | 14 |
| **Avg Ticket** | ≥ 99% | ≤ 5% | ≤ 3% | 30 |
| **Commission Rate** | ≥ 95% | ≤ 10% | ≤ 5% | 30 |
| **Supply Hours** | N/A | N/A | N/A | No promovible aún (sin bulk endpoint) |

### 8.2 Estados de Promoción

| Estado | Significado | source_badge |
|--------|-------------|-------------|
| `CERTIFIED` | Todos los thresholds cumplidos por ≥ N días | `YANGO_API` |
| `CANDIDATE` | En período de observación, thresholds cumplidos parcialmente | `YANGO_API_SHADOW` |
| `AUDIT_ONLY` | Datos disponibles pero no certificados para serving | `CT_BRIDGE` (Yango disponible en audit) |
| `UNAVAILABLE` | Sin datos de Yango API para esta métrica | `CT_BRIDGE` |
| `DEGRADED` | Estaba CERTIFIED pero cayó debajo de thresholds | `CT_BRIDGE` (Yango en revisión) |

### 8.3 Orden de Promoción Recomendado

```
Fase 1 (CF-H2E): Revenue        → más validado, ~95.6% match, delta 4.4%
Fase 2 (CF-H2E): Cancel Rate    → semántica directa, fácil de validar
Fase 3 (CF-H2E): GMV            → derivado de transactions, buena cobertura
Fase 4 (CF-H2F): Trips/Orders   → requiere validación exhaustiva, high stakes
Fase 5 (CF-H2F): Avg Ticket     → derivado de trips y GMV
Fase 6 (CF-H2F): Active Drivers → más complejo por ID mismatch
Fase 7 (CF-H2G): Commission Pct → derivado, última en promoverse
```

### 8.4 Tabla de Control de Promoción

```sql
CREATE TABLE ops.yango_metric_promotion_status (
    id                      SERIAL PRIMARY KEY,
    park_id                 TEXT NOT NULL,
    metric_name             TEXT NOT NULL,          -- 'revenue', 'trips', 'drivers', etc.
    promotion_status        TEXT NOT NULL,          -- 'CERTIFIED' | 'CANDIDATE' | 'AUDIT_ONLY' | 'UNAVAILABLE' | 'DEGRADED'
    coverage_pct_30d        NUMERIC,
    delta_avg_30d           NUMERIC,
    delta_max_30d           NUMERIC,
    days_above_threshold    INT,
    certified_at            TIMESTAMPTZ,
    degraded_at             TIMESTAMPTZ,
    last_checked_at         TIMESTAMPTZ DEFAULT now(),
    notes                   TEXT,
    UNIQUE (park_id, metric_name)
);
```

---

## 9. SOURCE BADGES — CONTRATO

### 9.1 Badges por Métrica

Cada celda en Omniview V2 tendrá un `source_badge` que indica el origen del dato:

| Badge | Color | Significado |
|-------|-------|-------------|
| `YANGO_API` | Verde | Dato desde Yango API, cobertura certificada |
| `YANGO_API_SHADOW` | Azul | Dato desde Yango API, en período de observación |
| `CT_BRIDGE` | Gris | Dato desde CT bridge (fuente legacy) |
| `MIXED` | Amarillo | Combinación de fuentes (ej. revenue Yango + drivers CT) |
| `MISSING` | Rojo | Sin dato de ninguna fuente |
| `PROXY` | Naranja | Dato estimado/proxy, no real |

### 9.2 Visibilidad en UI

- Tooltip en cada celda muestra: fuente, coverage %, última actualización
- Badge visible como ícono pequeño (no distrae, pero trazable)
- Dashboard de cobertura muestra matriz grain × métrica × source

---

## 10. SNAPSHOTS — DAILY / WEEKLY / MONTHLY

### 10.1 Estrategia de Snapshots

Los serving facts `ops.omniview_v2_source_canonical_fact` se snapshotean para serving rápido:

| Grain | Tabla Snapshot | Frecuencia | Ventana |
|-------|---------------|------------|---------|
| **Day** | `ops.omniview_v2_serving_snapshot` (ya existe) | Cada ingesta | 14 días rolling |
| **Week** | Agregación desde day fact | Semanal | 12 semanas rolling |
| **Month** | Agregación desde day fact | Mensual | 12 meses rolling |

### 10.2 Pipeline de Agregación

```
ops.omniview_v2_source_canonical_fact (day grain, source_badge)
    │
    ▼ WEEKLY ROLLUP
ops.omniview_v2_source_canonical_week_fact
    │ (SUM de métricas, AVG de rates, MODE de source_badge)
    │
    ▼ MONTHLY ROLLUP
ops.omniview_v2_source_canonical_month_fact
    │ (SUM de métricas, AVG de rates, MODE de source_badge)
```

### 10.3 Propuesta de Tablas de Agregación

```sql
-- Week fact (misma estructura que day, grain = week_start)
CREATE TABLE ops.omniview_v2_source_canonical_week_fact (
    LIKE ops.omniview_v2_source_canonical_fact INCLUDING ALL
);
ALTER TABLE ops.omniview_v2_source_canonical_week_fact
    DROP COLUMN source_date,
    ADD COLUMN week_start DATE NOT NULL;
CREATE UNIQUE INDEX ON ops.omniview_v2_source_canonical_week_fact
    (week_start, park_id, business_slice_name);

-- Month fact
CREATE TABLE ops.omniview_v2_source_canonical_month_fact (
    LIKE ops.omniview_v2_source_canonical_fact INCLUDING ALL
);
ALTER TABLE ops.omniview_v2_source_canonical_month_fact
    DROP COLUMN source_date,
    ADD COLUMN month DATE NOT NULL;
CREATE UNIQUE INDEX ON ops.omniview_v2_source_canonical_month_fact
    (month, park_id, business_slice_name);
```

### 10.4 Source Badge en Agregaciones

Cuando se agregan métricas de múltiples días con diferentes badges:
- Si todos los días tienen `YANGO_API` → badge = `YANGO_API`
- Si todos los días tienen `CT_BRIDGE` → badge = `CT_BRIDGE`
- Si hay mezcla → badge = `MIXED` con detalle en JSONB
- Si coverage < threshold agregado → badge = `YANGO_API` pero con `PARTIAL`

---

## 11. PLAN DE IMPLEMENTACIÓN POR FASES

### 11.1 Roadmap Visual

```
CF-H2A [COMPLETADO]  Yango Revenue Source Architecture
    │
CF-H2B [ESTE DOC]    Yango Omniview Raw Landing Foundation
    │                 - Arquitectura completa de migración
    │                 - Diseño de todas las tablas
    │                 - Estrategia de promoción por métrica
    │
CF-H2C                Raw Landing Stabilization
    │                 - Verificar ingesta sin max_pages
    │                 - Crear raw_yango.transaction_categories_ref
    │                 - Implementar ingesta de transaction categories
    │                 - Corregir gaps de schema (event_id, driver_profiles)
    │                 - Implementar ingestion_watermark
    │
CF-H2D                Normalized Layer Construction
    │                 - Extender raw_yango.mv_orders_day
    │                 - Crear raw_yango.mv_driver_activity_day
    │                 - Crear ops.yango_orders_day_fact
    │                 - Crear ops.yango_revenue_day_fact
    │                 - Crear ops.yango_driver_day_fact
    │                 - Pipeline diario: raw → mv → canonical
    │
CF-H2E                Coverage Observatory + Reconciliation
    │                 - Crear ops.yango_coverage_day_log
    │                 - Crear ops.yango_metric_promotion_status
    │                 - Pipeline de reconciliación diaria Yango vs CT
    │                 - Dashboard de cobertura por métrica
    │                 - Alertas de degradación
    │
CF-H2F                Canonical Mapper + Unified Serving
    │                 - Crear ops.omniview_v2_source_canonical_fact
    │                 - Mapear Yango + CT → serving fact unificado
    │                 - Asignar source_badge por métrica
    │                 - Crear week/month rollups
    │                 - Business slice mapping (category → slice)
    │
CF-H2G                Serving Integration + Cutover Certification
    │                 - Omniview V2 lee de source_canonical_fact
    │                 - Actualizar serving snapshots
    │                 - Certificar 30+ días de datos
    │                 - GO/NO-GO formal por métrica
    │                 - Rollback plan
    │
CF-H2H                Historical Backfill (opcional)
    │                 - Backfill Yango 2026-01-01 → 2026-05-31
    │                 - Solo métricas promovidas a CERTIFIED
    │                 - Baja prioridad
    │
CF-H2I                Continuous Certification
                      - Monitor de thresholds en producción
                      - Auto-degradación si métrica cae
                      - Auto-promoción si métrica se recupera
```

### 11.2 Detalle por Fase

#### CF-H2C — Raw Landing Stabilization

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Estabilizar ingesta raw: sin max_pages, con watermarks, con taxonomía |
| **Archivos** | `ingest_yango_raw_landing.py`, `raw_yango_repository.py`, nuevo: `yango_watermark_service.py` |
| **Migraciones** | `raw_yango.transaction_categories_ref`, `raw_yango.ingestion_watermark` |
| **Correcciones** | Agregar `event_id` a transactions_raw. Verificar consistencia driver_profiles_raw DDL vs código. |
| **GO** | 7 días consecutivos de ingesta sin errores para Lima. Categorías persistidas. Watermarks funcionales. |

#### CF-H2D — Normalized Layer Construction

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Construir capa normalizada: extender MVs existentes, crear nuevas, poblar canonical facts |
| **Archivos** | `refresh_raw_yango_mvs.py` (extender), nuevos: `yango_normalized_builder.py`, `yango_canonical_fact_builder.py` |
| **Migraciones** | Extender `mv_orders_day`. Nuevo: `mv_driver_activity_day`, `yango_orders_day_fact`, `yango_revenue_day_fact`, `yango_driver_day_fact` |
| **GO** | MVs refrescan correctamente. Canonical facts poblados para 14 días. |

#### CF-H2E — Coverage Observatory + Reconciliation

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Observatorio de cobertura diaria con reconciliación automatizada Yango vs CT |
| **Archivos** | Nuevos: `yango_coverage_service.py`, `yango_reconciliation_service.py`, `compute_daily_coverage.py` |
| **Migraciones** | `ops.yango_coverage_day_log`, `ops.yango_metric_promotion_status` |
| **GO** | 30 días de cobertura documentada. Reconciliación diaria funcional. Business slice mapping operativo. |

#### CF-H2F — Canonical Mapper + Unified Serving

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Unificar Yango + CT en serving fact con source_badge por métrica |
| **Archivos** | Nuevos: `source_canonical_mapper.py`, `source_canonical_rollup.py` |
| **Migraciones** | `ops.omniview_v2_source_canonical_fact`, `_week_fact`, `_month_fact` |
| **GO** | Serving fact poblado para 30 días. Badges correctos por métrica. Rollups week/month funcionales. |

#### CF-H2G — Serving Integration + Cutover Certification

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Enchufar Omniview V2 a source_canonical_fact. Certificar cutover. |
| **Archivos** | `omniview_v2_source_repository.py` (extender), `omniview_v2_snapshot_service.py` (extender) |
| **Migraciones** | Ninguna (usa tablas existentes) |
| **GO** | Omniview V2 muestra datos con source_badge. 30+ días certificados. Rollback test exitoso. |

---

## 12. GO / NO-GO PARA CF-H2B

### 12.1 GO Criteria

| # | Criterio | Estado |
|---|----------|--------|
| 1 | Endpoints de Yango API auditados y clasificados | **PASS** |
| 2 | Raw payload storage definido (existente + nuevas tablas) | **PASS** |
| 3 | Normalized facts diseñados (MVs + canonical facts) | **PASS** |
| 4 | Ingesta incremental con watermarks diseñada | **PASS** |
| 5 | Concurrencia multipark definida | **PASS** |
| 6 | Plan de reconciliación Yango vs CT definido | **PASS** |
| 7 | Promotion rules por métrica definidas | **PASS** |
| 8 | Source badges definidos con contrato de visibilidad | **PASS** |
| 9 | Snapshots daily/weekly/monthly diseñados | **PASS** |
| 10 | No se implementó nada | **PASS** |
| 11 | No se abrió Diagnostic Engine | **PASS** |
| 12 | Governance validation completa | **PASS** |

### 12.2 Classification

**CF_H2B_RAW_LANDING_ARCHITECTURE_READY**

### 12.3 Gaps Identificados (para resolver en CF-H2C)

| # | Gap | Severidad | Acción |
|---|-----|-----------|--------|
| 1 | `transaction_categories_ref` no existe — taxonomía no persistida | **MEDIUM** | Crear tabla + ingesta en CF-H2C |
| 2 | `event_id` no está en DDL de transactions_raw | LOW | Agregar columna en CF-H2C |
| 3 | Driver ID mismatch (conductor_id vs driver_profile_id) | **HIGH** | Investigar mapping table en CF-H2D |
| 4 | Business slice mapping no existe (category → slice) | **HIGH** | Diseñar mapping en CF-H2E |
| 5 | `driver_profiles_raw` posible inconsistencia DDL vs código | MEDIUM | Auditar en CF-H2C |
| 6 | Supply hours sin bulk endpoint — no escalable | MEDIUM | Aceptar limitación. Solo para spot checks. |
| 7 | `price` field type ambiguity (string vs object) | HIGH | Verificar con API live en CF-H2C |
| 8 | `cars/list` endpoint no implementado | LOW | P2 — postergar a CF-H2D+ |
| 9 | `orders/transactions/list` no implementado | MEDIUM | P2 — valioso para reconciliación |

### 12.4 Next Phase

**CF-H2C — Raw Landing Stabilization**

---

## 13. FIRMA

| Campo | Valor |
|-------|-------|
| **Diseñado por** | CF-H2B Yango Omniview Raw Landing Foundation |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Fase padre** | CF-H2 — Revenue Canonical Definition |
| **Clasificación** | `CF_H2B_RAW_LANDING_ARCHITECTURE_READY` |
| **Próxima fase** | CF-H2C — Raw Landing Stabilization |
| **Dependencias** | CF-H2A (completado), OV2 Close (2ab32e9), raw_yango schema (migration 181+) |
| **Bloquea** | Diagnostic Engine (hasta que CF-H2 cierre) |
