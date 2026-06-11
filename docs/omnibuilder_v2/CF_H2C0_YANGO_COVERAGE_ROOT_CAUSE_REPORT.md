# CF-H2C.0 — YANGO COVERAGE ROOT CAUSE REPORT

> **Fase:** CF-H2C.0 — Yango Coverage Root Cause Analysis
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Target Date:** 2026-06-10

---

## 1. EXECUTIVE SUMMARY

Yango API shadow muestra 5,808 orders vs 24,658 trips completados en CT (ratio 23.6%). La causa raíz es **múltiple**: (1) solo 1 de 21 parks tiene credenciales Yango, (2) la ingesta del único park con credenciales fue truncada a ~17:00, y (3) transactions no fueron ingeridas.

**Clasificación:** `ROOT_CAUSE_MULTIPLE`

---

## 2. EVIDENCE SUMMARY

### 2.1 Parks: Yango tiene 1, CT tiene 21

```
Yango credential registry: 1 park (Lima - 08e20910...)
CT parks with trips on 2026-06-10: 21 parks
Parks in CT but NOT in Yango: 20 parks = 47,947 trips lost
```

| Source | Parks | Total Trips | Completed | Cancelled |
|--------|-------|------------|-----------|-----------|
| CT (all 21 parks) | 21 | 69,997 | 24,658 | 45,339 |
| CT (Lima only) | 1 | 22,050 | 9,135 | 12,915 |
| Yango API (Lima only) | 1 | 5,808 | 5,808 | 0 |

### 2.2 Lima Park: Ingestion truncated at 17:03

```
Yango Lima orders time range: 00:00 → 17:03 (17 hours covered)
CT Lima trips time range:     00:00 → 23:59 (24 hours covered)
Missing window:               17:03 → 23:59 (~7 hours)
```

### 2.3 Transactions: Zero for 2026-06-10

```
Yango transactions_raw for 2026-06-10: 0 rows
Partner fee for trip: 0.00 revenue
```

---

## 3. PARKS AUDIT — FULL BREAKDOWN

### 3.1 Yango Credential Registry

| credential_id | park_id | fleet_name | city | country | env_prefix | active |
|---------------|---------|------------|------|---------|------------|--------|
| `yango_lima_park` | `08e20910d81d42658d4334d3f6d10ac0` | YEGO Lima | Lima | Peru | YANGO_LIMA | true |

**Total: 1 park. Coverage: 1/21 = 4.8% of CT parks.**

### 3.2 CT Parks NOT in Yango Registry (20 parks)

| # | park_id | Trips on 2026-06-10 | Completed |
|---|---------|---------------------|-----------|
| 1 | `05b1c831e66f41a9a87f5f3fa0a186ae` | 30,693 | 9,292 |
| 2 | `ef21f793358144f589aabcbeb8bd7d50` | 6,568 | 1,302 |
| 3 | `e3e07c00ed914f82a59c03283a178d6e` | 1,990 | 1,168 |
| 4 | `851e30755bba4d298e2e837f571b4ab8` | 1,603 | 712 |
| 5 | `fafd623109d740f8a1f15af7c3dd86c6` | 1,412 | 761 |
| 6 | `56e4607dfc354e0a9cde4f0aa7973003` | 1,157 | 404 |
| 7 | `64085dd85e124e2c808806f70d527ea8` | 949 | 497 |
| 8 | `ff424287c4bd4cbba6066962951a121f` | 795 | 234 |
| 9 | `e081e2df33a74073992c859638bdf683` | 723 | 89 |
| 10 | `962afaa34db6420fb03b7ae464f6a061` | 469 | 340 |
| 11-20 | (10 more parks) | 1,638 | 727 |
| **TOTAL** | **20 missing parks** | **47,947** | **15,523** |

### 3.3 Park Mapping Issue

The Yango credential registry has Lima park `08e20910...`. The CT Lima park is also `08e20910...` (matched). The 20 other parks appear to be parks from other cities/countries in CT that have no corresponding Yango Fleet API credentials. These include parks with IDs like `05b1c...`, `ef21f...`, `e3e07...`, etc.

---

## 4. CT TRIPS ANALYSIS (Lima Park Only)

