# Revenue Field Classification — Final Decision

**Generated:** 2026-06-05T00:19:31.089166-05:00

**Date Range:** 2026-06-01 -> 2026-06-04

---

## 1. Final Classification

| Field | Class | Conf | Action |
|-------|-------|------|--------|
| `orders.price` | **GMV_ONLY** | HIGH | Use as GMV. Do NOT map to revenue_yego. |
| `orders.trip_count` | **NEEDS_MORE_EVIDENCE** | MEDIUM | Monitor. More data needed for final classification. |
| `orders.driver_count` | **NEEDS_MORE_EVIDENCE** | LOW | Monitor. More data needed for final classification. |

---

## 2. Revenue Formula Recommendation

```
api_gmv                 = SUM(orders.price)                          # GMV
api_partner_revenue     = SUM(txn[partner_rides].amount)             # partner earnings
api_platform_commission = SUM(txn[platform_fees].amount)             # Yango's cut
api_partner_fees        = SUM(txn[partner_fees].amount)             # driver fees (EXCLUDE)

# Check: api_gmv ~= api_partner_revenue + api_platform_commission
# Map:   revenue_yego_final ~= api_partner_revenue
```

---

## 3. Evidence Summary

| Evidence | Value |
| API GMV | 0.00 |
| CT revenue_yego_final | 16,151.06 |
| Platform take (GMV - revenue) | -16,151.06 (0%) |
| API partner_rides total | 0.00 |
| API platform_fees total | 0.00 |
| partner_rides + platform_fees | 0.00 |
| GMV - (pr + pf) | 0.00 |

---

## 4. Recommendations

1. **Use `orders.price` as GMV.** Top-line trip value, NOT for revenue_yego.
2. **Use `txn[partner_rides].amount` as revenue_yego_final candidate.**
3. **Store `txn[platform_fees].amount` as platform commission separately.**
4. **EXCLUDE `txn[partner_fees]` from revenue.** Driver wallet adjustments.
5. **EXCLUDE bonuses/tips/promotions from base revenue.** Flag as adjustments.
6. **Run reconciliation weekly** to detect schema changes or drift.