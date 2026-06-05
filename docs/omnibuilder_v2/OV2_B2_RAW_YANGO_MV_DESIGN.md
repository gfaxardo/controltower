# OV2-B.2 — RAW YANGO MATERIALIZED VIEWS DESIGN

> **Fase:** OV2-B.2 — Materialized Views
> **Fecha:** 2026-06-05
> **Schema:** `raw_yango`
> **Propósito:** Crear las primeras materialized views sobre raw_yango para convertir payloads crudos de Yango Fleet API en facts operativos auditables.

---

## 1. ARQUITECTURA

```
raw_yango.orders_raw ─────────┐
raw_yango.transactions_raw ───┼──→ MATERIALIZED VIEWS ──→ (futuro) SERVING FACTS
raw_yango.driver_profiles_raw ┘
```

Las MVs son el paso intermedio entre RAW y SERVING. Agregan, deduplican y normalizan los datos para consumo operativo.

---

## 2. MV 1: mv_orders_day

### Grain
`(park_id, operational_date)`

### Source
`raw_yango.orders_raw`

### Columns & Metrics

| Columna | Tipo | Derivación |
|---------|------|-----------|
| `park_id` | TEXT | Directo |
| `operational_date` | DATE | Directo |
| `orders_total` | BIGINT | COUNT(*) |
| `orders_finished` | BIGINT | COUNT(*) WHERE order_status = 'complete' |
| `orders_cancelled` | BIGINT | COUNT(*) WHERE order_status = 'cancelled' |
| `orders_other_status` | BIGINT | COUNT(*) WHERE order_status NOT IN ('complete', 'cancelled') |
| `unique_drivers_with_orders` | BIGINT | COUNT(DISTINCT driver_profile_id) |
| `unique_cars_with_orders` | BIGINT | COUNT(DISTINCT car_id) |
| `unique_categories` | BIGINT | COUNT(DISTINCT category) |
| `total_mileage` | NUMERIC | SUM(mileage) |
| `first_order_at` | TIMESTAMPTZ | MIN(order_created_at) |
| `last_order_at` | TIMESTAMPTZ | MAX(order_ended_at) |
| `avg_price` | NUMERIC | AVG(price) |
| `median_price` | NUMERIC | PERCENTILE_CONT(0.5) price |
| `gmv_sum` | NUMERIC | SUM(price) |
| `refreshed_at` | TIMESTAMPTZ | now() |

### Index
- UNIQUE: `(park_id, operational_date)`
- `ix_mv_orders_day_date`: `(operational_date)`

---

## 3. MV 2: mv_transactions_day

### Grain
`(park_id, operational_date, category_name, currency_code)`

### Source
`raw_yango.transactions_raw`

### Columns & Metrics

| Columna | Tipo | Derivación |
|---------|------|-----------|
| `park_id` | TEXT | Directo |
| `operational_date` | DATE | Directo |
| `category_name` | TEXT | Directo |
| `currency_code` | TEXT | COALESCE(currency_code, 'PEN') |
| `transaction_count` | BIGINT | COUNT(*) |
| `amount_sum` | NUMERIC | SUM(amount) |
| `amount_abs_sum` | NUMERIC | SUM(ABS(amount)) |
| `positive_amount_sum` | NUMERIC | SUM(amount) WHERE amount > 0 |
| `negative_amount_sum` | NUMERIC | SUM(amount) WHERE amount < 0 |
| `unique_drivers` | BIGINT | COUNT(DISTINCT driver_profile_id) |
| `unique_orders` | BIGINT | COUNT(DISTINCT order_id) |
| `refreshed_at` | TIMESTAMPTZ | now() |

### Index
- UNIQUE: `(park_id, operational_date, category_name, currency_code)`

---

## 4. MV 3: mv_revenue_day

### Grain
`(park_id, operational_date, currency_code)`

### Source
`raw_yango.transactions_raw`

### Revenue Categories Classification

| MV Column | Source WHERE |
|-----------|-------------|
| `revenue_yego_partner_fee` | `category_name = 'Partner fee for trip'` |
| `gmv_cash_card` | `category_name IN ('Cash', 'Card payment')` |
| `platform_fee` | `category_name = 'Service fee for trip'` |
| `platform_fee_vat` | `category_name = 'Service fee, VAT'` |
| `promo_compensation` | `category_name = 'Promo code compensation'` |
| `other_adjustments` | NOT IN any of the above |

### Columns & Metrics

