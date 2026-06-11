# CF-H2A — YANGO REVENUE SOURCE ARCHITECTURE

> **Fase:** CF-H2A — Yango Revenue Source Architecture
> **Motor:** Control Foundation
> **Clasificación:** CF_H2A_ARCHITECTURE_READY
> **Fecha:** 2026-06-11
> **Propósito:** Diseñar la arquitectura canónica para usar Yango API como fuente confiable de revenue desde 2026-06-01

---

## 1. EXECUTIVE SUMMARY

Yango Fleet API (`https://fleet-api.yango.tech`) ha sido certificada como fuente de revenue con clasificación `CERTIFIED_REVENUE_AUDIT` (OV2-A.4, 2026-06-05). La categoría `Partner fee for trip` del endpoint `POST /v2/parks/transactions/list` correlaciona al ~95.6% con `revenue_yego_final` de Control Tower sobre la ventana de validación de 3 días.

Este documento define la arquitectura para promover Yango API como **fuente canónica de revenue desde 2026-06-01 en adelante**, estableciendo el contrato de corte (cutover), el modelo de datos requerido, la arquitectura de ingesta concurrente, el plan de reconciliación y el registro de riesgos.

**Estado actual del revenue:**
- Fuente primaria: `comision_empresa_asociada` en `public.trips_unified` → `ops.real_business_slice_*_fact.revenue_yego_net`
- Fallback proxy: `ticket * commission_pct` cuando commission es NULL/0
- Yango API ya ingiere datos en `raw_yango.*` (migraciones 181/186/187/188/189/190)
- `raw_yango.mv_revenue_day` ya calcula `revenue_partner_fee_amount` diario por park
- Lima Growth Engine ya consume Yango API como fuente operacional live (orders, drivers, revenue)

**Qué propone esta arquitectura:**
1. Mantener el pipeline actual intacto (CT bridge → `trips_unified` → `day_fact`)
2. Agregar Yango API como fuente canónica paralela de revenue desde 2026-06-01
3. Unificar en un **serving fact** (`ops.revenue_canonical_day_fact`) con `source_badge` trazable
4. No reemplazar trips/drivers desde CT bridge (solo revenue se promueve en esta fase)
5. No abrir Diagnostic Engine ni modificar Omniview V2

---

## 2. GOVERNANCE VALIDATION

### 2.1 Reglas de Engine (ai_operating_system.md)

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| Motor = Control Foundation | **PASS** | CF-H2A pertenece a Control Foundation. No es Diagnostic. |
| No mezclar engines | **PASS** | Solo Control Foundation. Sin Forecast/Suggestion/Decision/Action. |
| Serving-first architecture | **PASS** | Se propone `ops.revenue_canonical_day_fact` como serving fact gobernado. |
| Deterministic logic first | **PASS** | Revenue = `SUM(ABS(Partner fee for trip))`. Sin AI. |
| Máximo 1 ACTIVE + 1 READY NEXT | **PASS** | OMNI-P0 ACTIVE, CF-H2A/H2B READY NEXT. |
| Diagnostic PAUSED | **PASS** | No se activa Diagnostic. |

### 2.2 Reglas de Fase Actual (ai_current_phase.md)

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| CF-H2 Revenue Certification READY NEXT | **PASS** | `ai_current_phase.md:132`: "READY NEXT (puede correr en paralelo con OMNI-P0)" |
| POST_OV2_TRANSITION_AUDIT.md GO for CF-H2 | **PASS** | Sección 6: "GO for CF-H2 Revenue Certification" |
| OV2 cerrado (commit 2ab32e9) | **PASS** | OV2_CLOSE_5_RELEASE_COMMITTED |
| No modificar Omniview V1 | **PASS** | No se toca V1. |
| No modificar UI productiva | **PASS** | Solo diseño de arquitectura backend. |
| No abrir Diagnostic/Forecast/Suggestion/Decision/Action/AI Copilot/Learning | **PASS** | Todos PAUSED o BACKLOG. |

### 2.3 Reglas de POST_OV2_TRANSITION_AUDIT.md

| Regla | Estado | Evidencia |
|-------|--------|-----------|
| CF-H2 Revenue Certification es el next step | **PASS** | Sección 4: "DO FIRST" |
| No activar Yango ingestion fuera de CF-H2 | **PASS** | La ingesta existe pero se formaliza ahora como parte de CF-H2. |
| No abrir Diagnostic | **PASS** | Sección 5: "NO-GO for Diagnostic Engine activation" |

### 2.4 Governance Verdict

**GO for CF-H2A Architecture Design.** Todas las reglas de governance se cumplen. Esta fase es puramente diseño arquitectónico. No implementa, no ingesta, no modifica serving facts existentes.

---

## 3. CREDENTIALS & PARKS INVENTORY

### 3.1 Tabla de Registro

| Campo | Valor |
|-------|-------|
| **Schema/Tabla** | `raw_yango.api_park_credentials_registry` |
| **Migración** | 181_raw_yango_landing.py |
| **Propósito** | Registro de credenciales por park sin almacenar secrets en DB |

### 3.2 Columnas

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `id` | `SERIAL PRIMARY KEY` | Clave primaria |
| `credential_id` | `TEXT NOT NULL UNIQUE` | Identificador único (ej. `yango_lima_park`) |
| `park_id` | `TEXT NOT NULL` | Park ID de Yango Fleet API |
| `country` | `TEXT` | País |
| `city` | `TEXT` | Ciudad |
| `fleet_name` | `TEXT` | Nombre descriptivo de flota |
| `env_var_name` | `TEXT NOT NULL` | Prefijo de variable de entorno (NUNCA el valor) |
| `api_base_url` | `TEXT NOT NULL` | URL base de API |
| `is_active` | `BOOLEAN DEFAULT true` | Park activo para ingesta |
| `created_at` | `TIMESTAMPTZ` | Fecha de creación |
| `updated_at` | `TIMESTAMPTZ` | Última actualización |
| `notes` | `TEXT` | Notas adicionales |

