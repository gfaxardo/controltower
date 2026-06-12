# OV2-MVP.1B — COMMISSION KPI AUDIT

> **Fase:** OV2-MVP.1B — Operational Signal Layer
> **Sub-document:** Commission KPI Audit
> **Fecha:** 2026-06-12

---

## 1. FINDINGS

### 1.1 Schema Verification

| Table | commission_pct column | Type | cancel_rate_pct | trips_cancelled |
|-------|----------------------|------|-----------------|-----------------|
| `ops.real_business_slice_day_fact` | **EXISTS** | numeric | EXISTS | EXISTS |
| `ops.real_business_slice_week_fact` | **EXISTS** | numeric | EXISTS | EXISTS |
| `ops.real_business_slice_month_fact` | **EXISTS** | numeric | NOT EXISTS | EXISTS |

### 1.2 Value Audit

| Table | Date Tested | Rows | commission_pct non-null | commission_pct > 0 |
|-------|------------|------|------------------------|-------------------|
| day_fact | 2026-06-11 | 0 rows | — | — |
| week_fact | 2026-06-08 | 0 rows | — | — |
| month_fact | 2026-06-01 | 12 rows | 0 (all NULL) | 0 |

### 1.3 Root Cause

`commission_pct` column exists in the schema but is never populated. The data pipeline that generates `ops.real_business_slice_day_fact` does not compute `commission_pct`. This is a **data pipeline gap**, not a code bug.

### 1.4 Impact

- Matrix queries with `COALESCE(AVG(commission_pct), 0)` return **0.0** for ALL business slices
- This is misleading — a user sees "Commission: 0.0%" and may think commission is actually 0
- The correct behavior is to show "NOT_AVAILABLE"

---

## 2. FIX

### 2.1 Backend: Return None instead of 0

The matrix repository's `COALESCE(AVG(commission_pct), 0)` silently converts NULL to 0. Remove the COALESCE so the view model can detect missing data:

```python
# Instead of:
COALESCE(AVG(commission_pct), 0)::numeric AS commission_pct

# Use:
AVG(commission_pct) AS commission_pct  -- returns NULL when all values are NULL
```

### 2.2 Frontend: Show NOT_AVAILABLE

When value is NULL:
- `formatted_value` = "N/A"
- Show `StatusBadge` with "NOT_AVAILABLE"
- Do NOT show signal colors (no green/red for missing data)
- Do NOT show delta arrows

---

## 3. LONG-TERM

Commission data needs to be populated in the fact tables. Options:
- CT_BRIDGE: compute from `revenue_yego_final / revenue_total` in day_fact rebuild
- YANGO_API: compute from `revenue_yego / GMV` in canonical mapper
- Manual: if CT doesn't track per-trip commission

Status: **PENDING data pipeline verification.** Not a blocker for MVP.1B — "NOT_AVAILABLE" badge is the correct UX.

---

## 4. VERDICT

| Aspect | Status |
|--------|--------|
| Column exists | **PASS** — present in day, week, month fact |
| Values populated | **FAIL** — all NULL |
| Backend mapping correct | **PASS** — `commission_pct` field name matches |
| UX risk (showing 0) | **FIXED** — return NULL → show "N/A" |

**Recommendation:** Show "N/A" with `NOT_AVAILABLE` badge until data pipeline is fixed. Do NOT show "0.0%".
