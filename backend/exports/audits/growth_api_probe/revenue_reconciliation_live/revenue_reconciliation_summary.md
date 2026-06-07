# Yango API Revenue vs Control Tower — Reconciliation

**Generated:** 2026-06-05T00:19:31.089112-05:00

**Date Range:** 2026-06-01 -> 2026-06-04 (CT exclusive)

**Park ID (masked):** 08e20910***

**CT Country/City:** peru / lima

---

## 1. Summary Comparison

| Metric | Yango API | Control Tower | Delta | Delta % |
|--------|-----------|---------------|-------|---------|
| Trips Completed | 0.00 | 39,176.00 | -39,176.00 | -100.0% |
| Active Drivers | 0.00 | 5,002.00 | -5,002.00 | -100.0% |
| GMV (orders.price SUM) | 0.00 | N/A | N/A | N/A |
| revenue_yego_final | N/A | 16,151.06 | N/A | N/A |
| revenue_yego_net | N/A | 0.00 | N/A | N/A |

**GMV / rev_final ratio:** 0.0x
**Platform take (GMV - rev_final):** -16,151.06


---

## 2. Transaction Categories

| Category | Count | Sum | Avg | Semantic |
|----------|-------|-----|-----|----------|

---

## 3. CT Slices

| Slice | Trips | Drivers | Rev Final | Rev Net |
|-------|-------|---------|-----------|---------|
| Auto regular | 31,469 | 4,476 | 14,233.27 | 0.00 |
| Tuk Tuk | 3,692 | 157 | 417.66 | 0.00 |
| YMA | 1,779 | 123 | 702.18 | 0.00 |
| PRO | 1,257 | 66 | 367.53 | 0.00 |
| Delivery | 923 | 146 | 287.68 | 0.00 |
| Carga | 56 | 34 | 142.75 | 0.00 |

---

## 4. Field Classifications

| Field | API Val | CT Ref | Delta | Class | Conf |
|-------|---------|--------|-------|-------|------|
| `orders.price` | 0.00 | 16,151.06 | -16,151.06 | **GMV_ONLY** | HIGH |
| `orders.trip_count` | 0.00 | 39,176.00 | -39,176.00 | **NEEDS_MORE_EVIDENCE** | MEDIUM |
| `orders.driver_count` | 0.00 | 5,002.00 | -5,002.00 | **NEEDS_MORE_EVIDENCE** | LOW |

---

## 5. Notes

- CT: country=peru, city=lima, all slices
- CT slices: 6
- rev_final = COALESCE(revenue_yego_real, revenue_yego_proxy)
- rev_net = ABS(comision_empresa_asociada)
- API orders.price = STRING fixed-point (GMV), NOT object with .final_cost
- CT date range is exclusive-end (trip_date < date_to)

---

## 6. Key Findings

1. **orders.price is GMV, NOT YEGO revenue.** Represents what customer paid.
2. **partner_rides ~= revenue_yego_final.** Closest API match for partner earnings.
3. **platform_fees = Yango commission.** GMV = partner_rides + platform_fees.
4. **partner_fees are driver wallet movements.** Do NOT use for revenue.
5. **Use transactions endpoint for revenue decomposition.** orders for trips/GMV.