### 3.3 Parks Conocidos

| credential_id | park_id | fleet_name | country | city | env_var_name | is_active |
|---------------|---------|------------|---------|------|-------------|-----------|
| `yango_lima_park` | `08e20910d81d42658d4334d3f6d10ac0` | Yango Lima | PE | Lima | `YANGO_LIMA` | `true` |

**Nota:** La cantidad exacta de parks registrados debe verificarse con query directa a producción. Actualmente se conoce al menos 1 park (Lima). El número de parks se obtiene con: `SELECT COUNT(*) FROM raw_yango.api_park_credentials_registry WHERE is_active = true`.

### 3.4 Seguridad de Credenciales

| Aspecto | Implementación |
|---------|---------------|
| **Almacenamiento** | Variables de entorno `.env` — NUNCA en base de datos |
| **Referencia en DB** | Solo `env_var_name` (ej. `YANGO_LIMA`) |
| **Resolución** | `os.environ[f"{env_var_name}_API_KEY"]`, `os.environ[f"{env_var_name}_CLIENT_ID"]` |
| **Sanitización** | `_sanitize_message()` reemplaza secrets con `***` en logs |
| **Masking** | `_mask_id()` muestra solo primeros 8 caracteres en logs |
| **URL sanitization** | `_sanitize_url()` elimina credenciales de URLs logueadas |

### 3.5 Cobertura Esperada

| Dimensión | Estado | Notas |
|-----------|--------|-------|
| Lima, PE | **Activo** | Park `08e20910...` con credenciales configuradas |
| Parks adicionales | **Pendiente verificación** | El registry soporta múltiples parks. Auditoría requerida. |
| API base URL | `https://fleet-api.yango.tech` | Única para todos los parks |

---

## 4. YANGO API CONTRACT

### 4.1 Endpoint Principal de Revenue

| Aspecto | Detalle |
|---------|---------|
| **Endpoint** | `POST /v2/parks/transactions/list` |
| **Método** | `POST` |
| **Auth** | Headers: `X-Client-ID`, `X-API-Key`, `Accept-Language: en` |
| **Body** | `{"limit": 1000, "query": {"park": {"id": "<park_id>", "transaction": {"event_at": {"from": "...", "to": "..."}}}}}` |
| **Paginación** | Cursor-based (`next_cursor` en response) |
| **Page size máximo** | 1000 |
| **Filtro por fecha** | `query.park.transaction.event_at.from` / `event_at.to` (ISO 8601 con timezone) |
| **Filtro por categoría** | `query.park.transaction.category_ids[]` (opcional) |

### 4.2 Endpoint Secundario (Orders)

| Aspecto | Detalle |
|---------|---------|
| **Endpoint** | `POST /v1/parks/orders/list` |
| **Método** | `POST` |
| **Auth** | Mismos headers |
| **Body** | `{"limit": 500, "query": {"park": {"id": "<park_id>", "order": {"ended_at": {"from": "...", "to": "..."}, "statuses": ["complete"]}}}}` |
| **Paginación** | Cursor-based (`next_cursor`) |
| **Page size máximo** | 500 |

### 4.3 Campos de Revenue (Transactions)

| Campo API | Tipo | Significado | Uso |
|-----------|------|-------------|-----|
| `category_name: "Partner fee for trip"` | string | Comisión YEGO cobrada al conductor | **REVENUE CANÓNICO** |
| `amount` | string (fixed-point) | Monto (negativo = cargo al driver) | `ABS(amount)` = revenue |
| `currency_code` | string | Código ISO de moneda | `PEN` |
| `order_id` | string | Order ID vinculado | Trazabilidad |
| `driver_profile_id` | string | Driver ID vinculado | Trazabilidad |
| `event_at` | ISO datetime | Timestamp de la transacción | Fecha de revenue |
| `category_name: "Service fee for trip"` | string | Comisión de Yango (platform) | PLATFORM_FEE — NO es revenue YEGO |
| `category_name: "Service fee, VAT"` | string | IVA sobre platform fee | PLATFORM_FEE |
| `category_name: "Cash"` | string | Pago en efectivo | GMV — NO es revenue |
| `category_name: "Card payment"` | string | Pago con tarjeta | GMV — NO es revenue |

### 4.4 Campos de Orders

| Campo API | Tipo | Significado | Uso |
|-----------|------|-------------|-----|
| `id` | string | Order ID | Join con transactions |
| `status` | string | `complete`, `cancelled` | Filtro |
| `ended_at` | ISO datetime | Timestamp de finalización | Fecha operativa |
| `price` | string (fixed-point) | Precio bruto del viaje (GMV) | GMV — NO es revenue |
| `mileage` | number | Distancia | Referencia |
| `driver_profile.id` | string | Driver ID | Join con drivers |
| `payment_method` | string | Método de pago | Dimensional |
| `category` | string | Categoría de servicio | Dimensional |

### 4.5 Rate Limits & Performance

| Métrica | Valor Observado | Notas |
|---------|----------------|-------|
| Latencia p50 | ~400-500 ms | Medido en scale probe (14 días) |
| Latencia p95 | ~760-2200 ms | Varía; orders más lento que transactions |
| Rate limits (429) | 0 observados | Sin incidencias en 14 días de probe |
| Errores | 0 | 100% success rate en probe |
| Tiempo por página (orders) | ~20s | Para page_size=500 en Lima |
| Páginas/día (Lima) | ~25 páginas | Para ~12K orders/día con page_size=500 |
| Tiempo total/día (orders, Lima) | ~8 min | Secuencial, single park |
| Tiempo por página (transactions) | ~1-2s | Más rápido que orders, page_size=1000 |

