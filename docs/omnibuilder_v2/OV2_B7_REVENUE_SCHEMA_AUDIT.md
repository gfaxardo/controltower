# OV2-B.7 — REVENUE SCHEMA AUDIT

> **Date:** 2026-06-06
> **Motor:** Control Foundation / Revenue Serving Governance
> **Audit scope:** raw_yango.transactions_raw, mv_transactions_day, mv_revenue_day, Shadow API repository/service

---

## 1. TRANSACTIONS_RAW — Actual Columns

Schema: `raw_yango.transactions_raw` (verified via `information_schema.columns`)

| # | Column | Type | Description |
|---|--------|------|-------------|
| 1 | id | integer | PK |
| 2 | park_id | text | Park identifier |
| 3 | transaction_id | text | API transaction ID (UNIQUE with park_id) |
| 4 | event_at | timestamptz | Transaction event timestamp |
| 5 | category_id | text | API category ID (e.g. `partner_ride_fee`) |
| 6 | category_name | text | Human-readable category (e.g. `Partner fee for trip`) |
| 7 | group_id | text | Transaction group ID |
| 8 | amount | numeric | Transaction amount (negative = deduction, positive = credit) |
| 9 | currency_code | text | Currency code (e.g. `PEN`) |
| 10 | description | text | Transaction description |
| 11 | driver_profile_id | text | Driver UUID |
| 12 | order_id | text | Linked order UUID |
| 13 | created_by_identity | text | Who created the transaction |
| 14 | raw_payload | jsonb | Full API response payload |
| 15 | raw_payload_hash | text | SHA-256 of payload |
| 16 | api_fetched_at | timestamptz | When API was called |
| 17 | api_run_id | text | Ingestion run UUID |
| 18 | source_endpoint | text | API endpoint path |
| 19 | schema_version | text | Version of parser |
| 20 | inserted_at | timestamptz | Row insert time |
| 21 | updated_at | timestamptz | Row update time |
| 22 | operational_date | date | Derived date for partitioning |

**Key finding:** Columns `category_name`, `amount`, `currency_code`, `order_id`, and `event_at` all exist and are properly populated.

---

## 2. MV_REVENUE_DAY — Actual Columns

View: `raw_yango.mv_revenue_day` (created by migration 188, exists with data)

| # | Column | Type | Current Value (Jun 4) |
|---|--------|------|----------------------|
| 1 | park_id | text | 08e20910... |
| 2 | revenue_date | date | 2026-06-04 |
| 3 | currency | text | PEN |
| 4 | partner_fee_trip_amount | numeric | 1256.370 |
| 5 | partner_fee_trip_count | bigint | 3003 |
| 6 | service_fee_trip_amount | numeric | -3536.1412 |
| 7 | service_fee_vat_amount | numeric | -636.5048 |
| 8 | gmv_cash_card_amount | numeric | 39033.3 |
| 9 | promo_compensation_amount | numeric | 0 |
| 10 | adjustments_amount | numeric | 1026.5685 |
| 11 | revenue_candidate_amount | numeric | 1256.370 |
| 12 | revenue_candidate_count | bigint | 3003 |
| 13 | linked_orders | bigint | 2998 |
| 14 | revenue_per_order | numeric | 0.4076 |
| 15 | revenue_per_partner_fee_txn | numeric | 0.4184 |
| 16 | refreshed_at | timestamptz | 2026-06-05 21:39 |

---

## 3. WHERE `REVENUE_YEGO_PARTNER_FEE` APPEARS

| Location | Status |
|----------|--------|
| Migration 187 (`revenue_yego_partner_fee`) | **DEPRECATED** — superseded by migration 188 which renamed to `partner_fee_trip_amount` |
| Docs OV2_B2_RAW_YANGO_MV_DESIGN.md | Documentation-only reference |
| Docs OV2_B2_RAW_YANGO_MATERIALIZED_VIEWS.md | Documentation-only reference |
| Running DB (`raw_yango.mv_revenue_day`) | **DOES NOT EXIST** — column was renamed to `partner_fee_trip_amount` |

**Verdict:** `revenue_yego_partner_fee` does NOT exist in the live database. Any code referencing it will fail with `column does not exist`.

---

## 4. WHAT THE CODE EXPECTS

### Repository (`omniview_v2_shadow_repository.py`)

