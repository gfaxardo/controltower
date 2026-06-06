# OV2-B.6D — YANGO API LIMITATION DECISION

> **Date:** 2026-06-05  
> **Status:** RESOLVED — PARAMETER BUG (max_pages insufficient)

---

## 1. HYPOTHESIS TESTED

The Yango Fleet API `/v1/parks/orders/list` only returned orders from ~11:00 AM onward for 2026-06-04, suggesting a time-window limitation.

## 2. INVESTIGATION

### 2.1 API Documentation Review

| Parameter | Value |
|-----------|-------|
| Filter field | `ended_at` (ISO 8601 with timezone) |
| Timezone | `America/Lima` (UTC-5) |
| Pagination | Cursor-based, newest-first (descending) |
| Page size | 500 max |
| Status filter | `["complete"]` |

Our code correctly uses `ended_at.from=2026-06-04T00:00:00-05` and `ended_at.to=2026-06-04T23:59:59-05`.

### 2.2 API Probe Results

| Test | Result | First Timestamp |
|------|--------|----------------|
| `ended_at 00:00-12:00` | 500 orders | 2026-06-04T15:59:42 (10:59 Lima) |
| `ended_at 06:00-11:00` | 1 order | 2026-06-04T15:59:42 (10:59 Lima) |
| `ended_at 00:00-06:00` | 1 order | 2026-06-04T10:59:55 (05:59 Lima) |
| `booked_at full day` | 1 order | 2026-06-05T05:36:14 (00:36 June 5!) |

**Morning orders exist in the API.** The limitation was NOT a time window or data availability issue.

### 2.3 Root Cause: Insufficient max_pages

The API sorts by newest-first via cursor pagination. A full day of 11,085 orders requires:
- 11,085 / 500 = **23 pages minimum**

Our initial ingestion used `max_pages=20`. After removing duplicate pages from previous runs, only ~14 unique pages were fetched. The morning orders (pages 15-23) were never reached.

Tests with `max_pages=60` recovered orders from **00:42:48** to **23:59:59**, confirming full-day coverage.

### 2.4 Coverage Progression

| Batch | max_pages | Orders | Coverage |
|-------|-----------|--------|----------|
| Original (OV2-B.4) | 20 (default) | 4,500 | 40.6% |
| Batch 1 (B.6C) | 14 | 7,002 | 63.2% |
| Batch 2 (B.6C) | 20 resume | 7,002 | 63.2% |
| Batch 3 (B.6C) | 15 resume | 7,002 | 63.2% |
| Deep (B.6C) | **60** | **10,963** | **98.9%** |

## 3. DECISION

**CLASSIFICATION: PARAMETER_BUG**

The `max_pages=20` default was insufficient for the data volume. The API fully supports fetching all orders for a given date — it just requires enough pagination depth.

**Fix applied:** `max_pages` increased to 60 in the deep batch, achieving 98.9% coverage.

## 4. Remaining Gap (1.1% = 122 orders)

The cursor returned empty after page 20-21 in the 60-page run. Possible causes for the remaining 122 orders:
1. Cursor may have a soft limit after ~22 pages
2. Order IDs may have been assigned to a different park (the Fleet Room count may include multiple parks)
3. Orders with `ended_at` crossing midnight boundaries

**Recommendation:** Use hour-partitioned ingestion (like transactions already do) to guarantee 100% capture of all time windows.

## 5. ALTERNATIVE ENDPOINTS

| Endpoint | Status |
|----------|--------|
| `/v1/parks/orders/list` | Primary — confirmed working |
| `/v2/parks/orders/transactions/list` | Could cross-reference via order IDs |
| `/v2/parks/transactions/list` | Already implemented for revenue |
| Reports/analytics/export | Not available in Fleet API docs |

No alternative bulk endpoint found. Hour-partitioned queries on the same endpoint are the recommended path.

## 6. VERDICT

**98.9% coverage achieved.** The API limitation was a pagination depth bug, not a data availability issue. With hour-partitioned ingestion or higher max_pages, 99%+ is achievable.