### 4.6 Aprendizajes Previos

| Lección | Implicación |
|---------|-------------|
| page_size=500 para orders es el máximo | No se puede aumentar para acelerar |
| Cursor pagination es secuencial | No se puede paralelizar por página dentro de un mismo park+día |
| API es lenta para orders (~20s/página) | Requiere background job asíncrono, no sesión interactiva |
| ~25 páginas para un día completo en Lima | ~500s (~8 min) secuencial para orders |
| Transactions es más rápido (~1-2s/página) | Revenue puro puede ser más eficiente que orders |
| La ingesta previa fue truncada por max_pages | Para scheduled NO usar max_pages; solo para manual/debug |
| Sin rate limits observados | Margen de seguridad existe pero no garantizado |

---

## 5. PROPOSED DATA MODEL

### 5.1 Tablas Existentes (NO MODIFICAR)

Las siguientes tablas ya existen y operan en producción. **No se modifican en esta fase:**

| Schema/Tabla | Migración | Rol |
|-------------|-----------|-----|
| `raw_yango.orders_raw` | 181 | Raw orders desde API |
| `raw_yango.transactions_raw` | 181 | Raw transactions desde API |
| `raw_yango.driver_profiles_raw` | 181 | Raw driver profiles desde API |
| `raw_yango.api_park_credentials_registry` | 181 | Registro de credenciales |
| `raw_yango.api_ingestion_run` | 181+189 | Tracking de ingestion runs |
| `raw_yango.api_ingestion_page_checkpoint` | 189 | Checkpoint por página |
| `raw_yango.ingestion_errors` | 181 | Registro de errores |
| `raw_yango.mv_revenue_day` | 187→188→190 | Revenue diario agregado |
| `raw_yango.mv_orders_day` | 187→188 | Orders diarios agregados |
| `raw_yango.mv_transactions_day` | 187→188 | Transactions diarios por categoría |
| `raw_yango.mv_driver_profiles_snapshot` | 187→188 | Último perfil por driver |
| `raw_yango.mv_source_coverage_day` | 187→188 | Cobertura por día |
| `ops.real_business_slice_day_fact` | 119 | **Canonical day fact actual** |
| `ops.real_business_slice_week_fact` | 119 | Canonical week fact actual |
| `ops.real_business_slice_month_fact` | 116 | Canonical month fact actual |

### 5.2 Nueva Tabla Propuesta: `ops.revenue_canonical_day_fact`

Tabla de serving que unifica revenue de múltiples fuentes con trazabilidad de origen.

```sql
CREATE TABLE ops.revenue_canonical_day_fact (
    id                      BIGSERIAL PRIMARY KEY,
    source_date             DATE NOT NULL,              -- Fecha operativa del revenue
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,
    business_slice_name     TEXT,                        -- Mapeado desde dim.dim_business_slice_mapping
    fleet_display_name      TEXT,

    -- Revenue from Yango API (canonical source for >= 2026-06-01)
    revenue_yango_api       NUMERIC,                     -- SUM(ABS(Partner fee for trip)) from raw_yango.transactions_raw
    revenue_yango_currency  TEXT DEFAULT 'PEN',
    revenue_yango_orders_linked INT,                     -- Cantidad de orders con revenue en Yango API

    -- Revenue from CT bridge (legacy source, proxy-based)
    revenue_ct_bridge       NUMERIC,                     -- revenue_yego_net from existing day_fact
    revenue_ct_source       TEXT,                         -- 'real' / 'proxy' / 'mixed'

    -- Unified canonical revenue
    revenue_canonical       NUMERIC NOT NULL,            -- Selected source based on cutover rules
    revenue_source_badge    TEXT NOT NULL,               -- 'YANGO_API' | 'CT_BRIDGE' | 'YANGO_API_PARTIAL' | 'MISSING'
    revenue_coverage_pct    NUMERIC,                     -- % de trips con revenue presente

    -- Platform metrics (from Yango API)
    gmv_yango_api           NUMERIC,                     -- SUM(Cash + Card payment) from transactions
    platform_fee_yango_api  NUMERIC,                     -- SUM(ABS(Service fee for trip + VAT))

    -- Audit
    yango_ingestion_run_id  TEXT,                        -- FK lógica a api_ingestion_run.run_id
    revenue_mapped_at       TIMESTAMPTZ DEFAULT now(),
    reconciliation_status   TEXT,                        -- 'MATCH', 'MINOR_DELTA', 'MAJOR_DELTA', 'YANGO_ONLY', 'CT_ONLY', 'MISSING_BOTH'

    UNIQUE (source_date, park_id, business_slice_name)
);

CREATE INDEX ix_rcf_date ON ops.revenue_canonical_day_fact (source_date);
CREATE INDEX ix_rcf_park ON ops.revenue_canonical_day_fact (park_id);
CREATE INDEX ix_rcf_badge ON ops.revenue_canonical_day_fact (revenue_source_badge);
```

### 5.3 Nueva Tabla Propuesta: `ops.yango_revenue_coverage_log`

Registro diario de cobertura de revenue Yango por park para decisión de cutover.

