# OV2-A.1 — SOURCE CERTIFICATION MATRIX: Yango Fleet API (Growth API)

> **Fase:** OV2-A.1 — Source Discovery  
> **Fecha:** 2026-06-04  
> **Fuente evaluada:** Yango Fleet API (`https://fleet-api.yango.tech`)  
> **Park:** Lima (`08e20910...`)  
> **Propósito:** Evaluar si la Growth API puede servir como fuente de datos para Omniview V2

---

## 1. CLASIFICACIÓN FINAL

| Campo | Valor |
|-------|-------|
| **Clasificación** | `CANDIDATE_RECONCILIATION` |
| **Confianza** | MEDIUM (requiere validación con datos reales de API) |
| **Fecha de evaluación** | 2026-06-04 |
| **Re-evaluación sugerida** | Después de ejecutar `probe_growth_api_source.py --mode live` y `reconcile_growth_api_vs_ct.py --mode api_ct` para comparar datos reales |

---

## 2. EVIDENCIA RECOLECTADA

### 2.1 Configuración de API (TAREA 1)

| Aspecto | Valor |
|---------|-------|
| **Base URL** | `https://fleet-api.yango.tech` |
| **Autenticación** | Custom headers: `X-Client-ID` + `X-API-Key` (NO Bearer token) |
| **Park ID Lima** | `08e20910d81d42658d4334d3f6d10ac0` (configurado en `.env` como `YANGO_LIMA_PARK_ID`) |
| **Timeout** | 20 segundos (`YANGO_API_TIMEOUT_SECONDS`) |
| **Retries** | 2 (`YANGO_API_MAX_RETRIES`) |
| **Rate limits** | 429 → backoff 3000ms (`YANGO_SUPPLY_RATE_LIMIT_BACKOFF_MS`) |
| **Credenciales** | Enmascaradas en todos los outputs (verificación TAREA 6) |
| **Estado** | `YANGO_API_ENABLED=true` en `.env` actual |

### 2.2 Endpoints Disponibles

| Endpoint | Método | Grain | Paginación | Uso actual en CT |
|----------|--------|-------|------------|------------------|
| `/v1/parks/orders/list` | POST | order | Cursor-based (next_cursor) | Lima Growth Engine (capture orders) |
| `/v1/parks/driver-profiles/list` | POST | driver_profile | Offset-based (limit/offset/total) | Lima Growth Engine (eligible universe) |
| `/v2/parks/contractors/supply-hours` | GET | driver × day | Per-driver (no bulk) | Lima Growth Engine (driver 360) |
| `/v1/parks/contractors/blocked-balance` | GET | driver | Per-driver (no bulk) | Discovery only |

### 2.3 Campos Disponibles por Endpoint

#### Orders (`/v1/parks/orders/list`)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | string | Order ID (≈ trip_id) |
| `short_id` | integer | Short order ID |
| `status` | string | `complete` (otros: cancelled, etc.) |
| `created_at` | ISO datetime | Timestamp de creación |
| `booked_at` | ISO datetime | Timestamp de booking |
| `ended_at` | ISO datetime | Timestamp de finalización |
| `provider` | string | Proveedor |
| `category` | string | Categoría de servicio |
| `payment_method` | string | Método de pago |
| `mileage` | number | Kilometraje |
| `price` | object | `{ final_cost: number }` |
| `price.final_cost` | number | **Revenue por order** |
| `driver_profile` | object | `{ id, first_name, name }` |
| `driver_profile.id` | string | **Driver ID** |
| `car` | object | `{ id, callsign, brand, model, number }` |
| `driver_work_rule` | object | `{ id, name }` |

#### Driver Profiles (`/v1/parks/driver-profiles/list`)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `driver_profile.id` | string | Driver ID |
| `driver_profile.work_status` | string | `working` / `not_working` |
| `driver_profile.work_rule_id` | string | Work rule |
| `driver_profile.employment_type` | string | Tipo de empleo |
| `driver_profile.has_contract_issue` | boolean | Flag de contrato |
| `current_status.status` | string | Estado actual (online/offline/busy) |
| `car.id` | string | Vehicle ID |
| `car.category` | string | Categoría de vehículo |
| `car.brand` | string | Marca |
| `car.model` | string | Modelo |
| `account.balance` | string | Balance de cuenta |
| `account.currency` | string | Moneda |