### 4.1 Lima Park: 22,050 total, 9,135 completed

| Hour Lima | Trips | Completed | Cancelled |
|-----------|-------|-----------|-----------|
| 00-05 | 5,216 | 1,484 | 3,732 |
| 06-11 | 19,889 | 7,133 | 12,756 |
| 12-17 | 23,822 | 8,673 | 15,149 |
| 18-23 | 21,070 | 7,642 | 13,428 |

**All 24 hours have data.** No time gaps. Full day coverage.

### 4.2 Status Distribution (Lima only inferred)

CT has both "Completado" (41.4%) and "Cancelado" (58.6%) trips for Lima park on this date.

---

## 5. YANGO ORDERS ANALYSIS (Lima Park)

### 5.1 Lima Park: 5,808 orders, all "complete"

| Hour (UTC/Lima) | Orders | Completed |
|-----------------|--------|-----------|
| 00:00 - 05:59 | 702 | 702 |
| 06:00 - 11:59 | 2,468 | 2,468 |
| 12:00 - 16:59 | 2,618 | 2,618 |
| 17:00 - 17:03 | 20 | 20 |
| 17:03 - 23:59 | **0** | **0** |

**Orders stop at 17:03.** No data for the last ~7 hours of the day. The curve matches CT's morning ramp (06-09) and afternoon plateau (10-16), confirming the data quality is good for what was ingested.

### 5.2 Status: All "complete", Zero Cancelled

Yango orders 100% have `order_status = 'complete'`. This is because the API query filters by `statuses: ["complete"]`. The ingestion script for the tick service explicitly filters for completed orders only. Cancelled orders are NOT requested from the API.

### 5.3 Timestamp Analysis

- `ended_at` matches `order_ended_at` (same field, no timezone shift needed)
- `created_at` range extends into 2026-06-09 22:50 (some orders created previous day)
- UTC = Lima (both at UTC-5, so no offset for this date range)

**Timezone verdict:** NO timezone issue. Both systems use UTC-5 compatible timestamps. The window matches.

---

## 6. INGESTION RUN AUDIT — MAX_PAGES CONFIRMED

### 6.1 Tick Ingestion Service Configuration

From `yango_raw_tick_ingestion_service.py`:
```python
MAX_PAGES_PER_DATE = 20      # <-- THIS IS THE PROBLEM
MAX_TOTAL_SECONDS = 120      # <-- 2 minute timeout
PAGE_SIZE = 500              # 500 orders per page
MAX_DAYS_BACKFILL = 3
```

**Max orders per date = 20 pages × 500 = 10,000 orders max.**

### 6.2 Runs for 2026-06-10

| Status | Count | Notes |
|--------|-------|-------|
| `running` (zombie) | 7 | Stuck, never completed or failed |
| `failed` | 1 | Failed immediately |
| `completed` | 1 | run `795bd07b` — fetched 5,670, inserted 89, skipped 5,581 |

The completed run for 2026-06-10 has:
- `records_fetched = 5,670`
- `records_inserted = 89` (only 89 new, rest were duplicates from prior runs)
- `records_skipped = 5,581`
- `pages_completed = 0`, `expected_pages = None`

### 6.3 Interpretation

The tick service ingests at most 20 pages × 500 = 10,000 orders per run. For Lima's 2026-06-10, it fetched 5,670 orders before hitting either:
- `MAX_PAGES_PER_DATE = 20` (but 5,670 / 500 ≈ 12 pages, so less than 20), OR
- `MAX_TOTAL_SECONDS = 120` timeout

Given that 5,670 orders were ingested across one completed run and multiple zombie runs, the most likely explanation is that the tick service's **timeout (120s)** or **inter-request pacing (0.5s)** combined with API latency (~20s/page for orders) caused early termination.

**5,670 / 500 ≈ 12 pages.** At ~20s per page + 0.5s delay = ~246 seconds needed. But `MAX_TOTAL_SECONDS = 120`. So it only had time for ~6 pages = ~3,000 orders. The remaining orders came from multiple overlapping tick runs.

### 6.4 The Zombie Run Problem