```sql
CREATE TABLE ops.yango_revenue_coverage_log (
    id                      BIGSERIAL PRIMARY KEY,
    coverage_date           DATE NOT NULL,
    park_id                 TEXT NOT NULL,

    -- Orders coverage
    orders_ct_total         INT,                         -- Total orders en CT para esa fecha
    orders_yango_total      INT,                         -- Total orders en Yango API
    orders_yango_completed  INT,                         -- Orders completed en Yango API
    orders_coverage_pct     NUMERIC,                     -- orders_yango_completed / orders_ct_total * 100

    -- Revenue coverage
    revenue_yango_total     NUMERIC,                     -- SUM(ABS(Partner fee for trip))
    revenue_ct_total        NUMERIC,                     -- revenue_yego_net from day_fact
    revenue_delta_abs       NUMERIC,
    revenue_delta_pct       NUMERIC,

    -- Driver coverage
    drivers_yango_active    INT,
    drivers_ct_active       INT,
    drivers_coverage_pct    NUMERIC,

    -- Currency
    currency_check          TEXT,                        -- 'OK' | 'MISMATCH'

    -- Decision
    coverage_status         TEXT NOT NULL,               -- 'CERTIFIED' | 'PENDING' | 'INSUFFICIENT' | 'FAILED'
    promotion_eligible      BOOLEAN DEFAULT false,       -- true si coverage >= thresholds
    checked_at              TIMESTAMPTZ DEFAULT now(),

    UNIQUE (coverage_date, park_id)
);
```

### 5.4 Nueva Tabla Propuesta: `ops.revenue_source_cutover_config`

Configuración del contrato de corte por park.

```sql
CREATE TABLE ops.revenue_source_cutover_config (
    id                      SERIAL PRIMARY KEY,
    park_id                 TEXT NOT NULL,
    country                 TEXT,
    city                    TEXT,

    cutover_date            DATE NOT NULL,               -- 2026-06-01
    source_primary          TEXT NOT NULL DEFAULT 'YANGO_API',  -- 'YANGO_API' | 'CT_BRIDGE'
    source_pre_cutover      TEXT NOT NULL DEFAULT 'CT_BRIDGE',  -- Fuente para fechas < cutover_date

    -- Thresholds for Yango API promotion
    orders_coverage_min_pct NUMERIC DEFAULT 99.0,        -- Requiere >= 99% coverage de orders
    revenue_present_min_pct NUMERIC DEFAULT 99.0,        -- Requiere >= 99% de trips con revenue
    park_coverage_min_pct   NUMERIC DEFAULT 100.0,       -- Requiere 100% parks activos cubiertos
    currency_consistency    BOOLEAN DEFAULT true,         -- Requiere 100% currency match

    is_active               BOOLEAN DEFAULT true,
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),

    UNIQUE (park_id)
);
```

### 5.5 Tabla Existente a Extender: `ops.real_business_slice_*_fact`

NO se modifica la estructura. En su lugar, se agrega una columna calculada vía VIEW o se genera `revenue_canonical_day_fact` como serving fact independiente. La decisión final de si `revenue_yego_net` en los fact tables se actualiza con Yango API se difiere a CF-H2E (Revenue Canonical Mapper).

### 5.6 Relación entre Tablas

```
┌──────────────────────────────────────────────────────────────────┐
│                     RAW LAYER (ya existe)                         │
│                                                                    │
│  raw_yango.transactions_raw ─── raw_yango.orders_raw              │
│  raw_yango.mv_revenue_day ─── raw_yango.mv_orders_day             │
│  raw_yango.mv_source_coverage_day                                 │
│  raw_yango.api_ingestion_run ─── raw_yango.api_ingestion_page_*   │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   COVERAGE LAYER (nuevo)                          │
│                                                                    │
│  ops.yango_revenue_coverage_log  ←  compara Yango vs CT           │
│  ops.revenue_source_cutover_config ←  reglas de corte por park    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                   SERVING LAYER (nuevo)                           │
│                                                                    │
│  ops.revenue_canonical_day_fact                                   │
│    revenue_canonical       = selected source per cutover rules    │
│    revenue_source_badge    = 'YANGO_API' | 'CT_BRIDGE'            │
│    revenue_yango_api       = from mv_revenue_day                  │
│    revenue_ct_bridge       = from real_business_slice_day_fact    │
└────────────────────────┬─────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                     UI LAYER (existente)                          │
│                                                                    │
│  Omniview V2 / Vs Proy: lee de ops.revenue_canonical_day_fact    │
│  (migración futura: CF-H2G Serving Integration)                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. INGESTION RUNTIME ARCHITECTURE

### 6.1 Principios de Diseño

| Principio | Implementación |
|-----------|---------------|
| **Background job** | No bloquea UI. Ejecuta como tarea programada o bajo scheduler. |
| **Multipark concurrente** | Un worker por park+día. Parks independientes se ejecutan en paralelo. |
| **Cursor pagination secuencial** | Dentro de un mismo park+día, páginas se recorren secuencialmente (no paralelizable por cursor). |
| **Idempotencia** | `INSERT ... ON CONFLICT (park_id, order_id, raw_payload_hash) DO NOTHING`. |
| **Resume capability** | `api_ingestion_page_checkpoint` permite retomar desde última página exitosa si falla. |
| **Rate limit guard** | Backoff mandatorio de 3s para todas las goroutines si se detecta 429. |
| **No fallback monstruoso** | Si Yango API falla, se reporta `PARTIAL`; no se inventa revenue. |
| **No max_pages en scheduled** | max_pages solo para debugging manual. Scheduled ingiere hasta agotar cursor. |

### 6.2 Workers y Concurrencia

| Parámetro | Valor | Notas |
|-----------|-------|-------|
| `max_concurrency` inicial seguro | 3 | Un worker por park activo. Si hay 1 park = 1 worker secuencial. |
| Parks por worker | 1 park completo (todos los endpoints) | El worker recorre orders → transactions → driver_profiles secuencialmente |
| Paralelismo entre parks | Sí | Parks independientes pueden ingerirse en paralelo |
| Paralelismo entre endpoints | Sí (dentro de un park) | Orders y transactions pueden consultarse en paralelo |
| Paralelismo dentro de un endpoint | No | Cursor pagination es secuencial por diseño |

### 6.3 Flujo de Ingesta por Park+Día

```
1. Crear api_ingestion_run (status='running')
2. Resolver credenciales desde api_park_credentials_registry → .env
3. Si credenciales faltan → FAIL park, continuar con siguiente
4. Para cada endpoint_group [orders, transactions]:
   a. page = 1, cursor = None
   b. while cursor is not None or page == 1:
      - POST endpoint con cursor y date filter
      - Si 429 → backoff 3s, reintentar hasta 2 veces
      - Si 401/403 → FAIL park completo (no reintentar)
      - Si 5xx → exponential backoff 1s/2s/4s, max 3 reintentos
      - Si timeout → reintentar hasta 2 veces
      - Parsear response, calcular SHA256 de cada payload
      - INSERT ... ON CONFLICT DO NOTHING (batch)
      - Guardar api_ingestion_page_checkpoint
      - cursor = response.next_cursor
      - page += 1
   c. Actualizar métricas en api_ingestion_run
