# OV2-B.3 — YANGO SERVING FACTS READINESS

> **Fase:** OV2-B.3 — Serving Facts from Raw Landing
> **Fecha:** 2026-06-05
> **Schema:** `raw_yango`
> **Propósito:** Certificar que las MVs derivadas de raw_yango están listas como serving facts para Omniview V2.

---

## 1. MVs CREADAS

| MV | Grain | Rows | Days |
|----|-------|------|------|
| `mv_orders_day` | (park_id, order_date) | 2 | 2 |
| `mv_transactions_day` | (park_id, transaction_date, category, currency) | 36 | 2 |
| `mv_revenue_day` | (park_id, revenue_date, currency) | 2 | 2 |
| `mv_driver_profiles_snapshot` | (park_id, driver_profile_id) | 800 | — |
| `mv_source_coverage_day` | (park_id, coverage_date) | 2 | 2 |

### Source Lineage

```
Yango Fleet API
  → raw_yango.orders_raw         → mv_orders_day
  → raw_yango.transactions_raw   → mv_transactions_day, mv_revenue_day
  → raw_yango.driver_profiles_raw → mv_driver_profiles_snapshot
  → raw_yango.api_ingestion_run  → mv_source_coverage_day
```

### Revenue Semantic Rule

`revenue_candidate_amount = SUM(ABS(amount)) WHERE category_name = 'Partner fee for trip'`

Validado en OV2-A.4 (CERTIFIED_REVENUE_AUDIT). No mezclar con Service fee, GMV, ni otros ajustes.

### Coverage Rule

| Status | Condición |
|--------|-----------|
| FULL | orders + transactions + revenue_candidate > 0 |
| PARTIAL | orders OR transactions > 0 pero no ambos |
| ORDERS_ONLY | solo orders |
| TRANSACTIONS_ONLY | solo transactions |
| MISSING | sin datos |

---

## 2. REFRESH RESULT

5/5 OK. Elapsed: ~8.7s. Report: `mv_refresh_summary.md`

---

## 3. AUDIT RESULT

0 duplicates, 0 null keys, 0 null dates. Revenue per order within expected range.

---

## 4. RECONCILIATION

| Metric | MV | CT | Delta | Status |
|--------|-----|-----|-------|--------|
| Orders completed | 4,500 | 14,213 | -68.3% | API_PARTIAL |
| Revenue (partner fee) | 1,612.32 | 5,832.27 | -72.4% | CT_MULTI_SLICE |
| Revenue per order | **0.408** | **0.410** | **-0.7%** | **MATCH** |
| Revenue per txn | 0.418 | — | — | — |

### Classification

- **API_PARTIAL**: La API devuelve solo órdenes de un park. CT incluye múltiples business slices.
- **CT_MULTI_SLICE**: Revenue absoluto no comparable porque el scope de CT es mayor.
- **MATCH (per-unit)**: Revenue per order coincide dentro de 1%. Es la métrica relevante para validación.

---

## 5. LIMITACIONES

| Limitación | Impacto |
|-----------|---------|
| API cubre 1 park vs CT múltiples slices | Revenue absoluto no comparable; per-unit sí |
| Solo 2 días de datos | Sin serie temporal suficiente para tendencias |
| Driver profiles sin nombres reales | Solo IDs + work_status disponibles |
| API latencia alta (~100s/página) | Ingesta completa requiere partitioned resume |

---

## 6. GO / NO-GO PARA OV2-B.4

### GO

Serving facts están listos para alimentar Omniview V2:

- 5 MVs operativas con refresh <10s
- Revenue per order validado vs CT (-0.7%)
- Coverage status FULL para los días ingeridos
- 0 duplicados, 0 errores
- Source lineage documentado
- Revenue semantic rule clara

### Condiciones para OV2-B.4

1. Acumular más días de cobertura (ideal: 7+)
2. Completar transacciones pendientes (10/12 particiones)
3. NO tocar Omniview V1 durante la transición
4. OV2 UI debe leer de estas MVs, no de la API directa

---

## 7. GOVERNANCE

| Regla | Estado |
|-------|--------|
| No UI tocada | PASS |
| No Omniview V1 tocado | PASS |
| No serving actual ops.* tocado | PASS |
| No trips_2025/trips_2026 reemplazados | PASS |
| No credenciales expuestas | PASS |
| Todo aditivo | PASS |

---

## 8. FIRMA

| Campo | Valor |
|-------|-------|
| **Certificado por** | OV2-B.3 Serving Facts Readiness |
| **Fecha** | 2026-06-05 |
| **Próximo paso** | OV2-B.4 — Omniview V2 UI shadow mode |
| **Estado** | `SERVING_READY` — MVs certificadas, revenue validado |