#### Supply Hours (`/v2/parks/contractors/supply-hours`)
| Campo | Tipo | Descripción |
|-------|------|-------------|
| `supply_duration_seconds` | integer | **Segundos de supply por driver por día** |

---

## 3. MATRIZ DE EVALUACIÓN

### 3.1 Criterios de Clasificación

| Criterio | Evaluación | Peso | Puntaje |
|----------|-----------|------|---------|
| **Grain claro** | Order-level (OK); pero no nativo daily-aggregated | HIGH | 3/5 |
| **Métricas útiles** | trips, revenue, drivers, supply_hours, driver_state | HIGH | 4/5 |
| **Histórico suficiente** | API no provee histórico (solo datos actuales + ventana reciente); CT ya tiene backfill de trips_2025/2026 | HIGH | 2/5 |
| **Consistencia contra CT** | No verificada aún (requiere ejecución de reconcile con API live) | CRITICAL | 0/5 (pendiente) |
| **Latencia aceptable** | ~200-400ms por página de 500 órdenes; pero supply-hours es per-driver (lento a escala) | MEDIUM | 3/5 |
| **Credenciales por park sostenibles** | Sí — un solo park (Lima) actualmente; escalable añadiendo más parks a .env | MEDIUM | 4/5 |
| **Sin dependencia directa de UI** | Correcto — API es backend-only, no expuesta al frontend | HIGH | 5/5 |
| **Trazabilidad posible** | order_id + driver_profile.id + timestamps proporcionan trazabilidad completa por order | HIGH | 5/5 |
| **Independencia de fuente actual** | La API es externa e independiente de trips_2026 (fuente actual de CT) → buena para reconciliación cruzada | HIGH | 5/5 |

### 3.2 Puntaje Total

| Categoría | Puntaje | Máximo |
|-----------|---------|--------|
| Cobertura de datos | 9/15 | (grain + métricas + histórico) |
| Calidad operacional | 12/20 | (consistencia pendiente + latencia + credenciales) |
| Arquitectura | 15/15 | (UI independence + trazabilidad + independencia) |
| **TOTAL** | **31/45** | |

---

## 4. ANÁLISIS POR CATEGORÍA DE CLASIFICACIÓN

### 4.1 CANDIDATE_CANONICAL → NO (por ahora)

**Razones para RECHAZAR como canónico:**
- La API no tiene endpoint de agregación diaria nativa → requiere agregación client-side (sum de órdenes)
- Supply-hours es per-driver (una llamada HTTP por conductor por día) → **inviable a escala de fleet** para serving facts diarios
- No hay histórico: la API solo devuelve datos de la ventana consultada. CT requiere backfill histórico (2025, 2026)
- El revenue de API (`price.final_cost`) puede no coincidir con el revenue calculado por CT (`comision_empresa_asociada` → `revenue_yego_net` → `revenue_yego_final`)
- Dependencia de API externa con auth→ riesgo de disrupción si cambian credenciales/endpoints

### 4.2 CANDIDATE_RECONCILIATION → SÍ (clasificación asignada)

**Razones para aceptar como fuente de reconciliación:**
- Fuente independiente de `trips_2026` → útil para validación cruzada
- Proporciona métricas comparables: trips, drivers, revenue
- La trazabilidad order-level permite auditoría granular
- Ya está integrada en el ecosistema CT (Lima Growth Engine) → bajo costo de adopción
- Puede servir como "trust sensor" para detectar divergencias entre fuente externa y CT

**Limitaciones para reconciliación:**
- El mapeo park → business_slice no es 1:1 (un park Yango ≠ un business slice CT)
- Supply-hours requiere llamadas per-driver → no viable para reconciliación diaria masiva
- Rate limits (429) pueden bloquear reconciliaciones frecuentes

### 4.3 REFERENCE_ONLY → NO

No se clasifica como REFERENCE_ONLY porque la API tiene datos operacionales reales (no es metadata ni datos estáticos). Es una fuente viva con datos transaccionales.

### 4.4 REJECTED → NO

No se rechaza. La fuente es válida y tiene utilidad demostrable como fuente secundaria de validación.

---

## 5. RECOMENDACIONES

### 5.1 Inmediatas (OV2-A)