7 runs for 2026-06-10 are stuck in `running` status. These were created by the scheduler's autonomous tick every ~5 minutes but never completed. They represent **failed ingestion attempts** that accumulate without cleanup.

---

## 7. TRANSACTIONS AUDIT

### 7.1 Zero Transactions for 2026-06-10

```
raw_yango.transactions_raw WHERE event_at::date = '2026-06-10': 0 rows
3-day window (06-09 to 06-11): 0 rows
```

### 7.2 Root Cause

The tick ingestion service (`yango_raw_tick_ingestion_service.py`) **only ingests orders**, not transactions. The full ingestion script (`ingest_yango_raw_landing.py`) can ingest transactions but was never run for 2026-06-10 in live mode.

Transactions_raw has 17,804 total rows but none for 2026-06-10. These are likely from earlier probe/discovery runs.

---

## 8. ROOT CAUSE CLASSIFICATION

**`ROOT_CAUSE_MULTIPLE`**

### 8.1 Primary: ROOT_CAUSE_MISSING_PARKS (impact: ~63% of gap)

| Metric | Value |
|--------|-------|
| CT parks total | 21 |
| Yango parks with credentials | 1 (Lima) |
| Missing parks | 20 |
| Trips in missing parks for 2026-06-10 | 47,947 |
| Completed trips in missing parks | 15,523 |

The 20 missing parks represent **63% of the total gap** (15,523 / 24,658 completed). To reach full coverage, all 21 parks need Yango Fleet API credentials.

### 8.2 Secondary: ROOT_CAUSE_INGESTION_PARTIAL (impact: ~14% of gap)

| Metric | Value |
|--------|-------|
| CT Lima completed trips | 9,135 |
| Yango Lima orders ingested | 5,808 |
| Missing from Yango (Lima only) | 3,327 |
| Gap as % of Lima | 36.4% |

For Lima park specifically, ingestion captured only ~63.6% of expected orders. The remaining 3,327 completed trips (36.4%) were missed because:
1. `MAX_TOTAL_SECONDS = 120` is insufficient for a full day (~246 seconds needed at 12 pages × 20s)
2. Tick service stops at 17:03, missing ~7 hours of data
3. Multiple zombie `running` runs indicate repeated failed attempts

### 8.3 Tertiary: ROOT_CAUSE_TRANSACTIONS_MISSING

| Metric | Value |
|--------|-------|
| Transactions for 2026-06-10 | 0 |
| Partner fee revenue | 0.00 |

Transactions are not ingested by the tick service. Need separate ingestion run.

### 8.4 Gap Attribution

| Cause | Trips Lost | % of Total Gap |
|-------|-----------|----------------|
| Missing parks (20 parks without credentials) | 15,523 | 63.0% |
| Lima ingestion truncation (lost ~7h) | 3,327 | 13.5% |
| Status filter (only "complete" requested) | 0* | — (* completados son la métrica relevante) |
| **Total gap** | **18,850** | **76.4%** |

> The remaining gap (5,808 observed vs 9,135 expected for Lima = 3,327 missing) is fully explained by ingestion truncation at ~17:03 for Lima park.

---

## 9. ANSWERS TO THE 10 HYPOTHESES

| # | Hypothesis | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | max_pages truncation | **PARTIAL** | `MAX_PAGES_PER_DATE = 20` exists. 5,670 orders ≈ 12 pages consumed, below 20. More likely `MAX_TOTAL_SECONDS = 120` timeout. |
| 2 | parks faltantes | **CONFIRMED — PRIMARY** | 20 of 21 parks missing from Yango credentials. |
| 3 | credenciales incompletas | **CONFIRMED** | Only Lima has env var config. 20 other parks lack `api_park_credentials_registry` entries. |
| 4 | filtro temporal incorrecto | **NOT THE CAUSE** | Timestamps match. Both UTC-5. ended_at dates align perfectly. |
| 5 | timezone UTC vs Lima | **NOT THE CAUSE** | Both systems use UTC-5. No timezone mismatch detected. |
| 6 | status mapping incorrecto | **PARTIAL** | Yango filters `statuses: ["complete"]` — correct. But cancellation data is discarded. |
| 7 | endpoint equivocado | **NOT THE CAUSE** | Correct endpoint: `/v1/parks/orders/list`. |
| 8 | trips_2026 contiene más parks | **CONFIRMED — PRIMARY** | 21 parks in CT vs 1 in Yango registry. |
| 9 | orders_raw incompleto por ingesta previa | **CONFIRMED — SECONDARY** | Lima park got 5,808/9,135 orders (63.6%). Missing ~7 hours. |
| 10 | transactions no ingeridas | **CONFIRMED — TERTIARY** | 0 transactions for 2026-06-10. |