| Line | Column referenced | Actual MV column | Status |
|------|------------------|------------------|--------|
| 240 | `r.partner_fee_trip_amount AS revenue_partner_fee` | `partner_fee_trip_amount` | MATCH |
| 241 | `r.partner_fee_trip_count` | `partner_fee_trip_count` | MATCH |
| 242 | `r.revenue_per_order` | `revenue_per_order` | MATCH |
| 243 | `r.revenue_per_partner_fee_txn` | `revenue_per_partner_fee_txn` | MATCH |
| 272 | `partner_fee_trip_amount` | `partner_fee_trip_amount` | MATCH |
| 273 | `partner_fee_trip_count` | `partner_fee_trip_count` | MATCH |
| 274 | `service_fee_trip_amount` | `service_fee_trip_amount` | MATCH |
| 275 | `service_fee_vat_amount` | `service_fee_vat_amount` | MATCH |
| 276 | `gmv_cash_card_amount` | `gmv_cash_card_amount` | MATCH |
| 277 | `promo_compensation_amount` | `promo_compensation_amount` | MATCH |
| 278 | `adjustments_amount` | `adjustments_amount` | MATCH |
| 402 | `r.partner_fee_trip_amount` | `partner_fee_trip_amount` | MATCH |

**Verdict:** Repository column references match the actual MV. No code error found in current state.

### Service (`omniview_v2_shadow_service.py`)

| Line | Key read | Source | Status |
|------|---------|--------|--------|
| 84 | `r.get("revenue_partner_fee")` | Repository alias | MATCH |
| 98 | `kpis.revenue_partner_fee` | From service aggregation | MATCH |

**Verdict:** Service correctly reads the aliased column from the repository.

---

## 5. CORRECT COLUMN NAME

| Aspect | Value |
|--------|-------|
| Actual MV column | `partner_fee_trip_amount` |
| Canonical OV2 name (target) | `revenue_partner_fee_amount` |
| Repository alias | `revenue_partner_fee` |
| DO NOT USE | `revenue_yego_partner_fee` |

The canonical OV2 contract requires renaming `partner_fee_trip_amount` → `revenue_partner_fee_amount` in the MV. See TASK 3 for the migration.

---

## 6. DOES MV_REVENUE_DAY CONTAIN PARTNER FEE FOR TRIP?

**Yes.** Verified with live data:

```
partner_fee_trip_amount = 1256.370 PEN
partner_fee_trip_count  = 3003
revenue_per_order       = ~0.408 PEN
```

The `Partner fee for trip` category is correctly aggregated using `SUM(ABS(amount))` (absolute value of negative deduction amounts).

---

## 7. DOES TRANSACTIONS_RAW HAVE CATEGORY/GROUP/AMOUNT/CURRENCY?

**Yes.** All required fields exist and are populated:

| Field | Column name | Status |
|-------|------------|--------|
| Category | `category_name` | 19 distinct values |
| Category ID | `category_id` | System IDs (e.g. `partner_ride_fee`) |
| Group | `group_id` | Text field (often empty but present) |
| Amount | `amount` | Numeric, sign indicates credit/debit |
| Currency | `currency_code` | `PEN` (exclusive for Lima park) |

---

## 8. COLUMN MAPPING SUMMARY

| OV2 Canonical Name | Current MV Column | Transaction Category | Sign Handling |
|-------------------|-------------------|---------------------|---------------|
| revenue_partner_fee_amount | partner_fee_trip_amount | Partner fee for trip | ABS (positive) |
| revenue_partner_fee_count | partner_fee_trip_count | Partner fee for trip | COUNT |
| platform_fee_amount | service_fee_trip_amount | Service fee for trip | Raw (negative) |
| platform_fee_vat_amount | service_fee_vat_amount | Service fee, VAT | Raw (negative) |
| gmv_amount | gmv_cash_card_amount | Cash + Card payment | Raw (positive) |
| promo_compensation_amount | promo_compensation_amount | Promo code discount compensation | Raw |
| adjustments_amount | adjustments_amount | Everything else | Raw |
| revenue_per_order | revenue_per_order | Computed | revenue_partner_fee / linked_orders |

---

## 9. GAPS IDENTIFIED

| Gap | Severity | Fix |
|-----|----------|-----|
| MV uses `partner_fee_trip_amount` not `revenue_partner_fee_amount` | LOW | Rename in migration 190 |
| MV doesn't expose `revenue_source` field | MEDIUM | Add `'YANGO_TRANSACTIONS_API'` |
| MV doesn't expose `revenue_confidence` field | MEDIUM | Add `'AUDIT_CERTIFIED'` |
| `gmv_cash_card_amount` conflates Cash + Card | LOW | Split into `gmv_cash_amount` + `gmv_card_amount` |
| No `refunds_amount` column | MEDIUM | Extract from `Reimbursement for user cancellations` |
| No `total_transactions_count` separate | LOW | Already have `COUNT(*) AS total_txn_count` in migration 187 but lost in 188 |

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| Audit method | Direct `information_schema.columns` query + live data sampling |
| Date | 2026-06-06 |
| DB state | Migration 188 applied, MVs populated |
| Revenue data | Partner fee = 1256.37 PEN (3003 txns) for 2026-06-04 |