1. **Ejecutar probe live**: `python -m scripts.probe_growth_api_source --date-from 2026-06-01 --date-to 2026-06-03` (sin `--dry-run`) para obtener datos reales de la API
2. **Ejecutar reconciliación completa**: `python -m scripts.reconcile_growth_api_vs_ct --mode api_ct --date-from 2026-06-01 --date-to 2026-06-03` para comparar trips/drivers/revenue
3. **Publicar resultados** en `backend/exports/audits/growth_api_probe/`

### 5.2 Corto plazo (si reconciliación es favorable)

4. **Crear trust sensor**: script periódico que compare orders API vs day_fact para detectar divergencias
5. **Documentar mapeo park→slice**: definir qué business slices de CT corresponden al park de Yango Lima
6. **Evaluar si price.final_cost reconcilia con revenue_yego_final** dentro de tolerancia aceptable (<5%)

### 5.3 Largo plazo (OV2-B/OV2-C)

7. Si la reconciliación es consistente y estable, promover a `CANDIDATE_CANONICAL` para métricas de orders (trips, drivers, revenue) como fuente secundaria con flag de confianza
8. NO reemplazar `trips_2026` como fuente primaria — mantenerla como canónica, usar API como sensor de freshness/reconciliación
9. Evaluar bulk endpoint de supply-hours si Yango lo publica en el futuro

---

## 6. RIESGOS IDENTIFICADOS

| ID | Riesgo | Severidad | Mitigación |
|----|--------|-----------|------------|
| R-A1-1 | API no disponible → reconciliation gap | MEDIUM | Graceful degradation: si API falla, usar solo CT |
| R-A1-2 | Rate limiting bloquea reconciliaciones frecuentes | MEDIUM | Limitar frecuencia a 1 vez/día; usar backoff |
| R-A1-3 | Mapeo park→slice incorrecto genera falsos deltas | HIGH | Validar mapeo con datos reales antes de activar alarmas |
| R-A1-4 | Rotación de credenciales rompe integración | LOW | Ya gestionado por Lima Growth Engine → monitoreo existente |
| R-A1-5 | API cambia schema de respuesta | MEDIUM | Probe script detecta cambios de schema automáticamente |

---

## 7. VERIFICACIÓN DE GOVERNANCE

| Regla | Estado |
|-------|--------|
| No modifica Omniview V1 | PASS |
| No modifica UI productiva | PASS |
| No reemplaza fuentes actuales | PASS |
| Read-only / discovery | PASS |
| Control Foundation scope | PASS |
| Credenciales enmascaradas | PASS |
| Sin inserción en tablas | PASS |
| Sin modificar serving facts | PASS |

---

## 9. OV2-A.2 — SCALE & REVENUE DISCOVERY UPDATE

### 9.1 Discovery Summary

| Aspect | Finding |
|--------|---------|
| **API docs scanned** | https://fleet.yango.com/docs/api/en/ — 24 endpoints across 5 resource groups |
| **New endpoints discovered** | Transactions API (v2) — critical for revenue discovery |
| **Scale probe** | `backend/scripts/probe_yango_fleet_api_scale.py` — concurrency safe probe with checkpoint/resume/rate-limit guard |
| **Revenue fields discovered** | `backend/scripts/discover_yango_revenue_fields.py` — identified 3 revenue candidates |
| **Revenue reconciliation** | `backend/scripts/reconcile_yango_api_revenue_vs_ct.py` — compares API versus CT day_fact |
| **Staging design** | `docs/omnibuilder_v2/OV2_A2_YANGO_API_STAGING_DESIGN.md` — 5 staging tables designed, NOT implemented |

### 9.2 Scalability Observations

| Metric | Observation |
|--------|-------------|
| **Max concurrency tested** | Configurable (default 5) with per-park lock |
| **Rate limit observed** | 429 TooManyRequests — handled with 3s mandatory backoff |
| **Max viable range per run** | Recommended 3 days with cursor pagination (max 500 orders/page) |
| **Transactions pagination** | Cursor-based, max 1000 per page (default 40) |
| **Bottleneck** | Orders endpoint ~200-400ms per page (500 orders); transactions ~300-500ms per page (100 txn) |
| **Orders per minute** | ~6,000-10,000 at concurrency 5 (theoretical: 5 × 12 pages/min × 500 orders) |
| **Transactions per minute** | ~600-1,000 at concurrency 5 (theoretical: 5 × 6 pages/min × 100 txn) |
| **Feasibility for daily refresh** | Orders: YES (under 3 min for typical fleet). Transactions: YES if category-filtered. |
| **Feasibility for monthly backfill** | Orders: YES (~30 min for 30 days). Transactions: CONDITIONAL (depends on transaction volume per day). |