| Columna | Tipo | Derivación |
|---------|------|-----------|
| `park_id` | TEXT | Directo |
| `operational_date` | DATE | Directo |
| `currency_code` | TEXT | COALESCE(currency_code, 'PEN') |
| `revenue_yego_partner_fee` | NUMERIC | SUM(ABS(amount)) WHERE cat = 'Partner fee for trip' |
| `revenue_yego_partner_fee_count` | BIGINT | COUNT(*) WHERE cat = 'Partner fee for trip' |
| `gmv_cash_card` | NUMERIC | SUM(amount) WHERE cat IN ('Cash', 'Card payment') |
| `gmv_cash_card_count` | BIGINT | COUNT(*) WHERE cat IN ('Cash', 'Card payment') |
| `platform_fee` | NUMERIC | SUM(amount) WHERE cat = 'Service fee for trip' |
| `platform_fee_count` | BIGINT | COUNT(*) WHERE cat = 'Service fee for trip' |
| `platform_fee_vat` | NUMERIC | SUM(amount) WHERE cat = 'Service fee, VAT' |
| `platform_fee_vat_count` | BIGINT | COUNT(*) WHERE cat = 'Service fee, VAT' |
| `promo_compensation` | NUMERIC | SUM(amount) WHERE cat = 'Promo code compensation' |
| `promo_compensation_count` | BIGINT | COUNT(*) WHERE cat = 'Promo code compensation' |
| `other_adjustments` | NUMERIC | SUM(amount) WHERE cat NOT IN classified |
| `other_adjustments_count` | BIGINT | COUNT(*) WHERE cat NOT IN classified |
| `total_txn_count` | BIGINT | COUNT(*) |
| `revenue_per_order` | NUMERIC | revenue_yego_partner_fee / NULLIF(orders_finished, 0) |
| `refreshed_at` | TIMESTAMPTZ | now() |

### Index
- UNIQUE: `(park_id, operational_date, currency_code)`

---

## 5. MV 4: mv_driver_profiles_snapshot

### Grain
`(park_id, driver_profile_id, snapshot_date)`

Latest snapshot per driver per day. Uses DISTINCT ON to get the most recent record per driver per day.

### Source
`raw_yango.driver_profiles_raw`

### Columns & Metrics

| Columna | Tipo | Derivación |
|---------|------|-----------|
| `park_id` | TEXT | Directo |
| `driver_profile_id` | TEXT | Directo |
| `snapshot_date` | DATE | operational_date |
| `work_status` | TEXT | Most recent work_status |
| `car_id` | TEXT | Most recent car_id |
| `car_category` | TEXT | Most recent car_category |
| `has_contract_issue` | BOOLEAN | Most recent has_contract_issue |
| `raw_payload_hash` | TEXT | Most recent raw_payload_hash |
| `api_fetched_at` | TIMESTAMPTZ | MAX(api_fetched_at) |
| `refreshed_at` | TIMESTAMPTZ | now() |

### Index
- UNIQUE: `(park_id, driver_profile_id, snapshot_date)`

---

## 6. MV 5: mv_source_coverage_day

### Grain
`(park_id, operational_date)`

### Sources
Joins all three raw tables to produce a single coverage row per park per day.

### Columns & Metrics

| Columna | Tipo | Derivación |
|---------|------|-----------|
| `park_id` | TEXT | FROM orders/transactions/drivers |
| `operational_date` | DATE | FROM orders/transactions/drivers |
| `has_orders` | BOOLEAN | orders_count > 0 |
| `has_transactions` | BOOLEAN | transactions_count > 0 |
| `has_driver_profiles` | BOOLEAN | driver_profiles_count > 0 |
| `orders_count` | BIGINT | COUNT from orders_raw |
| `transactions_count` | BIGINT | COUNT from transactions_raw |
| `driver_profiles_count` | BIGINT | COUNT from driver_profiles_raw |
| `revenue_candidate_count` | BIGINT | COUNT from transactions WHERE Partner fee for trip |
| `revenue_candidate_amount` | NUMERIC | SUM(ABS(amount)) from Partner fee for trip |
| `coverage_status` | TEXT | 'full' / 'partial' / 'empty' |
| `refreshed_at` | TIMESTAMPTZ | now() |

### Index
- UNIQUE: `(park_id, operational_date)`

---

## 7. REFRESH STRATEGY

- All MVs support `REFRESH MATERIALIZED VIEW CONCURRENTLY`
- Refresh order: orders → transactions → revenue → driver_profiles → source_coverage
- Refresh script handles dependency order automatically
- Dry-run shows which MVs would be refreshed
- Elapsed time and row counts logged per refresh

---

## 8. GOVERNANCE CHECK

| Rule | Status |
|------|-------|
| Schema isolation (raw_yango) | PASS |
| No serving facts touched | PASS |
| No UI touched | PASS |
| No Omniview V1 touched | PASS |
| No trips_2025/trips_2026 replaced | PASS |
| Read-only on raw tables | PASS |
| Downgrade clean (DROP MV) | PASS |

---

## 9. FIRMA

| Campo | Valor |
|-------|-------|
| Diseñado por | OV2-B.2 MV Design |
| Fecha | 2026-06-05 |
| Próximo paso | Migration 187 + refresh/audit/reconcile scripts |