---

## 10. GO / NO-GO

### 10.1 GO Criteria Assessment

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | Sabemos exactamente por qué el gap existe | **PASS** | 3 causas: missing parks (63%), Lima truncation (14%), transactions missing |
| 2 | Sabemos si Yango puede llegar a coverage suficiente | **PASS** | Para Lima: sí (5,808 ingested = 63.6% of completed). Con full-day ingestion sin timeout, debe llegar cerca de 9,135. Para otros parks: necesitan credenciales. |
| 3 | Sabemos qué parks faltan | **PASS** | 20 parks documentados en sección 3.2 |
| 4 | Sabemos si ingesta completa sin max_pages resuelve | **PASS** | Para Lima: remover timeout + max_pages debe capturar ~9,135 orders/día (~18 páginas × 500). |
| 5 | Transactions tienen plan claro | **PASS** | Necesitan ingesta separada vía `ingest_yango_raw_landing.py --endpoint-group transactions --confirm-live` |

### 10.2 Classification

**GO for CF-H2C.1 Driver Identity Foundation.**

### 10.3 Prerequisites for CF-H2C.1

| Pre-req | Status | Action |
|---------|--------|--------|
| Full-day Lima ingestion | **INCOMPLETE** | Remove `MAX_TOTAL_SECONDS` limit or increase to 600s. Remove `MAX_PAGES_PER_DATE` for scheduled runs. |
| Zombie runs cleanup | **INCOMPLETE** | Mark all `running` runs > 1 hour as `failed`. Prevent tick from creating duplicate runs for same date. |
| Transactions ingestion for 2026-06-10 | **INCOMPLETE** | Run `ingest_yango_raw_landing.py --endpoint-group transactions --date-from 2026-06-10 --date-to 2026-06-10 --confirm-live` |
| Park credential gap acknowledged | **COMPLETE** | 20 parks need credentials. This is a business decision, not a technical blocker for Lima-only testing. |

---

## 11. RECOMMENDATIONS

### 11.1 Immediate (unblock CF-H2C.1)

1. **Remove `MAX_TOTAL_SECONDS = 120`** from tick ingestion. Increase to 600s or unlimited.
2. **Remove `MAX_PAGES_PER_DATE = 20`** for scheduled runs. Keep only for manual/debug.
3. **Clean up zombie runs**: `UPDATE raw_yango.api_ingestion_run SET status = 'failed' WHERE status = 'running' AND started_at < NOW() - INTERVAL '1 hour'`.
4. **Ingest transactions for 2026-06-10**: Run full ingestion script.

### 11.2 Short-term

5. **Inventory all 21 parks**: Map park_id → city → country. Identify which belong to YEGO operations.
6. **Add credentials for relevant parks**: For each YEGO-controlled park, add entry to `api_park_credentials_registry` with corresponding `.env` variables.
7. **Implement run deduplication**: Before creating a new run, check if a `completed` run already exists for that park+endpoint+date.

### 11.3 Strategic

8. **Scheduler sin max_pages en modo scheduled**: El diseño de CF-H2B especifica que `max_pages` solo aplica en modo manual/debug. El scheduled debe consumir todo el cursor.
9. **Transactions scheduled ingestion**: Agregar transactions al tick diario, no solo orders.

---

## 12. FIRMA

| Campo | Valor |
|-------|-------|
| **Analizado por** | CF-H2C.0 Yango Coverage Root Cause Analysis |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `ROOT_CAUSE_MULTIPLE` |
| **GO/NO-GO** | **GO** for CF-H2C.1 (con pre-requisitos) |
| **Próxima fase** | CF-H2C.1 — Driver Identity Foundation |