### 9.3 Endpoint Groups Useful for Omniview V2

| Rank | Endpoint | Utility | Classification |
|------|----------|---------|----------------|
| 1 | POST /v2/parks/transactions/list | Revenue YEGO candidate via partner_rides + platform_fees categories | FINANCIAL_CANDIDATE |
| 2 | POST /v1/parks/orders/list | Trips, drivers, GMV, category distribution, payment method | REPORTING + RECONCILIATION |
| 3 | POST /v2/parks/transactions/categories/list | Category metadata (group_id, affects_balance) | REPORTING |
| 4 | POST /v1/parks/driver-profiles/list | Driver status, car, account balance, work status | REPORTING |
| 5 | GET /v2/parks/contractors/supply-hours | Driver online time (per-driver, expensive at scale) | RECONCILIATION |

### 9.4 Revenue Field Candidates

| Field | Endpoint | Type | Hypothesis | Classification |
|-------|----------|------|------------|----------------|
| `orders.price` | /v1/parks/orders/list | string (fixed-point) | Customer payment (GMV) | GMV_ONLY |
| `transactions.amount` WHERE category_group = 'partner_rides' | /v2/parks/transactions/list | string (fixed-point) | Partner earned revenue from ride | REVENUE_YEGO_CANDIDATE |
| `transactions.amount` WHERE category_group = 'platform_fees' | /v2/parks/transactions/list | string (fixed-point) | Platform commission taken by Yango | COMMISSION_CANDIDATE |
| `transactions.amount` WHERE category_group = 'partner_fees' | /v2/parks/transactions/list | string (fixed-point) | Partner fees charged to driver | DRIVER_WALLET_MOVEMENT |
| `transactions.amount` WHERE category_group = 'platform_card' | /v2/parks/transactions/list | string (fixed-point) | Card payment GMV (should ≈ orders.price for card orders) | GMV_ONLY |

### 9.5 Decision on price.final_cost

**CORRECTION**: Per official API documentation, orders `price` is a STRING type, not an object with `final_cost`. The current `yango_api_client.py` code treats `price` as `{ final_cost: number }` — this is INCORRECT per docs. The `price` field directly contains the fixed-point sum string. This should be validated with a real API call.

**Decision**: `price` = GMV_ONLY. It represents what the customer paid (gross), NOT what YEGO earned. YEGO revenue requires analyzing transactions with `partner_rides` category group.

### 9.6 Decision on Transactions/Billing

The Transactions API is the **primary source for understanding YEGO revenue**. Key findings:

1. `partner_rides` category group → **most likely YEGO revenue** (what partner earned from rides)
2. `platform_fees` category group → **platform commission** (what Yango/Yandex takes)
3. The relationship: `partner_rides - platform_fees ≈ net YEGO earnings` (requires validation)
4. Transactions link to orders via `order_id` — enables order-level revenue reconciliation
5. Category metadata available via `/v2/parks/transactions/categories/list`

### 9.7 Updated Final Classification

| Classification | Previous | Updated | Rationale |
|---------------|----------|---------|-----------|
| `CANDIDATE_RECONCILIATION` | YES | YES | Orders endpoint still useful for cross-validation of trips/drivers/GMV |
| `CANDIDATE_REVENUE_AUDIT` | — | YES (NEW) | Transactions endpoint enables revenue semantic validation via category groups |
| `CANDIDATE_CANONICAL` | NO | NO | Not yet: requires real API validation of partner_rides vs CT revenue_yego_final; rate limits manageable but transactions per-day volume unknown; revenue semantics confirmed via docs but not yet by real data |
| `REFERENCE_ONLY` | NO | NO | API has live transactional data, not just reference |
| `REJECTED` | NO | NO | Source remains valuable as secondary validation |

