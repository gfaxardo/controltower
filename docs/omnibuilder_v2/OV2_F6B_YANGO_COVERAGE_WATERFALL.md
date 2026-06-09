# OV2-F.6B — YANGO COVERAGE WATERFALL

> **Date:** 2026-06-08
> **Status:** WATERFALL DOCUMENTED

## COVERAGE CHAIN

```
Yango Fleet API (fleet-api.yango.tech)
  ↓  POST /v1/parks/orders/list
  ↓  --max-pages=10 → LIMITED to 10 pages
raw_yango.orders_raw
  → 12,087 rows (3 dates, 1 park)
  → 1,000 rows for target park+date
  → 100% `order_status='complete'`
  → Coverage: 12,303 CT trips → only 1,000 captured (8.1%)
  ↓  REFRESH MATERIALIZED VIEW
raw_yango.mv_orders_day
  → 3 rows (1 per date, 1 park)
  → 1,000 orders_completed for target date
  → 468 unique_drivers
  → 100% accurate vs raw (no MV data loss) ✅
  ↓  RECONCILIATION ENDPOINT
GET /ops/omniview-v2/reconciliation/park
  → CT=12,303 vs Yango=1,000
  → MAJOR_DELTA (+1130%)
  → Status correct: Yango data incomplete
```

## PER-LAYER COVERAGE

| Layer | Rows | Max Date | Coverage % | Parks | Drivers |
|-------|------|----------|------------|-------|---------|
| Yango API | Unknown | 2026-06-06 | Partial (10 pages) | 1 | — |
| orders_raw | 12,087 | 2026-06-06 | 100% of fetched | 1 | 468 |
| mv_orders_day | 3 | 2026-06-06 | 100% of raw | 1 | 468 |
| Reconciliation | — | — | 8.1% of CT | 1/22 | 468/1,481 |

## BOTTLENECK

**Layer 1: Yango API ingestion** — `--max-pages=10` limits data fetch. Increasing to unlimited would capture ~12,000+ orders, bringing Yango closer to CT numbers.

---

*End of Coverage Waterfall*