5. Marcar api_ingestion_run como 'completed' o 'partial' o 'failed'
```

### 6.4 Políticas de Error

| Escenario | Comportamiento |
|-----------|---------------|
| **Credencial inválida (401/403)** | FAIL park. No reintentar. Loggear error. Continuar con siguiente park. |
| **Park falla** | Marcar run como 'partial'. Otros parks continúan. |
| **API devuelve parcial (timeout mid-pagination)** | Guardar checkpoint de última página exitosa. Run marcado como 'partial'. Próximo run puede retomar. |
| **Rate limit (429)** | Backoff 3s mandatorio. Max 2 reintentos. Si persiste, FAIL endpoint para ese park. |
| **Timeout por página** | Reintentar 2 veces. Si persiste, guardar checkpoint, marcar 'partial'. |
| **Error de parseo JSON** | Loggear error, skip payload individual. No detener ingesta. |
| **Todos los parks fallan** | Marcar run como 'failed'. |

### 6.5 Frecuencia de Ingesta

| Modo | Ventana | Trigger |
|------|---------|---------|
| **Scheduled (diario)** | date_from = ayer, date_to = ayer | Scheduler (ej. 5-min tick del Lima Growth scheduler o cron) |
| **Catch-up** | Rango multi-día | Manual o vía scheduler con flag catch_up |
| **Historical backfill** | >30 días | Script dedicado (CF-H2H). Rate-limited, baja prioridad. |

### 6.6 Estimación de Tiempos (Lima, 1 park)

| Endpoint | Páginas/día | Tiempo/página | Total |
|----------|------------|---------------|-------|
| Orders | ~25 | ~20s | ~500s (~8 min) |
| Transactions | ~5-10 | ~1-2s | ~10-20s |
| Driver Profiles | ~2-3 | ~2-3s | ~6-9s |
| **Total secuencial** | | | **~9 min** |
| **Total concurrente** (orders ∥ transactions) | | | **~8 min** |

### 6.7 Script de Ingesta Existente

`backend/scripts/ingest_yango_raw_landing.py` (1279 líneas) ya implementa la mayoría de esta arquitectura:
- Modo `--dry-run` por defecto
- `--confirm-live` para escritura real
- Paginación cursor-based
- Deduplicación SHA256 + ON CONFLICT DO NOTHING
- Registro en `api_ingestion_run` + `api_ingestion_page_checkpoint`
- Errores en `ingestion_errors`
- Soporte multipark

**Lo que falta para CF-H2B:**
1. Asegurar que el script funciona sin `max_pages` en modo scheduled
2. Concurrencia entre endpoints (orders ∥ transactions)
3. Integración con scheduler existente (Lima Growth scheduler o nuevo)
4. Refresh automático de MVs post-ingesta

---

## 7. CUTOVER CONTRACT (2026-06-01)

### 7.1 Definición del Corte

| Aspecto | Regla |
|---------|-------|
| **Fecha de corte** | 2026-06-01 00:00:00 (timezone del park) |
| **Antes del corte** (`< 2026-06-01`) | Revenue fuente: `CT_BRIDGE` (`comision_empresa_asociada` + proxy) |
| **Desde el corte** (`>= 2026-06-01`) | Revenue fuente: `YANGO_API` (`Partner fee for trip`) si coverage certificado |
| **Transición** | No se mezclan fuentes sin `source_badge`. Cada registro de revenue declara su origen. |

### 7.2 Reglas de Promoción

Para que un park+día use Yango API como fuente canónica de revenue:

```
TODAS las condiciones deben cumplirse:

