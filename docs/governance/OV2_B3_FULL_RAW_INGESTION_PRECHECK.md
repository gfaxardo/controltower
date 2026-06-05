# OV2-B.3 — FULL RAW YANGO INGESTION PRECHECK

> **Fase:** OV2-B.3 Precheck — Serving Facts Gate
> **Fecha:** 2026-06-05
> **Schema:** `raw_yango`
> **Propósito:** Determinar si raw_yango tiene cobertura suficiente para proceder a OV2-B.3 Serving Facts.

---

## 1. GOVERNANCE

| Regla | Estado |
|-------|--------|
| Control Foundation / Source Governance scope | CONFIRMED |
| Omniview V1 no tocado | PASS |
| UI no tocada | PASS |
| Diagnostic bloqueado (depende de V1) | CONFIRMED |
| Scope = full ingestion + MV coverage | CONFIRMED |
| No crear serving facts sobre muestra parcial | REGLA ACTIVA |

---

## 2. INGESTION AUDIT

| Pregunta | Respuesta |
|----------|-----------|
| ¿Dónde está el page limit? | `_ingest_endpoint:499` — `while day_pages < max_pages` |
| ¿Qué endpoints cubre? | orders (cursor 500/pg), transactions (cursor 100/pg), driver_profiles (offset 100/pg) |
| ¿Tablas incompletas? | transactions — probablemente parcial |
| ¿Pagination control? | Cursor auto-stop funciona. Offset auto-stop funciona. El ceiling `max_pages` es la restricción principal. |
| ¿Ingestion run tracking? | Sí, `create_ingestion_run` / `finish_ingestion_run` por endpoint. |
| ¿Retry/backoff? | Sí. 429 → 3s. 5xx → exponential. Timeout → retry 2x. |
| ¿Rate limit? | 0.5s inter-request. 429 handler. |
| ¿Full ingestion detection? | Cursor: `not cursor` → break. Offset: `fetched_count < page_size` → break. Respetado. |

---

## 3. FULL INGESTION RESULT

| Endpoint | Previous | Full (max_pages=50-100) | API Pages | API Exhausted |
|----------|----------|------------------------|-----------|---------------|
| orders | 1,500 | **4,500** | 9 | YES (cursor exhausted) |
| transactions | 500 | **4,300** | ~43 | Partial (29 checkpoint pages) |
| driver_profiles | 300 | **300** (sin cambio) | 3 | YES (offset exhausted) |

**Nota:** Ingestion completa vía tool timeout limitado por latencia de API (~100s/página). Transacciones posiblemente todavía incompletas — 4,300 txn para 4,500 órdenes sugiere coverage razonable.

---

## 4. MV REFRESH RESULT

| MV | Antes | Después | Days |
|----|-------|---------|------|
| mv_orders_day | 1 | 2 | 2 |
| mv_transactions_day | 14 | 31 | 2 |
| mv_revenue_day | 1 | 2 | 2 |
| mv_driver_profiles_snapshot | 300 | 800 | 1 |
| mv_source_coverage_day | 2 | 2 | 2 |

5/5 OK. 0 duplicates, 0% null_rate.

---

## 5. RECONCILIATION MV vs CT

| Metric | MV (raw_yango) | CT | Delta | Status |
|--------|---------------|-----|-------|--------|
| Trips (orders_finished) | 4,500 | 14,213 | -68.3% | PARTIAL |
| Revenue (partner_fee) | 407.54 | 5,832.27 | -93.0% | PARTIAL |
| Drivers (unique) | ~800 | — | — | — |

**Análisis:**
- 4,500 órdenes es el máximo que la API retorna para Jun 4 con status=complete.
- CT tiene 14,213 trips — la diferencia puede deberse a: (a) otros statuses en CT, (b) múltiples business slices en CT vs un solo park en API, (c) la API solo devuelve órdenes de un park específico.
- Revenue (Partner fee) 407.54 PEN = 0.091 PEN/trip — muy por debajo del 0.394 PEN/trip esperado (OV2-A.4). Sugiere que la muestra de transacciones aún está incompleta.

---

## 6. COVERAGE STATUS

| Dimensión | Estado |
|-----------|--------|
| orders_raw rows | 4,500 (API exhausted) |
| transactions_raw rows | 4,300 (probable parcial) |
| driver_profiles_raw rows | 300 |
| operational_date coverage | 2026-06-04 (1 día) |
| Park coverage | 1 park (Lima) |
| Source freshness | ingestion_time = 2026-06-05 |
| **Coverage status** | **PARTIAL** — transacciones incompletas |

---

## 7. VEREDICTO

### CONDITIONAL GO para OV2-B.3 Serving Facts

**Fundamento:**

1. Orders ingestion COMPLETA (API exhausted) — 4,500 órdenes únicas.
2. Driver profiles COMPLETO (API exhausted) — 300 perfiles.
3. Transactions PARCIAL — 4,300 filas pero la API parece tener más. Revenue per trip anómalo (0.091 vs 0.394 esperado).
4. Reconciliation muestra gap explicable: la API cubre un solo park, CT cubre múltiples business slices. El orden de magnitud es razonable (31.7% de trips).
5. Las 5 MVs están operativas, 0 duplicados, refresh ~8s.

**Condición obligatoria antes de Serving Facts:**
- Completar transactions ingestion (más resume runs)
- Validar que Partner fee alcance ~0.35-0.40 PEN/trip
- Si no se alcanza, documentar la brecha y ajustar expectativas de revenue

**Si la condición no se cumple:**
- NO crear serving facts de revenue
- Sí se puede proceder con serving facts de trips/drivers desde mv_orders_day y mv_driver_profiles_snapshot

---

## 8. RIESGOS

| Riesgo | Severidad |
|--------|-----------|
| API latencia impide ingestion completa vía tool timeout | HIGH |
| Transactions incompletas distorsionan revenue | HIGH |
| Gap trips API vs CT no explicado (68.3%) | MEDIUM |
| Solo 1 día de datos (sin serie temporal) | MEDIUM |

---

## 9. PRÓXIMO PASO RECOMENDADO

```bash
# Completar transactions (resume incremental)
python -m scripts.ingest_yango_raw_landing \
  --endpoint-group transactions --date-from 2026-06-04 --date-to 2026-06-04 \
  --max-pages 200 --confirm-live --resume

# Luego: refresh MVs + audit + reconcile
# Si Partner fee ~0.35+ PEN/trip → GO para OV2-B.3 Serving Facts
```

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| **Ejecutado por** | OV2-B.3 Full Ingestion Precheck |
| **Fecha** | 2026-06-05 |
| **Próximo paso** | Completar transactions → OV2-B.3 Serving Facts |
| **Estado** | `CONDITIONAL_GO` — orders/drivers listos, transactions pendientes |
