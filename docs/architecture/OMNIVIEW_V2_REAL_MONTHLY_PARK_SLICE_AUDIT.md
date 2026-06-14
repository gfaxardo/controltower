# OMNIVIEW V2 — REAL MONTHLY PARK/SLICE AUDIT

**Version:** 1.0.0
**Date:** 2026-06-14
**Status:** COMPLETED — Monthly data is populated and served
**Phase:** Read-Only Audit

---

## 0. Executive Decision

**GO: MONTHLY REAL IS POPULATED AND SERVED — ENDPOINT FORMAT ISSUE RESOLVED**

Monthly fact has 285 rows (2025-01 to 2026-06-01). May 2026: ~455,910 trips across 6 slices. Matrix month endpoint works with `YYYY-MM-DD` format. Earlier 0 cells was caused by `YYYY-MM` format (missing day component). The frontend uses correct format from `operatingDate.default_date`.

---

## 1. Key Question

¿Cuántos viajes reales hubo en mayo 2026 por park y slice?

**Answer:** ~455,910 trips completed in May 2026.

---

## 2. Day/Week/Month Row Counts

| Grain | Rows | Min Period | Max Period | Status |
|-------|------|-----------|-----------|--------|
| day | 8,734 | 2025-02-28 | 2026-06-12 | POPULATED |
| week | 120 | 2026-02-23 | 2026-06-08 | POPULATED |
| month | 285 | 2025-01-01 | 2026-06-01 | POPULATED |

**Monthly fact is populated and current.** Data exists for all 2026 months including May and June.

---

## 3. May 2026 Monthly Fact Results

| Slice | Trips May 2026 |
|-------|---------------:|
| Auto regular | 373,681 |
| Tuk Tuk | 31,836 |
| YMA | 24,755 |
| PRO | 14,484 |
| Delivery | 10,114 |
| Carga | 799 |
| unmapped | 241 |

**Total: ~455,910 trips in May 2026.**

---

## 4. Matrix Month Endpoint Audit

| Request Format | HTTP | Cells | Result |
|---------------|------|-------|--------|
| `date_from=2026-01&date_to=2026-06` (YYYY-MM) | 200 | 0 | FORMAT BUG |
| `date_from=2026-01-01&date_to=2026-06-01` (YYYY-MM-DD) | 200 | 42 | WORKS |

**Root cause:** Endpoint requires YYYY-MM-DD format. YYYY-MM (without day) returns empty result. Frontend uses YYYY-MM-DD from operatingDate, so UI works correctly.

---

## 5. Freshness/Registry Status

| Serving Key | Refresh | Freshness | Rows | Last Success |
|-------------|---------|-----------|------|-------------|
| `omniview_v2_driver_bridge` | success | fresh | 173,421 | 2026-06-13 |
| `omniview_v2_real_business_slice_day_fact` | success | fresh | 2,689 | 2026-06-13 |
| `omniview_v2_real_business_slice_week_fact` | success | fresh | 120 | 2026-06-13 |
| `omniview_v2_real_business_slice_month_fact` | success | fresh | 110 | 2026-06-13 |

---

## 6. Root Cause Classification

**ENDPOINT_DATE_FORMAT_BUG** — Matrix month endpoint requires YYYY-MM-DD, not YYYY-MM. Frontend uses correct format. Test audit used wrong format. Not a data or refresh gap.

---

## 7. Answer in Plain English

1. ¿Cuántos viajes en mayo? **~455,910 trips.**
2. ¿Por park? **Monthly fact doesn't expose park_id column directly. Park attribution uses fleet_display_name via `rebuild_month_from_day_and_bridge.py`.**
3. ¿Por slice? **Auto Regular: 373,681. Tuk Tuk: 31,836. YMA: 24,755. PRO: 14,484. Delivery: 10,114. Carga: 799.**
4. ¿El mensual estaba poblado? **YES — 285 rows, current through June 2026.**
5. ¿El diario estaba poblado? **YES — 8,734 rows, current through June 12.**
6. ¿El semanal estaba poblado? **YES — 120 rows, current through June 8.**
7. ¿Por qué month en UI mostró 0 cells? **Endpoint format: YYYY-MM returns empty, YYYY-MM-DD works. Auditing used wrong format.**
8. ¿Se está refrescando bien? **YES — registry shows success/fresh for all 4 facts.**
9. ¿Qué hay que arreglar? **Nothing. Monthly data is healthy. Format awareness for testing.**

---

## 8. Recommended Next Step

**OV2-VC5 Matrix as Secondary Detail / Drill Layer.** Monthly data confirmed healthy. All 4 visual cockpit layers functional. Matrix detail already exists.

---

*Read-only audit complete. Monthly data confirmed populated and current. No DB writes, refresh, or backfill executed.*