1. source_date >= cutover_date (2026-06-01)
2. orders_coverage_pct >= 99%   (orders Yango / orders CT)
3. revenue_present_pct >= 99%   (trips con Partner fee / total trips Yango)
4. park_coverage_pct >= 100%    (todos los parks activos tienen datos Yango)
5. currency_consistency = 100%  (toda transacción en misma moneda esperada)
6. yango_ingestion_status = 'completed'  (ingesta del día finalizó sin errores)
```

Si **cualquier** condición falla para un park+día específico:
- `revenue_source_badge = 'CT_BRIDGE'` (usa fuente legacy)
- `coverage_status = 'INSUFFICIENT'` en `yango_revenue_coverage_log`
- No se promueve Yango API para ese park+día

### 7.3 Badges de Revenue Source

| Badge | Significado | Cuándo se asigna |
|-------|-------------|------------------|
| `YANGO_API` | Revenue desde Yango Fleet API, cobertura certificada | Todas las condiciones de promoción cumplidas |
| `YANGO_API_PARTIAL` | Revenue desde Yango API pero cobertura < 100% | Algunas condiciones fallan marginalmente (ej. 95-99%) |
| `CT_BRIDGE` | Revenue desde CT bridge (`comision_empresa_asociada` + proxy) | Pre-corte o coverage insuficiente |
| `MISSING` | Sin revenue de ninguna fuente | Ni Yango ni CT tienen datos para ese park+día |

### 7.4 Tratamiento de Métricas No-Revenue

| Métrica | Fuente pre-corte | Fuente post-corte | Notas |
|---------|-----------------|-------------------|-------|
| **Revenue** | CT bridge | **Yango API** (si coverage OK) | Promovido en CF-H2A |
| **Trips/Orders** | CT bridge | CT bridge | Se mantiene en CT hasta certificar trip coverage con Yango (futuro) |
| **Active Drivers** | CT bridge | CT bridge | Se mantiene en CT hasta certificar driver coverage con Yango (futuro) |
| **GMV** | CT bridge (`gmv_passenger_paid`) | Yango API (`Cash + Card`) | Disponible si transactions cubren |
| **Avg Ticket** | CT bridge (`revenue/trips`) | CT bridge | Requiere normalización cross-fuente |

### 7.5 Thresholds Sugeridos

| Threshold | Valor | Justificación |
|-----------|-------|---------------|
| Orders coverage mínimo | 99% | Alineado con estándar de calidad de datos OV2 |
| Revenue presente mínimo | 99% | Garantiza que casi todos los trips tienen Partner fee |
| Park coverage mínimo | 100% | Todos los parks activos deben estar cubiertos |
| Currency consistency | 100% | No se permite mezcla de monedas en revenue canónico |
| Delta diario máximo aceptable | 5% | Entre Yango revenue y CT revenue para validación |
| Delta agregado máximo | 3% | Sobre ventana de 30 días |

---

## 8. RECONCILIATION PLAN

### 8.1 Fuentes Comparadas

| Fuente A | Fuente B | Qué se compara |
|----------|----------|---------------|
| `raw_yango.transactions_raw` (Partner fee) | `ops.real_business_slice_day_fact.revenue_yego_net` | Revenue diario |
| `raw_yango.orders_raw` (completed) | `ops.real_business_slice_day_fact.trips_completed` | Trips completados |
| `raw_yango.driver_profiles_raw` (active) | `ops.real_business_slice_day_fact.active_drivers` | Drivers activos |
| `raw_yango.transactions_raw` (Cash + Card) | `ops.real_business_slice_day_fact` (GMV fields) | GMV |

### 8.2 Dimensiones de Comparación

| Dimensión | Grain | Método |
|-----------|-------|--------|
| **Day** | Fecha operativa × park | Comparación directa |
| **Park** | Park ID | Agrupación por park |
| **Business Slice** | business_slice_name | Requiere mapeo order → slice vía CT bridge |
| **City** | city | Agrupación geográfica |
| **Country** | country | Agrupación geográfica |

### 8.3 Métricas de Reconciliación

| Métrica | Fórmula | Umbral de alerta |
|---------|---------|------------------|
| Completed orders match | `yango_orders_completed / ct_trips_completed * 100` | < 99% |
| Active drivers match | `yango_drivers / ct_drivers * 100` | < 95% |
| Revenue delta | `ABS(yango_revenue - ct_revenue) / ct_revenue * 100` | > 5% (diario), > 3% (agregado) |
| Avg ticket delta | `ABS(yango_avg_ticket - ct_avg_ticket) / ct_avg_ticket * 100` | > 10% |
| Missing orders | `ct_trips - yango_orders` | > 10 orders/día |
| Duplicate orders | `COUNT(*) - COUNT(DISTINCT order_id)` en Yango | > 0 |
| Currency mismatch | transactions con currency != esperada | > 0 |
| Stale park credentials | parks con last_ingestion > 48h | Cualquiera |

### 8.4 Clasificación de Resultados

| Clasificación | Condición | Significado |
|---------------|-----------|-------------|
| `MATCH` | Delta = 0% | Fuentes idénticas |
| `MINOR_DELTA` | Delta < 5% | Variación aceptable |
| `MAJOR_DELTA` | Delta 5-20% | Requiere investigación |
| `CT_ONLY` | Dato en CT, no en Yango | Posible gap de cobertura API |
| `YANGO_ONLY` | Dato en Yango, no en CT | Posible order no capturado por bridge |
| `MISSING_BOTH` | Sin dato en ninguna fuente | Park/día sin datos |

### 8.5 Scripts de Reconciliación Existentes

| Script | Propósito | Estado |
|--------|-----------|--------|
| `backend/scripts/reconcile_yango_api_revenue_vs_ct.py` | Revenue reconciliation | Existente |
| `backend/scripts/reconcile_yango_raw_vs_ct.py` | Raw data reconciliation | Existente |
| `backend/scripts/reconcile_yango_mv_vs_ct.py` | MV reconciliation | Existente |
| `backend/scripts/analyze_revenue_api_vs_ct_14d.py` | Análisis multi-día | Existente |
| `backend/scripts/discover_yango_revenue_fields.py` | Revenue field discovery | Existente |
| `backend/scripts/audit_yango_raw_coverage.py` | Coverage audit | Existente |

**Para CF-H2D (Coverage Observatory):** Unificar estos scripts en un pipeline de reconciliación diario automatizado con alertas.

---

## 9. RISK REGISTER

| ID | Riesgo | Probabilidad | Impacto | Severidad | Mitigación |
|----|--------|-------------|---------|-----------|------------|
| **R1** | API lenta (~20s/página orders) causa timeouts en ingesta diaria | MEDIUM | MEDIUM | **MEDIUM** | Background job asíncrono. Timeout 20s por página configurable. Si orders excede ventana, usar solo transactions para revenue. |
| **R2** | Rate limits no observados pero posibles en producción | LOW | HIGH | **MEDIUM** | Rate limit guard con backoff 3s. Sin rate limits en 14 días de probe = margen de seguridad. |
| **R3** | Credenciales inválidas o rotadas sin actualizar .env | MEDIUM | HIGH | **HIGH** | Health check pre-ingesta. Alerta si credencial 401/403. No reintentar. |
| **R4** | Park mapping incompleto entre park_id de Yango y dim_park de CT | MEDIUM | HIGH | **HIGH** | Auditoría de mapping park_id en `api_park_credentials_registry` vs `dim.dim_park`. Completar antes de cutover. |
| **R5** | Revenue field ambiguo — múltiples categorías Partner fee | LOW | MEDIUM | **LOW** | Solo `Partner fee for trip` certificada. `Partner fee for order return` requiere validación adicional. Mapeo de categorías documentado en OV2-A.3. |
| **R6** | Currency/money units — `amount` es string fixed-point, requiere parseo | LOW | HIGH | **MEDIUM** | `amount` en API es string (ej. `"-0.3940"`). Parseo a NUMERIC validado en código existente. |
| **R7** | Pagination truncation — cursor expira o se pierde mid-ingesta | LOW | MEDIUM | **LOW** | `api_ingestion_page_checkpoint` permite resume. Date-range filters mantienen ventanas cortas. |
| **R8** | Partial day ingestion — ingesta se corta antes de completar | MEDIUM | MEDIUM | **MEDIUM** | Run marcado como 'partial'. Resume capability vía checkpoint. Siguiente scheduled run completa. |
| **R9** | Duplicate orders — mismo order_id con distinto payload hash | LOW | LOW | **LOW** | UNIQUE(park_id, order_id, raw_payload_hash). Si cambia payload = nueva fila (trazabilidad). |
| **R10** | Historical backfill cost — backfill de 2026-01 a 2026-05 requiere ~150 días × ~8 min/día | HIGH | LOW | **MEDIUM** | Backfill solo si es necesario. Pre-corte revenue sigue siendo CT bridge. Backfill paralelo multipark reduce tiempo. |
| **R11** | UI consuming mixed sources — confusion si revenue cambia de fuente sin badge claro | MEDIUM | HIGH | **HIGH** | `revenue_source_badge` visible en UI. Tooltip explica origen. No mezclar sin badge. |
| **R12** | Yango API cambia schema de respuesta | LOW | HIGH | **MEDIUM** | `raw_payload` JSONB preserva respuesta completa. Schema version en cada registro. Monitor de cambios de schema. |
| **R13** | `Partner fee for trip` no cubre 100% de trips (transactions sin order_id) | MEDIUM | MEDIUM | **MEDIUM** | Revenue presente threshold = 99%. Si < 99%, mantener CT bridge como fuente. |

---

## 10. IMPLEMENTATION ROADMAP

### 10.1 Fases Propuestas

```
CF-H2A [AHORA]  Yango Revenue Source Architecture      ← ESTE DOCUMENTO
    │
