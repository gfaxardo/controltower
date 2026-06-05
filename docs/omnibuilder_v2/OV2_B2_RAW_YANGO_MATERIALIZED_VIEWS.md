# OV2-B.2 — RAW YANGO MATERIALIZED VIEWS

> **Fase:** OV2-B.2 — Materialized Views  
> **Fecha:** 2026-06-05  
> **Schema:** `raw_yango`  
> **Propósito:** Crear las primeras materialized views sobre raw_yango para convertir payloads crudos de Yango Fleet API en facts operativos auditables.

---

## 1. MVs CREADAS

| MV | Grain | Rows | Distinct Days | Duplicates |
|----|-------|------|---------------|------------|
| `mv_orders_day` | (park_id, operational_date) | 1 | 1 | 0 |
| `mv_transactions_day` | (park_id, operational_date, category_name, currency_code) | 14 | 1 | 0 |
| `mv_revenue_day` | (park_id, operational_date, currency_code) | 1 | 1 | 0 |
| `mv_driver_profiles_snapshot` | (park_id, driver_profile_id, snapshot_date) | 300 | 1 | 0 |
| `mv_source_coverage_day` | (park_id, operational_date) | 2 | 2 | 0 |

### mv_orders_day
Métricas: orders_total, orders_finished, orders_cancelled, unique_drivers_with_orders, unique_cars_with_orders, total_mileage, avg_price, median_price, gmv_sum, first/last order timestamps.

### mv_transactions_day
Métricas por categoría y moneda: transaction_count, amount_sum, amount_abs_sum, positive/negative_amount_sum, unique_drivers/orders.

### mv_revenue_day
Clasificación de revenue: revenue_yego_partner_fee, gmv_cash_card, platform_fee, platform_fee_vat, promo_compensation, other_adjustments, revenue_per_order.

### mv_driver_profiles_snapshot
DISTINCT ON por (park, driver, date) — último snapshot del día. work_status, car_id, car_category, has_contract_issue.

### mv_source_coverage_day
Coverage unificada: has_orders, has_transactions, has_driver_profiles, counts, revenue_candidate_count, coverage_status (full/partial/empty).

---

## 2. REFRESH

Migration 187 aplicada. Refresh script funcional:
```bash
python -m scripts.refresh_raw_yango_mvs --mv all
```

Resultados: 5/5 OK, ~8.5s total.

---

## 3. AUDIT

0 duplicates en todas las MVs. 0% null_rate en operational_date/snapshot_date. MVs correctamente indexadas con UNIQUE constraints.

---

## 4. RECONCILIATION

| Métrica | MV (raw_yango) | CT | Delta |
|---------|---------------|-----|-------|
| Trips | 1,500 | 14,213 | -89.4% |
| Revenue | 51.59 | 5,832.27 | -99.1% |

**Nota:** La muestra de raw_yango es limitada (5 páginas de órdenes, 5 de transacciones). CT tiene datos completos para el día. La cobertura completa requiere ingesta sin límite de páginas.

---

## 5. RIESGOS

| Riesgo | Severidad |
|--------|-----------|
| Muestra muy pequeña para reconciliación seria | HIGH |
| source_coverage_day muestra 2 días por backfill de operational_date (un día con NULL) | LOW |
| REFRESH CONCURRENTLY requiere índice único (ya creado) | LOW |

---

## 6. GO / NO-GO PARA OV2-B.3

**GO.** Las 5 MVs están creadas, refrescadas y auditadas. La arquitectura raw → MV está funcionando. Para OV2-B.3 (Serving Facts), se requiere:
- Ingesta completa de un día (sin límite de páginas) para reconciliación representativa
- Calibración de revenue coefficients por business slice

---

## 7. GOVERNANCE CHECK

| Regla | Estado |
|-------|--------|
| No UI tocada | PASS |
| No Omniview V1 tocado | PASS |
| No serving actual tocado | PASS |
| No trips_2025/trips_2026 reemplazados | PASS |
| Raw_yango como capa paralela | PASS |
| MVs en schema raw_yango | PASS |
| Sin backfill masivo | PASS |
| Sin credenciales expuestas | PASS |

---

## 8. FIRMA

| Campo | Valor |
|-------|-------|
| **Implementado por** | OV2-B.2 Materialized Views |
| **Fecha** | 2026-06-05 |
| **Próximo paso** | OV2-B.3 — Serving Facts from MVs |
| **Estado** | `GO` — MVs operativas, requiere ingesta completa antes de serving |