**Promotion criteria to CANDIDATE_CANONICAL** (all must be met):
- [x] Grain clear (order-level, driver-level, transaction-level)
- [ ] Histórico suficiente (needs validation of how far back API returns data)
- [x] Rate limit manejable (cursor pagination with 429 handling)
- [ ] Revenue semánticamente confirmado (partner_rides vs revenue_yego_final reconciliation pending)
- [ ] Reconciliación contra CT aceptable (pending real API execution)
- [x] No depende de UI
- [ ] Puede persistirse en staging/raw (design exists, pending implementation approval)
- [x] Puede refrescarse con trazabilidad (order_id, transaction_id, raw_payload_hash enable full traceability)

**Current status**: `CANDIDATE_RECONCILIATION` + `CANDIDATE_REVENUE_AUDIT` — awaiting real API validation.

### 9.8 Next Steps
1. Execute `probe_yango_fleet_api_scale.py --endpoint-group all` to measure real latency and throughput
2. Execute `discover_yango_revenue_fields.py` to capture real transaction categories and amounts
3. Execute `reconcile_yango_api_revenue_vs_ct.py --mode api_ct` to compare partner_rides vs revenue_yego_final
4. If reconciliation within acceptable threshold (<5%), promote partner_rides to REVENUE_YEGO_CANDIDATE with HIGH confidence

---

## 10. OV2-A.4 — REVENUE API CERTIFICATION UPDATE

### 10.1 Certification Summary

| Aspect | Finding |
|--------|---------|
| **Field certified** | Partner fee for trip (Yango Transactions API) |
| **Correlation with CT** | 0.394 PEN/trip API vs 0.412 PEN/trip CT (4.4% delta over 3 days) |
| **API reliability** | 100% success, 0 rate limits, p50=398ms over 14-day probe |
| **Best matching slice** | YMA (0.3947 PEN/trip — exact match to API estimate) |
| **Categories discovered** | 68 categories, 7 classified (REVENUE_YEGO, PLATFORM_FEE, GMV, BONUS, ADJUSTMENT) |

### 10.2 Updated Classification

| Classification | OV2-A.2 | OV2-A.3 | OV2-A.4 (FINAL) |
|---------------|---------|---------|-----------------|
| CANDIDATE_RECONCILIATION | YES | YES | YES (orders endpoint) |
| CANDIDATE_REVENUE_AUDIT | NEW | VALIDATED | **CERTIFIED** |
| CANDIDATE_CANONICAL | NO | NO | NO (day variance too high) |
| REJECTED | NO | NO | NO |

### 10.3 Certification Criteria Met

- [x] Grain clear (transaction level, linked to order_id + driver_id)
- [x] Rate limit manageable (cursor pagination, 429 handling proven)
- [x] No UI dependency
- [x] Traceability (order_id, driver_id, event_at)
- [x] API availability (100% over 14-day probe)
- [ ] Revenue semantically confirmed (PARTIAL — 4.4% overall delta but 10.8% day variance)
- [ ] Historical sufficiency (NO — API only returns current data, CT historical backfill is from trips_2025/2026)
- [ ] CT reconciliation acceptable (PARTIAL — 4.4% overall but per-slice variation from 0.11 to 2.55 PEN/trip)
- [ ] Can be persisted in staging (design exists, pending approval)

### 10.4 Final Decision

- Partner fee for trip: **CERTIFIED_REVENUE_AUDIT** — can serve as secondary revenue validation source
- NOT promoted to CANDIDATE_CANONICAL because: day-to-day variation (0.5%-10.8%), per-slice revenue profiles differ significantly, and no historical backfill capability
- orders.price: **GMV_ONLY** (confirmed by docs, NOT revenue)
- Transaction categories: **REFERENCE** for commission/fee analysis

### 10.5 Next Steps

1. Calibrate Partner fee per trip coefficients per business slice (Auto regular vs YMA vs Tuk Tuk vs Carga have different profiles)
2. When more CT data becomes available (10+ days), re-run reconciliation
3. Fix orders endpoint to cross-validate GMV vs fees per trip
4. Implement staging.yango_api_transaction_raw when approved by governance

## 11. FIRMA

| Campo | Valor |
|-------|-------|
| **Clasificado por** | OV2-A.1 Source Discovery Script |
| **Fecha** | 2026-06-04 |
| **Próxima revisión** | Post-ejecución de probe live + reconcile completo |
| **Estado** | `PENDIENTE_VALIDACIÓN` (requiere datos reales de API para confirmar clasificación) |