CF-H2B           Raw Landing Foundation                
    │            - Verificar/crear seed data en api_park_credentials_registry
    │            - Asegurar ingesta diaria funciona sin max_pages
    │            - Concurrencia orders ∥ transactions
    │            - Refresh automático de MVs post-ingesta
    │
CF-H2C           Concurrent Ingestion Runtime           
    │            - Workers por park con ThreadPoolExecutor
    │            - Resume capability vía page_checkpoint
    │            - Rate limit guard global
    │            - Integración con scheduler
    │
CF-H2D           Coverage Observatory                  
    │            - Pipeline diario de cobertura → ops.yango_revenue_coverage_log
    │            - Dashboard de cobertura (park × día × métrica)
    │            - Alertas de coverage degradation
    │
CF-H2E           Revenue Canonical Mapper              
    │            - Poblar ops.revenue_canonical_day_fact
    │            - Aplicar reglas de cutover por park
    │            - Asignar revenue_source_badge
    │            - Reconciliación automatizada diaria
    │
CF-H2F           Cutover Certification                 
    │            - Validar thresholds en 30+ días de datos
    │            - Certificar coverage ≥ 99% para todos los parks
    │            - GO/NO-GO formal para cutover
    │
CF-H2G           Serving Integration                   
    │            - Omniview V2 / Vs Proy lee de revenue_canonical_day_fact
    │            - Badge de fuente en UI
    │            - Rollback plan si Yango API falla
    │
CF-H2H           Historical Backfill (opcional)        
                 - Backfill Yango API 2026-01-01 → 2026-05-31
                 - Solo si se requiere consistencia histórica
                 - Baja prioridad
