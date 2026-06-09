# OV2-F.6B — ROOT CAUSE CLASSIFICATION

> **Date:** 2026-06-08
> **Status:** CLASSIFIED

## PRIMARY ROOT CAUSE

### API_PARTIAL — Yango ingestion truncated by `--max-pages=10`

**Evidence:**
- Yango raw: 1,000 orders for 2026-06-06
- CT bridge: 12,303 trips for same park+date
- Ingestion CLI ran with `--max-pages 10`
- Yango API paginates at 500 orders/page → max 5,000 orders per day with 10 pages
- Only 1,000 were returned (the API may return fewer per page)

**Impact:** 12.3× difference between CT and Yango

## RULED OUT

| Hypothesis | Evidence | Verdict |
|-----------|----------|---------|
| PARK_SCOPE_MISMATCH | Same park_id both sides | ❌ |
| DATE_WINDOW_MISMATCH | Same date (2026-06-06), Lima local = UTC-5 | ❌ |
| KPI_DEFINITION_MISMATCH | Both count completed trips/orders | ❌ |
| DRIVER_DEFINITION_MISMATCH | Similar semantics, different IDs | Minor |
| MV_FILTERING | MV = raw (1,000=1,000) | ❌ |
| CT_SCOPE_MISMATCH | CT reports Auto regular slice only | ❌ |

## VERDICT

**YANGO_INGESTION_PARTIAL** — The ingestion was limited by `--max-pages=10`. Full ingestion without page limits would bring Yango data to match CT scope.

---

*End of Root Cause Classification*
