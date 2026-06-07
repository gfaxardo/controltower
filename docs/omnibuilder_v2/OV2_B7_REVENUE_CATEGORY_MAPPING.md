# OV2-B.7 — REVENUE CATEGORY MAPPING AUDIT

> **Date:** 2026-06-06
> **Source:** `raw_yango.transactions_raw` (Yango Transactions API v2)
> **Park:** Lima (`08e20910...`)
> **Categories discovered:** 19

---

## 1. CATEGORY CLASSIFICATION

### 1.1 REVENUE_YEGO — Partner earned revenue

| Category | Count | Total Amount | ABS Amount | Avg/Txn |
|----------|-------|-------------|------------|---------|
| **Partner fee for trip** | 3,829 | -1,593.21 | **1,602.76** | 0.4184 |

**Formula:** `REVENUE_YEGO = SUM(|Partner fee for trip amount|)`
**Per-order:** 0.4076 PEN (1,256.37 / 3,003 unique orders for Jun 4)

This is the ONLY category that represents YEGO revenue from completed trips. The amount is negative in the API (deduction from driver wallet), so `ABS()` is required for revenue calculation.

### 1.2 PLATFORM_FEE — Yango platform commission

| Category | Count | Total Amount |
|----------|-------|-------------|
| Service fee for trip | 3,829 | -4,571.73 |
| Service fee for My Destinations and My Neighborhood modes | 941 | -521.67 |
| Partner fee for top-up | 107 | -66.04 |
| Partner transfer fee | 106 | -34.74 |

**Total platform fees:** -5,194.18 PEN

These are amounts taken by Yango/Yandex. NOT YEGO revenue.

### 1.3 PLATFORM_FEE_VAT

| Category | Count | Total Amount |
|----------|-------|-------------|
| Service fee, VAT | 3,827 | -822.87 |

VAT on platform fees.

### 1.4 GMV — Gross Merchandise Value (customer payments)

| Category | Count | Total Amount |
|----------|-------|-------------|
| Cash | 3,246 | 43,968.70 |
| Card payment | 524 | 6,443.20 |
| Corporate payment | 113 | 2,083.70 |
| Top-up via payment system | 107 | 1,197.04 |
| Paid with promo code | 5 | 38.70 |
| Manual charges | 17 | 133.00 |
| Tip | 9 | 11.03 |

**Total GMV:** 53,875.37 PEN

### 1.5 BONUS — Driver incentives

| Category | Count | Total Amount |
|----------|-------|-------------|
| Bonus | 193 | 305.89 |
| Promo code discount compensation | 609 | 1,025.30 |

**Total bonuses:** 1,331.19 PEN

### 1.6 ADJUSTMENT — Corrections and one-offs

| Category | Count | Total Amount |
|----------|-------|-------------|
| Bonus adjustment | 189 | -29.37 |
| Trip payment compensation | 15 | -52.00 |

### 1.7 REFUND — User cancellations

| Category | Count | Total Amount |
|----------|-------|-------------|
| Reimbursement for user cancellations | 32 | 132.53 |

### 1.8 TRANSFER — Wallet movements (non-revenue)

| Category | Count | Total Amount |
|----------|-------|-------------|
| Transfer | 106 | -2,949.26 |

---

## 2. MAPPING TO CT REVENUE

| CT Metric | API Source | Formula |
|-----------|-----------|---------|
| `revenue_yego_final` | Partner fee for trip | `SUM(|amount|)` |
| `revenue_yego_net` | Partner fee for trip - Service fee for trip - Service fee, VAT | `SUM(|partner_amount|) - |SUM(service_fee + vat)|` |
| `gmv` | Cash + Card payment + Corporate payment + Tip | `SUM(amount)` |

---

## 3. KEY FINDINGS

### 3.1 Partner fee for trip IS the YEGO revenue

Each `Partner fee for trip` transaction represents the commission YEGO earned from a driver's trip. The amount is negative (deduction from driver wallet). For revenue purposes, `ABS()` is applied.

### 3.2 Partner fee maps 1:1 with orders

- 3,829 partner fee transactions
- 3,826 negative (revenue) + 3 positive (reversals)
- Links to 2,998 unique orders for Jun 4
- Revenue per order: ~0.408 PEN

### 3.3 Platform fee vs Partner fee

| Type | Amount/Trip | Who Pays |
|------|------------|----------|
| Partner fee for trip | ~0.418 | YEGO earns from driver |
| Service fee for trip | ~1.194 | Driver pays Yango |
| Service fee, VAT | ~0.215 | Driver pays (tax) |

The relationship: `Partner fee + Service fee + VAT ≈ total driver deduction per trip (~1.827 PEN)`

### 3.4 Currency

All transactions for Lima park are in `PEN` (Peruvian Soles). No mixed-currency revenue.

### 3.5 GMV vs Revenue

Total GMV (customer paid): ~53,875 PEN/day
Total YEGO revenue: ~1,257 PEN/day
Revenue rate: ~2.33% of GMV

---

## 4. CATEGORY COMPLETENESS

| Required Category | Found? | In Code? |
|------------------|--------|----------|
| Partner fee for trip | YES (REVENUE_YEGO) | YES - filter in MV |
| Service fee for trip | YES (PLATFORM_FEE) | YES - filter in MV |
| Service fee, VAT | YES (PLATFORM_FEE_VAT) | YES - filter in MV |
| Cash | YES (GMV) | YES - filter in MV (combined with Card) |
| Card payment | YES (GMV) | YES - filter in MV (combined with Cash) |
| Promo code discount compensation | YES (BONUS) | YES - filter in MV |
| refunds | YES - `Reimbursement for user cancellations` | NOT in MV |
| adjustments | YES - `Bonus adjustment` + `Trip payment compensation` | PARTIALLY - `adjustments_amount` catches "everything else" |
| bonuses | YES - `Bonus` + `Promo code discount compensation` | PARTIALLY |

---

## 5. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| New categories appear in API | MEDIUM | MV filters use exclusion (NOT IN list) for adjustments — new categories fall into `adjustments_amount` by default |
| Category names change in API | HIGH | Validate category_name against known list; alert if unknown |
| Reversals (positive Partner fee) inflate ABS | LOW | 3 out of 3,829 = 0.08%, negligible impact |
| operational_date partition mismatch | MEDIUM | Transactions may have operational_date != event_at date; MV must use operational_date for daily aggregation |

---

## 6. OUTPUT FILES

- `backend/exports/audits/omniview_v2_shadow/revenue_category_inventory.csv` — Full category breakdown