```

### 10.2 Detalle por Fase

#### CF-H2B — Raw Landing Foundation

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Asegurar que la ingesta raw de Yango API funciona en modo scheduled sin truncamiento |
| **Archivos** | `backend/scripts/ingest_yango_raw_landing.py`, `backend/app/services/yango_raw_ingestion_service.py`, `backend/app/repositories/raw_yango_repository.py` |
| **Tablas** | `raw_yango.*` (existentes) |
| **Endpoints** | `/v1/parks/orders/list`, `/v2/parks/transactions/list` |
| **Tests** | Dry-run para Lima 2026-06-10, verify records > 0, verify no max_pages truncation |
| **GO** | Ingesta diaria completa sin errores para 3 días consecutivos |

#### CF-H2C — Concurrent Ingestion Runtime

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Runtime de ingesta concurrente con resume capability y rate limit guard |
| **Archivos** | Nuevo: `backend/app/services/yango_revenue_ingestion_orchestrator.py` |
| **Tablas** | `raw_yango.api_ingestion_run`, `raw_yango.api_ingestion_page_checkpoint` (existentes) |
| **Endpoints** | Orders ∥ Transactions concurrente |
| **Tests** | Ingesta concurrente 3 parks (si existen). Resume desde checkpoint tras interrupción simulada. |
| **GO** | Concurrente completa en < 10 min para Lima. Resume funciona. Rate limit guard testeado. |

#### CF-H2D — Coverage Observatory

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Observatorio de cobertura diaria Yango vs CT |
| **Archivos** | Nuevo: `backend/app/services/yango_coverage_service.py`, `backend/scripts/compute_yango_coverage.py` |
| **Tablas** | `ops.yango_revenue_coverage_log` (nueva), `ops.revenue_source_cutover_config` (nueva) |
| **Endpoints** | Solo lectura de DB |
| **Tests** | Coverage log poblado para 14 días. Métricas calculadas correctamente. |
| **GO** | Coverage diario visible. Alertas configuradas. |

#### CF-H2E — Revenue Canonical Mapper

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Mapear revenue a `ops.revenue_canonical_day_fact` con reglas de cutover |
| **Archivos** | Nuevo: `backend/app/services/revenue_canonical_mapper.py` |
| **Tablas** | `ops.revenue_canonical_day_fact` (nueva) |
| **Endpoints** | Solo lectura de DB + escritura a serving fact |
| **Tests** | 30 días de revenue mapeados. Badge correcto por fecha/park. Reconciliación automatizada. |
| **GO** | 30 días consecutivos con badge correcto. Delta revenue < 5% diario. |

#### CF-H2F — Cutover Certification

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Certificar que Yango API cumple thresholds para cutover |
| **Archivos** | `backend/scripts/certify_yango_revenue_cutover.py` |
| **Tablas** | Todas las anteriores |
| **Endpoints** | N/A (validación) |
| **Tests** | Coverage >= 99% por 30 días. Revenue presente >= 99%. Currency 100%. Park coverage 100%. |
| **GO** | Todos los thresholds cumplidos. Certificación firmada. GO formal para cutover. |

#### CF-H2G — Serving Integration

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Omniview V2 / Vs Proy consume revenue desde canonical fact con badge |
| **Archivos** | `backend/app/routers/omniview.py`, `backend/app/services/omniview_cascade_service.py` |
| **Tablas** | `ops.revenue_canonical_day_fact` → cascade a week/month |
| **Endpoints** | API de Omniview V2 |
| **Tests** | UI muestra revenue con source badge. Rollback funciona. |
| **GO** | Revenue en UI trazable a Yango API o CT bridge. Sin regresión en OV2. |

#### CF-H2H — Historical Backfill

| Aspecto | Detalle |
|---------|---------|
| **Objetivo** | Backfill opcional de revenue Yango para 2026-01-01 → 2026-05-31 |
| **Archivos** | `backend/scripts/backfill_yango_revenue_historical.py` |
| **Tablas** | `raw_yango.transactions_raw`, `ops.revenue_canonical_day_fact` |
| **Endpoints** | `/v2/parks/transactions/list` con fechas históricas |
| **Tests** | Revenue histórico cargado sin afectar serving facts existentes |
| **GO** | Backfill completado y reconciliado. Baja prioridad — solo si se requiere. |

---

## 11. GO / NO-GO

### 11.1 GO Criteria for CF-H2A

| # | Criterio | Estado |
|---|----------|--------|
| 1 | Arquitectura definida (este documento) | **PASS** |
| 2 | Corte 2026-06-01 definido con reglas explícitas | **PASS** |
| 3 | Tablas propuestas con schemas completos | **PASS** |
| 4 | Ingestion runtime propuesto con políticas de error | **PASS** |
| 5 | Reconciliation plan definido con métricas | **PASS** |
| 6 | Riesgos documentados con mitigaciones | **PASS** |
| 7 | No se implementó nada (solo diseño) | **PASS** |
| 8 | No se abrió Diagnostic Engine | **PASS** |
| 9 | Governance validation completa | **PASS** |

### 11.2 Classification

**CF_H2A_ARCHITECTURE_READY**

### 11.3 Next Phase

**CF-H2B — Raw Landing Foundation**

Objetivo: Verificar y estabilizar la ingesta raw de Yango API en modo scheduled, asegurando que funciona sin `max_pages`, con concurrencia entre endpoints, y con refresh automático de materialized views post-ingesta.

### 11.4 Próximo Prompt Sugerido

```
MOTOR: Control Foundation
FASE: CF-H2B — Raw Landing Foundation

OBJETIVO:
Verificar y estabilizar la ingesta raw de Yango Fleet API como base
para revenue canonicalization, siguiendo la arquitectura definida en
CF-H2A (docs/omnibuilder_v2/CF_H2A_YANGO_REVENUE_SOURCE_ARCHITECTURE.md).

TAREAS:
1. Auditar api_park_credentials_registry: cantidad de parks, credenciales activas
2. Ejecutar ingesta dry-run para Lima 2026-06-10 y verificar:
   - Orders se ingieren sin max_pages truncation
   - Transactions se ingieren completamente
   - api_ingestion_page_checkpoint funciona
3. Verificar refresh de raw_yango.mv_revenue_day post-ingesta
4. Documentar gaps encontrados (si los hay)
5. Preparar seed data para ops.revenue_source_cutover_config (park Lima, cutover 2026-06-01)

NO implementar serving facts.
NO tocar Omniview V2.
NO modificar fact tables existentes.
```

---

## 12. FIRMA

| Campo | Valor |
|-------|-------|
| **Diseñado por** | CF-H2A Yango Revenue Source Architecture |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `CF_H2A_ARCHITECTURE_READY` |
| **Próxima fase** | CF-H2B — Raw Landing Foundation |
| **Dependencias** | OV2 Close (2ab32e9), OV2-A.3/A.4 (revenue certification), raw_yango schema (migration 181+) |
| **Bloquea** | Diagnostic Engine (hasta que CF-H2 cierre) |
